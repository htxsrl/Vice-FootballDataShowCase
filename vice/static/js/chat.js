// La chat con Vice: domanda → eventi SSE (tappa, delta, vista, verifica, done, error) → risposta verificata
// con le citazioni cliccabili [E3] che accendono la prova sulla lavagna (M4.1, M4.5). Gli stessi eventi
// arrivano dai report (M4.8), uno solo per il preparatore (decisione 51), che cominciano con gli avvisi di Vice
// (evento `avvisi`, decisione 54). Ogni conversazione ha il suo giorno e resta salvata nell'elenco (decisioni 41
// e 43). All'apertura di oggi, al posto della presentazione, quello che resta da guardare.
import { $, ascolta, crea, dataBreve, dataLunga, emetti, escapeHtml, eventiSSE, giornoSettimana, rigaTip, secondi } from "./util.js";
import { contestoReport, contestoRichiesta, fileScaduto, sedutaDiOggiCaricata, stato } from "./stato.js";
import { daGuardare, mettiDato, punto, riquadroReport } from "./avvisi.js";
import { accendiEvidenza, mostra, togliSelezione } from "./lavagna.js";
import * as diario from "./diario.js";

let conv = { id: null, giorno: null, titolo: null, messaggi: [], storia: [] };   // la conversazione aperta
let occupato = false;
let lavagna = null;         // ciò che l'utente guarda sulla lavagna (giocatore scelto, vista)
let citaAccesa = null;

const scorri = () => { const m = $("#messaggi"); m.scrollTop = m.scrollHeight; };
// un report si legge dall'inizio: la chat si ferma sul suo titolo, con gli avvisi in testa (decisione 54)
const allInizio = (msg) => { const m = $("#messaggi"); m.scrollTop += msg.getBoundingClientRect().top - m.getBoundingClientRect().top - 12; };
const salva = () => {
  if (!conv.id || !conv.messaggi.length) return;   // una conversazione vuota non entra nell'elenco
  // il titolo si fissa alla prima domanda o al primo report, non alla nota del file caricato
  if (!conv.titolo && conv.messaggi.some((m) => m.tipo === "utente" || m.tipo === "report")) conv.titolo = diario.titoloDi(conv.messaggi);
  diario.salva(conv);
  emetti("conversazione-salvata", conv.id);
};
export const conversazioneAperta = () => conv;
export const inCorso = () => occupato;

export function impostaLavagna(sel) {
  lavagna = sel;
  const box = $("#contesto-lavagna");
  if (!sel) { box.hidden = true; return; }
  $("#contesto-testo").textContent = `Stai guardando ${sel.giocatore.nome}`;
  box.hidden = false;
}

// ---------- testo con citazioni ----------
function espandi(gruppo) {
  const out = [];
  for (const pezzo of gruppo.split(/\s*[,;]\s*/)) {
    const m = /^([ED])(\d+)\s*[-–]\s*[ED]?(\d+)$/.exec(pezzo);
    if (m) { for (let i = Number(m[2]); i <= Number(m[3]) && out.length < 30; i++) out.push(`${m[1]}${i}`); }
    else if (/^[ED]\d+$/.test(pezzo)) out.push(pezzo);
  }
  return out;
}

// le sigle in grassetto, col loro significato quando c'è accanto (decisione 52); le regole si costruiscono
// una volta sola dalle sigle del server (vice/agent/sigle.py), le stesse del glossario
const escRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
let regoleSigle = null;
function regole() {
  if (regoleSigle || !stato.sigle) return regoleSigle;
  const sigle = Object.keys(stato.sigle).sort((a, b) => b.length - a.length).map(escRe).join("|");
  const sig = [...new Set(Object.values(stato.sigle).flat())].sort((a, b) => b.length - a.length)
    .map((t) => `[${t[0].toUpperCase()}${t[0]}]${escRe(t.slice(1))}`).join("|");
  regoleSigle = {
    prima: new RegExp(`(${sig}) \\((${sigle})\\)`, "g"),               // «distanza totale (TD)»
    dopo: new RegExp(`(?<![\\w-])(${sigle}) \\((${sig})\\)`, "g"),      // «TD (distanza totale)»
    dentro: new RegExp(`\\((${sigle}), (${sig})\\)`, "g"),             // «(MD-2, due giorni prima della partita)»
    sola: new RegExp(`(?<![\\w-])(${sigle})(?![\\w+-])`, "g"),
  };
  return regoleSigle;
}
const SIGLA_SEGNATA = /(<strong class="sigla">.*?<\/strong>)/;
function segnaSigle(h) {
  const r = regole();
  if (!r) return h;
  const t = h.replace(r.prima, '<strong class="sigla">$1 ($2)</strong>')
    .replace(r.dopo, '<strong class="sigla">$1 ($2)</strong>')
    .replace(r.dentro, '(<strong class="sigla">$1, $2</strong>)');
  return t.split(SIGLA_SEGNATA).map((pezzo, i) => (i % 2 ? pezzo : pezzo.replace(r.sola, '<strong class="sigla">$1</strong>'))).join("");
}

