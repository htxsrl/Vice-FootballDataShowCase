"""Modello di prova (deterministico, gratuito) per provare l'interfaccia di Vice da capo a fondo.

Si accende solo con `VICE_LLM_PROVA=1` (vedi `scripts/prova_interfaccia.py`, che lo usa in un container
separato sulla porta 8743): l'app normale non lo usa mai. Prende il posto di `llm.passo` e ne imita gli
eventi (`delta`, `fine`), così tutto il resto è quello vero: strumenti, motore, verifica dei numeri e dei
giudizi, eventi della chat, viste della lavagna, report.

- **Agente:** sceglie gli strumenti dalle parole della domanda (giocatori, metriche, date, parole chiave) e risponde copiando etichette, numeri e posizioni dalle evidenze che riceve.
- **Report:** copia le evidenze dai dati nel prompt. **Correzione:** toglie le frasi.

Non è un modello linguistico: serve a controllare che i pezzi si parlino, non la qualità delle risposte.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator

from .data.anagrafica import GIOCATORI

NOME = "modello-di-prova"
METRICHE = [("distanza", "td"), ("alta velocit", "hsr"), ("hsr", "hsr"), ("sprint", "spr"), ("accelerazion", "acc"),
            ("decelerazion", "dcc"), ("hmld", "hmld"), ("metabolic", "hmld")]
TRABOCCHETTI = ("infortun", "acwr", "migliore", "minuti ha giocato", "velocità massima", "rischio")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre")


def _giocatori(q: str) -> list[str]:
    """I giocatori nominati (cognome o nome completo), nell'ordine in cui compaiono; poi la maglia."""
    trovati = []
    for _, (nome, cognome, numero, _) in sorted(GIOCATORI.items()):
        i = q.find(cognome.lower())
        if i >= 0:
            trovati.append((i, f"{nome} {cognome}"))
    trovati = [n for _, n in sorted(trovati)]
    m = re.search(r"\b(?:numero|maglia|il|la)\s+(\d{1,2})\b", q)
    if not trovati and m:
        trovati.append(m.group(1))
    return trovati


def _date(q: str) -> list[str]:
    out = [m.group(0) for m in re.finditer(r"\b\d{1,2}/\d{1,2}(?:/\d{4})?\b", q)]
    out += [m.group(0) for m in re.finditer(r"\b\d{1,2} (?:" + "|".join(MESI) + r")\b", q)]
    if "ieri" in q:
        out.append("ieri")
    return out


def _metrica(q: str) -> str | None:
    return next((m for parola, m in METRICHE if parola in q), None)


def scegli_strumenti(domanda: str) -> list[tuple[str, dict]]:
    """Le chiamate a strumenti per una domanda, con regole semplici e prevedibili."""
    q = domanda.lower()
    giocatori, date, metrica = _giocatori(q), _date(q), _metrica(q)
    con_metrica = {"metrica": metrica} if metrica else {}
    if any(t in q for t in TRABOCCHETTI):
        return [("limiti", {"domanda": domanda})]
    if "numeri sono giusti" in q or "verific" in q:
        return [("verifica_motore", {})]
    if len(giocatori) >= 2 and "confront" in q:
        return [("confronta", {"giocatori": giocatori})]
    if "partita" in q and "allenat" in q:
        return [("allenamento_vs_partita", {**({"giocatore": giocatori[0]} if giocatori else {}), **con_metrica})]
    if "compensat" in q or "postpartita" in q:
        return [("postpartita", {})]
    if "prima della partita" in q or "arriviamo" in q:
        return [("alta_velocita", {})]
    if giocatori:
        chiamate = [("giocatore", {"giocatore": giocatori[0], "data": d, **con_metrica}) for d in date]
        if not date or "oggi" in q:
            chiamate.append(("giocatore", {"giocatore": giocatori[0], **con_metrica}))
        return chiamate
    if "settimana" in q:
        out = [("settimana", con_metrica)]
        if "lavagna" in q or "vedere" in q or "mostra" in q:
            out.append(("mostra_vista", {"vista": "settimana", "parametri": con_metrica}))
        return out
    return [("seduta", {**({"data": date[0]} if date else {}), **con_metrica})]


def _frase(ev: dict) -> str:
    """Una frase da un'evidenza: cosa, valore, posizione rispetto alla fascia, etichetta."""
    pos = ev.get("posizione") or ev.get("esito")
    parti = f"{ev['cosa']}: {ev['valore']}"
    if pos in ("molto sopra", "sopra", "sotto", "molto sotto"):
        parti += f", {pos} la sua fascia"
    elif pos == "dentro":
        parti += ", dentro la sua fascia"
    return f"- {parti} [{ev['evidenza']}]."


def risposta(risultati: list[dict]) -> str:
    """La risposta dai risultati degli strumenti: le evidenze più rilevanti, copiate."""
    righe = ["Ecco cosa dicono i dati."]
    for r in risultati:
        if r.get("errore"):
            righe.append(f"Non riesco a rispondere: {r['errore']}.")
        if r.get("limiti"):
            righe.append("Questa domanda va oltre ciò che i dati permettono: non posso rispondere con i numeri.")
        evidenze = r.get("evidenze") or []
        fuori = [e for e in evidenze if (e.get("posizione") or e.get("esito")) not in (None, "dentro", "in linea")]
        for e in (fuori + [e for e in evidenze if e not in fuori])[:6]:
            righe.append(_frase(e))
    return "\n".join(righe)


def _report(prompt: str) -> str:
    """Un report dai dati nel prompt: le prime evidenze, copiate."""
    righe = ["## Sintesi", "Il report del modello di prova copia i dati del motore."]
    for m in list(re.finditer(r'"evidenza":\s*"(E\d+)",\s*"cosa":\s*"((?:[^"\\]|\\.)*)",\s*"valore":\s*"((?:[^"\\]|\\.)*)"', prompt))[:8]:
        righe.append(f"- {json.loads(chr(34) + m.group(2) + chr(34))}: {json.loads(chr(34) + m.group(3) + chr(34))} [{m.group(1)}].")
    return "\n".join(righe)


async def passo(messages: list[dict], model: str, tools: list[dict] | None = None, max_tokens: int = 2048,
                riserva: str | None = None, ragiona: bool = True) -> AsyncIterator[dict]:
    testo, chiamate = "", []
    if tools:
        ultimo_utente = max(i for i, m in enumerate(messages) if m["role"] == "user")
        dopo = messages[ultimo_utente + 1:]
        risultati = [json.loads(m["content"]) for m in dopo if m["role"] == "tool"]
        if not dopo:
            chiamate = [{"id": f"prova_{uuid.uuid4().hex[:8]}", "name": n, "arguments": json.dumps(a, ensure_ascii=False)}
                        for n, a in scegli_strumenti(messages[ultimo_utente]["content"])]
        else:
            testo = risposta(risultati)
    else:
        prompt = messages[-1]["content"]
        if "(problema:" in prompt:                       # correzione: si tolgono le frasi
            n = len(re.findall(r"^\d+:", prompt, re.M))
            testo = "\n".join(f"{i}: TOGLI" for i in range(1, n + 1))
        else:
            testo = _report(prompt)
    for i in range(0, len(testo), 40):
        yield {"type": "delta", "text": testo[i:i + 40]}
    yield {"type": "fine", "testo": testo, "tool_calls": chiamate, "usage": {"prompt_tokens": 0, "completion_tokens": 0},
           "costo": 0.0, "ms": 1, "spesa_chiave": None, "fine_motivo": "tool_calls" if chiamate else "stop", "modello": NOME}
