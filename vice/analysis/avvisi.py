"""Gli avvisi di Vice (decisione 53): le segnalazioni che Vice dà da sé, senza che gli si chieda.

Proposta e regole: wiki/metodi/avvisi.md. Nove famiglie, ciascuna con un testo scritto dal codice (come gli
spunti) e numeri presi dai dati; mai giudizi di forma, di rendimento o di rischio. Le prime tre riusano le
regole degli spunti (spunti.py), le altre sono nuove. Le soglie in SOGLIE sono **iniziali**: si tarano su
tutta la stagione con scripts/taratura_avvisi.py.

Tutto è calcolato "come quel giorno": la classificazione di ogni seduta usa solo lo storico precedente, e un
avviso del giorno X usa solo le sedute fino a X. Gli avvisi non hanno memoria: "una volta sola" vuol dire
che un avviso nasce il giorno in cui la sua condizione diventa vera (il giorno prima non lo era). Cosa succede
dopo (aggiornato, chiuso, scaduto) e come si mostrano nell'app: vice/analysis/archivio_avvisi.py (decisione 54).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from ..data.stagione import Visibile
from .comune import UNITA, anagrafica, date_partite, tutte_le_righe
from .evidenze import con_unita, data_it, giorno_md_it, numero_it
from .fasce import Riferimenti, classifica, tolleranza
from .settimana import compensazione, esposizione_velocita, forma_settimana
from .seduta import seduta
from .spunti import IN_LETTERE, candidati

# famiglia → (priorità, nome); la qualità del dato sta a parte (0)
FAMIGLIE = {
    "dato": (0, "Qualità del dato"),
    "richiamo": (1, "Richiamo dopo la partita"),
    "velocita": (2, "Alta velocità prima della partita"),
    "insolito": (3, "Carico insolito"),
    "settimana": (4, "Settimana sopra o sotto il solito"),
    "calo": (5, "Calo persistente"),
    "rientro": (6, "Rientro dopo un'assenza"),
    "reparto": (7, "Scarto di reparto"),
    "positivo": (8, "Note positive"),
}

SOGLIE = {
    "insolito_giorni": (-3, -2, -1),   # carico insolito del singolo: vicino alla partita…
    "insolito_oltre_p90": {"td": 0.25, "hsr": 0.25, "spr": 0.5, "dcc": 0.25},   # …oltre il P90 della sua fascia di tanto
    "settimana_min": 6,             # settimana sopra/sotto: almeno 6 settimane passate per il suo solito…
    "settimana_fattore": 1.3,       # …e la sua quota rispetto ai compagni oltre il suo P90 (o sotto il P10) di un altro 30%
    "settimana_metriche": ("td", "hsr"),   # lo sprint prima della partita ha già il suo avviso (famiglia 2)
    "insolito_squadra": 3,          # 3 o più giocatori insoliti nello stesso giorno: un solo avviso, è il programma
    "calo_giorni": 14,              # calo persistente: nelle ultime 2 settimane…
    "calo_sedute": 3,               # …almeno 3 sedute sotto il suo solito, con la squadra nella norma…
    "calo_quota": 0.6,              # …e almeno il 60% delle sue sedute confrontabili…
    "calo_percentile": 15,          # …con almeno una «molto sotto» o il percentile mediano di quelle sedute fino a 15
    "tendenza_recenti": 28,         # tendenza lunga: ultime 4 settimane…
    "tendenza_prima": (56, 84),     # …contro 8-12 settimane prima
    "tendenza_scarto": -25.0,       # scarto mediano in %
    "tendenza_min": 4,              # sedute in ciascun periodo
    "rientro_sedute": 3,            # rientro: almeno 3 sedute di squadra di fila senza dati
    "reparto_giorni": 14,           # scarto di reparto: ultime 2 settimane…
    "reparto_sedute": 4,            # …almeno 4 sedute condivise…
    "reparto_quota": 0.75,          # …e meno di tutti i compagni in almeno 3 su 4
    "reparto_minimo": {"hsr": 100, "spr": 30},   # sotto questi metri il reparto non fa quella cosa: niente avviso
    "positivo_partite": 2,          # in partita: due gare di fila da titolare sopra il suo solito
    "dato_sedute": 2,               # qualità del dato: due sedute di fila senza dati
    "dato_impossibile": {"td": 16000, "hsr": 3000, "spr": 1500},   # metri in una seduta: oltre, è un errore del file
}
# nell'app (decisione 54): gli avvisi che chiedono un'azione restano «da guardare»; rientri e note positive informano;
# la qualità del dato sta a parte
CATEGORIE = {"dato": "dato", "rientro": "informa", "positivo": "informa"}
MAX_AL_GIORNO = 3
MAX_NEL_RIASSUNTO = 5
METRICHE_CARICO = ("td", "hsr", "spr")
BASSO = ("sotto", "molto sotto")
RUOLI_PLURALE = {"difensore centrale": "difensori centrali", "terzino": "terzini", "centrocampista": "centrocampisti",
                 "esterno": "esterni", "attaccante": "attaccanti"}


@dataclass
class Avviso:
    famiglia: str
    data: pd.Timestamp
    testo: str
    giocatore_id: int | None = None
    giocatore: str | None = None
    riassunto: bool = False          # True: va nel riassunto settimanale, non tra gli avvisi del giorno
    gravita: float = 0.0             # per ordinare a parità di priorità
    evidenze: list[str] = field(default_factory=list)
    metriche: list[str] = field(default_factory=list)   # le misure di cui parla: identità dell'avviso e grafico da aprire
    chiude: str | None = None        # nota positiva: chiude il «calo» o il «rientro» aperto dello stesso giocatore
    urgente: bool = False            # qualità del dato: un valore impossibile, da vedere subito (in testa al report)

    @property
    def priorita(self) -> int:
        return FAMIGLIE[self.famiglia][0]

    @property
    def categoria(self) -> str:
        """«azione» (da guardare), «informa» (rientri e note positive) o «dato»."""
        return CATEGORIE.get(self.famiglia, "azione")

    @property
    def id(self) -> str:
        """Stabile tra un calcolo e l'altro: lo usa il «Visto» salvato nel browser."""
        chiave = f"{self.data:%Y-%m-%d}|{self.famiglia}|{self.giocatore_id}|{self.riassunto}|{self.testo}"
        return hashlib.sha1(chiave.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self) | {"id": self.id, "priorita": self.priorita, "categoria": self.categoria,
                               "nome_famiglia": FAMIGLIE[self.famiglia][1], "data": f"{self.data:%Y-%m-%d}"}


