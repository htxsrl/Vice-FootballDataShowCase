"""Export di una seduta e adattatore che lo rilegge nel formato Vice (M1.6, M4.8).

Dimostra il percorso "il club carica il suo export". Due formati accettati, riconosciuti dalle colonne:

- **Zenodo**: le righe del giorno così come stanno nel CSV del dataset Zenodo 18986229
  (`FECHA` seriale di Excel, `PlayerID`, `DIA`, `ESTATUS`, metriche, `RATIO*`…). Si usano solo data,
  codice del giocatore, tipo di seduta e metriche; `ESTATUS` solo nelle partite (chi è partito
  titolare). `RATIO*`, `MICRO` ed `ESTATUS` degli allenamenti contengono informazioni dal futuro e si
  ignorano, come nel motore.
- **"Da GPS"**: solo ciò che un GPS sa (nome del giocatore, data, tipo di seduta, metriche); nelle
  partite la colonna facoltativa "Starter", perché il GPS non sa chi è partito titolare.

Giorno MD, ruolo e titolare negli allenamenti li ricava Vice dal suo calendario e dalla sua anagrafica,
come farebbe con un club vero.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from .stagione import Stagione
from .zenodo import METRICHE, ORIGINE_EXCEL

COLONNE_METRICHE = {
    "Total Distance (m)": "td",
    "High Speed Running (m)": "hsr",
    "Sprint Distance (m)": "spr",
    "Accelerations": "acc",
    "Decelerations": "dcc",
    "HML Distance (m)": "hmld",
}
OBBLIGATORIE = ["Player Name", "Session Date", "Session Type", *COLONNE_METRICHE]
TIPI = {"Training": "allenamento", "Match": "partita"}
# formato Zenodo 18986229: colonna del CSV → metrica Vice
COLONNE_ZENODO = {col: m for m, (col, _, _) in METRICHE.items()}
OBBLIGATORIE_ZENODO = ["FECHA", "PlayerID", *COLONNE_ZENODO]


class ErroreExport(ValueError):
    """Export non valido: il messaggio è in italiano e si può mostrare all'utente."""


def esporta_seduta(seduta: pd.DataFrame, giocatori: pd.DataFrame) -> str:
    """Una seduta del formato Vice (righe di un solo giorno) → testo CSV dell'export."""
    if seduta["data"].nunique() != 1:
        raise ValueError("un export contiene una sola seduta")
    nomi = giocatori.set_index("giocatore_id")["nome_completo"]
    tipo = seduta["tipo"].iloc[0]
    out = pd.DataFrame({
        "Player Name": seduta["giocatore_id"].map(nomi),
        "Session Date": seduta["data"].dt.strftime("%Y-%m-%d"),
        "Session Type": "Match" if tipo == "partita" else "Training",
    })
    for col, m in COLONNE_METRICHE.items():
        out[col] = seduta[m].round().astype(int)
    if tipo == "partita":
        out["Starter"] = seduta["titolare_ultima_partita"].map({True: "Yes", False: "No"})
    return out.sort_values("Player Name").to_csv(index=False)


def righe_zenodo(csv_zenodo: Path, giorno) -> str:
    """Le righe di un giorno copiate **così come sono** dal CSV originale di Zenodo 18986229, con la sua
    intestazione: il file di prova "preso da Zenodo" da caricare nella demo (CC BY 4.0)."""
    if not csv_zenodo.exists():
        raise ErroreExport("Manca il CSV di Zenodo: scaricalo con scripts.scarica_zenodo.")
    righe = csv_zenodo.read_text(encoding="utf-8-sig").splitlines()
    seriale = str((pd.Timestamp(giorno).normalize() - ORIGINE_EXCEL).days)
    giorno_righe = [r for r in righe[1:] if r.split(";", 1)[0] == seriale]
    if not giorno_righe:
        raise ErroreExport(f"Nel CSV di Zenodo non ci sono righe del {pd.Timestamp(giorno):%d/%m/%Y}.")
    return "\r\n".join([righe[0], *giorno_righe]) + "\r\n"


