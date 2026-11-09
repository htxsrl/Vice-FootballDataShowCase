"""L'archivio degli avvisi e il loro stato (decisione 54, wiki/metodi/avvisi.md#nellinterfaccia-decisione-54).

- **Archivio:** gli avvisi mostrati di ogni giorno di seduta della stagione, calcolati "come quel giorno" con le
  righe del dataset (come la taratura), in data/processed/avvisi/archivio.json. Il file porta la **firma** del
  codice e dei dati che l'hanno prodotto: se una regola cambia, la firma non torna più e l'archivio si ricalcola
  (circa 80 s, senza costi). Lo rifà anche `python3 -m scripts.prepara_avvisi`.
- **Stato:** a un dato giorno ogni avviso è «aperto», «aggiornato» (un avviso più recente della stessa famiglia sullo
  stesso giocatore ne prende il posto; per rientri e note positive basta un avviso più recente qualsiasi sullo stesso
  giocatore), «chiuso» (la situazione è finita: un calo o un rientro con la nota «tornato nel suo solito», un
  dato che è tornato) o «scaduto» (gli avvisi di un giorno solo alla partita successiva; un calo dopo le due
  settimane della sua regola). Il «Visto» del preparatore sta nel browser, non qui.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path

import pandas as pd

from ..config import get_settings
from ..data.stagione import Stagione, stagione
from .avvisi import CATEGORIE, avvisi, classificazione, scegli
from .comune import tutte_le_righe

log = logging.getLogger("vice.avvisi")

DURATA_CALO = 14            # giorni: la finestra della regola del calo persistente
CARTELLA_CODICE = Path(__file__).resolve().parent.parent
STATI = ("aperto", "aggiornato", "chiuso", "scaduto")
INFORMANO = {f for f, c in CATEGORIE.items() if c == "informa"}   # rientri e note positive


def percorso() -> Path:
    return get_settings().processed_dir / "avvisi" / "archivio.json"


def firma() -> str:
    """Impronta del codice delle analisi (tranne questo file, che non cambia gli avvisi) e dei dati elaborati."""
    h = hashlib.sha1()
    sorgenti = sorted(p for p in (CARTELLA_CODICE / "analysis").glob("*.py") if p.name != Path(__file__).name)
    sorgenti += [CARTELLA_CODICE / "data" / n for n in ("stagione.py", "zenodo.py", "anagrafica.py")]
    dati = sorted((get_settings().processed_dir / "zenodo").glob("*"))
    for p in sorgenti + dati:
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def calcola(st: Stagione | None = None, fino_a=None) -> dict[str, list[dict]]:
    """Gli avvisi mostrati di ogni giorno di seduta (giorno, riassunto settimanale, qualità del dato), ognuno visto
    col solo suo passato. Le chiavi sono "AAAA-MM-GG"; un giorno senza avvisi ha la lista vuota."""
    st = st or stagione()
    fino_a = pd.Timestamp(fino_a) if fino_a is not None else st.fine
    c = classificazione(tutte_le_righe(st.al(fino_a)))
    out = {}
    for d in sorted(pd.Timestamp(x) for x in st.giorni_di_seduta if pd.Timestamp(x) <= fino_a):
        s = scegli(avvisi(st.al(d), c))
        out[f"{d:%Y-%m-%d}"] = [a.to_dict() for lista in (s["giorno"], s["riassunto"], s["dato"]) for a in lista]
    return out


def salva(giorni: dict[str, list[dict]], f: str | None = None) -> Path:
    p = percorso()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"firma": f or firma(), "giorni": giorni}, ensure_ascii=False, indent=1, default=str) + "\n",
                 encoding="utf-8")
    return p


def leggi() -> dict | None:
    try:
        return json.loads(percorso().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_archivio: dict[str, list[dict]] | None = None
_lucchetto = threading.Lock()


def archivio() -> dict[str, list[dict]]:
    """L'archivio in memoria: dal file se la firma torna, altrimenti ricalcolato (e salvato, se si può)."""
    global _archivio
    with _lucchetto:
        if _archivio is None:
            f = firma()
            salvato = leggi()
            if salvato and salvato.get("firma") == f:
                _archivio = salvato["giorni"]
            else:
                log.warning("archivio degli avvisi da ricalcolare (firma cambiata): circa 80 s")
                _archivio = calcola()
                try:
                    salva(_archivio, f)
                except OSError as e:   # per esempio un disco in sola lettura: si tiene in memoria
                    log.warning("archivio degli avvisi non salvato: %s", e)
        return _archivio


