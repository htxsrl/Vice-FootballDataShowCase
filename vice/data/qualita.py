"""Controlli di qualità sui dati Zenodo nel formato Vice (M1.4).

Il risultato (un dizionario semplice) si salva in data/processed/zenodo/qualita.json e i numeri
finiscono in wiki/dati/pipeline-zenodo.md.
"""

from __future__ import annotations

import pandas as pd

from .zenodo import METRICHE, DatiZenodo


def controlli_zenodo(d: DatiZenodo) -> dict:
    c, s, p = d.carichi, d.sedute, d.partite
    q: dict = {}

    q["conteggi"] = {
        "righe": len(c),
        "giocatori": int(c["giocatore_id"].nunique()),
        "giorni_di_seduta": len(s),
        "giorni_di_allenamento": int((s["tipo"] == "allenamento").sum()),
        "partite_con_dati_gps": int(p["dati_gps"].sum()),
        "partite_in_calendario": len(p),
        "partite_senza_dati_gps": [x.date().isoformat() for x in p.loc[~p["dati_gps"], "data"]],
        "microcicli_dataset": int(c["microciclo_dataset"].nunique()),
        "dal": c["data"].min().date().isoformat(),
        "al": c["data"].max().date().isoformat(),
        "righe_per_giorno_md": {int(k): int(v) for k, v in c["giorno_md"].value_counts().sort_index().items()},
        "righe_per_ruolo": {k: int(v) for k, v in c["ruolo"].value_counts().items()},
    }

    q["integrita"] = {
        "duplicati_giocatore_giorno": int(c.duplicated(["giocatore_id", "data"]).sum()),
        "valori_nulli": {m: int(c[m].isna().sum()) for m in METRICHE},
        "valori_negativi": {m: int((c[m] < 0).sum()) for m in METRICHE},
        "giocatori_con_piu_ruoli": int((c.groupby("giocatore_id")["ruolo"].nunique() > 1).sum()),
    }

    zeri_hsr = c[c["hsr"] == 0]
    q["zeri_e_valori_bassi"] = {
        "hsr_zero": len(zeri_hsr),
        "hsr_zero_per_giorno_md": {int(k): int(v) for k, v in zeri_hsr["giorno_md"].value_counts().sort_index().items()},
        "spr_zero": int((c["spr"] == 0).sum()),
        "td_sotto_500_m": c.loc[c["td"] < 500, ["data", "giocatore_id", "giorno_md", "td"]]
            .assign(data=lambda x: x["data"].dt.date.astype(str)).to_dict("records"),
    }

    # Valori molto lontani dal solito per metrica × giorno MD (oltre Q3 + 3 × IQR): segnalati, non tolti.
    estremi = {}
    for m in METRICHE:
        g = c.groupby("giorno_md")[m]
        soglia = g.transform(lambda x: x.quantile(0.75) + 3 * (x.quantile(0.75) - x.quantile(0.25)))
        estremi[m] = int((c[m] > soglia).sum())
    q["valori_estremi_q3_piu_3iqr"] = estremi

    # Calendario: giorni MD coerenti con le partite, distanza tra le partite.
    pre, post = s[s["giorno_md"] < 0], s[s["giorno_md"] > 0]
    gap = p["data"].sort_values().diff().dt.days.dropna().astype(int)
    q["calendario"] = {
        "giorni_md_coerenti_prima_della_partita": float(((pre["prossima_partita"] - pre["data"]).dt.days == -pre["giorno_md"]).mean()),
        "giorni_md_coerenti_dopo_la_partita": float(((post["data"] - post["ultima_partita"]).dt.days == post["giorno_md"]).mean()),
        "giorni_tra_partite": {int(k): int(v) for k, v in gap.value_counts().sort_index().items()},
        "settimane_con_due_partite": int((gap <= 4).sum()),
    }

    # Titolare: ricostruito dall'ultima partita contro ESTATUS del dataset.
    noto = c["titolare_ultima_partita"].notna()
    uguale = c.loc[noto, "titolare_ultima_partita"] == c.loc[noto, "estatus_dataset"].eq("T")
    prossima = _titolare_prossima_partita(d)
    diversi = c.loc[noto][~uguale.values]
    q["titolare"] = {
        "righe_con_titolare_noto": int(noto.sum()),
        "concordanza_con_estatus": float(uguale.mean()),
        "righe_discordanti": len(diversi),
        "discordanti_dove_estatus_anticipa_la_partita_successiva": int(
            (diversi["estatus_dataset"].eq("T").values == prossima.loc[diversi.index].values).sum()),
    }

    # Settimana tipo (mediane): serve a documentare la plausibilità dei dati.
    tipo = (c.groupby(["giorno_md", "titolare_ultima_partita"])[["td", "hsr", "spr"]].median()
            .round(0).reset_index())
    q["mediane_per_giorno_md_e_titolare"] = [
        {"giorno_md": int(r.giorno_md), "titolare": bool(r.titolare_ultima_partita),
         "td": float(r.td), "hsr": float(r.hsr), "spr": float(r.spr)}
        for r in tipo.itertuples()
    ]
    return q


def _titolare_prossima_partita(d: DatiZenodo) -> pd.Series:
    """Per ogni riga: il giocatore è stato titolare nella partita successiva? (solo per il controllo)."""
    c = d.carichi.merge(d.sedute[["data", "prossima_partita"]], on="data", how="left")
    in_partita = (c.loc[c["giorno_md"] == 0, ["data", "giocatore_id", "estatus_dataset"]]
                  .rename(columns={"data": "prossima_partita", "estatus_dataset": "st"}))
    c = c.merge(in_partita, on=["prossima_partita", "giocatore_id"], how="left")
    return pd.Series(c["st"].eq("T").values, index=d.carichi.index)
