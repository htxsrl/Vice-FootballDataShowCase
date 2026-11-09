"""M3.8 Verifica deterministica dei numeri e dei giudizi: ogni numero di una frase deve stare nelle
evidenze che la frase cita ([E3], [D1]…), e ogni giudizio a parole («sopra la fascia», «oggi») deve
essere coerente con quelle evidenze. Nessun LLM.

- Si divide il testo in frasi (righe e punti fermi; "5.436" non spezza).
- Si tolgono ciò che non è un dato: citazioni, date, giorni MD, nomi dei percentili (P10), anni,
  numeri di elenco, codici lunghi, numeri di maglia («Matteo Basile (9)», «il numero 9»), la finestra fissa
  del motore («ultime 4 settimane», `GIORNI_RECENTI`).
- Ogni numero rimasto (scritto all'italiana; "km" si converte in metri) deve coincidere, entro
  l'arrotondamento con cui è scritto, con un numero delle evidenze citate dalla frase.
- Giudizi (decisione 45): se la frase dice sopra, sotto, dentro o fuori dalla fascia (o dal solito, dal
  riferimento), «molto sopra», «fascia larga» o «oggi», almeno un'evidenza citata deve dire lo stesso.
  «Sopra la mediana» e «sotto il riferimento» si confrontano con P50. Le negazioni («non è sopra») non si
  giudicano. Nato da due errori visti: «percentile 65, sopra la fascia centrale» (65 sta dentro) e
  «MD-2 (oggi)» accanto a mediane di 4 settimane.
- Esito per frase: "senza numeri", "verificata", "non verificata" (con il motivo).
Decisione 31: chi chiama prova una correzione e poi toglie le frasi che non passano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..analysis.giocatore import GIORNI_RECENTI
from ..data.anagrafica import GIOCATORI
from .citazioni import Registro

MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
CITAZIONE = re.compile(r"\[\s*((?:[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)(?:\s*[,;]\s*[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)*)\s*\]")
DATA = re.compile(rf"\b(\d{{2}})/(\d{{2}})(?:/(\d{{2,4}}))?\b|\b(\d{{1,2}})\s+({MESI})\b", re.I)
DA_TOGLIERE = [
    re.compile(r"\b\d{2}/\d{2}(?:/\d{2,4})?\b"),                           # date 10/01/2024 (non "1/2 sedute")
    re.compile(rf"\b\d{{1,2}}\s+(?:{MESI})(?:\s+\d{{4}})?\b", re.I),       # 10 gennaio 2024
    re.compile(r"\b\d{4}/\d{2,4}\b"),                                      # stagione 2023/24
    re.compile(r"\bMD\s*[+\-−]\s*\d\b"),                                   # MD-3, MD+1
    re.compile(r"\b[PV]\d{1,2}\b"),                                        # P10, P90, V1
    re.compile(r"\bM\d+(?:\.\d+)?\b"),                                     # M2, M3.8
    re.compile(r"^\s*\d+[.)]\s", re.M),                                    # numeri di elenco
    re.compile(r"\b\d{6,}\b"),                                             # codici (Zenodo 18986229)
    re.compile(r"\b(?:19[5-9]\d|20[0-4]\d)\b(?!\s*(?:m\b|km\b|%|metri))"),  # anni
    re.compile(rf"\b{GIORNI_RECENTI // 7}\s+settimane\b", re.I),             # la finestra fissa del motore («ultime 4 settimane»)
]
# giudizi di posizione: «sopra la sua fascia», «sotto il solito», «dentro la fascia», «fuori fascia»…
_OGGETTO = (r"(?:\s+(?:a|al|alla|della|del|dalla|dal|la|il|le|lo|i|gli|nella|nel))?(?:\s+(?:sua|suo|loro|propria|proprio))?"
            r"\s+(?P<ogg>fascia(?:\s+(?:centrale|larga|abituale|storica|attesa))?|solito|norma|range|riferimento|abituale|mediana)")
GIUDIZIO = re.compile(r"(?P<molto>\bmolto\s+)?\b(?P<dir>sopra|sotto|oltre|dentro|entro|fuori|al di sopra|al di sotto)" + _OGGETTO, re.I)
IN_LINEA = re.compile(r"\bin linea con (?:il |la )?(?:suo |sua |loro )?(?:solito|fascia|norma|riferimento)\b|\bnella norma\b", re.I)
# «non titolari» è un gruppo di giocatori, non una negazione
NEGAZIONE = re.compile(r"\b(?:non(?!\s+titolar)|né|nessun[oa]?|senza)\b[^.;:]{0,25}$", re.I)
# il giudizio parla dei singoli giocatori, non della mediana di squadra («trainati da alcuni singoli molto sopra fascia»)
SINGOLI = re.compile(r"\b(?:singol[io]|giocator[ei]|alcun[ie]|qualcuno|compagni|chi|di loro|tra cui)\b", re.I)
OGGI = re.compile(r"\boggi\b", re.I)
# numeri di maglia, che non sono dati: «Matteo Basile (9)», «il numero 9», «maglia 9»
MAGLIE = {numero for _, _, numero, _ in GIOCATORI.values()}
MAGLIA_DOPO_NOME = [re.compile(rf"\b({re.escape(cognome)})\s*\((?:n\.\s*|#\s*|maglia\s+|numero\s+)?{numero}\)", re.I)
                    for _, cognome, numero, _ in GIOCATORI.values()]
MAGLIA = re.compile(r"\b(?:numero|maglia|n\.)\s*(\d{1,2})\b", re.I)
NUMERO = re.compile(r"(?<![\w,.])([+\-−]?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?:\.(\d{1,2})(?!\d))?(\s*km\b(?!\s*/\s*h))?")


@dataclass
class Numero:
    testo: str
    valore: float
    tolleranza: float


@dataclass
class Frase:
    testo: str
    citazioni: list[str] = field(default_factory=list)
    numeri: list[Numero] = field(default_factory=list)
    esito: str = "senza numeri"          # "senza numeri" | "verificata" | "non verificata"
    motivo: str = ""

    def to_dict(self) -> dict:
        return {"testo": self.testo, "citazioni": self.citazioni, "esito": self.esito, "motivo": self.motivo,
                "numeri": [n.testo for n in self.numeri]}


@dataclass
class Verifica:
    frasi: list[Frase]

    @property
    def con_numeri(self) -> list[Frase]:
        return [f for f in self.frasi if f.esito != "senza numeri"]

    @property
    def non_verificate(self) -> list[Frase]:
        return [f for f in self.frasi if f.esito == "non verificata"]

    @property
    def verificate(self) -> int:
        return sum(f.esito == "verificata" for f in self.frasi)

    def to_dict(self) -> dict:
        return {"frasi_con_numeri": len(self.con_numeri), "verificate": self.verificate,
                "non_verificate": [f.to_dict() for f in self.non_verificate]}


def dividi_frasi(testo: str) -> list[str]:
    """Righe, poi punti fermi seguiti da spazio e maiuscola (i numeri come 5.436 non spezzano)."""
    out = []
    for riga in testo.split("\n"):
        if not riga.strip():
            continue
        out += [p for p in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ«\"(*\-•])", riga) if p.strip()]
    return out


def numeri(testo: str) -> list[Numero]:
    t = CITAZIONE.sub(" ", testo)
    for r in DA_TOGLIERE:
        t = r.sub(" ", t)
    for r in MAGLIA_DOPO_NOME:
        t = r.sub(r"\1", t)
    t = MAGLIA.sub(lambda m: " " if int(m.group(1)) in MAGLIE else m.group(0), t)
    out = []
    for m in NUMERO.finditer(t):
        segno, intero, dec_virgola, dec_punto, km = m.groups()
        intero = intero.replace(".", "")
        dec = dec_virgola if dec_virgola is not None else dec_punto
        v = float(f"{intero}.{dec}") if dec else float(intero)
        tol = 0.5 * 10 ** (-len(dec)) if dec else 0.5
        if segno in ("-", "−"):
            v = -v
        if km:
            v, tol = v * 1000, tol * 1000
        out.append(Numero(m.group(0).strip(), v, tol + 1e-9))
    return out


def etichette(gruppo: str) -> list[str]:
    """"E3, E7" → [E3, E7]; "E10-E12" → [E10, E11, E12] (gli intervalli non vanno usati, ma si capiscono)."""
    out = []
    for parte in re.split(r"\s*[,;]\s*", gruppo):
        m = re.fullmatch(r"([ED])(\d+)\s*[-–]\s*[ED]?(\d+)", parte)
        if m and int(m.group(3)) >= int(m.group(2)) and int(m.group(3)) - int(m.group(2)) < 30:
            out += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(parte)
    return out


def date_scritte(testo: str) -> list[tuple[int, int]]:
    """(giorno, mese) delle date nel testo: 10/01/2024, 10/01, 10 gennaio."""
    out = []
    for m in DATA.finditer(testo):
        if m.group(1):
            g, mese = int(m.group(1)), int(m.group(2))
        else:
            g, mese = int(m.group(4)), MESI.split("|").index(m.group(5).lower()) + 1
        if 1 <= g <= 31 and 1 <= mese <= 12:
            out.append((g, mese))
    return out


def stati(ev, frase: str = "", singoli: bool = False) -> list[tuple[str, bool]]:
    """Dove sta un'evidenza rispetto alla sua fascia o al suo solito: [("sopra"|"sotto"|"dentro", molto)].
    Per le mediane di squadra: il percentile se la frase parla di percentile (fascia centrale P25-P75) e il
    giudizio non riguarda i singoli giocatori, altrimenti i conteggi dei giocatori sopra, sotto e dentro."""
    c = ev.contesto
    p = str(c.get("posizione") or c.get("esito") or c.get("descrizione") or "").lower()
    if p:
        for prefisso, out in (("molto sopra", ("sopra", True)), ("molto sotto", ("sotto", True)), ("sopra", ("sopra", False)),
                              ("più alto", ("sopra", False)), ("sotto", ("sotto", False)), ("più basso", ("sotto", False)),
                              ("dentro", ("dentro", False)), ("in linea", ("dentro", False))):
            if p.startswith(prefisso):
                return [out]
        return []
    if ev.unita == "percentile" and isinstance(ev.valore, (int, float)):
        conteggi = any(k in c for k in ("sopra", "sotto", "dentro"))
        if not conteggi or ("percentil" in frase.lower() and not singoli):
            v = float(ev.valore)
            return [("sopra", v > 90) if v > 75 else ("sotto", v < 10) if v < 25 else ("dentro", False)]
        # i conteggi uniscono «sopra» e «molto sopra»: non si sa quanto, si accetta anche «molto»
        return [(k, True) for k in ("sopra", "sotto", "dentro") if (c.get(k) or 0) > 0]
    # riepiloghi con i conteggi per esito (postpartita: «molto_sotto»: 5, «sotto_il_solito»: 3, «in_linea»: 7)
    out = []
    for k, n in c.items():
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            continue
        for prefisso, stato in (("molto_sopra", ("sopra", True)), ("molto_sotto", ("sotto", True)), ("sopra", ("sopra", False)),
                                ("sotto", ("sotto", False)), ("dentro", ("dentro", False)), ("in_linea", ("dentro", False))):
            if k.startswith(prefisso):
                out.append(stato)
                break
    return out


def stati_mediana(ev) -> list[tuple[str, bool]]:
    """Dove sta un'evidenza rispetto alla sua mediana (P50): il percentile contro 50, oppure il valore contro
    `mediana` o `riferimento`. «Molto» qui non si giudica."""
    v, c = ev.valore, ev.contesto
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return []
    rif = 50 if ev.unita == "percentile" else c.get("mediana", c.get("riferimento"))
    if isinstance(rif, bool) or not isinstance(rif, (int, float)):
        return []
    return [("sopra" if v > rif else "sotto" if v < rif else "dentro", True)]


def _giudizi(frase: str) -> list[tuple[str, bool, bool, bool, bool]]:
    """I giudizi di posizione affermati (non negati): (direzione, molto, fascia larga, parla dei singoli,
    rispetto alla mediana o al riferimento)."""
    out = []
    for m in GIUDIZIO.finditer(frase):
        if NEGAZIONE.search(frase[:m.start()]):
            continue
        d = m.group("dir").lower()
        d = {"oltre": "sopra", "al di sopra": "sopra", "al di sotto": "sotto", "entro": "dentro"}.get(d, d)
        larga = "larga" in m.group("ogg").lower()
        mediana = m.group("ogg").lower() in ("mediana", "riferimento")
        out.append((d, bool(m.group("molto")), larga, bool(SINGOLI.search(frase[max(0, m.start() - 40):m.start()])), mediana))
    for m in IN_LINEA.finditer(frase):
        if not NEGAZIONE.search(frase[:m.start()]):
            out.append(("dentro", False, False, False, False))
    return out


def _motivo(d: str, molto: bool, larga: bool, stati_citati: list[tuple[str, bool]]) -> str:
    parola = ("molto " if molto else "") + d + (" la fascia larga" if larga else "")
    dice = ", ".join(sorted({("molto " if m else "") + s for s, m in stati_citati}))
    if d in ("sopra", "sotto", "fuori") and (molto or larga) and any(s in ("sopra", "sotto") for s, _ in stati_citati):
        oltre = {"sopra": "sopra P90", "sotto": "sotto P10"}.get(d, "fuori da P10-P90")
        return (f"la frase dice «{parola}», cioè {oltre}, ma i dati citati dicono: {dice} («sopra» e «sotto» senza "
                f"«molto» vogliono dire fuori dalla fascia centrale P25-P75 ma dentro la fascia larga P10-P90)")
    return f"la frase dice «{parola}» ma i dati citati dicono: {dice}"


def _di_oggi(ev, oggi: str) -> bool | None:
    """True se l'evidenza è della seduta di oggi, False se è di un altro periodo, None se non si sa."""
    c = ev.contesto
    if c.get("data"):
        return str(c["data"])[:10] == oggi
    if c.get("dal") or c.get("al") or ev.id.startswith(("confronto/", "velocita/", "compensazione/")):
        return False
    return None


