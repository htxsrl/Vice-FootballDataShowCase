"""Il giorno in esame (decisione 47) e i report pronti (decisione 49).

Vice ragiona sempre da oggi; il giorno scelto nel calendario è quello delle domande senza data, così si può
confrontarlo con oggi. I report generati in anticipo si leggono dall'archivio senza chiamare il modello, ma
solo se i loro numeri tornano ancora coi dati del motore."""

import asyncio
import json

import pytest

from vice import llm
from vice.agent import agente, archivio
from vice.agent import report as reportistica
from vice.agent.citazioni import Registro
from vice.agent.contesto import ErroreStrumento, Sessione
from vice.agent.strumenti import esegui
from vice.config import get_settings
from vice.data.caricamenti import codice_dataset

OGGI, PRIMA = "2024-04-18", "2024-04-10"


def raccogli(gen):
    async def tutto():
        return [e async for e in gen]
    return asyncio.run(tutto())


@pytest.fixture
def prova(monkeypatch):
    monkeypatch.setenv("VICE_LLM_PROVA", "1")
    get_settings.cache_clear()
    reportistica.svuota_cache()
    yield
    get_settings.cache_clear()
    reportistica.svuota_cache()


# ---------- il giorno in esame ----------

def test_sessione_col_giorno_in_esame():
    s = Sessione.crea(OGGI, giorno=PRIMA)
    assert f"{s.oggi:%Y-%m-%d}" == OGGI and f"{s.giorno:%Y-%m-%d}" == PRIMA
    assert f"{s.data(None):%Y-%m-%d}" == PRIMA                 # le domande senza data
    assert f"{s.data('oggi'):%Y-%m-%d}" == OGGI                # «oggi» resta oggi
    assert f"{s.data('2024-04-17'):%Y-%m-%d}" == "2024-04-17"  # tra il giorno in esame e oggi si vede tutto
    assert Sessione.crea(OGGI, giorno=OGGI).giorno is None
    assert Sessione.crea(OGGI).chiave != s.chiave
    with pytest.raises(ErroreStrumento, match="dopo oggi"):
        Sessione.crea(OGGI, giorno="2024-04-19")
    with pytest.raises(ErroreStrumento, match="non riconosciuto"):
        Sessione.crea(OGGI, giorno="ieri l'altro")


def test_gli_strumenti_partono_dal_giorno_in_esame():
    s = Sessione.crea(OGGI, giorno=PRIMA)
    risultato, uscita, errore = esegui("seduta", "{}", s, Registro(OGGI))
    assert errore is None and json.loads(risultato)["contesto"]["data"] == "10/04/2024"
    assert uscita.vista["parametri"]["data"] == PRIMA


def test_prompt_col_giorno_in_esame_e_sigle_spiegate():
    testo, versione = agente.prompt_sistema(Sessione.crea(OGGI, giorno=PRIMA), None, {"HSR", "MD"})
    assert versione == "sistema_v5" and "La seduta di oggi è caricata." in testo     # il 18/04 è nei dati del club
    assert "Giorno in esame: 10/04/2024 (MD-3)" in testo and "Oggi è 18/04/2024" in testo
    assert "Già spiegate in questa conversazione (scrivi solo la sigla): HSR, MD." in testo
    testo, _ = agente.prompt_sistema(Sessione.crea(OGGI))
    assert "Giorno in esame" not in testo and "HMLD = distanza ad alto carico metabolico" in testo


def test_chat_e_vista_sul_giorno_in_esame(prova, client):
    eventi = raccogli(agente.turno([{"role": "user", "content": "Chi era fuori fascia nella distanza totale quel giorno?"}],
                                   Sessione.crea(OGGI, giorno=PRIMA)))
    vista = next(e["dati"] for e in eventi if e["evento"] == "vista")
    assert vista["parametri"]["data"] == PRIMA
    r = client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "giorno": PRIMA, "parametri": {"metrica": "td"}})
    assert r.status_code == 200 and r.json()["parametri"]["data"] == PRIMA
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "x"}], "oggi": OGGI, "giorno": "2024-04-20"})
    assert "dopo oggi" in r.text


