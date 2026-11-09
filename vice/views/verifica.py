"""V9 verifica: come sappiamo che i numeri sono giusti. Il motore riproduce le tabelle dell'articolo che descrive
i dati del club (M2.13). Fino al 06/11/2026 c'era anche la coerenza con SkillCorner, tolta con la decisione 57."""

from __future__ import annotations

from ..agent.contesto import Sessione
from ..analysis.evidenze import numero_it
from ..analysis.verifiche import replica_articolo
from .comune import FONTE_ZENODO


def vista_verifica(s: Sessione, parametri: dict) -> dict:
    rep = replica_articolo()
    schede = []
    for e in rep.evidenze:
        if e.id == "replica/tabella1":
            schede.append({"titolo": "Tabella 1 dell'articolo", "valore": f"{e.valore} celle su {e.contesto['celle']}",
                           "testo": f"riprodotte identiche, su {numero_it(e.contesto['righe'], 'n')} righe giocatore × giorno",
                           "evidenza": e.id})
        elif e.id.startswith("replica/tabella2/"):
            testo = "medie identiche" + (f"; le {e.contesto['refuso']} diverse sono un refuso dell'articolo" if e.contesto.get("refuso") else "")
            schede.append({"titolo": "Tabella 2, " + ("distanza totale" if e.id.endswith("/td") else "HSR dei difensori centrali"),
                           "valore": f"{e.valore} celle su {e.contesto['celle']}", "testo": testo, "evidenza": e.id})
    return {
        "vista": "verifica", "forma": "verifica", "parametri": {},
        "titolo": "Come sappiamo che i numeri sono giusti",
        "spiegazione": ("Il motore riproduce dai dati del club le tabelle dell'articolo scientifico che li descrive: "
                        "stesse righe, stesse medie. Le poche celle diverse sono un refuso dell'articolo."),
        "articolo": rep.sintesi.get("articolo"), "schede": schede,
        "chiave": "replica", "righe": [{"chiave": s["evidenza"], "evidenza": s["evidenza"]} for s in schede],
        "avvisi": [], "fonte": FONTE_ZENODO,
    }
