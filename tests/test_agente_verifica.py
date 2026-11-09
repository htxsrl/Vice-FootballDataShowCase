"""M3.8: la verifica deterministica dei numeri, su testi con risultato noto."""

import pytest

from vice.analysis.evidenze import evidenza
from vice.agent.citazioni import Registro
from vice.agent.verifica import dividi_frasi, numeri, pulisci_citazioni, senza_citazioni, togli, verifica


@pytest.fixture
def reg():
    r = Registro()
    r.etichetta(evidenza("a", "TD di Santini", 5436, "m", fascia_centrale=[4898, 6089], percentile=82))    # E1
    r.etichetta(evidenza("b", "Picco", 182.5, "m/min"))                                                   # E2
    r.etichetta(evidenza("c", "Scarto", -24, "%", giocatori=3))                                           # E3
    return r


def test_numeri_all_italiana():
    assert [n.valore for n in numeri("5.436 m e 182,5 m/min, 1.29 e 12%")] == [5436, 182.5, 1.29, 12]
    assert [n.valore for n in numeri("tra 4.898-6.089 m")] == [4898, 6089]
    km = numeri("5,4 km")[0]
    assert km.valore == 5400 and km.tolleranza == pytest.approx(50)
    assert numeri("oltre 25,2 km/h")[0].valore == 25.2              # km/h non è una distanza


def test_cio_che_non_e_un_dato_si_ignora():
    t = "Il 10/01/2024 (MD-3), il 10 gennaio, nella stagione 2023/24, sopra il P90, Zenodo 18986229, nel 2024 [E1]."
    assert numeri(t) == []
    assert numeri("1. Primo punto\n2. Secondo") == []


def test_esiti(reg):
    v = verifica("Santini ha fatto 5.436 m [E1]. Era al percentile 82 [E1].", reg)
    assert [f.esito for f in v.frasi] == ["verificata", "verificata"] and v.verificate == 2
    v = verifica("Santini ha fatto 5.436 m.", reg)
    assert v.frasi[0].esito == "non verificata" and "senza evidenza" in v.frasi[0].motivo
    v = verifica("Santini ha fatto 5.500 m [E1].", reg)
    assert v.frasi[0].esito == "non verificata" and "5.500" in v.frasi[0].motivo
    v = verifica("Picco di 182,5 m/min [E9].", reg)
    assert "inesistenti" in v.frasi[0].motivo
    v = verifica("Picco di 182,5 m/min [E1].", reg)                  # numero vero ma evidenza sbagliata
    assert v.frasi[0].esito == "non verificata"
    v = verifica("La seduta è andata bene.", reg)
    assert v.frasi[0].esito == "senza numeri" and v.con_numeri == []


def test_tolleranze_segno_e_definizioni(reg):
    assert verifica("Circa 5,4 km [E1].", reg).frasi[0].esito == "verificata"            # 5.436 m in km
    assert verifica("Più basso del 24% [E3].", reg).frasi[0].esito == "verificata"       # il segno a parole
    assert verifica("Tre giocatori: 3 [E3]. Fascia 4.898-6.089 m [E1].", reg).verificate == 2
    assert verifica("HSR oltre 19,8 km/h [D1].", reg).frasi[0].esito == "verificata"
    assert verifica("HSR oltre 19,8 km/h [D2].", reg).frasi[0].esito == "non verificata"


def test_frasi_e_pulizia(reg):
    t = "## Sintesi\nPrima frase 5.436 m [E1]. Seconda frase 7 m [E1].\n- punto 182,5 m/min [E2]"
    assert dividi_frasi(t) == ["## Sintesi", "Prima frase 5.436 m [E1].", "Seconda frase 7 m [E1].", "- punto 182,5 m/min [E2]"]
    v = verifica(t, reg)
    assert togli(t, v.non_verificate) == "## Sintesi\nPrima frase 5.436 m [E1].\n- punto 182,5 m/min [E2]"
    assert senza_citazioni("Ha fatto 5.436 m [E1] e [E2, D1].") == "Ha fatto 5.436 m e."


def test_numeri_del_nome_intervalli_e_date():
    r = Registro()
    r.etichetta(evidenza("p", "Picco di 1 min (metri al minuto) dei terzini per 90 minuti", 204.0, "m/min"))   # E1
    r.etichetta(evidenza("q", "Volume", 9032, "m"))                                                              # E2
    r.registra_date("oggi è il 18/04/2024, prossima partita 20/04/2024")
    assert verifica("Picco di 1 minuto: 204,0 m/min per 90' [E1].", r).frasi[0].esito == "verificata"
    assert verifica("Volumi 9.032 m e 204,0 m/min [E1-E2].", r).frasi[0].esito == "verificata"
    assert verifica("La partita del 20/04/2024 [E2].", r).frasi[0].esito == "senza numeri"
    v = verifica("La partita del 25 aprile.", r)
    assert v.frasi[0].esito == "non verificata" and "date" in v.frasi[0].motivo


