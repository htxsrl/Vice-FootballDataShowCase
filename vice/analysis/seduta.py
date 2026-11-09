"""M2.2 Classificazione della seduta: chi è dentro o fuori dalla sua fascia storica, e di quanto.

Posizioni rispetto alla fascia del giocatore (vedi fasce.py): "molto sotto" (sotto P10), "sotto"
(tra P10 e P25), "dentro" (P25-P75), "sopra" (tra P75 e P90), "molto sopra" (sopra P90), sempre
con la tolleranza operativa della metrica. È **aderenza al carico abituale**: sopra non vuol dire
meglio, e la fascia non è il programma della seduta, che Vice non conosce.
"""

from __future__ import annotations

import pandas as pd

from ..data.stagione import Visibile
from .comune import METRICHE, NOME_METRICA, UNITA, anagrafica
from .evidenze import Risultato, arrotonda, data_it, evidenza, giorno_md_it, maiuscola
from .fasce import Riferimenti, classifica

FUORI = ("molto sotto", "molto sopra")
MARGINI = ("sotto", "sopra")


def con_nomi(tabella: pd.DataFrame, v: Visibile) -> pd.DataFrame:
    ana = anagrafica(v)
    out = tabella.copy()
    out["giocatore"] = out["giocatore_id"].map(ana["nome_completo"])
    out["numero"] = out["giocatore_id"].map(ana["numero"])
    return out


def evidenze_classifica(tab: pd.DataFrame, prefisso: str) -> list:
    """Un'evidenza per giocatore × metrica: il valore, con fascia, percentile e casi nel contesto."""
    out = []
    for r in tab.itertuples(index=False):
        u = UNITA[r.metrica]
        ctx = {"giocatore_id": r.giocatore_id, "giocatore": r.giocatore, "data": r.data, "giorno_md": r.giorno_md,
               "gruppo": r.gruppo, "metrica": r.metrica, "posizione": r.posizione}
        if r.posizione != "senza fascia":
            ctx |= {"fascia_centrale": [arrotonda(r.p25, u), arrotonda(r.p75, u)],
                    "fascia_larga": [arrotonda(r.p10, u), arrotonda(r.p90, u)], "mediana": arrotonda(r.p50, u),
                    "percentile": arrotonda(r.percentile, "percentile"), "scarto": arrotonda(r.scarto, u),
                    "tolleranza": arrotonda(r.tolleranza, u), "livello": r.livello, "casi": int(r.casi),
                    "sedute": int(r.sedute), "provvisoria": bool(r.provvisoria)}
        out.append(evidenza(f"{prefisso}/{r.data:%Y-%m-%d}/{r.giocatore_id}/{r.metrica}",
                            f"{maiuscola(NOME_METRICA[r.metrica])} di {r.giocatore}, {data_it(r.data)} ({giorno_md_it(r.giorno_md)})",
                            r.valore, u, grafico=f"seduta/{r.giocatore_id}/{r.metrica}", **ctx))
    return out


def seduta(v: Visibile) -> Risultato:
    """La seduta di oggi contro le fasce attese calcolate sullo storico."""
    oggi = v.oggi
    if v.seduta_di_oggi.empty:
        return Risultato("seduta", oggi, pd.DataFrame(), avvisi=[f"il {data_it(oggi)} non c'è una seduta con dati"],
                         sintesi={"data": oggi, "giorno_md": v.contesto.giorno_md, "giocatori": 0})
    tab = con_nomi(classifica(v.storico, v.seduta_di_oggi, Riferimenti(v.storico)), v)
    giorno_md = int(v.seduta_di_oggi["giorno_md"].iloc[0])
    tipo = v.seduta_di_oggi["tipo"].iloc[0]
    evid = evidenze_classifica(tab, "seduta")
    avvisi = []

    senza = tab[tab["posizione"] == "senza fascia"]
    if len(senza) == len(tab):
        avvisi.append(f"nessuna fascia per {giorno_md_it(giorno_md)}: nello storico ci sono ancora troppo poche "
                      "sedute di questo tipo (inizio stagione)")
    elif len(senza):
        avvisi.append("alcuni giocatori sono senza fascia per almeno una metrica: lo storico del ruolo o della squadra "
                      "non basta ancora")
    con = tab[tab["posizione"] != "senza fascia"]

    per_metrica = {}
    for m in METRICHE:
        t = con[con["metrica"] == m]
        if t.empty:
            continue
        conteggi = {p: int((t["posizione"] == p).sum()) for p in ("molto sotto", "sotto", "dentro", "sopra", "molto sopra")}
        pm = float(t["percentile"].median())
        per_metrica[m] = {"percentile_mediano": arrotonda(pm, "percentile"), **conteggi}
        evid.append(evidenza(f"seduta/{oggi:%Y-%m-%d}/squadra/{m}",
                             f"{maiuscola(NOME_METRICA[m])}: percentile mediano della squadra, {data_it(oggi)}",
                             pm, "percentile", grafico=f"seduta/squadra/{m}",
                             data=oggi, giorno_md=giorno_md, metrica=m, giocatori=int(len(t)),
                             dentro=conteggi["dentro"], sopra=conteggi["sopra"] + conteggi["molto sopra"],
                             sotto=conteggi["sotto"] + conteggi["molto sotto"]))

    def elenco(posizioni) -> list[dict]:
        t = con[con["posizione"].isin(posizioni)].copy()
        t["distanza_da_50"] = (t["percentile"] - 50).abs()
        t = t.sort_values(["distanza_da_50", "giocatore"], ascending=[False, True])
        return [{"giocatore_id": r.giocatore_id, "giocatore": r.giocatore, "metrica": r.metrica,
                 "posizione": r.posizione, "valore": arrotonda(r.valore, UNITA[r.metrica]),
                 "percentile": arrotonda(r.percentile, "percentile"),
                 "evidenza": f"seduta/{oggi:%Y-%m-%d}/{r.giocatore_id}/{r.metrica}"} for r in t.itertuples()]

    sintesi = {"data": oggi, "giorno_md": giorno_md, "tipo": tipo, "giocatori": int(tab["giocatore_id"].nunique()),
               "per_metrica": per_metrica, "fuori_fascia": elenco(FUORI), "ai_margini": elenco(MARGINI)}
    fuori = sorted({f["giocatore"] for f in sintesi["fuori_fascia"]})
    evid.append(evidenza(f"seduta/{oggi:%Y-%m-%d}/squadra/fuori", f"Giocatori fuori dalla fascia larga in almeno una metrica, {data_it(oggi)}",
                         len(fuori), "giocatori", grafico="seduta/squadra", data=oggi, giorno_md=giorno_md,
                         giocatori_in_seduta=sintesi["giocatori"], nomi=fuori,
                         ai_margini=len({f["giocatore"] for f in sintesi["ai_margini"]} - set(fuori))))
    return Risultato("seduta", oggi, tab, evid, avvisi, sintesi)