# ---------- la classificazione di tutte le sedute, ognuna con le fasce del suo giorno ----------

def _classifica_giorno(righe: pd.DataFrame, d) -> pd.DataFrame:
    storico = righe[righe["data"] < d]
    c = classifica(storico, righe[righe["data"] == d], Riferimenti(storico))
    c["solida"] = (c["posizione"] != "senza fascia") & ~c["provvisoria"].fillna(True).astype(bool)
    return c


def classificazione(righe: pd.DataFrame) -> pd.DataFrame:
    """Ogni giocatore × seduta × metrica contro la sua fascia, calcolata con lo storico di prima di quel giorno."""
    return pd.concat([_classifica_giorno(righe, d) for d in sorted(righe["data"].unique())], ignore_index=True)


def con_la_seduta(c: pd.DataFrame, righe: pd.DataFrame, giorno) -> pd.DataFrame:
    """La classificazione `c` dei giorni prima di `giorno`, più la seduta di quel giorno presa da `righe` (per
    esempio quella di un file caricato): serve a calcolare gli avvisi di un giorno senza rifare tutta la stagione."""
    g = pd.Timestamp(giorno).normalize()
    prima = c[c["data"] < g]
    if righe[righe["data"] == g].empty:
        return prima
    return pd.concat([prima, _classifica_giorno(righe, g)], ignore_index=True)


def _contesto_squadra(c: pd.DataFrame) -> pd.Series:
    """Percentile mediano della squadra per seduta, metrica e gruppo (solo fasce solide)."""
    s = c[c["solida"]]
    return s.groupby(["data", "metrica", "gruppo"])["percentile"].median()


LETTERE = IN_LETTERE | {6: "sei", 7: "sette", 8: "otto", 9: "nove", 10: "dieci"}


def _quante(n: int) -> str:
    return LETTERE.get(n, str(n))


def _elenco(cose: list[str]) -> str:
    return cose[0] if len(cose) == 1 else ", ".join(cose[:-1]) + " e " + cose[-1]


def _date(date) -> str:
    return _elenco([data_it(d)[:5] for d in sorted(date)])


def _il(x: float) -> str:
    """«il 64%», ma «l'80%», «l'8%», «l'11%»."""
    t = numero_it(x, "%")
    return f"l'{t}%" if t.startswith("8") or t in ("1", "11") or t.startswith(("1,", "11,")) else f"il {t}%"


def _nome_m(m: str) -> str:
    return {"td": "distanza totale", "hsr": "alta velocità", "spr": "sprint", "acc": "accelerazioni",
            "dcc": "decelerazioni", "hmld": "HMLD"}[m]


# ---------- 1-3: dalle regole degli spunti ----------

METRICHE_TUTTE = ("td", "hsr", "spr", "acc", "dcc", "hmld")


def _metriche_di(evidenze) -> list[str]:
    """Le misure nominate dalle evidenze (l'ultimo pezzo dell'identificativo: «…/12/hsr»)."""
    trovate = {e.rsplit("/", 1)[-1] for e in evidenze}
    return [m for m in METRICHE_TUTTE if m in trovate]


# la rifinitura (MD-1) passa per il carico insolito, con la stessa soglia degli altri giorni
DAGLI_SPUNTI = {"compensazione": "richiamo", "compensazione_gruppo": "richiamo", "velocita": "velocita",
                "seduta_squadra": "insolito", "postpartita_titolari": "insolito"}