function inLinea(riga) {
  const h = segnaSigle(escapeHtml(riga)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])[*_](?!\s)(.+?)[*_](?=[\s).,;:!?]|$)/g, "$1<em>$2</em>"));
  return h.replace(/\[((?:[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)(?:\s*[,;]\s*[ED]\d+(?:\s*[-–]\s*[ED]?\d+)?)*)\]/g, (_, g) => {
    const tutte = espandi(g);
    // in un gruppo la lettera si scrive solo quando cambia: [E2|3|4|D1]
    const pezzi = tutte.map((e, i) => {
      const testo = i && e[0] === tutte[i - 1][0] ? e.slice(1) : e;
      return `<span class="cita${e.startsWith("D") ? " definizione" : ""}" data-e="${e}">${testo}</span>`;
    }).join("");
    return tutte.length > 1 ? `<span class="cita-gruppo">${pezzi}</span>` : pezzi;
  });
}

// «Lorenzo Cortese: HSR 658 m…»: il nome all'inizio di una voce d'elenco va in grassetto (niente cifre, poche parole)
function voceConEtichetta(t) {
  const m = /^([^:*[\]\d]{2,60}):\s+(\S.*)$/.exec(t);
  return m && m[1].trim().split(/\s+/).length <= 7 ? `**${m[1].trim()}:** ${m[2]}` : t;
}

