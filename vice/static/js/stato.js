// Lo stato condiviso tra chat e lavagna (decisione 47): Vice ragiona sempre dall'oggi della demo; il giorno
// in esame è quello della conversazione aperta, scelto dal calendario. La seduta di oggi arriva col file
// (decisione 54): il suo caricamento vale per tutte le richieste e resta salvato nel browser; un file di un
// giorno passato vale per quel giorno.
export const stato = {
  oggi: null,              // "AAAA-MM-GG": il giorno della demo, l'ultimo che Vice conosce
  giorno: null,            // il giorno in esame: le domande senza data riguardano questo giorno
  caricamenti: {},         // giorno → {caricamento, data, ...} dell'export caricato per quel giorno
  reportPronti: new Set(), // i giorni con un report pronto sul server (decisione 49)
  sigle: null,             // sigla → significati, per il grassetto nelle risposte (decisione 52)
};

const CHIAVE = "vice-seduta-di-oggi-v1";

/** Il file del giorno in esame, se c'è; altrimenti quello di oggi (che vale anche per i confronti con oggi). */
const fileDaUsare = () => (stato.caricamenti[stato.giorno] || stato.caricamenti[stato.oggi])?.caricamento || null;

export const sedutaDiOggiCaricata = () => Boolean(stato.caricamenti[stato.oggi]);

export function salvaCaricamento(j) {
  stato.caricamenti[j.data] = j;
  if (j.data !== stato.oggi) return;
  try { localStorage.setItem(CHIAVE, JSON.stringify(j)); } catch { /* il browser non salva: vale per questa visita */ }
}

export function togliCaricamento(giorno) {
  delete stato.caricamenti[giorno];
  if (giorno !== stato.oggi) return;
  try { localStorage.removeItem(CHIAVE); } catch { /* niente da togliere */ }
}

/** Il server non ha più quel file (lo tiene due ore): si toglie. Restituisce vero se c'era. */
export function fileScaduto(codice) {
  const giorno = Object.keys(stato.caricamenti).find((g) => stato.caricamenti[g].caricamento === codice);
  if (!giorno) return false;
  togliCaricamento(giorno);
  return true;
}

/** Il caricamento di oggi salvato nel browser, se è proprio di oggi. */
export function caricamentoSalvato() {
  try {
    const j = JSON.parse(localStorage.getItem(CHIAVE));
    return j && j.data === stato.oggi ? j : null;
  } catch { return null; }
}

/** I campi comuni alle richieste di chat e lavagna. */
export function contestoRichiesta() {
  const c = fileDaUsare();
  return { oggi: stato.oggi, ...(stato.giorno && stato.giorno !== stato.oggi ? { giorno: stato.giorno } : {}), ...(c ? { caricamento: c } : {}) };
}

/** Il report di un giorno si scrive come quel giorno: l'oggi del report è il giorno in esame. */
export function contestoReport() {
  const g = stato.giorno || stato.oggi;
  const c = stato.caricamenti[g]?.caricamento;
  return { oggi: g, ...(c ? { caricamento: c } : {}) };
}
