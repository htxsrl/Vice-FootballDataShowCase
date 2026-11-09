"""Le sigle spiegate la prima volta (decisione 48): nelle risposte e nei report, la prima volta che compare una
sigla in una conversazione si scrive il suo significato, poi basta la sigla.

Il modello lo fa da sé (regola nei prompt, nella forma «distanza ad alto carico metabolico (HMLD)»); se se ne
dimentica, `introduci` aggiunge il significato tra parentesi dopo la sigla, che resta grammaticale anche con
l'articolo («l'HSR (corsa ad alta velocità)»). I significati sono gli stessi del glossario dell'app
(wiki/metodi/glossario.md): un test controlla che coincidano.
"""

from __future__ import annotations

import re

# sigla → significati: il primo è quello che si scrive, gli altri valgono come spiegazione già data
SIGLE: dict[str, tuple[str, ...]] = {
    "TD": ("distanza totale",),
    "HSR": ("corsa ad alta velocità", "alta velocità"),
    "SPR": ("sprint",),
    "ACC": ("accelerazioni intense", "accelerazioni"),
    "DCC": ("decelerazioni intense", "decelerazioni"),
    "HMLD": ("distanza ad alto carico metabolico", "alto carico metabolico"),
    "ACWR": ("rapporto tra carico acuto e cronico", "carico acuto"),
    "RPE": ("fatica percepita",),
    "MD": ("giorno della partita", "partita"),
}
_PRIMA = {1: "il giorno", 2: "due giorni", 3: "tre giorni", 4: "quattro giorni", 5: "cinque giorni"}
SIGLA = re.compile(r"(?<![\w-])(TD|HSR|SPR|ACC|DCC|HMLD|ACWR|RPE|MD(?:[+-][1-5])?)(?![\w+-])")


def famiglia(sigla: str) -> str:
    """MD-2, MD+1 e MD sono la stessa sigla: spiegata una, sono spiegate tutte."""
    return "MD" if sigla.startswith("MD") else sigla


def significato(sigla: str) -> str:
    if sigla.startswith("MD") and len(sigla) > 2:
        n = int(sigla[3])
        return f"{_PRIMA[n]} {'prima della' if sigla[2] == '-' else 'dopo la'} partita"
    return SIGLE[famiglia(sigla)][0]


def spiegate(testi: list[str]) -> set[str]:
    """Le sigle già comparse nei messaggi precedenti di Vice: lì sono già state spiegate."""
    return {famiglia(m.group(1)) for t in testi for m in SIGLA.finditer(t or "")}


def _gia_spiegata(testo: str, inizio: int, fine: int, sigla: str) -> bool:
    """«significato (SIGLA)», «SIGLA (significato)» oppure «(SIGLA, significato)»."""
    parole = SIGLE[famiglia(sigla)] + ((significato(sigla),) if sigla.startswith("MD") else ())
    prima = testo[max(0, inizio - 60):inizio].lower()
    dopo = testo[fine:fine + 70].lower()
    tra_parentesi = prima.rstrip().endswith("(")
    if tra_parentesi and any(p in prima for p in parole):
        return True
    m = re.match(r"\s*(?:\(|,)([^)]*)\)", dopo)          # «SIGLA (significato)» o «(SIGLA, significato)»
    return bool(m) and any(p in m.group(1) for p in parole)


def introduci(testo: str, gia: set[str] | None = None) -> str:
    """Aggiunge il significato alla prima comparsa di ogni sigla non ancora spiegata nella conversazione."""
    gia = set(gia or ())
    pezzi, ultimo = [], 0
    for m in SIGLA.finditer(testo):
        sigla, fam = m.group(1), famiglia(m.group(1))
        if fam in gia:
            continue
        gia.add(fam)
        if _gia_spiegata(testo, m.start(), m.end(), sigla):
            continue
        # già dentro una parentesi, «(MD-2)»: si aggiunge con la virgola, «(MD-2, due giorni prima della partita)»
        dentro = testo[m.end():m.end() + 1] == ")"
        pezzi.append(testo[ultimo:m.end()] + (f", {significato(sigla)}" if dentro else f" ({significato(sigla)})"))
        ultimo = m.end()
    return "".join(pezzi) + testo[ultimo:]


def per_il_front_end() -> dict[str, list[str]]:
    """Sigla → significati, con le forme di MD (MD-1…MD-5, MD+1, MD+2): il front-end le mette in grassetto."""
    out = {s: list(v) for s, v in SIGLE.items()}
    for n in range(1, 6):
        out[f"MD-{n}"] = [significato(f"MD-{n}")]
    for n in (1, 2):
        out[f"MD+{n}"] = [significato(f"MD+{n}")]
    return out


def elenco_per_il_prompt() -> str:
    """Le sigle e il loro significato, per i prompt."""
    return "; ".join(f"{s} = {v[0]}" for s, v in SIGLE.items() if s != "MD") + "; MD-2 = due giorni prima della partita, " \
        "MD+1 = il giorno dopo la partita"
