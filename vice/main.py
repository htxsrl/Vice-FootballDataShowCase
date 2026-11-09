"""Vice — server FastAPI.

- `/api/chat`: l'agente con gli strumenti del motore (M3.1), in streaming SSE.
- `/api/report`: report della seduta, della settimana o del giocatore, per il preparatore (M3.4-M3.6, decisione 51).
- `/api/contesto`: dove siamo nella stagione il giorno dato, il calendario fino a oggi, i giorni coi report pronti e la
  rosa (M4.7, decisione 49).
- `/api/vista`: la specifica di una vista della lavagna, costruita dal motore (M4.2).
- `/api/carica` e `/api/export-prova`: l'export GPS di una seduta, caricato o scaricato (M4.8); la seduta del giorno
  della demo arriva solo così (decisione 54).
- `/api/avvisi`: gli avvisi di Vice col loro stato, per l'apertura e il menù «Da guardare» (decisione 54).
- `/`: la pagina, col glossario della wiki nel pannello «i» (decisione 46, vice/glossario.py).
Eventi SSE: `avvisi` (solo nei report, per primo), `tappa`, `delta`, `vista`, `verifica` (testo finale verificato), `done`,
`error`.
Architettura: wiki/tecnica/architettura.md; agente: wiki/tecnica/agente.md.
"""

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .agent import agente, archivio, da_guardare
from .agent.sigle import per_il_front_end as sigle_front_end
from .agent import report as reportistica
from .agent.contesto import GIORNO_DEMO, ErroreStrumento, Sessione
from .analysis.evidenze import data_it, giorno_md_it
from .config import get_settings
from .data import caricamenti
from .data.anagrafica import DICITURA, SQUADRA
from .data.export_gps import ErroreExport, esporta_seduta, formato, leggi_export, righe_zenodo
from .data.zenodo import METRICHE
from .glossario import glossario
from .llm import LLMError
from .views import costruisci

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def vita(_app: FastAPI):
    # gli avvisi (decisione 54): archivio e classificazione della stagione si preparano in un thread, senza aspettarli
    threading.Thread(target=da_guardare.prepara, name="prepara-avvisi", daemon=True).start()
    yield


app = FastAPI(title="Vice", version="0.4.0", lifespan=vita)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    oggi: str | None = Field(default=None, max_length=10, description="AAAA-MM-GG; vuoto = data predefinita")
    giorno: str | None = Field(default=None, max_length=10, description="giorno in esame scelto nel calendario (decisione 47)")
    lavagna: dict | None = None
    caricamento: str | None = Field(default=None, max_length=20, description="codice di un export caricato")


class VistaRequest(BaseModel):
    vista: str = Field(max_length=40)
    oggi: str | None = Field(default=None, max_length=10)
    giorno: str | None = Field(default=None, max_length=10)
    parametri: dict = Field(default_factory=dict)
    caricamento: str | None = Field(default=None, max_length=20)


class CaricaRequest(BaseModel):
    nome: str = Field(default="export.csv", max_length=200)
    testo: str = Field(min_length=1, max_length=2_000_000)


class ReportRequest(BaseModel):
    tipo: str = Field(pattern="^(seduta|settimana|giocatore)$")
    oggi: str | None = Field(default=None, max_length=10)
    giocatore: str | None = Field(default=None, max_length=60)
    caricamento: str | None = Field(default=None, max_length=20)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"dicitura": DICITURA, "glossario": glossario()})


@app.get("/api/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "llm_gateway": s.llm_base_url,
        "llm_key_configured": bool(s.llm_api_key),
        "models": {"agent": s.model_agent, "deep": s.model_deep, "riserva": s.model_riserva},
        **({"modello_di_prova": True} if s.llm_prova else {}),
    }


