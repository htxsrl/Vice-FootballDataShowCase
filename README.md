# Vice, il vice-preparatore AI

Vice è uno strumento di supporto decisionale per i preparatori atletici e il loro staff: risponde alle domande sulla
performance fisica dei giocatori. Ogni risposta arriva con il grafico costruito per quella domanda, e ogni numero citato
si ritrova nel grafico con un clic. Quando arriva una nuova seduta, Vice segnala da sé cosa merita attenzione. Le
decisioni restano allo staff.

Progetto candidato al [Football Data Showcase 2026](https://footballdataanalysis.wylab.net/#showcase) di Wylab e
TOP-IX, ambito **Performance**. Non commerciale. Autori: Human Technology Excellence - HTX SRL; referente Ivan Buttignon.

- **Demo pubblica, senza registrazione:** https://vice.ht-x.com
- **Documentazione del progetto (PDF):** [candidatura/Vice-documentazione.pdf](candidatura/Vice-documentazione.pdf)

## Come funziona, in breve

1. **Dati:** l'export GPS della seduta, letto e controllato da un adattatore che lo porta nel formato interno di Vice.
2. **Motore:** fasce storiche per giocatore, ruolo e giorno rispetto alla partita (percentili), e le analisi della seduta,
   della settimana, dell'alta velocità, del postpartita e del rapporto allenamento/partita. Tutti i numeri li calcola il
   codice, e ognuno è un'evidenza con un identificativo.
3. **Avvisi:** regole scritte nel codice dicono cosa guardare oggi (calo persistente, carico insolito, richiamo dopo la
   partita, rientro e altre famiglie).
4. **Modello linguistico:** sceglie le analisi e scrive la risposta citando le evidenze ([E1], [E2]…).
5. **Verifica:** prima di mostrare il testo, un controllo deterministico confronta ogni numero e ogni giudizio («sopra la
   fascia», «sotto il solito») con le evidenze citate; le frasi che non tornano si correggono o si tolgono.

Il dettaglio è nel PDF di documentazione.

## Avviarlo in locale

Serve Docker. Per la voce serve Chrome.

```bash
cp .env.example .env                          # poi la chiave del gateway in VICE_LLM_API_KEY
docker compose up -d --build                  # http://localhost:8742
docker compose exec vice python3 -m scripts.scarica_zenodo   # il CSV originale di Zenodo, per «Scarica il CSV della demo»
docker compose exec vice python3 -m pytest tests             # i test
```

- **Senza una chiave:** con `VICE_LLM_PROVA=1` nel `.env` parte il **modello di prova**, deterministico e senza costi: le
  risposte copiano numeri e posizioni dalle evidenze. Serve a provare l'interfaccia e la catena dei dati, non a giudicare
  la qualità delle risposte.
- `python3 scripts/prova_interfaccia.py` (dal computer, con Chrome e Playwright) prova l'interfaccia col modello di prova.
- `VICE_OGGI` sceglie il giorno della demo (predefinito: 19/04/2024).

## Modelli LLM usati

Le chiamate passano dal gateway Hydrogen di HTX (LiteLLM, API compatibile OpenAI, Claude su AWS Bedrock con inferenza in
Unione Europea), configurato in `.env` (`VICE_LLM_BASE_URL`, `VICE_LLM_API_KEY`; struttura in `.env.example`).

| Modello (nome sul gateway) | Variabile | Uso |
|---|---|---|
| `HTX-EU-Claude-Sonnet-5` | `VICE_MODEL_AGENT` | agente della chat (strumenti, grafico e risposta), report del preparatore, correzione delle frasi non verificate |
| `HTX-EU-Claude-Sonnet-4.6` | `VICE_MODEL_RISERVA` | riserva quando Sonnet 5 non risponde dopo i nuovi tentativi |

## Dati e licenze

- **Zenodo 18986229** (Rodríguez-Fernández, 2026), **CC BY 4.0**: log GPS di una stagione (2023/24) di una squadra
  professionistica, allenamenti e partite. Articolo: Sierra-Casas et al., *Data* 11(4), 84, DOI 10.3390/data11040084.
  Il CSV originale non è nel repository (si scarica con `scripts.scarica_zenodo`); `data/processed/` contiene il formato
  di Vice, i report pronti e l'archivio degli avvisi. Attribuzioni e modifiche: [data/README.md](data/README.md).
- **Nomi dei giocatori e della squadra di fantasia** (AS New Trieste); i dati sono reali e anonimi.
- Librerie in locale: Apache ECharts 5.6.0 (Apache 2.0), font Newsreader e Schibsted Grotesk (SIL Open Font License).

## Struttura del codice

| Cartella | Contenuto |
|---|---|
| `vice/data/` | lettura del dataset, «oggi» simulato senza dati dal futuro, anagrafica di fantasia, adattatore degli export |
| `vice/analysis/` | motore di analisi deterministico: fasce, seduta, settimana, partita, giocatore, avvisi, limiti |
| `vice/agent/` | agente con strumenti in sola lettura, citazioni, verifica dei numeri e dei giudizi, report, prompt versionati |
| `vice/views/` | le specifiche dei grafici della lavagna, costruite dal server |
| `vice/static/`, `vice/templates/` | interfaccia: JavaScript a moduli senza build, ECharts, temi chiaro e scuro |
| `scripts/` | scaricamento ed elaborazione dei dati, report pronti, banco di prova, prova dell'interfaccia |
| `tests/` | test pytest, compreso il controllo che nessuna analisi veda dati successivi all'«oggi» |
| `candidatura/` | testo e stampa del PDF di documentazione |
| `wiki/metodi/glossario.md` | il glossario delle sigle che l'app mostra col pulsante «i» |
