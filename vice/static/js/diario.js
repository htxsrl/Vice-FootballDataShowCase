// Le conversazioni (decisioni 41, 43 e 47): ognuna ha il suo giorno in esame, il suo titolo (la prima domanda)
// e i suoi messaggi; una nuova non cancella le vecchie e non c'è un limite di giorni. Stanno nel browser di chi
// usa Vice: se il browser non permette il salvataggio, la chat funziona lo stesso. Il pannello «Conversazioni»
// è solo l'elenco; i giorni si scelgono dal calendario (calendario.js).
import { $, crea, dataBreve, emetti, giornoSettimana } from "./util.js";

const CHIAVE = "vice-conversazioni-v1";
const VECCHIA = "vice-diario-v1";        // una conversazione per giorno (23/10/2026)

function leggiTutto() {
  let d = {};
  try { d = JSON.parse(localStorage.getItem(CHIAVE)) || {}; } catch { d = {}; }
  return migra(d);
}

function scriviTutto(d) {
  try {
    localStorage.setItem(CHIAVE, JSON.stringify(d));
    return true;
  } catch {
    emetti("memoria-piena");
    return false;
  }
}

// le conversazioni della versione precedente (una per giorno) diventano conversazioni dell'elenco
function migra(d) {
  let vecchie = null;
  try { vecchie = JSON.parse(localStorage.getItem(VECCHIA)); } catch { vecchie = null; }
  if (!vecchie) return d;
  for (const [giorno, c] of Object.entries(vecchie)) {
    if (!c?.messaggi?.length) continue;
    const id = `g${giorno.replaceAll("-", "")}`;
    if (!d[id]) d[id] = { id, giorno, titolo: titoloDi(c.messaggi), messaggi: c.messaggi, storia: c.storia || [], creata: c.aggiornato || Date.now(), aggiornata: c.aggiornato || Date.now() };
  }
  if (scriviTutto(d)) { try { localStorage.removeItem(VECCHIA); } catch { /* resta: si rileggerà */ } }
  return d;
}

/** Il titolo di una conversazione: la prima domanda, il titolo del primo report o il file caricato. */
export function titoloDi(messaggi) {
  const primo = messaggi.find((m) => m.tipo === "utente" || m.tipo === "report") || messaggi.find((m) => m.tipo === "nota");
  if (!primo) return "Conversazione";
  const t = primo.tipo === "report" ? primo.titolo : primo.testo;
  return t.length > 70 ? `${t.slice(0, 68)}…` : t;
}

export const nuovoId = () => `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
export const leggi = (id) => leggiTutto()[id] || null;

export function salva(conv) {
  const d = leggiTutto();
  const ora = Date.now();
  d[conv.id] = { ...conv, titolo: conv.titolo || titoloDi(conv.messaggi), creata: d[conv.id]?.creata || ora, aggiornata: ora };
  scriviTutto(d);
  disegnaElenco();
}

const conReport = (c) => c.messaggi?.some((m) => m.tipo === "report" && m.testo);

/** La conversazione più recente di quel giorno che contiene un report: il calendario la riapre. */
export function conversazioneDelGiorno(giorno) {
  return Object.values(leggiTutto()).filter((c) => c.giorno === giorno && conReport(c))
    .sort((a, b) => (b.aggiornata || 0) - (a.aggiornata || 0))[0] || null;
}

/** I giorni con un report salvato in questo browser (per esempio da un export caricato). */
export const giorniConReport = () => new Set(Object.values(leggiTutto()).filter(conReport).map((c) => c.giorno));

export function elimina(id) {
  const d = leggiTutto();
  delete d[id];
  scriviTutto(d);
  disegnaElenco();
}

// ---------- il pannello ----------
let sedute = [];          // [{data, tipo, md}] fino al giorno della demo
let oggiDemo = null;
let aperta = null;        // id della conversazione aperta

export function impostaSedute(calendario, giornoDemo) {
  sedute = calendario;
  oggiDemo = giornoDemo;
  disegnaElenco();
}

export function segnaAperta(id) {
  aperta = id;
  disegnaElenco();
}

const mdDi = (giorno) => sedute.find((s) => s.data === giorno);
const etichettaGiorno = (giorno) => {
  const s = mdDi(giorno);
  const md = s ? (s.tipo === "partita" ? "partita" : s.md) : "";
  return `${giornoSettimana(giorno).slice(0, 3)} ${dataBreve(giorno)}${md ? `, ${md}` : ""}`;
};

function disegnaElenco() {
  const el = $("#diario-elenco");
  if (!el) return;
  el.replaceChildren();
  // le conversazioni, dalla più recente
  const tutte = Object.values(leggiTutto()).sort((a, b) => (b.aggiornata || 0) - (a.aggiornata || 0));
  const lista = crea("ul", { class: "conversazioni" });
  for (const c of tutte) {
    const domande = c.messaggi.filter((m) => m.tipo === "utente").length;
    const report = c.messaggi.filter((m) => m.tipo === "report").length;
    const conteggio = [report ? `${report === 1 ? "un report" : `${report} report`}` : null,
      domande ? `${domande} ${domande === 1 ? "domanda" : "domande"}` : null].filter(Boolean).join(", ") || "nessuna domanda";
    lista.append(crea("li", {}, crea("button", {
      type: "button", class: "conversazione", "aria-current": String(c.id === aperta),
      onclick: () => emetti("apri-conversazione", c.id),
    },
    crea("span", { class: "conv-titolo", testo: c.titolo || titoloDi(c.messaggi) }),
    crea("span", { class: "conv-sotto", testo: `${etichettaGiorno(c.giorno)}${c.giorno === oggiDemo ? " (oggi)" : ""}, ${conteggio}` }))));
  }
  el.append(crea("section", {}, crea("h3", { testo: "Le tue conversazioni" }),
    tutte.length ? lista : crea("p", { class: "vuoto", testo: "Ancora nessuna: la prima domanda ne crea una." })));
}

export function avviaDiario() {
  const pannello = $("#diario"), velo = $("#velo"), apri = $("#apri-giorni");
  const mostra = (si) => {
    if (pannello.hidden === !si) return;
    if (si) emetti("pannello", "conversazioni");   // si chiude il calendario, se è aperto
    pannello.hidden = !si; velo.hidden = !si;
    apri.setAttribute("aria-expanded", String(si));
  };
  apri.addEventListener("click", () => mostra(pannello.hidden));
  $("#chiudi-giorni").addEventListener("click", () => mostra(false));
  velo.addEventListener("click", () => mostra(false));
  $("#nuova-oggi").addEventListener("click", () => { mostra(false); emetti("nuova-conversazione", oggiDemo); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") mostra(false); });
  return { chiudi: () => mostra(false) };
}
