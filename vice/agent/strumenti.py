"""M3.2 Catalogo degli strumenti dell'agente: solo lettura, uno per analisi del motore (M2).

Ogni strumento riceve la sessione (l'"oggi" simulato) e il registro delle evidenze del turno, e
restituisce un risultato **compatto**: sintesi ed evidenze rilevanti con le loro etichette [E…],
non le tabelle intere (un report del motore ha centinaia di evidenze). I numeri arrivano già
scritti all'italiana, da copiare così come sono.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from ..analysis import fasce as _fasce
from ..analysis import giocatore as _giocatore
from ..analysis.evidenze import Evidenza, Risultato, data_it, giorno_md_it
from ..analysis.limiti import limiti as _limiti
from ..analysis.motore import analisi_per_report
from ..analysis.partita import allenamento_partita
from ..analysis.settimana import compensazione, esposizione_velocita
from ..analysis.verifiche import replica_articolo
from . import da_guardare
from .citazioni import Registro
from .contesto import ErroreStrumento, Sessione

MAX_EVIDENZE = 40
METRICHE_PRINCIPALI = ("td", "hsr", "spr")


@dataclass
class Uscita:
    dati: dict                       # ciò che vede il modello
    vista: dict | None = None        # vista suggerita per la lavagna (M4)
    evidenze: list[Evidenza] = field(default_factory=list)


@dataclass
class Strumento:
    nome: str
    descrizione: str
    parametri: dict
    esegui: Callable[[Sessione, Registro, dict], Uscita]
    tappa: str                       # cosa mostrare mentre lavora ("leggo la seduta…")

    def schema(self) -> dict:
        return {"type": "function", "function": {"name": self.nome, "description": self.descrizione,
                                                 "parameters": self.parametri}}


def _ev(r: Risultato, *prefissi: str, metriche: tuple[str, ...] | None = None, limite: int = MAX_EVIDENZE) -> list[Evidenza]:
    out = [e for e in r.evidenze if e.id.startswith(prefissi)]
    if metriche:
        out = [e for e in out if e.contesto.get("metrica") in metriche or "metrica" not in e.contesto]
    return out[:limite]


def _pacchetto(reg: Registro, evidenze: list[Evidenza], **extra) -> Uscita:
    visti, uniche = set(), []
    for e in evidenze:
        if e.id not in visti:
            visti.add(e.id)
            uniche.append(e)
    uniche = uniche[:MAX_EVIDENZE]
    dati = {k: v for k, v in extra.items() if v not in (None, [], {})}
    dati["evidenze"] = [reg.per_il_modello(e) for e in uniche]
    return Uscita(dati, evidenze=uniche)


def _contesto(s: Sessione, giorno) -> dict:
    c = s.stagione.contesto(giorno)
    return {"data": data_it(giorno), "giorno_md": giorno_md_it(c.giorno_md),
            "ultima_partita": data_it(c.ultima_partita) if c.ultima_partita is not None else None,
            "prossima_partita": data_it(c.prossima_partita) if c.prossima_partita is not None else None}


P_DATA = {"data": {"type": "string", "description": "Giorno da analizzare (es. 10/01/2024); vuoto = il giorno in esame (di solito oggi). Mai dopo oggi."}}
P_GIOCATORE = {"giocatore": {"type": "string", "description": "Nome, cognome o numero di maglia (es. 'Santini', '6')."}}
P_METRICA = {"metrica": {"type": "string", "enum": ["td", "hsr", "spr", "acc", "dcc", "hmld"],
                         "description": "La metrica di cui chiede l'utente, se ne nomina una (td distanza totale, hsr alta "
                                        "velocità, spr sprint, acc accelerazioni, dcc decelerazioni, hmld alto carico "
                                        "metabolico): il grafico mostrerà quella."}}


def _metrica(a: dict) -> str | None:
    """La metrica chiesta, normalizzata; None se non c'è o non si riconosce (il grafico sceglie da solo)."""
    from ..views.comune import ALIAS_METRICA
    m = str(a.get("metrica") or "").strip().lower()
    m = ALIAS_METRICA.get(m, m)
    return m if m in ("td", "hsr", "spr", "acc", "dcc", "hmld") else None


def _con_metrica(vista: dict, a: dict) -> dict:
    m = _metrica(a)
    if m:
        vista["parametri"]["metrica"] = m
    return vista


# ---------- gli strumenti ----------

