"""Viste della lavagna: il server costruisce la specifica completa dei grafici, il front-end la disegna e basta.

Ogni vista riceve la sessione (l'"oggi" simulato, quindi niente dati dal futuro) e i parametri chiesti
dall'agente o dall'interfaccia, e restituisce una specifica JSON (vedi comune.py). Catalogo e regole:
wiki/tecnica/frontend-e-viste.md. Roadmap M4: wiki/roadmap.md.
"""

from __future__ import annotations

from collections.abc import Callable

from ..agent.contesto import ErroreStrumento, Sessione
from .curva import vista_curva
from .giocatore import vista_giocatore
from .partita import vista_partita
from .seduta import vista_seduta
from .settimana import vista_settimana
from .verifica import vista_verifica

COSTRUTTORI: dict[str, Callable[[Sessione, dict], dict]] = {
    "seduta": vista_seduta,                 # V2
    "settimana": vista_settimana,           # V1
    "giocatore": vista_giocatore,           # V3
    "curva_settimana": vista_curva,         # V5
    "allenamento_partita": vista_partita,   # V6
    "verifica": vista_verifica,             # V9 (V7 e V8, SkillCorner, tolte con la decisione 57)
}


def costruisci(nome: str, s: Sessione, parametri: dict | None = None) -> dict:
    """La specifica della vista `nome`. Errori in italiano (ErroreStrumento) per parametri non validi."""
    f = COSTRUTTORI.get(nome)
    if f is None:
        raise ErroreStrumento(f"vista non ancora disponibile: {nome}")
    p = {k: v for k, v in (parametri or {}).items() if v not in (None, "")}
    return f(s, p)
