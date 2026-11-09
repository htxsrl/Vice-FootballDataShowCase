"""Decisione 54: la seduta del giorno della demo si carica, gli avvisi nascono col caricamento e hanno uno stato
(aperto, aggiornato, chiuso, scaduto); in testa al report, all'apertura e nel menù «Da guardare»."""

import asyncio

import pandas as pd
import pytest

from vice.agent import da_guardare, report as reportistica
from vice.agent.contesto import GIORNO_DEMO, Sessione
from vice.agent.strumenti import esegui
from vice.agent.citazioni import Registro
from vice.analysis import archivio_avvisi
from vice.analysis.archivio_avvisi import con_lo_stato
from vice.data import caricamenti
from vice.data.caricamenti import codice_dataset
from vice.data.export_gps import esporta_seduta

DEMO = "2024-04-19"


def raccogli(gen):
    async def tutto():
        return [e async for e in gen]
    return asyncio.run(tutto())


def _testi(lista, **filtri):
    return [a["testo"] for a in lista if all(a.get(k) == v for k, v in filtri.items())]


# ---------- il giorno della demo: la seduta arriva col file ----------

def test_il_giorno_della_demo_non_ha_la_seduta_finche_non_si_carica():
    assert f"{GIORNO_DEMO:%Y-%m-%d}" == DEMO
    s = Sessione.crea()
    assert s.oggi == GIORNO_DEMO and not s.caricata()
    v = s.visibile()
    assert v.seduta_di_oggi.empty and v.sedute["data"].max() < GIORNO_DEMO      # Vice vede fino a ieri
    assert "non è ancora caricata" in s.senza_seduta_caricata()
    assert Sessione.crea("2024-04-18").caricata()                                 # i giorni prima sono già nei dati
    c = Sessione.crea(caricamento=codice_dataset(DEMO))                           # il file uguale al dataset
    assert c.caricata() and c.caricamento.dal_dataset and len(c.visibile().seduta_di_oggi) == 16
    assert c.chiave.endswith(codice_dataset(DEMO)) and c.senza_seduta_caricata() is None


def test_contesto_e_caricamento(client):
    c = client.get("/api/contesto").json()
    assert c["oggi"] == DEMO and c["giorno_md"] == "MD-1" and c["seduta_prevista"] and not c["seduta_caricata"]
    assert not c["seduta_oggi"] and c["calendario"]["sedute"][-1]["data"] == DEMO     # in calendario sì, nei dati no
    # il file di prova del giorno della demo: le righe del dataset, che Vice non conosceva
    testo = client.get("/api/export-prova", params={"data": DEMO}).text
    j = client.post("/api/carica", json={"nome": "z.csv", "testo": testo}).json()
    assert j["caricamento"] == codice_dataset(DEMO) and j["prima_volta"] and j["valori_diversi_dal_dataset"] == 0
    c = client.get("/api/contesto", params={"caricamento": j["caricamento"]}).json()
    assert c["seduta_caricata"] and c["seduta_oggi"]
    # un file del futuro non si usa
    futuro = esporta_seduta(Sessione.crea("2024-04-24").stagione.al("2024-04-24").seduta_di_oggi,
                            Sessione.crea().giocatori)
    r = client.post("/api/carica", json={"nome": "f.csv", "testo": futuro})
    assert r.status_code == 422 and "Vice non vede il futuro" in r.json()["detail"]


def test_il_report_della_seduta_non_caricata_non_si_scrive():
    eventi = []
    with pytest.raises(Exception, match="non è ancora caricata"):
        eventi = raccogli(reportistica.report("seduta", Sessione.crea()))
    assert not eventi


def test_lo_strumento_della_seduta_dice_che_va_caricata():
    testo, u, err = esegui("seduta", {}, Sessione.crea(), Registro(DEMO))
    assert err is None and "non è ancora caricata" in u.dati["seduta_non_caricata"]


# ---------- l'archivio e lo stato ----------

