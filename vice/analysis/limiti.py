"""M2.11 Limiti: cosa i dati non permettono di dire, perché, e cosa si può dire invece.

Serve ai "non lo so" dell'agente (M3.9) e alla sezione limiti dei report e del PDF. Di Zenodo si
dichiara il limite funzionale (decisione 22: mancano durate, velocità massima e RPE) e la non
trasferibilità delle fasce come proprietà del metodo (decisione 29). Gli altri limiti vengono dalla
revisione tecnica del 22/10/2026 (decisione 30).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .evidenze import Risultato


@dataclass(frozen=True)
class Limite:
    id: str
    titolo: str
    perche: str
    invece: str
    parole: tuple[str, ...]        # per riconoscere la domanda (in minuscolo)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("parole")
        return d


LIMITI = (
    Limite("rischio_infortuni", "Non stimo il rischio di infortunio",
           "Con i soli carichi esterni di una squadra non c'è un modo difendibile di prevederlo. L'ACWR (carico acuto "
           "su cronico), il più usato, è criticato in letteratura (Impellizzeri et al. 2020) e l'articolo stesso del "
           "dataset dice di non usarlo.",
           "Posso dirti chi è fuori dalla sua fascia storica, da quante sedute, e com'è andato il carico postpartita.",
           ("infortun", "acwr", "acuto", "cronico", "rischio", "si fa male", "lesion")),
    Limite("carico_interno", "Non misuro il carico interno",
           "Nei dati non ci sono RPE né frequenza cardiaca: solo il carico esterno misurato dal GPS.",
           "Posso descrivere il carico esterno: distanze, alta velocità, sprint, accelerazioni, decelerazioni, HMLD.",
           ("rpe", "fatica percepita", "frequenza cardiaca", "carico interno", "stanc", "affaticat", "wellness")),
    Limite("intensita_al_minuto", "Non calcolo l'intensità al minuto degli allenamenti",
           "Il dataset non ha la durata delle sedute né i minuti giocati.",
           "Posso confrontare i volumi della seduta con quelli abituali per quel giorno della settimana.",
           ("al minuto", "m/min", "metri al minuto", "durata", "densità", "intensità della seduta")),
    Limite("velocita_massima", "Non ho la velocità massima",
           "Il dataset non riporta la velocità di picco, quindi lo sprint è assoluto (sopra i 25,2 km/h) e non dice "
           "quanto un giocatore si avvicina alla sua velocità massima (Gualtieri et al. 2023).",
           "Posso dirti quanti metri ha registrato sopra i 25,2 km/h (sprint) e sopra i 19,8 km/h (HSR).",
           ("velocità massima", "velocità di picco", "top speed", "vmax", "più veloce", "velocità personale")),
    Limite("minuti_giocati", "Non conosco i minuti giocati",
           "Il dataset dice solo chi è partito titolare; un non titolare può essere entrato presto, un titolare uscito "
           "presto. Per questo il riferimento di partita è la media dei carichi osservati da titolare, non il carico di "
           "una partita intera.",
           "Il carico della partita lo leggo dai valori registrati, non dallo stato di titolare.",
           ("minuti giocati", "quanti minuti", "minutaggio", "sostituz", "è entrato", "90 minuti")),
    Limite("dati_mancanti", "Non so perché un dato manca",
           "Le righe dei giocatori infortunati, in rientro o con sedute non completate sono state tolte dal dataset "
           "senza indicare il motivo: «nessun dato» non vuol dire riposo né zero lavoro.",
           "Ti dico dove mancano i dati e confronto solo i giorni con dati.",
           ("assente", "assenza", "perché non", "non c'era", "manca", "infortunato", "dati mancanti")),
    Limite("periodi_senza_dati", "Ci sono periodi senza dati",
           "Mancano dal 02/12 al 15/12/2023 e dal 28/04 al 07/05/2024: con ogni probabilità sono le settimane con "
           "due partite, che gli autori dichiarano di aver escluso. A fine dicembre c'è la pausa invernale.",
           "Le settimane irregolari non entrano nei confronti col solito; le altre sì.",
           ("dicembre", "pausa", "buco", "periodo senza", "settimana con due partite", "infrasettimanale")),
    Limite("palestra", "Non vedo tutto il lavoro",
           "Il dataset non contiene le sedute in palestra (due a settimana secondo l'articolo) né il lavoro fuori "
           "dalle righe registrate.",
           "Descrivo il carico registrato in campo dal GPS.",
           ("palestra", "forza", "pesi", "lavoro individuale", "tutto il lavoro")),
    Limite("storico_non_programma", "La fascia è il carico abituale, non l'obiettivo",
           "Vice non conosce il programma della seduta: una seduta fuori fascia può essere esattamente quella prevista.",
           "Ti dico se il carico registrato è abituale per quel giorno; se era previsto lo sa lo staff.",
           ("obiettivo", "previsto", "programma", "ottimale", "giusto", "ideale")),
    Limite("soglie_operative", "Le soglie sono operative, non validate",
           "Percentili, tolleranze e regole degli spunti sono scelte dichiarate e provate con analisi di sensibilità: "
           "non sono soglie fisiologiche né stime dell'errore del GPS, e la loro utilità per lo staff non è ancora "
           "misurata. Le regole sono state riviste conoscendo l'intera stagione: i calcoli usano solo il passato, ma "
           "la verifica è retrospettiva.",
           "Ogni spunto mostra i numeri da cui nasce, e l'elenco completo dei candidati è consultabile.",
           ("soglia", "soglie", "affidabil", "validat", "falsi allarmi", "quanto è preciso")),
    Limite("incertezza_fasce", "Le fasce hanno un'incertezza",
           "Vengono da osservazioni ripetute degli stessi giocatori e da sedute condivise: il numero di casi non "
           "equivale a informazione indipendente. Una sola squadra e da tre a cinque giocatori per ruolo.",
           "Dichiaro sempre casi, sedute diverse e se una fascia è provvisoria (meno di 6 sedute): da quelle non nascono spunti.",
           ("incertezza", "quanti casi", "campione", "statistic", "significativ")),
    Limite("trasferibilita", "Le fasce non si trasferiscono ad altri club",
           "Le fasce si costruiscono sullo storico di ogni squadra: sono il suo carico abituale, non soglie generali.",
           "Con i dati di un altro club, Vice costruisce le fasce di quel club.",
           ("altri club", "altra squadra", "generalizz", "trasferib", "valori di riferimento", "norme")),
    Limite("indicatori_derivati", "ACC, DCC e HMLD sono indicatori derivati",
           "Sono conteggi di eventi oltre ±3 m/s² e una stima della potenza metabolica: non misurano fatica, danno "
           "muscolare o costo metabolico reale.",
           "Li descrivo come conteggi e distanze registrate, accanto alle altre metriche.",
           ("accelerazion", "decelerazion", "hmld", "metabolic", "meccanico", "danno muscolare")),
    Limite("giudizio", "Non giudico se un giocatore è andato meglio o peggio",
           "Un carico sopra la fascia non è un merito e uno sotto non è una colpa: dipende dal programma dello staff.",
           "Ti dico se il carico è dentro, sopra o sotto quello abituale per quel giorno, e di quanto.",
           ("meglio", "peggio", "migliore", "peggiore", "bravo", "scarso", "chi ha corso di più", "classifica")),
    Limite("prescrizioni", "Non prescrivo allenamenti",
           "Le decisioni restano allo staff. Le analisi non dicono se uno stimolo è sufficiente o se un giocatore ha "
           "recuperato.",
           "Propongo al massimo tre spunti da valutare, ognuno con i numeri da cui nasce.",
           ("cosa deve fare", "prescriv", "che esercizi", "quanto deve correre", "sufficiente", "recuperato")),
)

AVVERTENZA_RAPPORTO = ("Nel rapporto allenamento/partita gli allenamenti comprendono il riscaldamento e le partite no, "
                       "quindi il rapporto è un po' generoso con l'allenamento.")


def limiti(domanda: str | None = None) -> Risultato:
    """Tutti i limiti, o quelli che riguardano la domanda (per parole chiave)."""
    scelti = LIMITI
    if domanda:
        d = domanda.lower()
        scelti = tuple(x for x in LIMITI if any(p in d for p in x.parole)) or LIMITI
    tab = pd.DataFrame([x.to_dict() for x in scelti])
    return Risultato("limiti", pd.Timestamp.now().normalize(), tab, [], [AVVERTENZA_RAPPORTO],
                     {"limiti": [x.id for x in scelti], "filtrati": bool(domanda) and len(scelti) < len(LIMITI)})
