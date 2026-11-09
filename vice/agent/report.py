"""M3.4-M3.6 I report: seduta, settimana, giocatore, per il preparatore.

Decisione 32: una sola chiamata al modello con i dati del motore già calcolati (niente strumenti).
1. `analisi_per_report` (M2) → dati compatti per sezione, con le evidenze etichettate;
2. il modello dell'agente scrive il report con struttura fissa → verifica e correzione (decisione 31).
Un solo report, pensato per il preparatore (decisione 51): le riscritture per allenatore e giocatore non ci
sono più. Il report resta in una piccola cache; quelli della seduta generati in anticipo (archivio.py,
decisione 49) si leggono da data/processed/report/, dopo aver ricontrollato i loro numeri. La prima volta
che compare, ogni sigla ha il suo significato (sigle.py, decisione 48).
Decisione 54: in testa al report, prima del testo del modello, gli avvisi di Vice scritti dal codice (evento
`avvisi`): della seduta, quelli nati quel giorno; della settimana, quelli ancora aperti; del giocatore, i suoi.
La sezione «Spunti per lo staff» non c'è più, e dai report pronti si toglie alla lettura.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import OrderedDict
from collections.abc import AsyncIterator

from .. import llm
from ..analysis.evidenze import Evidenza, data_it, giorno_md_it
from ..analysis.motore import Analisi, analisi_per_report
from ..config import get_settings
from . import archivio, da_guardare
from .agente import Misure, esito_verifica, evento, riserva_di, togli_spunti_inventati, verifica_e_correggi
from .citazioni import Registro
from .contesto import ErroreStrumento, Sessione
from .prompt import carica
from .sigle import elenco_per_il_prompt, introduci
from .verifica import pulisci_citazioni, taglia_incompleto, verifica

TIPI = ("seduta", "settimana", "giocatore")
METRICHE_PRINCIPALI = ("td", "hsr", "spr")
_CACHE: "OrderedDict[tuple, tuple[str, Registro, dict]]" = OrderedDict()
_CACHE_MAX = 32


def _blocco(reg: Registro, evidenze: list[Evidenza | None], **extra) -> dict:
    visti, out = set(), []
    for e in evidenze:
        if e is not None and e.id not in visti:
            visti.add(e.id)
            out.append(reg.per_il_modello(e))
    return {k: v for k, v in extra.items() if v not in (None, [], {})} | ({"evidenze": out} if out else {})


def _cerca(an: Analisi, i: str) -> Evidenza | None:
    return an.evidenze().get(i)


def avvisi_del_report(tipo: str, s: Sessione, giocatore_id: int | None = None) -> list[dict]:
    """Gli avvisi in testa al report (decisione 54). Nel report del giocatore niente confronti coi compagni (D6):
    restano fuori lo scarto di reparto e la settimana rispetto ai compagni."""
    if tipo == "seduta":
        return da_guardare.del_giorno(s, s.oggi)
    if tipo == "settimana":
        return [a for a in da_guardare.stato(s)["avvisi"] if a["stato"] == "aperto"]
    return [a for a in da_guardare.del_giocatore(s, giocatore_id) if a["famiglia"] not in ("reparto", "settimana")]


def senza_spunti(testo: str) -> str:
    """Il testo di un report pronto senza la sezione «Spunti per lo staff» (decisione 54): ora ci sono gli avvisi."""
    righe, fuori = [], False
    for r in testo.split("\n"):
        if r.startswith("## "):
            fuori = r[3:].strip().lower().startswith("spunti per lo staff")
        if not fuori:
            righe.append(r)
    return "\n".join(righe).strip()


def _avvisi(an: Analisi) -> list[str]:
    visti = []
    for r in an.analisi.values():
        for a in r.avvisi:
            if a not in visti:
                visti.append(a)
    return visti


def _seduta(an: Analisi, reg: Registro) -> dict:
    r = an.analisi["seduta"]
    s = r.sintesi
    if not s.get("giocatori"):
        return {"nota": "nessuna seduta con dati oggi"}
    d = f"{s['data']:%Y-%m-%d}"
    return _blocco(reg, [_cerca(an, f"seduta/{d}/squadra/fuori")] + [e for e in r.evidenze if e.id.startswith(f"seduta/{d}/squadra/")]
                   + [_cerca(an, f["evidenza"]) for f in s["fuori_fascia"][:10]] + [_cerca(an, f["evidenza"]) for f in s["ai_margini"][:5]],
                   tipo=s["tipo"], giorno_md=giorno_md_it(s["giorno_md"]), giocatori=s["giocatori"])


def _velocita(an: Analisi, reg: Registro) -> dict:
    r = an.analisi["esposizione_velocita"]
    if r.tabella.empty:
        return {}
    p = f"velocita/{r.sintesi['partita']:%Y-%m-%d}"
    bassi = {x["giocatore_id"] for x in r.sintesi.get("sotto_il_solito", [])}
    return _blocco(reg, [_cerca(an, f"{p}/sintesi")] + [e for e in r.evidenze if e.contesto.get("giocatore_id") in bassi][:10],
                   finestra_completa=r.sintesi["finestra_completa"])


def _postpartita(an: Analisi, reg: Registro) -> dict:
    r = an.analisi["compensazione"]
    if r.tabella.empty:
        return {}
    p = f"compensazione/{r.sintesi['partita']:%Y-%m-%d}"
    rilevanti = r.tabella[r.tabella["esito"].isin(["sotto il solito", "molto sotto il solito"])]["giocatore_id"]
    titolari = [_cerca(an, x["evidenza"]) for x in r.sintesi.get("titolari_postpartita_sopra", [])][:4]
    return _blocco(reg, [_cerca(an, f"{p}/esiti"), _cerca(an, f"{p}/gruppo/hsr")]
                   + [_cerca(an, f"{p}/{g}/hsr") for g in rilevanti][:8] + titolari,
                   partita=data_it(r.sintesi["partita"]), finestra_aperta=r.sintesi["finestra_aperta"])


def _forma(an: Analisi, reg: Registro) -> dict:
    r = an.analisi["forma_settimana"]
    if r.tabella.empty:
        return {}
    ev = [e for e in r.evidenze if e.contesto.get("metrica") in ("td", "hsr")]
    return _blocco(reg, ev, settimana_regolare=r.sintesi.get("settimana_regolare"),
                   settimane_di_riferimento=r.sintesi.get("settimane_di_riferimento"))


def _griglia(an: Analisi, reg: Registro) -> dict:
    r = an.analisi.get("griglia_settimana")
    if r is None or r.tabella.empty:
        return {}
    ev = [e for e in r.evidenze if e.contesto.get("posizione") in ("molto sopra", "molto sotto")
          and e.contesto.get("metrica") in METRICHE_PRINCIPALI]
    return _blocco(reg, ev[:12])


def _partita(an: Analisi, reg: Registro, giocatore_id: int | None = None) -> dict:
    r = an.analisi.get("allenamento_partita")
    if r is None or r.tabella.empty:
        return {}
    if giocatore_id is None:
        ev = [e for e in r.evidenze if "/squadra/" in e.id]
    else:
        ev = [e for e in r.evidenze if e.contesto.get("giocatore_id") == giocatore_id and e.contesto.get("metrica") in METRICHE_PRINCIPALI]
    return _blocco(reg, ev)


def _qualita(an: Analisi, reg: Registro) -> dict:
    ev = an.evidenze()
    incompleti = [{"giocatore": q["giocatore"], "finestra": q["finestra"], "copertura": q["copertura"],
                   "sedute_con_dati": q["sedute"], "sedute_della_squadra": q["sedute_squadra"],
                   "evidenza": reg.etichetta(ev[q["evidenza"]])} for q in an.qualita if q["evidenza"] in ev]
    return {"dati_incompleti": incompleti, "avvertenze": _avvisi(an)}


def struttura(tipo: str, giorno_md: int | None) -> list[tuple[str, str]]:
    """Le sezioni del report del preparatore: (titolo, cosa scrivere)."""
    if tipo == "seduta":
        sezioni = [("Sintesi", "2-3 frasi: com'è andata la seduta rispetto al carico abituale di quel giorno"),
                   ("Fuori fascia", "chi è fuori dalla fascia larga, su quale metrica e di quanto")]
        if giorno_md in (0, 1, 2):
            sezioni.append(("Titolari e non titolari", "il carico postpartita: non titolari rispetto al loro solito, titolari sopra fascia"))
        elif giorno_md in (-2, -1):
            sezioni.append(("Verso la partita", "l'alta velocità registrata da MD-4 a MD-2"))
        return sezioni + [("Qualità del dato e limiti", "dati incompleti e avvertenze")]
    if tipo == "settimana":
        return [("Sintesi", "2-3 frasi sulla settimana"), ("Forma della settimana", "sedute di squadra rispetto alla settimana tipo"),
                ("Alta velocità", "chi ha registrato poca alta velocità da MD-4 a MD-2"),
                ("Postpartita", "il carico postpartita dei non titolari e dei titolari"),
                ("Allenamento rispetto alla partita", "la settimana finora in % della partita di riferimento"),
                ("Qualità del dato e limiti", "dati incompleti e avvertenze")]
    return [("Sintesi", "2-3 frasi sul giocatore"), ("La seduta di oggi", "le sue metriche rispetto alla sua fascia"),
            ("Andamento", "ultime 4 settimane rispetto al suo solito"),
            ("Allenamento rispetto alla partita", "la sua settimana in % della sua partita di riferimento"),
            ("Alta velocità e postpartita", "le sue finestre"), ("Qualità del dato e limiti", "dati incompleti e avvertenze")]


def dati_report(an: Analisi, reg: Registro, s: Sessione, giocatore_id: int | None = None,
                avvisi: list[dict] | None = None, etichette_degli_spunti: bool = False) -> dict:
    """I dati del report per il modello. `etichette_degli_spunti`: per rileggere i report pronti scritti coi prompt
    di prima (fino a report_v3), che avevano la sezione degli spunti: le loro evidenze prendono ancora le etichette
    di allora, così le citazioni che seguono (la qualità del dato) restano le stesse."""
    c = s.stagione.contesto(s.oggi)
    base = {"oggi": data_it(s.oggi), "giorno_md": giorno_md_it(c.giorno_md),
            "ultima_partita": data_it(c.ultima_partita) if c.ultima_partita is not None else None,
            "prossima_partita": data_it(c.prossima_partita) if c.prossima_partita is not None else None}
    if an.tipo == "seduta":
        d = {"seduta": _seduta(an, reg)}
        if c.giorno_md in (0, 1, 2):
            d["postpartita"] = _postpartita(an, reg)
        elif c.giorno_md in (-2, -1):
            d["alta_velocita"] = _velocita(an, reg)
    elif an.tipo == "settimana":
        d = {"forma_della_settimana": _forma(an, reg), "fuori_fascia_nella_settimana": _griglia(an, reg),
             "alta_velocita": _velocita(an, reg), "postpartita": _postpartita(an, reg), "allenamento_vs_partita": _partita(an, reg)}
    else:
        mie = lambda nome: [e for e in an.analisi[nome].evidenze if e.contesto.get("giocatore_id") == giocatore_id]   # noqa: E731
        d = {"giocatore": s.nome(giocatore_id), "seduta_di_oggi": _blocco(reg, mie("seduta")),
             "andamento": _blocco(reg, an.analisi["andamento"].evidenze, avvisi=an.analisi["andamento"].avvisi),
             "allenamento_vs_partita": _partita(an, reg, giocatore_id),
             "alta_velocita": _blocco(reg, mie("esposizione_velocita")), "postpartita": _blocco(reg, mie("compensazione")),
             "nota": "solo i dati del giocatore: niente confronti con i compagni"}
    mostrati = [a["testo"] for a in (avvisi or [])]
    if etichette_degli_spunti:
        ev = an.evidenze()
        for sp in an.spunti:
            for i in sp.evidenze:
                if i in ev:
                    reg.etichetta(ev[i])
    return base | d | ({"avvisi_gia_mostrati": mostrati} if mostrati else {}) | {"qualita_del_dato": _qualita(an, reg)}


def _titolo(tipo: str, s: Sessione, nome: str | None) -> str:
    if tipo == "seduta":
        return f"della seduta del {data_it(s.oggi)}"
    if tipo == "settimana":
        return f"della settimana fino al {data_it(s.oggi)}"
    return f"di {nome} al {data_it(s.oggi)}"


def _dall_archivio(s: Sessione, gid: int | None) -> tuple[str, Registro, dict] | None:
    """Il report pronto del giorno, se c'è e se i suoi numeri tornano ancora coi dati del motore."""
    salvato = archivio.leggi(s.oggi)
    if not salvato or not salvato.get("testo"):
        return None
    an = analisi_per_report(s.visibile(), "seduta", gid)
    reg = Registro(f"{s.oggi:%Y-%m-%d}")
    versione = re.fullmatch(r"report_v(\d+)", salvato.get("prompt") or "")
    con_spunti = versione is None or int(versione.group(1)) < 4
    dati = dati_report(an, reg, s, gid, etichette_degli_spunti=con_spunti)
    reg.registra_date(json.dumps(dati, ensure_ascii=False, default=str))
    testo = senza_spunti(salvato["testo"])
    ver = verifica(testo, reg)
    if ver.non_verificate:
        return None
    return testo, reg, esito_verifica(testo, ver, salvato.get("tolte", []), reg)


