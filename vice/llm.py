"""Client del gateway Hydrogen (LiteLLM, API compatibile OpenAI), in streaming.

Note sui modelli (wiki/tecnica/modelli-llm.md): niente `temperature`/`top_p` (Sonnet 5 e Opus 5.5 li
rifiutano), niente `response_format` JSON sui Claude, `tool_choice: auto` (Opus 5.5 non accetta lo
strumento forzato). Un passo può contenere sia testo sia chiamate a strumenti: si conservano entrambi.

Costo: in streaming il gateway non lo riporta nella risposta, quindi si calcola dai token con i
prezzi del gateway (`PREZZI`, letti dalle sue intestazioni il 22/10/2026).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx

from .config import get_settings

_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))

# $ per milione di token (ingresso, uscita), dalle intestazioni x-litellm-response-cost-* del gateway
PREZZI = {
    "HTX-EU-Claude-Haiku-4.5": (1.1, 5.5),
    "HTX-EU-Claude-Sonnet-5": (2.2, 11.0),
    "HTX-EU-Claude-Sonnet-4.6": (3.3, 16.5),
    "HTX-EU-Claude-Opus-5.5": (4.4, 22.0),
}


RAGIONAMENTO_SPEGNIBILE = {"HTX-EU-Claude-Sonnet-5"}   # Opus 5.5 risponde 400 a thinking disabled (TIDE)
RIPROVA_STATI = {429, 500, 502, 503, 504}   # errori temporanei del gateway o di Bedrock
RIPROVA_ATTESE = (1.5, 4.0)                  # secondi prima del 2° e del 3° tentativo


class LLMError(Exception):
    pass


def costo(modello: str, usage: dict | None) -> float | None:
    """Costo in dollari di una chiamata, dai token; None se il modello non ha un prezzo noto."""
    if not usage or modello not in PREZZI:
        return None
    p_in, p_out = PREZZI[modello]
    return (usage.get("prompt_tokens", 0) * p_in + usage.get("completion_tokens", 0) * p_out) / 1e6


async def passo(messages: list[dict], model: str, tools: list[dict] | None = None,
                max_tokens: int = 2048, riserva: str | None = None, ragiona: bool = True) -> AsyncIterator[dict]:
    """Come `_passo_modello`, ma se il modello fallisce anche dopo i nuovi tentativi e c'è un modello
    di riserva (Sonnet 4.6, decisione 34), il passo riparte con quello (evento `ricomincia`). L'evento
    `fine` dice chi ha risposto."""
    if get_settings().llm_prova:   # prove dell'interfaccia: modello deterministico, nessuna chiamata al gateway
        from . import llm_prova
        async for ev in llm_prova.passo(messages, model, tools, max_tokens, riserva, ragiona):
            yield ev
        return
    try:
        async for ev in _passo_modello(messages, model, tools, max_tokens, ragiona):
            yield ev
    except LLMError as e:
        if not riserva or riserva == model:
            raise
        yield {"type": "ricomincia", "motivo": f"{model} non disponibile ({str(e)[:80]}): passo a {riserva}"}
        async for ev in _passo_modello(messages, riserva, tools, max_tokens, ragiona):
            yield ev


async def _passo_modello(messages: list[dict], model: str, tools: list[dict] | None = None,
                         max_tokens: int = 2048, ragiona: bool = True) -> AsyncIterator[dict]:
    """Una chiamata al modello in streaming. Eventi:
    - `{"type": "delta", "text": ...}` mentre il testo arriva;
    - `{"type": "ricomincia"}` se lo stream si è interrotto e il passo riparte da capo (il testo
      ricevuto fin lì va scartato);
    - alla fine `{"type": "fine", "testo", "tool_calls", "usage", "costo", "ms", "spesa_chiave"}`,
      con le chiamate a strumenti complete (`id`, `name`, `arguments` come testo JSON)."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMError("Chiave del gateway mancante: imposta VICE_LLM_API_KEY in .env")
    payload: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True,
                     "stream_options": {"include_usage": True}}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if not ragiona and model in RAGIONAMENTO_SPEGNIBILE:
        # compiti a formato fisso: il ragionamento nascosto costa token e tempo (misura del 22/10/2026)
        payload["thinking"] = {"type": "disabled"}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    url = f"{settings.llm_base_url}/v1/chat/completions"
    inizio = time.monotonic()
    for tentativo in range(len(RIPROVA_ATTESE) + 1):
        testo, chiamate, usage, motivo = [], {}, None, {}
        ultimo = tentativo == len(RIPROVA_ATTESE)
        async with _client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode(errors="replace")[:300]
                if resp.status_code in RIPROVA_STATI and not ultimo:
                    await asyncio.sleep(RIPROVA_ATTESE[tentativo])
                    continue
                raise LLMError(f"Gateway: HTTP {resp.status_code} — {body}")
            async for ev in _leggi(resp, testo, chiamate, motivo):
                if ev.get("usage"):
                    usage = ev["usage"]
                else:
                    yield ev
            spesa = resp.headers.get("x-litellm-key-spend")
        # lo stream può interrompersi a metà (misurato il 22/10/2026 con Sonnet 5): niente motivo di chiusura
        if motivo.get("finish_reason") and not motivo.get("errore"):
            break
        if ultimo:
            raise LLMError("Il modello ha interrotto la risposta a metà. Riprova." +
                           (f" ({motivo['errore']})" if motivo.get("errore") else ""))
        yield {"type": "ricomincia", "motivo": motivo.get("errore") or "stream interrotto"}
        await asyncio.sleep(RIPROVA_ATTESE[tentativo])
    yield {"type": "fine", "testo": "".join(testo), "tool_calls": [chiamate[i] for i in sorted(chiamate)],
           "usage": usage, "costo": costo(model, usage), "ms": round((time.monotonic() - inizio) * 1000),
           "spesa_chiave": float(spesa) if spesa else None, "fine_motivo": motivo.get("finish_reason"), "modello": model}


async def _leggi(resp, testo: list, chiamate: dict, motivo: dict) -> AsyncIterator[dict]:
    """Legge lo stream SSE: delta di testo, chiamate a strumenti (accumulate), usage."""
    async for line in resp.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if chunk.get("error"):
            motivo["errore"] = str(chunk["error"].get("message", chunk["error"]) if isinstance(chunk["error"], dict) else chunk["error"])[:200]
            break
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if choice.get("finish_reason"):
                motivo["finish_reason"] = choice["finish_reason"]
            if delta.get("content"):
                testo.append(delta["content"])
                yield {"type": "delta", "text": delta["content"]}
            for tc in delta.get("tool_calls") or []:
                c = chiamate.setdefault(tc.get("index", 0), {"id": None, "name": "", "arguments": ""})
                c["id"] = tc.get("id") or c["id"]
                fn = tc.get("function") or {}
                c["name"] += fn.get("name") or ""
                c["arguments"] += fn.get("arguments") or ""
        if chunk.get("usage"):
            yield {"usage": chunk["usage"]}
