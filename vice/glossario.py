"""Il glossario dell'app (decisione 46): la parte di wiki/metodi/glossario.md tra i due segni `glossario-app`,
trasformata in HTML per il pannello «i».

Una sola fonte: la pagina della wiki. Nel container la cartella wiki/ è montata in sola lettura e
l'immagine contiene solo questo file (Dockerfile). Il Markdown della parte per l'app è volutamente
poco: titoli, paragrafi, elenchi a un livello, tabelle, blocchi di codice, grassetto, corsivo e
codice in linea; un eventuale link diventa testo, perché porterebbe a una pagina della wiki.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "wiki" / "metodi" / "glossario.md"
INIZIO = "<!-- glossario-app: inizio -->"
FINE = "<!-- glossario-app: fine -->"


@dataclass(frozen=True)
class Glossario:
    html: str
    sezioni: list[tuple[str, str]]   # (id, titolo) per l'indice del pannello


def parte_app(md: str) -> str:
    """Il testo tra i due segni; errore se mancano o sono nell'ordine sbagliato."""
    i, f = md.find(INIZIO), md.find(FINE)
    if i < 0 or f < i:
        raise ValueError("glossario: mancano i segni della parte per l'app")
    return md[i + len(INIZIO):f]


def _in_linea(testo: str) -> str:
    pezzi = re.split(r"(`[^`]+`)", testo)            # il codice in linea resta com'è
    out = []
    for p in pezzi:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{escape(p[1:-1])}</code>")
            continue
        h = escape(p, quote=False)
        h = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", h)                       # link → testo
        h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
        h = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", h)
        out.append(h)
    return "".join(out)


def _celle(riga: str) -> list[str]:
    return [c.strip() for c in riga.strip().strip("|").split("|")]


def _id(titolo: str, usati: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", titolo.lower().replace("à", "a").replace("è", "e")).strip("-") or "sezione"
    tid, n = f"gl-{base}", 2
    while tid in usati:
        tid, n = f"gl-{base}-{n}", n + 1
    usati.add(tid)
    return tid


def in_html(md: str) -> Glossario:
    out: list[str] = []
    sezioni: list[tuple[str, str]] = []
    usati: set[str] = set()
    par: list[str] = []
    lista: list[str] = []
    righe = md.split("\n")

    def chiudi() -> None:
        if par:
            out.append(f"<p>{_in_linea(' '.join(par))}</p>")
            par.clear()
        if lista:
            out.append("<ul>" + "".join(f"<li>{_in_linea(x)}</li>" for x in lista) + "</ul>")
            lista.clear()

    i = 0
    while i < len(righe):
        grezza = righe[i]
        r = grezza.strip()
        i += 1
        if not r or (r.startswith("<!--") and r.endswith("-->")):
            chiudi()
            continue
        if r.startswith("```"):                                   # blocco di codice, tale e quale
            chiudi()
            blocco = []
            while i < len(righe) and not righe[i].strip().startswith("```"):
                blocco.append(righe[i].rstrip())
                i += 1
            i += 1
            out.append(f"<pre>{escape(chr(10).join(blocco), quote=False)}</pre>")
            continue
        titolo = re.match(r"^(#{2,4})\s+(.+)$", r)
        if titolo:
            chiudi()
            livello = len(titolo.group(1)) + 1                    # ## → h3: il pannello ha già il suo h2
            if livello == 3:
                tid = _id(titolo.group(2), usati)
                sezioni.append((tid, titolo.group(2)))
                out.append(f'<h3 id="{tid}">{_in_linea(titolo.group(2))}</h3>')
            else:
                out.append(f"<h{livello}>{_in_linea(titolo.group(2))}</h{livello}>")
            continue
        if r.startswith("|"):                                     # tabella: intestazione, separatore, righe
            chiudi()
            tabella = [r]
            while i < len(righe) and righe[i].strip().startswith("|"):
                tabella.append(righe[i].strip())
                i += 1
            testa, corpo = _celle(tabella[0]), [_celle(t) for t in tabella[2:]]
            out.append("<div class=\"tabella\"><table><thead><tr>"
                       + "".join(f"<th>{_in_linea(c)}</th>" for c in testa) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_in_linea(c)}</td>" for c in riga) + "</tr>" for riga in corpo)
                       + "</tbody></table></div>")
            continue
        voce = re.match(r"^[-*]\s+(.+)$", r)
        if voce:
            if par:
                chiudi()
            lista.append(voce.group(1))
            continue
        if lista and grezza.startswith((" ", "\t")):               # continuazione della voce di elenco
            lista[-1] += " " + r
            continue
        if lista:
            chiudi()
        par.append(r)
    chiudi()
    return Glossario("\n".join(out), sezioni)


_cache: dict[Path, tuple[float, Glossario]] = {}


def glossario(percorso: Path = FILE) -> Glossario | None:
    """Il glossario pronto per la pagina; si rilegge quando il file cambia. None se il file non c'è."""
    try:
        quando = percorso.stat().st_mtime
    except OSError:
        return None
    if percorso not in _cache or _cache[percorso][0] != quando:
        _cache[percorso] = (quando, in_html(parte_app(percorso.read_text(encoding="utf-8"))))
    return _cache[percorso][1]
