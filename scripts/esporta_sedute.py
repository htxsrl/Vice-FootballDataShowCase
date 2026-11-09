"""M1.6 — Scrive un CSV "come da GPS" per ogni seduta della stagione Zenodo (da trascinare in Vice).

Uso (nel container):  python3 -m scripts.esporta_sedute
I file vanno in data/cache/export_sedute/ (gitignored): si rigenerano in un attimo.
"""

from __future__ import annotations

import sys

from vice.config import get_settings
from vice.data.export_gps import esporta_seduta
from vice.data.stagione import stagione


def main() -> int:
    dest = get_settings().data_dir / "cache" / "export_sedute"
    dest.mkdir(parents=True, exist_ok=True)
    st = stagione()
    for giorno in st.giorni_di_seduta:
        v = st.al(giorno)
        (dest / f"seduta_{giorno:%Y-%m-%d}.csv").write_text(esporta_seduta(v.seduta_di_oggi, v.giocatori))
    print(f"Fatto: {len(st.giorni_di_seduta)} export in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