@app.get("/api/contesto")
async def contesto(oggi: str | None = None, caricamento: str | None = Query(default=None, max_length=20)):
    try:
        s = Sessione.crea(oggi, caricamento=caricamento)
    except ErroreStrumento as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    c = s.stagione.contesto(s.oggi)
    g = s.giocatori
    v = s.visibile()
    prevista = s.stagione.al(s.oggi)   # il calendario delle sedute è noto in anticipo, i dati no (decisione 54)
    giorni = s.stagione.giorni_di_seduta
    prima = [d for d in giorni if d < s.oggi]
    dopo = [d for d in giorni if d > s.oggi]
    # la striscia della stagione: le sedute fino a oggi, e del futuro solo le date delle partite (D2)
    sedute = [{"data": f"{r.data:%Y-%m-%d}", "tipo": r.tipo, "md": giorno_md_it(r.giorno_md)} for r in prevista.sedute.itertuples()]
    partite_future = [f"{d:%Y-%m-%d}" for d in v.calendario["data"] if d > s.oggi]
    pronti = [d for d in archivio.giorni(s.oggi) if s.caricata(d)]
    return {"oggi": f"{s.oggi:%Y-%m-%d}", "oggi_it": data_it(s.oggi), "giorno_md": giorno_md_it(c.giorno_md),
            "settimana": c.settimana,
            "ultima_partita": f"{c.ultima_partita:%Y-%m-%d}" if c.ultima_partita is not None else None,
            "prossima_partita": f"{c.prossima_partita:%Y-%m-%d}" if c.prossima_partita is not None else None,
            "seduta_oggi": not v.seduta_di_oggi.empty,
            "seduta_prevista": not prevista.seduta_di_oggi.empty,      # oggi c'è una seduta in calendario
            "seduta_caricata": s.caricata(),                            # e Vice ne ha i dati (decisione 54)
            "tipo_seduta": str(prevista.seduta_di_oggi["tipo"].iloc[0]) if not prevista.seduta_di_oggi.empty else None,
            "giorno_demo": f"{GIORNO_DEMO:%Y-%m-%d}",
            "seduta_precedente": f"{prima[-1]:%Y-%m-%d}" if prima else None,
            "seduta_successiva": f"{dopo[0]:%Y-%m-%d}" if dopo else None,
            "stagione": {"inizio": f"{s.stagione.inizio:%Y-%m-%d}", "fine": f"{s.stagione.fine:%Y-%m-%d}"},
            "calendario": {"sedute": sedute, "partite_future": partite_future},
            "report_pronti": pronti,   # i giorni col pallino nel calendario (decisione 49), solo se caricati
            "sigle": sigle_front_end(),                  # in grassetto nelle risposte (decisione 52)
            "squadra": SQUADRA, "dicitura": DICITURA,
            "giocatori": g[["giocatore_id", "nome_completo", "numero", "ruolo"]].to_dict("records")}


@app.get("/api/avvisi")
async def avvisi(oggi: str | None = None, caricamento: str | None = Query(default=None, max_length=20)):
    """Gli avvisi di Vice fino all'ultimo giorno caricato, ciascuno col suo stato (decisione 54): l'apertura e il
    menù «Da guardare» li leggono da qui."""
    try:
        s = Sessione.crea(oggi, caricamento=caricamento)
    except ErroreStrumento as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return await asyncio.to_thread(da_guardare.stato, s)


