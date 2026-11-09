"""Pezzi comuni alle viste: giocatori come gettoni, metriche, scale degli assi, fonti.

Una vista è una **specifica dichiarativa** in JSON: dati già calcolati dal motore, testi già scritti
all'italiana, posizioni rispetto alla fascia. Il front-end ha un disegnatore per ogni `forma` e non fa
calcoli; i colori li decide il tema (chiaro o scuro) a partire dalle posizioni.
"""

from __future__ import annotations

import math

import pandas as pd

from ..agent.contesto import ErroreStrumento, Sessione
from ..analysis.comune import METRICHE, SIGLA, UNITA, anagrafica
from ..analysis.evidenze import arrotonda, con_unita, data_it, giorno_md_it, numero_it
from ..data.anagrafica import DICITURA
from ..data.stagione import Visibile

POSIZIONI = ("molto sotto", "sotto", "dentro", "sopra", "molto sopra")
SENZA_FASCIA = "senza fascia"

# nome breve per i titoli e nome dell'asse, per metrica
METRICA_VISTA = {
    "td": ("distanza totale", "metri"),
    "hsr": ("alta velocità", "metri oltre 19,8 km/h"),
    "spr": ("sprint", "metri oltre 25,2 km/h"),
    "acc": ("accelerazioni", "accelerazioni oltre 3 m/s²"),
    "dcc": ("decelerazioni", "decelerazioni oltre 3 m/s²"),
    "hmld": ("alto carico metabolico", "metri oltre 25,5 W/kg"),
}
FONTE_ZENODO = "Dati: Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0), GPS STATSports a 10 Hz."


# come l'agente o l'utente possono chiamare una metrica
ALIAS_METRICA = {
    "distanza": "td", "distanza totale": "td", "alta velocità": "hsr", "alta velocita": "hsr", "velocità": "hsr",
    "sprint": "spr", "accelerazioni": "acc", "decelerazioni": "dcc", "alto carico metabolico": "hmld",
}


def metrica(parametri: dict, predefinita: str = "hsr") -> str:
    m = str(parametri.get("metrica") or predefinita).strip().lower()
    m = ALIAS_METRICA.get(m, m)
    if m not in METRICHE:
        raise ErroreStrumento(f"metrica sconosciuta: {m} (ammesse: {', '.join(METRICHE)})")
    return m


def metriche_selezionabili() -> list[dict]:
    """I bottoni delle metriche, col significato della sigla e cosa misura per il suggerimento (decisione 52)."""
    from ..agent.sigle import SIGLE
    return [{"id": m, "sigla": SIGLA[m], "nome": METRICA_VISTA[m][0], "significato": SIGLE[SIGLA[m]][0],
             "misura": METRICA_VISTA[m][1]} for m in METRICHE]


def gettoni(v: Visibile) -> dict[int, dict]:
    """giocatore_id → gettone: nome, cognome, numero di maglia, ruolo (nomi di fantasia)."""
    ana = anagrafica(v)
    out = {}
    for gid, r in ana.iterrows():
        nome = str(r["nome_completo"])
        out[int(gid)] = {"id": int(gid), "nome": nome, "cognome": nome.split(" ", 1)[-1],
                         "numero": int(r["numero"]), "ruolo": str(r["ruolo"])}
    return out


def asse(valori: list[float], margine: float = 1.12) -> dict:
    """Scala da 0 con un passo "tondo" e un po' di spazio a destra per le etichette."""
    alto = max([float(x) for x in valori if x is not None and not math.isnan(float(x))] or [1.0]) * margine
    grezzo = alto / 6
    potenza = 10 ** math.floor(math.log10(grezzo)) if grezzo > 0 else 1
    passo = next(p * potenza for p in (1, 2, 2.5, 5, 10) if p * potenza >= grezzo)
    massimo = math.ceil(alto / passo) * passo
    return {"min": 0, "max": arrotonda(massimo, "n") if passo >= 1 else massimo, "passo": passo if passo < 1 else int(passo)}


def testo_valore(x, unita: str) -> str:
    return con_unita(x, unita) if x is not None and not (isinstance(x, float) and math.isnan(x)) else "nessun dato"


def fascia_testi(r, u: str) -> list[str]:
    """Le righe di dettaglio di una fascia, per il passaggio del mouse."""
    return [f"fascia centrale P25-P75: {numero_it(r.p25, u)}-{con_unita(r.p75, u)}",
            f"fascia larga P10-P90: {numero_it(r.p10, u)}-{con_unita(r.p90, u)}",
            f"mediana: {con_unita(r.p50, u)}",
            f"percentile nella sua storia: {numero_it(r.percentile, 'percentile')}",
            f"fascia {r.livello}, {int(r.casi)} casi" + (" (provvisoria)" if bool(r.provvisoria) else "")]


def giocatore_id(s: Sessione, parametri: dict) -> int | None:
    """Il giocatore della vista. `giocatore_id` è il codice interno (dagli strumenti e dall'interfaccia);
    `giocatore` è ciò che scrive l'utente o l'agente: nome, cognome o numero di maglia. Mai mescolati:
    un codice letto come numero di maglia mostrerebbe un altro giocatore (Cortese ha il codice 9, la
    maglia 9 è di Basile)."""
    if parametri.get("giocatore_id") not in (None, ""):
        try:
            gid = int(parametri["giocatore_id"])
        except (TypeError, ValueError) as e:
            raise ErroreStrumento(f"codice del giocatore non valido: {parametri['giocatore_id']}") from e
        if gid not in set(s.giocatori["giocatore_id"]):
            raise ErroreStrumento(f"nessun giocatore con il codice {gid}")
        return gid
    if parametri.get("giocatore") not in (None, ""):
        return s.giocatore(str(parametri["giocatore"]))
    return None


def giorno(s: Sessione, parametri: dict) -> pd.Timestamp:
    return s.data(parametri.get("data"))


def intestazione_giorno(g: pd.Timestamp, s: Sessione) -> str:
    """"oggi" oppure "il 10/01" per i titoli."""
    return "oggi" if g == s.oggi else f"il {data_it(g)[:5]}"


def unita(m: str) -> str:
    return UNITA[m]


def dicitura() -> str:
    return DICITURA


__all__ = ["POSIZIONI", "SENZA_FASCIA", "METRICA_VISTA", "FONTE_ZENODO", "metrica",
           "metriche_selezionabili", "gettoni", "giocatore_id", "asse", "testo_valore", "fascia_testi", "giorno",
           "intestazione_giorno", "unita", "dicitura", "giorno_md_it", "data_it", "arrotonda"]