def test_l_archivio_e_aggiornato():
    """L'archivio porta la firma del codice che l'ha calcolato: se le regole o il motore cambiano, va rifatto con
    docker compose exec -T vice python3 -m scripts.prepara_avvisi."""
    salvato = archivio_avvisi.leggi()
    assert salvato and salvato["firma"] == archivio_avvisi.firma(), "archivio degli avvisi da rifare: scripts.prepara_avvisi"


def test_l_archivio_coincide_col_calcolo_di_quel_giorno():
    from vice.analysis.avvisi import avvisi, classificazione, scegli
    from vice.analysis.comune import tutte_le_righe
    st = Sessione.crea().stagione
    g = "2024-04-17"
    sc = scegli(avvisi(st.al(g), classificazione(tutte_le_righe(st.al(g)))))
    calcolati = [a.to_dict() for lista in (sc["giorno"], sc["riassunto"], sc["dato"]) for a in lista]
    assert [a["id"] for a in calcolati] == [a["id"] for a in archivio_avvisi.archivio()[g]]


def test_la_storia_della_demo():
    """All'apertura del 19/04 restano da guardare Amato e Benedetti (calo del 17/04) e Cortese (tendenza del 15/04);
    caricato il file, Benedetti torna nel suo solito e il suo avviso si chiude; nascono Basile e Porcu."""
    prima = da_guardare.stato(Sessione.crea())
    assert prima["fino_al"] == "2024-04-18" and not prima["seduta_caricata"]
    aperti = [a for a in prima["avvisi"] if a["stato"] == "aperto" and a["categoria"] == "azione"]
    assert {(a["giocatore"], a["famiglia"], a["riassunto"]) for a in aperti} == {
        ("Simone Amato", "calo", False), ("Riccardo Benedetti", "calo", False), ("Lorenzo Cortese", "calo", True)}
    amato_15 = next(a for a in prima["avvisi"] if a["giocatore"] == "Simone Amato" and a["data"] == "2024-04-15")
    assert amato_15["stato"] == "aggiornato"                          # la tendenza lascia il posto al calo del 17/04
    amato_10 = next(a for a in prima["avvisi"] if a["giocatore"] == "Simone Amato" and a["data"] == "2024-04-10"
                    and a["famiglia"] == "calo")
    assert amato_10["stato"] == "chiuso" and amato_10["stato_dal"] == "2024-04-12"
    dopo = da_guardare.stato(Sessione.crea(caricamento=codice_dataset(DEMO)))
    nuovi = [a for a in dopo["avvisi"] if a["data"] == DEMO]
    assert {a["giocatore"] for a in nuovi} == {"Matteo Basile", "Christian Porcu", "Riccardo Benedetti"}
    benedetti = next(a for a in dopo["avvisi"] if a["giocatore"] == "Riccardo Benedetti" and a["data"] == "2024-04-17")
    assert benedetti["stato"] == "chiuso" and benedetti["stato_motivo"] == "tornato nel suo solito"


def _a(data, famiglia, gid=1, **altro):
    return {"id": f"{data}-{famiglia}-{gid}", "data": data, "famiglia": famiglia, "giocatore_id": gid, "priorita": 1,
            "metriche": ["td"], "riassunto": False} | altro


