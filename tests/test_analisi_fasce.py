"""M2.1-M2.2: fasce attese e posizioni, su dati sintetici con risultato noto."""

import numpy as np
import pandas as pd
import pytest

from vice.analysis.evidenze import arrotonda, evidenza, numero_it
from vice.analysis.comune import Settimana
from vice.analysis.fasce import (K_PESO, NON_TITOLARI, SCONOSCIUTO, TITOLARI, TUTTI, Distribuzione, Riferimenti,
                                 classifica, gruppo, posizione, rango_percentile, tolleranza)
from vice.analysis.partita import riferimenti_partita


def righe(giocatore, ruolo, giorno_md, valori, titolare=True, inizio="2024-01-01"):
    """Una riga per valore, un giorno diverso per ciascuna; le sei metriche uguali al valore."""
    date = pd.date_range(inizio, periods=len(valori), freq="7D")
    return pd.DataFrame({"data": date, "giocatore_id": giocatore, "ruolo": ruolo, "tipo": "allenamento",
                         "giorno_md": giorno_md, "titolare_ultima_partita": pd.array([titolare] * len(valori), dtype="boolean"),
                         **{m: np.asarray(valori, dtype=float) for m in ("td", "hsr", "spr", "acc", "dcc", "hmld")}})


def test_gruppo_decisione_25():
    assert gruppo(-3, True) == TUTTI and gruppo(-1, False) == TUTTI
    assert gruppo(0, True) == TITOLARI and gruppo(1, False) == NON_TITOLARI and gruppo(2, True) == TITOLARI
    assert gruppo(1, None) == SCONOSCIUTO and gruppo(1, pd.NA) == SCONOSCIUTO


def test_rango_percentile():
    a = np.array([1.0, 2, 3, 4])
    assert rango_percentile(0, a) == 0 and rango_percentile(5, a) == 100
    assert rango_percentile(2, a) == pytest.approx(37.5)      # 1 sotto + mezzo uguale, su 4
    assert np.isnan(rango_percentile(1, np.array([])))


def test_tolleranza_ibrida():
    """Decisione 28: il massimo tra un minimo assoluto e una quota della mediana."""
    assert tolleranza("hsr", 34) == 10 and tolleranza("hsr", 300) == pytest.approx(30)
    assert tolleranza("td", 3000) == 100 and tolleranza("td", 9000) == pytest.approx(270)
    assert tolleranza("spr", 0) == 5 and tolleranza("acc", 60) == pytest.approx(6)


def test_posizione_con_tolleranza():
    # fascia TD 4000-5000 (P25-P75), larga 3500-5500, mediana 4500: tolleranza max(100, 135) = 135 m
    assert posizione(5100, 3500, 4000, 4500, 5000, 5500, "td") == "dentro"       # sopra P75 ma entro la tolleranza
    assert posizione(5200, 3500, 4000, 4500, 5000, 5500, "td") == "sopra"
    assert posizione(5700, 3500, 4000, 4500, 5000, 5500, "td") == "molto sopra"
    assert posizione(3800, 3500, 4000, 4500, 5000, 5500, "td") == "sotto"
    assert posizione(3300, 3500, 4000, 4500, 5000, 5500, "td") == "molto sotto"


def test_fascia_del_ruolo_senza_parte_personale():
    st = pd.concat([righe(1, "terzino", -3, [100, 200, 300]), righe(2, "terzino", -3, [400, 500, 600])])
    f = Riferimenti(st).fascia(1, "terzino", -3, TUTTI, "td")
    assert f.riferimento == "ruolo" and f.peso_personale == 0 and f.casi == 6 and f.sedute == 3
    assert f.p50 == pytest.approx(350) and f.provvisoria                    # 3 sedute: si mostra, niente spunti


def quantile_pesato(valori, pesi, p):
    """Ricalcolo indipendente: posizione di ogni valore = cumulata fino a metà del suo peso."""
    d = pd.DataFrame({"v": valori, "w": pesi}).groupby("v")["w"].sum().sort_index()
    pos = 100 * (d.cumsum() - d / 2) / d.sum()
    return float(np.interp(p, pos.to_numpy(), d.index.to_numpy(dtype=float)))


def test_fascia_personale_fusa_col_ruolo():
    """Una sola distribuzione pesata: le 8 sedute personali pesano 8/16, il ruolo (che le contiene) il resto."""
    pers = list(range(1000, 1800, 100))                                    # 8 sedute personali
    st = pd.concat([righe(1, "terzino", -3, pers), righe(2, "terzino", -3, [100] * 8)])
    f = Riferimenti(st).fascia(1, "terzino", -3, TUTTI, "td")
    w = 8 / (8 + K_PESO)
    ruolo = pers + [100] * 8
    pesi = [w / 8] * 8 + [(1 - w) / 16] * 16
    for p in (10, 25, 50, 75, 90):
        assert getattr(f, f"p{p}") == pytest.approx(quantile_pesato(pers + ruolo, pesi, p))
    for p in (25, 50, 75, 90):     # quantili e ranghi coerenti (il P10 qui cade sugli otto 100, che pesano il 25%)
        assert f.percentile(getattr(f, f"p{p}")) == pytest.approx(p)
    assert f.peso_personale == pytest.approx(w) and f.livello == "personale e ruolo"
    assert f.casi_personali == 8 and f.casi == 16                          # le personali non si contano due volte