def _dagli_spunti(v: Visibile, allen: pd.DataFrame) -> list[Avviso]:
    if v.seduta_di_oggi.empty:
        return []
    analisi = {"seduta": seduta(v), "forma_settimana": forma_settimana(v), "esposizione_velocita": esposizione_velocita(v),
               "compensazione": compensazione(v)}
    out = []
    for s in candidati(v, analisi, "seduta", ultime_sedute=pd.DataFrame()):
        fam = DAGLI_SPUNTI.get(s.regola)
        if fam is None:
            continue
        # l'alta velocità si segnala una volta: a MD-1 solo se a MD-2 non c'era un allenamento
        if fam == "velocita" and v.contesto.giorno_md == -1 and (v.oggi - pd.Timedelta(days=1)) in set(allen["data"]):
            continue
        out.append(Avviso(fam, v.oggi, s.testo, s.giocatore_id, s.giocatore, gravita=s.gravita, evidenze=list(s.evidenze),
                          metriche=_metriche_di(s.evidenze)))
    # tanti giocatori senza alta velocità prima della stessa partita: un solo avviso, con i nomi
    vel = [a for a in out if a.famiglia == "velocita" and a.giocatore_id is not None]
    if len(vel) >= SOGLIE["insolito_squadra"]:
        partita = v.contesto.prossima_partita
        out = [a for a in out if a not in vel] + [Avviso(
            "velocita", v.oggi,
            f"Valutare se serve uno stimolo di velocità per {_quante(len(vel))} giocatori ({_elenco(sorted(a.giocatore for a in vel))}): "
            f"da MD-4 a MD-2 hanno registrato poco sprint o poca alta velocità rispetto al loro solito"
            + (f", prima della partita del {data_it(partita)[:5]}." if partita is not None else "."),
            gravita=float(len(vel)), evidenze=[e for a in vel for e in a.evidenze],
            metriche=sorted({m for a in vel for m in a.metriche}, key=METRICHE_TUTTE.index))]
    return out


# ---------- 3: carico insolito del singolo ----------