// Markdown minimo, riga per riga: titoli (##, ###, o una riga tutta in grassetto), elenchi, paragrafi; le righe
// "---" separano soltanto. L'elenco sotto «Spunti per lo staff» va in un riquadro.
function html(testo) {
  const out = [];
  let par = [], lista = [], sezione = "";
  const chiudiPar = () => { if (par.length) out.push(`<p>${par.join("<br>")}</p>`); par = []; };
  const chiudiLista = () => {
    if (lista.length) out.push(`<ul${/spunti/i.test(sezione) ? ' class="spunti"' : ""}>${lista.map((x) => `<li>${x}</li>`).join("")}</ul>`);
    lista = [];
  };
  const chiudi = () => { chiudiPar(); chiudiLista(); };
  for (const grezza of testo.split("\n")) {
    const r = grezza.trim();
    if (!r || /^([-*_]\s*){3,}$/.test(r)) { chiudi(); continue; }
    const titolo = /^(#{1,6})\s+(.+)$/.exec(r);
    if (titolo) {
      chiudi();
      sezione = titolo[2];
      out.push(titolo[1].length <= 2 ? `<h4>${inLinea(titolo[2])}</h4>` : `<h5>${inLinea(titolo[2])}</h5>`);
      continue;
    }
    const grassetto = /^\*\*([^*]+)\*\*:?$/.exec(r);
    if (grassetto) { chiudi(); sezione = grassetto[1]; out.push(`<h5>${inLinea(grassetto[1])}</h5>`); continue; }
    const voce = /^[-*•]\s+(.+)$/.exec(r);
    if (voce) { chiudiPar(); lista.push(inLinea(voceConEtichetta(voce[1]))); continue; }
    chiudiLista();
    par.push(inLinea(r));
  }
  chiudi();
  return out.join("");
}

const esc = (t) => escapeHtml(String(t ?? ""));

function attivaCitazioni(voce, evidenze, definizioni) {
  voce.querySelectorAll("span.cita").forEach((span) => {
    const e = span.dataset.e;
    const ev = evidenze?.[e];
    if (e.startsWith("D")) {
      // il suggerimento con lo stesso stile dei grafici (suggerimenti.js), non quello del browser
      span.dataset.tip = `<div class="tip"><strong>Definizione ${e}</strong>${esc(definizioni?.[e] || "Definizione fissa di Vice")}</div>`;
      span.tabIndex = 0;
      return;
    }
    if (!ev) return;
    const b = crea("button", { type: "button", class: "cita", "data-e": e, "aria-pressed": "false",
      "aria-label": `${e}: ${ev.etichetta}, ${ev.valore_testo ?? ev.valore}`,
      dataset: { tip: `<div class="tip"><strong>${e}</strong><span class="val">${esc(ev.valore_testo ?? ev.valore)}</span><br>${rigaTip(ev.etichetta)}`
        + `<br><span class="nota">clicca per vederlo sulla lavagna</span></div>` } }, span.textContent);
    b.addEventListener("click", () => {
      const spegni = citaAccesa === b;
      spegniCitazioni();
      citaAccesa = spegni ? null : b;
      if (!spegni) b.setAttribute("aria-pressed", "true");
      accendiEvidenza(spegni ? null : { ...ev, etichetta_citazione: e });
    });
    span.replaceWith(b);
  });
}

function spegniCitazioni() {
  document.querySelectorAll("button.cita[aria-pressed=true]").forEach((x) => x.setAttribute("aria-pressed", "false"));
  citaAccesa = null;
}

// ---------- disegno dei messaggi ----------
function disegnaUtente(testo) {
  $("#messaggi").append(crea("div", { class: "msg utente", testo }));
}

function disegnaNota(testo) {
  $("#messaggi").append(crea("p", { class: "nota-chat", testo }));
}

/** Contenuto finale di un messaggio di Vice (anche da una conversazione salvata). */
function riempi(msg, r) {
  msg.querySelectorAll(".tappe, .voce, footer").forEach((x) => x.remove());
  const voce = crea("div", { class: "voce" });
  voce.innerHTML = html(r.testo || "");
  attivaCitazioni(voce, r.evidenze, r.definizioni);
  msg.append(voce, piede(r));
  if (r.avvisi) mettiDato(voce, mettiRiquadro(msg, r.avvisi, false), r.avvisi);
}

/** Il riquadro «Da guardare» in testa a un report (decisione 54): sotto il titolo, prima del testo del modello. */
function mettiRiquadro(msg, dati, rifai = true) {
  let box = msg.querySelector(".da-guardare");
  if (box && !rifai) return box;
  box?.remove();
  box = riquadroReport(dati);
  const titolo = msg.querySelector(".report-titolo");
  if (titolo) titolo.after(box); else msg.prepend(box);
  return box;
}

function piede(r) {
  const f = crea("footer", { class: "verifica" });
  if (r.esito) {
    const n = r.esito.frasi_con_numeri, ok = r.esito.verificate, tolte = (r.esito.tolte || []).length;
    // frasi controllate: con numeri o con un giudizio («sopra la fascia», «oggi») da confrontare coi dati
    let testo = n === 0 ? "Nessun numero né giudizio da verificare" : `${ok} ${ok === 1 ? "frase" : "frasi"} su ${n} verificate sui dati`;
    if (tolte) testo += `; ${tolte} ${tolte === 1 ? "frase tolta perché non verificabile" : "frasi tolte perché non verificabili"}`;
    const segno = crea("span", { class: "segno", "aria-hidden": "true" });
    segno.innerHTML = '<svg viewBox="0 0 16 16"><path d="M6.2 11.4 2.8 8l1-1 2.4 2.4 6-6 1 1z"/></svg>';
    f.append(segno, crea("span", { class: "esito", testo }));
  }
  if (r.ms) f.append(crea("span", { class: "tempo", title: r.modello ? `modello ${r.modello}` : null, testo: `in ${secondi(r.ms)} s` }));
  const azioni = crea("span", { class: "azioni" });
  if (r.vista) azioni.append(crea("button", { type: "button", class: "mostra-vista", onclick: () => mostra(r.vista) }, "Mostra sulla lavagna"));
  f.append(azioni);
  return f;
}

// ---------- un turno: chat o report ----------
async function turno(url, corpo, msg, contesto = contestoRichiesta) {
  const segui = msg.classList.contains("report") ? () => allInizio(msg) : scorri;
  const tappe = crea("ul", { class: "tappe", "aria-label": "Cosa sta facendo Vice" });
  const voce = crea("div", { class: "voce in-arrivo" });
  msg.querySelectorAll(".tappe, .voce, footer").forEach((x) => x.remove());
  msg.classList.remove("errore");
  msg.append(tappe, voce);
  segui();
  const r = { testo: "", evidenze: {}, definizioni: {}, esito: null, vista: null, ms: 0, modello: null, avvisi: null };
  const inizio = performance.now();
  const tappa = (t) => {
    tappe.querySelectorAll("li.attiva").forEach((li) => { li.classList.remove("attiva"); li.classList.add("fatta"); });
    tappe.append(crea("li", { class: "attiva", testo: `${t}…` }));
    segui();
  };
  tappa("leggo la richiesta");
  let codiceFile = null;   // il file usato: se il server non l'ha più, si toglie (catch)
  try {
    const ctx = contesto();
    codiceFile = ctx.caricamento;
    const risp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...corpo, ...ctx }) });
    if (!risp.ok || !risp.body) {
      let dettaglio = "";
      try { dettaglio = (await risp.json()).detail; } catch { /* corpo non JSON */ }
      throw new Error(typeof dettaglio === "string" && dettaglio ? dettaglio : `HTTP ${risp.status}`);
    }
    for await (const { evento, dati } of eventiSSE(risp)) {
      if (evento === "avvisi") { r.avvisi = dati; mettiRiquadro(msg, dati); segui(); }
      else if (evento === "tappa") tappa(dati.testo);
      else if (evento === "delta") { r.testo += dati.text; voce.innerHTML = html(r.testo); segui(); }
      else if (evento === "ricomincia") r.testo = "";
      else if (evento === "vista") { r.vista = { vista: dati.vista, parametri: dati.parametri || {} }; mostra(r.vista); }
      else if (evento === "verifica") {
        const { testo, evidenze, definizioni, ...esito } = dati;
        Object.assign(r, { testo, evidenze: evidenze || {}, definizioni: definizioni || {}, esito });
      }
      else if (evento === "done") r.modello = dati.modello;
      else if (evento === "error") throw new Error(dati.message);
    }
    r.ms = performance.now() - inizio;
    riempi(msg, r);
    return r;
  } catch (e) {
    if (codiceFile && /ricaricalo/.test(e.message || "") && fileScaduto(codiceFile)) emetti("file-scaduto");
    msg.classList.add("errore");
    tappe.remove();
    voce.classList.remove("in-arrivo");
    voce.textContent = e.message && !/^HTTP|fetch/i.test(e.message) ? e.message : "Non riesco a raggiungere Vice. Riprova tra poco.";
    return null;
  } finally {
    segui();
  }
}

