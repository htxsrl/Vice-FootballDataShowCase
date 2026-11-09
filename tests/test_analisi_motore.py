"""M2.12: il motore sui dati veri. Anti-futuro, casi d'oro ricalcolati a mano, regole degli spunti."""

import json
import re

import numpy as np
import pandas as pd
import pytest

from vice.analysis.fasce import K_PESO, MIN_CASI_PERSONALE, TUTTI, Riferimenti, fascia_attesa, tolleranza
from vice.analysis.giocatore import andamento, confronta
from vice.analysis.limiti import LIMITI, limiti
from vice.analysis.motore import analisi_per_report
from vice.analysis.partita import allenamento_partita, riferimenti_partita
from vice.analysis.seduta import seduta
from vice.analysis.settimana import compensazione, esposizione_velocita, forma_settimana
from vice.analysis.spunti import MAX_PER_REGOLA, MAX_SPUNTI
from vice.config import get_settings
from vice.data import zenodo
from vice.data.stagione import Stagione

DATI = zenodo.carica(get_settings().processed_dir / "zenodo")
STAGIONE = Stagione(DATI)
C = DATI.carichi
SANTINI = 13                                   # centrocampista
GIORNI_CAMPIONE = ["2023-10-18", "2023-11-23", "2024-01-08", "2024-01-10", "2024-02-14", "2024-03-15",
                   "2024-03-17", "2024-04-18", "2024-04-19", "2024-05-09"]


# ---------- anti-futuro ----------

@pytest.mark.parametrize("oggi,tipo", [("2024-01-10", "seduta"), ("2024-03-17", "settimana"), ("2024-04-18", "giocatore")])
def test_cambiare_il_futuro_non_cambia_le_analisi(oggi, tipo):
    """Trappola: si stravolgono i dati dopo l'oggi; ogni analisi, evidenza e spunto resta identico."""
    futuro = C["data"] > pd.Timestamp(oggi)
    alterati = C.copy()
    alterati.loc[futuro, ["td", "hsr", "spr", "acc", "dcc", "hmld"]] *= 1000
    alterati.loc[futuro, "titolare_ultima_partita"] = ~alterati.loc[futuro, "titolare_ultima_partita"]
    altra = Stagione(zenodo.DatiZenodo(DATI.partite, DATI.sedute, alterati, DATI.giocatori))
    a = analisi_per_report(STAGIONE.al(oggi), tipo, SANTINI).to_dict()
    b = analisi_per_report(altra.al(oggi), tipo, SANTINI).to_dict()
    assert json.dumps(a["analisi"], sort_keys=True) == json.dumps(b["analisi"], sort_keys=True)
    assert a["spunti"] == b["spunti"]
    # contro-prova: la trappola morde davvero, una settimana dopo le analisi cambiano
    dopo = pd.Timestamp(oggi) + pd.Timedelta(days=7)
    c = analisi_per_report(STAGIONE.al(dopo), tipo, SANTINI).to_dict()
    d = analisi_per_report(altra.al(dopo), tipo, SANTINI).to_dict()
    assert json.dumps(c["analisi"], sort_keys=True) != json.dumps(d["analisi"], sort_keys=True)


# ---------- casi d'oro: i numeri del motore ricalcolati qui con pandas ----------

def quantile_pesato(valori, pesi, p):
    d = pd.DataFrame({"v": valori, "w": pesi}).groupby("v")["w"].sum().sort_index()
    pos = 100 * (d.cumsum() - d / 2) / d.sum()
    return float(np.interp(p, pos.to_numpy(), d.index.to_numpy(dtype=float)))


def test_fascia_personale_ricalcolata():
    oggi = pd.Timestamp("2024-01-10")                     # MD-3
    prima = C[C["data"] < oggi]
    pers = prima[(prima["giocatore_id"] == SANTINI) & (prima["giorno_md"] == -3)]["td"].tolist()
    ruolo = prima[(prima["ruolo"] == "centrocampista") & (prima["giorno_md"] == -3)]["td"].tolist()
    assert len(pers) >= MIN_CASI_PERSONALE
    w = len(pers) / (len(pers) + K_PESO)
    pesi = [w / len(pers)] * len(pers) + [(1 - w) / len(ruolo)] * len(ruolo)
    t = fascia_attesa(STAGIONE.al(oggi), SANTINI).tabella.set_index("metrica")
    for p in (10, 25, 50, 75, 90):
        assert t.loc["td", f"p{p}"] == pytest.approx(quantile_pesato(pers + ruolo, pesi, p))
    assert t.loc["td", "casi"] == len(ruolo)              # le sedute personali stanno già nel ruolo