def _da_guardare(s: Sessione, reg: Registro, lista: list[dict], giorno, evidenze: list[Evidenza]) -> tuple[list[dict], list[Evidenza]]:
    """Gli avvisi di Vice (decisione 54) con le etichette delle loro evidenze: quelle già nel pacchetto dello strumento
    e quelle delle sedute che citano. Restituisce gli avvisi per il modello e le evidenze in più da aggiungere."""
    if not lista:
        return [], []
    tutte = {e.id: e for e in evidenze}
    # di ogni avviso le evidenze più recenti (al massimo 3): bastano a citarlo, e il pacchetto resta compatto
    citate = list(dict.fromkeys(i for a in lista for i in sorted(a.get("evidenze", []), reverse=True)[:3]))
    if any(i not in tutte and i.startswith("seduta/") for i in citate):
        tutte = {e.id: e for e in da_guardare.evidenze(s, lista, giorno)} | tutte
    usate = [tutte[i] for i in citate if i in tutte]
    etichette = {e.id: reg.etichetta(e) for e in usate}
    return da_guardare.per_il_modello(lista, etichette), usate


def _senza_seduta(s: Sessione, g) -> dict | None:
    motivo = s.senza_seduta_caricata(g)
    return {"contesto": _contesto(s, g), "seduta_non_caricata": motivo} if motivo else None


def _t_seduta(s: Sessione, reg: Registro, a: dict) -> Uscita:
    g = s.data(a.get("data"))
    if (vuota := _senza_seduta(s, g)) is not None:
        return Uscita(vuota)
    an = analisi_per_report(s.visibile(g), "seduta")
    r = an.analisi["seduta"]
    if not r.sintesi.get("giocatori"):
        return Uscita({"contesto": _contesto(s, g), "avvisi": r.avvisi})
    m = _metrica(a)
    if m:   # la domanda riguarda una metrica: tutti quelli fuori dalla fascia centrale in quella metrica
        fuori = [r.evidenza(f["evidenza"]) for f in r.sintesi["fuori_fascia"] + r.sintesi["ai_margini"] if f["metrica"] == m][:16]
        margini = []
        nota = (f"evidenze di squadra, poi tutti quelli fuori dalla fascia centrale in {m} (molto sopra/sotto = fuori dalla "
                "fascia larga; sopra/sotto = ai margini)")
    else:
        fuori = [r.evidenza(f["evidenza"]) for f in r.sintesi["fuori_fascia"][:12]]
        margini = [r.evidenza(f["evidenza"]) for f in r.sintesi["ai_margini"][:6]]
        nota = "evidenze di squadra (percentile mediano per metrica), poi chi è fuori dalla fascia larga, poi chi è ai margini"
    base = [r.evidenza(f"seduta/{g:%Y-%m-%d}/squadra/fuori")] + _ev(r, f"seduta/{g:%Y-%m-%d}/squadra/") + fuori + margini
    dg, extra = _da_guardare(s, reg, da_guardare.del_giorno(s, g), g, list(an.evidenze().values()))
    out = _pacchetto(reg, base + extra, contesto=_contesto(s, g), avvisi=r.avvisi, da_guardare=dg, nota=nota)
    out.vista = _con_metrica({"vista": "seduta", "parametri": {"data": f"{g:%Y-%m-%d}"}}, a)
    return out


def _t_settimana(s: Sessione, reg: Registro, a: dict) -> Uscita:
    g = s.data(a.get("data"))
    an = analisi_per_report(s.visibile(g), "settimana")
    forma, griglia = an.analisi["forma_settimana"], an.analisi["griglia_settimana"]
    fuori = [e for e in griglia.evidenze if e.contesto.get("posizione") in ("molto sopra", "molto sotto")
             and e.contesto.get("metrica") in METRICHE_PRINCIPALI][:14]
    aperti = [x for x in da_guardare.stato(s, g)["avvisi"] if x["stato"] == "aperto" and x["categoria"] == "azione"]
    dg, extra = _da_guardare(s, reg, aperti, g, list(an.evidenze().values()))
    out = _pacchetto(reg, _ev(forma, "settimana/", metriche=METRICHE_PRINCIPALI) + fuori + extra,
                     contesto=_contesto(s, g), avvisi=forma.avvisi, da_guardare=dg,
                     settimana={"dal": data_it(forma.sintesi["settimana_dal"]) if forma.sintesi.get("settimana_dal") is not None else None,
                                "regolare": forma.sintesi.get("settimana_regolare"),
                                "settimane_di_riferimento": forma.sintesi.get("settimane_di_riferimento")},
                     nota="prima le mediane di squadra di ogni seduta contro lo stesso giorno MD delle settimane passate, "
                          "poi i singoli fuori dalla fascia larga nella settimana")
    out.vista = _con_metrica({"vista": "settimana", "parametri": {"data": f"{g:%Y-%m-%d}"}}, a)
    return out


