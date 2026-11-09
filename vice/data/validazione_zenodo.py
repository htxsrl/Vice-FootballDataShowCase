"""M2.13 Replica dell'articolo del dataset: i nostri numeri sono quelli pubblicati?

Articolo: Sierra-Casas et al., *Data* 2026, 11(4), 84 (wiki/fonti/zenodo-18986229-articolo-data-2026.pdf).
- Tabella 1: righe per giorno MD e stato (titolare/non titolare, colonna `ESTATUS` del dataset);
- Tabella 2: medie per giorno MD × ruolo × stato (qui distanza totale, e HSR dei difensori centrali);
- colonne `RATIO*`: il denominatore dichiarato è il massimo in partita, quello vero la media da titolare.

Usa le colonne del dataset che l'"oggi" simulato nasconde (`estatus_dataset`, `rapporto_*_dataset`):
è una verifica sul dataset intero, non un'analisi di Vice. Esiti in wiki/dati/pipeline-zenodo.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .zenodo import METRICHE

GIORNI = (0, 1, 2, -5, -4, -3, -2, -1)                 # ordine delle colonne dell'articolo
POSIZIONI = {"difensore centrale": "CD", "terzino": "FB", "centrocampista": "CM", "esterno": "WM", "attaccante": "FW"}
STATO = {"T": "S", "S": "NS"}                          # ESTATUS → sigle dell'articolo (S = starter)

TABELLA1 = {"NS": (183, 101, 91, 57, 102, 279, 201, 263), "S": (236, 29, 64, 43, 82, 238, 180, 226)}

TABELLA2_TD = {
    ("CD", "NS"): (2143.4, 2334.8, 2621.3, 4782.4, 5510.4, 5385.4, 5036.1, 3179.7),
    ("CD", "S"): (9672.0, 4964.9, 4852.1, 4444.5, 5252.1, 5373.3, 5172.9, 3173.3),
    ("FB", "NS"): (3859.5, 4597.6, 4959.7, 4502.0, 5312.0, 5776.6, 5530.4, 3245.6),
    ("FB", "S"): (9925.7, 2003.2, 2458.1, 4880.7, 5556.0, 5681.4, 5060.2, 3153.3),
    ("CM", "NS"): (3709.1, 5186.2, 4194.8, 4585.1, 5573.1, 5655.8, 5159.9, 2924.6),
    ("CM", "S"): (10590.6, 2106.9, 2408.4, 4547.8, 5564.7, 5451.3, 5271.1, 3039.8),
    ("WM", "NS"): (4138.7, 4797.3, 4265.8, 4589.9, 5608.2, 5527.3, 5114.1, 2997.0),
    ("WM", "S"): (8991.3, 2289.3, 2229.6, 4415.5, 5438.8, 5567.7, 5249.2, 3018.9),
    ("FW", "NS"): (3930.6, 4018.4, 4296.4, 4571.0, 5254.6, 5115.0, 4822.2, 2814.5),
    ("FW", "S"): (8976.8, 1794.0, 2557.9, 4678.4, 5285.4, 5493.6, 4828.3, 2995.0),
}
TABELLA2_HSR_CD = {"NS": (170.3, 202.6, 266.7, 81.9, 154.2, 148.5, 116.9, 55.6),
                   "S": (307.6, 84.4, 11.8, 89.4, 133.6, 152.6, 137.9, 63.4)}
# Refuso dell'articolo: per i difensori centrali, in questi giorni, titolari e non titolari sono scambiati
REFUSO_TD = {("CD", 1), ("CD", 2), ("CD", -5)}
TOLLERANZA = 0.1   # m: le medie dell'articolo hanno un decimale


def _con_sigle(carichi: pd.DataFrame) -> pd.DataFrame:
    return carichi.assign(pos=carichi["ruolo"].map(POSIZIONI), stato=carichi["estatus_dataset"].map(STATO))


def tabella1(carichi: pd.DataFrame) -> pd.DataFrame:
    """Confronto della Tabella 1: una riga per stato × giorno MD."""
    c = _con_sigle(carichi).groupby(["stato", "giorno_md"]).size()
    return pd.DataFrame([{"stato": s, "giorno_md": g, "articolo": n, "nostro": int(c.get((s, g), 0))}
                         for s, valori in TABELLA1.items() for g, n in zip(GIORNI, valori, strict=True)])


def tabella2(carichi: pd.DataFrame, metrica: str = "td") -> pd.DataFrame:
    """Confronto della Tabella 2 per la metrica (td: tutte le celle; hsr: difensori centrali)."""
    medie = _con_sigle(carichi).groupby(["pos", "stato", "giorno_md"])[metrica].mean()
    articolo = TABELLA2_TD if metrica == "td" else {("CD", s): v for s, v in TABELLA2_HSR_CD.items()}
    righe = []
    for (pos, stato), valori in articolo.items():
        altro = "S" if stato == "NS" else "NS"
        for g, a in zip(GIORNI, valori, strict=True):
            nostro = float(medie.get((pos, stato, g), np.nan))
            righe.append({"pos": pos, "stato": stato, "giorno_md": g, "articolo": a, "nostro": nostro,
                          "nostro_stato_scambiato": float(medie.get((pos, altro, g), np.nan)),
                          "uguale": abs(nostro - a) <= TOLLERANZA + 1e-9,
                          "refuso": metrica == "td" and (pos, g) in REFUSO_TD})
    return pd.DataFrame(righe)


def denominatori_ratio(carichi: pd.DataFrame) -> pd.DataFrame:
    """Per giocatore × metrica: il denominatore implicito delle colonne RATIO (valore / rapporto),
    la media e il massimo delle sue partite da titolare nel file."""
    tit = carichi[(carichi["giorno_md"] == 0) & (carichi["estatus_dataset"] == "T")]
    righe = []
    for m in METRICHE:
        ok = carichi[m] > 0
        den = (carichi.loc[ok, m] / carichi.loc[ok, f"rapporto_{m}_dataset"]).groupby(carichi.loc[ok, "giocatore_id"]).median()
        media, massimo = tit.groupby("giocatore_id")[m].mean(), tit.groupby("giocatore_id")[m].max()
        for gid, d in den.items():
            righe.append({"giocatore_id": gid, "metrica": m, "denominatore": d,
                          "media_da_titolare": media.get(gid, np.nan), "massimo_da_titolare": massimo.get(gid, np.nan)})
    out = pd.DataFrame(righe)
    out["scarto_media_pct"] = 100 * (out["denominatore"] / out["media_da_titolare"] - 1)
    out["scarto_massimo_pct"] = 100 * (out["denominatore"] / out["massimo_da_titolare"] - 1)
    return out


def riepilogo(carichi: pd.DataFrame) -> dict:
    """I numeri da citare (wiki, demo, PDF)."""
    t1, t2, hsr = tabella1(carichi), tabella2(carichi, "td"), tabella2(carichi, "hsr")
    refuso = t2[t2["refuso"]]
    den = denominatori_ratio(carichi).dropna(subset=["media_da_titolare"])
    per_metrica = den.groupby("metrica").agg(
        scarto_mediano_media_pct=("scarto_media_pct", lambda s: float(s.abs().median())),
        scarto_mediano_massimo_pct=("scarto_massimo_pct", "median"))
    return {
        "tabella1_celle_uguali": int((t1["articolo"] == t1["nostro"]).sum()), "tabella1_celle": len(t1),
        "tabella2_td_celle_uguali": int(t2["uguale"].sum()), "tabella2_td_celle": len(t2),
        "tabella2_td_refuso_spiegato": bool((abs(refuso["nostro_stato_scambiato"] - refuso["articolo"]) <= TOLLERANZA + 1e-9).all()),
        "tabella2_hsr_cd_celle_uguali": int(hsr["uguale"].sum()), "tabella2_hsr_cd_celle": len(hsr),
        "denominatori": per_metrica.round(1).to_dict("index"),
    }
