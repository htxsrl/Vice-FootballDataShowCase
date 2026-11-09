"""I report pronti (decisione 49): il report della seduta per il preparatore, generato in anticipo per una parte
dei giorni della stagione con `scripts/prepara_report.py` e salvato in data/processed/report/.

Nel calendario quei giorni hanno il pallino e aprirli non costa nulla. A ogni lettura i numeri del report si
ricontrollano coi dati del motore (vice/agent/report.py): se il motore è cambiato e il report non torna più,
si ignora e si rigenera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import get_settings


def cartella() -> Path:
    return get_settings().processed_dir / "report"


def percorso(giorno) -> Path:
    return cartella() / f"seduta-{pd.Timestamp(giorno):%Y-%m-%d}.json"


def giorni(fino_a=None) -> list[str]:
    """I giorni (AAAA-MM-GG) con un report pronto, fino a `fino_a` compreso."""
    c = cartella()
    if not c.exists():
        return []
    out = sorted(p.stem.removeprefix("seduta-") for p in c.glob("seduta-*.json"))
    if fino_a is not None:
        limite = f"{pd.Timestamp(fino_a):%Y-%m-%d}"
        out = [d for d in out if d <= limite]
    return out


def leggi(giorno) -> dict | None:
    try:
        return json.loads(percorso(giorno).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scrivi(giorno, dati: dict) -> Path:
    p = percorso(giorno)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p
