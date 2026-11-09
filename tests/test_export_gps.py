"""M1.6: export di seduta "come da GPS" e adattatore. Andata e ritorno su tutte le sedute della stagione."""

import pandas as pd
import pytest

from vice.config import get_settings
from vice.data import zenodo
from vice.data.export_gps import ErroreExport, esporta_seduta, leggi_export
from vice.data.stagione import Stagione

STAGIONE = Stagione(zenodo.carica(get_settings().processed_dir / "zenodo"))
CONFRONTO = ["data", "giocatore_id", "ruolo", "tipo", "giorno_md", "titolare_ultima_partita",
             "td", "hsr", "spr", "acc", "dcc", "hmld"]


def _export(giorno):
    v = STAGIONE.al(giorno)
    return v, esporta_seduta(v.seduta_di_oggi, v.giocatori)


@pytest.mark.parametrize("giorno", STAGIONE.giorni_di_seduta, ids=lambda d: d.strftime("%Y-%m-%d"))
def test_andata_e_ritorno(giorno):
    v, testo = _export(giorno)
    letto = leggi_export(testo, STAGIONE)
    atteso = v.seduta_di_oggi[CONFRONTO].sort_values("giocatore_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(letto[CONFRONTO], atteso, check_dtype=False)


def test_l_export_non_contiene_ciò_che_il_gps_non_sa():
    _, testo = _export("2023-11-14")
    intestazione = testo.splitlines()[0]
    assert "MD" not in intestazione and "Starter" not in intestazione
    assert intestazione.startswith("Player Name,Session Date,Session Type")


def test_separatore_italiano_e_virgola_decimale():
    """Un export salvato da Excel in italiano: ";" come separatore e virgola decimale."""
    import io

    _, testo = _export("2023-11-14")
    df = pd.read_csv(io.StringIO(testo))
    df["Total Distance (m)"] = df["Total Distance (m)"] + 0.5
    italiano = df.to_csv(index=False, sep=";", decimal=",")
    assert ";" in italiano.splitlines()[0] and ",5;" in italiano
    letto = leggi_export(italiano.encode("utf-8-sig"), STAGIONE)
    assert sorted(letto["td"]) == sorted(df["Total Distance (m)"])


@pytest.mark.parametrize("modifica, messaggio", [
    (lambda t: "", "vuoto"),
    (lambda t: t.replace("Total Distance (m)", "Distanza"), "Mancano le colonne"),
    (lambda t: t.replace("Tommaso Ferrandi", "Mario Rossi"), "non in rosa"),
    (lambda t: t.replace("Training", "Match"), "giorno di allenamento"),
    (lambda t: t.replace("2023-11-14", "14/11/2023"), "AAAA-MM-GG"),
])
def test_errori_chiari(modifica, messaggio):
    _, testo = _export("2023-11-14")
    with pytest.raises(ErroreExport, match=messaggio):
        leggi_export(modifica(testo), STAGIONE)


def test_valori_negativi():
    _, testo = _export("2023-11-14")
    righe = testo.splitlines()
    campi = righe[1].split(",")
    campi[3] = "-5"
    righe[1] = ",".join(campi)
    with pytest.raises(ErroreExport, match="negativi"):
        leggi_export("\n".join(righe), STAGIONE)


def test_giorno_di_pausa():
    _, testo = _export("2023-11-14")
    with pytest.raises(ErroreExport, match="pausa"):
        leggi_export(testo.replace("2023-11-14", "2023-12-25"), STAGIONE)


# ---------- formato Zenodo: le righe del giorno copiate dal CSV originale (decisione 42) ----------

from vice.data.export_gps import formato, righe_zenodo  # noqa: E402

CSV_ZENODO = get_settings().raw_dir / "zenodo" / "DataSetTMr.csv"
serve_il_csv = pytest.mark.skipif(not CSV_ZENODO.exists(), reason="manca il CSV di Zenodo in data/raw")


@serve_il_csv
@pytest.mark.parametrize("giorno", STAGIONE.giorni_di_seduta, ids=lambda d: d.strftime("%Y-%m-%d"))
def test_andata_e_ritorno_dal_csv_di_zenodo(giorno):
    """Le righe originali di ogni seduta, rilette dall'adattatore, sono identiche al formato Vice
    (titolare compreso: dall'ultima partita negli allenamenti, da ESTATUS nelle partite)."""
    testo = righe_zenodo(CSV_ZENODO, giorno)
    assert formato(testo.splitlines()[0].split(";")) == "zenodo"
    letto = leggi_export(testo, STAGIONE)
    atteso = STAGIONE.al(giorno).seduta_di_oggi[CONFRONTO].sort_values("giocatore_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(letto[CONFRONTO], atteso, check_dtype=False)


@serve_il_csv
def test_righe_zenodo_copiate_tali_e_quali():
    testo = righe_zenodo(CSV_ZENODO, "2024-04-18")
    originale = set(CSV_ZENODO.read_text(encoding="utf-8-sig").splitlines())
    righe = testo.splitlines()
    assert righe[0].startswith("FECHA;PlayerID;POS") and "RATIOTD" in righe[0]
    assert len(righe) == 16 and all(r in originale for r in righe)
    assert all(r.startswith("45400;") for r in righe[1:])          # 18/04/2024 come seriale di Excel


@serve_il_csv
def test_allenamento_zenodo_ignora_estatus():
    """Negli allenamenti ESTATUS può anticipare la formazione della partita successiva: si ignora."""
    testo = righe_zenodo(CSV_ZENODO, "2024-04-18")
    righe = testo.splitlines()
    tutti_titolari = [righe[0]] + [";".join(c if i != 7 else "T" for i, c in enumerate(r.split(";"))) for r in righe[1:]]
    a = leggi_export("\n".join(tutti_titolari), STAGIONE)["titolare_ultima_partita"].tolist()
    b = leggi_export(testo, STAGIONE)["titolare_ultima_partita"].tolist()
    assert a == b


@serve_il_csv
@pytest.mark.parametrize("modifica, messaggio", [
    (lambda r: [r[0]] + [x.replace("45400;2;", "45400;99;", 1) for x in r[1:]], "Codici di giocatore non in rosa"),
    (lambda r: r + [r[1].replace("45400;", "45399;", 1)], "una sola seduta"),
    (lambda r: [r[0]] + [x.replace("45400;", "18/04/2024;", 1) for x in r[1:]], "numero seriale di Excel"),
    (lambda r: [r[0].replace(";HSR;", ";ALTA;")] + r[1:], "Mancano le colonne del formato Zenodo"),
])
def test_errori_chiari_formato_zenodo(modifica, messaggio):
    righe = righe_zenodo(CSV_ZENODO, "2024-04-18").splitlines()
    with pytest.raises(ErroreExport, match=messaggio):
        leggi_export("\n".join(modifica(righe)), STAGIONE)


def test_csv_di_zenodo_mancante(tmp_path):
    with pytest.raises(ErroreExport, match="scarica_zenodo"):
        righe_zenodo(tmp_path / "manca.csv", "2024-04-18")
