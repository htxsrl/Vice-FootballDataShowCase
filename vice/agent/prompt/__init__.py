"""Prompt di Vice, versionati (M3.3): ogni file è `<nome>_v<N>.md`; si usa la versione più alta,
o quella indicata. La versione finisce negli eventi `done` e nel banco di prova."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent


@lru_cache
def carica(nome: str, versione: int | None = None) -> tuple[str, str]:
    """(testo, "nome_vN")"""
    trovati = {int(m.group(1)): p for p in CARTELLA.glob(f"{nome}_v*.md") if (m := re.fullmatch(rf"{nome}_v(\d+)\.md", p.name))}
    if not trovati:
        raise FileNotFoundError(f"prompt {nome} mancante")
    v = versione if versione is not None else max(trovati)
    return trovati[v].read_text(), f"{nome}_v{v}"