def giudizio_incoerente(frase: str, citazioni: list[str], registro: Registro) -> str:
    """Il motivo per cui un giudizio a parole non torna con le evidenze citate ("" se torna)."""
    evidenze = [ev for e in citazioni if (ev := registro.evidenza(e)) is not None]
    if not evidenze:
        return ""
    for d, molto, larga, singoli, mediana in _giudizi(frase):
        stati_citati = [x for ev in evidenze for x in (stati_mediana(ev) if mediana else stati(ev, frase, singoli))]
        if not stati_citati:
            continue
        if d == "fuori":
            ok = any(s in ("sopra", "sotto") and (m or not larga) for s, m in stati_citati)
        elif d == "dentro":   # «dentro la fascia larga» vale anche per «sopra» e «sotto» senza «molto»
            ok = any(s == "dentro" or (larga and not m) for s, m in stati_citati)
        else:
            ok = any(s == d and (m or not (molto or larga)) for s, m in stati_citati)
        if not ok:
            return _motivo(d, molto, larga, stati_citati)
    oggi = getattr(registro, "oggi", None)
    if oggi and OGGI.search(frase) and not NEGAZIONE.search(frase[:OGGI.search(frase).start()]):
        quando = [_di_oggi(ev, oggi) for ev in evidenze]
        if quando and all(q is False for q in quando):
            return "la frase dice «oggi» ma i dati citati non sono della seduta di oggi (sono di un altro giorno o di un periodo)"
    return ""