def svuota_cache() -> None:
    global _archivio
    with _lucchetto:
        _archivio = None


# ---------- lo stato a un dato giorno ----------

def _sovrapposte(a: dict, b: dict) -> bool:
    return not a.get("metriche") or not b.get("metriche") or bool(set(a["metriche"]) & set(b["metriche"]))


def _evento(a: dict, dopo: list[dict], fino_al: str, partite: list[str], presenze: dict[int, set[str]]) -> tuple | None:
    """Il primo fatto, entro `fino_al`, che toglie l'avviso `a` da quelli aperti: (data, stato, motivo, id)."""
    eventi = []
    gid = a.get("giocatore_id")
    if gid is not None:
        for b in dopo:
            if b["giocatore_id"] != gid:
                continue
            if b.get("chiude") == a["famiglia"] and _sovrapposte(a, b):
                eventi.append((b["data"], "chiuso", "tornato nel suo solito", b["id"]))
            elif b["famiglia"] == a["famiglia"]:   # stessa famiglia, stesso giocatore: vale il più recente
                eventi.append((b["data"], "aggiornato", "c'è un avviso più recente", b["id"]))
            elif a["famiglia"] in INFORMANO:
                # una buona notizia o un rientro non restano aperti accanto a un avviso più recente sullo stesso
                # giocatore (dati mancanti, un calo…): direbbero il contrario (08/11/2026, Guidi il 19/04)
                eventi.append((b["data"], "aggiornato", "c'è un avviso più recente", b["id"]))
        if a["famiglia"] == "dato" and not a.get("urgente"):
            tornati = sorted(d for d in presenze.get(gid, ()) if a["data"] < d <= fino_al)
            if tornati:
                eventi.append((tornati[0], "chiuso", "i dati sono tornati", None))
    if a["famiglia"] == "calo" and not a.get("riassunto"):
        fine = f"{pd.Timestamp(a['data']) + pd.Timedelta(days=DURATA_CALO):%Y-%m-%d}"
        if fine <= fino_al:
            eventi.append((fine, "scaduto", "passate le due settimane della regola", None))
    else:
        partita = next((p for p in partite if p > a["data"]), None)
        if partita is not None and partita <= fino_al:
            eventi.append((partita, "scaduto", "c'è stata la partita", None))
    eventi = [e for e in eventi if e[0] <= fino_al]
    return min(eventi, key=lambda e: e[0]) if eventi else None


def con_lo_stato(per_giorno: dict[str, list[dict]], fino_al, partite, presenze: dict[int, set[str]] | None = None) -> list[dict]:
    """Tutti gli avvisi nati fino a `fino_al`, ciascuno col suo stato a quel giorno; dal più recente.

    `partite`: le date delle partite; `presenze`: giocatore → giorni con dati (per chiudere gli avvisi sui dati
    mancanti quando i dati tornano)."""
    fino = f"{pd.Timestamp(fino_al):%Y-%m-%d}"
    partite = sorted(f"{pd.Timestamp(p):%Y-%m-%d}" for p in partite)
    presenze = presenze or {}
    tutti = sorted((dict(a) for d, lista in per_giorno.items() if d <= fino for a in lista),
                   key=lambda a: (a["data"], a["priorita"]))
    for i, a in enumerate(tutti):
        dopo = [b for b in tutti[i + 1:] if b["data"] > a["data"]]
        ev = _evento(a, dopo, fino, partite, presenze)
        if ev is None:
            a.update(stato="aperto", stato_dal=None, stato_motivo=None, stato_da=None)
        else:
            a.update(stato=ev[1], stato_dal=ev[0], stato_motivo=ev[2], stato_da=ev[3])
    return sorted(tutti, key=lambda a: (a["data"], -a["priorita"]), reverse=True)


def presenze_da(righe: pd.DataFrame) -> dict[int, set[str]]:
    """Giocatore → giorni (AAAA-MM-GG) in cui ha dati."""
    if righe.empty:
        return {}
    return {int(g): {f"{d:%Y-%m-%d}" for d in s} for g, s in righe.groupby("giocatore_id")["data"]}
