"""Stampa il PDF di documentazione (campo 11 del form) da candidatura/documentazione.html.

Si lancia **dal Mac** (serve Chrome con Playwright, come per la prova dell'interfaccia):

    TMPDIR=<cartella temporanea> python3 candidatura/genera_pdf.py

1. avvia il server di prova (`vice-prova`, porta 8743, modello di prova: nessun costo);
2. scatta le schermate dell'app in una cartella temporanea: apertura, «Mostra» sull'avviso di Amato, la domanda
   «Chi è fuori fascia oggi in alta velocità?» con la sua risposta e la citazione dell'HSR di Basile cliccata,
   settimana. La domanda e la risposta sono quelle vere, registrate una volta col modello vero da
   `registra_figura2.py` in `figura2-conversazione.json` e riaperte qui come una conversazione salvata nel browser.
   Nessuna schermata contiene testo scritto dal modello di prova: di quelle risposte si fotografa solo la lavagna;
3. stampa copertina e corpo con Chrome (il corpo con i numeri di pagina) e li unisce;
4. spegne il server e cancella la cartella temporanea.

Esce in candidatura/Vice-documentazione.pdf.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Page, sync_playwright
from pypdf import PdfReader, PdfWriter

CARTELLA = Path(__file__).resolve().parent
RADICE = CARTELLA.parent
USCITA = CARTELLA / "Vice-documentazione.pdf"
FONT = RADICE / "vice" / "static" / "vendor" / "fonts"
FIGURA2 = CARTELLA / "figura2-conversazione.json"   # domanda e risposta vere della Figura 2 (registra_figura2.py)

# il server di prova e gli aiuti della prova dell'interfaccia, senza duplicarli
_spec = importlib.util.spec_from_file_location("prova_interfaccia", RADICE / "scripts" / "prova_interfaccia.py")
prova = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prova)

PIEDE = ('<div style="width:100%; padding:0 19mm; font:7.5pt Helvetica, Arial, sans-serif; color:#6F7A83; '
         'display:flex; justify-content:space-between"><span>Vice · Football Data Showcase 2026</span>'
         '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def senza_fondo(file: Path, margine: int = 24) -> None:
    """Toglie in basso la parte vuota di una schermata (il fondo della lavagna sotto il grafico)."""
    im = Image.open(file).convert("RGB")
    fondo = Image.new("RGB", im.size, im.getpixel((im.width - 2, im.height - 2)))
    box = ImageChops.difference(im, fondo).point(lambda v: 255 if v > 12 else 0).getbbox()
    if box and box[3] + margine < im.height:
        im.crop((0, 0, im.width, box[3] + margine)).save(file, quality=84)


def foto(pg: Page, cartella: Path) -> None:
    """Le schermate dell'app, in JPEG a doppia densità."""
    salva = lambda nome, **k: pg.screenshot(path=str(cartella / f"{nome}.jpg"), type="jpeg", quality=84, **k)   # noqa: E731
    def lavagna(nome: str) -> None:
        f = cartella / f"{nome}.jpg"
        pg.locator("#lavagna").screenshot(path=str(f), type="jpeg", quality=84)
        senza_fondo(f)

    pg.set_viewport_size({"width": 1100, "height": 1000})
    pg.goto(prova.URL)
    pg.wait_for_selector(".benvenuto .punto")
    pg.click(".benvenuto .punto > summary")   # «Da guardare» è chiuso all'apertura (decisione 63): la figura lo mostra aperto
    pg.wait_for_timeout(1200)
    salva("apertura", clip={"x": 120, "y": 64, "width": 860, "height": 780})

    pg.set_viewport_size({"width": 1280, "height": 860})
    pg.locator(".punto .avviso").first.locator("button", has_text="Mostra sulla lavagna").click()
    prova.aspetta_lavagna(pg)
    lavagna("mostra")

    # la seduta di oggi caricata col CSV della demo; poi la domanda vera e la sua risposta (Figura 2), riaperte come una
    # conversazione salvata nel browser: a sinistra la domanda e la risposta, a destra il dato citato acceso
    pg.click("button[data-azione=prova]")
    pg.wait_for_selector("article.report footer", timeout=60000)
    prova.aspetta_lavagna(pg)
    conv = json.loads(FIGURA2.read_text(encoding="utf-8"))
    pg.evaluate("c => { const d = JSON.parse(localStorage.getItem('vice-conversazioni-v1') || '{}'); d[c.id] = c;"
                " localStorage.setItem('vice-conversazioni-v1', JSON.stringify(d)); }", conv)
    pg.set_viewport_size({"width": 1280, "height": 960})   # il grafico intero, con l'asse e il suo nome
    pg.goto(f"{prova.URL}/?c={conv['id']}")
    pg.wait_for_selector("article.msg.vice footer")
    prova.aspetta_lavagna(pg)
    cita = pg.locator("article.msg.vice").last.locator("button.cita[aria-label*='Matteo Basile']").first
    cita.click()
    prova.aspetta_lavagna(pg)
    pg.mouse.move(5, 5)
    pg.wait_for_timeout(500)
    salva("citazione")

    pg.set_viewport_size({"width": 1280, "height": 1100})
    prova.chiedi(pg, "Fammi vedere la settimana sulla lavagna")
    pg.mouse.move(5, 5)
    pg.wait_for_timeout(500)
    lavagna("settimana")


def stampa(browser, html: Path, uscita: Path, copertina: bool) -> None:
    pg = browser.new_page()
    pg.goto(html.as_uri())
    pg.evaluate("document.fonts.ready")
    nascondi = "section.capitolo" if copertina else ".copertina"
    pg.add_style_tag(content=f"{nascondi} {{ display: none !important; }}"
                     + ("" if copertina else " section.capitolo:first-of-type { break-before: auto; }"))
    pg.wait_for_timeout(300)
    pg.pdf(path=str(uscita), format="A4", print_background=True, prefer_css_page_size=True,
           display_header_footer=not copertina, header_template="<span></span>", footer_template=PIEDE)
    pg.close()


def main() -> int:
    prova.avvia_server()
    try:
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            tmp = Path(tmp)
            (tmp / "immagini").mkdir()
            browser = p.chromium.launch(channel="chrome")
            ctx = browser.new_context(device_scale_factor=2)
            foto(ctx.new_page(), tmp / "immagini")
            ctx.close()
            shutil.copy(CARTELLA / "documentazione.html", tmp / "documentazione.html")
            (tmp / "fonts").symlink_to(FONT)
            stampa(browser, tmp / "documentazione.html", tmp / "copertina.pdf", copertina=True)
            stampa(browser, tmp / "documentazione.html", tmp / "corpo.pdf", copertina=False)
            browser.close()
            w = PdfWriter()
            for f in ("copertina.pdf", "corpo.pdf"):
                for pagina in PdfReader(tmp / f).pages:
                    w.add_page(pagina)
            w.add_metadata({"/Title": "Vice, il vice-preparatore AI · Documentazione del progetto",
                            "/Author": "Ivan Buttignon"})
            with open(USCITA, "wb") as f:
                w.write(f)
    finally:
        prova.spegni_server()
    print(f"{USCITA} ({USCITA.stat().st_size / 1e6:.1f} MB, {len(PdfReader(USCITA).pages)} pagine)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
