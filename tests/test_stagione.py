"""M1.5: l'"oggi" simulato. Il test anti-futuro: Vice non deve mai vedere dati successivi all'oggi."""

import pandas as pd
import pytest

from vice.config import get_settings
from vice.data import zenodo
from vice.data.stagione import Stagione

DATI = zenodo.carica(get_settings().processed_dir / "zenodo")
STAGIONE = Stagione(DATI)
# tutti i giorni di seduta più alcuni giorni senza seduta (pause, prima e dopo la stagione)
GIORNI = list(DATI.sedute["data"]) + [pd.Timestamp(x) for x in
                                      ("2023-09-01", "2023-12-25", "2024-01-01", "2024-05-20")]


@pytest.mark.parametrize("oggi", GIORNI, ids=lambda d: d.strftime("%Y-%m-%d"))
def test_anti_futuro(oggi):
    v = STAGIONE.al(oggi)
    assert (v.storico["data"] < oggi).all()
    assert (v.seduta_di_oggi["data"] == oggi).all()
    assert (v.sedute["data"] <= oggi).all()
    assert (v.partite_giocate["data"] <= oggi).all()
    assert list(v.calendario.columns) == ["data"]          # del futuro si vedono solo le date delle partite
    for tabella in (v.storico, v.seduta_di_oggi):
        assert not any(c.startswith("rapporto_") or c == "estatus_dataset" for c in tabella.columns)


def test_cambiare_il_futuro_non_cambia_l_oggi():
    """Trappola: se si stravolgono i dati dopo l'oggi, ciò che Vice vede resta identico."""
    oggi = pd.Timestamp("2024-01-24")
    futuro = DATI.carichi["data"] > oggi
    alterati = DATI.carichi.copy()
    alterati.loc[futuro, ["td", "hsr", "spr"]] *= 1000
    alterati.loc[futuro, "titolare_ultima_partita"] = ~alterati.loc[futuro, "titolare_ultima_partita"]
    altra = Stagione(zenodo.DatiZenodo(DATI.partite, DATI.sedute, alterati, DATI.giocatori))
    a, b = STAGIONE.al(oggi), altra.al(oggi)
    pd.testing.assert_frame_equal(a.storico, b.storico)
    pd.testing.assert_frame_equal(a.seduta_di_oggi, b.seduta_di_oggi)


def test_seduta_di_oggi():
    v = STAGIONE.al("2023-09-10")                          # prima partita della stagione
    assert len(v.storico) == 0
    assert len(v.seduta_di_oggi) > 0 and set(v.seduta_di_oggi["tipo"]) == {"partita"}


def test_contesto_coerente_con_il_dataset():
    for r in DATI.sedute.itertuples():
        assert STAGIONE.contesto(r.data).giorno_md == r.giorno_md, r.data


def test_contesto_nei_giorni_di_pausa():
    c = STAGIONE.contesto("2023-12-25")                    # pausa invernale
    assert c.giorno_md is None
    assert c.ultima_partita == pd.Timestamp("2023-12-16")
    assert c.prossima_partita == pd.Timestamp("2024-01-07")
