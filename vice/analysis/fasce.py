"""M2.1 Fasce attese: il carico abituale di un giocatore in un giorno del microciclo.

Per metrica × giorno MD × gruppo, dallo storico **prima** dell'oggi:
- fascia centrale P25-P75 e fascia larga P10-P90. Descrivono **quanto è abituale** un carico: non
  sono un carico ottimale né l'obiettivo della seduta, che Vice non conosce;
- gruppo: titolari o non titolari dell'ultima partita solo a MD, MD+1 e MD+2; prima della partita
  una fascia unica (decisione 25);
- livelli: **personale** (almeno 8 sedute del giocatore in quel giorno MD e gruppo), fusa con quella
  del **ruolo**; altrimenti la fascia del ruolo, poi della **squadra**, ciascuna con almeno 6 casi
  da almeno 3 sedute diverse; sotto, nessuna fascia ("storico insufficiente"). Con meno di 6 sedute
  diverse la fascia è **provvisoria**: si mostra, ma non genera spunti.

Fusione: un'unica distribuzione pesata in cui le sedute personali pesano in tutto n / (n + 8) e
quelle del riferimento il resto; percentili e ranghi vengono dalla stessa distribuzione, quindi
sono coerenti (il P50 ha rango 50). Revisione tecnica del 22/10/2026, decisione 30.

Tolleranza per uscire dalla fascia (decisione 28): il massimo tra un minimo assoluto e una quota
della mediana della fascia. È una **tolleranza operativa**, non una stima dell'errore del GPS.
Formule e motivazioni: wiki/metodi/analisi-vice.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data.stagione import Visibile
from .comune import METRICHE, NOME_METRICA, UNITA, anagrafica, partita_ha_dati, stato_in_partita
from .evidenze import Risultato, arrotonda, data_it, evidenza, giorno_md_it

PERCENTILI = (10, 25, 50, 75, 90)
MIN_CASI = 6                  # sotto, la fascia di ruolo o di squadra non si calcola
MIN_SEDUTE = 3                # …e i casi devono venire da almeno 3 giorni diversi
MIN_SEDUTE_SPUNTI = 6         # sotto, la fascia è provvisoria: si mostra ma non genera spunti
MIN_CASI_PERSONALE = 8        # sotto, niente parte personale
K_PESO = 8                    # peso personale = n / (n + K_PESO)
GIORNI_CON_STATO = (0, 1, 2)  # decisione 25
# Tolleranza operativa (decisione 28): max(minimo assoluto, quota della mediana della fascia)
TOLLERANZA = {"td": (100, 0.03), "hsr": (10, 0.10), "spr": (5, 0.20), "acc": (2, 0.10), "dcc": (2, 0.10),
              "hmld": (30, 0.05)}

TITOLARI, NON_TITOLARI, TUTTI, SCONOSCIUTO = "titolari", "non titolari", "tutti", "sconosciuto"
POSIZIONI = ("molto sotto", "sotto", "dentro", "sopra", "molto sopra")


def gruppo(giorno_md: int, titolare) -> str:
    if giorno_md in GIORNI_CON_STATO:
        if titolare is None or titolare is pd.NA or (isinstance(titolare, float) and np.isnan(titolare)):
            return SCONOSCIUTO
        return TITOLARI if bool(titolare) else NON_TITOLARI
    return TUTTI


def con_gruppo(righe: pd.DataFrame) -> pd.DataFrame:
    out = righe.copy()
    tit = out["titolare_ultima_partita"]
    g = np.where(tit.isna(), SCONOSCIUTO, np.where(tit.fillna(False).astype(bool), TITOLARI, NON_TITOLARI))
    out["gruppo"] = np.where(out["giorno_md"].isin(GIORNI_CON_STATO), g, TUTTI)
    return out


def tolleranza(metrica: str, mediana: float) -> float:
    minimo, quota = TOLLERANZA[metrica]
    return max(minimo, quota * max(float(mediana), 0.0))


def posizione(valore: float, p10: float, p25: float, p50: float, p75: float, p90: float, metrica: str) -> str:
    """Dove cade il valore rispetto alla fascia, con la tolleranza della metrica."""
    t = tolleranza(metrica, p50)
    if valore < p10 - t:
        return "molto sotto"
    if valore < p25 - t:
        return "sotto"
    if valore > p90 + t:
        return "molto sopra"
    if valore > p75 + t:
        return "sopra"
    return "dentro"


class Distribuzione:
    """Distribuzione empirica (eventualmente pesata). Ogni valore distinto sta alla posizione
    "metà del suo peso" della cumulata (rango medio); quantili e ranghi interpolano linearmente
    tra queste posizioni, quindi sono l'uno l'inverso dell'altro."""

    def __init__(self, valori, pesi=None):
        v = np.asarray(valori, dtype=float)
        w = np.ones_like(v) if pesi is None else np.asarray(pesi, dtype=float)
        ordine = np.argsort(v, kind="stable")
        v, w = v[ordine], w[ordine]
        self.valori, inizio = np.unique(v, return_index=True)
        pesi_u = np.add.reduceat(w, inizio) if len(v) else np.array([])
        totale = pesi_u.sum()
        self.posizioni = 100.0 * (np.cumsum(pesi_u) - pesi_u / 2) / totale if len(v) else np.array([])

    def quantile(self, p: float) -> float:
        return float(np.interp(p, self.posizioni, self.valori))

    def rango(self, x: float) -> float:
        if not len(self.valori):
            return float("nan")
        if x < self.valori[0]:
            return 0.0
        if x > self.valori[-1]:
            return 100.0
        return float(np.interp(x, self.valori, self.posizioni))


