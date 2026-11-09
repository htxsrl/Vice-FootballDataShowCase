"""M1.4: i dati elaborati (data/processed/zenodo/, tracciati in git) tornano con il profilo verificato."""

import json

import pytest

from vice.config import get_settings
from vice.data import zenodo

CARTELLA = get_settings().processed_dir / "zenodo"


@pytest.fixture(scope="module")
def dati():
    return zenodo.carica(CARTELLA)


def test_conteggi(dati):
    c = dati.carichi
    assert len(c) == 2375
    assert c["giocatore_id"].nunique() == 20
    assert len(dati.sedute) == 151
    assert (dati.sedute["tipo"] == "allenamento").sum() == 121
    assert dati.partite["dati_gps"].sum() == 30
    assert len(dati.partite) == 32
    assert c["microciclo_dataset"].nunique() == 31


def test_giorni_md_coerenti_col_calendario(dati):
    s = dati.sedute
    pre, post = s[s["giorno_md"] < 0], s[s["giorno_md"] > 0]
    assert ((pre["prossima_partita"] - pre["data"]).dt.days == -pre["giorno_md"]).all()
    assert ((post["data"] - post["ultima_partita"]).dt.days == post["giorno_md"]).all()


def test_qualita_registrata():
    q = json.loads((CARTELLA / "qualita.json").read_text())
    assert q["integrita"]["duplicati_giocatore_giorno"] == 0
    assert q["calendario"]["settimane_con_due_partite"] == 0
    assert q["zeri_e_valori_bassi"]["hsr_zero"] == 86


def test_nessun_dato_personale(dati):
    for tabella in (dati.carichi, dati.giocatori, dati.sedute, dati.partite):
        assert not any("nome" in col or "nascita" in col or "birth" in col for col in tabella.columns)
