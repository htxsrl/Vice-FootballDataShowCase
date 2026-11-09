"""Anagrafica di fantasia della squadra Zenodo (M1.3, decisione 21).

I giocatori di Zenodo 18986229 sono anonimi (codici da 1 a 20): Vice dà loro nomi italiani
inventati e alla squadra un nome inventato. Lista approvata da Ivan il 21/10/2026; fissa, quindi
uguale a ogni avvio. Ruoli e numeri seguono i dati: numeri "da titolare" a chi ha giocato di più
da titolare. La dicitura va mostrata nell'app, nei report esportati e nel PDF.
"""

from __future__ import annotations

import pandas as pd

SQUADRA = "AS New Trieste"

DICITURA = ("Nomi dei giocatori e della squadra di fantasia; dati reali anonimi del dataset "
            "Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0).")

# id del dataset → (nome, cognome, numero di maglia, ruolo atteso)
GIOCATORI: dict[int, tuple[str, str, int, str]] = {
    11: ("Andrea", "Melis", 2, "terzino"),
    15: ("Edoardo", "Tosi", 3, "terzino"),
    10: ("Michele", "Valli", 22, "terzino"),
    6: ("Riccardo", "Benedetti", 4, "difensore centrale"),
    4: ("Alessio", "Dalmasso", 5, "difensore centrale"),
    8: ("Stefano", "Guidi", 15, "difensore centrale"),
    12: ("Pietro", "Ghio", 23, "difensore centrale"),
    1: ("Tommaso", "Ferrandi", 8, "centrocampista"),
    13: ("Federico", "Santini", 6, "centrocampista"),
    3: ("Nicolò", "Serafini", 16, "centrocampista"),
    17: ("Filippo", "Rinaldi", 14, "centrocampista"),
    2: ("Elia", "Gariglio", 21, "centrocampista"),
    16: ("Luca", "Cerutti", 7, "esterno"),
    14: ("Gabriele", "Longo", 11, "esterno"),
    9: ("Lorenzo", "Cortese", 17, "esterno"),
    5: ("Samuele", "Pinna", 20, "esterno"),
    19: ("Christian", "Porcu", 27, "esterno"),
    18: ("Matteo", "Basile", 9, "attaccante"),
    20: ("Simone", "Amato", 10, "attaccante"),
    7: ("Mattia", "Bosio", 19, "attaccante"),
}


class AnagraficaNonCoerente(ValueError):
    pass


def con_nomi(giocatori: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge nome, cognome, nome completo e numero alla tabella `giocatori` del formato Vice."""
    mancanti = set(giocatori["giocatore_id"]) - set(GIOCATORI)
    if mancanti:
        raise AnagraficaNonCoerente(f"giocatori senza nome di fantasia: {sorted(mancanti)}")
    out = giocatori.copy()
    out["nome"] = out["giocatore_id"].map(lambda i: GIOCATORI[i][0])
    out["cognome"] = out["giocatore_id"].map(lambda i: GIOCATORI[i][1])
    out["nome_completo"] = out["nome"] + " " + out["cognome"]
    out["numero"] = out["giocatore_id"].map(lambda i: GIOCATORI[i][2])
    diversi = out[out["ruolo"] != out["giocatore_id"].map(lambda i: GIOCATORI[i][3])]
    if len(diversi):
        raise AnagraficaNonCoerente(f"ruolo diverso dai dati per i giocatori {list(diversi['giocatore_id'])}")
    return out.sort_values(["numero"]).reset_index(drop=True)
