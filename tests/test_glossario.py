"""Il glossario (decisioni 46 e 48): la pagina della wiki è l'unica fonte, l'app ne mostra una tabella con
quattro colonne, i significati sono quelli che Vice scrive la prima volta che usa una sigla e le soglie sono
quelle del codice."""

import re

import pytest

from vice.agent.citazioni import DEFINIZIONI
from vice.agent.sigle import SIGLE
from vice.glossario import FILE, FINE, INIZIO, glossario, in_html, parte_app


@pytest.fixture(scope="module")
def righe() -> dict[str, list[str]]:
    assert FILE.exists(), f"manca {FILE}: nel container la wiki va montata (docker-compose.yml)"
    testo = FILE.read_text(encoding="utf-8")
    assert testo.count(INIZIO) == 1 and testo.count(FINE) == 1
    tabella = [r.strip() for r in parte_app(testo).strip().splitlines() if r.strip()]
    assert all(r.startswith("|") for r in tabella), "nella parte per l'app c'è solo la tabella"
    celle = [[c.strip() for c in r.strip("|").split("|")] for r in tabella]
    assert celle[0] == ["Sigla", "Significato", "Unità di misura", "Cosa misura"]
    assert all(len(c) == 4 for c in celle)
    return {c[0]: c[1:] for c in celle[2:]}


def it(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def test_significati_come_quelli_di_vice(righe):
    """Il significato del glossario comincia con quello che Vice scrive accanto alla sigla (vice/agent/sigle.py)."""
    for sigla, significati in SIGLE.items():
        assert sigla in righe, sigla
        assert righe[sigla][0].startswith(significati[0]), sigla


def test_soglie_del_gps(righe):
    hsr, spr, hmld, acc = next(n for e, _, n in DEFINIZIONI if e == "D1")      # [19.8, 25.2, 25.5, 3]
    assert f"oltre i {it(hsr)} km/h" in righe["HSR"][2]
    assert f"oltre i {it(spr)} km/h" in righe["SPR"][2]
    assert f"oltre i {it(hmld)} W/kg" in righe["HMLD"][2]
    assert f"oltre i {it(acc)} m/s²" in righe["ACC"][2] and f"oltre i {it(acc)} m/s²" in righe["DCC"][2]


def test_unita(righe):
    assert [righe[s][1] for s in ("TD", "HSR", "SPR", "HMLD")] == ["m"] * 4
    assert righe["ACC"][1] == righe["DCC"][1] == "numero"
    assert righe["MD"][1] == ""


def test_html_dell_app():
    g = glossario()
    assert g is not None and g.sezioni == []
    assert g.html.count("<table>") == 1 and "<th>Unità di misura</th>" in g.html
    for resto in ("**", "](", "|---", "<!--", "glossario-app", "Sigle del progetto"):
        assert resto not in g.html, resto
    assert "<a " not in g.html


def test_markdown_minimo():
    g = in_html("## Titolo\n\nUn *corsivo* e **grassetto** con [un link](x.md) e [E1].\n\n"
                "- voce che\n  continua\n- seconda `<b>`\n\n| A | B |\n|---|---|\n| 1 < 2 | |\n\n```\n a < b\n```\n")
    assert g.sezioni == [("gl-titolo", "Titolo")]
    assert "<p>Un <em>corsivo</em> e <strong>grassetto</strong> con un link e [E1].</p>" in g.html
    assert "<li>voce che continua</li>" in g.html and "<code>&lt;b&gt;</code>" in g.html
    assert "<td>1 &lt; 2</td><td></td>" in g.html and "<pre> a &lt; b</pre>" in g.html
    assert not re.search(r"[─-╿]", g.html)


def test_parte_app_senza_segni():
    with pytest.raises(ValueError):
        parte_app("# Glossario senza segni")


def test_pagina_col_pulsante(client):
    r = client.get("/")
    assert 'id="apri-glossario"' in r.text and 'aria-controls="glossario"' in r.text
    assert "High Speed Running" in r.text and "glossario-indice" not in r.text
