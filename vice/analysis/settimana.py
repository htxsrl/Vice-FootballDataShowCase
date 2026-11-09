"""La settimana (microciclo): forma (M2.3), esposizione all'alta velocità (M2.4), carico postpartita (M2.5).

- **Forma:** per ogni seduta della settimana, la mediana di squadra contro le mediane di squadra
  dello stesso giorno MD nelle settimane regolari passate. Con meno di 6 settimane la curva è
  provvisoria e non genera spunti. Più la griglia giocatori × giorni (vista V1), con ogni seduta
  classificata con le fasce di quel giorno.
- **Alta velocità:** sprint e HSR da MD-4 a MD-2.
- **Postpartita:** distanza, HSR e sprint dei non titolari dell'ultima partita a MD+1 e MD+2,
  accanto al carico della partita; più il carico postpartita dei titolari.

Somme di più giorni: il riferimento è la **somma dei riferimenti giornalieri** del giocatore (i
percentili delle sue fasce, giorno per giorno) **sui soli giorni in cui ha dati**. Non è il
percentile della somma: è una regola operativa dichiarata. Un giorno senza dati non vale zero:
il dataset toglie righe senza dire perché, quindi la copertura si dichiara a parte.

Nessuna di queste analisi dice se uno stimolo è sufficiente o se un giocatore ha recuperato:
descrivono il carico registrato rispetto allo storico (revisione tecnica del 22/10/2026).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.stagione import Visibile
from .comune import (METRICHE, NOME_METRICA, UNITA, Settimana, anagrafica, partita_ha_dati, partita_prima,
                     settimana_di, settimane_regolari, stato_in_partita, tutte_le_righe)
from .evidenze import Risultato, arrotonda, data_it, evidenza, giorno_md_it, maiuscola
from .fasce import (NON_TITOLARI, TUTTI, Riferimenti, classifica, con_gruppo, posizione, quantili, rango_percentile,
                    tolleranza)
from .partita import riferimenti_partita
from .seduta import con_nomi, evidenze_classifica

MIN_SETTIMANE = 4            # settimane passate per mostrare la curva tipica…
MIN_SETTIMANE_SPUNTI = 6     # …e per farne nascere spunti
FINESTRA_VELOCITA = (-4, -2)
SPRINT_MOLTO_BASSO = 10      # m: sprint registrato "molto basso" (0 m = "nullo")…
SPRINT_ATTESO_MIN = 30       # m: …ma conta solo per chi di solito, in quei giorni, ne fa almeno 30
QUOTA_COPERTA_DALLA_PARTITA = 60   # %: decisione 27, vedi compensazione()
QUOTA_GRUPPO = 0.5           # almeno metà dei non titolari valutati, e almeno 3, molto sotto: spunto di gruppo
MIN_GRUPPO = 3
METRICHE_POSTPARTITA = ("td", "hsr", "spr")


def copertura(sedute: int, sedute_squadra: int) -> str:
    if sedute_squadra == 0:
        return "nessuna seduta registrata"
    if sedute == 0:
        return "nessun dato"
    return "completa" if sedute >= sedute_squadra else "parziale"


# ---------- M2.3 forma della settimana ----------

def forma_settimana(v: Visibile) -> Risultato:
    oggi, ctx = v.oggi, v.contesto
    if ctx.giorno_md is None:
        return Risultato("forma_settimana", oggi, pd.DataFrame(), avvisi=["oggi è un giorno di pausa"])
    sett = settimana_di(v, oggi)
    righe = con_gruppo(tutte_le_righe(v))
    corrente = righe[sett.contiene(righe["data"]) & (righe["data"] <= oggi)]
    passate = settimane_regolari(v, sett.partita_iniziale)
    storico = righe[righe["data"] <= sett.partita_iniziale] if sett.partita_iniziale is not None else righe.iloc[:0]
    in_passate = np.zeros(len(storico), dtype=bool)
    for w in passate:
        in_passate |= w.contiene(storico["data"]).to_numpy()
    storico = storico[in_passate]
    avvisi = []
    if not sett.regolare:
        avvisi.append("settimana non regolare (pausa o periodo senza dati): il confronto col solito è indicativo")
    if len(passate) < MIN_SETTIMANE:
        avvisi.append("troppo poche settimane regolari nello storico per la curva tipica")
    elif len(passate) < MIN_SETTIMANE_SPUNTI:
        avvisi.append("curva tipica provvisoria: ancora poche settimane regolari, niente spunti dalla curva")

    med_storico = storico.groupby(["data", "giorno_md", "gruppo"])[list(METRICHE)].median().reset_index()
    tipica = med_storico.groupby(["giorno_md", "gruppo"])[list(METRICHE)].median().reset_index()
    tab, evid = [], []
    for (d, gmd, g), t in corrente.groupby(["data", "giorno_md", "gruppo"]):
        rif = med_storico[(med_storico["giorno_md"] == gmd) & (med_storico["gruppo"] == g)]
        for m in METRICHE:
            x = float(t[m].median())
            riga = {"data": d, "giorno_md": int(gmd), "tipo": t["tipo"].iloc[0], "gruppo": g, "metrica": m,
                    "giocatori": len(t), "mediana_squadra": x, "settimane": len(rif),
                    "provvisoria": len(rif) < MIN_SETTIMANE_SPUNTI}
            if len(rif) >= MIN_SETTIMANE:
                q = quantili(rif[m])
                riga |= q | {"percentile": rango_percentile(x, rif[m]),
                             "posizione": posizione(x, q["p10"], q["p25"], q["p50"], q["p75"], q["p90"], m)}
            else:
                riga |= {"posizione": "senza fascia"}
            tab.append(riga)
            u = UNITA[m]
            ctx_e = {"data": d, "giorno_md": int(gmd), "tipo": riga["tipo"], "gruppo": g, "metrica": m,
                     "giocatori": len(t), "settimane": len(rif), "provvisoria": riga["provvisoria"],
                     "posizione": riga["posizione"]}
            if "p50" in riga:
                ctx_e |= {"solito": arrotonda(riga["p50"], u), "fascia_centrale": [arrotonda(riga["p25"], u), arrotonda(riga["p75"], u)],
                          "fascia_larga": [arrotonda(riga["p10"], u), arrotonda(riga["p90"], u)],
                          "percentile": arrotonda(riga["percentile"], "percentile")}
            evid.append(evidenza(f"settimana/{d:%Y-%m-%d}/{g}/{m}",
                                 f"{maiuscola(NOME_METRICA[m])}: mediana della squadra ({g}), {data_it(d)} ({giorno_md_it(gmd)})",
                                 x, u, grafico=f"curva/{d:%Y-%m-%d}/{g}/{m}", **ctx_e))
    sintesi = {"data": oggi, "giorno_md": ctx.giorno_md, "settimana_dal": sett.partita_iniziale,
               "prossima_partita": sett.partita_finale, "settimana_regolare": sett.regolare,
               "settimane_di_riferimento": len(passate),
               "settimana_tipo": tipica.round(1).to_dict("records")}
    tab = pd.DataFrame(tab)
    if len(tab):
        fuori = tab[tab["posizione"].isin(["molto sotto", "molto sopra"])]
        sintesi["sedute_fuori_curva"] = [{"data": r.data, "giorno_md": r.giorno_md, "gruppo": r.gruppo, "metrica": r.metrica,
                                          "posizione": r.posizione, "evidenza": f"settimana/{r.data:%Y-%m-%d}/{r.gruppo}/{r.metrica}"}
                                         for r in fuori.itertuples()]
    return Risultato("forma_settimana", oggi, tab, evid, avvisi, sintesi)


def griglia_settimana(v: Visibile) -> Risultato:
    """Vista V1: ogni giocatore × seduta della settimana, classificato con le fasce di quel giorno."""
    oggi = v.oggi
    if v.contesto.giorno_md is None:
        return Risultato("griglia_settimana", oggi, pd.DataFrame(), avvisi=["oggi è un giorno di pausa"])
    sett = settimana_di(v, oggi)
    righe = tutte_le_righe(v)
    corrente = righe[sett.contiene(righe["data"]) & (righe["data"] <= oggi)]
    parti = []
    for d, seduta in corrente.groupby("data"):
        storico = righe[righe["data"] < d]
        parti.append(classifica(storico, seduta, Riferimenti(storico)))
    tab = con_nomi(pd.concat(parti, ignore_index=True), v) if parti else pd.DataFrame()
    evid = evidenze_classifica(tab, "seduta") if len(tab) else []
    return Risultato("griglia_settimana", oggi, tab, evid, [],
                     {"settimana_dal": sett.partita_iniziale, "prossima_partita": sett.partita_finale,
                      "sedute": int(corrente["data"].nunique())})


# ---------- somme di più giorni ----------

class _FascePerGiorno:
    """Riferimenti dello storico prima di ciascun giorno, calcolati una volta sola per giorno."""

    def __init__(self, righe: pd.DataFrame):
        self._righe, self._cache = righe, {}

    def __call__(self, giorno: pd.Timestamp) -> Riferimenti:
        if giorno not in self._cache:
            self._cache[giorno] = Riferimenti(self._righe[self._righe["data"] < giorno])
        return self._cache[giorno]


def _somma_riferimenti(fasce: _FascePerGiorno, giorni: pd.DataFrame, giocatore_id: int, ruolo: str, gruppo_: str,
                       metrica: str) -> dict | None:
    """Somma, sui giorni dati (data, giorno_md), dei percentili delle fasce giornaliere del giocatore.
    Una regola operativa: non è il percentile della somma. None se un giorno non ha fascia."""
    tot = dict.fromkeys(("p10", "p25", "p50", "p75", "p90"), 0.0)
    livelli, provvisoria = set(), False
    for g in giorni.itertuples():
        f = fasce(g.data).fascia(giocatore_id, ruolo, int(g.giorno_md), gruppo_, metrica)
        if f is None:
            return None
        for k, x in f.come_dict().items():
            tot[k] += x
        livelli.add(f.livello)
        provvisoria |= f.provvisoria
    tot["livello"] = " / ".join(sorted(livelli))
    tot["provvisoria"] = provvisoria
    return tot


def _esito(x: float, q: dict, metrica: str) -> str:
    t = tolleranza(metrica, q["p50"])
    if x >= q["p25"] - t:
        return "in linea"
    return "sotto il solito" if x >= q["p10"] - t else "molto sotto il solito"


def _ctx_riferimento(q: dict, u: str) -> dict:
    return {"riferimento": arrotonda(q["p50"], u), "fascia_centrale": [arrotonda(q["p25"], u), arrotonda(q["p75"], u)],
            "fascia_larga": [arrotonda(q["p10"], u), arrotonda(q["p90"], u)], "livello": q["livello"],
            "provvisoria": q["provvisoria"], "metodo": "somma dei riferimenti giornalieri"}


# ---------- M2.4 esposizione all'alta velocità ----------

def esposizione_velocita(v: Visibile) -> Risultato:
    """Sprint e HSR registrati da MD-4 a MD-2 contro la somma dei riferimenti giornalieri del giocatore,
    sui giorni della finestra in cui ha dati."""
    oggi, ctx = v.oggi, v.contesto
    if ctx.giorno_md is None:
        return Risultato("esposizione_velocita", oggi, pd.DataFrame(), avvisi=["oggi è un giorno di pausa"])
    # prima della partita si guarda la settimana in corso; il giorno della partita e dopo, quella appena chiusa
    partita = ctx.prossima_partita if ctx.giorno_md < 0 else ctx.ultima_partita
    righe = tutte_le_righe(v)
    righe = righe[righe["data"] <= oggi]
    a, b = FINESTRA_VELOCITA
    finestra = righe[(righe["data"] >= partita + pd.Timedelta(days=a)) & (righe["data"] <= partita + pd.Timedelta(days=b))
                     & righe["giorno_md"].between(a, b)]
    giorni_squadra = finestra[["data", "giorno_md"]].drop_duplicates().sort_values("data")
    completa = oggi >= partita + pd.Timedelta(days=b)
    sett = Settimana(partita_prima(v, partita), partita)
    giocatori = sorted(righe.loc[sett.contiene(righe["data"]), "giocatore_id"].unique())
    fasce, ana = _FascePerGiorno(righe), anagrafica(v)

    tab, evid, avvisi = [], [], []
    if not completa:
        avvisi.append(f"finestra MD-4…MD-2 non ancora conclusa: valori parziali fino al {data_it(oggi)}")
    if giorni_squadra.empty:
        avvisi.append(f"nessuna seduta registrata da MD-4 a MD-2 prima della partita del {data_it(partita)}")
    for gid in giocatori:
        nome, ruolo = ana.loc[gid, "nome_completo"], ana.loc[gid, "ruolo"]
        mie = finestra[finestra["giocatore_id"] == gid]
        giorni = mie[["data", "giorno_md"]].drop_duplicates().sort_values("data")
        cop = copertura(len(giorni), len(giorni_squadra))
        riga = {"giocatore_id": gid, "giocatore": nome, "ruolo": ruolo, "sedute": len(giorni),
                "sedute_squadra": len(giorni_squadra), "copertura": cop}
        for m in ("spr", "hsr"):
            x = float(mie[m].sum()) if len(mie) else np.nan
            q = _somma_riferimenti(fasce, giorni, gid, ruolo, TUTTI, m) if len(giorni) else None
            if cop in ("nessuna seduta registrata", "nessun dato"):
                pos = cop
            elif q is None:
                pos = "senza fascia"
            elif not completa:
                pos = "parziale"
            else:
                pos = posizione(x, q["p10"], q["p25"], q["p50"], q["p75"], q["p90"], m)
            riga |= {m: x, f"{m}_posizione": pos}
            if q is not None:
                riga |= {f"{m}_{k}": val for k, val in q.items()}
            ctx_e = {"giocatore_id": gid, "giocatore": nome, "metrica": m, "partita": partita, "sedute": len(giorni),
                     "sedute_squadra": len(giorni_squadra), "copertura": cop, "finestra_completa": bool(completa),
                     "posizione": pos}
            if q is not None:
                ctx_e |= _ctx_riferimento(q, UNITA[m])
            evid.append(evidenza(f"velocita/{partita:%Y-%m-%d}/{gid}/{m}",
                                 f"{maiuscola(NOME_METRICA[m])} registrata da {nome} da MD-4 a MD-2 prima della partita del {data_it(partita)}",
                                 x, UNITA[m], grafico=f"velocita/{gid}/{m}", **ctx_e))
        sprint = None
        if completa and len(giorni) and riga.get("spr_p50", 0) >= SPRINT_ATTESO_MIN:
            sprint = "nullo" if riga["spr"] == 0 else ("molto basso" if riga["spr"] < SPRINT_MOLTO_BASSO else None)
        riga["sprint_registrato"] = sprint
        tab.append(riga)
    tab = pd.DataFrame(tab)
    sintesi = {"data": oggi, "partita": partita, "finestra_completa": bool(completa), "sedute_squadra": len(giorni_squadra)}
    if len(tab):
        sotto = ["molto sotto", "sotto"]
        bassi = tab[tab["spr_posizione"].isin(sotto) | tab["hsr_posizione"].isin(sotto) | tab["sprint_registrato"].notna()]
        sintesi["sotto_il_solito"] = [{"giocatore_id": r.giocatore_id, "giocatore": r.giocatore,
                                       "spr": arrotonda(r.spr, "m"), "hsr": arrotonda(r.hsr, "m"),
                                       "spr_posizione": r.spr_posizione, "hsr_posizione": r.hsr_posizione,
                                       "sprint_registrato": r.sprint_registrato, "copertura": r.copertura,
                                       "evidenza": f"velocita/{partita:%Y-%m-%d}/{r.giocatore_id}/spr"} for r in bassi.itertuples()]
        sintesi["copertura_incompleta"] = [{"giocatore_id": r.giocatore_id, "giocatore": r.giocatore, "sedute": r.sedute,
                                            "sedute_squadra": r.sedute_squadra, "copertura": r.copertura}
                                           for r in tab[tab["copertura"].isin(["parziale", "nessun dato"])].itertuples()]
        evid.append(evidenza(f"velocita/{partita:%Y-%m-%d}/sintesi", f"Alta velocità da MD-4 a MD-2 prima della partita del {data_it(partita)}: giocatori sotto il solito",
                             len(sintesi["sotto_il_solito"]), "giocatori", grafico="velocita/squadra", partita=partita,
                             giocatori=len(tab), sedute_squadra=len(giorni_squadra), finestra_completa=bool(completa),
                             copertura_incompleta=len(sintesi["copertura_incompleta"]),
                             nomi=[x["giocatore"] for x in sintesi["sotto_il_solito"]]))
    return Risultato("esposizione_velocita", oggi, tab, evid, avvisi, sintesi)


# ---------- M2.5 carico postpartita (compensazione) ----------

def compensazione(v: Visibile) -> Risultato:
    """Il carico postpartita dei non titolari dell'ultima partita (MD+1 e MD+2): distanza, HSR e sprint
    contro la somma dei loro riferimenti giornalieri, accanto al carico della partita. Più il carico
    postpartita dei titolari, con la fascia dei titolari.

    Decisione 27: nessuna esenzione sulla distanza. Lo spunto si basa sull'HSR e non nasce se tra
    partita e postpartita il giocatore ha già superato il 60% del suo HSR di riferimento."""
    oggi = v.oggi
    partita = partita_prima(v, oggi)
    if partita is None:
        return Risultato("compensazione", oggi, pd.DataFrame(), avvisi=["nessuna partita prima di oggi"])
    righe = tutte_le_righe(v)
    righe = righe[righe["data"] <= oggi]
    prossima = v.contesto.prossima_partita
    in_partita = righe[(righe["data"] == partita) & (righe["giorno_md"] == 0)]
    nella_sett = righe[Settimana(partita, prossima).contiene(righe["data"])]
    giocatori = sorted(set(in_partita["giocatore_id"]) | set(nella_sett["giocatore_id"]))
    dati = partita_ha_dati(v, partita)
    stato = stato_in_partita(righe, partita, giocatori, dati)
    non_titolari = [g for g in giocatori if stato[g] is False]
    avvisi = []
    if not dati:
        avvisi.append(f"la partita del {data_it(partita)} non ha dati GPS: titolari e non titolari sconosciuti")
    ultimo = partita + pd.Timedelta(days=2)
    if prossima is not None:
        ultimo = min(ultimo, prossima - pd.Timedelta(days=1))
    aperta = oggi < ultimo
    dopo = righe[(righe["data"] > partita) & (righe["data"] <= ultimo) & righe["giorno_md"].isin([1, 2])]
    # sedute postpartita registrate = giorni in cui almeno un non titolare ha dati
    giorni_squadra = dopo.loc[dopo["giocatore_id"].isin(non_titolari), ["data", "giorno_md"]].drop_duplicates().sort_values("data")
    if not aperta and giorni_squadra.empty and non_titolari:
        avvisi.append(f"dopo la partita del {data_it(partita)} non risultano sedute postpartita registrate")
    senza_riga = [g for g in non_titolari if g not in set(in_partita["giocatore_id"])]
    if senza_riga:
        avvisi.append(f"alcuni non titolari non hanno dati della partita del {data_it(partita)}: non hanno giocato "
                      "o il dato manca (il dataset non lo distingue)")
    fasce, ana = _FascePerGiorno(righe), anagrafica(v)
    rif_partita = riferimenti_partita(v.storico, v.giocatori).set_index(["giocatore_id", "metrica"])

    tab, evid = [], []
    for gid in non_titolari:
        nome, ruolo = ana.loc[gid, "nome_completo"], ana.loc[gid, "ruolo"]
        mia = dopo[dopo["giocatore_id"] == gid]
        giorni = mia[["data", "giorno_md"]].drop_duplicates().sort_values("data")
        p = in_partita[in_partita["giocatore_id"] == gid]
        cop = copertura(len(giorni), len(giorni_squadra))
        riga = {"giocatore_id": gid, "giocatore": nome, "ruolo": ruolo, "partita": partita, "riga_partita": len(p) > 0,
                "sedute": len(giorni), "sedute_squadra": len(giorni_squadra), "copertura": cop}
        for m in METRICHE_POSTPARTITA:
            ref = rif_partita["riferimento"].get((gid, m), np.nan)
            part = float(p[m].sum()) if len(p) else np.nan            # senza riga: non registrato, non zero
            post = float(mia[m].sum()) if len(mia) else np.nan
            q = _somma_riferimenti(fasce, giorni, gid, ruolo, NON_TITOLARI, m) if len(giorni) else None
            if aperta:
                esito = "in corso"
            elif cop in ("nessuna seduta registrata", "nessun dato"):
                esito = cop
            elif q is None:
                esito = "senza fascia"
            else:
                esito = _esito(post, q, m)
            riga |= {f"partita_{m}": part, f"post_{m}": post, f"rif_{m}": ref, f"esito_{m}": esito,
                     f"partita_{m}_pct": 100 * part / ref if ref and not pd.isna(ref) and not pd.isna(part) else np.nan,
                     f"totale_{m}_pct": 100 * (part + (0 if pd.isna(post) else post)) / ref
                     if ref and not pd.isna(ref) and not pd.isna(part) else np.nan}
            if q is not None:
                riga |= {f"{m}_{k}": val for k, val in q.items()}
        riga["esito"] = riga["esito_hsr"]
        riga["coperto_dalla_partita"] = bool(not pd.isna(riga["totale_hsr_pct"])
                                             and riga["totale_hsr_pct"] >= QUOTA_COPERTA_DALLA_PARTITA)
        tab.append(riga)
        for m in METRICHE_POSTPARTITA:
            u = UNITA[m]
            ctx_e = {"giocatore_id": gid, "giocatore": nome, "metrica": m, "partita": partita, "sedute": len(giorni),
                     "sedute_squadra": len(giorni_squadra), "copertura": cop, "esito": riga[f"esito_{m}"],
                     "finestra_aperta": bool(aperta), "partita_registrata": riga["riga_partita"],
                     "in_partita": arrotonda(riga[f"partita_{m}"], u),
                     "partita_pct": arrotonda(riga[f"partita_{m}_pct"], "%"),
                     "partita_piu_postpartita_pct": arrotonda(riga[f"totale_{m}_pct"], "%")}
            if f"{m}_p50" in riga:
                ctx_e |= _ctx_riferimento({k: riga[f"{m}_{k}"] for k in ("p10", "p25", "p50", "p75", "p90", "livello", "provvisoria")}, u)
            evid.append(evidenza(f"compensazione/{partita:%Y-%m-%d}/{gid}/{m}",
                                 f"{maiuscola(NOME_METRICA[m])} di {nome} nelle sedute postpartita dopo la partita del {data_it(partita)} (non titolare)",
                                 riga[f"post_{m}"], u, grafico=f"compensazione/{gid}", **ctx_e))

    # titolari: il loro carico postpartita (MD+1 e MD+2) contro la fascia dei titolari
    postpartita_titolari = []
    tit = dopo[dopo["giocatore_id"].isin([g for g, s in stato.items() if s is True])]
    for d, s in tit.groupby("data"):
        postpartita_titolari.append(classifica(None, s, fasce(d)))
    postpartita_titolari = con_nomi(pd.concat(postpartita_titolari, ignore_index=True), v) if postpartita_titolari else pd.DataFrame()
    if len(postpartita_titolari):
        evid += evidenze_classifica(postpartita_titolari, "seduta")
    tab = pd.DataFrame(tab)
    # se almeno metà dei non titolari valutati (e almeno 3) è molto sotto, è la seduta, non il singolo;
    # contano solo i confronti con fasce non provvisorie, come per tutti gli spunti
    valutati = tab[tab["esito"].isin(["in linea", "sotto il solito", "molto sotto il solito"])
                   & ~tab["hsr_provvisoria"].fillna(True).astype(bool)] if len(tab) and "hsr_provvisoria" in tab else tab.iloc[:0]
    molto_sotto = valutati[valutati["esito"] == "molto sotto il solito"] if len(valutati) else valutati
    di_gruppo = bool(len(molto_sotto) >= MIN_GRUPPO and len(molto_sotto) >= QUOTA_GRUPPO * len(valutati))
    # la prima seduta registrata dal giorno in cui la finestra si chiude: lì il report della seduta ne parla
    dopo_chiusura = righe.loc[righe["data"] >= ultimo, "data"]
    appena_chiusa = bool(not aperta and len(dopo_chiusura) and dopo_chiusura.min() == oggi)
    sintesi = {"data": oggi, "partita": partita, "finestra_aperta": bool(aperta), "appena_chiusa": appena_chiusa,
               "sedute_squadra": len(giorni_squadra), "valutati": int(len(valutati)), "molto_sotto": int(len(molto_sotto)),
               "sotto_di_gruppo": di_gruppo, "non_titolari": int(len(tab)),
               "per_esito": tab["esito"].value_counts().to_dict() if len(tab) else {}}
    if len(valutati):
        hsr_m = float(molto_sotto["post_hsr"].median()) if len(molto_sotto) else None
        rif_m = float(molto_sotto["hsr_p50"].median()) if len(molto_sotto) else None
        evid.append(evidenza(f"compensazione/{partita:%Y-%m-%d}/gruppo/hsr",
                             f"HSR postpartita dei non titolari dopo la partita del {data_it(partita)}: mediana dei valutati",
                             valutati["post_hsr"].median(), "m", grafico="compensazione/gruppo", partita=partita,
                             valutati=int(len(valutati)), molto_sotto=int(len(molto_sotto)),
                             hsr_mediano_molto_sotto=arrotonda(hsr_m, "m"), riferimento_mediano_molto_sotto=arrotonda(rif_m, "m"),
                             sotto_di_gruppo=di_gruppo))
    if len(tab):
        sintesi["copertura_incompleta"] = [{"giocatore_id": r.giocatore_id, "giocatore": r.giocatore, "sedute": r.sedute,
                                            "sedute_squadra": r.sedute_squadra, "copertura": r.copertura}
                                           for r in tab[tab["copertura"].isin(["parziale", "nessun dato"])].itertuples()]
        evid.append(evidenza(f"compensazione/{partita:%Y-%m-%d}/esiti", f"Non titolari della partita del {data_it(partita)}, per esito dell'HSR postpartita",
                             len(tab), "giocatori", grafico="compensazione/gruppo", partita=partita,
                             finestra_aperta=bool(aperta), sedute_squadra=len(giorni_squadra),
                             **{e.replace(" ", "_"): int(n) for e, n in sintesi["per_esito"].items()}))
    if len(postpartita_titolari):
        sopra = postpartita_titolari[postpartita_titolari["metrica"].isin(["td", "hsr"])
                                     & postpartita_titolari["posizione"].isin(["sopra", "molto sopra"])]
        sintesi["titolari_postpartita_sopra"] = [{"giocatore_id": r.giocatore_id, "giocatore": r.giocatore, "data": r.data,
                                                  "giorno_md": r.giorno_md, "metrica": r.metrica, "posizione": r.posizione,
                                                  "evidenza": f"seduta/{r.data:%Y-%m-%d}/{r.giocatore_id}/{r.metrica}"}
                                                 for r in sopra.itertuples()]
    return Risultato("compensazione", oggi, tab, evid, avvisi, sintesi,
                     altre={"titolari_postpartita": postpartita_titolari})
