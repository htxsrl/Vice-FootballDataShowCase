"""V6 Allenamento ↔ partita: la settimana finora in % della partita di riferimento di ciascuno (decisione 24),
contro quanto di solito si è fatto allo stesso punto della settimana.

Il punto ha il colore della posizione rispetto a quel solito (P10-P90 e P25-P75 del motore, senza tolleranza: è una
quota, non una misura), come nelle altre viste; le righe vanno in ordine di maglia, mai dalla percentuale più alta,
perché non è una classifica (08/11/2026)."""

from __future__ import annotations

from ..agent.contesto import Sessione
from ..analysis.comune import UNITA
from ..analysis.evidenze import arrotonda, con_unita, data_it, giorno_md_it, numero_it
from ..analysis.partita import AVVISO_RISCALDAMENTO, allenamento_partita
from .comune import (FONTE_ZENODO, METRICA_VISTA, POSIZIONI, asse, dicitura, gettoni, giocatore_id, giorno, metrica,
                     metriche_selezionabili)


def posizione_quota(x: float, p10: float, p25: float, p75: float, p90: float) -> str:
    """Dove cade la quota della settimana rispetto al suo solito a questo punto della settimana."""
    if x < p10:
        return "molto sotto"
    if x < p25:
        return "sotto"
    if x <= p75:
        return "dentro"
    return "sopra" if x <= p90 else "molto sopra"


def vista_partita(s: Sessione, parametri: dict) -> dict:
    g = giorno(s, parametri)
    m = metrica(parametri)
    gid_chiesto = giocatore_id(s, parametri)
    v = s.visibile(g)
    r = allenamento_partita(v)
    nome = METRICA_VISTA[m][0]
    base = {"vista": "allenamento_partita", "forma": "fasce",
            "parametri": {"data": f"{g:%Y-%m-%d}", "metrica": m, **({"giocatore_id": gid_chiesto} if gid_chiesto else {})},
            "metrica": m, "metriche": metriche_selezionabili(), "fonte": FONTE_ZENODO, "dicitura": dicitura(),
            "titolo": f"Quanta partita abbiamo allenato, {nome}", "avvisi": list(r.avvisi)}
    if r.tabella.empty:
        return base | {"righe": [], "vuota": "Nessun dato per confrontare la settimana con la partita."}
    u = UNITA[m]
    t = r.tabella[r.tabella["metrica"] == m].copy()
    t = t[t["settimana_pct"].notna()]
    gioc = gettoni(v)
    t = t.assign(numero=[gioc[int(g)]["numero"] for g in t["giocatore_id"]]).sort_values("numero")
    righe = []
    for x in t.itertuples():
        gid = int(x.giocatore_id)
        ha_solito = x.solito_p50 == x.solito_p50   # non NaN
        riga = {"giocatore": gioc[gid], "chiave": f"partita/{gid}/{m}", "evidenza": f"partita/{g:%Y-%m-%d}/{gid}/{m}/settimana",
                "valore": arrotonda(x.settimana_pct, "%"), "valore_testo": f"{numero_it(x.settimana_pct, '%')}%",
                "posizione": "neutra", "acceso": gid == gid_chiesto,
                "dettagli": [f"settimana finora: {con_unita(x.settimana, u)} in {int(x.sedute_settimana)} sedute",
                             f"riferimento di partita: {con_unita(x.riferimento, u)} (media da titolare, {x.livello}, {int(x.partite)} partite)"]}
        if ha_solito:
            riga["fascia"] = {k: arrotonda(getattr(x, f"solito_{k}"), "%") for k in ("p10", "p25", "p50", "p75", "p90")}
            riga["posizione"] = posizione_quota(x.settimana_pct, x.solito_p10, x.solito_p25, x.solito_p75, x.solito_p90)
            riga["dettagli"].append(f"di solito a questo punto della settimana: {numero_it(x.solito_p25, '%')}-{numero_it(x.solito_p75, '%')}% "
                                    f"(P25-P75 di {int(x.settimane_solito)} settimane; P10-P90 {numero_it(x.solito_p10, '%')}-"
                                    f"{numero_it(x.solito_p90, '%')}%)")
        righe.append(riga)
    valori = list(t["settimana_pct"]) + list(t["solito_p90"].dropna()) + [100]
    md = giorno_md_it(r.sintesi.get("giorno_md"))
    return base | {
        "spiegazione": (f"Allenamenti della settimana fino al {data_it(g)} ({md}), in percentuale della partita di riferimento di "
                        "ciascuno: la media dei suoi carichi da titolare (o del suo ruolo, se ha meno di 3 partite da titolare). "
                        "Le bande sono quanto si era fatto di solito allo stesso punto della settimana nelle settimane passate "
                        "(larga P10-P90, centrale P25-P75); il colore del punto dice dove cade la settimana. "
                        f"Attenzione: {AVVISO_RISCALDAMENTO}."),
        "asse": asse(valori) | {"nome": f"% della partita di riferimento, {nome}"},
        "riferimenti": [{"valore": 100, "testo": "una partita"}],
        "etichette": "tutte",
        "legenda": [{"tipo": "barra-larga", "testo": "di solito a questo punto della settimana, P10-P90"},
                    {"tipo": "barra-centrale", "testo": "P25-P75"},
                    {"tipo": "tacca", "testo": "mediana del solito"},
                    {"tipo": "riferimento", "testo": "100% = una partita di riferimento"},
                    *({"tipo": "punto", "posizione": p, "testo": "dentro il solito" if p == "dentro" else p} for p in POSIZIONI)],
        "righe": righe,
    }
