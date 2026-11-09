"""M1.1 — Scarica il dataset Zenodo 18986229 (CSV + dizionario dei dati) in data/raw/zenodo/.

Uso (nel container):  python3 -m scripts.scarica_zenodo

Le impronte md5 sono quelle pubblicate da Zenodo (verificate sull'API il 21/10/2026): se il file
cambia, lo script si ferma invece di usare dati diversi. Licenza CC BY 4.0 (data/README.md).
"""

from __future__ import annotations

import sys

import httpx

from scripts._scarica import scarica, scrivi_manifesto
from vice.config import get_settings

RECORD = "18986229"
DOI = "10.5281/zenodo.18986229"
FILE = {  # nome → (md5, byte)
    "DataSetTMr.csv": ("864bfbc3f78a736f60bba764de8d4f4d", 278946),
    "DataDictionary.xlsx": ("10959d59ba0ad221a0b783d618d27d53", 11448),
}


def main() -> int:
    dest = get_settings().raw_dir / "zenodo"
    registro = []
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        for nome, (md5, size) in FILE.items():
            url = f"https://zenodo.org/records/{RECORD}/files/{nome}?download=1"
            esito = scarica(client, url, dest / nome, algoritmo="md5", attesa=md5, dimensione=size)
            registro.append({"file": nome, "byte": size, "md5": md5})
            print(f"  {esito:13s} {nome}")
    scrivi_manifesto(dest, {"record": f"https://zenodo.org/records/{RECORD}", "doi": DOI, "licenza": "CC BY 4.0"}, registro)
    print(f"Fatto: {len(registro)} file in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