def quantili(valori) -> dict:
    d = Distribuzione(valori)
    return {f"p{p}": d.quantile(p) for p in PERCENTILI}


def rango_percentile(valore: float, campioni) -> float:
    """Rango percentile (0-100) del valore nei campioni, con la stessa regola dei quantili."""
    return Distribuzione(campioni).rango(valore)


@dataclass(frozen=True)
class Fascia:
    metrica: str
    giorno_md: int
    gruppo: str
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    riferimento: str              # "ruolo" o "squadra": il livello che completa (o sostituisce) il personale
    peso_personale: float         # 0 = solo riferimento
    casi_personali: int
    casi: int                     # osservazioni distinte (le personali sono già dentro il riferimento)
    sedute: int                   # giorni diversi da cui vengono
    _dist: Distribuzione = field(repr=False, compare=False, default=None)

    @property
    def livello(self) -> str:
        return f"personale e {self.riferimento}" if self.peso_personale > 0 else self.riferimento

    @property
    def provvisoria(self) -> bool:
        return self.sedute < MIN_SEDUTE_SPUNTI

    @property
    def tolleranza(self) -> float:
        return tolleranza(self.metrica, self.p50)

    def percentile(self, valore: float) -> float:
        return self._dist.rango(valore)

    def posizione(self, valore: float) -> str:
        return posizione(valore, self.p10, self.p25, self.p50, self.p75, self.p90, self.metrica)

    def scarto(self, valore: float) -> float:
        """Di quanto il valore esce dalla fascia centrale (0 se è dentro)."""
        if valore > self.p75:
            return valore - self.p75
        if valore < self.p25:
            return valore - self.p25
        return 0.0

    def come_dict(self) -> dict:
        return {"p10": self.p10, "p25": self.p25, "p50": self.p50, "p75": self.p75, "p90": self.p90}

    def arrotondata(self) -> dict:
        """I percentili come si mostrano e si citano."""
        u = UNITA[self.metrica]
        return {k: arrotonda(x, u) for k, x in self.come_dict().items()}