def test_chiudi_frase():
    from vice.agent.verifica import chiudi_frase
    assert chiudi_frase("Prima frase. Sulla lavagna trovi la seduta con la") == "Prima frase."
    assert chiudi_frase("Riga uno [E1]\n- punto finito.") == "Riga uno [E1]\n- punto finito."
    assert chiudi_frase("Tutto bene [E2]") == "Tutto bene [E2]"


# ---------- giudizi a parole (decisione 45) ----------

import pytest  # noqa: E402

from vice.agent.contesto import Sessione  # noqa: E402
from vice.analysis.giocatore import confronta  # noqa: E402
from vice.analysis.seduta import seduta  # noqa: E402


@pytest.fixture(scope="module")
def giudizi():
    s = Sessione.crea("2024-04-18")
    v = s.visibile()
    ev = {e.id: e for e in seduta(v).evidenze}
    reg = Registro("2024-04-18")
    et = {nome: reg.etichetta(ev[i]) for nome, i in (
        ("cortese", "seduta/2024-04-18/9/hsr"), ("pinna", "seduta/2024-04-18/5/hsr"), ("tosi_td", "seduta/2024-04-18/15/td"),
        ("squadra_hsr", "seduta/2024-04-18/squadra/hsr"), ("squadra_td", "seduta/2024-04-18/squadra/td"))}
    et["confronto"] = reg.etichetta(next(e for e in confronta(v, [15, 9]).evidenze if e.id.startswith("confronto/")))
    return reg, et


@pytest.mark.parametrize("frase, passa", [
    ("Cortese è molto sopra la sua fascia con 658 m [{cortese}].", True),
    ("Pinna è sopra la fascia [{pinna}].", False),                           # Pinna è dentro
    ("Pinna non è sopra la sua fascia [{pinna}].", True),                    # negazione: non si giudica
    ("Cortese è dentro la sua fascia [{cortese}].", False),
    ("Tosi è sopra la fascia centrale in distanza [{tosi_td}].", True),
    ("Tosi è sopra la fascia larga in distanza [{tosi_td}].", False),        # è «sopra», non «molto sopra»
    ("Tosi è molto sopra la sua fascia [{tosi_td}].", False),
    ("Tosi è fuori fascia [{tosi_td}].", True),
    # caso visto il 26/10: «sopra» vuol dire fuori dalla centrale ma dentro la larga
    ("Tosi è sopra la fascia centrale ma dentro la fascia larga [{tosi_td}].", True),
    ("Cortese è dentro la fascia larga [{cortese}].", False),                # è «molto sopra»
    ("Pinna è in linea con il suo solito [{pinna}].", True),
    ("L'HSR della squadra è al percentile 65, sopra la fascia centrale [{squadra_hsr}].", False),   # caso visto il 22/10
    # caso visto il 25/10: il percentile di squadra è centrale, ma «molto sopra» riguarda i singoli (conteggi)
    ("L'HSR della squadra è al percentile 65 [{squadra_hsr}], trainato da alcuni singoli molto sopra fascia.", True),
    ("In distanza 2 sono sopra fascia e 1 sotto [{squadra_td}].", True),     # i conteggi della squadra
    # caso visto il 26/10: «sotto la mediana» si confronta con P50, non con la fascia P25-P75
    ("L'HSR della squadra è al percentile 65, sopra la mediana storica [{squadra_hsr}].", True),
    ("L'HSR della squadra è al percentile 65, sotto la mediana storica [{squadra_hsr}].", False),
    ("Cortese è sopra la sua mediana con 658 m [{cortese}].", True),
    ("Cortese è sotto il suo riferimento con 658 m [{cortese}].", False),
    ("Oggi Cortese ha fatto 658 m [{cortese}].", True),
    ("A MD-5 (oggi) Tosi ha una mediana di 35 m [{confronto}].", False),     # caso visto il 25/10: mediane di 4 settimane
])
def test_giudizi_a_parole(giudizi, frase, passa):
    reg, et = giudizi
    f = verifica(frase.format(**et), reg).frasi[0]
    assert (f.esito != "non verificata") == passa, f.motivo


