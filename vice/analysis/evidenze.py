"""Evidenze: ogni numero che Vice può dire, con il suo contesto (M2; verifica dei numeri in M3.8).

Ogni analisi restituisce un `Risultato`: una tabella (per le viste e i test), le evidenze (per
l'agente e la verifica), gli avvisi (cosa manca o cosa vale con cautela) e una sintesi. I numeri
li produce sempre il codice; l'LLM li può solo citare. Tutto è serializzabile in JSON.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

# decimali con cui un numero si mostra e si cita, per unità di misura
DECIMALI = {"m": 0, "n": 0, "%": 0, "percentile": 0, "casi": 0, "sedute": 0, "settimane": 0,
            "partite": 0, "giocatori": 0, "minuti": 0, "m/min": 1}


def arrotonda(valore: Any, unita: str) -> Any:
    """Arrotonda come si mostra: interi per metri e conteggi, un decimale per i metri al minuto."""
    if valore is None or isinstance(valore, (str, bool)):
        return valore
    v = float(valore)
    if math.isnan(v):
        return None
    d = DECIMALI.get(unita, 2)
    v = round(v, d)
    return int(v) if d == 0 else v


def pulisci(x: Any) -> Any:
    """Converte in tipi JSON: date in AAAA-MM-GG, numpy in Python, NaN in None."""
    if isinstance(x, dict):
        return {str(k): pulisci(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [pulisci(v) for v in x]
    if isinstance(x, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(x).strftime("%Y-%m-%d")
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else float(x)
    if x is pd.NA or x is pd.NaT:
        return None
    return x


@dataclass(frozen=True)
class Evidenza:
    id: str                       # stabile e leggibile, es. "seduta/2024-01-10/13/td"
    etichetta: str                # frase breve in italiano: cosa è il numero
    valore: Any                   # già arrotondato come si mostra
    unita: str                    # "m", "n", "%", "m/min", "percentile", "" …
    contesto: dict = field(default_factory=dict)   # giocatore, data, giorno MD, fascia, casi…
    grafico: str | None = None    # elemento del grafico da evidenziare (M4.5)

    def numeri(self) -> list[float]:
        """Tutti i numeri citabili: il valore e quelli del contesto (fascia, percentile, casi…)."""
        out: list[float] = []

        def raccogli(x: Any) -> None:
            if isinstance(x, bool) or x is None:
                return
            if isinstance(x, (int, float)):
                out.append(float(x))
            elif isinstance(x, dict):
                for v in x.values():
                    raccogli(v)
            elif isinstance(x, list):
                for v in x:
                    raccogli(v)
        raccogli(self.valore)
        raccogli(self.contesto)
        return out

    def to_dict(self) -> dict:
        return {"id": self.id, "etichetta": self.etichetta, "valore": self.valore, "unita": self.unita,
                "contesto": self.contesto, "grafico": self.grafico}


def evidenza(id: str, etichetta: str, valore: Any, unita: str, grafico: str | None = None,
             **contesto: Any) -> Evidenza:
    return Evidenza(id=id, etichetta=etichetta, valore=arrotonda(pulisci(valore), unita), unita=unita,
                    contesto=pulisci(contesto), grafico=grafico)


@dataclass
class Risultato:
    analisi: str                  # nome dell'analisi, es. "seduta"
    oggi: pd.Timestamp
    tabella: pd.DataFrame         # per le viste e i test
    evidenze: list[Evidenza] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)
    sintesi: dict = field(default_factory=dict)
    altre: dict[str, pd.DataFrame] = field(default_factory=dict)   # tabelle secondarie, per le viste

    def evidenza(self, id: str) -> Evidenza:
        for e in self.evidenze:
            if e.id == id:
                return e
        raise KeyError(id)

    def to_dict(self) -> dict:
        return {"analisi": self.analisi, "oggi": pulisci(self.oggi), "sintesi": pulisci(self.sintesi),
                "avvisi": list(self.avvisi), "evidenze": [e.to_dict() for e in self.evidenze],
                "tabella": pulisci(self.tabella.to_dict("records")),
                "altre": {k: pulisci(t.to_dict("records")) for k, t in self.altre.items()}}


def numero_it(x: Any, unita: str = "") -> str:
    """5436.2 → "5.436" (m); 182.04 → "182,0" (m/min): come si scrive in italiano."""
    v = arrotonda(x, unita)
    if v is None:
        return "n.d."
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    intero, dec = f"{v:,.{DECIMALI.get(unita, 2)}f}".split(".")
    return intero.replace(",", ".") + "," + dec


def con_unita(x: Any, unita: str) -> str:
    """5436.6, "m" → "5.437 m"; 73, "n" → "73"; 54, "%" → "54%"."""
    n = numero_it(x, unita)
    if unita in ("n", "", "percentile"):
        return n
    return f"{n}%" if unita == "%" else f"{n} {unita}"


def maiuscola(s: str) -> str:
    """Prima lettera maiuscola, senza toccare le sigle (a differenza di str.capitalize)."""
    return s[:1].upper() + s[1:]


def data_it(d: Any) -> str:
    """10/01/2024"""
    return pd.Timestamp(d).strftime("%d/%m/%Y")


def giorno_md_it(g: int | None) -> str:
    """-3 → "MD-3", 0 → "MD", 1 → "MD+1", None → "pausa"."""
    if g is None or (isinstance(g, float) and math.isnan(g)):
        return "pausa"
    g = int(g)
    return "MD" if g == 0 else f"MD{g:+d}"
