# Vice · testo della bozza del PDF di documentazione

> Tutto il testo del PDF (campo 11 del form), nello stesso ordine, ricavato da `documentazione.html` il
> 06/11/2026 per leggerlo e correggerlo più comodamente. Il PDF si stampa dall'HTML: le correzioni fatte qui
> vanno riportate in `documentazione.html` prima di ristamparlo. Le parti **[tra parentesi quadre, in
> grassetto]** sono da completare; le immagini sono indicate col nome del file.

---
## Copertina

**Titolo:** Vice

**Sottotitolo:** il vice-preparatore AI per la performance fisica

Vice è lo **strumento di supporto decisionale** per i preparatori atletici e il loro staff: risponde alle domande dello staff sulla performance fisica dei giocatori. Ogni risposta arriva con il **grafico costruito per quella domanda**, e **ogni numero citato si ritrova nel grafico con un clic**. Quando arriva una nuova seduta, **Vice segnala da sé cosa merita attenzione**. Le decisioni restano allo staff.

- **Ambito:** Performance
- **Autori:** Human Technology Excellence - HTX SRL
- **Referente:** Ivan Buttignon
- **Demo:** https://vice.ht-x.com
- **Video:** **[link al video della demo, 2-3 minuti]**
- **Codice:** https://github.com/htxsrl/Vice-FootballDataShowCase
- **Data:** 10/11/2026

**Dataset di esempio utilizzati**: 
- Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0) 

---
## 1. Il problema

Dopo ogni allenamento e ogni partita lo staff atletico riceve una **grande quantità di dati** su ciascun giocatore. Le unità GPS registrano posizione e velocità e, con accelerometri, giroscopi e magnetometri, anche accelerazioni, frenate e cambi di direzione; da queste misure si ricavano indicatori come la potenza metabolica e molte altre. 
 A seconda del club si aggiungono il tracking ottico delle partite, i test di forza, la frequenza cardiaca. 
 Spesso i dati arrivano da **fornitori diversi**, ognuno con la propria piattaforma e il proprio formato di esportazione.

Da questi dati il preparatore atletico deve ricavare **ogni giorno risposte a domande precise**:

| Quando | La domanda dello staff |
|---|---|
| Dopo ogni seduta | Chi si è allontanato dal suo carico abituale, e di quanto? |
| Dopo la partita | Chi non ha giocato ha recuperato il lavoro della partita, o serve un richiamo? |
| Prima della partita | Qualcuno arriva alla partita con poca corsa ad alta velocità? |
| Durante la settimana | Qualcuno è in calo mentre la squadra no? |
| Dopo un'assenza | Com'è ripartito chi rientra? |

Per rispondere, ogni valore va confrontato con **lo storico giusto**: lo stesso giocatore, lo stesso ruolo, lo stesso giorno rispetto alla partita. Poi il risultato va spiegato all'allenatore. 
Le piattaforme dei fornitori e le dashboard mostrano però **molte misure e molti grafici insieme**: molte volte non c'è la risposta precisa che soddisfa la richiesta esatta dello staff, oppure va cercata tra la grande quantità di dati e grafici presentati. 
Inoltre, il confronto con lo storico giusto va spesso **costruito a mano**. 

Il tema tocca due degli ostacoli che la survey 2026 dell'Osservatorio sulla Football Data Analysis di Wylab propone per il settore in Italia: la «**difficoltà di comunicazione tra area tecnica e area analitica**» e la «**mancanza di rigore metodologico**».

---
## 2. Vice

Vice è un assistente AI pensato per **un solo ambito, la performance fisica** dei calciatori. 
**Non è una dashboard**: il preparatore infatti parte da una domanda, la chiede a Vice in linguaggio naturale e Vice **mostra soltanto ciò che serve a rispondere**. 
Si regge su tre idee.

### 2.1 Vice è pro-attivo

Quando arriva la seduta del giorno, **Vice segnala da sé** cosa merita attenzione prima della seduta successiva o della partita: chi si è allontanato molto dal suo carico abituale, in eccesso o in difetto; chi non ha giocato e dopo la partita ha fatto poca alta velocità; chi arriva alla partita con poco sprint; chi, nelle ultime due settimane, è sotto il suo solito mentre la squadra no; chi rientra dopo un'assenza e chi è tornato nel suo solito. 
Gli avvisi sono scritti dal codice e sono **pochi, al massimo tre al giorno**, in modo da presentare allo staff solo informazioni veramente rilevanti e significative. 
Ognuno propone cosa valutare, verificare o approfondire, e si può aprire sulla lavagna, discutere in chat o segnare come visto (Figura 1). 
**La decisione resta sempre al preparatore atletico e allo staff.**