def test_seduta_valori_e_posizioni_coerenti():
    v = STAGIONE.al("2024-01-10")
    t = seduta(v).tabella
    oggi = C[C["data"] == v.oggi].set_index("giocatore_id")
    for r in t[t["posizione"] != "senza fascia"].itertuples():
        assert r.valore == oggi.loc[r.giocatore_id, r.metrica]
        if r.posizione == "molto sopra":
            assert r.valore > r.p90
        if r.posizione == "molto sotto":
            assert r.valore < r.p10
        if r.posizione == "dentro":
            t_ = tolleranza(r.metrica, r.p50)
            assert r.p25 - t_ <= r.valore <= r.p75 + t_


def test_riferimento_di_partita_ricalcolato():
    oggi = pd.Timestamp("2024-01-10")
    v = STAGIONE.al(oggi)
    rif = riferimenti_partita(v.storico, v.giocatori).set_index(["giocatore_id", "metrica"])
    tit = C[(C["data"] < oggi) & (C["giorno_md"] == 0) & C["titolare_ultima_partita"].fillna(False).astype(bool)]
    mie = tit[tit["giocatore_id"] == SANTINI]
    assert rif.loc[(SANTINI, "td"), "livello"] == "personale"
    assert rif.loc[(SANTINI, "td"), "riferimento"] == pytest.approx(mie["td"].mean())
    # Elia Gariglio (2) non parte mai titolare: si usa la media dei centrocampisti titolari
    assert rif.loc[(2, "hsr"), "livello"] == "ruolo"
    assert rif.loc[(2, "hsr"), "riferimento"] == pytest.approx(tit[tit["ruolo"] == "centrocampista"]["hsr"].mean())


def test_settimana_in_percentuale_della_partita():
    oggi = pd.Timestamp("2024-01-10")                     # settimana dal 07/01 (partita) al 13/01
    r = allenamento_partita(STAGIONE.al(oggi)).tabella.set_index(["giocatore_id", "metrica"])
    sett = C[(C["data"] > pd.Timestamp("2024-01-07")) & (C["data"] <= oggi) & (C["tipo"] == "allenamento")]
    somma = sett[sett["giocatore_id"] == SANTINI]["td"].sum()
    x = r.loc[(SANTINI, "td")]
    assert x["settimana"] == somma and x["settimana_pct"] == pytest.approx(100 * somma / x["riferimento"])


def test_forma_della_settimana_mediana_di_oggi():
    v = STAGIONE.al("2024-01-10")
    t = forma_settimana(v).tabella
    oggi = t[(t["data"] == v.oggi) & (t["metrica"] == "td")].iloc[0]
    assert oggi["mediana_squadra"] == C[C["data"] == v.oggi]["td"].median()


def test_esposizione_velocita_somme():
    v = STAGIONE.al("2024-04-18")                         # MD-2: finestra MD-4…MD-2 del 20/04 conclusa
    r = esposizione_velocita(v)
    assert r.sintesi["finestra_completa"]
    f = C[(C["data"] >= pd.Timestamp("2024-04-16")) & (C["data"] <= v.oggi) & C["giorno_md"].between(-4, -2)]
    t = r.tabella.set_index("giocatore_id")
    for gid, g in f.groupby("giocatore_id"):
        assert t.loc[gid, "spr"] == g["spr"].sum() and t.loc[gid, "sedute"] == len(g)
    # dato mancante ≠ zero: Basile ha dati per 1 seduta su 2, l'atteso è quello del suo giorno
    assert t.loc[18, "copertura"] == "parziale" and t.loc[18, "spr_posizione"] == "dentro"
    assert t.loc[8, "copertura"] == "nessun dato" and pd.isna(t.loc[8, "spr"])
    assert {q["giocatore_id"] for q in r.sintesi["copertura_incompleta"]} >= {8, 18}


def test_compensazione_riguarda_i_non_titolari_dell_ultima_partita():
    v = STAGIONE.al("2024-04-17")                         # MD-3; ultima partita 13/04
    r = compensazione(v)
    partita = C[(C["data"] == pd.Timestamp("2024-04-13")) & (C["giorno_md"] == 0)]
    titolari = set(partita.loc[partita["titolare_ultima_partita"].astype(bool), "giocatore_id"])
    assert r.sintesi["partita"] == pd.Timestamp("2024-04-13") and not r.sintesi["finestra_aperta"]
    assert len(r.tabella) and not (set(r.tabella["giocatore_id"]) & titolari)


