"""M3: strumenti, loop dell'agente e report, con un modello finto (nessuna chiamata al gateway)."""

import asyncio
import json

import pytest

from vice.agent import agente
from vice.agent import report as reportistica
from vice.agent.citazioni import Registro
from vice.agent.contesto import ErroreStrumento, Sessione
from vice.agent.strumenti import CATALOGO, MAX_EVIDENZE, esegui, schemi

OGGI = "2024-04-18"            # MD-2


@pytest.fixture(scope="module")
def s():
    return Sessione.crea(OGGI)


def raccogli(gen):
    async def tutto():
        return [ev async for ev in gen]
    return asyncio.run(tutto())


# ---------- contesto e strumenti ----------

def test_giocatori_e_date(s):
    assert s.nome(s.giocatore("Santini")) == "Federico Santini"
    assert s.giocatore("4") == s.giocatore("Benedetti") == s.giocatore("riccardo benedetti")  # numero di maglia
    assert s.giocatore("Nicolo Serafini") == s.giocatore("Nicolò Serafini")          # accenti
    with pytest.raises(ErroreStrumento):
        s.giocatore("Rossi")
    assert s.data("10/01/2024").strftime("%Y-%m-%d") == "2024-01-10"
    assert s.data("10 gennaio").strftime("%Y-%m-%d") == "2024-01-10"
    with pytest.raises(ErroreStrumento, match="futuro"):
        s.data("2024-05-01")


@pytest.mark.parametrize("nome,argomenti", [
    ("seduta", {}), ("settimana", {}), ("alta_velocita", {}), ("postpartita", {}), ("allenamento_vs_partita", {}),
    ("allenamento_vs_partita", {"giocatore": "Santini"}), ("giocatore", {"giocatore": "Basile"}),
    ("fascia_attesa", {"giocatore": "6", "giorno_md": "MD-1"}), ("confronta", {"giocatori": ["Tosi", "Melis"]}),
    ("verifica_motore", {}),
    ("limiti", {"domanda": "ACWR"}), ("mostra_vista", {"vista": "giocatore", "parametri": {"giocatore": "Pinna"}}),
])
def test_ogni_strumento_risponde_compatto(s, nome, argomenti):
    reg = Registro()
    testo, uscita, errore = esegui(nome, json.dumps(argomenti), s, reg)
    assert errore is None, errore
    dati = json.loads(testo)
    assert len(dati.get("evidenze", [])) <= MAX_EVIDENZE and len(testo) < 12000
    for e in dati.get("evidenze", []):                     # ogni evidenza mostrata è nel registro
        assert reg.evidenza(e["evidenza"]) is not None


def test_errori_degli_strumenti_tornano_al_modello(s):
    for nome, arg in [("seduta", {"data": "2024-05-01"}), ("giocatore", {"giocatore": "Rossi"}), ("inesistente", {}),
                      ("mostra_vista", {"vista": "torta"}), ("seduta", "non json")]:
        testo, uscita, errore = esegui(nome, arg if isinstance(arg, str) else json.dumps(arg), s, Registro())
        assert uscita is None and errore and "errore" in json.loads(testo)


def test_catalogo():
    assert len(CATALOGO) == 11 and len(schemi()) == 11
    assert all(t["function"]["description"] for t in schemi())


# ---------- loop dell'agente ----------

def test_turno_con_strumenti_e_verifica(s, modello_finto):
    def risposta_finale(messaggi):
        dati = json.loads(messaggi[-2]["content"])          # risultato di `seduta`
        e = dati["evidenze"][0]
        return {"testo": f"Oggi {e['cosa'].split(' in ')[0].lower()}: {e['valore']} [{e['evidenza']}]."}
    m = modello_finto([{"testo": "Controllo.", "tool_calls": [("seduta", "{}"), ("mostra_vista", '{"vista": "seduta"}')]},
                       risposta_finale])
    eventi = raccogli(agente.turno([{"role": "user", "content": "Com'è andata oggi?"}], s))
    nomi = [e["evento"] for e in eventi]
    assert nomi[0] == "delta" and "tappa" in nomi and nomi[-3:] == ["vista", "verifica", "done"]
    ver = eventi[-2]["dati"]
    assert ver["verificate"] == ver["frasi_con_numeri"] == 1 and ver["tolte"] == [] and "E1" in ver["evidenze"]
    assert eventi[-3]["dati"]["vista"] == "seduta" and eventi[-3]["dati"]["origine"] == "agente"
    done = eventi[-1]["dati"]
    assert done["chiamate"] == 2 and [x["nome"] for x in done["strumenti"]] == ["seduta", "mostra_vista"]
    sistema = m.richieste[0][0][0]["content"]
    assert "18/04/2024" in sistema and "ACWR" in sistema and "[D1]" in sistema
    assert m.richieste[0][2] and m.richieste[0][1] == "HTX-EU-Claude-Sonnet-5"


