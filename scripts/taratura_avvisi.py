"""Taratura degli avvisi (decisione 53): li fa girare su tutti i giorni di seduta della stagione, senza costi.

    docker compose exec -T vice python3 -m scripts.taratura_avvisi                    # tutta la stagione
    docker compose exec -T vice python3 -m scripts.taratura_avvisi --fino-a 2024-04-18

Ogni giorno vede solo il suo passato. Stampa, per famiglia, quanti avvisi nascono, quanti si mostrano (al massimo
3 al giorno e 5 nel riassunto settimanale; la qualità del dato a parte) e quanti a settimana, con alcuni esempi.
Salva tutto in data/processed/avvisi/taratura.json, per rileggere gli avvisi giorno per giorno.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from vice.agent.contesto import Sessione
from vice.analysis.avvisi import FAMIGLIE, SOGLIE, avvisi, classificazione, scegli
from vice.analysis.comune import tutte_le_righe
from vice.analysis.evidenze import giorno_md_it
from vice.config import get_settings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fino-a", default=None, help="ultimo giorno (AAAA-MM-GG); di default la fine della stagione")
    ap.add_argument("--esempi", type=int, default=4, help="esempi per famiglia")
    args = ap.parse_args()

    st = Sessione.crea().stagione
    fino_a = pd.Timestamp(args.fino_a) if args.fino_a else st.fine
    t0 = time.time()
    c = classificazione(tutte_le_righe(st.al(fino_a)))
    print(f"classificazione di tutte le sedute: {time.time() - t0:.0f} s")

    giorni = sorted(pd.Timestamp(d) for d in st.giorni_di_seduta if pd.Timestamp(d) <= fino_a)
    per_giorno = []
    for d in giorni:
        v = st.al(d)
        tutti = avvisi(v, c)
        s = scegli(tutti)
        per_giorno.append({"data": f"{d:%Y-%m-%d}", "giorno_md": giorno_md_it(v.contesto.giorno_md),
                           "tutti": [a.to_dict() for a in tutti],
                           "mostrati": {k: [a.to_dict() for a in lista] for k, lista in s.items()}})
    print(f"{len(giorni)} giorni in {time.time() - t0:.0f} s\n")

    nati, mostrati, giorni_con = Counter(), Counter(), Counter()
    settimana_mostrati: dict[str, Counter] = defaultdict(Counter)
    esempi: dict[str, list[dict]] = defaultdict(list)
    for g in per_giorno:
        sett = pd.Timestamp(g["data"]).strftime("%G-%V")
        for a in g["tutti"]:
            nati[a["famiglia"]] += 1
            esempi[a["famiglia"]].append(a)
        visti = {a["famiglia"] for lista in g["mostrati"].values() for a in lista}
        for lista in g["mostrati"].values():
            for a in lista:
                mostrati[a["famiglia"]] += 1
                settimana_mostrati[sett][a["famiglia"]] += 1
        for f in visti:
            giorni_con[f] += 1

    settimane = sorted(settimana_mostrati) or ["-"]
    print(f"{'famiglia':38} {'nati':>5} {'mostrati':>9} {'giorni':>7} {'a settimana':>12}")
    for f, (_, nome) in sorted(FAMIGLIE.items(), key=lambda x: x[1][0]):
        media = mostrati[f] / max(len(settimane), 1)
        print(f"{nome:38} {nati[f]:>5} {mostrati[f]:>9} {giorni_con[f]:>7} {media:>12.1f}")
    totali = [sum(settimana_mostrati[s].values()) for s in settimane]
    senza_dato = [sum(n for f, n in settimana_mostrati[s].items() if f != "dato") for s in settimane]
    print(f"\nsettimane con sedute: {len(settimane)}; avvisi mostrati a settimana (senza la qualità del dato): "
          f"mediana {np.median(senza_dato):.0f}, media {np.mean(senza_dato):.1f}, massimo {max(senza_dato)}, minimo {min(senza_dato)}")
    print(f"giorni senza avvisi del giorno: {sum(1 for g in per_giorno if not g['mostrati']['giorno'])} su {len(per_giorno)}")

    scelti_esempi = {}
    for f, lista in esempi.items():
        passo = max(len(lista) // args.esempi, 1)
        scelti_esempi[f] = lista[::passo][:args.esempi]
    print("\nesempi:")
    for f, (_, nome) in sorted(FAMIGLIE.items(), key=lambda x: x[1][0]):
        for a in scelti_esempi.get(f, []):
            print(f"- [{nome}, {a['data']}] {a['testo']}")

    cartella = get_settings().processed_dir / "avvisi"
    cartella.mkdir(parents=True, exist_ok=True)
    riepilogo = {"fino_a": f"{fino_a:%Y-%m-%d}", "soglie": SOGLIE, "giorni": len(per_giorno), "settimane": len(settimane),
                 "per_famiglia": {f: {"nati": nati[f], "mostrati": mostrati[f], "giorni": giorni_con[f]} for f in FAMIGLIE},
                 "a_settimana_senza_dato": {"mediana": float(np.median(senza_dato)), "media": float(np.mean(senza_dato)),
                                            "massimo": int(max(senza_dato)), "minimo": int(min(senza_dato))},
                 "a_settimana_tutti": {"mediana": float(np.median(totali)), "massimo": int(max(totali))}}
    (cartella / "taratura.json").write_text(json.dumps({"riepilogo": riepilogo, "giorni": per_giorno}, ensure_ascii=False,
                                                       indent=1, default=str) + "\n", encoding="utf-8")
    print(f"\nsalvato in {cartella / 'taratura.json'}")


if __name__ == "__main__":
    main()
