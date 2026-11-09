"""«Da guardare» (decisione 54): gli avvisi di Vice per chi usa l'app.

Gli avvisi di un giorno nascono quando la sua seduta è caricata: per i giorni nei dati del club vengono
dall'archivio (vice/analysis/archivio_avvisi.py), per un file modificato si calcolano al momento. Lo stato a un
giorno (aperto, aggiornato, chiuso, scaduto) è quello dell'archivio; il «Visto» lo tiene il browser.
Ogni avviso porta anche il grafico da aprire sulla lavagna («Mostra») e la domanda per «Chiedi a Vice».
Regole: wiki/metodi/avvisi.md#nellinterfaccia-decisione-54.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from functools import lru_cache

import pandas as pd

from ..analysis.archivio_avvisi import archivio, con_lo_stato, presenze_da
from ..analysis.avvisi import avvisi, classificazione, con_la_seduta, scegli
from ..analysis.comune import tutte_le_righe
from ..analysis.evidenze import Evidenza, data_it, giorno_md_it
from ..analysis.seduta import evidenze_classifica
from ..analysis.spunti import ultime_sedute_classificate
from ..data.stagione import stagione
from .contesto import Sessione

_DAL_VIVO: "OrderedDict[tuple, list[dict]]" = OrderedDict()


@lru_cache(maxsize=1)
def _classificazione_stagione() -> pd.DataFrame:
    """Tutte le sedute del dataset, ognuna con le fasce del suo giorno (circa 6 s, una volta sola)."""
    st = stagione()
    return classificazione(tutte_le_righe(st.al(st.fine)))


def _semplice(x):
    return x.item() if hasattr(x, "item") else str(x)


def prepara() -> None:
    """All'avvio del server, in un thread: l'archivio e la classificazione della stagione pronti in memoria."""
    archivio()
    _classificazione_stagione()


def _grezzi_del_giorno(s: Sessione, g: pd.Timestamp) -> list[dict]:
    if not s.caricata(g):
        return []
    car = s.caricamento
    if car is not None and car.data == g and not car.dal_dataset:
        k = (f"{g:%Y-%m-%d}", car.codice)
        if k not in _DAL_VIVO:
            v = s.visibile(g)
            c = con_la_seduta(_classificazione_stagione(), tutte_le_righe(v), g)
            sc = scegli(avvisi(v, c))
            grezzi = [a.to_dict() for lista in (sc["giorno"], sc["riassunto"], sc["dato"]) for a in lista]
            _DAL_VIVO[k] = json.loads(json.dumps(grezzi, default=_semplice))   # come quelli dell'archivio: tipi di Python
            while len(_DAL_VIVO) > 16:
                _DAL_VIVO.popitem(last=False)
        return _DAL_VIVO[k]
    return archivio().get(f"{g:%Y-%m-%d}", [])


def del_giorno(s: Sessione, giorno=None) -> list[dict]:
    """Gli avvisi nati quel giorno (vuoto se la sua seduta non è caricata), pronti per l'app."""
    g = pd.Timestamp(giorno if giorno is not None else s.oggi).normalize()
    return [per_app(a, f"{g:%Y-%m-%d}") for a in _grezzi_del_giorno(s, g)]


def stato(s: Sessione, fino_al=None) -> dict:
    """Tutti gli avvisi fino all'ultimo giorno caricato (o fino a `fino_al`, se prima), col loro stato."""
    ultimo = s.oggi if s.caricata(s.oggi) else s.oggi - pd.Timedelta(days=1)
    fino = min(pd.Timestamp(fino_al).normalize(), ultimo) if fino_al is not None else ultimo
    oggi = f"{s.oggi:%Y-%m-%d}"
    per_giorno = {d: lista for d, lista in archivio().items() if d < oggi}
    if s.caricata(s.oggi):
        per_giorno[oggi] = _grezzi_del_giorno(s, s.oggi)
    car = s.caricamento
    if car is not None and car.data < s.oggi:     # un giorno passato ricaricato con un file: i suoi avvisi
        per_giorno[f"{car.data:%Y-%m-%d}"] = _grezzi_del_giorno(s, car.data)
    v = s.visibile(fino)
    lista = con_lo_stato(per_giorno, fino, list(v.calendario["data"]), presenze_da(tutte_le_righe(v)))
    return {"fino_al": f"{fino:%Y-%m-%d}", "seduta_caricata": s.caricata(), "avvisi": [per_app(a, f"{fino:%Y-%m-%d}") for a in lista]}