*[Immagine: immagini/apertura.jpg]*

**Figura 1. L'apertura di Vice il 19/04/2024.** Prima che si carichi la seduta del giorno, Vice ricorda gli avvisi ancora da guardare: Simone Amato e Riccardo Benedetti sotto il loro solito nelle ultime due settimane. Ogni avviso ha tre azioni: mostrarlo sulla lavagna, chiederne conto a Vice, segnarlo come visto.

### 2.2 Una risposta precisa, con il suo grafico

Il preparatore scrive o detta la domanda **con le sue parole**: «Chi è fuori fascia oggi in alta velocità?», «Come sta Cortese?», «I non titolari hanno recuperato il lavoro della partita?». 
Vice risponde **in poche righe** e, accanto alla chat, porta sulla lavagna **il grafico costruito per quella domanda**: la misura chiesta, il giorno chiesto, il giocatore in evidenza (Figura 2). All'apertura la pagina mostra solo la chat; la lavagna compare quando una risposta ha un grafico, e mostra una vista alla volta.

### 2.3 Ogni numero ha la sua prova

Ogni frase che contiene un numero **cita il dato da cui viene**, con un'etichetta come [E1]. Un clic sull'etichetta porta la lavagna sul grafico giusto e **accende il punto corrispondente** (Figura 2). **I numeri non li scrive il modello linguistico: li calcola il codice.** Prima di mostrare il testo, **un controllo automatico** confronta ogni numero e ogni giudizio («sopra la fascia», «sotto il solito») con i dati citati; le frasi che non tornano vengono corrette o tolte, e il messaggio lo dichiara.

*[Immagine: immagini/citazione.jpg]*

**Figura 2. Dalla domanda al dato.** Il 19/04/2024, caricata la seduta, il preparatore chiede «Chi è fuori fascia oggi in alta velocità?». Vice risponde in poche righe: tre giocatori sopra la loro fascia, ogni numero con la sua citazione, tutte le frasi verificate sui dati. Il clic sulla citazione [E1], «69 m, molto sopra la fascia larga», accende sulla lavagna la riga di Matteo Basile e, sopra il grafico, la prova del numero. Ogni riga è un giocatore: le bande sono la sua fascia storica per quel giorno della settimana, il punto è il valore di oggi.

**Vice in tre misure, sulla stagione 2023/24** (come sono state ottenute: capitolo 6):

- **1.494 su 1.494**: le frasi con numeri nei 142 report che Vice ha scritto per la stagione, tutte verificate sui dati prima di essere mostrate
- **28 su 28**: le domande di prova superate dall'agente: domande dello staff, report, grafici e trabocchetti come il rischio infortuni
- **8**: gli avvisi a settimana, in mediana sulla stagione (al massimo 14): lo staff ne riceve pochi

---
## 3. Una giornata con Vice

Vice si apre dal browser, senza registrazione: https://vice.ht-x.com. 
La demo si svolge il 19/04/2024, vigilia di una partita, con la stagione precedente già nei dati.

1. **Caricare la seduta.** Il preparatore trascina nella chat l'export scaricato dalla piattaforma del fornitore. Vice dice cosa ha letto e analizza i numeri del file, anche se un valore è stato cambiato a mano.
2. **Leggere avvisi e report.** In testa gli avvisi nati quel giorno; sotto, il report: sintesi, chi è fuori fascia, verso la partita, qualità del dato.
3. **Guardare la prova.** «Mostra sulla lavagna» apre il grafico di un avviso; un clic su una citazione accende il dato.
4. **Chiedere.** In chat, o tenendo premuto il microfono.
5. **Tornare indietro.** Dal calendario si apre qualunque giorno della stagione: le domande successive riguardano quel giorno, e lo si può confrontare con oggi.

*[Immagine: immagini/mostra.jpg, immagini/settimana.jpg]*

