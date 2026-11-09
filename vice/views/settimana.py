"""V1 La settimana: griglia giocatori × sedute del microciclo, ogni cella con la posizione rispetto alla fascia."""

from __future__ import annotations

from ..agent.contesto import Sessione
from ..analysis.comune import UNITA
from ..analysis.evidenze import con_unita, data_it, giorno_md_it, numero_it
from ..analysis.settimana import griglia_settimana
from .comune import FONTE_ZENODO, METRICA_VISTA, SENZA_FASCIA, dicitura, gettoni, giorno, metrica, metriche_selezionabili


def vista_settimana(s: Sessione, parametri: dict) -> dict:
    g = giorno(s, parametri)
    m = metrica(parametri)
    v = s.visibile(g)
    r = griglia_settimana(v)
    nome, nome_asse = METRICA_VISTA[m]
    base = {"vista": "settimana", "forma": "griglia", "parametri": {"data": f"{g:%Y-%m-%d}", "metrica": m}, "metrica": m,
            "metriche": metriche_selezionabili(), "fonte": FONTE_ZENODO, "dicitura": dicitura(), "avvisi": list(r.avvisi),
            "titolo": f"La settimana, {nome}"}
    if r.tabella.empty:
        return base | {"giorni": [], "righe": [],
                       "vuota": "Nessuna seduta con dati in questa settimana" + (": oggi è un giorno di pausa." if r.avvisi else ".")}
    t = r.tabella[r.tabella["metrica"] == m]
    u = UNITA[m]
    giorni = []
    for d in sorted(t["data"].unique()):
        md = int(t.loc[t["data"] == d, "giorno_md"].iloc[0])
        giorni.append({"data": f"{d:%Y-%m-%d}", "data_testo": data_it(d)[:5], "md": giorno_md_it(md), "oggi": d == s.oggi})
    gioc = gettoni(v)
    righe = []
    for gid, tg in t.groupby("giocatore_id"):
        celle = {}
        for x in tg.itertuples():
            celle[f"{x.data:%Y-%m-%d}"] = {
                "posizione": x.posizione, "valore_testo": con_unita(x.valore, u),
                "chiave": f"seduta/{int(gid)}/{m}", "evidenza": f"seduta/{x.data:%Y-%m-%d}/{int(gid)}/{m}",
                "dettaglio": (f"{giorno_md_it(x.giorno_md)} {data_it(x.data)[:5]}: {con_unita(x.valore, u)}, "
                              + ("senza fascia" if x.posizione == SENZA_FASCIA else
                                 "dentro la fascia" if x.posizione == "dentro" else x.posizione)
                              + (f" (P25-P75 {numero_it(x.p25, u)}-{con_unita(x.p75, u)})" if x.posizione != SENZA_FASCIA else ""))}
        righe.append({"giocatore": gioc[int(gid)], "celle": celle})
    righe.sort(key=lambda x: x["giocatore"]["numero"])
    dal = r.sintesi.get("settimana_dal")
    return base | {
        "spiegazione": (f"{nome_asse[0].upper() + nome_asse[1:]}: ogni cella dice dove cade la seduta rispetto alla fascia "
                        f"del giocatore per quel giorno della settimana. Cella tratteggiata: il giocatore non era in seduta."
                        + (f" Settimana dalla partita del {data_it(dal)[:5]}." if dal is not None else "")),
        "giorni": giorni, "righe": righe,
    }
