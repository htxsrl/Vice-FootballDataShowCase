"""L'archivio degli avvisi (decisione 54): gli avvisi mostrati di ogni giorno di seduta, senza costi.

    docker compose exec -T vice python3 -m scripts.prepara_avvisi            # ricalcola e salva (circa 80 s)
    docker compose exec -T vice python3 -m scripts.prepara_avvisi --controlla # dice solo se l'archivio è aggiornato

Va rifatto quando cambiano le regole degli avvisi o il motore: l'archivio porta la firma del codice che l'ha
prodotto, e un test fallisce se non torna. Salva data/processed/avvisi/archivio.json; stampa quanti avvisi
restano da guardare all'apertura di ogni giorno (gli aperti che chiedono un'azione), per la taratura del flusso.
"""

from __future__ import annotations

import argparse
import sys
import time
from statistics import median

import pandas as pd

from vice.analysis.archivio_avvisi import calcola, con_lo_stato, firma, leggi, presenze_da, salva
from vice.analysis.comune import tutte_le_righe
from vice.data.stagione import stagione


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--controlla", action="store_true", help="non ricalcola: dice se la firma torna")
    args = ap.parse_args()
    f = firma()
    if args.controlla:
        salvato = leggi()
        ok = bool(salvato) and salvato.get("firma") == f
        print("archivio aggiornato" if ok else "archivio da rifare: python3 -m scripts.prepara_avvisi")
        return 0 if ok else 1
    t0 = time.time()
    st = stagione()
    giorni = calcola(st)
    p = salva(giorni, f)
    n = sum(len(x) for x in giorni.values())
    print(f"{len(giorni)} giorni, {n} avvisi in {time.time() - t0:.0f} s → {p}")

    # quanti avvisi «da guardare» all'apertura: gli aperti che chiedono un'azione, fino al giorno prima
    righe = tutte_le_righe(st.al(st.fine))
    presenze = presenze_da(righe)
    partite = list(st.al(st.fine).calendario["data"])
    conti, riassunti = {}, {}
    for d in sorted(giorni):
        prima = pd.Timestamp(d) - pd.Timedelta(days=1)
        lista = con_lo_stato(giorni, prima, partite, {g: {x for x in s if x <= f"{prima:%Y-%m-%d}"} for g, s in presenze.items()})
        aperti = [a for a in lista if a["stato"] == "aperto" and a["categoria"] == "azione"]
        conti[d] = sum(1 for a in aperti if not a["riassunto"])
        riassunti[d] = sum(1 for a in aperti if a["riassunto"])
    for nome, c in (("del giorno", conti), ("della settimana in breve", riassunti)):
        valori = list(c.values())
        print(f"da guardare all'apertura, {nome}: mediana {median(valori)}, massimo {max(valori)} "
              f"({', '.join(d for d, x in c.items() if x == max(valori))}), zero in {valori.count(0)} giorni su {len(valori)}")
    for d in ("2024-04-17", "2024-04-18", "2024-04-19"):
        if d in conti:
            print(f"  apertura del {d}: {conti[d]} del giorno, {riassunti[d]} della settimana in breve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