**Figura 3. Due domande, due grafici.** A sinistra lo sprint di Simone Amato nelle ultime sedute, aperto da «Mostra sulla lavagna» sul suo avviso: ogni seduta ha la sua fascia per quel giorno della settimana, e la spiegazione dice «più basso del suo solito». A destra la settimana della squadra in alta velocità: una cella per giocatore e seduta, col valore e una freccia per la posizione rispetto alla fascia. I colori sono scelti per restare distinguibili anche da chi non distingue il rosso dal verde.

| Operazione | Tempo | Costo |
|---|---|---|
| Analisi di una giornata (motore) | 0,5 s in media | nessuno |
| Avvisi di una seduta caricata | circa 1 s | nessuno |
| Report della seduta scritto dal modello | 10-22 s | 0,02-0,06 $ |
| Report già pronto, riletto e ricontrollato | meno di 1 s | nessuno |
| Domanda in chat | 7-18 s | 0,02-0,04 $ |

---

## 4. Due settimane di aprile, viste da Vice

Gli avvisi di un giocatore, **letti in sequenza**, raccontano ciò che la tabella di un solo giorno non mostra. Ecco quelli di Simone Amato tra la partita del 06/04 e quella del 20/04/2024 (MD è il giorno della partita: MD-3 tre giorni prima, MD+2 due giorni dopo; HSR è la corsa ad alta velocità, oltre 19,8 km/h):

| Giorno | Avviso | Cosa dice Vice (testo del codice, abbreviato) |
|---|---|---|
| 08/04, MD+2 | Richiamo | Non è partito titolare e dopo la partita ha fatto 0 m di HSR, sotto la sua fascia (169-377 m): con la partita arriva al 27% del suo riferimento. |
| 10/04, MD-3 | Calo persistente | In cinque sedute meno alta velocità, sprint e distanza totale del suo solito, mentre la squadra era nella norma. |
| 11/04, MD-2 | Settimana sotto il solito | Finora gli allenamenti valgono in alta velocità il 48% della sua partita, contro una mediana di squadra del 128%. |
| 12/04, MD-1 | Nota positiva | Tornato nel suo carico abituale in alta velocità e distanza totale. |
| 15/04, MD+2 | Tendenza lunga | Nelle ultime quattro settimane fa meno sprint di due-tre mesi prima (scarto mediano −32%). |
| 17/04, MD-3 | Calo persistente | In cinque sedute meno sprint del suo solito, con la squadra nella norma. Resta da guardare il giorno della demo. |

La lettura per lo staff è concreta: **dopo il richiamo l'alta velocità è tornata nel solito, lo sprint no**. Il 19/04, caricata la seduta, Vice aggiunge un carico insolito di Matteo Basile alla vigilia della partita (alta velocità 69 m, fascia larga 2-53 m), un calo della distanza totale di Christian Porcu e il ritorno nel suo solito di Riccardo Benedetti.

---
## 5. Come funziona

- **1. Dati**: l'export della seduta, letto e controllato
- **2. Motore**: fasce storiche e analisi, ogni numero con la sua evidenza
- **3. Avvisi**: regole scritte nel codice: cosa guardare oggi
- **4. Modello**: sceglie le analisi e scrive, citando le evidenze
- **5. Verifica**: numeri e giudizi confrontati coi dati prima di mostrarli

Le sei misure del GPS (TD, HSR, SPR, ACC, DCC, HMLD) e il dataset su cui la demo le calcola sono descritti nel capitolo 8.

### Il carico abituale: le fasce storiche

Per ogni misura e giorno rispetto alla partita (e, a MD, MD+1 e MD+2, separando titolari e non titolari) Vice costruisce dallo storico precedente la distribuzione dei valori e ne ricava due fasce: la **fascia centrale**, tra il 25° e il 75° percentile (P25-P75), che descrive il carico abituale, e la **fascia larga**, tra il 10° e il 90° (P10-P90), oltre la quale un valore è poco usuale. I percentili reggono meglio della media su distribuzioni asimmetriche come quelle dello sprint; sono scelte dichiarate, senza significato clinico.

| Livello della fascia | Quando si usa | Come si calcola |
|---|---|---|
| Personale | almeno 8 sedute del giocatore in quel giorno | una distribuzione pesata: le sue sedute pesano n / (n + 8), cioè il 50% con 8 sedute e il 75% con 24; il resto è il ruolo |
| Ruolo | altrimenti, con almeno 6 casi da almeno 3 sedute diverse | percentili del ruolo |
| Squadra | altrimenti, con le stesse soglie | percentili della squadra |
| Nessuna | sotto le soglie | «storico insufficiente», come nelle prime tre settimane |

