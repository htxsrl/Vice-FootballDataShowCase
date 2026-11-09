"""Le verifiche del motore come evidenze citabili: replica dell'articolo del dataset (M2.13)."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ..config import get_settings
from ..data import zenodo
from ..data.validazione_zenodo import riepilogo
from .evidenze import Risultato, evidenza

ARTICOLO = "Sierra-Casas et al., Data 2026, 11(4), 84"


@lru_cache
def _riepilogo() -> dict:
    return riepilogo(zenodo.carica(get_settings().processed_dir / "zenodo").carichi)


def replica_articolo() -> Risultato:
    r = _riepilogo()
    oggi = pd.Timestamp.now().normalize()
    evid = [
        evidenza("replica/tabella1", f"Tabella 1 dell'articolo del dataset riprodotta: celle identiche ({ARTICOLO})",
                 r["tabella1_celle_uguali"], "n", celle=r["tabella1_celle"], righe=2375),
        evidenza("replica/tabella2/td", "Tabella 2 dell'articolo, distanza totale: medie identiche", r["tabella2_td_celle_uguali"],
                 "n", celle=r["tabella2_td_celle"], refuso=r["tabella2_td_celle"] - r["tabella2_td_celle_uguali"],
                 refuso_spiegato=r["tabella2_td_refuso_spiegato"],
                 nota="le celle diverse sono un refuso dell'articolo: titolari e non titolari scambiati per i difensori centrali"),
        evidenza("replica/tabella2/hsr", "Tabella 2 dell'articolo, HSR dei difensori centrali: medie identiche",
                 r["tabella2_hsr_cd_celle_uguali"], "n", celle=r["tabella2_hsr_cd_celle"]),
    ]
    for m, d in r["denominatori"].items():
        evid.append(evidenza(f"replica/denominatori/{m}", f"Colonne RATIO del dataset ({m.upper()}): scarto mediano del denominatore dalla media da titolare",
                             d["scarto_mediano_media_pct"], "%", metrica=m, scarto_dal_massimo_pct=round(d["scarto_mediano_massimo_pct"])))
    return Risultato("replica_articolo", oggi, pd.DataFrame(), evid, [], {"articolo": ARTICOLO})
