"""M2.6 Allenamento ↔ partita: quanto della partita stiamo allenando (decisione 24).

Riferimento di partita di un giocatore, per ogni metrica: la **media dei carichi osservati nelle
sue partite da titolare** giocate prima dell'oggi. Con meno di 3 partite da titolare si usa la media
delle prestazioni da titolare del suo ruolo, da almeno 3 partite diverse. È la stessa grandezza
delle colonne `RATIO*` del dataset, che però la calcolano sull'intera stagione, futuro compreso.
Senza i minuti non è il carico di una partita intera: tra i titolari c'è anche chi è uscito presto.
Accanto alla media si danno mediana e P25-P75, per vedere quanto è stabile.

Avvertenza da dichiarare: negli allenamenti è compreso il riscaldamento, nelle partite no
(articolo del dataset, §5.3.2), quindi il rapporto è un po' generoso con l'allenamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.stagione import Visibile
from .comune import (METRICHE, NOME_METRICA, UNITA, anagrafica, settimana_di, settimane_regolari, taglio,
                     tutte_le_righe)
from .evidenze import Risultato, arrotonda, evidenza, maiuscola

MIN_PARTITE = 3            # partite da titolare per un riferimento personale (e partite diverse per quello di ruolo)
MIN_SETTIMANE_SOLITO = 4   # settimane passate per dire "di solito a questo punto della settimana"
AVVISO_RISCALDAMENTO = ("negli allenamenti è compreso il riscaldamento, nelle partite no: il rapporto "
                        "allenamento/partita è un po' generoso con l'allenamento")


def riferimenti_partita(storico: pd.DataFrame, giocatori: pd.DataFrame) -> pd.DataFrame:
    """Una riga per giocatore × metrica: riferimento (media), mediana, P25-P75, livello
    ("personale"/"ruolo"), prestazioni e partite diverse da cui viene."""
    tit = storico[(storico["giorno_md"] == 0) & storico["titolare_ultima_partita"].fillna(False).astype(bool)]
    righe = []
    for g in giocatori.itertuples():
        mie = tit[tit["giocatore_id"] == g.giocatore_id]
        del_ruolo = tit[tit["ruolo"] == g.ruolo]
        if len(mie) >= MIN_PARTITE:
            base, livello = mie, "personale"
        elif del_ruolo["data"].nunique() >= MIN_PARTITE:
            base, livello = del_ruolo, "ruolo"
        else:
            base, livello = None, None
        for m in METRICHE:
            riga = {"giocatore_id": g.giocatore_id, "ruolo": g.ruolo, "metrica": m, "livello": livello,
                    "riferimento": np.nan, "mediana": np.nan, "p25": np.nan, "p75": np.nan,
                    "prestazioni": 0 if base is None else int(len(base)),
                    "partite": 0 if base is None else int(base["data"].nunique())}
            if base is not None:
                riga |= {"riferimento": float(base[m].mean()), "mediana": float(base[m].median()),
                         "p25": float(base[m].quantile(0.25)), "p75": float(base[m].quantile(0.75))}
            righe.append(riga)
    return pd.DataFrame(righe)


def _quota(valore, riferimento) -> float:
    if riferimento is None or pd.isna(riferimento) or riferimento == 0:
        return np.nan
    return 100.0 * valore / riferimento


def allenamento_partita(v: Visibile) -> Risultato:
    """Seduta di oggi e settimana finora come % della partita tipo da titolare di ciascun giocatore."""
    oggi, ctx = v.oggi, v.contesto
    ana = anagrafica(v)
    rif = riferimenti_partita(v.storico, v.giocatori)
    avvisi = [AVVISO_RISCALDAMENTO]
    if ctx.giorno_md is None:
        return Risultato("allenamento_partita", oggi, pd.DataFrame(), avvisi=["oggi è un giorno di pausa"] + avvisi)

    sett = settimana_di(v, oggi)
    righe = tutte_le_righe(v)
    allen = righe[(righe["tipo"] == "allenamento") & sett.contiene(righe["data"])]
    somma_sett = allen.groupby("giocatore_id")[list(METRICHE)].sum()
    sedute_sett = allen.groupby("giocatore_id").size()
    oggi_r = v.seduta_di_oggi.set_index("giocatore_id")

    # "di solito a questo punto della settimana": settimane passate tagliate allo stesso giorno MD
    passate = settimane_regolari(v, sett.partita_iniziale)
    solito: dict[tuple[int, str], list[float]] = {}
    for w in passate:
        fine = taglio(w, ctx.giorno_md)
        a = v.storico[(v.storico["tipo"] == "allenamento") & w.contiene(v.storico["data"]) & (v.storico["data"] <= fine)]
        for gid, s in a.groupby("giocatore_id")[list(METRICHE)].sum().iterrows():
            for m in METRICHE:
                solito.setdefault((gid, m), []).append(s[m])
    if not sett.regolare:
        avvisi.append("settimana non regolare (pausa o periodo senza dati): il confronto col solito è indicativo")

    giocatori = sorted(set(sedute_sett.index) | set(oggi_r.index))
    tab, evid = [], []
    for gid in giocatori:
        nome = ana.loc[gid, "nome_completo"]
        for m in METRICHE:
            r = rif[(rif["giocatore_id"] == gid) & (rif["metrica"] == m)].iloc[0]
            ref = r["riferimento"]
            v_oggi = float(oggi_r.loc[gid, m]) if gid in oggi_r.index else np.nan
            v_sett = float(somma_sett.loc[gid, m]) if gid in somma_sett.index else 0.0
            quote_solite = [_quota(x, ref) for x in solito.get((gid, m), [])]
            q = np.percentile(quote_solite, (25, 50, 75)) if len(quote_solite) >= MIN_SETTIMANE_SOLITO else [np.nan] * 3
            q_larga = np.percentile(quote_solite, (10, 90)) if len(quote_solite) >= MIN_SETTIMANE_SOLITO else [np.nan] * 2   # avvisi
            riga = {"giocatore_id": gid, "giocatore": nome, "metrica": m, "riferimento": ref, "livello": r["livello"],
                    "partite": int(r["partite"]), "oggi": v_oggi, "oggi_pct": _quota(v_oggi, ref),
                    "settimana": v_sett, "settimana_pct": _quota(v_sett, ref),
                    "sedute_settimana": int(sedute_sett.get(gid, 0)),
                    "solito_p25": q[0], "solito_p50": q[1], "solito_p75": q[2], "settimane_solito": len(quote_solite),
                    "solito_p10": q_larga[0], "solito_p90": q_larga[1]}
            tab.append(riga)
            if pd.isna(ref):
                continue
            base = f"partita/{oggi:%Y-%m-%d}/{gid}/{m}"
            u = UNITA[m]
            evid.append(evidenza(f"{base}/riferimento", f"{maiuscola(NOME_METRICA[m])} di riferimento in partita di {nome}",
                                 ref, u, grafico=f"partita/{gid}/{m}", giocatore_id=gid, giocatore=nome, metrica=m,
                                 livello=r["livello"], partite=int(r["partite"]), prestazioni=int(r["prestazioni"]),
                                 mediana=arrotonda(r["mediana"], u), fascia_partite=[arrotonda(r["p25"], u), arrotonda(r["p75"], u)],
                                 definizione="media dei carichi osservati nelle sue partite da titolare prima di oggi"
                                 if r["livello"] == "personale" else "media dei carichi dei titolari del ruolo prima di oggi"))
            if not pd.isna(v_oggi):
                evid.append(evidenza(f"{base}/oggi", f"{maiuscola(NOME_METRICA[m])} di {nome} oggi in % della sua partita di riferimento",
                                     riga["oggi_pct"], "%", grafico=f"partita/{gid}/{m}", giocatore_id=gid, giocatore=nome,
                                     metrica=m, data=oggi, giorno_md=ctx.giorno_md, carico=arrotonda(v_oggi, u),
                                     riferimento=arrotonda(ref, u)))
            if riga["sedute_settimana"]:
                evid.append(evidenza(f"{base}/settimana", f"{maiuscola(NOME_METRICA[m])} di {nome}: allenamenti della settimana finora in % della partita di riferimento",
                                     riga["settimana_pct"], "%", grafico=f"partita/{gid}/{m}", giocatore_id=gid,
                                     giocatore=nome, metrica=m, fino_a=oggi, giorno_md=ctx.giorno_md,
                                     sedute=riga["sedute_settimana"], carico=arrotonda(v_sett, u), riferimento=arrotonda(ref, u),
                                     solito=[arrotonda(x, "%") for x in q] if len(quote_solite) >= MIN_SETTIMANE_SOLITO else None,
                                     settimane_solito=len(quote_solite)))
    tab = pd.DataFrame(tab)
    sintesi = {"data": oggi, "giorno_md": ctx.giorno_md, "settimana_dal": sett.partita_iniziale,
               "prossima_partita": sett.partita_finale, "settimana_regolare": sett.regolare,
               "giocatori": len(giocatori)}
    if len(tab):
        for m in ("td", "hsr", "spr"):
            t = tab[(tab["metrica"] == m) & tab["sedute_settimana"].gt(0)]
            if len(t):
                sintesi[f"settimana_pct_mediana_{m}"] = arrotonda(t["settimana_pct"].median(), "%")
                o = tab[(tab["metrica"] == m)]["oggi_pct"].dropna()
                evid.append(evidenza(f"partita/{oggi:%Y-%m-%d}/squadra/{m}",
                                     f"{maiuscola(NOME_METRICA[m])}: allenamenti della settimana finora in % della partita di riferimento, mediana della squadra",
                                     t["settimana_pct"].median(), "%", grafico=f"partita/squadra/{m}", metrica=m, fino_a=oggi,
                                     giorno_md=ctx.giorno_md, giocatori=int(len(t)),
                                     oggi_mediana_pct=arrotonda(o.median(), "%") if len(o) else None))
    return Risultato("allenamento_partita", oggi, tab, evid, avvisi, sintesi)