Un valore esce da un bordo della fascia solo se lo supera di una **tolleranza operativa**, il massimo tra un minimo assoluto e una quota della mediana. Non è l'errore del GPS: per alta velocità, sprint e conteggi non esiste una stima trasferibile (Beato et al., 2018; Varley et al., 2017; Hopkins, 2000). Una fascia costruita su meno di 6 sedute diverse è **provvisoria**: si mostra ma non genera avvisi, perché i giocatori della stessa seduta seguono lo stesso programma e non sono casi indipendenti.

| Misura | TD | HSR | SPR | ACC, DCC | HMLD |
|---|---|---|---|---|---|
| Tolleranza | 100 m o 3% | 10 m o 10% | 5 m o 20% | 2 o 10% | 30 m o 5% |

### Le analisi

| Analisi | Domanda | Cosa confronta |
|---|---|---|
| Seduta | Chi è fuori dal suo carico abituale oggi? | ogni giocatore e misura contro la sua fascia; per la squadra il percentile mediano |
| Settimana | La settimana segue la curva solita? | la mediana di squadra di ogni seduta contro lo stesso giorno delle settimane passate |
| Alta velocità | Chi arriva alla partita con poca velocità? | sprint e HSR da MD-4 a MD-2 contro la somma dei suoi riferimenti giornalieri (Gualtieri et al., 2023; Dello Iacono et al., 2023) |
| Postpartita | Chi non ha giocato ha recuperato il lavoro? | i non titolari a MD+1 e MD+2 contro il loro solito, sommando la partita (Clemente et al., 2024) |
| Allenamento e partita | Quanto della partita stiamo allenando? | la settimana in % del riferimento di partita: la media del giocatore da titolare, o del ruolo se ha meno di 3 partite (Ammann e Altmann, 2023) |
| Andamento | Sta calando o crescendo? | le ultime 4 settimane contro le sue sedute precedenti dello stesso giorno |

Ogni risultato è un insieme di **evidenze**: un identificativo stabile (per esempio `seduta/2024-04-19/9/hsr`), il valore arrotondato come si mostra e il contesto (fascia, percentile, tolleranza, numero di casi, copertura dei dati). Un report si basa su 300-650 evidenze.

### Gli avvisi

Gli avvisi nascono dalle analisi e devono superare **tre filtri**: essere difendibili con i dati disponibili, portare a una scelta concreta dello staff, essere rari e persistenti.

| Famiglia | Quando nasce |
|---|---|
| Richiamo dopo la partita | un non titolare ha fatto dopo la partita molta meno alta velocità del solito, e con la partita resta sotto il 60% del suo riferimento |
| Alta velocità prima della partita | a MD-2 o MD-1, sprint nullo o quasi per chi di solito ne fa, oppure sprint o HSR molto sotto il solito |
| Carico insolito | vicino alla partita, distanza o HSR oltre il P90 della sua fascia di almeno il 25% (sprint e decelerazioni del 50%) |
| Settimana sopra o sotto il solito | a MD-2, la sua settimana rispetto ai compagni è lontana da come è di solito |
| Calo persistente | almeno 3 sedute sotto il suo solito in due settimane, mentre la squadra in quelle sedute era nella norma |
| Rientro dopo un'assenza | di nuovo dati dopo almeno 3 sedute di squadra senza |
| Scarto di reparto | nel riassunto settimanale, chi fa sistematicamente meno di tutti i compagni di reparto |
| Note positive | chi torna nel suo solito dopo un calo o un rientro |
| Qualità del dato | valori impossibili nel file, o un giocatore senza dati da due sedute |

Il preparatore segna un avviso come visto. Vice lo aggiorna quando ne nasce uno più recente sullo stesso giocatore, lo chiude quando la situazione finisce, per esempio con la nota «tornato nel suo solito», e lo fa scadere alla partita successiva o, per un calo, dopo due settimane. Le soglie sono state tarate sull'intera stagione, guardando ogni giorno col solo suo passato: in mediana **8 avvisi a settimana** e al massimo 14, escluse le segnalazioni sui dati; in 69 giorni di seduta su 151 non nasce alcun avviso. Il rischio di infortunio è **escluso di proposito** (Impellizzeri et al., 2020).

