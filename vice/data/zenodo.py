"""Zenodo 18986229 → formato Vice (M1.2).

Il CSV originale (data/raw/zenodo/DataSetTMr.csv) ha una riga per giocatore × giorno. Qui diventa
quattro tabelle indipendenti dal fornitore:

- `partite`:   calendario delle partite (anche le 2 senza dati GPS, ricostruite dai giorni MD);
- `sedute`:    un giorno per riga (allenamento o partita), con giorno MD e partite di riferimento;
- `carichi`:   giocatore × giorno, con ruolo, titolare nell'ultima partita e le 6 metriche;
- `giocatori`: id del dataset e ruolo (i nomi di fantasia stanno in `anagrafica.py`).

Scelte (dettagli e numeri in wiki/dati/pipeline-zenodo.md):
- "titolare" = titolare nell'**ultima partita giocata** prima della seduta, ricavato dalla riga
  della partita; senza riga in quella partita = non titolare. Non si usa `ESTATUS` delle sedute:
  in 55 righe anticipa la formazione della partita successiva (dato dal futuro). Se l'ultima
  partita non ha dati GPS, il valore resta sconosciuto.
- Le colonne `RATIO*` del dataset dividono per un valore di partita stagionale del giocatore
  (nei dati è la sua media da titolare, non il massimo dichiarato dall'articolo), cioè usano
  anche partite future: si conservano solo per il confronto di M2.6 e non entrano nell'"oggi"
  simulato.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ORIGINE_EXCEL = pd.Timestamp("1899-12-30")  # giorno 0 dei numeri seriali di Excel

RUOLI = {
    "CEN": "difensore centrale",
    "LAT": "terzino",
    "MED": "centrocampista",
    "EXT": "esterno",
    "DEL": "attaccante",
}
METRICHE = {  # colonna Vice → (colonna Zenodo, unità, descrizione)
    "td": ("TD", "m", "distanza totale"),
    "hsr": ("HSR", "m", "distanza ad alta velocità (> 19,8 km/h)"),
    "spr": ("SPR", "m", "distanza in sprint (> 25,2 km/h)"),
    "acc": ("ACC", "n", "accelerazioni"),
    "dcc": ("DCC", "n", "decelerazioni"),
    "hmld": ("HMLD", "m", "distanza ad alto carico metabolico"),
}
DIACAT_ATTESO = {-5: 5, -4: 4, -3: 3, -2: 2, -1: 1, 0: 0, 1: 11, 2: 22}


class FormatoNonValido(ValueError):
    pass


@dataclass(frozen=True)
class DatiZenodo:
    partite: pd.DataFrame
    sedute: pd.DataFrame
    carichi: pd.DataFrame
    giocatori: pd.DataFrame


def leggi_csv(path: Path) -> pd.DataFrame:
    """CSV originale: separatore `;`, virgola decimale, BOM nell'intestazione."""
    raw = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    attese = {"FECHA", "PlayerID", "POS", "MICRO", "DIA", "DIACat", "ESTATUS"} | {c for c, _, _ in METRICHE.values()}
    mancanti = attese - set(raw.columns)
    if mancanti:
        raise FormatoNonValido(f"colonne mancanti nel CSV Zenodo: {sorted(mancanti)}")
    return raw


def converti(raw: pd.DataFrame) -> DatiZenodo:
    df = pd.DataFrame({
        "data": ORIGINE_EXCEL + pd.to_timedelta(raw["FECHA"].astype(int), unit="D"),
        "giocatore_id": raw["PlayerID"].astype(int),
        "ruolo_codice": raw["POS"].astype(str),
        "giorno_md": raw["DIA"].astype(int),
        "microciclo_dataset": raw["MICRO"].astype(int),
        "estatus_dataset": raw["ESTATUS"].astype(str),
    })
    _controlla_codici(raw, df)
    df["ruolo"] = df["ruolo_codice"].map(RUOLI)
    df["tipo"] = df["giorno_md"].map(lambda d: "partita" if d == 0 else "allenamento")
    for col, (orig, _, _) in METRICHE.items():
        df[col] = raw[orig].astype(float)
    for col, (orig, _, _) in METRICHE.items():
        df[f"rapporto_{col}_dataset"] = raw[f"RATIO{orig}"].astype(float)

    partite = _calendario(df)
    df = _aggiungi_titolare(df, partite)
    sedute = _sedute(df, partite)
    giocatori = (df.groupby("giocatore_id")
                 .agg(ruolo_codice=("ruolo_codice", "first"), ruolo=("ruolo", "first"))
                 .reset_index())
    colonne = (["data", "giocatore_id", "ruolo", "tipo", "giorno_md", "titolare_ultima_partita"]
               + list(METRICHE)
               + [f"rapporto_{c}_dataset" for c in METRICHE] + ["microciclo_dataset", "estatus_dataset"])
    carichi = df[colonne].sort_values(["data", "giocatore_id"]).reset_index(drop=True)
    return DatiZenodo(partite=partite, sedute=sedute, carichi=carichi, giocatori=giocatori)


