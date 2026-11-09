"""Le sedute caricate dall'interfaccia (M4.8, effetto "Dal file al report"; decisione 54).

Un export GPS caricato viene letto dall'adattatore (export_gps.py) e tenuto **in memoria** per un paio
d'ore con un codice: le richieste che portano quel codice (chat, viste, report) analizzano le righe del
file al posto della seduta del dataset per quel giorno. Niente su disco, niente database: se il server
riparte, il file va ricaricato. Un file con gli stessi valori del dataset ha invece il codice
`dataset-AAAA-MM-GG` e non occupa memoria (vice/agent/contesto.py lo riconosce).
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import pandas as pd

DURATA_S = 2 * 60 * 60
MAX_CARICAMENTI = 20
# un file uguale alle righe del dataset non si tiene in memoria: il codice dice solo il giorno (decisione 54), così
# vale anche dopo un riavvio del server e il report può venire dai report pronti
PREFISSO_DATASET = "dataset-"


@dataclass(frozen=True)
class Caricamento:
    codice: str
    data: pd.Timestamp
    righe: pd.DataFrame
    nome_file: str
    quando: float

    @property
    def dal_dataset(self) -> bool:
        """Il file aveva gli stessi valori del dataset: si usano le righe del dataset."""
        return self.codice.startswith(PREFISSO_DATASET)


def codice_dataset(giorno) -> str:
    return f"{PREFISSO_DATASET}{pd.Timestamp(giorno):%Y-%m-%d}"


_memoria: "OrderedDict[str, Caricamento]" = OrderedDict()


def _pulisci() -> None:
    adesso = time.time()
    for k in [k for k, c in _memoria.items() if adesso - c.quando > DURATA_S]:
        del _memoria[k]
    while len(_memoria) > MAX_CARICAMENTI:
        _memoria.popitem(last=False)


def salva(righe: pd.DataFrame, nome_file: str) -> Caricamento:
    _pulisci()
    c = Caricamento(uuid.uuid4().hex[:12], pd.Timestamp(righe["data"].iloc[0]).normalize(), righe, nome_file[:120], time.time())
    _memoria[c.codice] = c
    return c


def trova(codice: str | None) -> Caricamento | None:
    _pulisci()
    return _memoria.get(codice) if codice else None


def svuota() -> None:
    _memoria.clear()
