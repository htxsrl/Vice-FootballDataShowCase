"""M1.3: anagrafica di fantasia coerente con i dati e senza doppioni."""

from vice.config import get_settings
from vice.data import anagrafica, zenodo
from vice.data.stagione import Stagione


def test_coerente_con_i_dati():
    dati = zenodo.carica(get_settings().processed_dir / "zenodo")
    g = anagrafica.con_nomi(dati.giocatori)                # solleva se ruoli o giocatori non tornano
    assert len(g) == 20


def test_nomi_e_numeri_unici():
    valori = anagrafica.GIOCATORI.values()
    assert len({cognome for _, cognome, _, _ in valori}) == 20
    assert len({numero for _, _, numero, _ in valori}) == 20


def test_sempre_uguale():
    dati = zenodo.carica(get_settings().processed_dir / "zenodo")
    a = Stagione(dati).al("2024-01-10").giocatori
    b = Stagione(dati).al("2024-03-10").giocatori
    assert list(a["nome_completo"]) == list(b["nome_completo"])
    assert "Tommaso Ferrandi" in set(a["nome_completo"])


def test_dicitura():
    assert "fantasia" in anagrafica.DICITURA and "18986229" in anagrafica.DICITURA