def test_distribuzione_coerente():
    """Rango e quantile sono l'uno l'inverso dell'altro dentro la distribuzione; agli estremi i
    valori ripetuti fanno da gradino (qui l'1 vale due casi su quattro: posizione 25)."""
    d = Distribuzione([1, 1, 2, 5])
    for p in (30, 50, 80):
        assert d.rango(d.quantile(p)) == pytest.approx(p)
    assert d.quantile(20) == 1 and d.rango(1) == 25
    assert d.rango(0) == 0 and d.rango(9) == 100


def test_ripiego_sulla_squadra_e_poi_niente():
    # ruolo con 2 casi: si passa alla squadra (6 casi da 4 giorni diversi)
    st = pd.concat([righe(1, "terzino", -3, [100, 200]), righe(2, "esterno", -3, [300, 400, 500, 600])])
    f = Riferimenti(st).fascia(1, "terzino", -3, TUTTI, "td")
    assert f.riferimento == "squadra" and f.casi == 6
    # 6 casi ma tutti dalla stessa seduta: niente fascia (servono 3 sedute diverse)
    una = pd.concat([righe(g, "terzino", -3, [100 * g]) for g in range(1, 7)])
    assert Riferimenti(una).fascia(1, "terzino", -3, TUTTI, "td") is None


def test_titolari_e_non_titolari_separati_dopo_la_partita():
    st = pd.concat([righe(1, "terzino", 1, [1000] * 6, titolare=True), righe(2, "terzino", 1, [5000] * 6, titolare=False)])
    r = Riferimenti(st)
    assert r.fascia(3, "terzino", 1, TITOLARI, "td").p50 == 1000
    assert r.fascia(3, "terzino", 1, NON_TITOLARI, "td").p50 == 5000
    assert r.fascia(3, "terzino", 1, SCONOSCIUTO, "td").casi == 12        # stato ignoto: insieme


def test_classifica_una_riga_per_giocatore_e_metrica():
    st = righe(2, "terzino", -3, [100, 200, 300, 400, 500, 600])
    oggi = righe(1, "terzino", -3, [900], inizio="2024-06-01")
    t = classifica(st, oggi)
    assert len(t) == 6 and set(t["posizione"]) == {"molto sopra"}
    vuota = classifica(st.iloc[:0], oggi)
    assert set(vuota["posizione"]) == {"senza fascia"} and "percentile" in vuota.columns


def test_evidenze_arrotondate_e_serializzabili():
    import json
    e = evidenza("x/1", "prova", 5436.6, "m", data=pd.Timestamp("2024-01-10"), fascia=[np.float64(1.5), np.nan])
    assert e.valore == 5437 and isinstance(e.valore, int)
    assert e.contesto == {"data": "2024-01-10", "fascia": [1.5, None]}
    json.dumps(e.to_dict())
    assert 5437.0 in e.numeri() and 1.5 in e.numeri()
    assert arrotonda(182.04, "m/min") == 182.0 and numero_it(5436.6, "m") == "5.437" and numero_it(182.04, "m/min") == "182,0"


def test_settimana_regolare_tra_6_e_8_giorni():
    g = pd.Timestamp("2024-01-01")
    assert not Settimana(g, g + pd.Timedelta(days=4)).regolare
    assert Settimana(g, g + pd.Timedelta(days=6)).regolare and Settimana(g, g + pd.Timedelta(days=8)).regolare
    assert not Settimana(g, g + pd.Timedelta(days=14)).regolare


def test_riferimento_di_ruolo_da_tre_partite_diverse():
    """Tre prestazioni da titolare dello stesso ruolo ma in una sola partita non bastano."""
    una = pd.concat([righe(g, "terzino", 0, [9000]) for g in (1, 2, 3)])
    giocatori = pd.DataFrame({"giocatore_id": [4], "ruolo": ["terzino"]})
    assert riferimenti_partita(una, giocatori)["livello"].isna().all()
    tre = pd.concat([righe(g, "terzino", 0, [9000], inizio=f"2024-01-0{g}") for g in (1, 2, 3)])
    r = riferimenti_partita(tre, giocatori)
    assert (r["livello"] == "ruolo").all() and (r["partite"] == 3).all()