def _t_alta_velocita(s: Sessione, reg: Registro, a: dict) -> Uscita:
    g = s.data(a.get("data"))
    r = esposizione_velocita(s.visibile(g))
    if r.tabella.empty:
        return Uscita({"contesto": _contesto(s, g), "avvisi": r.avvisi})
    p = f"velocita/{r.sintesi['partita']:%Y-%m-%d}"
    bassi = {x["giocatore_id"] for x in r.sintesi.get("sotto_il_solito", [])}
    singoli = [e for e in r.evidenze if e.contesto.get("giocatore_id") in bassi]
    incompleti = {c["giocatore_id"] for c in r.sintesi.get("copertura_incompleta", [])}
    singoli += [e for e in r.evidenze if e.contesto.get("giocatore_id") in incompleti and e.id.endswith("/spr")]
    return _pacchetto(reg, _ev(r, f"{p}/sintesi") + singoli, contesto=_contesto(s, g), avvisi=r.avvisi,
                      nota="la copertura dei dati di ciascuno è nel campo 'copertura' della sua evidenza")


def _t_postpartita(s: Sessione, reg: Registro, a: dict) -> Uscita:
    g = s.data(a.get("data"))
    r = compensazione(s.visibile(g))
    if r.tabella.empty:
        return Uscita({"contesto": _contesto(s, g), "avvisi": r.avvisi})
    p = f"compensazione/{r.sintesi['partita']:%Y-%m-%d}"
    titolari = [r.evidenza(x["evidenza"]) for x in r.sintesi.get("titolari_postpartita_sopra", [])][:6]
    return _pacchetto(reg, _ev(r, f"{p}/esiti", f"{p}/gruppo") + [e for e in r.evidenze if e.id.endswith("/hsr") and "/gruppo/" not in e.id]
                      + titolari, contesto=_contesto(s, g), avvisi=r.avvisi,
                      nota="HSR postpartita dei non titolari contro la somma dei loro riferimenti giornalieri; "
                           "non dice se lo stimolo è sufficiente; la copertura dei dati è nel campo 'copertura'")


def _t_allenamento_partita(s: Sessione, reg: Registro, a: dict) -> Uscita:
    g = s.data(a.get("data"))
    r = allenamento_partita(s.visibile(g))
    if a.get("giocatore"):
        gid = s.giocatore(a["giocatore"])
        ev = [e for e in r.evidenze if e.contesto.get("giocatore_id") == gid and e.contesto.get("metrica") in METRICHE_PRINCIPALI]
    else:
        ev = _ev(r, f"partita/{g:%Y-%m-%d}/squadra/")
    out = _pacchetto(reg, ev, contesto=_contesto(s, g), avvisi=r.avvisi)
    p = {"data": f"{g:%Y-%m-%d}", **({"giocatore_id": s.giocatore(a["giocatore"])} if a.get("giocatore") else {})}
    out.vista = _con_metrica({"vista": "allenamento_partita", "parametri": p}, a)
    return out


def _t_giocatore(s: Sessione, reg: Registro, a: dict) -> Uscita:
    gid = s.giocatore(a.get("giocatore", ""))
    g = s.data(a.get("data"))
    an = analisi_per_report(s.visibile(g), "giocatore", gid)
    mie = lambda r: [e for e in r.evidenze if e.contesto.get("giocatore_id") == gid]   # noqa: E731
    ev = (mie(an.analisi["seduta"])[:6] + an.analisi["andamento"].evidenze
          + [e for e in mie(an.analisi["allenamento_partita"]) if e.contesto.get("metrica") in METRICHE_PRINCIPALI]
          + mie(an.analisi["esposizione_velocita"]) + mie(an.analisi["compensazione"]))
    dg, extra = _da_guardare(s, reg, da_guardare.del_giocatore(s, gid, g), g, list(an.evidenze().values()))
    out = _pacchetto(reg, ev + extra,
                     contesto=_contesto(s, g), giocatore=s.nome(gid), da_guardare=dg, qualita=an.qualita,
                     **({"seduta_non_caricata": s.senza_seduta_caricata(g)} if s.senza_seduta_caricata(g) else {}),
                     nota="solo i dati del giocatore: niente confronti con i compagni salvo richiesta esplicita")
    out.vista = _con_metrica({"vista": "giocatore", "parametri": {"giocatore_id": gid, "data": f"{g:%Y-%m-%d}"}}, a)
    return out