def del_giocatore(s: Sessione, giocatore_id: int, giorno=None, giorni: int = 21) -> list[dict]:
    """Gli avvisi di un giocatore: quelli ancora aperti e quelli delle ultime settimane, al giorno dato."""
    st = stato(s, giorno)
    limite = f"{pd.Timestamp(st['fino_al']) - pd.Timedelta(days=giorni):%Y-%m-%d}"
    return [a for a in st["avvisi"] if a["giocatore_id"] == giocatore_id and (a["stato"] == "aperto" or a["data"] >= limite)]


# ---------- presentazione: il grafico da aprire e la domanda per Vice ----------

def _vista(a: dict, fino_al: str | None = None) -> tuple[dict | None, dict | None]:
    """(vista della lavagna, cosa accendere) per «Mostra». Il grafico del giocatore arriva fino all'ultimo giorno
    caricato (`fino_al`), con la seduta dell'avviso accesa: si vede anche com'è andata dopo."""
    fam, d, gid = a["famiglia"], a["data"], a.get("giocatore_id")
    m = (a.get("metriche") or [None])[0]
    con_m = {"metrica": m} if m else {}
    if fam == "dato":
        return None, None
    if gid is None:
        if fam == "reparto":
            return {"vista": "settimana", "parametri": {"data": d, **con_m}}, None
        if fam == "positivo":
            return {"vista": "curva_settimana", "parametri": {"data": d, **con_m}}, None
        return {"vista": "seduta", "parametri": {"data": d, **con_m}}, None
    if fam == "settimana":
        return {"vista": "allenamento_partita", "parametri": {"data": d, **con_m}}, {"giocatore_id": gid}
    if fam == "insolito":
        return {"vista": "seduta", "parametri": {"data": d, **con_m}}, {"giocatore_id": gid, "evidenza": f"seduta/{d}/{gid}/{m}"}
    if fam == "reparto":
        return {"vista": "settimana", "parametri": {"data": d, **con_m}}, {"giocatore_id": gid}
    if fam == "positivo" and a.get("riassunto"):   # in partita: il grafico del giocatore mostra solo gli allenamenti
        return None, None
    metrica = m or "td"
    return ({"vista": "giocatore", "parametri": {"giocatore_id": gid, "data": max(d, fino_al or d), "metrica": metrica}},
            {"giocatore_id": gid, "evidenza": f"seduta/{d}/{gid}/{metrica}"})


def _domanda(a: dict) -> str | None:
    if a["famiglia"] == "dato":
        return None
    quando = data_it(pd.Timestamp(a["data"]))[:5]
    del_ = "dell'" if quando.startswith(("08", "11")) else "del "    # «dell'11/04», «dell'08/04»
    if a.get("giocatore"):
        return f"Spiegami l'avviso su {a['giocatore']} {del_}{quando}: da cosa nasce?"
    return f"Spiegami l'avviso {del_}{quando} sulla squadra: da cosa nasce?"


def per_app(a: dict, fino_al: str | None = None) -> dict:
    vista, accendi = _vista(a, fino_al)
    md = giorno_md_it(stagione().contesto(a["data"]).giorno_md)
    return a | {"vista": vista, "accendi": accendi, "domanda": _domanda(a), "giorno_md": md}


# ---------- per gli strumenti dell'agente: gli avvisi con le loro etichette [E…] ----------

def evidenze(s: Sessione, lista: list[dict], giorno=None) -> list[Evidenza]:
    """Le evidenze delle sedute citate dagli avvisi (le ultime 16 della squadra), così Vice può citarle."""
    ids = {e for a in lista for e in a.get("evidenze", []) if e.startswith("seduta/")}
    if not ids:
        return []
    g = pd.Timestamp(giorno if giorno is not None else s.oggi).normalize()
    tab = ultime_sedute_classificate(s.visibile(g), 16)
    return [e for e in evidenze_classifica(tab, "seduta") if e.id in ids] if len(tab) else []


def per_il_modello(lista: list[dict], etichette: dict[str, str]) -> list[dict]:
    """Gli avvisi come li vede il modello: testo, giorno, famiglia, stato ed etichette delle evidenze."""
    out = []
    for a in lista:
        et = [etichette[e] for e in sorted(a.get("evidenze", []), reverse=True) if e in etichette]
        out.append({"testo": a["testo"], "giorno": data_it(pd.Timestamp(a["data"])), "famiglia": a["nome_famiglia"],
                    **({"stato": a["stato"]} if a.get("stato") else {}),
                    **({"etichette": list(dict.fromkeys(et))} if et else {})})
    return out
