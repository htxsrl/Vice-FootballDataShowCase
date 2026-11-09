"""Il client del gateway: streaming, chiamate a strumenti, costo, nuovi tentativi. Gateway simulato."""

import asyncio
import json

import httpx
import pytest

import vice.llm as llm


def sse(*chunks, fine=True):
    righe = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    if fine:
        righe.append("data: [DONE]\n\n")
    return "".join(righe).encode()


COMPLETA = sse(
    {"choices": [{"delta": {"content": "Ciao "}}]},
    {"choices": [{"delta": {"content": "staff", "tool_calls": [{"index": 0, "id": "c1", "function": {"name": "seduta", "arguments": '{"da'}}]}}]},
    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ta": ""}'}}]}, "finish_reason": "tool_calls"}]},
    {"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 100}},
)
TRONCA = sse({"choices": [{"delta": {"content": "Ciao a me"}}]}, fine=False)


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(llm, "RIPROVA_ATTESE", (0, 0))
    monkeypatch.setenv("VICE_LLM_API_KEY", "finta")
    llm.get_settings.cache_clear()

    def crea(risposte):
        coda = list(risposte)

        def gestore(request):
            stato, corpo = coda.pop(0)
            return httpx.Response(stato, content=corpo, headers={"x-litellm-key-spend": "1.5"})
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(gestore)))
        return coda
    yield crea
    llm.get_settings.cache_clear()


def eventi():
    async def tutto():
        return [e async for e in llm.passo([{"role": "user", "content": "x"}], "HTX-EU-Claude-Sonnet-5", tools=[{}])]
    return asyncio.run(tutto())


def test_stream_completo(gateway):
    gateway([(200, COMPLETA)])
    ev = eventi()
    fine = ev[-1]
    assert [e["text"] for e in ev if e["type"] == "delta"] == ["Ciao ", "staff"]
    assert fine["tool_calls"] == [{"id": "c1", "name": "seduta", "arguments": '{"data": ""}'}]
    assert fine["costo"] == pytest.approx((1000 * 2.2 + 100 * 11) / 1e6) and fine["spesa_chiave"] == 1.5
    assert fine["fine_motivo"] == "tool_calls"


def test_errore_temporaneo_poi_successo(gateway):
    gateway([(503, b'{"error": "Bedrock is unable"}'), (200, COMPLETA)])
    assert eventi()[-1]["testo"] == "Ciao staff"


def test_stream_interrotto_riparte(gateway):
    gateway([(200, TRONCA), (200, COMPLETA)])
    ev = eventi()
    assert [e["type"] for e in ev].count("ricomincia") == 1 and ev[-1]["testo"] == "Ciao staff"


def test_interruzioni_ripetute_diventano_errore(gateway):
    gateway([(200, TRONCA)] * 3)
    with pytest.raises(llm.LLMError, match="interrotto"):
        eventi()
    gateway([(400, b'{"error": "bad"}')])
    with pytest.raises(llm.LLMError, match="400"):
        eventi()


def test_modello_di_riserva(gateway):
    gateway([(503, b"{}"), (503, b"{}"), (503, b"{}"), (200, COMPLETA)])

    async def tutto():
        return [e async for e in llm.passo([{"role": "user", "content": "x"}], "HTX-EU-Claude-Sonnet-5",
                                            riserva="HTX-EU-Claude-Sonnet-4.6")]
    ev = asyncio.run(tutto())
    assert ev[0]["type"] == "ricomincia" and "Sonnet-4.6" in ev[0]["motivo"]
    assert ev[-1]["modello"] == "HTX-EU-Claude-Sonnet-4.6" and ev[-1]["costo"] == pytest.approx((1000 * 3.3 + 100 * 16.5) / 1e6)


def test_riserve_configurate():
    from vice.agent.agente import riserva_di
    assert riserva_di("HTX-EU-Claude-Sonnet-5") == "HTX-EU-Claude-Sonnet-4.6"      # decisione 34
    assert riserva_di("HTX-EU-Claude-Haiku-4.5") == "HTX-EU-Claude-Sonnet-4.6"
    assert riserva_di("HTX-EU-Claude-Sonnet-4.6") == "HTX-EU-Claude-Sonnet-5"