def test_le_regole_dello_stato():
    partite = ["2024-01-13", "2024-01-20"]
    per_giorno = {
        "2024-01-08": [_a("2024-01-08", "insolito"), _a("2024-01-08", "calo", 2), _a("2024-01-08", "dato", 3)],
        "2024-01-10": [_a("2024-01-10", "calo", 4)],
        "2024-01-11": [_a("2024-01-11", "positivo", 4, chiude="calo"), _a("2024-01-11", "insolito", 5)],
        "2024-01-12": [_a("2024-01-12", "insolito", 5, metriche=["hsr"])],
    }
    stato = lambda fino, pres=None: {a["id"]: a for a in con_lo_stato(per_giorno, fino, partite, pres)}   # noqa: E731
    s = stato("2024-01-12")
    assert s["2024-01-10-calo-4"]["stato"] == "chiuso"                 # la nota positiva chiude il calo
    assert s["2024-01-11-insolito-5"]["stato"] == "aggiornato"          # stessa famiglia e giocatore: vale il più recente
    assert s["2024-01-08-insolito-1"]["stato"] == "aperto"
    s = stato("2024-01-13")
    assert s["2024-01-08-insolito-1"]["stato"] == "scaduto" and s["2024-01-08-insolito-1"]["stato_dal"] == "2024-01-13"
    assert s["2024-01-08-calo-2"]["stato"] == "aperto"                  # il calo dura le due settimane della sua regola
    assert stato("2024-01-22")["2024-01-08-calo-2"]["stato"] == "scaduto"
    # il dato mancante si chiude quando i dati tornano
    assert stato("2024-01-12", {3: {"2024-01-10"}})["2024-01-08-dato-3"]["stato"] == "chiuso"
    assert stato("2024-01-12", {3: {"2024-01-05"}})["2024-01-08-dato-3"]["stato"] == "aperto"
    # niente dal futuro: gli avvisi dopo il giorno chiesto non esistono
    assert "2024-01-12-insolito-5" not in stato("2024-01-11")


def test_una_buona_notizia_non_resta_accanto_a_un_avviso_piu_recente():
    """08/11/2026: il 19/04 Guidi era insieme «di nuovo nel suo solito» (15/04) e «senza dati» (18/04). Una buona
    notizia o un rientro lasciano il posto a qualunque avviso più recente sullo stesso giocatore."""
    partite = ["2024-01-20"]
    per_giorno = {
        "2024-01-08": [_a("2024-01-08", "positivo", 1), _a("2024-01-08", "rientro", 2), _a("2024-01-08", "positivo", 3)],
        "2024-01-10": [_a("2024-01-10", "dato", 1), _a("2024-01-10", "calo", 2)],
    }
    s = {a["id"]: a for a in con_lo_stato(per_giorno, "2024-01-11", partite)}
    assert s["2024-01-08-positivo-1"]["stato"] == "aggiornato" and s["2024-01-08-positivo-1"]["stato_dal"] == "2024-01-10"
    assert s["2024-01-08-rientro-2"]["stato"] == "aggiornato"
    assert s["2024-01-08-positivo-3"]["stato"] == "aperto"            # nessun avviso nuovo su di lui
    assert s["2024-01-10-dato-1"]["stato"] == "aperto"                # e l'avviso nuovo resta aperto


def test_all_apertura_del_19_04_guidi_non_e_tra_le_buone_notizie():
    prima = da_guardare.stato(Sessione.crea())
    aperti = [a for a in prima["avvisi"] if a["stato"] == "aperto"]
    assert any(a["giocatore"] == "Stefano Guidi" and a["categoria"] == "dato" for a in aperti)
    assert not any(a["giocatore"] == "Stefano Guidi" and a["categoria"] == "informa" for a in aperti)


# ---------- il file modificato: gli avvisi si calcolano al momento ----------

def test_un_file_modificato_ha_i_suoi_avvisi():
    caricamenti.svuota()
    base = Sessione.crea(caricamento=codice_dataset(DEMO))
    righe = base.visibile().seduta_di_oggi.copy()
    righe.loc[righe.index[0], "spr"] = 2000.0                           # più sprint che alta velocità, e oltre 1,5 km
    c = caricamenti.salva(righe, "modificato.csv")
    s = Sessione.crea(caricamento=c.codice)
    lista = da_guardare.del_giorno(s)
    urgenti = [a for a in lista if a["famiglia"] == "dato" and a["urgente"]]
    assert urgenti and all(isinstance(a["giocatore_id"], int) for a in lista)
    assert any(a["data"] == DEMO and a["urgente"] for a in da_guardare.stato(s)["avvisi"])


# ---------- report, strumenti, presentazione ----------

def test_il_report_comincia_con_gli_avvisi(modello_finto):
    reportistica.svuota_cache()
    m = modello_finto([{"testo": "## Sintesi\nSeduta nella norma."}])
    eventi = raccogli(reportistica.report("seduta", Sessione.crea(caricamento=codice_dataset(DEMO)), usa_archivio=False))
    assert eventi[0]["evento"] == "avvisi"
    avvisi = eventi[0]["dati"]["avvisi"]
    assert {a["giocatore"] for a in avvisi} == {"Matteo Basile", "Christian Porcu", "Riccardo Benedetti"}
    prompt = m.richieste[0][0][0]["content"]
    assert "Spunti per lo staff" not in prompt and "avvisi_gia_mostrati" in prompt and "Basile" in prompt


