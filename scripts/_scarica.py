"""Scaricamento con controllo dell'impronta e ripresa dei file interrotti (usato dagli script dei dati)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

BLOCCO = 1 << 20  # 1 MB


class ImprontaErrata(Exception):
    pass


def impronta(path: Path, algoritmo: str) -> str:
    """md5 / sha256 del file, oppure "git" (sha1 dell'oggetto blob di git, come nell'albero di GitHub)."""
    if algoritmo == "git":
        h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    else:
        h = hashlib.new(algoritmo)
    with path.open("rb") as f:
        while chunk := f.read(BLOCCO):
            h.update(chunk)
    return h.hexdigest()


def scarica(client: httpx.Client, url: str, dest: Path, *, algoritmo: str, attesa: str,
            dimensione: int | None = None) -> str:
    """Scarica `url` in `dest` e controlla l'impronta. Restituisce "già presente" o "scaricato".

    Se il file c'è già con l'impronta giusta non lo riscarica; se un download si era interrotto
    riparte dal file `.part` (richiesta Range).
    """
    if dest.exists() and impronta(dest, algoritmo) == attesa:
        return "già presente"
    dest.parent.mkdir(parents=True, exist_ok=True)
    parziale = dest.with_name(dest.name + ".part")
    gia = parziale.stat().st_size if parziale.exists() else 0
    if dimensione is not None and gia > dimensione:  # parziale corrotto: si ricomincia
        parziale.unlink()
        gia = 0
    if dimensione is None or gia < dimensione:
        headers = {"Range": f"bytes={gia}-"} if gia else {}
        with client.stream("GET", url, headers=headers, follow_redirects=True) as r:
            if r.status_code == 200:
                gia = 0  # il server non riprende: si ricomincia
            elif r.status_code != 206:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code} per {url}", request=r.request, response=r)
            with parziale.open("ab" if gia else "wb") as f:
                for chunk in r.iter_bytes(BLOCCO):
                    f.write(chunk)
    if dimensione is not None and parziale.stat().st_size != dimensione:
        raise ImprontaErrata(f"{dest.name}: {parziale.stat().st_size} byte invece di {dimensione}")
    trovata = impronta(parziale, algoritmo)
    if trovata != attesa:
        parziale.unlink()
        raise ImprontaErrata(f"{dest.name}: impronta {algoritmo} {trovata} invece di {attesa}")
    parziale.replace(dest)
    return "scaricato"


def scrivi_manifesto(cartella: Path, fonte: dict, file: list[dict]) -> Path:
    """Registro di cosa è stato scaricato, da dove e con quale impronta (resta in data/raw/)."""
    manifesto = {
        "fonte": fonte,
        "scaricato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": file,
    }
    path = cartella / "MANIFEST.json"
    path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2))
    return path
