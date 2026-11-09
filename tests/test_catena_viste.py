"""La catena agente → vista → lavagna mostra il giocatore, il giorno e la metrica della domanda.

Nata da un errore visto da Ivan il 25/10/2026: «Come sta Cortese?» → testo su Cortese, grafico di Matteo
Basile. Lo strumento passava alla vista il codice del giocatore (9) e la vista lo leggeva come numero di
maglia (la 9 è di Basile). Qui si percorre la catena intera, per tutti i giocatori, senza chiamare il modello.
"""

import json

import pytest

from vice.agent.citazioni import Registro
from vice.agent.contesto import Sessione
from vice.agent.strumenti import esegui
from vice.views import costruisci

OGGI = "2024-04-18"
S = Sessione.crea(OGGI)
ROSA = S.giocatori[["giocatore_id", "nome_completo", "cognome", "numero"]].to_dict("records")


def _vista_da_strumento(nome, argomenti):
    _, u, err = esegui(nome, argomenti, S, Registro())
    assert err is None, err
    return costruisci(u.vista["vista"], S, u.vista["parametri"])


def test_ci_sono_codici_che_sono_anche_numeri_di_maglia_di_altri():
    """La trappola esiste davvero: se un codice venisse letto come maglia, cambierebbe giocatore."""
    maglie = {g["numero"]: g["giocatore_id"] for g in ROSA}
    assert any(g["giocatore_id"] in maglie and maglie[g["giocatore_id"]] != g["giocatore_id"] for g in ROSA)


@pytest.mark.parametrize("g", ROSA, ids=lambda g: g["cognome"])
def test_scheda_del_giocatore_mostra_lui(g):
    for chi in (g["cognome"], g["nome_completo"], str(g["numero"])):
        v = _vista_da_strumento("giocatore", {"giocatore": chi})
        assert v["giocatore"]["id"] == g["giocatore_id"] and v["titolo"].startswith(g["nome_completo"])
        assert v["parametri"]["giocatore_id"] == g["giocatore_id"]
        # ogni seduta del grafico è sua (solo i suoi dati, D6)
        assert all(f"/{g['giocatore_id']}/" in r["evidenza"] for r in v["righe"])


@pytest.mark.parametrize("g", ROSA, ids=lambda g: g["cognome"])
def test_vista_chiesta_dall_agente_mostra_lui(g):
    for chi in (g["cognome"], str(g["numero"]), g["numero"]):
        v = _vista_da_strumento("mostra_vista", {"vista": "giocatore", "parametri": {"giocatore": chi}})
        assert v["giocatore"]["id"] == g["giocatore_id"], (chi, v["titolo"])


@pytest.mark.parametrize("g", ROSA, ids=lambda g: g["cognome"])
def test_cambio_di_metrica_resta_sullo_stesso_giocatore(g):
    """L'interfaccia rimanda i parametri della vista cambiando solo la metrica."""
    v = _vista_da_strumento("giocatore", {"giocatore": g["cognome"]})
    for m in ("td", "spr"):
        w = costruisci("giocatore", S, {**v["parametri"], "metrica": m})
        assert w["giocatore"]["id"] == g["giocatore_id"] and w["metrica"] == m


def test_citazione_dell_andamento_porta_al_giocatore_giusto():
    """Come fa l'interfaccia: dall'id dell'evidenza «andamento/<data>/<codice>/<metrica>» alla vista."""
    for g in ROSA:
        v = costruisci("giocatore", S, {"giocatore_id": g["giocatore_id"], "metrica": "hsr"})
        assert v["giocatore"]["id"] == g["giocatore_id"]


def test_allenamento_partita_accende_il_giocatore_chiesto():
    v = _vista_da_strumento("allenamento_vs_partita", {"giocatore": "Cortese", "metrica": "hsr"})
    accese = [r["giocatore"]["cognome"] for r in v["righe"] if r.get("acceso")]
    assert accese == ["Cortese"]


def test_seduta_e_settimana_restano_sul_giorno_e_sulla_metrica():
    v = _vista_da_strumento("seduta", {"data": "10/04/2024", "metrica": "spr"})
    assert v["parametri"] == {"data": "2024-04-10", "metrica": "spr"}
    v = _vista_da_strumento("settimana", {"metrica": "td"})
    assert v["metrica"] == "td" and v["giorni"][-1]["data"] == OGGI


def _eventi(testo):
    out, ev = [], None
    for riga in testo.splitlines():
        if riga.startswith("event:"):
            ev = riga.split(":", 1)[1].strip()
        elif riga.startswith("data:") and ev:
            out.append((ev, json.loads(riga.split(":", 1)[1])))
    return out


@pytest.mark.parametrize("domanda, strumento, argomenti, atteso", [
    ("Come sta Cortese?", "giocatore", {"giocatore": "Cortese"}, "Lorenzo Cortese"),
    ("Come sta il 17?", "giocatore", {"giocatore": "17"}, "Lorenzo Cortese"),
    ("Come sta Basile?", "giocatore", {"giocatore": "Basile"}, "Matteo Basile"),
    ("Mostrami Melis", "mostra_vista", {"vista": "giocatore", "parametri": {"giocatore": "Melis"}}, "Andrea Melis"),
])
def test_turno_di_chat_fino_al_grafico(client, modello_finto, domanda, strumento, argomenti, atteso):
    """Il percorso dell'interfaccia: /api/chat emette la vista, /api/vista la costruisce."""
    modello_finto([{"testo": "", "tool_calls": [(strumento, json.dumps(argomenti))]}, {"testo": "Ecco."}])
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": domanda}], "oggi": OGGI})
    viste = [d for e, d in _eventi(r.text) if e == "vista"]
    assert len(viste) == 1
    spec = client.post("/api/vista", json={"vista": viste[0]["vista"], "parametri": viste[0]["parametri"], "oggi": OGGI}).json()
    assert spec["titolo"].startswith(atteso), spec["titolo"]