def test_i_report_pronti_perdono_gli_spunti():
    testo = "## Sintesi\nUno.\n\n## Spunti per lo staff\n\n- Valutare se serve.\n\n## Qualità del dato e limiti\n- Due."
    assert reportistica.senza_spunti(testo) == "## Sintesi\nUno.\n\n## Qualità del dato e limiti\n- Due."


def test_il_report_del_giocatore_senza_confronti_coi_compagni():
    s = Sessione.crea("2024-04-11")
    gid = s.giocatore("Amato")
    avvisi = reportistica.avvisi_del_report("giocatore", s, gid)
    assert avvisi and all(a["giocatore_id"] == gid and a["famiglia"] not in ("reparto", "settimana") for a in avvisi)
    assert any(a["famiglia"] == "settimana" for a in da_guardare.del_giocatore(s, gid))   # c'è, ma resta fuori


def test_gli_strumenti_danno_gli_avvisi_con_le_etichette():
    s = Sessione.crea(caricamento=codice_dataset(DEMO))
    reg = Registro(DEMO)
    _, u, err = esegui("seduta", {}, s, reg)
    assert err is None and len(u.dati["da_guardare"]) == 3
    basile = next(a for a in u.dati["da_guardare"] if "Basile" in a["testo"])
    assert basile["etichette"] and reg.evidenza(basile["etichette"][0]).id.startswith(f"seduta/{DEMO}/")
    _, u, _ = esegui("giocatore", {"giocatore": "Amato"}, s, reg)
    assert any("Simone Amato ha fatto meno sprint" in a["testo"] and a.get("etichette") for a in u.dati["da_guardare"])


def test_mostra_e_chiedi():
    s = Sessione.crea(caricamento=codice_dataset(DEMO))
    per = {a["giocatore"]: a for a in da_guardare.del_giorno(s)}
    basile = per["Matteo Basile"]
    assert basile["vista"] == {"vista": "seduta", "parametri": {"data": DEMO, "metrica": "hsr"}}
    assert basile["accendi"]["evidenza"] == f"seduta/{DEMO}/{basile['giocatore_id']}/hsr"
    assert per["Christian Porcu"]["vista"]["vista"] == "giocatore"
    assert basile["domanda"] == "Spiegami l'avviso su Matteo Basile del 19/04: da cosa nasce?"
    dato = next(a for a in da_guardare.stato(s)["avvisi"] if a["famiglia"] == "dato")
    assert dato["vista"] is None and dato["domanda"] is None


def test_api_avvisi(client):
    r = client.get("/api/avvisi").json()
    assert r["fino_al"] == "2024-04-18" and not r["seduta_caricata"]
    assert all(a["stato"] in archivio_avvisi.STATI and a["data"] <= "2024-04-18" for a in r["avvisi"])
    r = client.get("/api/avvisi", params={"caricamento": codice_dataset(DEMO)}).json()
    assert r["fino_al"] == DEMO and r["avvisi"][0]["data"] == DEMO
    assert client.get("/api/avvisi", params={"oggi": "2030-01-01"}).status_code == 422
    assert pd.Timestamp(r["fino_al"]) == GIORNO_DEMO


def test_le_date_senza_anno_sono_della_stagione():
    """«19/04» (come in «Spiegami l'avviso … del 19/04») era letto come anno 1: nessun dato."""
    s = Sessione.crea()
    assert f"{s.data('19/04'):%Y-%m-%d}" == DEMO and f"{s.data('15/01'):%Y-%m-%d}" == "2024-01-15"
    assert f"{s.data('10/09'):%Y-%m-%d}" == "2023-09-10"
    with pytest.raises(Exception, match="fuori dalla stagione"):
        s.data("01/01/2020")
