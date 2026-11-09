"""V5 La curva della settimana: la mediana di squadra di ogni seduta del microciclo contro le settimane passate."""

from __future__ import annotations

from ..agent.contesto import Sessione
from ..analysis.comune import UNITA
from ..analysis.evidenze import arrotonda, con_unita, data_it, giorno_md_it, numero_it
from ..analysis.settimana import forma_settimana
from .comune import FONTE_ZENODO, METRICA_VISTA, asse, dicitura, giorno, metrica, metriche_selezionabili

GIORNI = (1, 2, -5, -4, -3, -2, -1)     # l'ordine del microciclo, dalla partita alla successiva (esclusa)


def vista_curva(s: Sessione, parametri: dict) -> dict:
    g = giorno(s, parametri)
    m = metrica(parametri)
    r = forma_settimana(s.visibile(g))
    nome, nome_asse = METRICA_VISTA[m]
    base = {"vista": "curva_settimana", "forma": "curva", "parametri": {"data": f"{g:%Y-%m-%d}", "metrica": m},
            "metrica": m, "metriche": metriche_selezionabili(), "fonte": FONTE_ZENODO, "dicitura": dicitura(),
            "avvisi": list(r.avvisi), "titolo": f"La forma della settimana, {nome}"}
    if r.tabella.empty:
        return base | {"giorni": [], "righe": [], "vuota": "Oggi è un giorno di pausa: nessuna settimana in corso."}
    u = UNITA[m]
    t = r.tabella[r.tabella["metrica"] == m]
    tipo = {(x["giorno_md"], x["gruppo"]): x[m] for x in r.sintesi.get("settimana_tipo", [])}
    md_oggi = r.sintesi.get("giorno_md")
    pos_oggi = GIORNI.index(md_oggi) if md_oggi in GIORNI else len(GIORNI)
    giorni = []
    for i, md in enumerate(GIORNI):
        sedute = t[t["giorno_md"] == md]
        if len(sedute):
            x = sedute.iloc[0]
            d = x["data"]
            giorni.append({
                "md": giorno_md_it(md), "data": f"{d:%Y-%m-%d}", "data_testo": data_it(d)[:5], "gruppo": x["gruppo"],
                "valore": arrotonda(x["mediana_squadra"], u), "valore_testo": con_unita(x["mediana_squadra"], u),
                "posizione": x["posizione"], "provvisoria": bool(x["provvisoria"]),
                "fascia": {k: arrotonda(x[k], u) for k in ("p10", "p25", "p50", "p75", "p90")},
                "tipico": arrotonda(tipo.get((md, x["gruppo"]), x["p50"]), u),
                "chiave": f"curva/{d:%Y-%m-%d}/{x['gruppo']}/{m}", "evidenza": f"settimana/{d:%Y-%m-%d}/{x['gruppo']}/{m}",
                "dettagli": [f"mediana di squadra: {con_unita(x['mediana_squadra'], u)} ({int(x['giocatori'])} giocatori"
                             + (f", {x['gruppo']}" if x["gruppo"] != "tutti" else "") + ")",
                             f"settimane passate, P25-P75: {numero_it(x['p25'], u)}-{con_unita(x['p75'], u)}",
                             f"settimane passate, P10-P90: {numero_it(x['p10'], u)}-{con_unita(x['p90'], u)}",
                             f"{int(x['settimane'])} settimane di riferimento" + (" (provvisoria)" if bool(x["provvisoria"]) else "")],
                "azione": {"vista": "seduta", "parametri": {"data": f"{d:%Y-%m-%d}", "metrica": m}},
            })
        else:
            tip = tipo.get((md, "tutti"))
            futuro = i > pos_oggi
            giorni.append({"md": giorno_md_it(md), "tipico": arrotonda(tip, u) if tip is not None else None, "futuro": futuro,
                           "dettagli": ["giorno non ancora arrivato: solo la settimana tipo" if futuro
                                        else "nessuna seduta con dati in questo giorno"]})
    valori = [x.get("fascia", {}).get("p90") for x in giorni] + [x.get("valore") for x in giorni] + [x.get("tipico") for x in giorni]
    dal = r.sintesi.get("settimana_dal")
    return base | {
        "spiegazione": (f"Mediana di squadra, {nome_asse}, per ogni seduta della settimana"
                        + (f" iniziata con la partita del {data_it(dal)[:5]}" if dal is not None else "")
                        + f". Le bande sono le mediane dello stesso giorno nelle {r.sintesi.get('settimane_di_riferimento', 0)} "
                        "settimane passate (P10-P90 e P25-P75); la linea tratteggiata è la settimana tipo. Dopo la partita "
                        "conta il gruppo che si è allenato."),
        "asse": asse([x for x in valori if x is not None]) | {"nome": nome_asse},
        "giorni": giorni, "righe": [x for x in giorni if "valore" in x],
    }