### Il modello linguistico e la verifica

Vice usa Claude Sonnet 5 di Anthropic attraverso il gateway Hydrogen di HTX, su AWS Bedrock con inferenza in Unione Europea; se il modello non risponde dopo due tentativi, subentra Claude Sonnet 4.6. In chat il modello dispone di **11 strumenti in sola lettura**: le analisi del motore, i limiti dei dati e uno strumento che porta un grafico sulla lavagna. Riceve i risultati come evidenze etichettate ([E3]), con i numeri già scritti da citare così come sono. Per i report riceve in una sola chiamata i dati già calcolati e scrive secondo una struttura fissa.

Prima di mostrare il testo, **un controllo deterministico** lo verifica frase per frase:

- **numeri:** ogni numero deve coincidere, entro l'arrotondamento con cui è scritto, con un numero dell'evidenza citata;
- **giudizi:** se una frase dice sopra, sotto, dentro o fuori dalla fascia, almeno un dato citato deve dire lo stesso;
- **suggerimenti:** le frasi che iniziano con «Valutare», «Verificare» o «Approfondire» devono venire dagli avvisi del codice: il modello non ne inventa.

Le frasi che non passano vanno a una sola chiamata di correzione, con il motivo; quelle che non passano ancora **si tolgono**, e il messaggio lo dichiara («N frasi su N verificate sui dati»).

---
## 6. Come lo abbiamo verificato

I controlli rispondono a tre domande diverse: il software fa ciò che dichiara? I dati sono coerenti? Le indicazioni sono utili allo staff?

- **Software.** 801 test automatici. Un test controlla, su tutti i 151 giorni di seduta, che Vice non veda dati successivi all'oggi.
 Ogni errore corretto ha il suo test. Una prova automatica dell'interfaccia in Chrome esegue 99 controlli sul copione della demo.
- **Dati.** La replica delle tabelle dell'articolo che descrive il dataset (capitolo 8). 
- **Agente.** Un banco di prova di 28 scenari: domande dello staff, report, domande con grafico e domande trabocchetto (rischio infortuni, ACWR, «il migliore», minuti giocati, una data futura, la velocità massima). Nell'ultimo giro completo, del 26/10/2026, li ha superati tutti.
- **Utilità.** Non è ancora misurata. Le regole sono state scelte conoscendo l'intera stagione: è una verifica retrospettiva, non una validazione con uno staff.

### Il postpartita dei non titolari nella stagione

| Esito (HSR postpartita) | Casi |
|---|---|
| in linea col solito | 108 |
| nessuna seduta postpartita registrata | 64 |
| senza fascia (storico insufficiente) | 51 |
| nessun dato del giocatore | 23 |
| sotto il solito | 20 |
| molto sotto il solito | 17 |

*30 partite, 283 non titolari: una fotografia per partita, a finestra postpartita chiusa.*

Dei 17 casi molto sotto il solito, 7 avevano già fatto molta alta velocità in partita, 9 rientrano in episodi di gruppo, che indicano il programma e non il singolo, e 5 hanno fasce provvisorie; un caso può ricadere in più gruppi. Restano **3 richiami individuali** in tutta la stagione. In 108 casi su 291 manca il carico della partita: il dataset non distingue chi non ha giocato da un dato perso, e Vice lo dichiara **invece di contarlo come zero**.

---
## 7. Limiti e sviluppi

### Limiti

- **Dati assenti nel dataset di esempio.** Mancano carico interno (RPE, frequenza cardiaca), durata delle sedute, minuti giocati e velocità massima: niente intensità al minuto, e lo sprint è assoluto, non relativo alla velocità massima del giocatore. Il riferimento di partita, senza i minuti, non equivale a una partita intera.
- **Le fasce sono lo storico, non il programma.** Dicono quanto un carico è abituale, non se era previsto né se è giusto. Si costruiscono sullo storico di ogni squadra e non sono soglie da trasferire ad altri club.
- **Soglie operative.** Percentili, tolleranze e regole degli avvisi sono scelte dichiarate, riviste conoscendo l'intera stagione: non sono soglie fisiologiche né l'errore del GPS.
- **Verifica del testo.** Il controllo riguarda numeri, giudizi di posizione e suggerimenti; una frase interpretativa senza numeri non è verificabile in questo modo.
- **Utilità non misurata.** Nessuno staff ha ancora usato Vice sulla propria stagione.

