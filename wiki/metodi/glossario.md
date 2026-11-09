# Glossario

> Le sigle di Vice, in una tabella. Pagina chiesta da Ivan il 28/10/2026 (decisione 46) e snellita lo stesso
> giorno su sua richiesta: solo una tabella con quattro colonne, Sigla, Significato, Unità di misura e Cosa
> misura (decisione 48 in [strategia](../progetto/strategia.md)).
>
> **È anche il glossario dell'app:** il pulsante «i» in alto a destra mostra la parte compresa tra i due segni
> `glossario-app` ([frontend-e-viste](../tecnica/frontend-e-viste.md#glossario)). Il «Significato» è quello che
> Vice scrive la prima volta che usa una sigla in una conversazione (`vice/agent/sigle.py`), e le soglie sono
> quelle del codice: `tests/test_glossario.py` controlla entrambe le cose.
>
> Il metodo (fasce, tolleranze, analisi, spunti) è spiegato in [analisi-vice](analisi-vice.md); i dati in
> [pipeline Zenodo](../dati/pipeline-zenodo.md).

<!-- glossario-app: inizio -->

| Sigla | Significato | Unità di misura | Cosa misura |
|---|---|---|---|
| MD | giorno della partita (Match Day) | | MD-1 è il giorno prima della partita, MD+1 il giorno dopo |
| TD | distanza totale (Total Distance) | m | tutta la distanza percorsa |
| HSR | corsa ad alta velocità (High Speed Running) | m | la distanza oltre i 19,8 km/h, sprint compreso |
| SPR | sprint | m | la distanza oltre i 25,2 km/h |
| ACC | accelerazioni intense | numero | le accelerazioni oltre i 3 m/s² |
| DCC | decelerazioni intense | numero | le frenate oltre i 3 m/s² |
| HMLD | distanza ad alto carico metabolico (High Metabolic Load Distance) | m | la distanza percorsa con potenza metabolica oltre i 25,5 W/kg |
| m/min | metri al minuto | m/min | quanta strada si fa in un minuto |
| P10 … P90 | percentile | | P90 è il valore sotto cui sta il 90% delle sedute passate |
| P25-P75 | fascia centrale | | la metà centrale delle sedute passate: il carico abituale |
| P10-P90 | fascia larga | | 8 sedute passate su 10 |
| [E1] | evidenza | | un numero calcolato da Vice: cliccalo per vederlo sulla lavagna |
| [D1] | definizione | | una soglia o una regola di Vice: passaci sopra per leggerla |
| ACWR | rapporto tra carico acuto e cronico | | Vice non lo usa |
| RPE | fatica percepita | | Vice non la misura: non è nei dati |

<!-- glossario-app: fine -->

## Sigle del progetto

Servono al team e nell'app non compaiono.

| Sigla | Significato | Dove |
|---|---|---|
| M0-M6 | le tappe della roadmap: Fondamenta, Dati, Motore di analisi, Agente e report, Lavagna e AG-UI, Rifinitura e misure, Candidatura; M2.4 e simili sono i sottopunti | [roadmap](../roadmap.md) |
| V1-V9 | le viste della lavagna; V4 non è stata fatta | [frontend-e-viste](../tecnica/frontend-e-viste.md#catalogo-delle-viste) |
| decisione 45 | le decisioni numerate del registro | [strategia](../progetto/strategia.md) |
| D1-D6 | le sei decisioni di prodotto iniziali (per esempio D6: report del giocatore senza confronti coi compagni) | [roadmap](../roadmap.md) |
| [D1]-[D6], [E1]… | le definizioni fisse e le evidenze citate nei testi di Vice | [agente](../tecnica/agente.md) |
| AG-UI | *Agentic UI*: l'interfaccia che l'agente compone mentre risponde, presa da TIDE | [ispirazione TIDE](../progetto/ispirazione-tide-agui.md) |
| LLM | il modello linguistico che scrive le risposte | [modelli-llm](../tecnica/modelli-llm.md) |
| SSE | *Server-Sent Events*: il server manda la risposta un pezzo alla volta | [architettura](../tecnica/architettura.md) |
| KPI | *Key Performance Indicator*: un indicatore | [analisi-vice](analisi-vice.md) |

**Attenzione alla lettera D:** le decisioni D1-D6 della roadmap e le definizioni [D1]-[D6] sono cose diverse.
Le prime si scrivono senza parentesi, le seconde sempre tra parentesi quadre.