async def report(tipo: str, s: Sessione, giocatore: str | None = None, modello: str | None = None,
                 usa_archivio: bool = True) -> AsyncIterator[dict]:
    """Eventi: avvisi (decisione 54), tappa, delta, verifica, done (come la chat)."""
    if tipo not in TIPI:
        raise ErroreStrumento(f"report sconosciuto: {tipo}")
    if tipo == "giocatore" and not giocatore:
        raise ErroreStrumento("la scheda del giocatore richiede il giocatore")
    modello = modello or get_settings().model_agent
    gid = s.giocatore(giocatore) if giocatore else None
    if tipo == "seduta" and (motivo := s.senza_seduta_caricata(s.oggi)):
        raise ErroreStrumento(f"Non posso scrivere il report: {motivo}.")
    misure = Misure()
    # decisione 54: prima di tutto gli avvisi, scritti dal codice
    avvisi = await asyncio.to_thread(avvisi_del_report, tipo, s, gid)
    yield evento("avvisi", {"tipo": tipo, "giorno": f"{s.oggi:%Y-%m-%d}", "avvisi": avvisi})
    chiave = (tipo, s.chiave, gid, modello)
    versione = None
    dalla_cache = chiave in _CACHE
    dall_archivio = False
    dal_dataset = s.caricamento is None or s.caricamento.dal_dataset
    if not dalla_cache and usa_archivio and tipo == "seduta" and dal_dataset and s.giorno is None:
        pronto = await asyncio.to_thread(_dall_archivio, s, gid)
        if pronto is not None:
            _CACHE[chiave] = pronto
            dalla_cache = dall_archivio = True

    if dalla_cache:
        _, _, esito = _CACHE[chiave]
        _CACHE.move_to_end(chiave)
    else:
        yield evento("tappa", {"testo": "leggo i dati del motore", "strumento": None})
        an = await asyncio.to_thread(analisi_per_report, s.visibile(), tipo, gid)
        reg = Registro(f"{s.oggi:%Y-%m-%d}")
        dati = dati_report(an, reg, s, gid, avvisi)
        reg.registra_date(json.dumps(dati, ensure_ascii=False, default=str))
        modello_testo, versione = carica("report")
        sezioni = struttura(tipo, s.stagione.contesto(s.oggi).giorno_md)
        prompt = modello_testo.format(titolo=_titolo(tipo, s, s.nome(gid) if gid else None),
                                      struttura="\n".join(f"- `## {t}`: {c}" for t, c in sezioni),
                                      dati=json.dumps(dati, ensure_ascii=False, indent=1, default=str),
                                      sigle=elenco_per_il_prompt())
        yield evento("tappa", {"testo": "scrivo il report", "strumento": None})
        testo, fine = [], None
        async for ev in llm.passo([{"role": "user", "content": prompt}], modello, max_tokens=3000, riserva=riserva_di(modello),
                                  ragiona=False):
            if ev["type"] == "delta":
                testo.append(ev["text"])
                yield evento("delta", {"text": ev["text"], "passo": 0})
            elif ev["type"] == "ricomincia":
                testo = []
                yield evento("ricomincia", {"passo": 0})
            else:
                fine = ev
        misure.aggiungi(fine, "report", modello)
        bozza = pulisci_citazioni("".join(testo).strip())
        if fine.get("fine_motivo") == "length":
            bozza = taglia_incompleto(bozza) + "\n\n_Report accorciato: il modello ha raggiunto la lunghezza massima._"
        yield evento("tappa", {"testo": "verifico i numeri", "strumento": None})
        finale, ver, tolte = await verifica_e_correggi(bozza, reg, modello, misure)
        ammessi = dati.get("avvisi_gia_mostrati", [])
        finale, ver, tolte = togli_spunti_inventati(finale, ammessi, reg, ver, tolte)
        finale = introduci(finale)                         # la prima volta, ogni sigla col suo significato
        esito = esito_verifica(finale, ver, tolte, reg)
        _CACHE[chiave] = (finale, reg, esito)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)

    yield evento("verifica", esito)
    yield evento("done", {"modello": modello, "prompt": versione or "dalla cache", "tipo": tipo,
                          "report_dalla_cache": dalla_cache, "report_pronto": dall_archivio, **misure.riassunto()})


def svuota_cache() -> None:
    _CACHE.clear()