class Riferimenti:
    """Lo storico raggruppato una volta sola, per calcolare in fretta molte fasce."""

    def __init__(self, storico: pd.DataFrame):
        s = con_gruppo(storico) if len(storico) else storico.assign(gruppo=pd.Series(dtype=str))
        self.n_righe = len(s)
        self._pers = self._gruppi(s, ["giocatore_id", "giorno_md", "gruppo"])
        self._ruolo = self._gruppi(s, ["ruolo", "giorno_md", "gruppo"])
        self._squadra = self._gruppi(s, ["giorno_md", "gruppo"])

    @staticmethod
    def _gruppi(s: pd.DataFrame, chiavi: list[str]) -> dict:
        if s.empty:
            return {}
        return {k: {**{m: g[m].to_numpy(dtype=float) for m in METRICHE}, "_date": g["data"].to_numpy()}
                for k, g in s.groupby(chiavi)}

    def _campioni(self, tabella: dict, chiave: tuple, gruppo_: str, metrica: str) -> tuple[np.ndarray, int]:
        """(valori, numero di giorni diversi da cui vengono)"""
        gruppi = (TITOLARI, NON_TITOLARI) if gruppo_ == SCONOSCIUTO else (gruppo_,)  # stato ignoto: insieme
        parti = [tabella[chiave + (g,)] for g in gruppi if chiave + (g,) in tabella]
        if not parti:
            return np.array([]), 0
        valori = np.concatenate([p[metrica] for p in parti])
        giorni = len(np.unique(np.concatenate([p["_date"] for p in parti])))
        return valori, giorni

    def fascia(self, giocatore_id: int, ruolo: str, giorno_md: int, gruppo_: str, metrica: str) -> Fascia | None:
        pers, _ = self._campioni(self._pers, (giocatore_id, giorno_md), gruppo_, metrica)
        (rif, giorni), nome_rif = self._campioni(self._ruolo, (ruolo, giorno_md), gruppo_, metrica), "ruolo"
        if len(rif) < MIN_CASI or giorni < MIN_SEDUTE:
            (rif, giorni), nome_rif = self._campioni(self._squadra, (giorno_md,), gruppo_, metrica), "squadra"
        if len(rif) < MIN_CASI or giorni < MIN_SEDUTE:
            return None
        peso = 0.0
        if len(pers) >= MIN_CASI_PERSONALE:
            peso = len(pers) / (len(pers) + K_PESO)
            pesi = np.concatenate([np.full(len(pers), peso / len(pers)), np.full(len(rif), (1 - peso) / len(rif))])
            dist = Distribuzione(np.concatenate([pers, rif]), pesi)
        else:
            dist = Distribuzione(rif)
        q = [dist.quantile(p) for p in PERCENTILI]
        return Fascia(metrica, giorno_md, gruppo_, *q, riferimento=nome_rif, peso_personale=peso,
                      casi_personali=int(len(pers)), casi=int(len(rif)), sedute=int(giorni), _dist=dist)


COLONNE_CLASSIFICA = ["data", "giocatore_id", "ruolo", "giorno_md", "tipo", "gruppo", "metrica", "valore",
                      "p10", "p25", "p50", "p75", "p90", "percentile", "posizione", "scarto", "tolleranza", "livello",
                      "peso_personale", "casi_personali", "casi", "sedute", "provvisoria"]


