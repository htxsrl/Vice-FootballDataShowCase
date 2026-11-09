"""Genera in anticipo i report della seduta (decisione 49) e li salva in data/processed/report/.

    docker compose exec -T vice python3 -m scripts.prepara_report --prova            # elenca i giorni, nessuna chiamata
    docker compose exec -T vice python3 -m scripts.prepara_report --tetto 4.5        # dal giorno della demo all'indietro
    docker compose exec -T vice python3 -m scripts.prepara_report --giorni 2024-04-18,2024-04-17

Usa il modello vero, quindi **costa**: si lancia solo con l'ok di Ivan. Parte dal giorno della demo e va
all'indietro, un giorno di seduta alla volta (allenamenti e partite), e si ferma prima di superare il tetto
di spesa: i giorni più vecchi restano senza report e nel calendario non hanno il pallino. Salta i giorni che
hanno già il report, salvo `--rifai`.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime

import pandas as pd

from vice.agent import archivio
from vice.agent.contesto import OGGI_PREDEFINITO, Sessione
from vice.agent.report import report
from vice.analysis.evidenze import data_it
from vice.data.caricamenti import codice_dataset

STIMA_INIZIALE = 0.04   # $ a report, finché non ce ne sono di misurati


def titolo(s: Sessione) -> str:
    tipo = "partita" if s.stagione.contesto(s.oggi).giorno_md == 0 else "seduta"
    return f"Report della {tipo} del {data_it(s.oggi)}"


async def uno(giorno: pd.Timestamp) -> dict:
    # come se la seduta fosse stata caricata col file del dataset: serve per il giorno della demo (decisione 54)
    s = Sessione.crea(giorno, caricamento=codice_dataset(giorno))
    esito, fine = None, None
    t0 = time.perf_counter()
    async for ev in report("seduta", s, usa_archivio=False):
        if ev["evento"] == "verifica":
            esito = ev["dati"]
        elif ev["evento"] == "done":
            fine = ev["dati"]
    return {"data": f"{giorno:%Y-%m-%d}", "tipo": "seduta", "titolo": titolo(s), "testo": esito["testo"],
            "frasi_con_numeri": esito["frasi_con_numeri"], "verificate": esito["verificate"], "tolte": esito["tolte"],
            "correzioni": fine.get("correzioni", []), "modello": fine["modello"], "prompt": fine["prompt"],
            "costo": fine.get("costo") or 0.0, "secondi": round(time.perf_counter() - t0, 1),
            "generato_il": datetime.now().isoformat(timespec="seconds")}


def giorni_da_fare(fino_a: pd.Timestamp, dal: pd.Timestamp | None, scelti: list[str] | None, rifai: bool) -> list[pd.Timestamp]:
    st = Sessione.crea(fino_a).stagione
    sedute = sorted((pd.Timestamp(d) for d in st.giorni_di_seduta if pd.Timestamp(d) <= fino_a), reverse=True)
    if dal is not None:
        sedute = [d for d in sedute if d >= dal]
    if scelti:
        voluti = {pd.Timestamp(x) for x in scelti}
        sedute = [d for d in sedute if d in voluti]
    return [d for d in sedute if rifai or archivio.leggi(d) is None]


async def principale(args) -> None:
    fino_a = pd.Timestamp(args.fino_a)
    giorni = giorni_da_fare(fino_a, pd.Timestamp(args.dal) if args.dal else None,
                            args.giorni.split(",") if args.giorni else None, args.rifai)
    print(f"{len(giorni)} giorni senza report, dal {giorni[0]:%d/%m/%Y} all'indietro" if giorni else "nessun giorno da fare")
    if args.prova or not giorni:
        return
    speso, costi, fatti = 0.0, [], 0
    coda = list(giorni)
    sem = asyncio.Semaphore(args.paralleli)

    async def lavora(g: pd.Timestamp) -> None:
        nonlocal speso, fatti
        async with sem:
            try:
                r = await uno(g)
            except Exception as e:   # noqa: BLE001 — un giorno che non riesce non ferma gli altri
                print(f"✗ {g:%d/%m/%Y}: {e}", flush=True)
                return
            archivio.scrivi(g, r)
            speso += r["costo"]
            costi.append(r["costo"])
            fatti += 1
            print(f"✓ {g:%d/%m/%Y}  {r['verificate']}/{r['frasi_con_numeri']} verificate, {len(r['tolte'])} tolte, "
                  f"{r['costo']:.4f} $, {r['secondi']} s  (totale {speso:.2f} $)", flush=True)

    in_corso: set[asyncio.Task] = set()
    while coda:
        stima = sum(costi) / len(costi) if costi else STIMA_INIZIALE
        if speso + stima * (len(in_corso) + 1) > args.tetto:
            print(f"tetto di {args.tetto} $ raggiunto: mi fermo, {len(coda)} giorni restano senza report")
            break
        t = asyncio.create_task(lavora(coda.pop(0)))
        in_corso.add(t)
        t.add_done_callback(in_corso.discard)
        while len(in_corso) >= args.paralleli:
            await asyncio.sleep(0.2)
    if in_corso:
        await asyncio.gather(*in_corso)
    print(f"\n{fatti} report salvati in {archivio.cartella()}, {speso:.2f} $ in tutto")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fino-a", default=OGGI_PREDEFINITO, help="ultimo giorno (AAAA-MM-GG), di default quello della demo")
    ap.add_argument("--dal", help="primo giorno da considerare (AAAA-MM-GG)")
    ap.add_argument("--giorni", help="solo questi giorni, separati da virgole")
    ap.add_argument("--tetto", type=float, default=1.0, help="spesa massima in dollari (default 1)")
    ap.add_argument("--paralleli", type=int, default=3, help="report generati insieme (default 3)")
    ap.add_argument("--rifai", action="store_true", help="rigenera anche i giorni che hanno già il report")
    ap.add_argument("--prova", action="store_true", help="elenca i giorni senza chiamare il modello")
    asyncio.run(principale(ap.parse_args()))


if __name__ == "__main__":
    main()
