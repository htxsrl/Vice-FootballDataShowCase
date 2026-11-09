"""Il motore in un punto solo: quali analisi servono a ciascun report, più spunti e limiti.

Lo usano lo script della demo di M2 e, da M3, l'agente. Ogni analisi riceve solo ciò che Vice vede
"oggi" (vice/data/stagione.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data.stagione import Visibile
from .evidenze import Risultato
from .giocatore import andamento
from .limiti import limiti
from .partita import allenamento_partita
from .seduta import evidenze_classifica, seduta
from .settimana import compensazione, esposizione_velocita, forma_settimana, griglia_settimana
from .spunti import Spunto, candidati, seleziona, ultime_sedute_classificate

TIPI_REPORT = ("seduta", "settimana", "giocatore")


@dataclass
class Analisi:
    tipo: str
    analisi: dict[str, Risultato]
    spunti: list[Spunto]
    limiti: Risultato
    giocatore_id: int | None = None
    candidati: list[Spunto] = field(default_factory=list)    # tutti gli spunti nati, anche quelli non mostrati
    qualita: list[dict] = field(default_factory=list)        # dati mancanti: chi non ha dati e dove

    def evidenze(self) -> dict:
        """Tutte le evidenze del report, per id (la verifica dei numeri di M3.8 parte da qui)."""
        return {e.id: e for r in self.analisi.values() for e in r.evidenze}

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "giocatore_id": self.giocatore_id,
                "analisi": {k: r.to_dict() for k, r in self.analisi.items()},
                "spunti": [s.to_dict() for s in self.spunti], "candidati": [s.to_dict() for s in self.candidati],
                "qualita": self.qualita, "limiti": self.limiti.to_dict()}


def analisi_per_report(v: Visibile, tipo: str = "seduta", giocatore_id: int | None = None) -> Analisi:
    if tipo not in TIPI_REPORT:
        raise ValueError(f"tipo di report sconosciuto: {tipo} (ammessi: {', '.join(TIPI_REPORT)})")
    if tipo == "giocatore" and giocatore_id is None:
        raise ValueError("il report del giocatore richiede giocatore_id")
    a: dict[str, Risultato] = {
        "seduta": seduta(v),
        "forma_settimana": forma_settimana(v),
        "esposizione_velocita": esposizione_velocita(v),
        "compensazione": compensazione(v),
    }
    if tipo in ("settimana", "giocatore"):
        a["allenamento_partita"] = allenamento_partita(v)
    if tipo == "settimana":
        a["griglia_settimana"] = griglia_settimana(v)
    if tipo == "giocatore":
        a["andamento"] = andamento(v, giocatore_id)
    ultime = ultime_sedute_classificate(v)
    cand = candidati(v, a, tipo, giocatore_id, ultime_sedute=ultime)
    # le evidenze degli spunti "consecutive" vengono da sedute passate: si aggiungono al report
    if not ultime.empty:
        a["ultime_sedute"] = Risultato("ultime_sedute", v.oggi, ultime, evidenze_classifica(ultime, "seduta"))
    return Analisi(tipo, a, seleziona(cand), limiti(), giocatore_id, cand, qualita(a, giocatore_id))


def qualita(a: dict[str, Risultato], giocatore_id: int | None = None) -> list[dict]:
    """Copertura dei dati per la sezione "qualità del dato" del report: non sono spunti, perché
    Vice non sa perché un dato manca (il dataset toglie righe senza motivo)."""
    out = []
    for nome, finestra, suffisso in (("esposizione_velocita", "da MD-4 a MD-2", "spr"), ("compensazione", "postpartita", "hsr")):
        s = a[nome].sintesi
        prefisso = "velocita" if nome == "esposizione_velocita" else "compensazione"
        for c in s.get("copertura_incompleta", []):
            if giocatore_id is None or c["giocatore_id"] == giocatore_id:
                out.append(c | {"finestra": finestra,
                                "evidenza": f"{prefisso}/{s['partita']:%Y-%m-%d}/{c['giocatore_id']}/{suffisso}"})
    return out