def classifica(storico: pd.DataFrame | None, seduta: pd.DataFrame, rif: Riferimenti | None = None) -> pd.DataFrame:
    """Ogni giocatore × metrica della seduta contro la sua fascia attesa (dallo storico dato).
    Una riga per giocatore × metrica; senza fascia, posizione = "senza fascia"."""
    rif = rif or Riferimenti(storico)
    s = con_gruppo(seduta)
    righe = []
    for r in s.itertuples(index=False):
        for m in METRICHE:
            valore = float(getattr(r, m))
            f = rif.fascia(r.giocatore_id, r.ruolo, int(r.giorno_md), r.gruppo, m)
            base = {"data": r.data, "giocatore_id": r.giocatore_id, "ruolo": r.ruolo, "giorno_md": int(r.giorno_md),
                    "tipo": r.tipo, "gruppo": r.gruppo, "metrica": m, "valore": valore}
            if f is None:
                righe.append(base | {"posizione": "senza fascia"})
                continue
            righe.append(base | f.come_dict() | {
                "percentile": f.percentile(valore), "posizione": f.posizione(valore), "scarto": f.scarto(valore),
                "tolleranza": f.tolleranza, "livello": f.livello, "peso_personale": f.peso_personale,
                "casi_personali": f.casi_personali, "casi": f.casi, "sedute": f.sedute, "provvisoria": f.provvisoria})
    return pd.DataFrame(righe, columns=COLONNE_CLASSIFICA)


# ---------- strumento: la fascia attesa di un giocatore ----------

def fascia_attesa(v: Visibile, giocatore_id: int, giorno_md: int | None = None) -> Risultato:
    """Il carico abituale del giocatore nel giorno MD dato (di default quello di oggi).
    A MD+1 e MD+2 conta il suo stato nell'ultima partita; a MD si danno entrambe le fasce."""
    giorno_md = v.contesto.giorno_md if giorno_md is None else giorno_md
    ana = anagrafica(v)
    nome, ruolo = ana.loc[giocatore_id, "nome_completo"], ana.loc[giocatore_id, "ruolo"]
    avvisi: list[str] = []
    if giorno_md is None:
        return Risultato("fascia_attesa", v.oggi, pd.DataFrame(), avvisi=["oggi è un giorno di pausa: nessun giorno MD"])
    if giorno_md == 0:
        gruppi = [TITOLARI, NON_TITOLARI]
    elif giorno_md in GIORNI_CON_STATO:
        partita = v.contesto.ultima_partita
        stato = stato_in_partita(v.storico, partita, [giocatore_id], partita_ha_dati(v, partita))[giocatore_id] \
            if partita is not None else None
        gruppi = [gruppo(giorno_md, stato)]
        if gruppi[0] == SCONOSCIUTO:
            avvisi.append("stato nell'ultima partita sconosciuto (partita senza dati GPS): fascia di titolari e non titolari insieme")
    else:
        gruppi = [TUTTI]
    rif = Riferimenti(v.storico)
    righe, evid = [], []
    for g in gruppi:
        for m in METRICHE:
            f = rif.fascia(giocatore_id, ruolo, giorno_md, g, m)
            if f is None:
                avvisi.append(f"{NOME_METRICA[m]}: storico insufficiente per una fascia a {giorno_md_it(giorno_md)} ({g})")
                continue
            righe.append({"giocatore_id": giocatore_id, "giorno_md": giorno_md, "gruppo": g, "metrica": m,
                          **f.come_dict(), "livello": f.livello, "casi": f.casi, "sedute": f.sedute,
                          "provvisoria": f.provvisoria})
            a = f.arrotondata()
            evid.append(evidenza(
                f"fascia/{v.oggi:%Y-%m-%d}/{giocatore_id}/{giorno_md}/{g}/{m}",
                f"Fascia storica di {nome} a {giorno_md_it(giorno_md)} ({g}): {NOME_METRICA[m]}",
                f.p50, UNITA[m], grafico=f"fascia/{giocatore_id}/{m}",
                giocatore_id=giocatore_id, giocatore=nome, giorno_md=giorno_md, gruppo=g, metrica=m,
                fascia_centrale=[a["p25"], a["p75"]], fascia_larga=[a["p10"], a["p90"]], mediana=a["p50"],
                livello=f.livello, casi=f.casi, sedute=f.sedute, provvisoria=f.provvisoria,
                calcolata_al=data_it(v.oggi)))
    return Risultato("fascia_attesa", v.oggi, pd.DataFrame(righe), evid, avvisi,
                     {"giocatore": nome, "giorno_md": giorno_md, "gruppi": gruppi})