def _insolito(c: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    soglie = SOGLIE["insolito_oltre_p90"]
    t = c[(c["data"] == oggi) & (c["tipo"] == "allenamento") & c["solida"] & c["metrica"].isin(list(soglie))
          & c["giorno_md"].isin(SOGLIE["insolito_giorni"])]
    per_giocatore: dict[int, list[tuple]] = {}
    for r in t.itertuples():
        if r.valore > r.p90 * (1 + soglie[r.metrica]) and r.valore > r.p90 + r.tolleranza:
            per_giocatore.setdefault(int(r.giocatore_id), []).append((r, False))
    if len(per_giocatore) >= SOGLIE["insolito_squadra"]:
        md = giorno_md_it(next(iter(per_giocatore.values()))[0][0].giorno_md)
        return [Avviso("insolito", oggi, f"Verificare se la seduta di oggi ({md}) era prevista più carica del solito: "
                       f"{_quante(len(per_giocatore))} giocatori sono molto oltre la loro fascia larga "
                       f"({_elenco(sorted(nomi[g] for g in per_giocatore))}).", gravita=float(len(per_giocatore)),
                       evidenze=[f"seduta/{oggi:%Y-%m-%d}/{g}/{r.metrica}" for g, voci in per_giocatore.items() for r, _ in voci],
                       metriche=[m for m in METRICHE_TUTTE if any(r.metrica == m for voci in per_giocatore.values() for r, _ in voci)])]
    out = []
    for gid, voci in per_giocatore.items():
        pezzi = [f"{_nome_m(r.metrica)} {con_unita(r.valore, UNITA[r.metrica])} "
                 + ("(il più alto che abbia mai registrato in quel giorno della settimana)" if rec
                    else f"(fascia larga {numero_it(r.p10, UNITA[r.metrica])}-{con_unita(r.p90, UNITA[r.metrica])})")
                 for r, rec in voci]
        md = giorno_md_it(voci[0][0].giorno_md)
        out.append(Avviso("insolito", oggi, f"Verificare se il carico di {nomi[gid]} a {md} era previsto: {_elenco(pezzi)}.",
                          gid, nomi[gid], gravita=max(r.valore / r.p90 for r, _ in voci),
                          evidenze=[f"seduta/{oggi:%Y-%m-%d}/{gid}/{r.metrica}" for r, _ in voci],
                          metriche=[r.metrica for r, _ in voci]))
    return out


# ---------- 4: settimana sopra o sotto il solito ----------

def _quote(v: Visibile, rif: pd.Series, settimana, fine: pd.Timestamp, righe: pd.DataFrame) -> pd.DataFrame | None:
    """Per una settimana tagliata a `fine`: la quota della sua partita di ciascuno (allenamenti finora / riferimento) e
    la stessa quota rispetto alla mediana della squadra. Solo chi ha fatto tutte le sedute della squadra."""
    a = righe[(righe["tipo"] == "allenamento") & settimana.contiene(righe["data"]) & (righe["data"] <= fine)]
    if a.empty:
        return None
    n = a["data"].nunique()
    sedute = a.groupby("giocatore_id").size()
    somme = a.groupby("giocatore_id")[list(METRICHE_CARICO)].sum()
    somme = somme[sedute.reindex(somme.index) == n]
    out = []
    for m in SOGLIE["settimana_metriche"]:
        q = (100 * somme[m] / somme.index.map(lambda g: rif.get((g, m), np.nan))).dropna()
        if len(q) < 6 or q.median() <= 0:
            continue
        out.append(pd.DataFrame({"giocatore_id": q.index, "metrica": m, "quota": q.values, "squadra": q.median(),
                                 "relativa": q.values / q.median()}))
    return pd.concat(out, ignore_index=True) if out else None


def _settimana(v: Visibile, allen: pd.DataFrame) -> list[Avviso]:
    """La settimana di un giocatore, in % della sua partita, rispetto ai compagni: fuori da come sta di solito rispetto
    a loro allo stesso punto della settimana. Il confronto coi compagni toglie l'effetto del calendario (settimane più
    o meno lunghe), quello con le sue settimane passate toglie le abitudini del ruolo."""
    from .comune import settimana_di, settimane_regolari, taglio
    from .partita import riferimenti_partita
    md = v.contesto.giorno_md
    if v.seduta_di_oggi.empty or md not in (-2, -1):
        return []
    if md == -1 and (v.oggi - pd.Timedelta(days=1)) in set(allen["data"]):
        return []                                      # una volta a settimana: a MD-2, o a MD-1 se a MD-2 non ci si allenava
    righe = tutte_le_righe(v)
    rif = riferimenti_partita(v.storico, v.giocatori).set_index(["giocatore_id", "metrica"])["riferimento"]
    sett = settimana_di(v, v.oggi)
    ora = _quote(v, rif, sett, v.oggi, righe)
    if ora is None:
        return []
    storia = [q for w in settimane_regolari(v, sett.partita_iniziale) if (q := _quote(v, rif, w, taglio(w, md), righe)) is not None]
    if len(storia) < SOGLIE["settimana_min"]:
        return []
    storia = pd.concat(storia, ignore_index=True)
    ana = anagrafica(v)
    trovati: dict[tuple[int, str], list] = {}
    for r in ora.itertuples():
        passate = storia[(storia["giocatore_id"] == r.giocatore_id) & (storia["metrica"] == r.metrica)]["relativa"]
        if len(passate) < SOGLIE["settimana_min"]:
            continue
        p10, p90 = np.percentile(passate, (10, 90))
        fattore = SOGLIE["settimana_fattore"]
        verso = "sopra" if r.relativa > p90 * fattore else "sotto" if r.relativa < p10 / fattore else None
        if verso is not None:
            lontano = r.relativa / p90 if verso == "sopra" else p10 / max(r.relativa, 1e-6)
            trovati.setdefault((int(r.giocatore_id), verso), []).append((r, float(lontano)))
    out = []
    for (gid, verso), voci in trovati.items():
        nome = ana.loc[gid, "nome_completo"]
        pezzi = [f"in {_nome_m(r.metrica)} {_il(r.quota)} della sua partita, contro una mediana di squadra del "
                 f"{numero_it(r.squadra, '%')}%" for r, _ in voci]
        quota = f"finora gli allenamenti valgono {_elenco(pezzi)}"
        testo = (f"Verificare se per {nome} era prevista una settimana più carica di quella dei compagni: {quota}; di solito, a "
                 "questo punto della settimana, gli sta più vicino." if verso == "sopra" else
                 f"Valutare se c'è margine per {nome}: {quota}; di solito, a questo punto della settimana, gli sta più vicino.")
        out.append(Avviso("settimana", v.oggi, testo, gid, nome, gravita=max(x for _, x in voci),
                          evidenze=[f"partita/{v.oggi:%Y-%m-%d}/{gid}/{r.metrica}/settimana" for r, _ in voci],
                          metriche=[r.metrica for r, _ in voci]))
    return out


# ---------- 5: calo persistente (e la sua fine, nota positiva) ----------

def _sedute_basse(c: pd.DataFrame, squadra: pd.Series) -> pd.DataFrame:
    """Le righe di allenamento solide di td/hsr/spr, con «bassa» = sotto il suo solito mentre la squadra era nella norma."""
    t = c[(c["tipo"] == "allenamento") & c["solida"] & c["metrica"].isin(METRICHE_CARICO)].copy()
    chiave = pd.MultiIndex.from_frame(t[["data", "metrica", "gruppo"]])
    sq = squadra.reindex(chiave).to_numpy()
    t["squadra_norma"] = (sq >= 25) & (sq <= 75)
    t["sotto"] = t["posizione"].isin(BASSO)
    t["bassa"] = t["sotto"] & t["squadra_norma"]
    return t


def _calo_vero(g: pd.DataFrame, giorno: pd.Timestamp) -> bool:
    """g: le righe di un giocatore e una metrica. Vero se al giorno dato il calo è in corso."""
    fin = g[(g["data"] > giorno - pd.Timedelta(days=SOGLIE["calo_giorni"])) & (g["data"] <= giorno)]
    basse = fin[fin["bassa"]]
    forte = basse["posizione"].eq("molto sotto").any() or basse["percentile"].median() <= SOGLIE["calo_percentile"]
    return (len(basse) >= SOGLIE["calo_sedute"] and len(basse) >= SOGLIE["calo_quota"] * len(fin) and bool(forte)
            and giorno in set(basse["data"]))


def _calo(t: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    oggi_t = t[t["data"] == oggi]
    nuovi: dict[int, list[tuple[str, pd.DataFrame]]] = {}
    tornati: dict[int, list[str]] = {}
    for (gid, m), g in t[t["giocatore_id"].isin(oggi_t["giocatore_id"])].groupby(["giocatore_id", "metrica"]):
        g = g[g["data"] <= oggi].sort_values("data")
        date = list(g["data"])
        if not date or date[-1] != oggi:
            continue
        prima = date[-2] if len(date) >= 2 else None
        if _calo_vero(g, oggi) and (prima is None or not _calo_vero(g, prima)):
            fin = g[(g["data"] > oggi - pd.Timedelta(days=SOGLIE["calo_giorni"])) & g["bassa"]]
            nuovi.setdefault(int(gid), []).append((m, fin))
        # fine del calo: due sedute di fila non sotto il solito, dopo una seduta in cui il calo era in corso
        if len(date) >= 3 and not g["sotto"].iloc[-1] and not g["sotto"].iloc[-2] and _calo_vero(g, date[-3]):
            tornati.setdefault(int(gid), []).append(m)
    out = []
    for gid, voci in nuovi.items():
        date = sorted(set().union(*[set(f["data"]) for _, f in voci]))
        n = len(date)
        out.append(Avviso("calo", oggi,
                          f"Approfondire con il giocatore e lo staff: nelle ultime due settimane, in {_quante(n)} sedute, "
                          f"{nomi[gid]} ha fatto meno {_elenco([_nome_m(m) for m, _ in voci])} del suo solito, mentre la squadra "
                          f"in quelle sedute era nella norma ({_date(date)}).",
                          gid, nomi[gid], gravita=float(n),
                          evidenze=[f"seduta/{d:%Y-%m-%d}/{gid}/{m}" for m, f in voci for d in f["data"]],
                          metriche=[m for m, _ in voci]))
    for gid, metriche in tornati.items():
        out.append(Avviso("positivo", oggi,
                          f"Da segnalare: {nomi[gid]} è tornato nel suo carico abituale in {_elenco([_nome_m(m) for m in metriche])} "
                          "nelle ultime due sedute, dopo un periodo sotto il suo solito.", gid, nomi[gid],
                          evidenze=[f"seduta/{oggi:%Y-%m-%d}/{gid}/{m}" for m in metriche], metriche=list(metriche), chiude="calo"))
    return out


def _tendenza(allen: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    """Riassunto settimanale: le ultime 4 settimane contro 8-12 settimane prima, negli stessi giorni prima della partita."""
    a = allen[allen["giorno_md"] < 0]
    rec = a[(a["data"] > oggi - pd.Timedelta(days=SOGLIE["tendenza_recenti"])) & (a["data"] <= oggi)]
    da, al = SOGLIE["tendenza_prima"]
    vec = a[(a["data"] > oggi - pd.Timedelta(days=al)) & (a["data"] <= oggi - pd.Timedelta(days=da))]
    out = []
    for gid in sorted(set(rec["giocatore_id"]) & set(vec["giocatore_id"])):
        r, w = rec[rec["giocatore_id"] == gid], vec[vec["giocatore_id"] == gid]
        if len(r) < SOGLIE["tendenza_min"] or len(w) < SOGLIE["tendenza_min"]:
            continue
        cali = []
        for m in METRICHE_CARICO:
            mr, mw = r.groupby("giorno_md")[m].median(), w.groupby("giorno_md")[m].median()
            comuni = [d for d in mr.index if d in mw.index and mw[d] > 0]
            if len(comuni) < 2:
                continue
            scarto = float(np.median([100 * (mr[d] / mw[d] - 1) for d in comuni]))
            diff = float(np.median([mr[d] - mw[d] for d in comuni]))
            if scarto <= SOGLIE["tendenza_scarto"] and abs(diff) > tolleranza(m, float(np.median([mw[d] for d in comuni]))):
                cali.append((m, scarto))
        if cali:
            cosa = _elenco([_nome_m(m) for m, _ in cali])
            scarti = ", ".join(f"{_nome_m(m)} {numero_it(s, '%')}%" for m, s in cali)
            out.append(Avviso("calo", oggi,
                              f"Approfondire con il giocatore e lo staff: nelle ultime quattro settimane {nomi[gid]} ha fatto meno "
                              f"{cosa} di due-tre mesi fa, negli stessi giorni prima della partita (scarto mediano: {scarti}).",
                              int(gid), nomi[gid], riassunto=True, gravita=-min(s for _, s in cali), metriche=[m for m, _ in cali]))
    return out


# ---------- 6: rientro dopo un'assenza (e la sua fine, nota positiva) ----------

def _rientro(allen: pd.DataFrame, t: pd.DataFrame, c: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    date = sorted(allen["data"].unique())
    if not date or date[-1] != oggi:
        return []
    presenze = allen.groupby("giocatore_id")["data"].apply(set)
    out = []
    for gid in sorted(allen[allen["data"] == oggi]["giocatore_id"]):
        sue = presenze[gid]
        assenti = 0
        for d in reversed(date[:-1]):
            if d in sue:
                break
            assenti += 1
        else:
            continue                                   # mai visto prima: nessun rientro
        if assenti >= SOGLIE["rientro_sedute"]:
            ultima = max(d for d in sue if d < oggi)
            r = c[(c["data"] == oggi) & (c["giocatore_id"] == gid) & (c["metrica"] == "td")]
            quota = ""
            if len(r) and r["solida"].iloc[0] and r["p50"].iloc[0] > 0:
                quota = (f": oggi ha fatto {_il(100 * r['valore'].iloc[0] / r['p50'].iloc[0])} della sua "
                         f"distanza abituale per {giorno_md_it(r['giorno_md'].iloc[0])}")
            out.append(Avviso("rientro", oggi,
                              f"{nomi[gid]} è tornato dopo {(oggi - ultima).days} giorni senza dati ({_quante(assenti)} sedute)"
                              f"{quota}. Vice non sa perché mancava.", int(gid), nomi[gid], gravita=float(assenti),
                              evidenze=[f"seduta/{oggi:%Y-%m-%d}/{gid}/td"], metriche=["td"]))
        # fine del rientro: dopo un rientro nelle ultime 3 settimane, le prime due sedute di fila nel suo solito
        sue_date = sorted(d for d in sue if d <= oggi)
        if len(sue_date) < 3:
            continue
        rientri = [sue_date[i] for i in range(1, len(sue_date))
                   if sum(1 for d in date if sue_date[i - 1] < d < sue_date[i]) >= SOGLIE["rientro_sedute"]
                   and sue_date[i] >= oggi - pd.Timedelta(days=21)]
        if not rientri:
            continue
        dopo = [d for d in sue_date if d >= rientri[-1]]
        g = t[(t["giocatore_id"] == gid) & t["data"].isin(dopo)]
        ok = [not g[g["data"] == d].empty and not g[g["data"] == d]["sotto"].any() for d in dopo]
        prima_coppia = next((j for j in range(1, len(dopo)) if ok[j - 1] and ok[j]), None)
        if prima_coppia is not None and dopo[prima_coppia] == oggi:
            out.append(Avviso("positivo", oggi,
                              f"Da segnalare: {nomi[gid]} è di nuovo nel suo carico abituale in distanza, alta velocità e "
                              f"sprint, {(oggi - rientri[-1]).days} giorni dopo il rientro.", int(gid), nomi[gid],
                              evidenze=[f"seduta/{oggi:%Y-%m-%d}/{gid}/{m}" for m in METRICHE_CARICO],
                              metriche=list(METRICHE_CARICO), chiude="rientro"))
    return out


# ---------- 7: scarto di reparto (riassunto settimanale) ----------

def _reparto(allen: pd.DataFrame, t_all: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series, ruoli: pd.Series,
             partite: list[pd.Timestamp]) -> list[Avviso]:
    out = []
    a = allen[(allen["data"] > oggi - pd.Timedelta(days=SOGLIE["reparto_giorni"])) & (allen["data"] <= oggi)]
    for ruolo, gr in a.groupby("ruolo"):
        if gr["giocatore_id"].nunique() < 3:
            continue
        for m in ("hsr", "spr"):
            per_seduta = {d: s.set_index("giocatore_id")[m] for d, s in gr.groupby("data") if len(s) >= 3}
            for gid in sorted(gr["giocatore_id"].unique()):
                condivise = [d for d, s in per_seduta.items() if gid in s.index]
                ultimo = [d for d in condivise if per_seduta[d][gid] < per_seduta[d].drop(gid).min()
                          and per_seduta[d].drop(gid).median() >= SOGLIE["reparto_minimo"][m]]
                if len(condivise) >= SOGLIE["reparto_sedute"] and len(ultimo) >= SOGLIE["reparto_quota"] * len(condivise):
                    out.append(Avviso("reparto", oggi,
                                      f"Verificare se le esercitazioni espongono {nomi[gid]} {'all' + chr(39) + 'alta velocità' if m == 'hsr' else 'allo sprint'} "
                                      f"quanto gli altri {RUOLI_PLURALE[ruolo]}: nelle ultime {_quante(len(condivise))} sedute condivise "
                                      + (f"ha fatto meno di tutti in tutte e {_quante(len(condivise))}." if len(ultimo) == len(condivise)
                                         else f"ha fatto meno di tutti in {_quante(len(ultimo))} su {_quante(len(condivise))}."),
                                      int(gid), nomi[gid], riassunto=True,
                                      gravita=len(ultimo) / len(condivise), metriche=[m]))
    # un reparto intero sotto il suo solito nella settimana appena chiusa, mentre il resto della squadra no
    prima = [p for p in partite if p < oggi]
    if len(prima) >= 2:
        sett = t_all[(t_all["data"] > prima[-2]) & (t_all["data"] < prima[-1]) & t_all["metrica"].isin(["hsr", "spr"])]
        for (ruolo, m), g in sett.groupby(["ruolo", "metrica"]):
            sedute = sorted(g["data"].unique())
            if len(sedute) < 3:
                continue
            sotto = 0
            for d in sedute:
                rep = g[g["data"] == d]["percentile"].median()
                resto = sett[(sett["data"] == d) & (sett["metrica"] == m) & (sett["ruolo"] != ruolo)]["percentile"].median()
                sotto += int(rep < 25 and resto >= 25)
            if sotto >= max(3, len(sedute) / 2):
                out.append(Avviso("reparto", oggi,
                                  f"Verificare se la settimana ha dato ai {RUOLI_PLURALE[ruolo]} il loro solito {_nome_m(m)}: in "
                                  f"{_quante(sotto)} sedute su {len(sedute)} il reparto è stato sotto il suo solito, il resto della "
                                  "squadra no.", riassunto=True, gravita=sotto / len(sedute), metriche=[m]))
    return out


# ---------- 8: note positive (settimana completa, partite) ----------

def _settimana_completa(v: Visibile, allen: pd.DataFrame) -> list[Avviso]:
    md = v.contesto.giorno_md
    domani_partita = md == -1 or (md == -2 and (v.oggi + pd.Timedelta(days=1)) not in set(allen["data"]))
    if v.seduta_di_oggi.empty or not domani_partita:
        return []
    r = esposizione_velocita(v)
    if r.tabella.empty or not r.sintesi.get("finestra_completa") or r.sintesi.get("sotto_il_solito"):
        return []
    valutati = r.tabella["giocatore_id"].nunique()
    if valutati < 10:
        return []
    return [Avviso("positivo", v.oggi, f"Da segnalare: prima della partita del {data_it(v.contesto.prossima_partita)[:5]} tutti i "
                   f"{valutati} giocatori valutati hanno avuto la loro alta velocità solita da MD-4 a MD-2.", metriche=["hsr", "spr"])]


def _partite_sopra(righe: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    """Riassunto settimanale: alta velocità sopra il suo solito in due gare di fila da titolare (il contesto conta)."""
    p = righe[(righe["tipo"] == "partita") & (righe["data"] < oggi)].sort_values("data")
    tit = p[p["titolare_ultima_partita"].fillna(False).astype(bool)]
    ultime = sorted(p["data"].unique())[-SOGLIE["positivo_partite"]:]
    if len(ultime) < SOGLIE["positivo_partite"]:
        return []
    out = []
    for gid, g in tit.groupby("giocatore_id"):
        recenti = g[g["data"].isin(ultime)]
        prima = g[g["data"] < ultime[0]]["hsr"]
        if len(recenti) < len(ultime) or len(prima) < 3:
            continue
        p75 = float(np.percentile(prima, 75))
        if (recenti["hsr"] > p75 + tolleranza("hsr", float(prima.median()))).all():
            valori = _elenco([con_unita(x, "m") for x in recenti["hsr"]])
            out.append(Avviso("positivo", oggi,
                              f"Da segnalare: in partita {nomi[gid]} è sopra il suo solito di alta velocità da due gare di fila da "
                              f"titolare ({valori}; di solito fino a {con_unita(p75, 'm')}). Il contesto della partita conta: non è un "
                              "giudizio di rendimento.", int(gid), nomi[gid], riassunto=True, metriche=["hsr"]))
    return out


# ---------- 9: qualità del dato ----------

def _dato(allen: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series) -> list[Avviso]:
    date = sorted(allen["data"].unique())
    if not date or date[-1] != oggi:
        return []
    out = []
    presenze = allen.groupby("giocatore_id")["data"].apply(set)
    n = SOGLIE["dato_sedute"]
    if len(date) >= n + 3:
        for gid, sue in presenze.items():
            mancate = date[-n:]
            if all(d not in sue for d in mancate) and all(d in sue for d in date[-n - 3:-n]):
                out.append(Avviso("dato", oggi, f"Verificare il dato: {nomi[gid]} non ha dati nelle ultime {_quante(n)} sedute "
                                  f"({_date(mancate)}), dopo che c'erano nelle precedenti.", int(gid), nomi[gid]))
    oggi_r = allen[allen["data"] == oggi]
    for r in oggi_r.itertuples():
        if r.spr > r.hsr:
            out.append(Avviso("dato", oggi, f"Verificare il dato: lo sprint di {nomi[r.giocatore_id]} ({con_unita(r.spr, 'm')}) supera "
                              f"l'alta velocità ({con_unita(r.hsr, 'm')}), che lo comprende.", int(r.giocatore_id), nomi[r.giocatore_id],
                              metriche=["hsr", "spr"], urgente=True))
        if r.hsr > r.td:
            out.append(Avviso("dato", oggi, f"Verificare il dato: l'alta velocità di {nomi[r.giocatore_id]} supera la distanza totale.",
                              int(r.giocatore_id), nomi[r.giocatore_id], metriche=["td", "hsr"], urgente=True))
        for m, limite in SOGLIE["dato_impossibile"].items():
            if getattr(r, m) > limite:
                out.append(Avviso("dato", oggi, f"Verificare il dato: {_nome_m(m)} di {nomi[r.giocatore_id]} "
                                  f"{con_unita(getattr(r, m), UNITA[m])} in una seduta, oltre ogni valore plausibile.",
                                  int(r.giocatore_id), nomi[r.giocatore_id], metriche=[m], urgente=True))
    return out


# ---------- tutti gli avvisi di un giorno ----------

def giorno_del_riassunto(allen: pd.DataFrame, partite: list[pd.Timestamp], oggi: pd.Timestamp) -> bool:
    """Il riassunto settimanale si fa al primo allenamento dopo la partita."""
    prima = [p for p in partite if p < oggi]
    return bool(prima) and oggi in set(allen["data"]) and not any(prima[-1] < d < oggi for d in allen["data"].unique())


def _riassunto(righe: pd.DataFrame, allen: pd.DataFrame, c: pd.DataFrame, oggi: pd.Timestamp, nomi: pd.Series,
               ruoli: pd.Series, partite: list[pd.Timestamp]) -> list[Avviso]:
    return (_tendenza(allen, oggi, nomi) + _reparto(allen, c[c["solida"]], oggi, nomi, ruoli, partite)
            + _partite_sopra(righe, oggi, nomi))


def _riassunto_nuovo(righe, allen, c, oggi, nomi, ruoli, partite) -> list[Avviso]:
    """Il riassunto settimanale, senza ripetere gli avvisi sui singoli già dati la settimana prima."""
    nuovi = _riassunto(righe, allen, c, oggi, nomi, ruoli, partite)
    prima = [p for p in partite if p < oggi]
    prec = [d for d in sorted(allen["data"].unique()) if len(prima) >= 2 and prima[-2] < d < prima[-1]]
    if not prec:
        return nuovi
    d = prec[0]
    vecchi = _riassunto(righe[righe["data"] <= d], allen[allen["data"] <= d], c[c["data"] <= d], d, nomi, ruoli,
                        [p for p in partite if p <= d])
    gia = {(a.famiglia, a.giocatore_id, a.testo.split(":")[0]) for a in vecchi if a.giocatore_id is not None}
    return [a for a in nuovi if a.giocatore_id is None or (a.famiglia, a.giocatore_id, a.testo.split(":")[0]) not in gia]


def avvisi(v: Visibile, c: pd.DataFrame | None = None) -> list[Avviso]:
    """Tutti gli avvisi del giorno, prima della selezione. `c`: la classificazione delle sedute fino a oggi
    (classificazione()); se manca si calcola, ma serve circa un minuto per una stagione."""
    righe = tutte_le_righe(v)
    if c is None:
        c = classificazione(righe)
    c = c[c["data"] <= v.oggi]
    oggi = v.oggi
    allen = righe[righe["tipo"] == "allenamento"]
    ana = anagrafica(v)
    nomi, ruoli = ana["nome_completo"], ana["ruolo"]
    partite = [p for p in date_partite(v) if p <= oggi]
    t = _sedute_basse(c, _contesto_squadra(c))
    out = _dagli_spunti(v, allen) + _dato(allen, oggi, nomi)
    if oggi in set(allen["data"]):
        out += _insolito(c, oggi, nomi) + _settimana(v, allen) + _calo(t, oggi, nomi) + _rientro(allen, t, c, oggi, nomi)
        out += _settimana_completa(v, allen)
        if giorno_del_riassunto(allen, partite, oggi):
            out += _riassunto_nuovo(righe, allen, c, oggi, nomi, ruoli, partite)
    return out


def scegli(tutti: list[Avviso]) -> dict[str, list[Avviso]]:
    """Gli avvisi da mostrare: al massimo 3 del giorno, 5 nel riassunto; la qualità del dato a parte."""
    ordine = lambda a: (a.priorita, a.giocatore_id is not None, -a.gravita)   # noqa: E731 — prima la squadra
    giorno = sorted([a for a in tutti if not a.riassunto and a.famiglia != "dato"], key=ordine)[:MAX_AL_GIORNO]
    riassunto = sorted([a for a in tutti if a.riassunto], key=ordine)[:MAX_NEL_RIASSUNTO]
    return {"giorno": giorno, "riassunto": riassunto, "dato": [a for a in tutti if a.famiglia == "dato"]}