def test_fotografia_2024_01_10():
    """Fotografia (regressione), presa il 22/10/2026 dopo la revisione: una seduta di MD-3 molto sotto
    il solito in distanza."""
    s = seduta(STAGIONE.al("2024-01-10")).sintesi
    assert s["giocatori"] == 18 and s["per_metrica"]["td"]["percentile_mediano"] == 10
    assert s["per_metrica"]["td"]["molto sotto"] == 5 and s["fuori_fascia"][0]["giocatore"] == "Gabriele Longo"


# ---------- le correzioni della revisione tecnica (22/10/2026) ----------

def test_partita_senza_dati_non_vale_zero():
    t = compensazione(STAGIONE.al("2024-03-13")).tabella.set_index("giocatore_id")
    assert not t.loc[2, "riga_partita"] and pd.isna(t.loc[2, "partita_hsr"]) and pd.isna(t.loc[2, "totale_hsr_pct"])


def test_decisione_27_niente_esenzione_sulla_distanza():
    # Santini dopo il 19/11: 66,7% della distanza in partita, ma non è più esentato
    t = compensazione(STAGIONE.al("2023-11-22")).tabella.set_index("giocatore_id")
    assert t.loc[13, "esito"] != "ha giocato molto" and not t.loc[13, "coperto_dalla_partita"]
    # Tosi dopo il 06/04: partita più postpartita al 117% del suo HSR → nessuno spunto
    t = compensazione(STAGIONE.al("2024-04-10")).tabella.set_index("giocatore_id")
    assert t.loc[15, "coperto_dalla_partita"] and t.loc[15, "totale_hsr_pct"] > 100
    for tipo in ("seduta", "settimana", "giocatore"):
        a = analisi_per_report(STAGIONE.al("2024-04-10"), tipo, 15)
        assert not [s for s in a.candidati if s.giocatore_id == 15 and s.regola == "compensazione"]


def test_lo_spunto_di_gruppo_non_cancella_quello_del_giocatore():
    v = STAGIONE.al("2024-03-11")                         # postpartita leggero per tutto il gruppo
    assert [s.regola for s in analisi_per_report(v, "settimana").spunti].count("compensazione_gruppo") == 1
    individuale = analisi_per_report(STAGIONE.al("2024-03-13"), "giocatore", 2).spunti
    assert [s.regola for s in individuale] == ["compensazione"]


def test_andamento_con_mediana_storica_zero():
    s = andamento(STAGIONE.al("2023-11-29"), 3).sintesi["per_metrica"]["spr"]
    assert s["scarto_mediano_pct"] is None and s["nota"] and s["descrizione"] == "più alto del suo solito"


def test_andamento_verdetto_e_scarto_dalle_stesse_sedute():
    """Decisione 55: Amato, sprint, al 18/04. Prima le sedute a MD-1 (solito zero, 0 contro 0) tiravano differenza e
    rango al centro e la vista diceva «in linea» con uno scarto del -80%; ora contano le sedute con un solito."""
    s = andamento(STAGIONE.al("2024-04-18"), 20).sintesi["per_metrica"]["spr"]
    assert s["descrizione"] == "più basso del suo solito" and s["scarto_mediano_pct"] == -80
    assert (s["sedute_usate"], s["sedute"]) == (6, 9) and s["percentile_mediano"] < 35


def test_fascia_pesata_coerente():
    f = Riferimenti(STAGIONE.al("2024-05-10").storico).fascia(19, "esterno", -1, TUTTI, "td")
    assert f.percentile(f.p50) == pytest.approx(50) and f.casi == 117 and f.casi_personali == 13


def test_report_della_seduta_solo_con_dati_di_oggi():
    """Nel report della seduta gli spunti citano la seduta di oggi (o la chiusura del postpartita)."""
    for oggi in STAGIONE.giorni_di_seduta[::4]:
        a = analisi_per_report(STAGIONE.al(oggi), "seduta")
        for s in a.spunti:
            if s.regola in ("seduta_squadra", "postpartita_titolari", "rifinitura", "consecutive"):
                assert any(f"/{oggi:%Y-%m-%d}/" in e for e in s.evidenze), (oggi, s.testo)


# ---------- tutti i giorni campione: niente errori, evidenze in ordine, spunti nelle regole ----------

VERBI = ("Valutare", "Verificare", "Approfondire")
VIETATE = ("meglio", "peggio", "infortun", "acwr", " deve ", "rischio")


