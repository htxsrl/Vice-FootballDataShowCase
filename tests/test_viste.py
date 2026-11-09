"""M4: le viste della lavagna (specifiche costruite dal server) e le API di vista, contesto e caricamento.

Le viste non calcolano niente di nuovo: riordinano i risultati del motore. Qui si controlla che i numeri
siano quelli del motore, che ogni elemento rimandi a un'evidenza vera (per le citazioni cliccabili) e che
nessuna vista guardi dopo l'oggi.
"""

import pandas as pd
import pytest

from vice.agent.contesto import ErroreStrumento, Sessione
from vice.analysis.partita import allenamento_partita
from vice.analysis.seduta import seduta
from vice.analysis.settimana import forma_settimana, griglia_settimana
from vice.data import caricamenti
from vice.views import COSTRUTTORI, costruisci

OGGI = "2024-04-18"


@pytest.fixture(scope="module")
def s():
    return Sessione.crea(OGGI)


def test_catalogo_delle_viste():
    assert set(COSTRUTTORI) == {"seduta", "settimana", "giocatore", "curva_settimana", "allenamento_partita", "verifica"}


@pytest.mark.parametrize("nome,parametri", [
    ("seduta", {}), ("settimana", {}), ("giocatore", {"giocatore": "Cortese"}), ("curva_settimana", {}),
    ("allenamento_partita", {}), ("verifica", {}),
])
def test_ogni_vista_ha_la_sua_forma(s, nome, parametri):
    v = costruisci(nome, s, parametri)
    assert v["vista"] == nome and v["forma"] in {"fasce", "griglia", "curva", "verifica"}
    assert v["titolo"] and v["righe"] and v["fonte"]


def test_seduta_numeri_del_motore(s):
    v = costruisci("seduta", s, {"metrica": "hsr"})
    cortese = next(r for r in v["righe"] if r["giocatore"]["cognome"] == "Cortese")
    assert cortese["valore"] == 658 and cortese["posizione"] == "molto sopra"
    assert cortese["fascia"] == {"p10": 100, "p25": 172, "p50": 303, "p75": 490, "p90": 550}
    assert cortese["valore_testo"] == "658 m"
    assert v["conteggi"]["molto sopra"] == 5 and v["conteggi"]["dentro"] == 8
    assert v["asse"]["min"] == 0 and v["asse"]["max"] >= 658


def test_seduta_ogni_riga_rimanda_a_un_evidenza(s):
    ids = {e.id for e in seduta(s.visibile()).evidenze}
    graf = {e.grafico for e in seduta(s.visibile()).evidenze}
    for m in ("td", "hsr", "spr", "acc"):
        v = costruisci("seduta", s, {"metrica": m})
        for r in v["righe"]:
            assert r["evidenza"] in ids and r["chiave"] in graf


def test_seduta_senza_metrica_sceglie_quella_con_piu_fuori_fascia(s):
    assert costruisci("seduta", s, {})["metrica"] == "hsr"   # 6 fuori dalla fascia larga in HSR il 18/04


def test_nomi_delle_metriche_come_li_scrive_l_agente(s):
    assert costruisci("seduta", s, {"metrica": "alta velocità"})["metrica"] == "hsr"
    assert costruisci("seduta", s, {"metrica": "HSR"})["metrica"] == "hsr"
    with pytest.raises(ErroreStrumento):
        costruisci("seduta", s, {"metrica": "velocità massima"})


def test_nessuna_vista_vede_il_futuro(s):
    with pytest.raises(ErroreStrumento, match="Vice non vede il futuro"):
        costruisci("seduta", s, {"data": "2024-04-19"})


def test_seduta_di_un_giorno_senza_dati(s):
    v = costruisci("seduta", s, {"data": "2024-04-14"})
    assert v["righe"] == [] and "non c'è una seduta" in v["vuota"]