def test_frase_non_verificata_corretta_o_tolta(s, modello_finto):
    m = modello_finto([{"testo": "", "tool_calls": [("seduta", "{}")]},
                       {"testo": "La squadra è andata bene. Santini ha fatto 9.999 m [E1]."},
                       {"testo": "1: TOGLI"}])                  # la correzione rinuncia
    eventi = raccogli(agente.turno([{"role": "user", "content": "E Santini?"}], s))
    ver = next(e["dati"] for e in eventi if e["evento"] == "verifica")
    assert ver["testo"] == "La squadra è andata bene." and len(ver["tolte"]) == 1 and "tolte" in ver["badge"]
    assert len(m.richieste) == 3 and "TOGLI" in m.richieste[2][0][0]["content"]


def test_correzione_riuscita(s, modello_finto):
    def corretta(messaggi):
        return {"testo": "1: Oggi in seduta c'erano 15 giocatori [E1]."}
    modello_finto([{"testo": "", "tool_calls": [("seduta", "{}")]}, {"testo": "Oggi in seduta c'erano 16 giocatori [E1]."}, corretta])
    ver = next(e["dati"] for e in raccogli(agente.turno([{"role": "user", "content": "quanti?"}], s)) if e["evento"] == "verifica")
    assert ver["testo"] == "Oggi in seduta c'erano 15 giocatori [E1]." and ver["verificate"] == 1 and ver["tolte"] == []


def test_testo_dei_passi_di_sola_vista_si_conserva(s, modello_finto):
    modello_finto([{"testo": "Ecco la settimana.", "tool_calls": [("mostra_vista", '{"vista": "settimana"}')]},
                   {"testo": "Ho aperto la vista."}])
    ver = next(e["dati"] for e in raccogli(agente.turno([{"role": "user", "content": "settimana"}], s)) if e["evento"] == "verifica")
    assert ver["testo"].startswith("Ecco la settimana.")


def test_limite_di_passi_e_strumento_sconosciuto(s, modello_finto):
    m = modello_finto([{"testo": "", "tool_calls": [("inesistente", "{}")]}] * agente.MAX_PASSI)
    eventi = raccogli(agente.turno([{"role": "user", "content": "x"}], s))
    assert "Non sono riuscito" in next(e["dati"]["testo"] for e in eventi if e["evento"] == "verifica")
    assert len(m.richieste) == agente.MAX_PASSI
    assert "strumento sconosciuto" in m.richieste[1][0][-1]["content"]


def test_le_citazioni_della_cronologia_si_tolgono(s, modello_finto):
    m = modello_finto([{"testo": "Ok."}])
    raccogli(agente.turno([{"role": "user", "content": "a"}, {"role": "assistant", "content": "Ha fatto 5.436 m [E1]."},
                           {"role": "user", "content": "b"}], s))
    assert m.richieste[0][0][2]["content"] == "Ha fatto 5.436 m."


# ---------- report ----------

