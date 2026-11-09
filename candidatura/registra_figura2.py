"""Registra la domanda e la risposta della Figura 2 del PDF, col modello vero (costa circa 0,03 $).

Si lancia **dal Mac**, con l'app accesa su http://localhost:8742 (modello vero) e Chrome con Playwright:

    python3 candidatura/registra_figura2.py

Apre Vice come una persona: carica il CSV della demo (il report del 19/04 arriva dai report pronti, gratis), apre una
conversazione nuova e chiede «Chi è fuori fascia oggi in alta velocità?». La conversazione, così come Vice la salva nel
browser (domanda, risposta verificata, evidenze citate, grafico), finisce in `candidatura/figura2-conversazione.json`:
`genera_pdf.py` la riapre sul server di prova a ogni stampa, quindi la figura mostra sempre la stessa risposta vera, senza
nuovi costi. Si rifà solo se cambiano la domanda, il motore o il prompt.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8742"
DOMANDA = "Chi è fuori fascia oggi in alta velocità?"
USCITA = Path(__file__).resolve().parent / "figura2-conversazione.json"


def main() -> None:
    salute = json.loads(urllib.request.urlopen(f"{URL}/api/health", timeout=5).read())
    if salute.get("modello_di_prova"):
        sys.exit("sulla 8742 c'è il modello di prova: per la figura serve il modello vero")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        pg = browser.new_page(viewport={"width": 1280, "height": 860})
        pg.goto(URL)
        pg.wait_for_selector(".benvenuto .punto")
        pg.click("button[data-azione=prova]")
        pg.wait_for_selector("article.report footer", timeout=120000)
        pg.click("#nuova")
        pg.wait_for_selector(".benvenuto")
        pg.fill("#domanda", DOMANDA)
        pg.click("#invia")
        pg.wait_for_function("document.querySelector('article.msg.vice footer') && "
                             "!document.querySelector('article.msg.vice .voce.in-arrivo')", timeout=180000)
        piede = pg.locator("article.msg.vice").last.locator("footer").inner_text()
        m = re.search(r"(\d+) frasi? su (\d+) verificate", piede)
        if not m or m.group(1) != m.group(2) or "tolt" in piede:
            sys.exit(f"risposta non tutta verificata, non la salvo: {piede!r}")
        tutte = json.loads(pg.evaluate("localStorage.getItem('vice-conversazioni-v1')"))
        conv = next(c for c in tutte.values() if any(x.get("testo") == DOMANDA for x in c["messaggi"] if x["tipo"] == "utente"))
        USCITA.write_text(json.dumps(conv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        risposta = next(x for x in conv["messaggi"] if x["tipo"] == "vice")
        print(risposta["testo"])
        print("---", piede.splitlines()[0], "→", USCITA)
        browser.close()


if __name__ == "__main__":
    main()
