"""Demo di M2: cosa vede il motore di Vice in un giorno della stagione.

Uso (nel container):
    python3 -m scripts.demo_motore                          # 18/04/2024, report della seduta
    python3 -m scripts.demo_motore --oggi 2024-01-10 --tipo settimana
    python3 -m scripts.demo_motore --oggi 2024-03-20 --tipo giocatore --giocatore 13
    python3 -m scripts.demo_motore --replica                # verifica contro l'articolo del dataset

Stampa i risultati delle analisi deterministiche (i numeri che in M3 l'agente citerà), gli spunti
e gli avvisi. Nessun LLM: tutto viene dal codice.
"""

from __future__ import annotations

import argparse
import sys
import time

from vice.analysis.comune import NOME_METRICA, UNITA
from vice.analysis.evidenze import con_unita, data_it, giorno_md_it
from vice.analysis.motore import analisi_per_report
from vice.data import zenodo
from vice.config import get_settings
from vice.data.anagrafica import DICITURA, SQUADRA
from vice.data.stagione import stagione
from vice.data.validazione_zenodo import riepilogo


def _m(x, metrica: str) -> str:
    return con_unita(x, UNITA[metrica])


def sedute(n: int) -> str:
    return "1 seduta" if n == 1 else f"{n} sedute"


def titolo(t: str) -> None:
    print(f"\n── {t} " + "─" * max(0, 70 - len(t)))


