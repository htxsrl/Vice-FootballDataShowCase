"""Prova l'agente o un report dal terminale, con il modello vero (costa: vedi il costo in fondo).

Uso (nel container):
    python3 -m scripts.prova_agente "Com'è andata la seduta di oggi?"
    python3 -m scripts.prova_agente --oggi 2024-01-10 "Chi è fuori fascia?"
    python3 -m scripts.prova_agente --report seduta
    python3 -m scripts.prova_agente --report giocatore --giocatore Santini
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from vice.agent import agente
from vice.agent import report as reportistica
from vice.agent.contesto import Sessione


async def esegui(args) -> int:
    s = Sessione.crea(args.oggi)
    t0 = time.time()
    if args.report:
        gen = reportistica.report(args.report, s, args.giocatore, modello=args.modello)
    else:
        gen = agente.turno([{"role": "user", "content": args.domanda}], s, modello=args.modello)
    ver, done = None, None
    async for ev in gen:
        if ev["evento"] == "tappa":
            print(f"  · {ev['dati']['testo']}", flush=True)
        elif ev["evento"] == "vista":
            print(f"  · vista: {ev['dati']}")
        elif ev["evento"] == "verifica":
            ver = ev["dati"]
        elif ev["evento"] == "done":
            done = ev["dati"]
    print("\n" + ver["testo"] + "\n")
    print(f"{ver['badge']}" + (f" | tolte: {ver['tolte']}" if ver["tolte"] else ""))
    print(f"{', '.join(done['modelli_usati'])} · {done['chiamate']} chiamate · {done['token_ingresso']} + {done['token_uscita']} token · "
          f"{done['costo']} $ · {time.time() - t0:.1f} s · prompt {done['prompt']}")
    if done.get("strumenti"):
        print("strumenti: " + ", ".join(f"{x['nome']}{x['argomenti'] if x['argomenti'] != '{}' else ''}"
                                        + (f" (errore: {x['errore']})" if x["errore"] else "") for x in done["strumenti"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("domanda", nargs="?", default="Com'è andata la seduta di oggi?")
    ap.add_argument("--oggi", default=None)
    ap.add_argument("--report", choices=reportistica.TIPI)
    ap.add_argument("--giocatore")
    ap.add_argument("--modello", default=None)
    return asyncio.run(esegui(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