def verifica(testo: str, registro: Registro) -> Verifica:
    frasi = []
    for s in dividi_frasi(testo):
        f = Frase(s, [e for gruppo in CITAZIONE.findall(s) for e in etichette(gruppo)], numeri(s))
        sconosciute_date = [d for d in date_scritte(s) if registro.date and d not in registro.date]
        if sconosciute_date:
            f.esito, f.motivo = "non verificata", "date non presenti nei dati: " + ", ".join(f"{g:02d}/{m:02d}" for g, m in sconosciute_date)
            frasi.append(f)
            continue
        if f.numeri:
            ammessi, sconosciute = [], []
            for e in f.citazioni:
                n = registro.numeri(e)
                (sconosciute.append(e) if n is None else ammessi.extend(n))
            # il segno si dice a parole ("più basso del 24%" per −24): si confrontano i valori assoluti
            mancanti = [n.testo for n in f.numeri if not any(abs(abs(n.valore) - abs(a)) <= n.tolleranza for a in ammessi)]
            if not f.citazioni:
                f.esito, f.motivo = "non verificata", "numeri senza evidenza citata"
            elif sconosciute:
                f.esito, f.motivo = "non verificata", f"evidenze inesistenti: {', '.join(sconosciute)}"
            elif mancanti:
                f.esito, f.motivo = "non verificata", f"numeri non presenti nelle evidenze citate: {', '.join(mancanti)}"
            else:
                f.esito = "verificata"
        # i giudizi a parole, anche nelle frasi senza numeri (decisione 45)
        if f.esito != "non verificata" and f.citazioni:
            motivo = giudizio_incoerente(s, f.citazioni, registro)
            if motivo:
                f.esito, f.motivo = "non verificata", motivo
            elif f.esito == "senza numeri" and (_giudizi(s) or OGGI.search(s)):
                f.esito = "verificata"
        frasi.append(f)
    return Verifica(frasi)