def _t_fascia_attesa(s: Sessione, reg: Registro, a: dict) -> Uscita:
    gid = s.giocatore(a.get("giocatore", ""))
    md = a.get("giorno_md")
    md = int(str(md).upper().replace("MD", "").replace("+", "") or 0) if md not in (None, "") else None
    r = _fasce.fascia_attesa(s.visibile(s.in_esame), gid, md)
    return _pacchetto(reg, r.evidenze, giocatore=s.nome(gid), avvisi=r.avvisi)


def _t_confronta(s: Sessione, reg: Registro, a: dict) -> Uscita:
    nomi = a.get("giocatori") or []
    if len(nomi) < 2:
        raise ErroreStrumento("servono almeno due giocatori da confrontare")
    ids = [s.giocatore(n) for n in nomi]
    r = _giocatore.confronta(s.visibile(), ids)
    return _pacchetto(reg, r.evidenze, avvisi=r.avvisi, giocatori=r.sintesi["giocatori"],
                      nota="sono mediane delle ultime 4 settimane per giorno MD, non la seduta di oggi: non chiamarle «oggi»")


def _t_verifica(s: Sessione, reg: Registro, a: dict) -> Uscita:
    rep = replica_articolo()
    out = _pacchetto(reg, rep.evidenze, articolo=rep.sintesi["articolo"])
    out.vista = {"vista": "verifica", "parametri": {}}
    return out


def _t_limiti(s: Sessione, reg: Registro, a: dict) -> Uscita:
    r = _limiti(a.get("domanda"))
    return Uscita({"limiti": r.tabella.to_dict("records"), "avvertenza": r.avvisi[0],
                   "nota": "rispondi spiegando il perché e cosa si può dire invece; per le soglie cita [D1]"})


VISTE = {   # solo le viste che la lavagna sa disegnare (il confronto tra giocatori, V4, non c'è)
    "settimana": "griglia giocatori × giorni della settimana (parametri: data)",
    "seduta": "la seduta con le fasce di ogni giocatore (parametri: data, metrica)",
    "giocatore": "andamento di un giocatore con la sua fascia (parametri: giocatore, metrica)",
    "curva_settimana": "curva della settimana contro la settimana tipo (parametri: data, metrica)",
    "allenamento_partita": "carico della settimana in % della partita di riferimento (parametri: data, giocatore)",
    "verifica": "verifiche del motore: replica delle tabelle dell'articolo del dataset",
}


def _t_mostra_vista(s: Sessione, reg: Registro, a: dict) -> Uscita:
    vista = a.get("vista")
    if vista not in VISTE:
        raise ErroreStrumento(f"vista sconosciuta: {vista} (ammesse: {', '.join(VISTE)})")
    p = dict(a.get("parametri") or {})
    if "data" in p:
        p["data"] = f"{s.data(p['data']):%Y-%m-%d}"
    if p.get("giocatore") not in (None, ""):     # testo dell'agente (nome o maglia) → codice, in un campo a parte
        p["giocatore_id"] = s.giocatore(str(p.pop("giocatore")))
    p.pop("giocatore", None)
    if "giocatori" in p:
        p["giocatori_id"] = [s.giocatore(str(x)) for x in p.pop("giocatori")]
    return Uscita({"ok": True}, vista={"vista": vista, "parametri": p})


