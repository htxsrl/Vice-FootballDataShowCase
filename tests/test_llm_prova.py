"""Il modello di prova (VICE_LLM_PROVA=1) fa girare tutta la catena dell'agente senza chiamare il gateway:
strumenti, verifica di numeri e giudizi, vista per la lavagna. Le domande sono quelle del copione della demo
(wiki/progetto/prova-della-demo.md)."""

import asyncio

import pytest

from vice.agent import agente
from vice.agent import report as reportistica
from vice.agent.contesto import Sessione
from vice.config import get_settings
from vice.views import costruisci

OGGI = "2024-04-18"


@pytest.fixture
def prova(monkeypatch):
    monkeypatch.setenv("VICE_LLM_PROVA", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _turno(domanda):
    s = Sessione.crea(OGGI)

    async def raccogli():
        return [ev async for ev in agente.turno([{"role": "user", "content": domanda}], s)]
    eventi = asyncio.run(raccogli())
    per = {e["evento"]: e["dati"] for e in eventi}
    vista = costruisci(per["vista"]["vista"], s, per["vista"]["parametri"]) if "vista" in per else None
    return per, vista


@pytest.mark.parametrize("domanda, vista_attesa, titolo", [
    ("Chi è fuori fascia oggi nella distanza totale?", "seduta", "Distanza totale oggi"),
    ("Chi è fuori fascia oggi in alta velocità?", "seduta", "Alta velocità oggi"),
    ("Come sta Cortese?", "giocatore", "Lorenzo Cortese"),
    ("Come sta il numero 9?", "giocatore", "Matteo Basile"),
    ("Com'era la distanza totale di Cortese il 10/04 rispetto a oggi?", "giocatore", "Lorenzo Cortese, distanza totale"),
    ("Quanto della partita abbiamo allenato questa settimana?", "allenamento_partita", "Quanta partita"),
    ("Fammi vedere la settimana sulla lavagna", "settimana", "La settimana"),
    ("Come fate a sapere che i numeri sono giusti?", "verifica", "Come sappiamo"),
])
def test_catena_completa_col_modello_di_prova(prova, domanda, vista_attesa, titolo):
    per, vista = _turno(domanda)
    assert per["done"]["modelli_usati"] == ["modello-di-prova"] and per["done"]["costo"] == 0   # nessuna chiamata al gateway
    assert vista and vista["vista"] == vista_attesa and vista["titolo"].startswith(titolo), vista and vista["titolo"]
    v = per["verifica"]
    assert v["frasi_con_numeri"] > 0 and v["verificate"] == v["frasi_con_numeri"] and not v["tolte"], v


def test_trabocchetto_senza_grafico(prova):
    per, vista = _turno("Qual è il rischio infortuni di Tosi?")
    assert vista is None and "oltre ciò che i dati permettono" in per["verifica"]["testo"]


def test_report_col_modello_di_prova(prova):
    s = Sessione.crea(OGGI)
    reportistica.svuota_cache()

    async def raccogli(tipo, giocatore=None):
        return {e["evento"]: e["dati"] async for e in reportistica.report(tipo, s, giocatore)}
    for tipo, giocatore in (("seduta", None), ("settimana", None), ("giocatore", "Santini")):
        v = asyncio.run(raccogli(tipo, giocatore))["verifica"]
        assert v["verificate"] == v["frasi_con_numeri"] > 0 and not v["tolte"], (tipo, v)