def _controlla_codici(raw: pd.DataFrame, df: pd.DataFrame) -> None:
    sconosciuti = set(df["ruolo_codice"]) - set(RUOLI)
    if sconosciuti:
        raise FormatoNonValido(f"ruoli sconosciuti: {sorted(sconosciuti)}")
    if not df["giorno_md"].between(-5, 2).all():
        raise FormatoNonValido("giorno MD fuori dall'intervallo -5…+2")
    diacat = raw["DIACat"].astype(int)
    if not (df["giorno_md"].map(DIACAT_ATTESO) == diacat).all():
        raise FormatoNonValido("DIACat non coerente con DIA (attesi 11 = MD+1, 22 = MD+2)")
    if not df["estatus_dataset"].isin(["T", "S"]).all():
        raise FormatoNonValido("ESTATUS diverso da T/S")


def _calendario(df: pd.DataFrame) -> pd.DataFrame:
    """Partite registrate (righe con MD 0) più quelle implicite nei giorni MD (data − giorno MD)."""
    registrate = set(df.loc[df["giorno_md"] == 0, "data"])
    implicite = set(df["data"] - pd.to_timedelta(df["giorno_md"], unit="D"))
    date = sorted(registrate | implicite)
    giocatori = df[df["giorno_md"] == 0].groupby("data")["giocatore_id"].nunique()
    partite = pd.DataFrame({"data": date})
    partite["dati_gps"] = partite["data"].isin(registrate)
    partite["giocatori_con_dati"] = partite["data"].map(giocatori).fillna(0).astype(int)
    return partite


def _aggiungi_titolare(df: pd.DataFrame, partite: pd.DataFrame) -> pd.DataFrame:
    """Titolare nell'ultima partita giocata (quella del giorno stesso, se è giorno di partita)."""
    cal = partite.sort_values("data")[["data", "dati_gps"]].rename(columns={"data": "ultima_partita"})
    df = pd.merge_asof(df.sort_values("data"), cal, left_on="data", right_on="ultima_partita",
                       direction="backward")
    in_partita = (df.loc[df["giorno_md"] == 0, ["data", "giocatore_id", "estatus_dataset"]]
                  .rename(columns={"data": "ultima_partita", "estatus_dataset": "status_partita"}))
    df = df.merge(in_partita, on=["ultima_partita", "giocatore_id"], how="left")
    con_dati = df["dati_gps"].fillna(False).astype(bool)
    titolare = pd.Series(pd.NA, index=df.index, dtype="boolean")  # sconosciuto se la partita non ha dati
    titolare[con_dati] = df.loc[con_dati, "status_partita"].eq("T")  # niente riga = non ha giocato
    df["titolare_ultima_partita"] = titolare
    return df.drop(columns=["ultima_partita", "dati_gps", "status_partita"])


def _sedute(df: pd.DataFrame, partite: pd.DataFrame) -> pd.DataFrame:
    giorni = (df.groupby("data")
              .agg(tipo=("tipo", "first"), giorno_md=("giorno_md", "first"),
                   giorno_md_unico=("giorno_md", "nunique"), giocatori=("giocatore_id", "nunique"),
                   microciclo_dataset=("microciclo_dataset", "first"))
              .reset_index())
    if (giorni["giorno_md_unico"] > 1).any():
        raise FormatoNonValido("lo stesso giorno ha giorni MD diversi")
    cal = partite[["data"]].sort_values("data")
    giorni = pd.merge_asof(giorni.sort_values("data"), cal.rename(columns={"data": "ultima_partita"}),
                           left_on="data", right_on="ultima_partita", direction="backward")
    giorni = pd.merge_asof(giorni, cal.rename(columns={"data": "prossima_partita"}),
                           left_on="data", right_on="prossima_partita", direction="forward")
    return giorni.drop(columns="giorno_md_unico")


# ---------- salvataggio e lettura dei dati elaborati ----------

TABELLE = ("partite", "sedute", "carichi", "giocatori")


def salva(dati: DatiZenodo, cartella: Path) -> list[Path]:
    cartella.mkdir(parents=True, exist_ok=True)
    percorsi = []
    for nome in TABELLE:
        p = cartella / f"{nome}.parquet"
        getattr(dati, nome).to_parquet(p, index=False)
        percorsi.append(p)
    return percorsi


def carica(cartella: Path) -> DatiZenodo:
    return DatiZenodo(**{nome: pd.read_parquet(cartella / f"{nome}.parquet") for nome in TABELLE})