function blocca(si) {
  occupato = si;
  $("#invia").disabled = si;
}

function togliBenvenuto() {
  $("#messaggi .benvenuto")?.remove();
}

export function nota(testo) {
  togliBenvenuto();
  disegnaNota(testo);
  conv.messaggi.push({ tipo: "nota", testo });
  salva();
  scorri();
}

export async function invia(testo) {
  testo = testo.trim();
  if (!testo || occupato) return;
  blocca(true);
  togliBenvenuto();
  disegnaUtente(testo);
  conv.messaggi.push({ tipo: "utente", testo });
  conv.storia.push({ role: "user", content: testo });
  const msg = crea("article", { class: "msg vice" });
  $("#messaggi").append(msg);
  const r = await turno("/api/chat", {
    messages: conv.storia.slice(-20),
    lavagna: lavagna ? { vista: lavagna.titolo, giocatore: lavagna.giocatore.nome } : null,
  }, msg);
  if (r) {
    conv.storia.push({ role: "assistant", content: r.testo });
    conv.messaggi.push({ tipo: "vice", ...r });
  } else {
    conv.storia.pop();
  }
  salva();
  blocca(false);
}

/** Il messaggio di un report: uno solo, pensato per il preparatore (decisione 51). */
function messaggioReport(rec) {
  const msg = crea("article", { class: "msg vice report" });
  const scrivi = async () => {
    if (occupato) return;
    blocca(true);
    const r = await turno("/api/report", { tipo: rec.rtipo, giocatore: rec.giocatore }, msg, contestoReport);
    if (r) {
      Object.assign(rec, r, { vista: r.vista || rec.vista });
      riempi(msg, rec);   // il piede con «Mostra sulla lavagna» e la vista del report
      conv.storia.push({ role: "user", content: rec.titolo }, { role: "assistant", content: r.testo });
      if (!conv.messaggi.includes(rec)) conv.messaggi.push(rec);
      salva();
    }
    blocca(false);
  };
  msg.append(crea("p", { class: "report-titolo", testo: rec.titolo }));
  return { msg, scrivi };
}