### Sviluppi

- **Rischio di infortunio:** al momento Vice non valuta il rischio di infortunio di un calciatore in quanto il dataset Zenodo non contiene informazioni sufficienti. L'ACWR è criticato (Impellizzeri et al., 2020) e l'articolo del dataset sconsiglia di usarlo. Il dataset inoltre non ha le righe degli infortunati, quindi un modello non si potrebbe nemmeno verificare. Infatti, con i soli carichi esterni non esiste un metodo di previsione difendibile. 
Con carico interno, minuti e dati sanitari si potranno affiancare analisi oggi escluse, solo con metodi validati e dati trattati secondo il GDPR.
- **Validazione con uno staff:** una stagione in parallelo al lavoro reale, misurando quali avvisi portano a una scelta e quali no.
- **Altri fornitori e altri dati:** un adattatore per l'export di ciascun fornitore, e le misure oggi assenti, come test di forza, frequenza cardiaca e minuti giocati.
- **Più squadre e più stagioni:** per misurare quanto le regole degli avvisi si trasferiscono.

---
## 8. I dati utilizzati

In un club il preparatore scarica l'export della seduta dalla piattaforma del suo fornitore e lo carica in Vice. Un adattatore traduce ogni formato nel **formato interno di Vice** (giocatore, giorno, giorno rispetto alla partita, ruolo, misure), così il motore di analisi **non dipende da chi ha prodotto il dato**. 
Per simulare il comportamento reale di Vice è stato utilizzato un **dataset pubblico ed anonimo**, Zenodo 18986229. 

| Dataset | Cosa simula | Contenuto | Licenza |
|---|---|---|---|
| Zenodo 18986229 | gli export GPS di un club, seduta per seduta | una stagione (2023/24) di una squadra professionistica: una riga per giocatore e giorno, allenamenti e partite, dati anonimi | CC BY 4.0 |

### Zenodo 18986229: la stagione di un club

Il dataset accompagna l'articolo di Sierra-Casas et al. (2026). Raccoglie i dati GPS (STATSports Viper a 10 Hz, con accelerometro a 100 Hz) di una squadra arrivata tra le prime quattro del suo campionato: 2.375 righe, 20 giocatori di movimento, 151 giorni di seduta dal 10/09/2023 al 10/05/2024, cioè 121 allenamenti e 30 partite. Ogni riga indica il giorno rispetto alla partita, da MD-5 (cinque giorni prima) a MD+2 (due giorni dopo), e lo stato di titolare. Le misure sono le **sei più usate per il carico esterno**:

| Sigla | Misura | Definizione |
|---|---|---|
| TD | Distanza totale | metri percorsi |
| HSR | Corsa ad alta velocità | metri sopra 19,8 km/h, sprint compreso |
| SPR | Sprint | metri sopra 25,2 km/h |
| ACC, DCC | Accelerazioni e decelerazioni intense | numero di eventi sopra 3 m/s² e sotto −3 m/s² |
| HMLD | Distanza ad alto carico metabolico | metri con potenza metabolica sopra 25,5 W/kg |

*Soglie dal testo dell'articolo (§5.3.1). Il riscaldamento è compreso negli allenamenti ed escluso dalle partite.*

Nella demo i codici anonimi dei giocatori diventano nomi italiani di fantasia, così come la squadra è di fantasia e si chiama AS New Trieste. 
Vice rivive la stagione giorno per giorno: **di ogni giorno conosce solo i dati precedenti**, mentre il calendario delle partite è noto in anticipo, come nella realtà. 
La seduta del giorno della demo arriva solo caricando l'export csv della sessione di allenamento di quel giorno. 

Il dataset è stato verificato prima di essere utilizzato: 

- **Le tabelle dell'articolo si riproducono dai dati.** La Tabella 1 è identica (16 celle su 16). Della Tabella 2, distanza totale, sono identiche 74 celle su 80: le 6 diverse sono un refuso dell'articolo, che per i difensori centrali a MD+1, MD+2 e MD-5 scambia titolari e non titolari, come confermano i rapporti del dataset e la Tabella 3 dello stesso articolo.
- **Alcune colonne contengono informazioni dal futuro, e Vice non le usa.** Lo stato di titolare scritto nei giorni prima della partita è, in 55 righe, già la formazione della partita successiva; i rapporti allenamento/partita sono calcolati sulle medie dell'intera stagione. Vice ricava il titolare dall'ultima partita giocata e ricalcola i rapporti col solo passato.
- **Mancano due periodi** (02/12-15/12/2023 e 28/04-07/05/2024), probabilmente le settimane con due partite che gli autori dichiarano di aver escluso. Anche le righe di infortunati e sedute incomplete sono state tolte: per Vice un dato mancante non vale zero, e il motivo dell'assenza non viene ipotizzato.

