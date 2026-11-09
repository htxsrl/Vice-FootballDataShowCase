"""L'"oggi" simulato (M1.5): l'unico punto da cui il motore legge i dati di Zenodo.

La stagione 2023/24 si rivive giorno per giorno (decisione D2 della roadmap). Dato un giorno X:

- `storico`: i carichi dei giorni **prima** di X (base delle fasce attese);
- `seduta_di_oggi`: i carichi del giorno X (vuota se quel giorno non c'è seduta);
- `sedute` e `partite_giocate`: il calendario fino a X compreso;
- `calendario`: le date di tutte le partite, anche future. Come nella realtà, il calendario è
  noto in anticipo e serve a sapere a quanti giorni dalla partita siamo; i dati no.

Le colonne del dataset che contengono informazioni future (`rapporto_*_dataset`, calcolate su un
valore di partita dell'intera stagione; `estatus_dataset`, che a volte anticipa la formazione) non
escono mai da qui.
Il test anti-futuro è in tests/test_stagione.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import get_settings
from .anagrafica import con_nomi
from .zenodo import DatiZenodo, carica

COLONNE_NASCOSTE = ("estatus_dataset", "microciclo_dataset")
GIORNI_MD_MIN, GIORNI_MD_MAX = -5, 2


def _pubbliche(carichi: pd.DataFrame) -> pd.DataFrame:
    nascoste = [c for c in carichi.columns if c.startswith("rapporto_") or c in COLONNE_NASCOSTE]
    return carichi.drop(columns=nascoste)


@dataclass(frozen=True)
class Contesto:
    """Dove siamo nella stagione il giorno X (serve anche alla barra dell'"oggi", M4.7)."""
    oggi: pd.Timestamp
    giorno_md: int | None          # None = giorno di pausa (lontano da ogni partita)
    ultima_partita: pd.Timestamp | None
    prossima_partita: pd.Timestamp | None
    settimana: int                 # 1 = la settimana che parte dalla prima partita; 0 = prima


@dataclass(frozen=True)
class Visibile:
    oggi: pd.Timestamp
    contesto: Contesto
    giocatori: pd.DataFrame        # con nomi e numeri di fantasia
    calendario: pd.DataFrame       # solo le date delle partite
    partite_giocate: pd.DataFrame
    sedute: pd.DataFrame
    storico: pd.DataFrame
    seduta_di_oggi: pd.DataFrame


class Stagione:
    def __init__(self, dati: DatiZenodo):
        self._dati = dati
        self._carichi = _pubbliche(dati.carichi)
        self._giocatori = con_nomi(dati.giocatori)   # nomi di fantasia (decisione 21)
        self._date_partite = pd.DatetimeIndex(dati.partite["data"]).sort_values()

    @property
    def giorni_di_seduta(self) -> list[pd.Timestamp]:
        return list(self._dati.sedute["data"])

    @property
    def inizio(self) -> pd.Timestamp:
        return self._dati.sedute["data"].min()

    @property
    def fine(self) -> pd.Timestamp:
        return self._dati.sedute["data"].max()

    def contesto(self, oggi: date | str | pd.Timestamp) -> Contesto:
        oggi = pd.Timestamp(oggi).normalize()
        passate = self._date_partite[self._date_partite <= oggi]
        future = self._date_partite[self._date_partite >= oggi]
        ultima = passate[-1] if len(passate) else None
        prossima = future[0] if len(future) else None
        # Come nel dataset: il dopo-partita (MD+1, MD+2) ha la precedenza sul pre-partita.
        giorno_md = None
        if ultima is not None and (oggi - ultima).days <= GIORNI_MD_MAX:
            giorno_md = (oggi - ultima).days
        elif prossima is not None and (prossima - oggi).days <= -GIORNI_MD_MIN:
            giorno_md = -(prossima - oggi).days
        return Contesto(oggi=oggi, giorno_md=giorno_md, ultima_partita=ultima,
                        prossima_partita=prossima, settimana=len(passate))

    def al(self, oggi: date | str | pd.Timestamp) -> Visibile:
        """Tutto ciò che Vice può vedere il giorno `oggi`: niente dati successivi."""
        oggi = pd.Timestamp(oggi).normalize()
        d, c = self._dati, self._carichi
        return Visibile(
            oggi=oggi,
            contesto=self.contesto(oggi),
            giocatori=self._giocatori.copy(),
            calendario=d.partite[["data"]].copy(),
            partite_giocate=d.partite[d.partite["data"] <= oggi].reset_index(drop=True),
            sedute=d.sedute[d.sedute["data"] <= oggi].reset_index(drop=True),
            storico=c[c["data"] < oggi].reset_index(drop=True),
            seduta_di_oggi=c[c["data"] == oggi].reset_index(drop=True),
        )


@lru_cache
def stagione(cartella: Path | None = None) -> Stagione:
    """La stagione Zenodo elaborata (data/processed/zenodo/), caricata una volta sola."""
    return Stagione(carica(cartella or get_settings().processed_dir / "zenodo"))