def test_settimana_griglia(s):
    v = costruisci("settimana", s, {"metrica": "hsr"})
    assert [g["md"] for g in v["giorni"]] == ["MD+2", "MD-3", "MD-2"]
    assert [g["oggi"] for g in v["giorni"]] == [False, False, True]
    ids = {e.id for e in griglia_settimana(s.visibile()).evidenze}
    for r in v["righe"]:
        for c in r["celle"].values():
            assert c["evidenza"] in ids
    passata = costruisci("settimana", s, {"data": "2024-04-17"})   # la settimana vista dal 17/04: oggi resta il 18/04
    assert not any(g["oggi"] for g in passata["giorni"])
    melis = next(r for r in v["righe"] if r["giocatore"]["cognome"] == "Melis")
    assert melis["celle"]["2024-04-18"]["posizione"] == "molto sopra" and "2024-04-15" not in melis["celle"]


def test_curva_della_settimana(s):
    v = costruisci("curva_settimana", s, {"metrica": "hsr"})
    assert [g["md"] for g in v["giorni"]] == ["MD+1", "MD+2", "MD-5", "MD-4", "MD-3", "MD-2", "MD-1"]
    giorni = {g["md"]: g for g in v["giorni"]}
    assert giorni["MD-2"]["valore"] == 186 and giorni["MD-1"]["futuro"] is True and "valore" not in giorni["MD-1"]
    ids = {e.id for e in forma_settimana(s.visibile()).evidenze}
    assert all(g["evidenza"] in ids for g in v["giorni"] if "evidenza" in g)


def test_giocatore_solo_i_suoi_dati(s):
    v = costruisci("giocatore", s, {"giocatore": "17", "metrica": "hsr"})   # numero di maglia di Cortese
    assert v["giocatore"]["cognome"] == "Cortese"
    assert all("/9/hsr" in r["evidenza"] for r in v["righe"])                # D6: nessun compagno
    date = [r["evidenza"].split("/")[1] for r in v["righe"]]
    assert date == sorted(date, reverse=True) and date[0] == OGGI
    assert v["righe"][0]["valore"] == 658
    with pytest.raises(ErroreStrumento):
        costruisci("giocatore", s, {})


def test_allenamento_partita(s):
    v = costruisci("allenamento_partita", s, {"metrica": "hsr"})
    assert v["riferimenti"] == [{"valore": 100, "testo": "una partita"}]
    # il colore segue il solito a questo punto della settimana; senza solito il punto resta neutro (08/11/2026)
    for r in v["righe"]:
        if "fascia" in r:
            f = r["fascia"]
            atteso = ("molto sotto" if r["valore"] < f["p10"] else "sotto" if r["valore"] < f["p25"] else "dentro"
                      if r["valore"] <= f["p75"] else "sopra" if r["valore"] <= f["p90"] else "molto sopra")
            assert r["posizione"] == atteso, (r["giocatore"]["cognome"], r["valore"], f)
        else:
            assert r["posizione"] == "neutra"
    numeri = [r["giocatore"]["numero"] for r in v["righe"]]
    assert numeri == sorted(numeri), "in ordine di maglia: non è una classifica"
    ids = {e.id for e in allenamento_partita(s.visibile()).evidenze}
    assert all(r["evidenza"] in ids for r in v["righe"])
    assert "riscaldamento" in v["spiegazione"]


def test_verifica(s):
    """V9: solo la replica dell'articolo del dataset (la coerenza con SkillCorner è tolta, decisione 57)."""
    v = costruisci("verifica", s, {})
    assert [x["valore"] for x in v["schede"]] == ["16 celle su 16", "74 celle su 80", "16 celle su 16"]
    assert "refuso" in v["schede"][1]["testo"] and "Zenodo 18986229" in v["fonte"]
    assert {r["evidenza"] for r in v["righe"]} == {x["evidenza"] for x in v["schede"]}


def test_vista_sconosciuta(s):
    with pytest.raises(ErroreStrumento):
        costruisci("confronto_magico", s, {})


# ---------- API ----------

def test_api_vista(client):
    r = client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "parametri": {"metrica": "td"}})
    assert r.status_code == 200 and r.json()["metrica"] == "td"
    assert client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "parametri": {"data": "2024-05-01"}}).status_code == 422