CATALOGO: dict[str, Strumento] = {t.nome: t for t in [
    Strumento("seduta", "La seduta di un giorno (di default il giorno in esame): per ogni metrica il percentile mediano della squadra, "
              "chi è fuori dalla sua fascia storica e di quanto, e gli avvisi di Vice nati quel giorno (da guardare). Usalo "
              "per ogni domanda su oggi o su un giorno preciso, anche su una sola metrica (\"chi è fuori fascia oggi in HSR\").", {"type": "object", "properties": {**P_DATA, **P_METRICA}}, _t_seduta,
              "leggo la seduta"),
    Strumento("settimana", "La settimana (microciclo) fino al giorno dato: mediane di squadra di ogni seduta contro la "
              "settimana tipo, i giocatori fuori fascia e gli avvisi di Vice ancora aperti (da guardare).", {"type": "object", "properties": {**P_DATA, **P_METRICA}}, _t_settimana,
              "guardo la settimana"),
    Strumento("alta_velocita", "La somma di sprint e HSR nella finestra da MD-4 a MD-2 prima della partita, contro i "
              "riferimenti di ciascun giocatore: chi arriva alla partita con poca alta velocità e chi ha dati incompleti. Non è "
              "la seduta di oggi.", {"type": "object", "properties": P_DATA},
              _t_alta_velocita, "controllo l'alta velocità"),
    Strumento("postpartita", "Il carico postpartita (MD+1, MD+2) dei non titolari dell'ultima partita contro il loro "
              "solito, con il carico della partita; più i titolari sopra fascia.", {"type": "object", "properties": P_DATA},
              _t_postpartita, "guardo il postpartita"),
    Strumento("allenamento_vs_partita", "Allenamenti della settimana finora in % della partita di riferimento (media "
              "da titolare): della squadra o di un giocatore.", {"type": "object", "properties": {**P_DATA, **P_GIOCATORE, **P_METRICA}},
              _t_allenamento_partita, "confronto allenamento e partita"),
    Strumento("giocatore", "Scheda di un giocatore: seduta del giorno, andamento delle ultime 4 settimane, allenamento "
              "rispetto alla partita, alta velocità, postpartita e i suoi avvisi di Vice (da guardare). Solo i suoi dati.",
              {"type": "object", "properties": {**P_GIOCATORE, **P_DATA, **P_METRICA}, "required": ["giocatore"]}, _t_giocatore,
              "apro la scheda del giocatore"),
    Strumento("fascia_attesa", "La fascia storica di un giocatore per un giorno MD (di default quello del giorno in esame).",
              {"type": "object", "properties": {**P_GIOCATORE, "giorno_md": {"type": "string", "description": "es. MD-3, MD+1"}},
               "required": ["giocatore"]}, _t_fascia_attesa, "calcolo la fascia attesa"),
    Strumento("confronta", "Confronto descrittivo tra giocatori scelti (ultime 4 settimane, per giorno MD), con le "
              "mediane di ruolo e squadra. Mai classifiche. Solo testo: non c'è un grafico di confronto.",
              {"type": "object", "properties": {"giocatori": {"type": "array", "items": {"type": "string"}}},
               "required": ["giocatori"]}, _t_confronta, "metto a confronto"),
    Strumento("verifica_motore", "Come sappiamo che i numeri sono giusti: il motore riproduce le tabelle dell'articolo "
              "che descrive il dataset del club.", {"type": "object", "properties": {}}, _t_verifica,
              "recupero le verifiche"),
    Strumento("limiti", "Cosa i dati non permettono di dire (rischio infortuni, ACWR, carico interno, minuti, velocità "
              "massima, motivi delle assenze…), perché, e cosa si può dire invece.",
              {"type": "object", "properties": {"domanda": {"type": "string"}}}, _t_limiti, "controllo i limiti dei dati"),
    Strumento("mostra_vista", "Porta sulla lavagna la vista più utile alla risposta. Viste: "
              + "; ".join(f"{k}: {v}" for k, v in VISTE.items()),
              {"type": "object", "properties": {"vista": {"type": "string", "enum": list(VISTE)},
                                                "parametri": {"type": "object"}}, "required": ["vista"]},
              _t_mostra_vista, "preparo la vista"),
]}


def schemi() -> list[dict]:
    return [t.schema() for t in CATALOGO.values()]


def esegui(nome: str, argomenti: str | dict, s: Sessione, reg: Registro) -> tuple[str, Uscita | None, str | None]:
    """(testo JSON per il modello, uscita, errore). Esegue solo strumenti del catalogo."""
    t = CATALOGO.get(nome)
    if t is None:
        return json.dumps({"errore": f"strumento sconosciuto: {nome}"}, ensure_ascii=False), None, "strumento sconosciuto"
    try:
        a = json.loads(argomenti) if isinstance(argomenti, str) else dict(argomenti or {})
        if not isinstance(a, dict):
            raise ErroreStrumento("parametri non validi")
        u = t.esegui(s, reg, a)
    except ErroreStrumento as e:
        return json.dumps({"errore": str(e)}, ensure_ascii=False), None, str(e)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        return json.dumps({"errore": f"parametri non validi: {e}"}, ensure_ascii=False), None, str(e)
    testo = json.dumps(u.dati, ensure_ascii=False, separators=(",", ":"), default=str)
    reg.registra_date(testo)
    return testo, u, None
