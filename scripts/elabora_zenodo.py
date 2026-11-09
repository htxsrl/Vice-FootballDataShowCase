"""M1.2-M1.4 — Converte Zenodo 18986229 nel formato Vice e ne controlla la qualità.

Uso (nel container, dopo scripts.scarica_zenodo):  python3 -m scripts.elabora_zenodo

Scrive in data/processed/zenodo/: partite, sedute, carichi, giocatori (Parquet) e qualita.json.
"""

from __future__ import annotations

import json
import sys

from vice.config import get_settings
from vice.data import zenodo
from vice.data.qualita import controlli_zenodo


def main() -> int:
    s = get_settings()
    dati = zenodo.converti(zenodo.leggi_csv(s.raw_dir / "zenodo" / "DataSetTMr.csv"))
    dest = s.processed_dir / "zenodo"
    for p in zenodo.salva(dati, dest):
        print(f"  scritto {p.relative_to(s.data_dir)} ({p.stat().st_size // 1024} KB)")
    q = controlli_zenodo(dati)
    (dest / "qualita.json").write_text(json.dumps(q, ensure_ascii=False, indent=2))
    print(json.dumps({k: q[k] for k in ("conteggi", "integrita", "calendario", "titolare")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