VERBI_SPUNTO = re.compile(r"^\W*(Valutare|Verificare|Approfondire)\b")


def spunti_inventati(testo: str, ammessi: list[str]) -> list[str]:
    """Le frasi da spunto («Valutare…», «Verificare…», «Approfondire…») che non vengono dalla tabella delle
    regole del motore (confronto sulle prime parole). Gli spunti li decide il motore, mai il modello."""
    out = []
    for f in dividi_frasi(testo):
        pulita = CITAZIONE.sub("", f).lstrip("-•* ").strip()
        if VERBI_SPUNTO.match(pulita) and not any(pulita[:40].lower() in a.lower() or a[:40].lower() in pulita.lower()
                                                  for a in ammessi):
            out.append(f)
    return out


def togli(testo: str, frasi: list[Frase]) -> str:
    """Il testo senza le frasi indicate (le righe rimaste vuote spariscono)."""
    for f in frasi:
        testo = testo.replace(f.testo, "", 1)
    righe = [r.rstrip() for r in testo.split("\n")]
    pulite = [r for r in righe if r.strip() not in ("", "-", "*", "•")]
    return "\n".join(pulite).strip()


# «[E1-E9 non citabili come intervallo, vedi sotto]» (risposta reale, 28/10/2026): un commento del modello
# dentro la citazione. Restano le etichette, il commento si toglie (serve almeno una parola di tre lettere,
# così «[E3 e E7]» non si tocca).
NOTA_IN_CITAZIONE = re.compile(r"\[\s*((?:[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)(?:\s*[,;]\s*[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)*)"
                               r"\s+(?=[^\]]*[a-zà-ù]{3})[^\]]*\]")


def pulisci_citazioni(testo: str) -> str:
    """Dentro le parentesi quadre delle citazioni restano solo le etichette."""
    return NOTA_IN_CITAZIONE.sub(r"[\1]", testo)


def chiudi_frase(testo: str) -> str:
    """Se il testo finisce a metà frase (succede quando il modello chiama una vista nel mezzo di una frase),
    si toglie il frammento finale."""
    t = testo.rstrip()
    if not t or t[-1] in ".!?:)]»\"*" or t.endswith("```"):
        return t
    ultima = max(t.rfind(". "), t.rfind(".\n"), t.rfind("\n"), t.rfind("! "), t.rfind("? "))
    return t[:ultima + 1].rstrip() if ultima > 0 else t


def taglia_incompleto(testo: str) -> str:
    """Se il modello si è fermato per il tetto di token, l'ultima riga è a metà: si toglie."""
    righe = testo.rstrip().split("\n")
    return "\n".join(righe[:-1]).rstrip() if len(righe) > 1 else testo


def senza_citazioni(testo: str) -> str:
    """Per la cronologia mandata al modello: le etichette di un turno non valgono nel successivo."""
    return re.sub(r"\s*" + CITAZIONE.pattern, "", testo)