def formato(colonne) -> str:
    """ "zenodo" se il file ha le colonne del dataset Zenodo, altrimenti "gps"."""
    return "zenodo" if {"FECHA", "PlayerID"} <= {str(c).strip() for c in colonne} else "gps"


def leggi_export(contenuto: str | bytes, stagione: Stagione) -> pd.DataFrame:
    """Testo CSV di un export (formato Zenodo o "da GPS") → righe nel formato Vice (come `Visibile.seduta_di_oggi`)."""
    if isinstance(contenuto, bytes):
        contenuto = contenuto.decode("utf-8-sig", errors="replace")
    contenuto = contenuto.lstrip("\ufeff")
    if not contenuto.strip():
        raise ErroreExport("Il file è vuoto.")
    try:  # separatore "," o ";" (Excel in italiano, CSV di Zenodo)
        df = pd.read_csv(io.StringIO(contenuto), sep=None, engine="python", dtype=str)
    except Exception as exc:  # noqa: BLE001
        raise ErroreExport(f"Non riesco a leggere il CSV: {exc}") from exc
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda col: col.str.strip())
    if formato(df.columns) == "zenodo":
        giorno, tipo, ids, metriche, starter = _da_zenodo(df, stagione)
    else:
        giorno, tipo, ids, metriche, starter = _da_gps(df, stagione)
    return _righe_vice(giorno, tipo, ids, metriche, starter, stagione)


def _numeri(colonna: pd.Series, nome: str) -> pd.Series:
    valori = pd.to_numeric(colonna.str.replace(",", ".", regex=False), errors="coerce")
    if valori.isna().any() or (valori < 0).any():
        raise ErroreExport(f'Valori mancanti, non numerici o negativi nella colonna "{nome}".')
    return valori.astype(float)


def _da_gps(df: pd.DataFrame, stagione: Stagione):
    mancanti = [c for c in OBBLIGATORIE if c not in df.columns]
    if mancanti:
        raise ErroreExport(f"Mancano le colonne: {', '.join(mancanti)}.")
    date = pd.to_datetime(df["Session Date"], errors="coerce", format="%Y-%m-%d")
    if date.isna().any():
        raise ErroreExport("Alcune date non sono nel formato AAAA-MM-GG.")
    if date.nunique() != 1:
        raise ErroreExport("Il file deve contenere una sola seduta (una sola data).")
    tipi = df["Session Type"].map(TIPI)
    if tipi.isna().any() or tipi.nunique() != 1:
        raise ErroreExport('La colonna "Session Type" deve valere "Training" o "Match", uguale per tutte le righe.')
    g = stagione.al(date.iloc[0]).giocatori
    per_nome = dict(zip(g["nome_completo"].str.casefold(), g["giocatore_id"]))
    ids = df["Player Name"].str.casefold().map(per_nome)
    if ids.isna().any():
        raise ErroreExport(f"Giocatori non in rosa: {', '.join(df.loc[ids.isna(), 'Player Name'])}.")
    metriche = pd.DataFrame({m: _numeri(df[col], col).values for col, m in COLONNE_METRICHE.items()})
    starter = None
    if "Starter" in df.columns:
        starter = df["Starter"].str.casefold().map({"yes": True, "no": False})
    return date.iloc[0], tipi.iloc[0], ids, metriche, starter


