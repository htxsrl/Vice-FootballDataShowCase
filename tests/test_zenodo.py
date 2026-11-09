"""M1.2: conversione di Zenodo 18986229 nel formato Vice, su un CSV sintetico con i casi difficili."""

import pandas as pd
import pytest

from vice.data import zenodo

INTESTAZIONE = ("FECHA;PlayerID;POS;POSCat;MICRO;DIA;DIACat;ESTATUS;ESTCat;TD;HSR;SPR;ACC;DCC;HMLD;"
                "RATIOTD;RATIOHSR;RATIOSPR;RATIOACC;RATIODCC;RATIOHMLD")
DIACAT = {-5: 5, -4: 4, -3: 3, -2: 2, -1: 1, 0: 0, 1: 11, 2: 22}


def riga(fecha, giocatore, dia, estatus, td, pos="MED", diacat=None):
    diacat = DIACAT[dia] if diacat is None else diacat
    return f"{fecha};{giocatore};{pos};6;8;{dia};{diacat};{estatus};1;{td};100;20;10;12;500;0,5;0,25;0;1;1;0,75"


def csv_sintetico(tmp_path, righe):
    p = tmp_path / "zenodo.csv"
    p.write_text("﻿" + "\n".join([INTESTAZIONE, *righe]) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def dati(tmp_path):
    # 45179 = 10/09/2023 (partita), 45180 = MD+1, 45183 = MD-2, 45185 = 16/09 (partita),
    # 45190 = MD-2 di una partita del 23/09 che non ha righe (partita senza dati GPS).
    righe = [
        riga(45179, 1, 0, "T", 10000), riga(45179, 2, 0, "S", 3000),
        riga(45180, 1, 1, "T", 1700), riga(45180, 2, 1, "S", 4300), riga(45180, 3, 1, "S", 4400, pos="CEN"),
        # il giocatore 2 sarà titolare il 16/09: ESTATUS lo anticipa già a MD-2 (dato dal futuro)
        riga(45183, 1, -2, "T", 5100), riga(45183, 2, -2, "T", 5200), riga(45183, 3, -2, "S", 5300, pos="CEN"),
        riga(45185, 1, 0, "S", 2500), riga(45185, 2, 0, "T", 9900),
        riga(45190, 1, -2, "S", 5000),
    ]
    return zenodo.converti(zenodo.leggi_csv(csv_sintetico(tmp_path, righe)))


def test_date_e_tipi(dati):
    c = dati.carichi
    assert c["data"].min() == pd.Timestamp("2023-09-10")
    assert set(c.loc[c["giorno_md"] == 0, "tipo"]) == {"partita"}
    assert set(c.loc[c["giorno_md"] != 0, "tipo"]) == {"allenamento"}
    assert c.loc[0, "rapporto_td_dataset"] == 0.5        # virgola decimale
    assert set(c["ruolo"]) == {"centrocampista", "difensore centrale"}


def test_calendario_con_partita_senza_dati(dati):
    p = dati.partite
    assert list(p["data"].dt.strftime("%d/%m")) == ["10/09", "16/09", "23/09"]
    assert list(p["dati_gps"]) == [True, True, False]


def test_titolare_dall_ultima_partita_giocata(dati):
    c = dati.carichi.set_index(["data", "giocatore_id"])["titolare_ultima_partita"]
    assert c[(pd.Timestamp("2023-09-11"), 1)]           # titolare il 10/09
    assert not c[(pd.Timestamp("2023-09-11"), 3)]        # senza riga in partita = non titolare
    assert not c[(pd.Timestamp("2023-09-14"), 2)]        # ESTATUS "T" ignorato: era il futuro
    assert not c[(pd.Timestamp("2023-09-16"), 1)]        # il giorno della partita conta quella partita
    assert c[(pd.Timestamp("2023-09-16"), 2)]


def test_sedute_con_partite_di_riferimento(dati):
    s = dati.sedute.set_index("data")
    assert s.loc["2023-09-14", "prossima_partita"] == pd.Timestamp("2023-09-16")
    assert s.loc["2023-09-11", "ultima_partita"] == pd.Timestamp("2023-09-10")
    assert s.loc["2023-09-21", "prossima_partita"] == pd.Timestamp("2023-09-23")


def test_diacat_incoerente(tmp_path):
    p = csv_sintetico(tmp_path, [riga(45180, 1, 1, "T", 1700, diacat=1)])
    with pytest.raises(zenodo.FormatoNonValido):
        zenodo.converti(zenodo.leggi_csv(p))


def test_ruolo_sconosciuto(tmp_path):
    p = csv_sintetico(tmp_path, [riga(45179, 1, 0, "T", 9000, pos="POR")])
    with pytest.raises(zenodo.FormatoNonValido):
        zenodo.converti(zenodo.leggi_csv(p))