def test_report_del_preparatore(s, modello_finto):
    reportistica.svuota_cache()

    def scrivi(messaggi):
        prompt = messaggi[0]["content"]
        dati = json.loads(prompt.split("```json")[1].split("```")[0])
        e = dati["seduta"]["evidenze"][1]
        return {"testo": f"## Sintesi\nPercentile mediano della distanza totale: {e['valore']} [{e['evidenza']}].\n## Spunti per lo staff\n- Nessuno."}
    m = modello_finto([scrivi])
    eventi = raccogli(reportistica.report("seduta", s))
    prompt = m.richieste[0][0][0]["content"]
    assert "## Verso la partita" in prompt and "## Titolari e non titolari" not in prompt     # MD-2
    ver = next(e["dati"] for e in eventi if e["evento"] == "verifica")
    assert ver["verificate"] == ver["frasi_con_numeri"] == 1
    assert m.richieste[0][2] is None                                                       # niente strumenti (decisione 32)
    # un solo report (decisione 51): chiederlo di nuovo non chiama il modello, viene dalla cache
    m2 = modello_finto([])
    eventi = raccogli(reportistica.report("seduta", s))
    assert not m2.richieste and eventi[-1]["dati"]["report_dalla_cache"] is True
    assert "linguaggio" not in eventi[-1]["dati"] and "modello_veloce" not in eventi[-1]["dati"]


def test_report_regole(s):
    for tipo, gioc in [("giocatore", None), ("mensile", None)]:
        with pytest.raises(ErroreStrumento):
            raccogli(reportistica.report(tipo, s, gioc))


def test_il_banco_riconosce_gli_spunti_inventati():
    from scripts.banco_di_prova import SCENARI, _spunti_inventati
    motore = ["Valutare se serve uno stimolo di velocità per Matteo Basile: da MD-4 a MD-2 ha registrato 107 m di sprint"]
    testo = ("La seduta è nella norma [E1].\n- Valutare se serve uno stimolo di velocità per Matteo Basile: da MD-4 a MD-2 "
             "ha registrato 107 m di sprint [E3].\n- Valutare se serve monitorare Ghio.")
    assert _spunti_inventati(testo, motore) == ["Valutare se serve monitorare Ghio."]
    assert len(SCENARI) == 28 and len({s["id"] for s in SCENARI}) == 28   # 12 e 13 (SkillCorner) tolti, decisione 57


# ---------- il grafico segue la domanda (decisione 44) ----------

def test_scegli_vista_tra_quelle_suggerite():
    from vice.agent.agente import scegli_vista
    g = lambda d, m=None: {"vista": "giocatore", "parametri": {"giocatore_id": 9, "data": d, **({"metrica": m} if m else {})}, "origine": "automatica"}  # noqa: E731
    # due giorni dello stesso giocatore: si mostra il più recente, con la metrica chiesta
    assert scegli_vista(g("2024-04-10", "td"), g("2024-04-18"))["parametri"] == {"giocatore_id": 9, "data": "2024-04-18", "metrica": "td"}
    assert scegli_vista(g("2024-04-18"), g("2024-04-10"))["parametri"]["data"] == "2024-04-18"
    # stesso giorno: vince quella con la metrica
    assert scegli_vista(g("2024-04-18"), g("2024-04-18", "spr"))["parametri"]["metrica"] == "spr"
    # tipi diversi o giocatori diversi: resta la prima
    seduta = {"vista": "seduta", "parametri": {"data": "2024-04-18"}}
    assert scegli_vista(seduta, g("2024-04-18", "td")) is seduta
    altro = {"vista": "giocatore", "parametri": {"giocatore_id": 15, "data": "2024-04-18"}}
    assert scegli_vista(g("2024-04-10"), altro)["parametri"]["giocatore_id"] == 9


def test_la_metrica_della_domanda_arriva_al_grafico():
    from vice.agent.citazioni import Registro
    from vice.agent.contesto import Sessione
    from vice.agent.strumenti import esegui
    s = Sessione.crea("2024-04-18")
    _, u, err = esegui("seduta", {"metrica": "td"}, s, Registro())
    assert err is None and u.vista["parametri"] == {"data": "2024-04-18", "metrica": "td"}
    # con la metrica, il modello riceve tutti quelli fuori dalla fascia centrale in quella metrica
    nomi = {e.contesto.get("giocatore") for e in u.evidenze if e.contesto.get("metrica") == "td" and e.contesto.get("posizione") != "dentro"}
    assert {"Edoardo Tosi", "Christian Porcu"} <= nomi
    _, u, _ = esegui("giocatore", {"giocatore": "Cortese", "metrica": "distanza totale"}, s, Registro())
    assert u.vista["parametri"]["metrica"] == "td"
    _, u, _ = esegui("seduta", {"metrica": "velocità massima"}, s, Registro())     # non riconosciuta: grafico libero
    assert "metrica" not in u.vista["parametri"]