def test_la_prima_sigla_della_chat_ha_il_significato(modello_finto):
    s = Sessione.crea(OGGI)
    modello_finto([{"testo": "L'HSR della squadra è nella fascia."}])
    finale = next(e["dati"] for e in raccogli(agente.turno([{"role": "user", "content": "e l'alta velocità?"}], s))
                  if e["evento"] == "verifica")
    assert finale["testo"] == "L'HSR (corsa ad alta velocità) della squadra è nella fascia."
    # la seconda volta, nella stessa conversazione, basta la sigla
    modello_finto([{"testo": "L'HSR di oggi resta nella fascia."}])
    storia = [{"role": "user", "content": "e l'alta velocità?"}, {"role": "assistant", "content": finale["testo"]},
              {"role": "user", "content": "e adesso?"}]
    finale = next(e["dati"] for e in raccogli(agente.turno(storia, s)) if e["evento"] == "verifica")
    assert finale["testo"] == "L'HSR di oggi resta nella fascia."


# ---------- i report pronti ----------

def _genera(giorno):
    """Il report del preparatore col modello di prova, come lo genera scripts/prepara_report.py."""
    from scripts.prepara_report import uno
    return asyncio.run(uno(__import__("pandas").Timestamp(giorno)))


def test_report_pronto_dall_archivio(prova, monkeypatch, client):
    r = _genera(OGGI)
    assert r["testo"] and r["verificate"] == r["frasi_con_numeri"] and r["titolo"] == "Report della seduta del 18/04/2024"
    archivio.scrivi(OGGI, r)
    assert archivio.giorni() == [OGGI] and archivio.giorni("2024-04-17") == []
    reportistica.svuota_cache()

    async def vietato(*a, **k):
        raise AssertionError("il report pronto non deve chiamare il modello")
        yield   # serve solo a farne un generatore asincrono
    monkeypatch.setattr(llm, "passo", vietato)
    eventi = raccogli(reportistica.report("seduta", Sessione.crea(OGGI)))
    per = {e["evento"]: e["dati"] for e in eventi}
    assert per["verifica"]["testo"] == r["testo"] and per["verifica"]["evidenze"]
    assert per["done"]["report_pronto"] is True and per["done"]["chiamate"] == 0
    assert client.get("/api/contesto").json()["report_pronti"] == [OGGI]


def test_report_pronto_coi_numeri_sbagliati_si_ignora(prova):
    r = _genera(OGGI)
    sbagliato = r | {"testo": "## Sintesi\nLa distanza totale mediana è 99.999 m [E1]."}
    archivio.scrivi(OGGI, sbagliato)
    assert reportistica._dall_archivio(Sessione.crea(OGGI), None) is None
    archivio.scrivi(OGGI, r)
    assert reportistica._dall_archivio(Sessione.crea(OGGI), None) is not None
    # con un file caricato o con un giorno in esame, l'archivio non si usa
    eventi = raccogli(reportistica.report("seduta", Sessione.crea(OGGI, giorno=PRIMA)))
    assert next(e["dati"] for e in eventi if e["evento"] == "done")["report_pronto"] is False


@pytest.mark.archivio_vero
def test_i_report_pronti_veri_tornano_coi_dati():
    """Ogni report salvato in data/processed/report/ si legge ancora: i suoi numeri tornano col motore di oggi.
    Se il motore cambia e questo test fallisce, quei report vanno rigenerati (scripts/prepara_report.py --rifai)."""
    giorni = archivio.giorni()
    for g in giorni[::7]:                                       # uno ogni sette: il controllo completo è lento
        # il giorno della demo ha la seduta solo col file (decisione 54): qui quello uguale al dataset
        assert reportistica._dall_archivio(Sessione.crea(g, caricamento=codice_dataset(g)), None) is not None, g