@app.post("/api/vista")
async def vista(req: VistaRequest):
    try:
        s = Sessione.crea(req.oggi, caricamento=req.caricamento, giorno=req.giorno)
        return costruisci(req.vista, s, req.parametri)
    except ErroreStrumento as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _streaming(genera):
    async def eventi():
        try:
            async for ev in genera():
                yield _sse(ev["evento"], ev["dati"])
        except (LLMError, ErroreStrumento) as exc:
            yield _sse("error", {"message": str(exc)})
        except Exception:  # noqa: BLE001 — l'utente non deve vedere tracce Python
            yield _sse("error", {"message": "Errore di comunicazione con il modello. Riprova."})

    return StreamingResponse(eventi(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/carica")
async def carica(req: CaricaRequest):
    """Un export GPS di una seduta → righe nel formato Vice, tenute in memoria con un codice (M4.8). Un file con gli
    stessi valori del dataset ha il codice `dataset-AAAA-MM-GG` e non occupa memoria (decisione 54)."""
    s = Sessione.crea()
    try:
        righe = leggi_export(req.testo, s.stagione)
    except ErroreExport as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    data = pd.Timestamp(righe["data"].iloc[0]).normalize()
    if data > GIORNO_DEMO:
        raise HTTPException(status_code=422, detail=f"il file è del {data_it(data)}, dopo oggi ({data_it(GIORNO_DEMO)}): "
                                                    "Vice non vede il futuro")
    # confronto con il dataset: il file può essere modificato, e Vice usa i suoi numeri
    v = s.stagione.al(data)
    dataset = v.seduta_di_oggi.set_index("giocatore_id")[list(METRICHE)] if not v.seduta_di_oggi.empty else None
    diversi = None
    if dataset is not None:
        nostro = righe.set_index("giocatore_id")[list(METRICHE)]
        comuni = nostro.index.intersection(dataset.index)
        diversi = int((nostro.loc[comuni].round() != dataset.loc[comuni].round()).sum().sum()) + \
            len(nostro.index.symmetric_difference(dataset.index)) * len(METRICHE)
    codice = caricamenti.codice_dataset(data) if diversi == 0 else caricamenti.salva(righe, req.nome).codice
    ctx = s.stagione.contesto(data)
    fmt = formato(req.testo.lstrip("\ufeff").splitlines()[0].replace(";", ",").split(","))
    return {"caricamento": codice, "data": f"{data:%Y-%m-%d}", "data_it": data_it(data), "giorno_md": giorno_md_it(ctx.giorno_md),
            "tipo": str(righe["tipo"].iloc[0]), "giocatori": int(len(righe)), "formato": fmt,
            "valori_diversi_dal_dataset": diversi,
            "prima_volta": bool(data >= GIORNO_DEMO)}   # la seduta di oggi: Vice non la conosceva


@app.get("/api/export-prova")
async def export_prova(data: str | None = None, formato_file: str = Query("zenodo", alias="formato", pattern="^(zenodo|gps)$")):
    """Il file di prova di una seduta, da scaricare e ricaricare (decisione 36): di default le righe di quel
    giorno copiate dal CSV originale di Zenodo 18986229 (decisione 42); con `formato=gps` l'export "come lo
    esporta un GPS"."""
    try:
        s = Sessione.crea(data)
    except ErroreStrumento as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    v = s.stagione.al(s.oggi)   # le righe del dataset, anche per la seduta di oggi da caricare (decisione 54)
    if v.seduta_di_oggi.empty:
        raise HTTPException(status_code=404, detail=f"il {data_it(s.oggi)} non c'è una seduta con dati")
    if formato_file == "zenodo":
        try:
            testo = righe_zenodo(get_settings().raw_dir / "zenodo" / "DataSetTMr.csv", s.oggi)
        except ErroreExport as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        nome = f"zenodo-18986229-seduta-{s.oggi:%Y-%m-%d}.csv"
    else:
        testo = esporta_seduta(v.seduta_di_oggi, v.giocatori)
        nome = f"vice-export-gps-{s.oggi:%Y-%m-%d}.csv"
    return Response(testo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@app.post("/api/chat")
async def chat(req: ChatRequest):
    def genera():
        sessione = Sessione.crea(req.oggi, caricamento=req.caricamento, giorno=req.giorno)
        return agente.turno([m.model_dump() for m in req.messages], sessione, req.lavagna)
    return _streaming(lambda: _con_sessione(genera))


@app.post("/api/report")
async def report(req: ReportRequest):
    def genera():
        sessione = Sessione.crea(req.oggi, caricamento=req.caricamento)
        return reportistica.report(req.tipo, sessione, req.giocatore)
    return _streaming(lambda: _con_sessione(genera))


async def _con_sessione(genera):
    """Crea la sessione dentro lo stream, così un errore di data diventa un evento `error`."""
    async for ev in genera():
        yield ev
