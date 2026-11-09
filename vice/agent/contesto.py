"""Il contesto di un turno: l'"oggi" simulato, i giocatori riconosciuti per nome o numero, le date.

L'"oggi" lo decide l'interfaccia (barra dell'oggi, M4.7), mai il modello: gli strumenti accettano
date passate ma rifiutano quelle successive all'oggi, così Vice non vede il futuro.
Il **giorno in esame** (decisione 47) è il giorno scelto nel calendario: Vice ragiona sempre dall'oggi, ma
le domande senza data riguardano quel giorno, così si può anche confrontarlo con oggi.
**Il giorno della demo** (decisione 54) è il 19/04/2024: i giorni prima sono già nei dati del club, la seduta di
quel giorno arriva solo col file caricato (o col file di prova). Finché non c'è, Vice vede fino a ieri.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date

import pandas as pd

from ..data import caricamenti
from ..data.stagione import Stagione, Visibile, stagione

OGGI_PREDEFINITO = os.environ.get("VICE_OGGI", "2024-04-19")   # il giorno della demo, MD-1 (decisione 54)
GIORNO_DEMO = pd.Timestamp(OGGI_PREDEFINITO).normalize()
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre")


class ErroreStrumento(ValueError):
    """Errore da riportare al modello (e all'utente) in italiano."""


def senza_la_seduta(v: Visibile) -> Visibile:
    """Il giorno di `v` senza la sua seduta, come se non fosse ancora caricata (decisione 54): niente righe di quel
    giorno, e il giorno non conta tra le sedute e le partite giocate."""
    g = v.oggi
    return replace(v, seduta_di_oggi=v.seduta_di_oggi.iloc[0:0].copy(),
                   sedute=v.sedute[v.sedute["data"] < g].reset_index(drop=True),
                   partite_giocate=v.partite_giocate[v.partite_giocate["data"] < g].reset_index(drop=True))


def _dal_dataset(codice: str, st: Stagione) -> caricamenti.Caricamento | None:
    """Il codice `dataset-AAAA-MM-GG`: un file uguale alle righe del dataset di quel giorno."""
    if not codice.startswith(caricamenti.PREFISSO_DATASET):
        return None
    try:
        g = pd.Timestamp(codice.removeprefix(caricamenti.PREFISSO_DATASET)).normalize()
    except (ValueError, TypeError):
        return None
    righe = st.al(g).seduta_di_oggi
    if righe.empty:
        return None
    return caricamenti.Caricamento(caricamenti.codice_dataset(g), g, righe, "dataset", 0.0)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Sessione:
    oggi: pd.Timestamp
    stagione: Stagione
    caricamento: caricamenti.Caricamento | None = None   # export GPS caricato: sostituisce la seduta di quel giorno
    giorno: pd.Timestamp | None = None                     # giorno in esame, se diverso da oggi (decisione 47)

    @classmethod
    def crea(cls, oggi: date | str | None = None, st: Stagione | None = None, caricamento: str | None = None,
             giorno: date | str | None = None) -> "Sessione":
        st = st or stagione()
        car = None
        if caricamento:
            car = caricamenti.trova(caricamento) or _dal_dataset(caricamento, st)
            if car is None:
                raise ErroreStrumento("il file caricato non è più disponibile (il server tiene i file per due ore): ricaricalo")
            oggi = oggi or car.data
        o = pd.Timestamp(oggi or OGGI_PREDEFINITO).normalize()
        if not (st.inizio - pd.Timedelta(days=30) <= o <= st.fine + pd.Timedelta(days=30)):
            raise ErroreStrumento(f"data fuori dalla stagione: {o:%d/%m/%Y} (stagione dal {st.inizio:%d/%m/%Y} al {st.fine:%d/%m/%Y})")
        if car is not None and car.data > o:
            car = None   # un file di un giorno dopo l'oggi non si usa
        g = None
        if giorno:
            try:
                g = pd.Timestamp(giorno).normalize()
            except (ValueError, TypeError) as e:
                raise ErroreStrumento(f"giorno non riconosciuto: «{giorno}» (usa AAAA-MM-GG)") from e
            if g > o:
                raise ErroreStrumento(f"il {g:%d/%m/%Y} è dopo oggi ({o:%d/%m/%Y}): Vice non vede il futuro")
            if g < st.inizio - pd.Timedelta(days=30):
                raise ErroreStrumento(f"giorno fuori dalla stagione: {g:%d/%m/%Y}")
            if g == o:
                g = None
        return cls(o, st, car, g)

    @property
    def in_esame(self) -> pd.Timestamp:
        """Il giorno delle domande senza data: quello scelto nel calendario, altrimenti oggi."""
        return self.giorno if self.giorno is not None else self.oggi

    @property
    def chiave(self) -> str:
        """Per le cache: il giorno e, se c'è, il file caricato."""
        return (f"{self.oggi:%Y-%m-%d}" + (f"@{self.giorno:%Y-%m-%d}" if self.giorno is not None else "")
                + (f"+{self.caricamento.codice}" if self.caricamento else ""))

    def caricata(self, giorno: date | str | pd.Timestamp | None = None) -> bool:
        """Vice ha la seduta di quel giorno (decisione 54): è prima del giorno della demo, oppure c'è il suo file."""
        g = pd.Timestamp(giorno if giorno is not None else self.oggi).normalize()
        return g < GIORNO_DEMO or (self.caricamento is not None and g == self.caricamento.data)

    def visibile(self, giorno: pd.Timestamp | None = None) -> Visibile:
        g = pd.Timestamp(giorno if giorno is not None else self.oggi).normalize()
        v = self.stagione.al(g)
        if self.caricamento is not None and g == self.caricamento.data:
            return replace(v, seduta_di_oggi=self.caricamento.righe.copy())
        if not self.caricata(g):
            return senza_la_seduta(v)
        return v

    def senza_seduta_caricata(self, giorno: pd.Timestamp | None = None) -> str | None:
        """Il motivo per cui non ci sono dati di quel giorno, se è perché la seduta non è ancora caricata."""
        g = pd.Timestamp(giorno if giorno is not None else self.oggi).normalize()
        if self.caricata(g) or self.stagione.al(g).seduta_di_oggi.empty:
            return None
        return (f"la seduta del {g:%d/%m/%Y} non è ancora caricata: si carica l'export GPS di quel giorno "
                "(o il file di prova); intanto Vice conosce i dati fino al giorno prima")

    @property
    def giocatori(self) -> pd.DataFrame:
        return self.stagione.al(self.oggi).giocatori

    def data(self, testo: str | None) -> pd.Timestamp:
        """Una data scritta come AAAA-MM-GG, GG/MM/AAAA o "10 gennaio"; mai dopo l'oggi. Vuota = il giorno in esame."""
        if not testo:
            return self.in_esame
        t = _norm(testo)
        if t in ("oggi", "today"):
            return self.oggi
        if t == "ieri":
            return self.oggi - pd.Timedelta(days=1)
        m = re.fullmatch(r"(\d{1,2}) (" + "|".join(MESI) + r")(?: (\d{4}))?", t)
        senza_anno = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})", t)        # «19/04»: l'anno è quello della stagione
        nella_stagione = lambda mese: self.oggi.year if mese <= self.oggi.month else self.oggi.year - 1   # noqa: E731
        try:
            if m:
                mese = MESI.index(m.group(2)) + 1
                anno = int(m.group(3)) if m.group(3) else nella_stagione(mese)
                d = pd.Timestamp(year=anno, month=mese, day=int(m.group(1)))
            elif senza_anno:
                mese = int(senza_anno.group(2))
                d = pd.Timestamp(year=nella_stagione(mese), month=mese, day=int(senza_anno.group(1)))
            else:
                d = pd.Timestamp(pd.to_datetime(t, dayfirst="/" in t)).normalize()
        except (ValueError, TypeError) as e:
            raise ErroreStrumento(f"data non riconosciuta: «{testo}» (usa per esempio 10/01/2024)") from e
        if d > self.oggi:
            raise ErroreStrumento(f"il {d:%d/%m/%Y} è dopo oggi ({self.oggi:%d/%m/%Y}): Vice non vede il futuro")
        if d < self.stagione.inizio - pd.Timedelta(days=30):
            raise ErroreStrumento(f"il {d:%d/%m/%Y} è fuori dalla stagione (dal {self.stagione.inizio:%d/%m/%Y})")
        return d

    def giocatore(self, testo: str | int) -> int:
        """Riconosce un giocatore da nome, cognome, nome completo o numero di maglia."""
        g = self.giocatori
        t = _norm(str(testo)).lstrip("#")
        if t.isdigit():
            r = g[g["numero"] == int(t)]
            if len(r) == 1:
                return int(r["giocatore_id"].iloc[0])
            raise ErroreStrumento(f"nessun giocatore con il numero {t}")
        completi = g["nome_completo"].map(_norm)
        for serie in (completi, g["cognome"].map(_norm), g["nome"].map(_norm)):
            r = g[serie == t]
            if len(r) == 1:
                return int(r["giocatore_id"].iloc[0])
            if len(r) > 1:
                raise ErroreStrumento("più giocatori corrispondono a «%s»: %s" % (testo, ", ".join(r["nome_completo"])))
        r = g[completi.str.contains(t, regex=False)]
        if len(r) == 1:
            return int(r["giocatore_id"].iloc[0])
        if len(r) > 1:
            raise ErroreStrumento("più giocatori corrispondono a «%s»: %s" % (testo, ", ".join(r["nome_completo"])))
        raise ErroreStrumento(f"nessun giocatore «{testo}» nella rosa")

    def nome(self, giocatore_id: int) -> str:
        g = self.giocatori.set_index("giocatore_id")
        return str(g.loc[giocatore_id, "nome_completo"])