def _da_zenodo(df: pd.DataFrame, stagione: Stagione):
    mancanti = [c for c in OBBLIGATORIE_ZENODO if c not in df.columns]
    if mancanti:
        raise ErroreExport(f"Mancano le colonne del formato Zenodo: {', '.join(mancanti)}.")
    seriale = pd.to_numeric(df["FECHA"], errors="coerce")
    if seriale.isna().any():
        raise ErroreExport('La colonna "FECHA" deve contenere la data come numero seriale di Excel (per esempio 45400).')
    date = ORIGINE_EXCEL + pd.to_timedelta(seriale.astype(int), unit="D")
    if date.nunique() != 1:
        raise ErroreExport("Il file deve contenere una sola seduta (una sola data): dal CSV di Zenodo vanno prese le righe di un giorno.")
    giorno = date.iloc[0]
    if "DIA" in df.columns:
        dia = pd.to_numeric(df["DIA"], errors="coerce")
        if dia.isna().any() or dia.nunique() != 1:
            raise ErroreExport('La colonna "DIA" deve avere lo stesso giorno MD in tutte le righe.')
        tipo = "partita" if int(dia.iloc[0]) == 0 else "allenamento"
    else:
        md = stagione.al(giorno).contesto.giorno_md
        tipo = "partita" if md == 0 else "allenamento"
    codici = pd.to_numeric(df["PlayerID"], errors="coerce")
    validi = set(stagione.al(giorno).giocatori["giocatore_id"])
    fuori = df.loc[codici.isna() | ~codici.isin(validi), "PlayerID"]
    if len(fuori):
        raise ErroreExport(f"Codici di giocatore non in rosa: {', '.join(fuori)}.")
    metriche = pd.DataFrame({m: _numeri(df[col], col).values for col, m in COLONNE_ZENODO.items()})
    starter = None
    if tipo == "partita" and "ESTATUS" in df.columns:   # solo nelle partite: negli allenamenti anticipa il futuro
        starter = df["ESTATUS"].str.upper().map({"T": True, "S": False})
    return giorno, tipo, codici.astype(int), metriche, starter


def _righe_vice(giorno, tipo, ids: pd.Series, metriche: pd.DataFrame, starter, stagione: Stagione) -> pd.DataFrame:
    vista = stagione.al(giorno)
    if vista.contesto.giorno_md is None:
        raise ErroreExport(f"Il {giorno:%d/%m/%Y} non è in nessun microciclo della stagione (giorno di pausa).")
    tipo_atteso = "partita" if vista.contesto.giorno_md == 0 else "allenamento"
    if tipo != tipo_atteso:
        raise ErroreExport(f"Il {giorno:%d/%m/%Y} secondo il calendario è un giorno di {tipo_atteso}, "
                           f"ma il file dice {tipo}.")
    ids = pd.Series(ids).reset_index(drop=True)
    if ids.duplicated().any():
        g = vista.giocatori.set_index("giocatore_id")["nome_completo"]
        raise ErroreExport(f"Giocatori ripetuti: {', '.join(g.get(int(i), str(i)) for i in ids[ids.duplicated()])}.")
    g = vista.giocatori
    out = pd.DataFrame({"data": [giorno] * len(ids), "giocatore_id": ids.astype(int).values})
    out["ruolo"] = out["giocatore_id"].map(g.set_index("giocatore_id")["ruolo"])
    out["tipo"] = tipo
    out["giorno_md"] = vista.contesto.giorno_md
    out["titolare_ultima_partita"] = _titolare(starter, out, vista, tipo)
    for m in METRICHE:
        out[m] = metriche[m].values
    return out[["data", "giocatore_id", "ruolo", "tipo", "giorno_md", "titolare_ultima_partita", *METRICHE]] \
        .sort_values("giocatore_id").reset_index(drop=True)


def _titolare(starter, out: pd.DataFrame, vista, tipo: str) -> pd.Series:
    if tipo == "partita":  # lo dice il file, se c'è la colonna ("Starter" o ESTATUS di Zenodo)
        if starter is None:
            return pd.Series(pd.NA, index=out.index, dtype="boolean")
        return pd.Series(pd.Series(starter).values, index=out.index, dtype="boolean")
    # allenamento: titolare nell'ultima partita giocata, dallo storico di Vice
    ultima = vista.contesto.ultima_partita
    con_dati = vista.partite_giocate.set_index("data")["dati_gps"]
    if ultima is None or not bool(con_dati.get(ultima, False)):
        return pd.Series(pd.NA, index=out.index, dtype="boolean")
    in_partita = vista.storico[vista.storico["data"] == ultima].set_index("giocatore_id")["titolare_ultima_partita"]
    return pd.Series(out["giocatore_id"].map(in_partita).fillna(False).astype(bool).values,
                     index=out.index, dtype="boolean")
