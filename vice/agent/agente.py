"""M3.1 Il loop dell'agente: function calling nativo, `tool_choice: auto`, al massimo 6 passi.

Per ogni turno:
1. prompt di sistema con l'"oggi", le definizioni citabili e lo stato della lavagna (M3.2b);
2. passi del modello in streaming: il testo arriva subito (evento `delta`), gli strumenti si eseguono
   e i risultati tornano al modello; si eseguono solo strumenti del catalogo;
3. il testo scritto nei passi di sola vista si conserva (Sonnet 5 a volte risponde lì: lezione di TIDE);
4. verifica dei numeri, un tentativo di correzione, poi le frasi che non passano si tolgono
   (decisione 31); l'evento `verifica` porta il testo finale, che sostituisce quello in streaming.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from .. import llm
from ..data.anagrafica import DICITURA, SQUADRA
from ..analysis.evidenze import con_unita, data_it, giorno_md_it
from ..config import get_settings
from .citazioni import DEFINIZIONI, Registro, testo_definizioni
from .contesto import Sessione
from .prompt import carica
from .sigle import elenco_per_il_prompt, introduci, spiegate
from .strumenti import CATALOGO, esegui, schemi
from .verifica import (Frase, Verifica, chiudi_frase, pulisci_citazioni, senza_citazioni, spunti_inventati, taglia_incompleto,
                       togli, verifica)

MAX_PASSI = 6


def evento(nome: str, dati: dict) -> dict:
    return {"evento": nome, "dati": dati}


@dataclass
class Misure:
    """Tempi, token, costo e strumenti di un turno (per l'evento `done` e il banco di prova)."""
    chiamate: list[dict] = field(default_factory=list)
    strumenti: list[dict] = field(default_factory=list)
    da_correggere: int = 0           # frasi che non passavano la prima verifica
    correzioni: list[dict] = field(default_factory=list)   # quelle frasi, col motivo (per il banco di prova)

    def aggiungi(self, fine: dict, ruolo: str, modello: str) -> None:
        self.chiamate.append({"ruolo": ruolo, "modello": fine.get("modello") or modello, "ms": fine["ms"], "costo": fine["costo"],
                              "usage": fine["usage"], "spesa_chiave": fine.get("spesa_chiave")})

    def riassunto(self) -> dict:
        tot = lambda k: sum((c["usage"] or {}).get(k, 0) for c in self.chiamate)   # noqa: E731
        costi = [c["costo"] for c in self.chiamate if c["costo"] is not None]
        return {"chiamate": len(self.chiamate), "ms_modello": sum(c["ms"] for c in self.chiamate),
                "modelli_usati": sorted({c["modello"] for c in self.chiamate}),
                "token_ingresso": tot("prompt_tokens"), "token_uscita": tot("completion_tokens"),
                "costo": round(sum(costi), 5) if costi else None, "strumenti": self.strumenti,
                "frasi_da_correggere": self.da_correggere, "correzioni": self.correzioni}


def prompt_sistema(s: Sessione, lavagna: dict | None = None, gia: set[str] | None = None) -> tuple[str, str]:
    testo, versione = carica("sistema")
    c = s.stagione.contesto(s.oggi)
    esame = ""
    if s.giorno is not None:   # decisione 47: il giorno scelto nel calendario
        g = s.stagione.contesto(s.giorno)
        esame = (f"- **Giorno in esame: {data_it(s.giorno)} ({giorno_md_it(g.giorno_md)})**, scelto dall'utente nel calendario: "
                 "le domande senza data riguardano quel giorno (gli strumenti lo usano già quando la data è vuota). "
                 f"«Oggi» resta il {data_it(s.oggi)}: se l'utente chiede un confronto con oggi, chiama gli strumenti per "
                 f"entrambi i giorni. Nei report di quel giorno «oggi» vuol dire il {data_it(s.giorno)}: tu scrivi la data.\n")
    gia_testo = ("Già spiegate in questa conversazione (scrivi solo la sigla): " + ", ".join(sorted(gia)) + ".") if gia else ""
    lav = ""
    if lavagna:
        lav = "- Sulla lavagna l'utente sta guardando: " + json.dumps(lavagna, ensure_ascii=False) + \
              ". \"Questo giocatore\" o \"questa seduta\" si riferiscono a ciò che guarda.\n"
    return testo.format(squadra=SQUADRA, oggi=data_it(s.oggi), giorno_md=giorno_md_it(c.giorno_md), seduta_di_oggi=_seduta_di_oggi(s),
                        ultima_partita=data_it(c.ultima_partita) if c.ultima_partita is not None else "nessuna",
                        prossima_partita=data_it(c.prossima_partita) if c.prossima_partita is not None else "nessuna",
                        dicitura=DICITURA, lavagna=lav, definizioni=testo_definizioni(), giorno_in_esame=esame,
                        sigle=elenco_per_il_prompt(), sigle_spiegate=gia_testo), versione


def _seduta_di_oggi(s: Sessione) -> str:
    """La riga del prompt sulla seduta di oggi (decisione 54): caricata o ancora da caricare."""
    if s.senza_seduta_caricata(s.oggi):
        return ("**La seduta di oggi non è ancora caricata.** Alle domande su oggi rispondi che serve l'export GPS di oggi "
                "(si trascina nella chat, oppure c'è il file di prova); intanto puoi rispondere sui giorni precedenti, dicendo "
                "sempre di quale giorno parli.")
    if s.visibile(s.oggi).seduta_di_oggi.empty:
        return "Oggi non c'è una seduta con dati."
    return "La seduta di oggi è caricata."


def riserva_di(modello: str) -> str:
    """Il modello di riserva se quello scelto non risponde (decisione 34): Sonnet 4.6 per l'agente e per il
    veloce; se a non rispondere è proprio la riserva, l'agente."""
    st = get_settings()
    return st.model_riserva if modello != st.model_riserva else st.model_agent


async def chiama(messaggi: list[dict], modello: str, misure: Misure, ruolo: str, tools: list[dict] | None = None,
                 max_tokens: int = 2048, ragiona: bool = True) -> dict:
    """Una chiamata senza streaming verso il client: restituisce l'evento `fine`."""
    fine = None
    async for ev in llm.passo(messaggi, modello, tools, max_tokens, riserva=riserva_di(modello), ragiona=ragiona):
        if ev["type"] == "fine":
            fine = ev
    misure.aggiungi(fine, ruolo, modello)
    return fine


def _evidenze_per_correzione(reg: Registro) -> str:
    righe = []
    for e, ev in reg.tutte().items():
        d = reg.per_il_modello(ev)
        extra = {k: v for k, v in d.items() if k not in ("evidenza", "cosa", "valore")}
        righe.append(f"[{e}] {ev.etichetta}: {d['valore']}" + (f" — {json.dumps(extra, ensure_ascii=False)}" if extra else ""))
    return "\n".join(righe) + "\n" + testo_definizioni()


async def verifica_e_correggi(testo: str, reg: Registro, modello: str, misure: Misure) -> tuple[str, Verifica, list[str]]:
    """Decisione 31: un tentativo di correzione delle frasi che non passano, poi si tolgono."""
    ver = verifica(testo, reg)
    if not ver.non_verificate:
        return testo, ver, []
    da_correggere = ver.non_verificate
    misure.da_correggere += len(da_correggere)
    misure.correzioni += [{"frase": f.testo, "motivo": f.motivo} for f in da_correggere]
    modello_testo, _ = carica("correzione")
    elenco = "\n".join(f"{i}: {f.testo}\n   (problema: {f.motivo})" for i, f in enumerate(da_correggere, 1))
    fine = await chiama([{"role": "user", "content": modello_testo.format(frasi=elenco, evidenze=_evidenze_per_correzione(reg))}],
                        modello, misure, "correzione", max_tokens=1500, ragiona=False)
    nuovo, tolte = testo, []
    for riga in fine["testo"].splitlines():
        m = re.match(r"\s*(\d+)\s*:\s*(.*)$", riga)
        if not m or not (1 <= int(m.group(1)) <= len(da_correggere)):
            continue
        originale, corretta = da_correggere[int(m.group(1)) - 1].testo, m.group(2).strip()
        if corretta.upper().strip("`*. ") == "TOGLI":
            tolte.append(originale)
            corretta = ""
        nuovo = nuovo.replace(originale, corretta, 1)
    ancora = verifica(nuovo, reg).non_verificate
    tolte += [f.testo for f in ancora]
    finale = togli(nuovo, ancora)
    return finale, verifica(finale, reg), tolte


def evidenze_citate(testo: str, reg: Registro) -> dict:
    """Le evidenze citate nel testo finale, per le citazioni cliccabili (M4.5)."""
    out = {}
    for e in sorted(set(re.findall(r"\b(E\d+)\b", testo)), key=lambda x: int(x[1:])):
        ev = reg.evidenza(e)
        if ev:
            testo = con_unita(ev.valore, ev.unita) if isinstance(ev.valore, (int, float)) and not isinstance(ev.valore, bool) else ev.valore
            out[e] = {"id": ev.id, "etichetta": ev.etichetta, "valore": ev.valore, "unita": ev.unita, "valore_testo": testo,
                      "grafico": ev.grafico, "giocatore_id": ev.contesto.get("giocatore_id")}
    return out


def togli_spunti_inventati(testo: str, ammessi: list[str], reg: Registro, ver: Verifica, tolte: list[str]) -> tuple[str, Verifica, list[str]]:
    """Gli spunti li dà solo la tabella delle regole del motore: le frasi da spunto inventate dal modello si
    tolgono e si contano tra le tolte (il banco di prova del 25/10/2026 ne ha trovata una)."""
    inventati = spunti_inventati(testo, ammessi)
    if not inventati:
        return testo, ver, tolte
    nuovo = togli(testo, [Frase(f) for f in inventati])
    return nuovo, verifica(nuovo, reg), tolte + inventati


def scegli_vista(attuale: dict | None, nuova: dict) -> dict:
    """Tra le viste suggerite dagli strumenti di un turno: vale la prima, salvo che una successiva dello
    stesso tipo sia più recente (due giorni dello stesso giocatore: si mostra il più recente, che contiene
    anche l'altro) o porti la metrica chiesta che la prima non ha."""
    if attuale is None:
        return nuova
    if nuova["vista"] != attuale["vista"]:
        return attuale
    pa, pn = attuale.get("parametri", {}), nuova.get("parametri", {})
    if pa.get("giocatore_id") != pn.get("giocatore_id"):
        return attuale
    piu_recente = (pn.get("data") or "") > (pa.get("data") or "")
    if piu_recente or (pn.get("metrica") and not pa.get("metrica")):
        metrica = pn.get("metrica") or pa.get("metrica")
        return nuova | {"parametri": {**pn, **({"metrica": metrica} if metrica else {})}}
    return attuale


def definizioni_citate(testo: str) -> dict:
    """Il testo delle definizioni fisse citate ([D1]…), per il passaggio del mouse sulle citazioni."""
    citate = set(re.findall(r"\b(D\d+)\b", testo))
    return {e: t for e, t, _ in DEFINIZIONI if e in citate}


def esito_verifica(testo: str, ver: Verifica, tolte: list[str], reg: Registro) -> dict:
    n, ok = len(ver.con_numeri), ver.verificate
    badge = f"frasi verificate: {ok}/{n}" + (f" · {len(tolte)} tolte perché non verificabili" if tolte else "")
    return {"testo": testo, "frasi_con_numeri": n, "verificate": ok, "tolte": tolte, "badge": badge,
            "evidenze": evidenze_citate(testo, reg), "definizioni": definizioni_citate(testo)}


async def turno(messaggi: list[dict], sessione: Sessione, lavagna: dict | None = None,
                modello: str | None = None) -> AsyncIterator[dict]:
    """Un turno di chat. Eventi: tappa, delta, vista, verifica, done (errori: eccezioni al chiamante)."""
    modello = modello or get_settings().model_agent
    reg, misure = Registro(f"{sessione.oggi:%Y-%m-%d}"), Misure()
    gia = spiegate([m["content"] for m in messaggi if m["role"] == "assistant"])   # sigle già spiegate (decisione 48)
    sistema, versione = prompt_sistema(sessione, lavagna, gia)
    reg.registra_date(sistema)                                   # oggi, ultima e prossima partita
    for m in messaggi:                                           # date nominate dall'utente o già dette
        reg.registra_date(m["content"])
    msgs = [{"role": "system", "content": sistema}] + [
        {"role": m["role"], "content": senza_citazioni(m["content"]) if m["role"] == "assistant" else m["content"]}
        for m in messaggi]
    tools = schemi()
    portato: list[str] = []
    spunti_forniti: list[str] = []
    vista, vista_suggerita = None, None
    risposta = None
    for n in range(MAX_PASSI):
        fine = None
        async for ev in llm.passo(msgs, modello, tools, riserva=riserva_di(modello)):
            if ev["type"] == "delta":
                yield evento("delta", {"text": ev["text"], "passo": n})
            elif ev["type"] == "ricomincia":
                yield evento("ricomincia", {"passo": n})
            else:
                fine = ev
        misure.aggiungi(fine, "agente", modello)
        chiamate = fine["tool_calls"]
        testo = (fine["testo"] or "").strip()
        if fine.get("fine_motivo") == "length" and not chiamate:
            testo = taglia_incompleto(testo)
        if not chiamate:
            risposta = "\n\n".join(portato + ([testo] if testo else []))
            break
        for c in chiamate:
            c["id"] = c["id"] or f"call_{uuid.uuid4().hex[:12]}"
            c["arguments"] = c["arguments"] or "{}"
        msgs.append({"role": "assistant", "content": testo or None,
                     "tool_calls": [{"id": c["id"], "type": "function",
                                     "function": {"name": c["name"], "arguments": c["arguments"]}} for c in chiamate]})
        if testo and all(c["name"] == "mostra_vista" for c in chiamate):
            portato.append(testo)
        for c in chiamate:
            st = CATALOGO.get(c["name"])
            yield evento("tappa", {"testo": st.tappa if st else c["name"], "strumento": c["name"]})
            risultato, uscita, errore = await asyncio.to_thread(esegui, c["name"], c["arguments"], sessione, reg)
            misure.strumenti.append({"nome": c["name"], "argomenti": c["arguments"], "errore": errore})
            if uscita:
                spunti_forniti += [sp["testo"] for sp in uscita.dati.get("da_guardare", []) if isinstance(sp, dict)]
            if uscita and uscita.vista:
                if c["name"] == "mostra_vista":
                    vista = uscita.vista | {"origine": "agente"}
                else:
                    vista_suggerita = scegli_vista(vista_suggerita, uscita.vista | {"origine": "automatica"})
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": risultato})
    if risposta is None:
        risposta = "\n\n".join(portato) or "Non sono riuscito a concludere in pochi passi: prova a semplificare la domanda."
    risposta = pulisci_citazioni(chiudi_frase(risposta))
    yield evento("tappa", {"testo": "verifico i numeri", "strumento": None})
    finale, ver, tolte = await verifica_e_correggi(risposta, reg, modello, misure)
    finale, ver, tolte = togli_spunti_inventati(finale, spunti_forniti, reg, ver, tolte)
    finale = introduci(finale, gia)                              # la prima volta, ogni sigla col suo significato
    if vista or vista_suggerita:
        yield evento("vista", vista or vista_suggerita)
    yield evento("verifica", esito_verifica(finale, ver, tolte, reg))
    yield evento("done", {"modello": modello, "prompt": versione, "spunti_forniti": spunti_forniti, **misure.riassunto()})
