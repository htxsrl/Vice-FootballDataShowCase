"""V3 Il giocatore: le sue ultime sedute di allenamento, ciascuna contro la sua fascia di quel giorno.

Solo i suoi dati, nessun confronto con i compagni (D6).
"""

from __future__ import annotations

from collections import OrderedDict

import pandas as pd

from ..agent.contesto import ErroreStrumento, Sessione
from ..analysis.comune import UNITA
from ..analysis.evidenze import arrotonda, con_unita, data_it, giorno_md_it, numero_it
from ..analysis.giocatore import andamento
from ..analysis.spunti import ultime_sedute_classificate
from .comune import (FONTE_ZENODO, METRICA_VISTA, SENZA_FASCIA, asse, dicitura, fascia_testi, gettoni, giocatore_id, giorno,
                     metrica, metriche_selezionabili)

SEDUTE = 16
_cache: OrderedDict = OrderedDict()   # (oggi, file caricato) → sedute classificate (1-2 s di calcolo)


def _classificate(s: Sessione, g: pd.Timestamp) -> pd.DataFrame:
    k = (g, s.caricamento.codice if s.caricamento else None)
    if k not in _cache:
        _cache[k] = ultime_sedute_classificate(s.visibile(g), SEDUTE)
        while len(_cache) > 8:
            _cache.popitem(last=False)
    return _cache[k]


def vista_giocatore(s: Sessione, parametri: dict) -> dict:
    gid = giocatore_id(s, parametri)
    if gid is None:
        raise ErroreStrumento("manca il giocatore")
    g = giorno(s, parametri)
    m = metrica(parametri)
    v = s.visibile(g)
    gioc = gettoni(v)[gid]
    nome, nome_asse = METRICA_VISTA[m]
    u = UNITA[m]
    tab = _classificate(s, g)
    t = tab[(tab["giocatore_id"] == gid) & (tab["metrica"] == m)].sort_values("data", ascending=False) if len(tab) else tab
    base = {"vista": "giocatore", "forma": "fasce", "parametri": {"giocatore_id": gid, "data": f"{g:%Y-%m-%d}", "metrica": m},
            "metrica": m, "metriche": metriche_selezionabili(), "giocatore": gioc, "fonte": FONTE_ZENODO, "dicitura": dicitura(),
            "titolo": f"{gioc['nome']}, {nome} nelle ultime sedute", "avvisi": []}
    if t.empty:
        return base | {"righe": [], "vuota": f"Nessun allenamento di {gioc['nome']} tra gli ultimi {SEDUTE} della squadra."}
    righe = []
    for x in t.itertuples():
        riga = {"etichetta": data_it(x.data)[:5], "sotto": giorno_md_it(x.giorno_md),
                "chiave": f"seduta/{gid}/{m}", "evidenza": f"seduta/{x.data:%Y-%m-%d}/{gid}/{m}",
                "valore": arrotonda(x.valore, u), "valore_testo": con_unita(x.valore, u), "posizione": x.posizione,
                "azione": {"vista": "seduta", "parametri": {"data": f"{x.data:%Y-%m-%d}", "metrica": m}}}
        if x.posizione != SENZA_FASCIA:
            riga |= {"fascia": {k: arrotonda(getattr(x, k), u) for k in ("p10", "p25", "p50", "p75", "p90")},
                     "provvisoria": bool(x.provvisoria), "dettagli": fascia_testi(x, u)}
        else:
            riga["dettagli"] = ["nessuna fascia: storico ancora insufficiente"]
        righe.append(riga)
    a = andamento(v, gid)
    pm = (a.sintesi.get("per_metrica") or {}).get(m) or {}
    nota = ""
    if pm.get("descrizione"):
        # decisione 55: il verdetto e lo scarto vengono dalle stesse sedute; se alcune restano fuori, si dice
        usate, tutte = pm.get("sedute_usate"), pm.get("sedute")
        quante = (f", su {usate} delle {tutte} sedute: nelle altre il suo solito è zero"
                  if usate and tutte and usate < tutte and pm.get("scarto_mediano_pct") is not None else "")
        nota = (f" Ultime 4 settimane: {pm['descrizione']}"
                + (f" (scarto mediano {numero_it(pm['scarto_mediano_pct'], '%')}% dalla sua mediana dello stesso giorno{quante})"
                   if pm.get("scarto_mediano_pct") is not None else "") + ".")
    valori = list(t["valore"]) + list(t["p90"].dropna())
    return base | {
        "spiegazione": (f"{nome_asse[0].upper() + nome_asse[1:]} negli allenamenti di {gioc['nome']} tra gli ultimi {SEDUTE} "
                        "della squadra, dal più recente. Ogni riga ha la sua fascia storica per quel giorno della settimana: "
                        f"banda larga P10-P90, banda centrale P25-P75, trattino sulla mediana. Solo i suoi dati.{nota}"),
        "asse": asse(valori) | {"nome": nome_asse},
        "righe": righe, "avvisi": list(a.avvisi),
        "chiavi_squadra": [f"andamento/{gid}/{m}"],
    }
