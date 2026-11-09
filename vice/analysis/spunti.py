"""M2.10 Spunti per lo staff (decisione D4): una tabella di regole deterministiche → frasi base.

Ogni regola ha soglie esplicite, una priorità e una frase che usa solo numeri presi dalle evidenze
citate (lo controlla un test). Gli spunti propongono cosa **valutare, verificare o approfondire**:
"Valutare se serve…" (decisione 26), mai prescrizioni. Non nascono da fasce provvisorie.
- Al massimo 3 per report e 2 della stessa regola; prima il contesto di squadra, poi i singoli.
- Report della seduta: solo dati nuovi di oggi (o la chiusura della finestra postpartita).
  Report della settimana e del giocatore: anche i giorni precedenti, con la data nella frase.
- L'elenco completo dei candidati resta consultabile (`candidati`).
Revisione tecnica del 22/10/2026: wiki/metodi/analisi-vice.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from ..data.stagione import Visibile
from .comune import NOME_METRICA, UNITA, tutte_le_righe
from .evidenze import Risultato, con_unita, data_it, giorno_md_it, numero_it
from .fasce import Riferimenti, classifica
from .seduta import con_nomi

MAX_SPUNTI = 3
MAX_PER_REGOLA = 2
SEDUTE_CONSECUTIVE = 3
IN_LETTERE = {2: "due", 3: "tre", 4: "quattro", 5: "cinque"}   # i conteggi nelle frasi non sono numeri da verificare

# La tabella delle regole: è anche ciò che la wiki e l'agente mostrano.
REGOLE = [
    {"id": "seduta_squadra", "priorita": 1, "report": ("seduta", "settimana"),
     "quando": "allenamento con mediana di squadra di distanza totale o HSR «molto sopra» o «molto sotto» le mediane dello "
               "stesso giorno MD nelle settimane regolari passate (almeno 6)",
     "frase": "Verificare se il programma prevedeva questo carico: …"},
    {"id": "compensazione_gruppo", "priorita": 1, "report": ("seduta", "settimana"),
     "quando": "dopo la partita, almeno 3 non titolari valutati e almeno la metà di loro con HSR postpartita «molto sotto» "
               "la somma dei loro riferimenti giornalieri: è il programma, non il singolo",
     "frase": "Verificare se il programma postpartita prevedeva meno alta velocità del solito: …"},
    {"id": "rifinitura", "priorita": 2, "report": ("seduta", "giocatore"),
     "quando": "seduta di MD-1 con distanza totale o HSR «molto sopra» (oltre il P90 della sua fascia più la tolleranza)",
     "frase": "Verificare se il carico di MD-1 di {giocatore} era previsto: …"},
    {"id": "compensazione", "priorita": 2, "report": ("seduta", "settimana", "giocatore"),
     "quando": "non titolare, finestra MD+1/MD+2 chiusa: HSR postpartita «molto sotto» la somma dei P10 dei suoi riferimenti "
               "giornalieri (meno la tolleranza), sui giorni con dati; non se tra partita e postpartita ha già superato il 60% "
               "del suo HSR di riferimento (decisione 27). Nel report della seduta solo nella prima seduta dopo la chiusura",
     "frase": "Valutare se serve un richiamo per {giocatore}: …"},
    {"id": "velocita", "priorita": 3, "report": ("seduta", "settimana", "giocatore"),
     "quando": "a MD-2 o MD-1, finestra MD-4…MD-2 conclusa, almeno un giorno con dati: sprint registrato nullo o sotto i 10 m "
               "per chi di solito in quei giorni ne fa almeno 30, oppure sprint o HSR «molto sotto» la somma dei riferimenti",
     "frase": "Valutare se serve uno stimolo di velocità per {giocatore}: …"},
    {"id": "postpartita_titolari", "priorita": 4, "report": ("seduta", "settimana", "giocatore"),
     "quando": "titolare a MD+1 o MD+2 con distanza totale o HSR «molto sopra» la fascia dei titolari",
     "frase": "Verificare il carico postpartita registrato per {giocatore}: … Il dato non misura lo stato di recupero."},
    {"id": "consecutive", "priorita": 5, "report": ("seduta", "settimana", "giocatore"),
     "quando": f"{SEDUTE_CONSECUTIVE} allenamenti di fila fuori dalla fascia centrale nella stessa direzione (distanza totale "
               "o HSR), ciascuno con le fasce del suo giorno; nel report della seduta solo se oggi è uno dei tre",
     "frase": "Approfondire con lo staff lo scostamento di {giocatore}: …"},
]
PRIORITA = {r["id"]: r["priorita"] for r in REGOLE}


@dataclass
class Spunto:
    regola: str
    testo: str
    evidenze: list[str]
    giocatore_id: int | None = None
    giocatore: str | None = None
    gravita: float = 0.0          # per ordinare a parità di priorità: quanto si è lontani dal solito
    priorita: int = field(init=False)

    def __post_init__(self):
        self.priorita = PRIORITA[self.regola]

    def to_dict(self) -> dict:
        return asdict(self)


def _m(x, metrica) -> str:
    return con_unita(x, UNITA[metrica])


def _tra(a, b, metrica) -> str:
    """240, 400 → "240-400 m"."""
    return f"{numero_it(a, UNITA[metrica])}-{con_unita(b, UNITA[metrica])}"


def _quando(data, oggi) -> str:
    return "oggi" if pd.Timestamp(data) == pd.Timestamp(oggi) else f"il {data_it(data)}"


def _dati_per(sedute: int, sedute_squadra: int) -> str:
    return f" (dati per {sedute} sedute su {sedute_squadra})" if sedute < sedute_squadra else ""


def _non_provvisorie(t: pd.DataFrame) -> pd.DataFrame:
    return t[~t["provvisoria"].fillna(True).astype(bool)] if "provvisoria" in t else t.iloc[:0]


# ---------- le regole ----------

def _seduta_squadra(r: Risultato, tipo: str) -> list[Spunto]:
    t = r.tabella
    if t.empty:
        return []
    t = _non_provvisorie(t[(t["tipo"] == "allenamento") & t["metrica"].isin(["td", "hsr"])
                           & t["posizione"].isin(["molto sopra", "molto sotto"])])
    if tipo == "seduta":
        t = t[t["data"] == r.oggi]
    out = []
    for x in t.itertuples():
        chi = "" if x.gruppo == "tutti" else f" dei {x.gruppo}"
        out.append(Spunto("seduta_squadra",
                          f"Verificare se il programma prevedeva questo carico: la {NOME_METRICA[x.metrica]} mediana{chi} "
                          f"registrata {_quando(x.data, r.oggi)} è {_m(x.mediana_squadra, x.metrica)}, contro i "
                          f"{_m(x.p50, x.metrica)} delle sedute storiche di {giorno_md_it(x.giorno_md)}.",
                          [f"settimana/{x.data:%Y-%m-%d}/{x.gruppo}/{x.metrica}"], gravita=abs(float(x.percentile) - 50)))
    return out


def _compensazione(r: Risultato, tipo: str) -> list[Spunto]:
    s = r.sintesi
    if r.tabella.empty or s.get("finestra_aperta") or (tipo == "seduta" and not s.get("appena_chiusa")):
        return []   # nel report della seduta se ne parla una volta, quando la finestra si chiude
    out = []
    data, pid = data_it(s["partita"]), f"{s['partita']:%Y-%m-%d}"
    gruppo = bool(s.get("sotto_di_gruppo")) and tipo != "giocatore"
    if gruppo:
        t = r.tabella[r.tabella["esito"] == "molto sotto il solito"]
        g = r.evidenza(f"compensazione/{pid}/gruppo/hsr").contesto
        out.append(Spunto("compensazione_gruppo",
                          f"Verificare se il programma postpartita prevedeva meno alta velocità del solito: dopo la partita "
                          f"del {data}, {s['molto_sotto']} non titolari su {s['valutati']} valutati sono molto sotto la loro "
                          f"fascia storica di HSR (mediana {_m(g['hsr_mediano_molto_sotto'], 'hsr')}, contro "
                          f"{_m(g['riferimento_mediano_molto_sotto'], 'hsr')}).",
                          [f"compensazione/{pid}/gruppo/hsr"] + [f"compensazione/{pid}/{gid}/hsr" for gid in t["giocatore_id"]],
                          gravita=3.0))
    for x in r.tabella.itertuples():
        if x.esito != "molto sotto il solito" or x.coperto_dalla_partita or gruppo:
            continue
        if bool(x.hsr_provvisoria):     # c'è sempre: l'esito "molto sotto" richiede la somma dei riferimenti
            continue
        if x.riga_partita:
            partita = f"; con la partita arriva al {numero_it(x.totale_hsr_pct, '%')}% del suo HSR di riferimento"
        else:
            partita = "; della partita non ci sono dati"
        out.append(Spunto("compensazione",
                          f"Valutare se serve un richiamo per {x.giocatore}: non è partito titolare il {data} e nelle sedute "
                          f"postpartita registrate ha fatto {_m(x.post_hsr, 'hsr')} di HSR"
                          f"{_dati_per(x.sedute, x.sedute_squadra)}, sotto la sua fascia storica "
                          f"({_tra(x.hsr_p25, x.hsr_p75, 'hsr')}){partita}.",
                          [f"compensazione/{pid}/{x.giocatore_id}/hsr"], x.giocatore_id, x.giocatore,
                          gravita=float(1 - x.post_hsr / x.hsr_p50) if x.hsr_p50 else 1.0))
    return out


def _rifinitura(r: Risultato) -> list[Spunto]:
    t = r.tabella
    if t.empty or r.sintesi.get("giorno_md") != -1:
        return []
    out = []
    for x in _non_provvisorie(t[t["metrica"].isin(["td", "hsr"]) & (t["posizione"] == "molto sopra")]).itertuples():
        out.append(Spunto("rifinitura",
                          f"Verificare se il carico di MD-1 di {x.giocatore} era previsto: oggi {_m(x.valore, x.metrica)} di "
                          f"{NOME_METRICA[x.metrica]}, oltre la fascia storica delle sue rifiniture (fino a {_m(x.p90, x.metrica)}).",
                          [f"seduta/{x.data:%Y-%m-%d}/{x.giocatore_id}/{x.metrica}"], x.giocatore_id, x.giocatore,
                          gravita=float(x.percentile)))
    return out


def _velocita(r: Risultato, giorno_md: int | None) -> list[Spunto]:
    t = r.tabella
    if t.empty or not r.sintesi.get("finestra_completa") or giorno_md not in (-2, -1):
        return []
    out = []
    data, pid = data_it(r.sintesi["partita"]), f"{r.sintesi['partita']:%Y-%m-%d}"
    for x in t.itertuples():
        if x.copertura not in ("completa", "parziale") or pd.isna(getattr(x, "spr_p50", float("nan"))):
            continue
        if bool(x.spr_provvisoria) or bool(x.hsr_provvisoria):
            continue
        # sprint_registrato è "nullo", "molto basso" o NaN: un NaN in Python vale vero, quindi si guarda notna
        # (difetto trovato il 28/10/2026 dalla taratura degli avvisi: segnalava tutti i giocatori)
        if not (pd.notna(x.sprint_registrato) or x.spr_posizione == "molto sotto" or x.hsr_posizione == "molto sotto"):
            continue
        mancanza = max(1 - x.spr / x.spr_p50 if x.spr_p50 else 0, 1 - x.hsr / x.hsr_p50 if x.hsr_p50 else 0)
        out.append(Spunto("velocita",
                          f"Valutare se serve uno stimolo di velocità per {x.giocatore}: da MD-4 a MD-2 ha registrato "
                          f"{_m(x.spr, 'spr')} di sprint e {_m(x.hsr, 'hsr')} di HSR{_dati_per(x.sedute, x.sedute_squadra)}, "
                          f"contro un riferimento di {_m(x.spr_p50, 'spr')} e {_m(x.hsr_p50, 'hsr')} per quei giorni, "
                          f"prima della partita del {data}.",
                          [f"velocita/{pid}/{x.giocatore_id}/spr", f"velocita/{pid}/{x.giocatore_id}/hsr"],
                          x.giocatore_id, x.giocatore, gravita=float(mancanza)))
    return out


def _postpartita_titolari(r: Risultato, tipo: str) -> list[Spunto]:
    t = r.altre.get("titolari_postpartita", pd.DataFrame())
    if t.empty:
        return []
    t = _non_provvisorie(t[t["metrica"].isin(["td", "hsr"]) & (t["posizione"] == "molto sopra")])
    if tipo == "seduta":
        t = t[t["data"] == r.oggi]
    out = []
    for x in t.itertuples():
        out.append(Spunto("postpartita_titolari",
                          f"Verificare il carico postpartita registrato {_quando(x.data, r.oggi)} per {x.giocatore}: "
                          f"{_m(x.valore, x.metrica)} di {NOME_METRICA[x.metrica]} a {giorno_md_it(x.giorno_md)}, oltre la "
                          f"fascia storica dei titolari (fino a {_m(x.p90, x.metrica)}). Il dato non misura lo stato di recupero.",
                          [f"seduta/{x.data:%Y-%m-%d}/{x.giocatore_id}/{x.metrica}"], x.giocatore_id, x.giocatore,
                          gravita=float(x.percentile)))
    return out


def ultime_sedute_classificate(v: Visibile, n: int = SEDUTE_CONSECUTIVE) -> pd.DataFrame:
    """Gli ultimi n allenamenti della squadra fino a oggi, ognuno con le fasce del suo giorno."""
    righe = tutte_le_righe(v)
    allen = righe[righe["tipo"] == "allenamento"]
    date = sorted(allen["data"].unique())[-n:]
    parti = []
    for d in date:
        storico = righe[righe["data"] < d]
        parti.append(classifica(storico, allen[allen["data"] == d], Riferimenti(storico)))
    return con_nomi(pd.concat(parti, ignore_index=True), v) if parti else pd.DataFrame()


def _consecutive(t: pd.DataFrame, oggi: pd.Timestamp, tipo: str) -> list[Spunto]:
    if t.empty or t["data"].nunique() < SEDUTE_CONSECUTIVE:
        return []
    if tipo == "seduta" and oggi not in set(t["data"]):
        return []   # nessun allenamento nuovo oggi: niente da aggiungere
    out = []
    for (gid, m), g in t[t["metrica"].isin(["td", "hsr"])].groupby(["giocatore_id", "metrica"]):
        g = g.sort_values("data")
        if len(g) < SEDUTE_CONSECUTIVE or g["provvisoria"].fillna(True).astype(bool).any():
            continue   # ha saltato uno degli allenamenti, o una fascia è provvisoria
        for verso, pos in (("sotto", ("sotto", "molto sotto")), ("sopra", ("sopra", "molto sopra"))):
            if g["posizione"].isin(pos).all():
                nome = g["giocatore"].iloc[0]
                date = [data_it(d) for d in g["data"]]
                elenco = ", ".join(date[:-1]) + " e " + date[-1]
                out.append(Spunto("consecutive",
                                  f"Approfondire con lo staff lo scostamento di {nome}: negli ultimi {IN_LETTERE[len(g)]} "
                                  f"allenamenti ({elenco}) la {NOME_METRICA[m]} è rimasta {verso} la sua fascia storica.",
                                  [f"seduta/{d:%Y-%m-%d}/{gid}/{m}" for d in g["data"]], gid, nome,
                                  gravita=float((g["percentile"] - 50).abs().mean())))
    return out


def candidati(v: Visibile, analisi: dict[str, Risultato], tipo: str = "seduta", giocatore_id: int | None = None,
              ultime_sedute: pd.DataFrame | None = None) -> list[Spunto]:
    """Tutti gli spunti che le regole del tipo di report fanno nascere, in ordine di priorità."""
    attive = {r["id"] for r in REGOLE if tipo in r["report"]}
    cand: list[Spunto] = []
    if "seduta_squadra" in attive and "forma_settimana" in analisi:
        cand += _seduta_squadra(analisi["forma_settimana"], tipo)
    if "compensazione" in analisi:
        cand += [s for s in _compensazione(analisi["compensazione"], tipo) if s.regola in attive]
    if "rifinitura" in attive and "seduta" in analisi:
        cand += _rifinitura(analisi["seduta"])
    if "velocita" in attive and "esposizione_velocita" in analisi:
        cand += _velocita(analisi["esposizione_velocita"], v.contesto.giorno_md)
    if "postpartita_titolari" in attive and "compensazione" in analisi:
        cand += _postpartita_titolari(analisi["compensazione"], tipo)
    if "consecutive" in attive:
        cand += _consecutive(ultime_sedute if ultime_sedute is not None else ultime_sedute_classificate(v), v.oggi, tipo)
    if any(s.regola == "compensazione_gruppo" for s in cand):
        # lo stesso fatto visto dalla curva di squadra: basta lo spunto sul postpartita
        cand = [s for s in cand if not (s.regola == "seduta_squadra" and "/non titolari/" in s.evidenze[0])]
    if giocatore_id is not None:
        cand = [s for s in cand if s.giocatore_id == giocatore_id]
    cand.sort(key=lambda s: (s.priorita, -s.gravita))
    out, visti = [], set()
    for s in cand:                       # una volta per regola e giocatore (per la squadra, per frase)
        chiave = (s.regola, s.giocatore_id if s.giocatore_id is not None else s.testo)
        if chiave not in visti:
            visti.add(chiave)
            out.append(s)
    return out


def seleziona(cand: list[Spunto]) -> list[Spunto]:
    """I primi 3, al massimo 2 per regola."""
    scelti, per_regola = [], {}
    for s in cand:
        if per_regola.get(s.regola, 0) >= MAX_PER_REGOLA:
            continue
        scelti.append(s)
        per_regola[s.regola] = per_regola.get(s.regola, 0) + 1
        if len(scelti) == MAX_SPUNTI:
            break
    return scelti


def spunti(v: Visibile, analisi: dict[str, Risultato], tipo: str = "seduta", giocatore_id: int | None = None,
           ultime_sedute: pd.DataFrame | None = None) -> list[Spunto]:
    return seleziona(candidati(v, analisi, tipo, giocatore_id, ultime_sedute))