@pytest.mark.parametrize("oggi", GIORNI_CAMPIONE)
@pytest.mark.parametrize("tipo", ["seduta", "settimana"])
def test_report_e_spunti(oggi, tipo):
    a = analisi_per_report(STAGIONE.al(oggi), tipo)
    json.dumps(a.to_dict())                                # tutto serializzabile
    ev = a.evidenze()
    ids = [e.id for r in a.analisi.values() for e in r.evidenze]
    assert len(ev) >= 1
    for r in a.analisi.values():
        assert len({e.id for e in r.evidenze}) == len(r.evidenze), r.analisi    # id unici dentro un'analisi
    assert len(a.spunti) <= MAX_SPUNTI
    regole = [s.regola for s in a.spunti]
    assert all(regole.count(x) <= MAX_PER_REGOLA for x in regole)
    for s in a.spunti:
        assert s.testo.startswith(VERBI), s.testo
        assert not any(p in s.testo.lower() for p in VIETATE), s.testo
        assert s.evidenze and all(e in ev for e in s.evidenze), (s.regola, s.evidenze)
        assert not any(ev[e].contesto.get("provvisoria") for e in s.evidenze), s.testo   # niente spunti da fasce provvisorie
    assert ids


NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def numeri_del_testo(testo: str) -> list[float]:
    """Numeri scritti all'italiana, tolte le date e i giorni MD."""
    testo = re.sub(r"\d{2}/\d{2}/\d{4}|MD[+-]\d", " ", testo)
    return [float(x.replace(".", "").replace(",", ".")) for x in NUMERO.findall(testo)]


def test_ogni_numero_degli_spunti_viene_dalle_evidenze():
    """Un giorno di seduta ogni cinque (su tutti i 151 passa, ma servono 2 minuti): la regola delle
    citazioni vale già per le frasi base degli spunti."""
    controllati = 0
    for oggi in STAGIONE.giorni_di_seduta[::5]:
        for tipo in ("seduta", "settimana"):
            a = analisi_per_report(STAGIONE.al(oggi), tipo)
            ev = a.evidenze()
            for s in a.spunti:
                ammessi = {x for e in s.evidenze for x in ev[e].numeri()}
                for n in numeri_del_testo(s.testo):
                    assert any(abs(n - x) < 1e-6 for x in ammessi), (oggi, s.testo, n)
                    controllati += 1
    assert controllati > 50


def test_inizio_stagione_senza_fasce():
    s = seduta(STAGIONE.al("2023-09-13"))
    assert set(s.tabella["posizione"]) == {"senza fascia"} and "inizio stagione" in s.avvisi[0]


def test_giorno_senza_seduta():
    v = STAGIONE.al("2023-12-25")
    assert seduta(v).avvisi and forma_settimana(v).avvisi == ["oggi è un giorno di pausa"]


def test_report_sconosciuto_o_senza_giocatore():
    v = STAGIONE.al("2024-01-10")
    with pytest.raises(ValueError):
        analisi_per_report(v, "mensile")
    with pytest.raises(ValueError):
        analisi_per_report(v, "giocatore")


# ---------- giocatore ----------

def test_andamento_e_confronto():
    v = STAGIONE.al("2024-03-20")
    a = andamento(v, SANTINI)
    assert a.sintesi["sedute_confrontate"] >= 4 and set(a.sintesi["per_metrica"]) == {"td", "hsr", "spr", "acc", "dcc", "hmld"}
    assert all(x["descrizione"].endswith("suo solito") for x in a.sintesi["per_metrica"].values())
    c = confronta(v, [18, 13, 4])
    assert c.sintesi["giocatori"] == ["Alessio Dalmasso", "Federico Santini", "Matteo Basile"]   # per numero di maglia
    assert "non una classifica" in c.avvisi[0]


# ---------- limiti ----------

def test_limiti():
    assert len(limiti().tabella) == len(LIMITI) == 15
    assert limiti("Qual è il rischio infortuni di Santini secondo l'ACWR?").sintesi["limiti"][0] == "rischio_infortuni"
    assert limiti("chi ha corso meglio?").sintesi["limiti"] == ["giudizio"]


@pytest.mark.parametrize("oggi", ["2023-11-02", "2024-02-01", "2024-03-07"])
def test_lo_spunto_di_velocita_non_segnala_chi_e_nella_norma(oggi):
    """Il 28/10/2026 la taratura degli avvisi ha trovato che un NaN in «sprint registrato» valeva vero: la regola
    segnalava tutti, anche chi aveva fatto più sprint del solito. Ora solo sprint nullo o molto basso, o molto sotto."""
    v = STAGIONE.al(oggi)
    tab = esposizione_velocita(v).tabella.set_index("giocatore")
    vel = [s for s in analisi_per_report(v, "seduta").candidati if s.regola == "velocita"]
    assert vel
    for s in vel:
        x = tab.loc[s.giocatore]
        assert pd.notna(x["sprint_registrato"]) or "molto sotto" in (x["spr_posizione"], x["hsr_posizione"]), s.testo
