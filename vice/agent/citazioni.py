"""Le evidenze di un turno, con etichette brevi da citare nel testo: [E1], [E2]… e le definizioni [D1]…

Il modello vede solo le evidenze che gli strumenti gli passano, ciascuna con la sua etichetta e con
i numeri già scritti all'italiana, così li può copiare esattamente. La verifica (verifica.py) usa
lo stesso registro: un numero è verificato solo se sta nelle evidenze citate dalla sua frase.
"""

from __future__ import annotations

from typing import Any

from ..analysis.evidenze import Evidenza, con_unita, giorno_md_it, numero_it

# Definizioni fisse, sempre citabili: soglie e regole che il testo può nominare.
DEFINIZIONI = [
    ("D1", "Soglie del GPS del club: HSR oltre 19,8 km/h (sprint compreso), sprint oltre 25,2 km/h, "
           "HMLD oltre 25,5 W/kg, accelerazioni e decelerazioni oltre ±3 m/s²", [19.8, 25.2, 25.5, 3]),
    ("D2", "Fasce storiche: centrale P25-P75, larga P10-P90; fascia personale da 8 sedute; provvisoria sotto le "
           "6 sedute diverse", [25, 75, 10, 90, 8, 6]),
    ("D3", "Finestra dell'alta velocità prima della partita: da MD-4 a MD-2; sprint registrato molto basso sotto i 10 m",
     [10]),
    ("D4", "Riferimento di partita: media dei carichi osservati nelle partite da titolare (almeno 3); il postpartita non "
           "genera spunti se partita e postpartita superano il 60% dell'HSR di riferimento", [3, 60]),
    ("D5", "Andamento: ultimi 28 giorni contro le sedute precedenti dello stesso giorno MD", [28]),
    ("D6", "Dati del club: stagione 2023/24, 20 giocatori di movimento, 2.375 righe giocatore × giorno, 121 giorni di "
           "allenamento e 30 partite; GPS STATSports a 10 Hz", [20, 2375, 121, 30, 10]),
]


class Registro:
    """Le evidenze mostrate al modello nel turno, con etichette progressive."""

    def __init__(self, oggi: str | None = None):
        self.oggi = oggi                              # "AAAA-MM-GG": per controllare i giudizi «oggi» (decisione 45)
        self._per_etichetta: dict[str, Evidenza] = {}
        self._per_id: dict[str, str] = {}
        self.definizioni = {e: n for e, _, n in DEFINIZIONI}
        self.date: set[tuple[int, int]] = set()      # (giorno, mese) visti nei dati del turno

    def registra_date(self, testo: str) -> None:
        """Le date che compaiono nei dati mandati al modello: solo queste si possono scrivere."""
        from .verifica import date_scritte
        self.date.update(date_scritte(testo))

    def etichetta(self, ev: Evidenza) -> str:
        if ev.id not in self._per_id:
            e = f"E{len(self._per_id) + 1}"
            self._per_id[ev.id] = e
            self._per_etichetta[e] = ev
        return self._per_id[ev.id]

    def evidenza(self, etichetta: str) -> Evidenza | None:
        return self._per_etichetta.get(etichetta)

    def numeri(self, etichetta: str) -> list[float] | None:
        """I numeri citabili di un'evidenza: valore, contesto e quelli del nome ("picco di 1 minuto", "per 90 minuti")."""
        if etichetta in self.definizioni:
            return list(self.definizioni[etichetta])
        ev = self.evidenza(etichetta)
        if ev is None:
            return None
        from .verifica import numeri as numeri_nel_testo
        return ev.numeri() + [n.valore for n in numeri_nel_testo(ev.etichetta)]

    def __len__(self) -> int:
        return len(self._per_etichetta)

    def tutte(self) -> dict[str, Evidenza]:
        return dict(self._per_etichetta)

    def per_il_modello(self, ev: Evidenza) -> dict:
        """Un'evidenza compatta, con etichetta e numeri scritti come si devono copiare."""
        if ev.valore is None:
            valore = "nessun dato"
        elif isinstance(ev.valore, str):
            valore = ev.valore
        else:
            valore = con_unita(ev.valore, ev.unita)
        out: dict[str, Any] = {"evidenza": self.etichetta(ev), "cosa": ev.etichetta, "valore": valore}
        for k, v in ev.contesto.items():
            if k in ("giocatore_id", "metrica", "giocatore", "data", "partita"):
                continue
            out[k] = giorno_md_it(v) if k == "giorno_md" else _italiano(v, ev.unita if k in UNITA_DEL_VALORE else "")
        return out


# chiavi del contesto che hanno la stessa unità del valore
UNITA_DEL_VALORE = {"fascia_centrale", "fascia_larga", "mediana", "riferimento", "solito", "scarto", "tolleranza",
                    "carico", "in_partita", "differenza_mediana", "mediana_ruolo", "mediana_squadra", "fascia_partite",
                    "hsr_mediano_molto_sotto", "riferimento_mediano_molto_sotto", "p10", "p90"}


def _italiano(v: Any, unita: str) -> Any:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        if unita:
            return con_unita(v, unita)
        return numero_it(v, "n") if float(v).is_integer() else numero_it(v, "").rstrip("0").rstrip(",")
    if isinstance(v, list):
        return [_italiano(x, unita) for x in v]
    if isinstance(v, dict):
        return {k: _italiano(x, unita) for k, x in v.items()}
    return v


def testo_definizioni() -> str:
    return "\n".join(f"[{e}] {t}" for e, t, _ in DEFINIZIONI)
