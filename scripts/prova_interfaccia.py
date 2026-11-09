"""Prova automatica dell'interfaccia in Chrome, sul copione della demo, senza costi (punto 3 del 25/10/2026).

Si lancia **dal Mac** (serve Chrome con Playwright, che nel container non c'è):

    python3 scripts/prova_interfaccia.py            # avvia il server di prova, prova, lo spegne
    python3 scripts/prova_interfaccia.py --lascia   # lascia acceso il server di prova (http://127.0.0.1:8743)

Avvia un container separato (`vice-prova`, porta 8743) con il **modello di prova** (`VICE_LLM_PROVA=1`,
vice/llm_prova.py): niente chiamate al gateway, e l'app normale sulla 8742 non viene toccata. Poi usa la
pagina come una persona: l'apertura con gli avvisi da guardare e la seduta di oggi da caricare (decisione 54),
il file di prova, il report con gli avvisi in testa, «Mostra», «Chiedi a Vice», «Visto» e il menù «Da guardare»,
domande del copione (wiki/progetto/prova-della-demo.md), grafici, citazioni, sigle spiegate, glossario,
divisore, calendario coi report pronti, conversazioni salvate, file di Zenodo, file modificato, tema scuro,
telefono. Per ogni passo controlla che il grafico sia quello della domanda e che tutte le frasi siano verificate.
Esce con codice 1 se un controllo fallisce.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from vice.agent.sigle import introduci  # noqa: E402 — solo re, nessuna dipendenza
PORTA = 8743
URL = f"http://127.0.0.1:{PORTA}"
CONTAINER = "vice-prova"

# domanda → (inizio del titolo del grafico atteso, None se non deve cambiare grafico)
DOMANDE = [
    ("Chi è fuori fascia oggi nella distanza totale?", "Distanza totale oggi"),
    ("Come sta Cortese?", "Lorenzo Cortese"),
    ("Come sta il numero 9?", "Matteo Basile"),                       # maglia 9 = Basile; codice 9 = Cortese
    ("Com'era la distanza totale di Cortese il 10/04 rispetto a oggi?", "Lorenzo Cortese, distanza totale"),
    ("Quanto della partita abbiamo allenato questa settimana?", "Quanta partita"),
    ("Fammi vedere la settimana sulla lavagna", "La settimana"),
    ("Come fate a sapere che i numeri sono giusti?", "Come sappiamo"),
    ("Qual è il rischio infortuni di Tosi?", None),
]

esiti: list[tuple[bool, str]] = []


def controlla(ok: bool, cosa: str) -> bool:
    esiti.append((bool(ok), cosa))
    print(("✓ " if ok else "✗ ") + cosa, flush=True)
    return bool(ok)


# ---------- il server di prova ----------

def avvia_server() -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], cwd=RADICE, capture_output=True)
    subprocess.run(["docker", "compose", "run", "--rm", "-d", "--name", CONTAINER, "-p", f"127.0.0.1:{PORTA}:8000",
                    "-e", "VICE_LLM_PROVA=1", "vice", "uvicorn", "vice.main:app", "--host", "0.0.0.0", "--port", "8000"],
                   cwd=RADICE, check=True, capture_output=True)
    for _ in range(60):
        try:
            salute = json.loads(urllib.request.urlopen(f"{URL}/api/health", timeout=2).read())
            if not salute.get("modello_di_prova"):
                spegni_server()
                sys.exit("il server sulla porta di prova non usa il modello di prova: mi fermo per non spendere")
            return
        except OSError:
            time.sleep(1)
    spegni_server()
    sys.exit("il server di prova non risponde")


def spegni_server() -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], cwd=RADICE, capture_output=True)


# ---------- aiuti ----------

def chiedi(pg: Page, domanda: str) -> str:
    """Manda una domanda e aspetta la risposta verificata; restituisce il piede della risposta."""
    n = pg.locator("article.msg.vice").count()
    pg.fill("#domanda", domanda)
    pg.click("#invia")
    pg.wait_for_function(f"document.querySelectorAll('article.msg.vice').length > {n} && "
                         "!document.querySelector('article.msg.vice:last-of-type .voce.in-arrivo')", timeout=60000)
    aspetta_lavagna(pg)
    ultimo = pg.locator("article.msg.vice").last
    return ultimo.locator("footer").inner_text() if ultimo.locator("footer").count() else ultimo.inner_text()


def aspetta_lavagna(pg: Page) -> None:
    """Aspetta che il grafico chiesto sia disegnato (la lavagna toglie aria-busy quando ha finito)."""
    pg.wait_for_timeout(300)
    pg.wait_for_function("!document.querySelector('#vista-principale[aria-busy]')", timeout=30000)
    pg.wait_for_timeout(300)


def titolo_lavagna(pg: Page) -> str:
    h = pg.locator("#vista-principale h2")
    return h.inner_text() if h.count() else ""


def tutte_verificate(piede: str) -> bool:
    m = re.search(r"(\d+) frasi? su (\d+) verificate", piede)
    return bool(m) and m.group(1) == m.group(2) and "tolt" not in piede


# ---------- le prove ----------

def conta_avvisi(pg: Page) -> int:
    c = pg.locator("#conta-avvisi")
    return int(c.inner_text()) if c.is_visible() else 0


def prova_apertura_e_avvisi(pg: Page) -> None:
    """Decisione 54: all'apertura quello che resta da guardare e la seduta di oggi da caricare; col file di prova il
    report comincia con gli avvisi nuovi; Mostra, Visto, Chiedi a Vice e il menù «Da guardare»."""
    pg.goto(URL)
    pg.wait_for_selector(".benvenuto .punto")
    benvenuto = pg.inner_text(".benvenuto")
    controlla(pg.locator("#lavagna").is_hidden(), "all'apertura c'è solo la chat")
    controlla("Ciao, sono Vice" in benvenuto and "Leggo i dati GPS" not in benvenuto,
              "il benvenuto: una riga di presentazione, poi gli avvisi al posto del testo descrittivo")
    controlla("seduta di oggi non è ancora caricata" in benvenuto and "seduta da caricare" in pg.inner_text("#giorno-sotto"),
              "la seduta di oggi (19/04) è da caricare")
    controlla(pg.locator(".benvenuto .demo .demo-etichetta").inner_text().strip() == "Demo"
              and pg.evaluate("document.querySelector('.benvenuto .demo').compareDocumentPosition("
                              "document.querySelector('.benvenuto .punto')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0
              and pg.evaluate("document.querySelector('.benvenuto .punto').compareDocumentPosition("
                              "document.querySelector('.benvenuto .domande')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0,
              "apertura: prima la demo (dichiarata), poi «Da guardare», poi le domande d'esempio")
    controlla(pg.locator(".benvenuto details.punto:not([open]) .conta-titolo").inner_text() == "3"
              and pg.locator("#home").is_hidden(),
              "apertura: «Da guardare» chiuso, col numero degli avvisi; niente «Home» sulla pagina iniziale (decisione 63)")
    pg.click(".benvenuto .punto > summary")
    corpo = pg.locator(".benvenuto .punto-corpo")
    pg.wait_for_timeout(200)
    controlla(corpo.evaluate("e => getComputedStyle(e).overflowY") == "auto" and corpo.evaluate("e => e.scrollHeight > e.clientHeight")
              and corpo.evaluate("e => e.getBoundingClientRect().bottom <= document.querySelector('#composer').getBoundingClientRect().top + 1"),
              "aperto, «Da guardare» arriva fino alla casella della domanda e scorre al suo interno, non con la pagina")
    # textContent: dal 09/11/2026 la settimana in breve è chiusa, e inner_text di un elemento non mostrato è vuoto
    nomi = pg.locator(".punto .avviso strong").evaluate_all("els => els.map(e => e.textContent)")
    controlla(sorted(nomi) == ["Lorenzo Cortese", "Riccardo Benedetti", "Simone Amato"] and conta_avvisi(pg) == 3,
              f"da guardare all'apertura: Amato e Benedetti, Cortese nella settimana in breve ({nomi}, {conta_avvisi(pg)} in testata)")
    controlla("Stefano Guidi" in pg.inner_text(".righe-brevi.dato") and "Luca Cerutti" in pg.inner_text(".righe-brevi.buone"),
              "a parte: i dati da verificare e le buone notizie")
    controlla("Stefano Guidi" not in pg.inner_text(".righe-brevi.buone"),
              "Guidi senza dati il 18/04 non è anche tra le buone notizie (08/11/2026)")
    controlla(pg.locator(".punto .avviso").first.evaluate("e => getComputedStyle(e.querySelector('.famiglia')).color")
              != "rgb(179, 38, 30)", "niente rosso negli avvisi del giorno")
    # Mostra: il grafico dell'avviso, con la seduta accesa
    pg.locator(".punto .avviso").first.locator("button", has_text="Mostra sulla lavagna").click()
    aspetta_lavagna(pg)
    controlla(titolo_lavagna(pg).startswith("Simone Amato, sprint"), f"Mostra: il grafico di Amato nello sprint ({titolo_lavagna(pg)})")
    spiegazione = pg.inner_text("#vista-principale .spiegazione")
    controlla("più basso del suo solito" in spiegazione, "Mostra: il grafico dice anche lui «più basso del suo solito» (decisione 55)")
    # Visto: esce dal conto, e il browser se lo ricorda
    pg.locator(".punto .avviso").first.locator("button.visto").click()
    controlla(conta_avvisi(pg) == 2, "Visto: in testata gli avvisi da guardare scendono a 2")
    pg.reload()
    pg.wait_for_selector(".benvenuto .punto")
    pg.click(".benvenuto .punto > summary")
    controlla("Simone Amato" not in pg.inner_text(".punto .avvisi-lista") and conta_avvisi(pg) == 2,
              "Visto: dopo la ricarica Amato non è più da guardare")
    # il file di prova di oggi: il report comincia con gli avvisi nuovi
    pg.click("button[data-azione=prova]")
    pg.wait_for_selector("article.report footer", timeout=60000)
    aspetta_lavagna(pg)
    nota = pg.locator(".nota-chat").last.inner_text()
    controlla("è la seduta di oggi" in nota, f"il file di prova è la seduta di oggi ({nota[:80]}…)")
    riquadro = pg.locator("article.report .da-guardare")
    nuovi = riquadro.locator(".avviso strong").evaluate_all("els => els.map(e => e.textContent)")   # il riquadro è chiuso
    controlla(riquadro.count() == 1 and sorted(nuovi) == ["Christian Porcu", "Matteo Basile", "Riccardo Benedetti"],
              f"il report comincia con gli avvisi di oggi: {nuovi}")
    controlla(riquadro.get_attribute("open") is None and riquadro.locator(".conta-titolo").inner_text() == "3",
              "nel report «Da guardare oggi» è chiuso, col numero: in evidenza resta la sintesi (decisione 63)")
    riquadro.locator("summary").first.click()
    controlla(pg.locator("article.report .voce h4", has_text="Spunti").count() == 0, "il report non ha più la sezione degli spunti")
    controlla(tutte_verificate(pg.locator("article.report footer").inner_text()), "il report del 19/04 è tutto verificato")
    controlla("seduta da caricare" not in pg.inner_text("#giorno-sotto") and conta_avvisi(pg) == 3,
              f"dopo il caricamento: Basile e Porcu da guardare, Benedetti chiuso ({conta_avvisi(pg)} in testata)")
    # il menù «Da guardare»: lo storico col calo di Benedetti chiuso
    pg.click("#apri-avvisi")
    in_alto = pg.inner_text("#avvisi-elenco > section:first-of-type")
    controlla("Matteo Basile" in in_alto and "Simone Amato" not in in_alto,
              "menù: in alto solo il nuovo (Basile sì, Amato già visto no)")
    controlla(pg.locator("#avvisi details.passate").get_attribute("open") is None, "menù: le segnalazioni passate sono chiuse")
    pg.click("#avvisi details.passate > summary")
    pannello = pg.inner_text("#avvisi details.passate")
    controlla("chiuso il 19/04: tornato nel suo solito" in pannello and "Simone Amato" in pannello,
              "menù: nelle segnalazioni passate il calo di Benedetti chiuso e Amato visto")
    pg.keyboard.press("Escape")
    # Chiedi a Vice: la domanda sull'avviso di Basile, in chat
    basile = riquadro.locator(".avviso", has_text="Matteo Basile")
    basile.locator("button", has_text="Chiedi a Vice").click()
    pg.wait_for_function("document.querySelectorAll('article.msg.vice').length > 1 && "
                         "!document.querySelector('article.msg.vice:last-of-type .voce.in-arrivo')", timeout=60000)
    aspetta_lavagna(pg)
    domanda = pg.locator(".msg.utente").last.inner_text()
    piede = pg.locator("article.msg.vice").last.locator("footer").inner_text()
    controlla(domanda.startswith("Spiegami l'avviso su Matteo Basile del 19/04") and titolo_lavagna(pg).startswith("Matteo Basile")
              and tutte_verificate(piede), f"Chiedi a Vice: la domanda su Basile, il suo grafico, frasi verificate ({piede.splitlines()[0]})")


def prova_domande(pg: Page) -> None:
    inizio = pg.locator("article.msg.vice").count()     # prima ci sono il report e la risposta sull'avviso
    for domanda, titolo in DOMANDE:
        prima = titolo_lavagna(pg)
        piede = chiedi(pg, domanda)
        dopo = titolo_lavagna(pg)
        if titolo is None:
            controlla(dopo == prima, f"«{domanda}»: nessun grafico nuovo")
            controlla("oltre ciò che i dati permettono" in pg.locator("article.msg.vice").last.inner_text(), f"«{domanda}»: rifiuta")
            continue
        controlla(dopo.startswith(titolo), f"«{domanda}»: grafico «{dopo}»")
        controlla(tutte_verificate(piede), f"«{domanda}»: tutte le frasi verificate ({piede.splitlines()[0] if piede else '-'})")
        cita = pg.locator("article.msg.vice").last.locator("button.cita").first
        if cita.count():
            cita.click()
            aspetta_lavagna(pg)
            controlla(bool(titolo_lavagna(pg)), f"«{domanda}»: la citazione {cita.inner_text()} porta a un grafico ({titolo_lavagna(pg)})")
            controlla(pg.locator("#vista-principale .prova-citata").count() == 1,
                      f"«{domanda}»: sopra il grafico la prova della citazione {cita.inner_text()}")
    # lavagna → chat: clic su un giocatore della griglia della settimana
    indice = [d for d, _ in DOMANDE].index("Fammi vedere la settimana sulla lavagna")
    pg.locator("article.msg.vice").nth(inizio + indice).locator("button.mostra-vista").click()
    aspetta_lavagna(pg)
    nome = pg.locator(".griglia .nome").first
    if nome.count() and pg.locator(".griglia .cella").count():
        fine_nome = nome.bounding_box()["x"] + nome.bounding_box()["width"]
        distanza = pg.locator(".griglia .cella").first.bounding_box()["x"] - fine_nome
        controlla(distanza < 40, f"griglia: le celle stanno accanto ai nomi ({distanza:.0f} px), non schiacciate in fondo")
        pannello = pg.locator("#vista-principale .pannello").bounding_box()
        ultima = pg.locator(".griglia .cella").last.bounding_box()
        vuoto = pannello["x"] + pannello["width"] - (ultima["x"] + ultima["width"])
        controlla(vuoto < 40, f"griglia: arriva fino al bordo della scheda ({vuoto:.0f} px liberi), niente spazio vuoto")
    if controlla(nome.count() > 0, "la griglia della settimana è sulla lavagna"):
        nome.click()
        controlla(pg.locator("#contesto-lavagna").is_visible(), "clic su un giocatore → «Stai guardando…»")


def prova_glossario(pg: Page) -> None:
    """Il pulsante «i» apre il glossario (una tabella a quattro colonne) accanto alla chat; Esc lo chiude."""
    pg.click("#apri-glossario")
    pannello = pg.locator("#glossario")
    testate = pannello.locator("th").all_inner_texts()
    controlla(pannello.is_visible() and testate == ["Sigla", "Significato", "Unità di misura", "Cosa misura"],
              f"glossario: si apre col pulsante «i», con le quattro colonne {testate}")
    controlla("distanza ad alto carico metabolico" in pannello.inner_text(), "glossario: c'è HMLD col suo significato")
    chat = pg.locator("#domanda").bounding_box()
    controlla(chat["x"] + chat["width"] / 2 < pannello.bounding_box()["x"], "glossario: la chat resta visibile accanto")
    pg.keyboard.press("Escape")
    controlla(pannello.is_hidden() and pg.evaluate("document.activeElement.id") == "apri-glossario",
              "glossario: Esc lo chiude e il fuoco torna al pulsante")


def prova_sigle(pg: Page) -> None:
    """La prima volta una sigla ha il suo significato, poi basta la sigla (decisione 48)."""
    risposte = pg.locator("article.msg.vice .voce").all_inner_texts()
    controlla(bool(risposte) and introduci(risposte[0]) == risposte[0] and "il giorno prima della partita" in risposte[0],
              "sigle: nel report, la prima risposta, ogni sigla ha il suo significato (MD-1 compreso)")
    controlla(all("il giorno prima della partita" not in r for r in risposte[1:4]),
              "sigle: nelle risposte dopo, MD-1 senza la spiegazione")


def prova_resa(pg: Page) -> None:
    """La resa del testo e i suggerimenti (decisione 52): sigle in grassetto, riquadro uguale a quello dei grafici."""
    controlla(pg.locator("article.msg.vice .voce strong.sigla").count() > 0, "resa: le sigle sono in grassetto")
    box = pg.locator("#suggerimento-box")
    pg.locator(".metriche button", has_text="HSR").first.hover()
    pg.wait_for_timeout(200)
    controlla(box.is_visible() and "corsa ad alta velocità" in box.inner_text()
              and pg.locator(".metriche button", has_text="HSR").first.get_attribute("title") is None,
              f"resa: sul bottone HSR il riquadro col significato, non quello del browser ({box.inner_text() if box.is_visible() else '-'})")
    cita = pg.locator("article.msg.vice button.cita").first
    cita.scroll_into_view_if_needed()
    pg.wait_for_timeout(300)
    cita.hover()
    pg.wait_for_timeout(200)
    controlla(box.is_visible() and "clicca per vederlo sulla lavagna" in box.inner_text(), "resa: sulla citazione lo stesso riquadro")
    pg.mouse.move(5, 5)


def prova_divisore(pg: Page) -> None:
    """Il divisore tra chat e lavagna: si trascina, si sposta con le frecce, torna com'era col doppio clic."""
    chat = lambda: round(pg.locator(".chat").bounding_box()["width"])   # noqa: E731
    prima = chat()
    box = pg.locator("#divisore").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(x, y)
    pg.mouse.down()
    pg.mouse.move(x + 180, y, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(300)
    controlla(abs(chat() - (prima + 180)) <= 4, f"divisore: trascinato, la chat passa da {prima} a {chat()} px")
    pg.focus("#divisore")
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(200)
    controlla(abs(chat() - (prima + 180 - 24)) <= 4, "divisore: la freccia a sinistra stringe la chat")
    pg.dblclick("#divisore")
    pg.wait_for_timeout(300)
    controlla(abs(chat() - prima) <= 4, "divisore: il doppio clic la riporta com'era")


def prova_calendario(pg: Page) -> None:
    """Il calendario (decisioni 47 e 49): i giorni col pallino portano al report di Vice, gli altri all'invito a
    caricare l'export; le domande senza data riguardano il giorno scelto."""
    pg.click("#apri-calendario")
    pallini = pg.eval_on_selector_all(".cal-giorno.con-report", "els => els.map(e => e.dataset.giorno)")
    oggi = pg.get_attribute(".cal-giorno.oggi", "data-giorno")
    passati = [g for g in pallini if g < oggi]
    if not controlla(bool(passati), f"calendario: {len(pallini)} giorni col pallino del report"):
        return
    giorno = passati[-1]
    gg = f"{giorno[8:10]}/{giorno[5:7]}"
    n_conv = len(json.loads(pg.evaluate("localStorage.getItem('vice-conversazioni-v1') || '{}'")))
    pg.click(f".cal-giorno[data-giorno='{giorno}']")
    pg.wait_for_function("document.querySelector('article.msg.vice.report footer')", timeout=60000)
    aspetta_lavagna(pg)
    piede = pg.locator("article.msg.vice.report footer").inner_text()
    controlla(tutte_verificate(piede), f"calendario: il report del {gg} è pronto e verificato ({piede.splitlines()[0]})")
    controlla(pg.locator("article.msg.vice.report .da-guardare").count() == 1
              and pg.locator("article.msg.vice.report .voce h4", has_text="Spunti").count() == 0,
              f"calendario: il report del {gg} comincia con i suoi avvisi, senza la sezione degli spunti")
    controlla("giorno in esame" in pg.inner_text("#giorno-sotto"), "calendario: la testata dice che è il giorno in esame")
    controlla(gg in titolo_lavagna(pg), f"calendario: la lavagna mostra il {gg} ({titolo_lavagna(pg)})")
    chiedi(pg, "Chi era fuori fascia quel giorno?")
    controlla(gg in titolo_lavagna(pg), f"calendario: una domanda senza data riguarda il {gg} ({titolo_lavagna(pg)})")
    # lo stesso giorno, di nuovo dal calendario: si riapre la stessa conversazione
    pg.click("#apri-calendario")
    pg.click(f".cal-giorno[data-giorno='{giorno}']")
    pg.wait_for_timeout(1200)
    n_dopo = len(json.loads(pg.evaluate("localStorage.getItem('vice-conversazioni-v1') || '{}'")))
    controlla(n_dopo == n_conv + 1 and pg.locator("article.msg.vice").count() == 2,
              "calendario: lo stesso giorno riapre la sua conversazione")
    # un giorno passato senza report: l'invito a caricare l'export
    pg.click("#apri-calendario")
    vuoto = pg.evaluate(f"[...document.querySelectorAll('.cal-giorno:not(.con-report):not([disabled])')]"
                        f".map(e => e.dataset.giorno).filter(g => g < '{oggi}').pop()")
    pg.click(f".cal-giorno[data-giorno='{vuoto}']")
    pg.wait_for_timeout(1200)
    avviso = pg.locator(".avviso-giorno")
    controlla(avviso.count() == 1 and "Non hai caricato alcun dato" in avviso.inner_text(),
              f"calendario: il {vuoto[8:10]}/{vuoto[5:7]} senza report invita a caricare l'export")


def prova_conversazioni(pg: Page) -> None:
    n = pg.locator("#messaggi .msg").count()
    pg.reload()
    pg.wait_for_timeout(1500)
    aspetta_lavagna(pg)
    controlla(pg.locator("#messaggi .msg").count() == n, f"dopo la ricarica la conversazione resta ({n} messaggi)")
    controlla(bool(titolo_lavagna(pg)), "dopo la ricarica torna l'ultimo grafico")
    pg.click("#apri-giorni")
    titoli = pg.locator("button.conversazione").all_inner_texts()
    controlla(any(t.startswith("Report della seduta del 19/04/2024") for t in titoli), "la conversazione è nell'elenco col suo titolo")
    pg.click("#chiudi-giorni")
    # «Home» (decisione 63): con chat e grafico riporta alla pagina iniziale di oggi, senza cancellare niente
    controlla(pg.locator("#home").is_visible(), "con chat e grafico c'è il bottone «Home»")
    pg.click("#home")
    pg.wait_for_timeout(800)
    controlla(pg.locator(".benvenuto").count() == 1 and pg.locator("#lavagna").is_hidden() and pg.locator("#home").is_hidden(),
              "«Home» riporta alla pagina iniziale di oggi, solo chat, e il bottone sparisce")
    pg.click("#apri-giorni")
    controlla(pg.locator("button.conversazione").count() == len(titoli), "«Home» non cancella le conversazioni")
    pg.click("#chiudi-giorni")
    pg.click("#nuova")
    pg.wait_for_timeout(800)
    controlla(pg.locator(".benvenuto").count() == 1 and pg.locator("#lavagna").is_hidden(), "«Nuova» apre una conversazione vuota, solo chat")
    controlla(pg.locator(".benvenuto .carica-oggi").count() == 0 and pg.locator(".benvenuto [data-report]").count() == 1,
              "con la seduta di oggi caricata, niente invito a caricarla e c'è il report di oggi")
    pg.click("#apri-giorni")
    controlla(pg.locator("button.conversazione").count() == len(titoli), "la conversazione nuova non cancella le vecchie")
    pg.click("#chiudi-giorni")


def prova_file(pg: Page, cartella: Path) -> None:
    with pg.expect_download() as d:
        pg.click("a.prova")
    file = cartella / d.value.suggested_filename
    d.value.save_as(file)
    controlla(file.read_text().startswith("FECHA;PlayerID"), f"il file di prova viene da Zenodo ({file.name})")
    pg.set_input_files("#file-export", str(file))
    pg.wait_for_selector("article.report footer", timeout=60000)
    aspetta_lavagna(pg)
    nota = pg.locator(".nota-chat").last.inner_text()
    controlla("righe originali del dataset Zenodo" in nota and "è la seduta di oggi" in nota, "Vice dice cosa ha letto: la seduta di oggi")
    controlla(tutte_verificate(pg.locator("article.report footer").inner_text()), "il report automatico è tutto verificato")
    controlla(titolo_lavagna(pg).endswith("rispetto alla fascia di ciascuno"), f"col report, la seduta sulla lavagna ({titolo_lavagna(pg)})")
    controlla(pg.locator("article.report .linguaggi").count() == 0, "un solo report, senza la scelta del linguaggio (decisione 51)")

    # il file modificato: Cortese (codice 9) a 300 m di alta velocità (19/04/2024 è il seriale 45401 di Excel)
    righe = file.read_text().splitlines()
    for i, r in enumerate(righe):
        campi = r.split(";")
        if campi[:2] == ["45401", "9"]:
            controlla(campi[10] != "300", f"nel file Cortese ha {campi[10]} m di alta velocità")
            campi[10] = "300"
            righe[i] = ";".join(campi)
    modificato = cartella / "zenodo-modificato.csv"
    modificato.write_text("\r\n".join(righe) + "\r\n")
    pg.click("#nuova")
    pg.wait_for_timeout(600)
    pg.set_input_files("#file-export", str(modificato))
    pg.wait_for_selector("article.report footer", timeout=60000)
    controlla("1 valore è diverso" in pg.locator(".nota-chat").last.inner_text(), "Vice si accorge del valore cambiato")
    chiedi(pg, "Cortese è ancora fuori fascia in alta velocità?")
    etichetta = pg.locator("#vista-principale .grafico").get_attribute("aria-label") or ""
    controlla("19/04 300 m" in etichetta, "il grafico usa il numero del file: Cortese 300 m")

    pg.set_input_files("#file-export", str(RADICE / "README.md"))
    pg.wait_for_timeout(1500)
    controlla("Non posso usare README.md" in pg.locator(".nota-chat").last.inner_text(), "un file sbagliato dà un errore chiaro")


def prova_tema_e_telefono(browser) -> None:
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    errori = []
    pg.on("pageerror", lambda e: errori.append(str(e)))
    pg.goto(URL + "?tema=scuro")
    pg.wait_for_selector(".benvenuto .punto")
    controlla(pg.locator("#conta-avvisi").is_visible() and pg.evaluate("document.documentElement.scrollWidth") <= 390,
              "telefono: in testata il numero degli avvisi, e l'apertura senza scorrimento orizzontale")
    pg.click("#apri-avvisi")
    controlla(pg.locator("#avvisi").is_visible() and pg.evaluate("document.documentElement.scrollWidth") <= 390,
              "telefono: il menù «Da guardare» si apre senza scorrimento orizzontale")
    pg.click("#chiudi-avvisi")
    chiedi(pg, "Come sta Cortese?")
    controlla(titolo_lavagna(pg).startswith("Lorenzo Cortese"), "telefono, tema scuro: grafico giusto")
    controlla(pg.evaluate("document.documentElement.scrollWidth") <= 390, "telefono: nessuno scorrimento orizzontale")
    pg.click("#apri-glossario")
    controlla(pg.locator("#glossario").is_visible() and pg.evaluate("document.documentElement.scrollWidth") <= 390,
              "telefono: il glossario si apre senza scorrimento orizzontale")
    pg.click("#chiudi-glossario")
    pg.click("#apri-calendario")
    controlla(pg.locator("#calendario").is_visible() and pg.evaluate("document.documentElement.scrollWidth") <= 390,
              "telefono: il calendario si apre senza scorrimento orizzontale")
    pg.click("#chiudi-calendario")
    controlla(not errori, f"telefono: nessun errore nella pagina {errori[:1]}")
    pg.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lascia", action="store_true", help="lascia acceso il server di prova")
    args = ap.parse_args()
    avvia_server()
    try:
        with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
            browser = p.chromium.launch(channel="chrome")
            ctx = browser.new_context(viewport={"width": 1440, "height": 950}, accept_downloads=True)
            pg = ctx.new_page()
            errori = []
            pg.on("pageerror", lambda e: errori.append(str(e)))
            # risposte del server con errore; l'unico atteso è il rifiuto del file sbagliato (/api/carica, 422)
            pg.on("response", lambda r: errori.append(f"{r.status} {r.url}") if r.status >= 400
                  and not (r.url.endswith("/api/carica") and r.status == 422) else None)
            prova_apertura_e_avvisi(pg)
            prova_domande(pg)
            prova_sigle(pg)
            prova_resa(pg)
            prova_glossario(pg)
            prova_divisore(pg)
            prova_conversazioni(pg)
            prova_file(pg, Path(tmp))
            prova_calendario(pg)
            controlla(not errori, f"nessun errore nella pagina {errori[:2]}")
            prova_tema_e_telefono(browser)
            browser.close()
    finally:
        if not args.lascia:
            spegni_server()
    falliti = [c for ok, c in esiti if not ok]
    print(f"\n{len(esiti) - len(falliti)} controlli su {len(esiti)} superati")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