def test_api_contesto_calendario_fino_a_oggi(client):
    c = client.get("/api/contesto", params={"oggi": OGGI}).json()
    assert c["seduta_oggi"] is True and c["seduta_precedente"] == "2024-04-17" and c["seduta_successiva"] == "2024-04-19"
    assert all(x["data"] <= OGGI for x in c["calendario"]["sedute"])          # D2: niente sedute dal futuro
    assert all(d > OGGI for d in c["calendario"]["partite_future"]) and "2024-04-20" in c["calendario"]["partite_future"]


def test_export_di_prova_e_caricamento(client):
    caricamenti.svuota()
    # di default le righe originali del CSV di Zenodo (decisione 42)
    z = client.get("/api/export-prova", params={"data": OGGI})
    assert z.status_code == 200 and z.text.startswith("FECHA;PlayerID")
    assert "zenodo-18986229" in z.headers["content-disposition"]
    j = client.post("/api/carica", json={"nome": "zenodo.csv", "testo": z.text}).json()
    assert j["formato"] == "zenodo" and j["data"] == OGGI and j["giocatori"] == 15 and j["valori_diversi_dal_dataset"] == 0
    # anche il formato "da GPS"
    r = client.get("/api/export-prova", params={"data": OGGI, "formato": "gps"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.startswith("Player Name,Session Date,Session Type")
    j = client.post("/api/carica", json={"nome": "prova.csv", "testo": r.text}).json()
    assert j["formato"] == "gps" and j["data"] == OGGI and j["giocatori"] == 15 and j["valori_diversi_dal_dataset"] == 0
    # un file modificato: Vice usa i numeri del file
    righe = [(",".join(x.split(",")[:4] + ["700"] + x.split(",")[5:]) if x.startswith("Lorenzo Cortese") else x)
             for x in r.text.splitlines()]
    j2 = client.post("/api/carica", json={"nome": "mod.csv", "testo": "\n".join(righe)}).json()
    assert j2["valori_diversi_dal_dataset"] == 1
    v = client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "parametri": {"metrica": "hsr"},
                                        "caricamento": j2["caricamento"]}).json()
    assert next(x for x in v["righe"] if x["giocatore"]["cognome"] == "Cortese")["valore"] == 700
    # senza il codice, o in un altro giorno, vale il dataset
    v = client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "parametri": {"metrica": "hsr"}}).json()
    assert next(x for x in v["righe"] if x["giocatore"]["cognome"] == "Cortese")["valore"] == 658
    assert Sessione.crea("2024-04-17", caricamento=j2["caricamento"]).caricamento is None


def test_caricamento_non_valido(client):
    r = client.post("/api/carica", json={"nome": "x.csv", "testo": "a,b\n1,2"})
    assert r.status_code == 422 and "Mancano le colonne" in r.json()["detail"]
    r = client.post("/api/vista", json={"vista": "seduta", "oggi": OGGI, "caricamento": "nonesiste"})
    assert r.status_code == 422 and "ricaricalo" in r.json()["detail"]
    assert client.get("/api/export-prova", params={"data": "2024-04-14"}).status_code == 404
    assert client.get("/api/export-prova", params={"data": OGGI, "formato": "xls"}).status_code == 422


def test_sessione_con_caricamento_cambia_solo_quel_giorno():
    caricamenti.svuota()
    base = Sessione.crea(OGGI)
    righe = base.visibile().seduta_di_oggi.copy()
    righe.loc[righe["giocatore_id"] == 9, "hsr"] = 1.0
    c = caricamenti.salva(righe, "t.csv")
    s = Sessione.crea(OGGI, caricamento=c.codice)
    assert s.chiave.endswith(c.codice)
    oggi = s.visibile().seduta_di_oggi
    assert float(oggi.loc[oggi["giocatore_id"] == 9, "hsr"].iloc[0]) == 1.0
    ieri = s.visibile(pd.Timestamp("2024-04-17"))
    assert ieri.seduta_di_oggi.equals(base.visibile(pd.Timestamp("2024-04-17")).seduta_di_oggi)
