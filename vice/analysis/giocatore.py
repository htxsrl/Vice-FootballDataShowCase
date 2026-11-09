"""Il giocatore: andamento (M2.7) e confronti (M2.8). Solo descrittivo.

- **Andamento:** le sedute di allenamento delle ultime 4 settimane contro la sua stagione prima di
  quelle settimane, a parità di giorno MD (e di stato dopo la partita). Per ogni seduta: differenza
  dalla sua mediana di quel giorno, in metri e in %; per metrica: le mediane. Niente "meglio" o
  "peggio".
- **Confronti:** con sé stesso, col ruolo, con la squadra, tra giocatori scelti; mediane per giorno
  MD nello stesso periodo. L'ordine è quello dei numeri di maglia: **mai classifiche** sui carichi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.stagione import Visibile
from .comune import METRICHE, NOME_METRICA, UNITA, anagrafica, tutte_le_righe
from .evidenze import Risultato, arrotonda, data_it, evidenza, giorno_md_it, maiuscola
from .fasce import MIN_CASI, con_gruppo, rango_percentile, tolleranza

GIORNI_RECENTI = 28
MIN_SEDUTE_RECENTI = 4             # sedute recenti confrontabili, per metrica
SOGLIA_SCARTO = 10                 # %: scarto mediano minimo dal suo solito
SOGLIE_PERCENTILE = (35, 65)       # percentile mediano fuori da qui
# "Più alto/basso del suo solito" solo se valgono tutte: percentile mediano fuori da 35-65 (robusto),
# differenza assoluta mediana oltre la tolleranza della metrica (conta sul campo) e, se calcolabile,
# scarto mediano oltre ±10%. Con mediana storica zero lo scarto % non esiste e si dice.
# Decisione 55 (30/10/2026): le tre condizioni si calcolano sulle stesse sedute, quelle in cui il suo solito non è
# zero (0 contro 0 non dice nulla, e nello sprint a MD-1 capita quasi sempre): prima la differenza e il rango le
# contavano tutte e la percentuale no, e la vista poteva dire «in linea» con uno scarto del -80% (Amato, sprint,
# 18/04). Se quelle sedute sono meno di 4, si contano tutte senza la percentuale, come prima (Serafini, 29/11).


def andamento(v: Visibile, giocatore_id: int, giorni: int = GIORNI_RECENTI) -> Risultato:
    oggi = v.oggi
    ana = anagrafica(v)
    nome = ana.loc[giocatore_id, "nome_completo"]
    righe = con_gruppo(tutte_le_righe(v))
    mie = righe[(righe["giocatore_id"] == giocatore_id) & (righe["tipo"] == "allenamento")]
    inizio = oggi - pd.Timedelta(days=giorni - 1)
    recenti, prima = mie[mie["data"] >= inizio], mie[mie["data"] < inizio]
    tab, evid, avvisi = [], [], []
    for r in recenti.itertuples(index=False):
        rif = prima[(prima["giorno_md"] == r.giorno_md) & (prima["gruppo"] == r.gruppo)]
        if len(rif) < MIN_CASI:
            continue
        for m in METRICHE:
            med = float(rif[m].median())
            x = float(getattr(r, m))
            tab.append({"data": r.data, "giorno_md": r.giorno_md, "gruppo": r.gruppo, "metrica": m, "valore": x,
                        "mediana_solita": med, "casi": len(rif), "differenza": x - med,
                        "scarto_pct": 100 * (x / med - 1) if med > 0 else np.nan,
                        "percentile": rango_percentile(x, rif[m])})
    tab = pd.DataFrame(tab, columns=["data", "giorno_md", "gruppo", "metrica", "valore", "mediana_solita", "casi",
                                     "differenza", "scarto_pct", "percentile"])
    sedute = int(tab["data"].nunique()) if len(tab) else 0
    sintesi = {"giocatore": nome, "dal": inizio, "al": oggi, "sedute_confrontate": sedute,
               "sedute_recenti": int(recenti["data"].nunique()), "per_metrica": {}}
    if sedute < MIN_SEDUTE_RECENTI:
        avvisi.append("troppo poche sedute recenti confrontabili col suo storico: andamento non calcolato")
        return Risultato("andamento", oggi, tab, evid, avvisi, sintesi)
    for m in METRICHE:
        tutte = tab[tab["metrica"] == m]
        confrontabili = tutte[tutte["mediana_solita"] > 0]          # dove lo scarto in % esiste
        t = confrontabili if len(confrontabili) >= MIN_SEDUTE_RECENTI else tutte
        pc, diff = float(t["percentile"].median()), float(t["differenza"].median())
        sc = float(t["scarto_pct"].median()) if t is confrontabili else None
        toll = tolleranza(m, float(t["mediana_solita"].median()))
        if pc > SOGLIE_PERCENTILE[1] and diff > toll and (sc is None or sc > SOGLIA_SCARTO):
            descr = "più alto del suo solito"
        elif pc < SOGLIE_PERCENTILE[0] and diff < -toll and (sc is None or sc < -SOGLIA_SCARTO):
            descr = "più basso del suo solito"
        else:
            descr = "in linea con il suo solito"
        nota = None if sc is not None else "variazione percentuale non calcolabile: mediana storica zero in troppe sedute"
        sintesi["per_metrica"][m] = {"scarto_mediano_pct": arrotonda(sc, "%"), "differenza_mediana": arrotonda(diff, UNITA[m]),
                                     "percentile_mediano": arrotonda(pc, "percentile"), "descrizione": descr, "nota": nota,
                                     "sedute_usate": int(t["data"].nunique()), "sedute": int(tutte["data"].nunique())}
        evid.append(evidenza(f"andamento/{oggi:%Y-%m-%d}/{giocatore_id}/{m}",
                             f"{maiuscola(NOME_METRICA[m])} di {nome} nelle ultime {giorni // 7} settimane rispetto al suo solito (differenza mediana)",
                             diff, UNITA[m], grafico=f"andamento/{giocatore_id}/{m}", giocatore_id=giocatore_id, giocatore=nome,
                             metrica=m, dal=inizio, al=oggi, sedute=int(t["data"].nunique()), percentile_mediano=arrotonda(pc, "percentile"),
                             scarto_mediano_pct=arrotonda(sc, "%"), tolleranza=arrotonda(toll, UNITA[m]), descrizione=descr,
                             nota=nota, definizione="a parità di giorno MD, contro le sue sedute precedenti; contano le sedute in "
                                                    "cui il suo solito non è zero, se sono almeno 4"))
    return Risultato("andamento", oggi, tab, evid, avvisi, sintesi)


def confronta(v: Visibile, giocatori: list[int], giorni: int = GIORNI_RECENTI,
              metriche: tuple[str, ...] = ("td", "hsr", "spr")) -> Risultato:
    """Mediane per giorno MD nello stesso periodo: dei giocatori scelti, del loro ruolo e della squadra."""
    oggi = v.oggi
    ana = anagrafica(v)
    inizio = oggi - pd.Timedelta(days=giorni - 1)
    righe = con_gruppo(tutte_le_righe(v))
    periodo = righe[(righe["data"] >= inizio) & (righe["tipo"] == "allenamento")]
    chiavi = ["giorno_md", "gruppo"]
    squadra = periodo.groupby(chiavi)[list(metriche)].median()
    tab, evid = [], []
    ordinati = sorted(giocatori, key=lambda g: ana.loc[g, "numero"])   # ordine di maglia, mai per valore
    for gid in ordinati:
        nome, ruolo = ana.loc[gid, "nome_completo"], ana.loc[gid, "ruolo"]
        mie = periodo[periodo["giocatore_id"] == gid]
        del_ruolo = periodo[periodo["ruolo"] == ruolo].groupby(chiavi)[list(metriche)].median()
        for (gmd, g), t in mie.groupby(chiavi):
            for m in metriche:
                x = float(t[m].median())
                tab.append({"giocatore_id": gid, "giocatore": nome, "ruolo": ruolo, "giorno_md": gmd, "gruppo": g,
                            "metrica": m, "mediana": x, "sedute": len(t),
                            "mediana_ruolo": float(del_ruolo.loc[(gmd, g), m]), "mediana_squadra": float(squadra.loc[(gmd, g), m])})
                u = UNITA[m]
                evid.append(evidenza(f"confronto/{oggi:%Y-%m-%d}/{gid}/{gmd}/{g}/{m}",
                                     f"{maiuscola(NOME_METRICA[m])} di {nome} a {giorno_md_it(gmd)}: mediana dal {data_it(inizio)} al {data_it(oggi)}",
                                     x, u, grafico=f"confronto/{gid}/{gmd}/{m}", giocatore_id=gid, giocatore=nome,
                                     giorno_md=gmd, gruppo=g, metrica=m, sedute=len(t),
                                     mediana_ruolo=arrotonda(del_ruolo.loc[(gmd, g), m], u),
                                     mediana_squadra=arrotonda(squadra.loc[(gmd, g), m], u)))
    tab = pd.DataFrame(tab)
    return Risultato("confronto", oggi, tab, evid,
                     ["confronto descrittivo per giorno MD, non una classifica: i carichi dipendono dal ruolo e dal programma"],
                     {"giocatori": [ana.loc[g, "nome_completo"] for g in ordinati], "dal": inizio, "al": oggi})