---
## 9. Riferimenti e crediti

### Dati

- Rodríguez-Fernández A. (2026). *DATASETTMRatiosoccerseasson* [dataset]. Zenodo. DOI 10.5281/zenodo.18986229. Licenza CC BY 4.0. Modifiche di Vice: formato, nomi e numeri di maglia di fantasia, rapporti ricalcolati col solo passato.
- Sierra-Casas A., Castillo D., Clemente F. M., Rodríguez-Fernández A. (2026). Daily and accumulated training-to-match load ratios in professional soccer: the influence of starting status and playing position across a full competitive season. *Data* 11(4), 84. DOI 10.3390/data11040084.

### Letteratura

- Ammann L., Altmann S. (2023). Training and match load ratios in professional soccer: should we use player- or position-specific match reference values? *Frontiers in Sports and Active Living* 5:1151828. DOI 10.3389/fspor.2023.1151828.
- Beato M., Devereux G., Stiff A. (2018). Validity and reliability of Global Positioning System units (STATSports Viper) for measuring distance and peak speed in sports. *Journal of Strength and Conditioning Research* 32(10):2831-2837. DOI 10.1519/JSC.0000000000002778.
- Clemente F. M., Pillitteri G., Palucci Vieira L. H., Rabbani A., Zmijewski P., Beato M. (2024). Balancing the load: a narrative review with methodological implications of compensatory training strategies for non-starting soccer players. *Biology of Sport* 41(4):173-185. DOI 10.5114/biolsport.2024.139071.
- Dello Iacono A., Beato M., Unnithan V., Shushan T. (2023). Programming high-speed and sprint running exposure in football: beliefs and practices of more than 100 practitioners worldwide. *International Journal of Sports Physiology and Performance* 18(7):742-757. DOI 10.1123/ijspp.2023-0013.
- Gualtieri A., Rampinini E., Dello Iacono A., Beato M. (2023). High-speed running and sprinting in professional adult soccer: current thresholds definition, match demands and training strategies. A systematic review. *Frontiers in Sports and Active Living* 5:1116293. DOI 10.3389/fspor.2023.1116293.
- Hopkins W. G. (2000). Measures of reliability in sports medicine and science. *Sports Medicine* 30(1):1-15. DOI 10.2165/00007256-200030010-00001.
- Impellizzeri F. M., Marcora S. M., Coutts A. J. (2019). Internal and external training load: 15 years on. *International Journal of Sports Physiology and Performance* 14(2):270-273. DOI 10.1123/ijspp.2018-0935.
- Impellizzeri F. M., Tenan M. S., Kempton T., Novak A., Coutts A. J. (2020). Acute:chronic workload ratio: conceptual issues and fundamental pitfalls. *International Journal of Sports Physiology and Performance* 15(6):907-913. DOI 10.1123/ijspp.2019-0864.
- Varley M. C., Jaspers A., Helsen W. F., Malone J. J. (2017). Methodological considerations when quantifying high-intensity efforts in team sport using Global Positioning System technology. *International Journal of Sports Physiology and Performance* 12(8):1059-1068. DOI 10.1123/ijspp.2016-0534.

### Software e modelli

- Python con FastAPI, Uvicorn, pandas, NumPy, PyArrow, httpx e Jinja2; 
- Apache ECharts 5.6.0 per i grafici; font Newsreader e Schibsted Grotesk (SIL Open Font License). 
- Modelli: Claude Sonnet 5 e, come riserva, Claude Sonnet 4.6 di Anthropic, attraverso il gateway Hydrogen di HTX su AWS Bedrock in Unione Europea. Il codice, con test e documentazione, è nel repository pubblico https://github.com/htxsrl/Vice-FootballDataShowCase.

Nomi dei giocatori e della squadra di fantasia; dati reali anonimi del dataset Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0). 
