"""Fixture comuni. I test girano nel container: docker compose exec vice python3 -m pytest tests"""

import pytest


def pytest_configure(config):
    # Avviso interno di starlette (alias deprecato di anyio): non dipende dal nostro codice.
    config.addinivalue_line("filterwarnings", "ignore:The anyio.abc.BlockingPortal alias:DeprecationWarning")
    config.addinivalue_line("markers", "archivio_vero: il test legge i report pronti veri di data/processed/report/")


@pytest.fixture(autouse=True)
def archivio_vuoto(monkeypatch, tmp_path_factory, request):
    """I report pronti veri (decisione 49) non entrano nei test, salvo in quelli che li chiedono: altrimenti un
    report generato in anticipo prenderebbe il posto di quello che il test fa scrivere al modello finto."""
    if request.node.get_closest_marker("archivio_vero"):
        return
    from vice.agent import archivio
    cartella = tmp_path_factory.mktemp("report")
    monkeypatch.setattr(archivio, "cartella", lambda: cartella)


@pytest.fixture
def client():
    # Import qui dentro, così il filtro sopra è già attivo quando starlette emette l'avviso.
    from fastapi.testclient import TestClient

    from vice.main import app

    with TestClient(app) as c:
        yield c


class ModelloFinto:
    """Sostituisce vice.llm.passo: restituisce risposte scritte in anticipo, senza chiamare il gateway.
    Ogni risposta è un dict con `testo` e, facoltativo, `tool_calls` [(nome, argomenti)]."""

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.richieste = []          # (messaggi, modello, tools) di ogni chiamata

    async def __call__(self, messages, model, tools=None, max_tokens=2048, riserva=None, ragiona=True):
        self.richieste.append((messages, model, tools))
        r = self.risposte.pop(0) if self.risposte else {"testo": "Fine."}
        if callable(r):
            r = r(messages)
        testo = r.get("testo", "")
        for i in range(0, len(testo), 20):
            yield {"type": "delta", "text": testo[i:i + 20]}
        chiamate = [{"id": f"c{n}", "name": nome, "arguments": arg} for n, (nome, arg) in enumerate(r.get("tool_calls", []))]
        yield {"type": "fine", "testo": testo, "tool_calls": chiamate,
               "usage": {"prompt_tokens": 1000, "completion_tokens": 100}, "costo": 0.0033, "ms": 5, "spesa_chiave": None,
               "modello": model}


@pytest.fixture
def modello_finto(monkeypatch):
    """Uso: m = modello_finto([...risposte]); poi si chiama l'agente o l'API."""
    import vice.llm as llm

    def crea(risposte):
        m = ModelloFinto(risposte)
        monkeypatch.setattr(llm, "passo", m)
        return m
    return crea