def stampa(a, oggi) -> None:
    an = a.analisi
    s = an["seduta"].sintesi
    titolo("Seduta di oggi")
    if not s.get("giocatori"):
        print("  " + "; ".join(an["seduta"].avvisi))
    else:
        print(f"  {s['giocatori']} giocatori, {s['tipo']} ({giorno_md_it(s['giorno_md'])}). Percentile mediano della squadra:")
        print("  " + " · ".join(f"{m.upper()} {d['percentile_mediano']}" for m, d in s["per_metrica"].items()))
        if s["fuori_fascia"]:
            print("  Fuori dalla fascia larga (P10-P90):")
            for f in s["fuori_fascia"][:8]:
                print(f"    - {f['giocatore']}: {NOME_METRICA[f['metrica']]} {_m(f['valore'], f['metrica'])}, "
                      f"{f['posizione']} (percentile {f['percentile']})")
        for x in an["seduta"].avvisi:
            print(f"  ! {x}")

    f = an["forma_settimana"].sintesi
    titolo("Forma della settimana")
    if "settimana_dal" in f:
        print(f"  Dalla partita del {data_it(f['settimana_dal'])} a quella del {data_it(f['prossima_partita'])}; "
              f"{f['settimane_di_riferimento']} settimane regolari di riferimento.")
        fuori = f.get("sedute_fuori_curva", [])
        print("  Sedute di squadra fuori dalla curva tipica: " +
              (", ".join(f"{data_it(x['data'])} {x['metrica'].upper()} ({x['gruppo']}) {x['posizione']}" for x in fuori) or "nessuna"))
    for x in an["forma_settimana"].avvisi:
        print(f"  ! {x}")

    e = an["esposizione_velocita"].sintesi
    titolo("Alta velocità da MD-4 a MD-2")
    if "partita" in e:
        stato = "conclusa" if e["finestra_completa"] else "in corso"
        print(f"  Verso la partita del {data_it(e['partita'])}, finestra {stato} ({sedute(e['sedute_squadra'])} della squadra).")
        for x in e.get("sotto_il_solito", [])[:6]:
            extra = f", sprint registrato {x['sprint_registrato']}" if x["sprint_registrato"] else ""
            print(f"    - {x['giocatore']}: sprint {x['spr']} m ({x['spr_posizione']}), HSR {x['hsr']} m ({x['hsr_posizione']}){extra}")

    c = an["compensazione"].sintesi
    titolo("Postpartita (non titolari: HSR rispetto alla somma dei riferimenti)")
    if "partita" in c:
        stato = "aperta" if c["finestra_aperta"] else "chiusa"
        print(f"  Dopo la partita del {data_it(c['partita'])} (finestra {stato}, {sedute(c['sedute_squadra'])} postpartita con dati):")
        print("  " + ", ".join(f"{k}: {n}" for k, n in c["per_esito"].items()))
        for x in c.get("titolari_postpartita_sopra", [])[:4]:
            print(f"    titolare sopra la fascia postpartita: {x['giocatore']} {x['metrica'].upper()} a {giorno_md_it(x['giorno_md'])} ({x['posizione']})")

    if "allenamento_partita" in an:
        p = an["allenamento_partita"].sintesi
        titolo("Allenamento ↔ partita (media da titolare = 100%)")
        print(f"  Allenamenti della settimana finora, mediana della squadra: distanza {p.get('settimana_pct_mediana_td')}%, "
              f"HSR {p.get('settimana_pct_mediana_hsr')}%, sprint {p.get('settimana_pct_mediana_spr')}% di una partita.")

    if "andamento" in an:
        g = an["andamento"].sintesi
        titolo(f"Andamento di {g['giocatore']} (ultime 4 settimane)")
        for m, d in g["per_metrica"].items():
            print(f"    {m.upper()}: {d['descrizione']} (scarto mediano {d['scarto_mediano_pct']}%, percentile {d['percentile_mediano']})")
        for x in an["andamento"].avvisi:
            print(f"  ! {x}")

    if a.qualita:
        titolo("Qualità del dato")
        for q in a.qualita[:8]:
            nelle = "nell'unica seduta" if q["sedute_squadra"] == 1 else f"nelle {q['sedute_squadra']} sedute"
            dati = f"nessun dato {nelle}" if q["sedute"] == 0 else \
                f"dati per {sedute(q['sedute'])} su {q['sedute_squadra']}"
            print(f"  - {q['giocatore']}: {dati} ({q['finestra']})")

    titolo(f"Spunti per lo staff ({len(a.spunti)} su {len(a.candidati)} candidati)")
    for i, sp in enumerate(a.spunti, 1):
        print(f"  {i}. [{sp.regola}] {sp.testo}")
        print(f"     evidenze: {', '.join(sp.evidenze)}")
    if not a.spunti:
        print("  nessuno: niente che le regole segnalino")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--oggi", default="2024-04-18")
    ap.add_argument("--tipo", default="seduta", choices=("seduta", "settimana", "giocatore"))
    ap.add_argument("--giocatore", type=int, default=None, help="id del giocatore nel dataset (1-20)")
    ap.add_argument("--replica", action="store_true", help="verifica contro le tabelle dell'articolo")
    args = ap.parse_args()

    if args.replica:
        r = riepilogo(zenodo.carica(get_settings().processed_dir / "zenodo").carichi)
        titolo("Replica dell'articolo del dataset (Data 2026, 11(4), 84)")
        print(f"  Tabella 1: {r['tabella1_celle_uguali']}/{r['tabella1_celle']} celle identiche")
        print(f"  Tabella 2, distanza: {r['tabella2_td_celle_uguali']}/{r['tabella2_td_celle']} identiche; "
              f"le altre sono il refuso (titolari e non titolari scambiati): {'sì' if r['tabella2_td_refuso_spiegato'] else 'no'}")
        print(f"  Tabella 2, HSR dei difensori centrali: {r['tabella2_hsr_cd_celle_uguali']}/{r['tabella2_hsr_cd_celle']}")
        print("  Denominatore delle colonne RATIO, scarto mediano dalla media da titolare (e dal massimo):")
        for m, d in r["denominatori"].items():
            print(f"    {m.upper()}: {d['scarto_mediano_media_pct']}% (massimo: {d['scarto_mediano_massimo_pct']}%)")
        return 0
    st = stagione()
    v = st.al(args.oggi)
    t0 = time.time()
    a = analisi_per_report(v, args.tipo, args.giocatore)
    dt = time.time() - t0
    print(f"{SQUADRA} · {data_it(v.oggi)} · {giorno_md_it(v.contesto.giorno_md)} · report: {args.tipo}")
    print(f"({DICITURA})")
    stampa(a, v.oggi)
    titolo("Numeri")
    print(f"  {len(a.evidenze())} evidenze citabili, calcolate in {dt:.2f} s; avvertenza fissa: {a.limiti.avvisi[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
