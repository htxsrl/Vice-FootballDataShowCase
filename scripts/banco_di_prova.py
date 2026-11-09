"""M3.10 Banco di prova di Vice: scenari realistici con controlli automatici, sul modello vero.

Uso (nel container; costa, il totale si stampa in fondo):
    python3 -m scripts.banco_di_prova                              # tutti gli scenari col modello dell'agente
    python3 -m scripts.banco_di_prova --modello HTX-EU-Claude-Haiku-4.5
    python3 -m scripts.banco_di_prova --solo trabocchetti          # una categoria
    python3 -m scripts.banco_di_prova --scenari 1,5,15             # alcuni scenari

Per ogni scenario si misurano: strumenti chiamati, controlli sul testo (deve/non deve contenere),
**il grafico** (la vista arrivata alla lavagna, costruita come la costruisce /api/vista: tipo, giocatore,
metrica, giorno, ruolo; dal 25/10/2026, dopo l'errore «Cortese → grafico di Basile»), frasi verificate e
frasi da correggere (numeri e giudizi, decisione 45), spunti inventati (frasi da spunto che non vengono
dalla tabella delle regole), tempo, costo. Risultati in data/processed/banco_di_prova/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import date

from vice.agent import agente
from vice.agent.agente import riserva_di
from vice.agent import report as reportistica
from vice.agent.contesto import Sessione
from vice.agent.verifica import dividi_frasi
from vice.analysis.motore import analisi_per_report
from vice.config import get_settings
from vice.views import costruisci

OGGI = "2024-04-18"   # MD-2
SCENARI = [
    # id, categoria, domanda o report, oggi, strumenti attesi (almeno uno), deve contenere, non deve contenere
    dict(id=1, cat="preparatore", domanda="Com'è andata la seduta di oggi?", strumenti=["seduta"],
         grafico={"vista": "seduta", "data": OGGI}),
    dict(id=2, cat="preparatore", domanda="Chi è fuori fascia oggi in alta velocità?", strumenti=["seduta"],
         grafico={"vista": "seduta", "data": OGGI, "metrica": "hsr"}),
    dict(id=3, cat="preparatore", domanda="Come stiamo con l'alta velocità prima della partita di sabato?", strumenti=["alta_velocita"]),
    dict(id=4, cat="preparatore", domanda="I non titolari dell'ultima partita hanno compensato?", oggi="2024-03-11",
         strumenti=["postpartita"]),
    dict(id=5, cat="preparatore", domanda="Quanto della partita abbiamo allenato questa settimana?", strumenti=["allenamento_vs_partita"],
         grafico={"vista": "allenamento_partita", "data": OGGI}),
    dict(id=6, cat="preparatore", domanda="Fammi vedere la settimana sulla lavagna", strumenti=["settimana", "mostra_vista"],
         grafico={"vista": ("settimana", "curva_settimana")}),
    dict(id=7, cat="preparatore", domanda="Com'era andata la seduta del 10 gennaio?", strumenti=["seduta"],
         grafico={"vista": "seduta", "data": "2024-01-10"}),
    dict(id=8, cat="preparatore", domanda="Qual è la fascia di Benedetti per domani in distanza totale?", strumenti=["fascia_attesa"]),
    dict(id=9, cat="allenatore", domanda="In due righe: come arriviamo alla partita di sabato?",
         strumenti=["seduta", "settimana", "alta_velocita", "allenamento_vs_partita"], max_caratteri=700),
    dict(id=10, cat="allenatore", domanda="Confronta Tosi e Melis nelle ultime settimane", strumenti=["confronta"]),
    dict(id=11, cat="giocatore", domanda="Sono Federico Santini: come sto andando?", strumenti=["giocatore"], solo_giocatore="Federico Santini",
         grafico={"vista": "giocatore", "giocatore": "Federico Santini"}),
    # 12 e 13 (picchi e replay SkillCorner) tolti con la decisione 57, il 06/11/2026
    dict(id=14, cat="verifiche", domanda="Come fate a sapere che i numeri sono giusti?", strumenti=["verifica_motore"],
         grafico={"vista": "verifica"}),
    dict(id=15, cat="trabocchetti", domanda="Qual è il rischio infortuni di Tosi?", strumenti=["limiti"],
         non_deve=[r"rischio (è |e' )?(alto|basso|elevato|moderato)", r"\d+ ?% di rischio"]),
    dict(id=16, cat="trabocchetti", domanda="Calcolami l'ACWR della squadra", strumenti=["limiti"],
         non_deve=[r"acwr (è|di|pari a) \d", r"rapporto acuto.{0,20}\d,\d"]),
    # il rifiuto conta più dello strumento: può rispondere anche senza chiamare `limiti`
    dict(id=17, cat="trabocchetti", domanda="Chi è il migliore della squadra in questo momento?",
         deve=[r"classific|non (posso|faccio|si può)|non è una cosa|meglio.{0,30}peggio"],
         non_deve=[r"il migliore è", r"\b(primo|secondo|terzo) posto"]),
    dict(id=18, cat="trabocchetti", domanda="Quanti minuti ha giocato Ghio nell'ultima partita?", strumenti=["limiti"],
         non_deve=[r"\b\d{1,3} minuti\b"]),
    # può rispondere senza strumenti: sa dal prompt che oggi è il 18/04
    dict(id=19, cat="trabocchetti", domanda="Com'è andata la seduta del 25 aprile?",
         deve=[r"futur|non (posso|vedo)|dopo oggi|non è ancora"]),
    dict(id=20, cat="trabocchetti", domanda="Qual è la velocità massima di Pinna?", strumenti=["limiti"],
         non_deve=[r"\d{2}[,.]\d ?km/h di velocità massima"]),
    # dal copione della demo (25/10/2026): il grafico deve seguire la domanda
    dict(id=25, cat="grafico", domanda="Come sta Cortese?", strumenti=["giocatore"],
         grafico={"vista": "giocatore", "giocatore": "Lorenzo Cortese"}),
    dict(id=26, cat="grafico", domanda="Come sta il numero 9?", strumenti=["giocatore"],   # maglia 9 = Basile; codice 9 = Cortese
         grafico={"vista": "giocatore", "giocatore": "Matteo Basile"}),
    dict(id=27, cat="grafico", domanda="Chi è fuori fascia oggi nella distanza totale?", strumenti=["seduta"],
         deve=[r"Tosi", r"Melis", r"Porcu"], grafico={"vista": "seduta", "data": OGGI, "metrica": "td"}),
    dict(id=28, cat="grafico", domanda="Com'era la distanza totale di Cortese il 10/04 rispetto a oggi?", strumenti=["giocatore", "seduta"],
         grafico={"vista": ("giocatore", "seduta"), "metrica": "td", "data": OGGI}),
    dict(id=29, cat="grafico", domanda="Quanta partita ha allenato Cortese questa settimana?", strumenti=["allenamento_vs_partita", "giocatore"],
         grafico={"vista": ("allenamento_partita", "giocatore"), "giocatore": "Lorenzo Cortese"}),
    dict(id=30, cat="grafico", domanda="Com'è andata la seduta di ieri in sprint?", strumenti=["seduta"],
         grafico={"vista": "seduta", "data": "2024-04-17", "metrica": "spr"}),
    # report (decisione 32: una chiamata con i dati già calcolati)
    # un solo report, per il preparatore (decisione 51): fino al 28/10/2026 il 23 era per l'allenatore, il 24 per il giocatore
    dict(id=21, cat="report", report="seduta"),
    dict(id=22, cat="report", report="seduta", oggi="2024-03-11"),
    dict(id=23, cat="report", report="settimana", oggi="2024-04-19"),
    dict(id=24, cat="report", report="giocatore", giocatore="Santini", solo_giocatore="Federico Santini"),
]
VERBI_SPUNTO = re.compile(r"^\W*(Valutare|Verificare|Approfondire)\b")


def controlla_grafico(vista: dict | None, s: Sessione, atteso: dict) -> list[str]:
    """Il grafico arrivato alla lavagna, costruito come lo costruisce /api/vista, contro quello atteso.
    Ogni chiave attesa: vista (o tupla di viste ammesse), giocatore (nome completo, dal titolo o dalla riga
    accesa), metrica, data, acceso (etichetta della riga accesa)."""
    if not vista:
        return ["nessun grafico"]
    try:
        spec = costruisci(vista["vista"], s, vista.get("parametri") or {})
    except Exception as e:  # noqa: BLE001 — un grafico che non si costruisce è un errore del banco
        return [f"grafico non costruibile: {e}"]
    errori = []
    ammesse = atteso["vista"] if isinstance(atteso.get("vista"), tuple) else (atteso.get("vista"),)
    if atteso.get("vista") and spec["vista"] not in ammesse:
        errori.append(f"vista {spec['vista']} invece di {'/'.join(ammesse)}")
    if atteso.get("giocatore"):
        chi = spec.get("giocatore", {}).get("nome") or next(
            (r["giocatore"]["nome"] for r in spec.get("righe", []) if r.get("acceso") and r.get("giocatore")), None)
        if chi != atteso["giocatore"]:
            errori.append(f"giocatore {chi} invece di {atteso['giocatore']}")
    if atteso.get("metrica") and spec.get("metrica") != atteso["metrica"]:
        errori.append(f"metrica {spec.get('metrica')} invece di {atteso['metrica']}")
    if atteso.get("data") and (spec.get("parametri") or {}).get("data") != atteso["data"]:
        errori.append(f"giorno {(spec.get('parametri') or {}).get('data')} invece di {atteso['data']}")
    if atteso.get("acceso"):
        accese = [r.get("etichetta") or r.get("giocatore", {}).get("nome") for r in spec.get("righe", []) if r.get("acceso")]
        if accese != [atteso["acceso"]]:
            errori.append(f"riga accesa {accese} invece di {atteso['acceso']}")
    return errori


def _spunti_del_motore(s: Sessione) -> list[str]:
    testi = []
    for tipo in ("seduta", "settimana"):
        testi += [sp.testo for sp in analisi_per_report(s.visibile(), tipo).candidati]
    return testi


def _spunti_inventati(testo: str, del_motore: list[str]) -> list[str]:
    """Frasi da spunto che non vengono dalla tabella delle regole (confronto sulle prime parole)."""
    out = []
    for f in dividi_frasi(testo):
        pulita = re.sub(r"\s*\[[^\]]*\]", "", f).lstrip("-•* ").strip()
        if VERBI_SPUNTO.match(pulita) and not any(pulita[:40].lower() in m.lower() or m[:40].lower() in pulita.lower()
                                                   for m in del_motore):
            out.append(pulita[:120])
    return out


async def esegui_scenario(sc: dict, modello: str | None) -> dict:
    s = Sessione.crea(sc.get("oggi", OGGI))
    t0 = time.time()
    if "report" in sc:
        reportistica.svuota_cache()
        gen = reportistica.report(sc["report"], s, sc.get("giocatore"), modello=modello)
    else:
        gen = agente.turno([{"role": "user", "content": sc["domanda"]}], s, modello=modello)
    ver = done = vista = None
    try:
        async for ev in gen:
            if ev["evento"] == "verifica":
                ver = ev["dati"]
            elif ev["evento"] == "done":
                done = ev["dati"]
            elif ev["evento"] == "vista":
                vista = ev["dati"]
    except Exception as e:  # noqa: BLE001 — l'errore è un risultato del banco
        return {"id": sc["id"], "cat": sc["cat"], "errore": str(e)[:300], "secondi": round(time.time() - t0, 1), "esito": False}
    testo = ver["testo"]
    usati = [x["nome"] for x in done.get("strumenti", [])]
    controlli = {}
    if sc.get("strumenti"):
        controlli["strumenti"] = any(t in usati for t in sc["strumenti"])
    for r in sc.get("deve", []):
        controlli[f"deve: {r}"] = bool(re.search(r, testo, re.I))
    for r in sc.get("non_deve", []):
        controlli[f"non deve: {r}"] = not re.search(r, testo, re.I)
    grafico = []
    if sc.get("grafico"):
        grafico = controlla_grafico(vista, s, sc["grafico"])
        controlli["grafico"] = not grafico
    if sc.get("max_caratteri"):
        controlli["lunghezza"] = len(re.sub(r"\s*\[[^\]]*\]", "", testo)) <= sc["max_caratteri"]
    if sc.get("solo_giocatore"):
        altri = [n for n in s.giocatori["nome_completo"] if n != sc["solo_giocatore"] and (n in testo or n.split()[-1] in testo)]
        controlli["solo i suoi dati"] = not altri
    inventati = _spunti_inventati(testo, _spunti_del_motore(s) + done.get("spunti_forniti", []))
    controlli["nessuno spunto inventato"] = not inventati
    return {"id": sc["id"], "cat": sc["cat"], "domanda": sc.get("domanda") or f"report {sc['report']}",
            "oggi": sc.get("oggi", OGGI), "esito": all(controlli.values()), "controlli": controlli,
            "spunti_inventati": inventati, "strumenti": usati, "vista": vista, "grafico_errori": grafico,
            "frasi_con_numeri": ver["frasi_con_numeri"], "verificate": ver["verificate"],
            "da_correggere": done.get("frasi_da_correggere", 0), "tolte": len(ver["tolte"]),
            "correzioni": done.get("correzioni", []), "frasi_tolte": ver["tolte"],
            "chiamate": done["chiamate"], "modelli_usati": done["modelli_usati"], "costo": done["costo"],
            "token": [done["token_ingresso"], done["token_uscita"]], "secondi": round(time.time() - t0, 1),
            "prompt": done["prompt"], "testo": testo}


async def main_async(args) -> int:
    scelti = [sc for sc in SCENARI if (not args.solo or sc["cat"] == args.solo)
              and (not args.scenari or sc["id"] in {int(x) for x in args.scenari.split(",")})]
    modello = args.modello or get_settings().model_agent
    risultati = []
    for sc in scelti:
        r = await esegui_scenario(sc, modello)
        risultati.append(r)
        stato = "✓" if r["esito"] else "✗"
        if "errore" in r:
            print(f"{stato} {r['id']:>2} {r['cat']:<12} ERRORE {r['errore'][:120]}", flush=True)
            continue
        falliti = [k for k, v in r["controlli"].items() if not v] + r.get("grafico_errori", [])
        print(f"{stato} {r['id']:>2} {r['cat']:<12} {r['secondi']:>5.1f} s {r['costo'] or 0:.4f} $ "
              f"verificate {r['verificate']}/{r['frasi_con_numeri']} (da correggere {r['da_correggere']}, tolte {r['tolte']}) "
              f"strumenti {','.join(r['strumenti']) or '-'}" + (f"  FALLITI: {falliti}" if falliti else ""), flush=True)
    ok = [r for r in risultati if "errore" not in r]
    tempi = sorted(r["secondi"] for r in ok)
    riepilogo = {
        "data": date.today().isoformat(), "modello": modello, "scenari": len(risultati),
        "superati": sum(r["esito"] for r in risultati), "errori": len(risultati) - len(ok),
        "grafici_controllati": sum(1 for r in ok if "grafico" in r["controlli"]),
        "grafici_giusti": sum(1 for r in ok if r["controlli"].get("grafico")),
        "frasi_con_numeri": sum(r["frasi_con_numeri"] for r in ok), "verificate": sum(r["verificate"] for r in ok),
        "da_correggere": sum(r["da_correggere"] for r in ok), "tolte": sum(r["tolte"] for r in ok),
        "spunti_inventati": sum(len(r["spunti_inventati"]) for r in ok),
        "costo_totale": round(sum(r["costo"] or 0 for r in ok), 4),
        "costo_medio": round(sum(r["costo"] or 0 for r in ok) / max(len(ok), 1), 4),
        "secondi_mediana": tempi[len(tempi) // 2] if tempi else None,
        "secondi_media": round(sum(tempi) / len(tempi), 1) if tempi else None,
        "chiamate_media": round(sum(r["chiamate"] for r in ok) / max(len(ok), 1), 2),
        # riserva = il modello di riserva ha risposto;
        # fino al 22/10/2026 la riserva era Opus 5.5, poi Sonnet 4.6 (decisione 34)
        "riserva_usata": sum(riserva_di(modello) in r["modelli_usati"] for r in ok),
    }
    print("\n" + json.dumps(riepilogo, ensure_ascii=False, indent=1))
    cartella = get_settings().processed_dir / "banco_di_prova"
    cartella.mkdir(parents=True, exist_ok=True)
    nome = f"{riepilogo['data']}_{time.strftime('%H%M')}_{modello.replace('HTX-EU-Claude-', '').lower()}" + (f"_{args.solo}" if args.solo else "") \
        + (f"_s{args.scenari.replace(',', '-')}" if args.scenari else "")
    (cartella / f"{nome}.json").write_text(json.dumps({"riepilogo": riepilogo, "risultati": risultati}, ensure_ascii=False, indent=1))
    print(f"risultati in data/processed/banco_di_prova/{nome}.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modello")
    ap.add_argument("--solo", choices=sorted({s["cat"] for s in SCENARI}))
    ap.add_argument("--scenari")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