def test_giudizi_sui_conteggi_del_postpartita():
    """Caso visto il 26/10: «5 risultano molto sotto il solito [E1, E2]» citando i riepiloghi del postpartita,
    che hanno i conteggi per esito e non una posizione."""
    from vice.analysis.settimana import compensazione
    s = Sessione.crea("2024-04-15")
    reg = Registro("2024-04-15")
    et = {e.id.rsplit("/", 1)[-1]: reg.etichetta(e) for e in compensazione(s.visibile()).evidenze if e.id.endswith("/esiti")}
    passa = lambda frase: verifica(frase.format(**et), reg).frasi[0].esito != "non verificata"   # noqa: E731
    assert passa("Due non titolari sono sotto il solito e sette in linea con il solito [{esiti}].")
    assert not passa("Due non titolari sono molto sopra il solito [{esiti}].")


def test_i_numeri_di_maglia_non_sono_dati(reg):
    """Caso visto il 26/10: l'intestazione «**Matteo Basile (9)**» veniva tolta perché il 9 non è nelle evidenze."""
    assert verifica("**Matteo Basile (9)**", reg).frasi[0].esito == "senza numeri"
    assert verifica("Il numero 9 sta bene.", reg).frasi[0].esito == "senza numeri"
    assert verifica("**Andrea Melis (9)**", reg).frasi[0].esito == "non verificata"      # Melis ha il 2


def test_la_finestra_fissa_del_motore_non_e_un_dato(reg):
    """Caso visto il 26/10: «**Tosi vs Melis, mediane ultime 4 settimane:**» veniva tolta. Le 4 settimane sono
    la finestra fissa del motore (GIORNI_RECENTI); un altro numero di settimane resta da verificare."""
    assert verifica("**Tosi vs Melis, mediane ultime 4 settimane (per giorno MD):**", reg).frasi[0].esito == "senza numeri"
    assert verifica("Nelle ultime 6 settimane è cresciuto.", reg).frasi[0].esito == "non verificata"


def test_il_motivo_spiega_la_fascia_larga(giudizi):
    """Caso visto il 25/10: «sprint 0 m, sotto fascia larga [0 m, 135 m]» con l'evidenza «sotto». Il motivo
    deve dire alla correzione che «sotto» sta dentro la fascia larga, così la frase si corregge e non si toglie."""
    reg, et = giudizi
    f = verifica("Tosi è sopra la fascia larga in distanza [{tosi_td}].".format(**et), reg).frasi[0]
    assert f.esito == "non verificata" and "sopra P90" in f.motivo and "dentro la fascia larga P10-P90" in f.motivo


def test_frase_senza_numeri_ma_con_giudizio_conta_come_controllata(giudizi):
    reg, et = giudizi
    v = verifica("Pinna è dentro la sua fascia [{pinna}]. Buona seduta.".format(**et), reg)
    assert [f.esito for f in v.frasi] == ["verificata", "senza numeri"]


def test_spunti_inventati_si_tolgono():
    from vice.agent.verifica import spunti_inventati
    ammessi = ["Valutare se serve rivedere il carico ad alta velocità di Cortese a MD-1."]
    testo = ("- Valutare se serve rivedere il carico ad alta velocità di Cortese a MD-1 [E3].\n"
             "Valutare se il programma prevedeva questo carico ridotto [E1].\nTosi ha fatto 6.673 m [E2].")
    assert spunti_inventati(testo, ammessi) == ["Valutare se il programma prevedeva questo carico ridotto [E1]."]
    assert spunti_inventati(testo, []) == ["- Valutare se serve rivedere il carico ad alta velocità di Cortese a MD-1 [E3].",
                                           "Valutare se il programma prevedeva questo carico ridotto [E1]."]


@pytest.mark.parametrize("testo, atteso", [
    ("Mediane sempre dentro fascia [E1-E9 non citabili come intervallo, vedi sotto].", "Mediane sempre dentro fascia [E1-E9]."),
    ("Cortese 658 m [E8, E9 vedi la lavagna].", "Cortese 658 m [E8, E9]."),
    ("Cortese 658 m [E8, E9].", "Cortese 658 m [E8, E9]."),
    ("Cortese e Tosi [E3 e E7].", "Cortese e Tosi [E3 e E7]."),
    ("fascia [0 m, 135 m]", "fascia [0 m, 135 m]"),
])
def test_commenti_dentro_le_citazioni(testo, atteso):
    """Un commento del modello dentro la citazione si toglie, le etichette restano (risposta reale del 28/10/2026)."""
    assert pulisci_citazioni(testo) == atteso

