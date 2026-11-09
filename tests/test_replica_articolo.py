"""M2.13: i nostri dati riproducono le tabelle dell'articolo del dataset Zenodo (Data 2026, 11(4), 84)."""

from vice.config import get_settings
from vice.data import zenodo
from vice.data.stagione import stagione
from vice.data.validazione_zenodo import denominatori_ratio, riepilogo, tabella1, tabella2
from vice.analysis.partita import riferimenti_partita

CARICHI = zenodo.carica(get_settings().processed_dir / "zenodo").carichi


def test_tabella1_identica():
    t = tabella1(CARICHI)
    assert len(t) == 16
    assert (t["articolo"] == t["nostro"]).all(), t[t["articolo"] != t["nostro"]]
    assert t["nostro"].sum() == 2375


def test_tabella2_distanza_totale():
    t = tabella2(CARICHI, "td")
    assert len(t) == 80
    assert t.loc[~t["refuso"], "uguale"].all(), t[~t["refuso"] & ~t["uguale"]]
    assert t["uguale"].sum() == 74
    # le 6 celle del refuso: il valore dell'articolo è il nostro dello stato opposto
    r = t[t["refuso"]]
    assert len(r) == 6 and not r["uguale"].any()
    assert ((r["nostro_stato_scambiato"] - r["articolo"]).abs() <= 0.1 + 1e-9).all()


def test_tabella2_hsr_difensori_centrali():
    t = tabella2(CARICHI, "hsr")
    assert len(t) == 16 and t["uguale"].all(), t[~t["uguale"]]


def test_i_rapporti_del_dataset_usano_la_media_da_titolare():
    """L'articolo dichiara il massimo in partita; i dati dicono media da titolare (decisione 24)."""
    den = denominatori_ratio(CARICHI).dropna(subset=["media_da_titolare"])
    for m, g in den.groupby("metrica"):
        assert g["scarto_media_pct"].abs().median() < 5, m
        assert g["scarto_massimo_pct"].median() < -10, m     # col massimo lo scarto sarebbe grande


def test_il_riferimento_di_vice_a_fine_stagione_ritrova_i_denominatori():
    """Col solo passato, a stagione finita, il riferimento di Vice coincide quasi con quello del dataset."""
    v = stagione().al("2024-05-12")
    rif = riferimenti_partita(v.storico, v.giocatori)
    rif = rif[rif["livello"] == "personale"].set_index(["giocatore_id", "metrica"])["riferimento"]
    den = denominatori_ratio(CARICHI).set_index(["giocatore_id", "metrica"])["denominatore"]
    scarti = (100 * (den.reindex(rif.index) / rif - 1)).abs()
    assert len(scarti) >= 90 and scarti.median() < 5


def test_riepilogo():
    r = riepilogo(CARICHI)
    assert r["tabella1_celle_uguali"] == 16 and r["tabella2_td_celle_uguali"] == 74
    assert r["tabella2_td_refuso_spiegato"] and r["tabella2_hsr_cd_celle_uguali"] == 16