/** Un report (seduta, settimana o giocatore) nella chat. */
export async function report(tipo, { giocatore = null, titolo = null } = {}) {
  if (occupato) return;
  togliBenvenuto();
  const data = stato.giorno;   // il grafico del giorno del report
  const vista = tipo === "seduta" ? { vista: "seduta", parametri: { data } }
    : tipo === "settimana" ? { vista: "curva_settimana", parametri: { data } }
      : { vista: "giocatore", parametri: { giocatore, data } };
  const rec = { tipo: "report", rtipo: tipo, giocatore, titolo: titolo || `Report: ${tipo}`, testo: "", vista };
  const { msg, scrivi } = messaggioReport(rec);
  $("#messaggi").append(msg);
  togliSelezione();
  mostra(vista);
  await scrivi();
}

// ---------- i giorni ----------
/** Il titolo del report di un giorno: seduta o partita. */
export const titoloReport = (giorno, md) => `Report della ${md === "MD" ? "partita" : "seduta"} del ${dataLunga(giorno)}`;

const DOMANDE_PASSATE = ["Chi era fuori fascia quel giorno?", "Confronta quel giorno con oggi"];
const ICONA_DOMANDA = '<path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 2v9h4v1.8L11.3 15H19V6H5Z"/>';
const ICONA_REPORT = '<path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 1.5V8h4.5L14 3.5ZM7 12h10v1.6H7V12Zm0 4h10v1.6H7V16Z"/>';

