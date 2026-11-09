"""V2 La seduta: per ogni giocatore il valore del giorno contro la sua fascia storica (una metrica)."""

from __future__ import annotations

from ..agent.contesto import Sessione
from ..analysis.comune import UNITA
from ..analysis.evidenze import arrotonda, con_unita, data_it, giorno_md_it
from ..analysis.seduta import seduta as analisi_seduta
from .comune import (FONTE_ZENODO, METRICA_VISTA, POSIZIONI, SENZA_FASCIA, asse, dicitura, fascia_testi, gettoni,
                     giorno, intestazione_giorno, metrica, metriche_selezionabili)

FORTI = ("molto sotto", "molto sopra")


def metrica_piu_interessante(tab) -> str:
    """Senza una metrica richiesta: quella con più giocatori fuori dalla fascia larga (a parità, la prima
    tra distanza, alta velocità e sprint)."""
    conti = {m: int(tab[(tab["metrica"] == m) & tab["posizione"].isin(FORTI)].shape[0]) for m in ("td", "hsr", "spr")}
    return max(conti, key=lambda m: (conti[m], -("td", "hsr", "spr").index(m)))


def vista_seduta(s: Sessione, parametri: dict) -> dict:
    g = giorno(s, parametri)
    v = s.visibile(g)
    r = analisi_seduta(v)
    quando = intestazione_giorno(g, s)
    base = {"vista": "seduta", "forma": "fasce", "fonte": FONTE_ZENODO, "dicitura": dicitura(),
            "metriche": metriche_selezionabili(), "avvisi": list(r.avvisi)}
    if r.tabella.empty:
        m = metrica(parametri)
        return base | {"parametri": {"data": f"{g:%Y-%m-%d}", "metrica": m}, "metrica": m,
                       "titolo": f"Nessuna seduta {quando}", "righe": [],
                       "vuota": f"Il {data_it(g)} non c'è una seduta con dati GPS: scegli un altro giorno."}
    tab = r.tabella
    m = metrica(parametri, metrica_piu_interessante(tab))
    t = tab[tab["metrica"] == m].copy()
    unita = UNITA[m]
    nome, nome_asse = METRICA_VISTA[m]
    gioc = gettoni(v)

    con = t[t["posizione"] != SENZA_FASCIA].sort_values(["p50", "giocatore"], ascending=[False, True])
    senza = t[t["posizione"] == SENZA_FASCIA].sort_values("giocatore")
    righe = []
    for x in list(con.itertuples()) + list(senza.itertuples()):
        gid = int(x.giocatore_id)
        riga = {"chiave": f"seduta/{gid}/{m}", "evidenza": f"seduta/{g:%Y-%m-%d}/{gid}/{m}",
                "giocatore": gioc[gid], "valore": arrotonda(x.valore, unita),
                "valore_testo": con_unita(x.valore, unita), "posizione": x.posizione}
        if x.posizione != SENZA_FASCIA:
            riga |= {"fascia": {k: arrotonda(getattr(x, k), unita) for k in ("p10", "p25", "p50", "p75", "p90")},
                     "provvisoria": bool(x.provvisoria), "dettagli": fascia_testi(x, unita)}
        else:
            riga["dettagli"] = ["nessuna fascia: storico ancora insufficiente"]
        righe.append(riga)

    conteggi = {p: int((t["posizione"] == p).sum()) for p in (*POSIZIONI, SENZA_FASCIA)}
    md = giorno_md_it(r.sintesi["giorno_md"])
    gruppi = sorted(set(t["gruppo"]) - {"tutti"})
    nota_gruppo = (" Dopo la partita titolari e non titolari hanno fasce separate." if gruppi else "")
    valori = list(t["valore"]) + list(con["p90"])
    return base | {
        "parametri": {"data": f"{g:%Y-%m-%d}", "metrica": m}, "metrica": m,
        "titolo": f"{nome[0].upper() + nome[1:]} {quando}, rispetto alla fascia di ciascuno",
        "spiegazione": (f"{nome_asse[0].upper() + nome_asse[1:]} nella seduta del {data_it(g)} ({md}). Fascia storica di "
                        f"ogni giocatore per questo giorno della settimana: banda larga P10-P90, banda centrale P25-P75, "
                        f"trattino sulla mediana.{nota_gruppo}"),
        "asse": asse(valori) | {"nome": nome_asse},
        "righe": righe, "conteggi": conteggi,
        "chiavi_squadra": [f"seduta/squadra/{m}", "seduta/squadra"],
    }
