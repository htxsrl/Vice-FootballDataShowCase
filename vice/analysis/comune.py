"""Pezzi comuni alle analisi: metriche, nomi, calendario e settimane viste dall'"oggi".

Tutto parte da un `Visibile` (vice/data/stagione.py), che contiene solo il passato. Il calendario
delle partite è noto anche nel futuro, come nella realtà; i dati no.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.stagione import Visibile
from ..data.zenodo import METRICHE as _METRICHE_ZENODO

METRICHE: tuple[str, ...] = tuple(_METRICHE_ZENODO)        # td, hsr, spr, acc, dcc, hmld
UNITA = {m: u for m, (_, u, _) in _METRICHE_ZENODO.items()}
NOME_METRICA = {                                            # per le frasi
    "td": "distanza totale", "hsr": "distanza ad alta velocità (HSR)", "spr": "distanza in sprint",
    "acc": "accelerazioni", "dcc": "decelerazioni", "hmld": "distanza ad alto carico metabolico (HMLD)",
}
SIGLA = {"td": "TD", "hsr": "HSR", "spr": "SPR", "acc": "ACC", "dcc": "DCC", "hmld": "HMLD"}

SETTIMANA_REGOLARE_GIORNI = (6, 8)  # tra due partite: fuori da qui è una pausa o un periodo senza dati


def tutte_le_righe(v: Visibile) -> pd.DataFrame:
    """Storico più seduta di oggi: tutto ciò che è successo fino a oggi compreso."""
    if v.seduta_di_oggi.empty:
        return v.storico
    if v.storico.empty:
        return v.seduta_di_oggi
    return pd.concat([v.storico, v.seduta_di_oggi], ignore_index=True)


def anagrafica(v: Visibile) -> pd.DataFrame:
    """giocatore_id → nome_completo, numero, ruolo (nomi di fantasia)."""
    return v.giocatori.set_index("giocatore_id")[["nome_completo", "numero", "ruolo"]]


def date_partite(v: Visibile) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(v.calendario["data"]).sort_values()


def partita_prima(v: Visibile, giorno: pd.Timestamp) -> pd.Timestamp | None:
    """L'ultima partita **prima** del giorno (esclusa quella del giorno stesso)."""
    d = date_partite(v)
    d = d[d < giorno]
    return d[-1] if len(d) else None


def partita_da(v: Visibile, giorno: pd.Timestamp) -> pd.Timestamp | None:
    """La prima partita dal giorno in poi (compresa quella del giorno stesso)."""
    d = date_partite(v)
    d = d[d >= giorno]
    return d[0] if len(d) else None


def stato_in_partita(righe: pd.DataFrame, partita: pd.Timestamp, giocatori: list[int],
                     partita_con_dati: bool) -> dict[int, bool | None]:
    """Titolare (True) o no (False) nella partita; None se la partita non ha dati GPS.
    Chi non ha la riga della partita non ha giocato: non titolare."""
    if not partita_con_dati:
        return {g: None for g in giocatori}
    riga = righe[(righe["data"] == partita) & (righe["giorno_md"] == 0)]
    tit = riga.set_index("giocatore_id")["titolare_ultima_partita"]
    return {g: bool(tit[g]) if g in tit.index and not pd.isna(tit[g]) else False for g in giocatori}


def partita_ha_dati(v: Visibile, partita: pd.Timestamp) -> bool:
    p = v.partite_giocate
    r = p[p["data"] == partita]
    return bool(len(r)) and bool(r["dati_gps"].iloc[0])


@dataclass(frozen=True)
class Settimana:
    """Il microciclo: dal giorno dopo una partita fino alla partita successiva compresa."""
    partita_iniziale: pd.Timestamp | None   # la partita che apre la settimana (esclusa)
    partita_finale: pd.Timestamp | None     # la partita che la chiude (compresa)

    @property
    def giorni(self) -> int | None:
        if self.partita_iniziale is None or self.partita_finale is None:
            return None
        return (self.partita_finale - self.partita_iniziale).days

    @property
    def regolare(self) -> bool:
        """6-8 giorni tra le partite. Le altre sono pause o periodi senza dati nel dataset."""
        return self.giorni is not None and SETTIMANA_REGOLARE_GIORNI[0] <= self.giorni <= SETTIMANA_REGOLARE_GIORNI[1]

    def contiene(self, giorni: pd.Series) -> pd.Series:
        dopo = giorni > self.partita_iniziale if self.partita_iniziale is not None else True
        prima = giorni <= self.partita_finale if self.partita_finale is not None else True
        return dopo & prima


def settimana_di(v: Visibile, giorno: pd.Timestamp) -> Settimana:
    """La settimana a cui appartiene il giorno (il giorno di partita chiude la sua settimana)."""
    return Settimana(partita_prima(v, giorno), partita_da(v, giorno))


def settimane_regolari(v: Visibile, fino_a: pd.Timestamp | None) -> list[Settimana]:
    """Le settimane regolari (6-8 giorni) concluse entro la data data, partita finale compresa."""
    if fino_a is None:
        return []
    d = date_partite(v)
    return [s for s in (Settimana(a, b) for a, b in zip(d[:-1], d[1:])) if s.partita_finale <= fino_a and s.regolare]



def taglio(settimana: Settimana, giorno_md: int) -> pd.Timestamp | None:
    """Il giorno di una settimana che corrisponde al giorno MD dato: prima della partita si conta
    all'indietro dalla partita finale, dopo la partita in avanti da quella iniziale."""
    if giorno_md <= 0:
        return settimana.partita_finale + pd.Timedelta(days=giorno_md) if settimana.partita_finale is not None else None
    return settimana.partita_iniziale + pd.Timedelta(days=giorno_md) if settimana.partita_iniziale is not None else None