function benvenuto(info) {
  const t = $("#benvenuto").content.cloneNode(true);
  const quando = `${giornoSettimana(info.oggi)} ${dataLunga(info.oggi)}`;
  const passato = info.oggi !== stato.oggi;
  const pronto = stato.reportPronti.has(info.oggi);
  const caricata = passato || sedutaDiOggiCaricata();
  const daCaricare = !passato && info.seduta_prevista && !caricata;     // decisione 54: la seduta di oggi si carica
  const partita = info.prossima_partita ? ` La prossima partita è ${giornoSettimana(info.prossima_partita)} ${dataLunga(info.prossima_partita).slice(0, 5)}.` : "";
  t.querySelector("[data-campo=oggi]").textContent = passato
    ? `Stai guardando ${quando} (${info.giorno_md}). Le domande senza data riguardano quel giorno; puoi anche confrontarlo con oggi, ${giornoSettimana(stato.oggi)} ${dataLunga(stato.oggi)}.`
    : `Oggi è ${quando} (${info.giorno_md}).${partita}`;
  // oggi, al posto della presentazione lunga, quello che resta da guardare (decisione 54)
  const posto = t.querySelector("[data-campo=punto]");
  if (passato) posto.remove();
  else {
    t.querySelector("[data-campo=presentazione]").remove();
    if (daGuardare().length) t.querySelector("[data-campo=saluto]").textContent += " Ecco cosa resta da guardare.";
    posto.replaceWith(punto());
  }
  const carica = t.querySelector("[data-campo=carica]");
  if (daCaricare) {
    carica.querySelector("[data-azione=prova]").addEventListener("click", () => emetti("usa-file-prova"));
    carica.querySelector("[data-azione=file]").addEventListener("click", () => $("#file-export").click());
    const scarica = carica.querySelector("a");
    scarica.href = `/api/export-prova?data=${info.oggi}`;
    scarica.title = `Le righe del ${dataLunga(info.oggi)} copiate dal CSV del dataset Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0): per provare a modificarlo e ricaricarlo`;
  } else carica.remove();
  const suggerite = t.querySelector(".suggerite");
  const prova = t.querySelector("[data-campo=prova]");
  if (info.seduta_oggi) {
    prova.href = `/api/export-prova?data=${info.oggi}`;
    prova.title = `Le righe del ${dataLunga(info.oggi)} copiate dal CSV del dataset Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0)`;
    if (passato) prova.textContent = `Scarica le righe del ${dataBreve(info.oggi)} dal file di Zenodo, poi trascinale qui`;
  } else prova.remove();
  const bottoneReport = suggerite.querySelector("[data-report]");
  if (pronto || (!passato && info.seduta_oggi)) {
    if (passato) bottoneReport.textContent = `Il report del ${dataBreve(info.oggi)}`;
  } else bottoneReport.remove();
  if (daCaricare) suggerite.querySelectorAll("[data-oggi]").forEach((b) => b.remove());   // senza la seduta di oggi
  const domande = t.querySelector(".domande");
  if (passato) {
    suggerite.querySelectorAll("button:not([data-report])").forEach((b) => b.remove());
    if (pronto) for (const d of DOMANDE_PASSATE) suggerite.append(crea("button", { type: "button" }, d));
    else {
      // decisione 49: senza report, l'invito a caricare l'export di quel giorno
      const bottone = crea("button", { type: "button", class: "carica-qui", onclick: () => $("#file-export").click() }, "Carica l'export GPS");
      domande.before(crea("div", { class: "avviso-giorno", role: "status" },
        crea("p", { testo: `Non hai caricato alcun dato per il ${dataLunga(info.oggi)}. Carica l'export GPS di quel giorno per generare il report.` }), bottone));
    }
  }
  // le domande d'esempio come schede, con l'icona: il report col foglio, le domande col fumetto (08/11/2026)
  suggerite.querySelectorAll("button").forEach((b) => {
    const testo = b.textContent;
    b.className = `domanda${b.dataset.report ? " domanda-report" : ""}`;
    b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${b.dataset.report ? ICONA_REPORT : ICONA_DOMANDA}</svg>`;
    b.append(crea("span", { testo }));
  });
  if (!suggerite.querySelector("button")) { suggerite.remove(); domande.querySelector(".domande-titolo").remove(); }
  if (!domande.querySelector("button, a")) domande.remove();
  suggerite.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.report) report(b.dataset.report, { titolo: titoloReport(info.oggi, info.giorno_md) });
    else invia(b.textContent);
  });
  return t;
}

/** Apre una conversazione (nuova o salvata) nel suo giorno. Restituisce l'ultima vista mostrata, se c'è. */
export function apriConversazione(c, info) {
  conv = { id: c.id, giorno: c.giorno, titolo: c.titolo || null, messaggi: c.messaggi || [], storia: c.storia || [] };
  citaAccesa = null;
  const box = $("#messaggi");
  box.replaceChildren();
  if (!conv.messaggi.length) {
    box.append(benvenuto(info));
    return null;
  }
  let ultima = null;
  for (const m of conv.messaggi) {
    if (m.tipo === "utente") disegnaUtente(m.testo);
    else if (m.tipo === "nota") disegnaNota(m.testo);
    else if (m.tipo === "vice") { const msg = crea("article", { class: "msg vice" }); box.append(msg); riempi(msg, m); }
    else if (m.tipo === "report" && m.testo) { const { msg } = messaggioReport(m); box.append(msg); riempi(msg, m); }
    if (m.vista) ultima = m.vista;
  }
  scorri();
  return ultima;
}

export function avviaChat() {
  const area = $("#domanda");
  const ridimensiona = () => { area.style.height = "auto"; area.style.height = `${Math.min(area.scrollHeight, 140)}px`; };
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); const t = area.value; area.value = ""; ridimensiona(); invia(t); });
  area.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); } });
  area.addEventListener("input", ridimensiona);
  // il segnaposto lungo solo se ci sta: nella chat stretta resterebbe tagliato a metà (08/11/2026)
  const lungo = area.placeholder;
  new ResizeObserver(() => { area.placeholder = area.clientWidth < 420 ? "Chiedi a Vice…" : lungo; }).observe(area);
  $("#contesto-togli").addEventListener("click", () => impostaLavagna(null));
  ascolta("prova-tolta", spegniCitazioni);   // la «prova» chiusa dalla lavagna spegne anche la citazione
  return { area, ridimensiona };
}
