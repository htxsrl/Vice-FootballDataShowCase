"""Le sigle spiegate la prima volta (decisione 48): il significato accanto alla prima sigla della conversazione,
poi solo la sigla."""

import pytest

from vice.agent.sigle import introduci, significato, spiegate
from vice.agent.verifica import numeri


@pytest.mark.parametrize("testo, atteso", [
    ("HMLD sopra la fascia [E3].", "HMLD (distanza ad alto carico metabolico) sopra la fascia [E3]."),
    ("l'HSR di Cortese [E2]", "l'HSR (corsa ad alta velocità) di Cortese [E2]"),
    ("a MD-2 la squadra", "a MD-2 (due giorni prima della partita) la squadra"),
    ("a MD+1 i titolari", "a MD+1 (il giorno dopo la partita) i titolari"),
    ("il 18/04/2024 (MD-2): 658 m", "il 18/04/2024 (MD-2, due giorni prima della partita): 658 m"),
])
def test_aggiunge_il_significato(testo, atteso):
    assert introduci(testo) == atteso


@pytest.mark.parametrize("testo", [
    "La distanza ad alto carico metabolico (HMLD) è sopra la fascia [E3].",
    "Due giorni prima della partita (MD-2) la squadra",
    "L'HSR (corsa ad alta velocità) è nella fascia.",
    "La corsa ad alta velocità (HSR) e poi di nuovo HSR.",
])
def test_lascia_stare_se_gia_spiegata(testo):
    assert introduci(testo) == testo


def test_un_secondo_passaggio_non_cambia_nulla():
    for t in ("HMLD sopra [E3].", "il 18/04/2024 (MD-2): 658 m e MD-1", "l'HSR di Cortese e TD"):
        una = introduci(t)
        assert introduci(una) == una, t


def test_solo_la_prima_volta():
    t = introduci("HSR [E1]. Poi ancora HSR [E2] e SPR [E3], SPR.")
    assert t == "HSR (corsa ad alta velocità) [E1]. Poi ancora HSR [E2] e SPR (sprint) [E3], SPR."


def test_conversazione_gia_avviata():
    prima = ["La corsa ad alta velocità (HSR) di Cortese è nella fascia [E1]. Oggi è MD-2 (due giorni prima della partita)."]
    gia = spiegate(prima)
    assert gia == {"HSR", "MD"}
    assert introduci("HSR e MD+1 e TD.", gia) == "HSR e MD+1 e TD (distanza totale)."


def test_non_tocca_parole_simili():
    testo = "HSRx, MDA, TDS e l'acc minuscolo restano come sono; [E12] e P10-P90 anche."
    assert introduci(testo) == testo


def test_significati_senza_numeri():
    """Il significato si aggiunge dopo la verifica: non deve portare numeri nuovi nel testo."""
    for s in ("TD", "HSR", "SPR", "ACC", "DCC", "HMLD", "ACWR", "RPE", "MD", "MD-1", "MD-5", "MD+2"):
        assert not numeri(significato(s)), s
