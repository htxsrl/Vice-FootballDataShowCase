"""Gli avvisi di Vice (decisione 53, wiki/metodi/avvisi.md): calcolati come quel giorno, con testi dal codice,
pochi al giorno e senza le parole vietate."""

import re

import pandas as pd
import pytest

from vice.analysis.avvisi import FAMIGLIE, MAX_AL_GIORNO, MAX_NEL_RIASSUNTO, avvisi, classificazione, scegli
from vice.analysis.comune import tutte_le_righe
from vice.config import get_settings
from vice.data import zenodo
from vice.data.stagione import Stagione

STAGIONE = Stagione(zenodo.carica(get_settings().processed_dir / "zenodo"))
VIETATE = re.compile(r"\b(rischio|infortun|in forma|in difficoltà|meglio|peggio|sovraccarico)\b", re.I)


@pytest.fixture(scope="module")
def classificate():
    return classificazione(tutte_le_righe(STAGIONE.al("2024-04-18")))


@pytest.mark.parametrize("giorno", ["2024-04-08", "2024-04-10", "2024-04-11", "2024-04-17"])
def test_avvisi_di_un_giorno(classificate, giorno):
    tutti = avvisi(STAGIONE.al(giorno), classificate)
    for a in tutti:
        assert a.famiglia in FAMIGLIE and a.testo and not VIETATE.search(a.testo), a.testo
    s = scegli(tutti)
    assert len(s["giorno"]) <= MAX_AL_GIORNO and len(s["riassunto"]) <= MAX_NEL_RIASSUNTO


def test_come_quel_giorno(classificate):
    """La classificazione calcolata con i soli dati fino a quel giorno dà gli stessi avvisi di quella di tutta la stagione."""
    giorno = "2024-04-10"
    solo_passato = classificazione(tutte_le_righe(STAGIONE.al(giorno)))
    a = [x.testo for x in avvisi(STAGIONE.al(giorno), classificate)]
    b = [x.testo for x in avvisi(STAGIONE.al(giorno), solo_passato)]
    assert a == b and a


def test_le_storie_della_taratura(classificate):
    """Casi letti a mano nella taratura del 28/10/2026: il richiamo e il rientro dopo la partita del 06/04, il calo di
    Amato con la squadra nella norma."""
    testi = lambda g: [x.testo for x in avvisi(STAGIONE.al(g), classificate)]   # noqa: E731
    assert any(t.startswith("Valutare se serve un richiamo per Simone Amato") for t in testi("2024-04-08"))
    assert any(t.startswith("Stefano Guidi è tornato dopo") for t in testi("2024-04-08"))
    assert any("Simone Amato ha fatto meno" in t and "la squadra in quelle sedute era nella norma" in t for t in testi("2024-04-10"))


def test_ogni_avviso_una_volta_sola(classificate):
    """Lo stesso avviso non si ripete il giorno dopo, se la situazione non cambia."""
    date = [d for d in sorted(pd.Timestamp(x) for x in STAGIONE.giorni_di_seduta) if pd.Timestamp("2024-03-25") <= d <= pd.Timestamp("2024-04-18")]
    visti = set()
    for d in date:
        for a in avvisi(STAGIONE.al(d), classificate):
            if a.famiglia in ("calo", "rientro") and not a.riassunto:
                chiave = (a.famiglia, a.giocatore_id, a.testo)
                assert chiave not in visti, a.testo
                visti.add(chiave)
