// «Da guardare» (decisione 54): gli avvisi che Vice dà da sé. Nascono col caricamento della seduta; il server dà
// lo stato di ciascuno (aperto, aggiornato, chiuso, scaduto), il browser ricorda quelli che il preparatore ha segnato
// come visti. Lo stesso avviso compare all'apertura, in testa al report e nel menù «Da guardare», con tre gesti:
// Mostra (il suo grafico sulla lavagna), Chiedi a Vice (la domanda in chat), Visto. Nel menù in alto restano solo
// quelli nuovi o non ancora visti; visti, chiusi, aggiornati e scaduti stanno nelle «segnalazioni passate», da aprire
// (08/11/2026).
import { $, crea, dataBreve, emetti, escapeHtml, giornoSettimana, riduciMovimento } from "./util.js";
import { stato } from "./stato.js";
import { mostraAcceso } from "./lavagna.js";

const CHIAVE_VISTI = "vice-avvisi-visti-v1";
const MAX_APERTURA = 5;          // all'apertura; gli altri restano nel menù
const GIORNI_STORICO = 21;       // lo storico del menù, prima di «tutta la stagione»

let elenco = { fino_al: null, seduta_caricata: false, avvisi: [] };
let visti = leggiVisti();

function leggiVisti() {
  try { return JSON.parse(localStorage.getItem(CHIAVE_VISTI)) || {}; } catch { return {}; }
}
function scriviVisti() {
  try { localStorage.setItem(CHIAVE_VISTI, JSON.stringify(visti)); } catch { /* il browser non salva: vale per questa visita */ }
}

export const visto = (a) => Boolean(visti[a.id]);
export const tutti = () => elenco.avvisi;
const aperti = (cat) => elenco.avvisi.filter((a) => a.stato === "aperto" && a.categoria === cat);
/** Gli avvisi che chiedono un'azione e nessuno ha ancora segnato come visti. */
export const daGuardare = () => aperti("azione").filter((a) => !visto(a));

export function segnaVisto(a, si) {
  if (si) visti[a.id] = Date.now(); else delete visti[a.id];
  scriviVisti();
  document.querySelectorAll(`.avviso[data-id="${a.id}"]`).forEach((el) => aggiornaVoce(el, a));
  conta();
  // nel menù un avviso visto scende tra le segnalazioni passate (e torna su se lo si rimette da guardare)
  const pannello = $("#avvisi");
  if (pannello && !pannello.hidden) {
    const dentro = pannello.contains(document.activeElement);
    disegnaPannello();
    if (dentro) $("#avvisi-elenco").focus({ preventScroll: true });
  }
}

/** Rilegge gli avvisi dal server (all'avvio e dopo un caricamento). */
export async function aggiorna() {
  const car = stato.caricamenti[stato.oggi]?.caricamento;
  const q = new URLSearchParams({ oggi: stato.oggi, ...(car ? { caricamento: car } : {}) });
  try {
    const r = await fetch(`/api/avvisi?${q}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    elenco = await r.json();
  } catch (e) {
    console.info("avvisi non disponibili:", e.message);
  }
  conta();
  disegnaPannello();
  emetti("avvisi", elenco);
}

// ---------- una voce ----------
const quando = (a) => `${giornoSettimana(a.data).slice(0, 3)} ${dataBreve(a.data)}${a.giorno_md ? `, ${a.giorno_md}` : ""}`;

function conNome(testo, a) {
  const t = escapeHtml(testo);
  return a.giocatore ? t.replace(escapeHtml(a.giocatore), `<strong>${escapeHtml(a.giocatore)}</strong>`) : t;
}
const testoConNome = (a) => conNome(a.testo, a);

// Il testo di un avviso (scritto dal codice) è «cosa valutare: perché». Si divide ai primi due punti, così la scheda
// si legge in due tempi: la domanda per lo staff, poi i numeri che la motivano. «Da segnalare:» non dice nulla e si toglie.
const SOLO_PREFISSO = /^(Da segnalare):\s*/;
function dividi(testo) {
  const t = testo.replace(SOLO_PREFISSO, "");
  const i = t.indexOf(": ");
  if (i < 12 || i > 120) return { cosa: null, perche: t };
  const resto = t.slice(i + 2);
  return { cosa: t.slice(0, i), perche: resto.charAt(0).toUpperCase() + resto.slice(1) };
}

// icone delle azioni (24×24, riempite col colore del testo)
const ICONE = {
  mostra: '<path d="M4 19h16v2H4zM5 11h3v6H5zm5.5-6h3v12h-3zM16 8h3v9h-3z"/>',
  chiedi: '<path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 2v9h4v1.8L11.3 15H19V6H5Z"/>',
  report: '<path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 1.5V8h4.5L14 3.5ZM7 12h10v1.6H7V12Zm0 4h10v1.6H7V16Z"/>',
  visto: '<path d="M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z"/>',
};
function azione(nome, testo, onclick, attr = {}) {
  const b = crea("button", { type: "button", class: `azione azione-${nome}`, onclick, ...attr });
  b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONE[nome]}</svg><span>${escapeHtml(testo)}</span>`;
  return b;
}

const STATO_TESTO = {
  aggiornato: (a) => `aggiornato il ${dataBreve(a.stato_dal)}`,
  chiuso: (a) => `chiuso il ${dataBreve(a.stato_dal)}: ${a.stato_motivo}`,
  scaduto: (a) => (a.stato_motivo === "c'è stata la partita" ? `scaduto con la partita del ${dataBreve(a.stato_dal)}`
    : `scaduto il ${dataBreve(a.stato_dal)}`),
};

function aggiornaVoce(el, a) {
  const b = el.querySelector("button.visto");
  const si = visto(a);
  el.classList.toggle("e-visto", si && a.stato === "aperto");
  if (b) {
    b.setAttribute("aria-pressed", String(si));
    b.querySelector("span").textContent = si ? "Visto" : "Segna come visto";
    b.setAttribute("aria-label", si ? "Visto: clicca per rimetterlo tra quelli da guardare" : "Segna come visto");
    b.dataset.tip = `<div class="tip">${si ? "<strong>Visto</strong>clicca per rimetterlo tra quelli da guardare" : "Segna come visto"}</div>`;
  }
}

/** Un avviso, come scheda: famiglia e giorno, cosa valutare, perché, e i gesti nel piede.
 * `opzioni.stato`: mostra lo stato (nel menù); `opzioni.report`: «Apri il report del giorno». */
export function voce(a, opzioni = {}) {
  const passato = a.stato && a.stato !== "aperto";
  const li = crea("li", { class: `avviso cat-${a.categoria}${a.urgente ? " urgente" : ""}${passato ? " passato" : ""}`,
    dataset: { id: a.id } });
  const testa = crea("p", { class: "avviso-testa" },
    crea("span", { class: "famiglia", testo: a.urgente ? "Valore impossibile nel file" : a.nome_famiglia }),
    crea("span", { class: "quando", testo: quando(a) }));
  li.append(testa);
  if (opzioni.stato && passato) li.append(crea("p", { class: "stato", testo: STATO_TESTO[a.stato](a) }));
  else if (opzioni.stato && a.categoria === "azione" && visto(a)) li.append(crea("p", { class: "stato", testo: "segnato come visto" }));
  const { cosa, perche } = dividi(a.testo);
  if (cosa) { const p = crea("p", { class: "avviso-cosa" }); p.innerHTML = conNome(cosa, a); li.append(p); }
  const testo = crea("p", { class: "avviso-testo" });
  // il nome in grassetto una volta sola, dove compare per primo
  testo.innerHTML = cosa && a.giocatore && cosa.includes(a.giocatore) ? escapeHtml(perche) : conNome(perche, a);
  li.append(testo);
  const azioni = crea("div", { class: "avviso-azioni" });
  if (a.vista) azioni.append(azione("mostra", "Mostra sulla lavagna", () => { emetti("pannello", null); mostraAcceso(a.vista, a.accendi); }));
  if (a.domanda) azioni.append(azione("chiedi", "Chiedi a Vice", () => emetti("chiedi", a.domanda)));
  if (opzioni.report) azioni.append(azione("report", "Apri il report del giorno", () => emetti("apri-giorno", a.data)));
  if (a.categoria === "azione" && (a.stato === "aperto" || !a.stato)) {
    azioni.append(azione("visto", "Segna come visto", () => segnaVisto(a, !visto(a)), { "aria-pressed": "false" }));
    azioni.lastChild.classList.add("visto");
  }
  if (azioni.childElementCount) li.append(azioni);
  aggiornaVoce(li, a);
  return li;
}

const lista = (avvisi, opzioni) => crea("ul", { class: "avvisi-lista" }, avvisi.map((a) => voce(a, opzioni)));

// righe brevi, senza gesti: la qualità del dato e le buone notizie
const SENZA_PREFISSO = /^(Verificare il dato|Da segnalare):\s*/;
function righeBrevi(avvisi, classe, titolo) {
  if (!avvisi.length) return null;
  return crea("div", { class: `righe-brevi ${classe}` }, crea("p", { class: "righe-titolo", testo: titolo }),
    crea("ul", {}, avvisi.map((a) => {
      const li = crea("li", { dataset: { id: a.id } });
      li.innerHTML = testoConNome({ ...a, testo: a.testo.replace(SENZA_PREFISSO, "") });
      return li;
    })));
}

// ---------- all'apertura: quelli ancora da guardare ----------
// Aperto, un riquadro «Da guardare» arriva fino alla casella della domanda e scorre al suo interno: si legge tutto senza
// scorrere la pagina (decisione 63). L'altezza minima resta comoda anche se il riquadro è già in basso.
const ALTEZZA_MINIMA = 240;
function adattaAltezza(scheda) {
  const corpo = scheda.querySelector(":scope > .punto-corpo");
  if (!scheda.open || !corpo) return;
  const limite = $("#composer")?.getBoundingClientRect().top ?? innerHeight;
  corpo.style.maxHeight = `${Math.max(ALTEZZA_MINIMA, Math.floor(limite - corpo.getBoundingClientRect().top - 12))}px`;
  // su uno schermo basso (un proiettore a 1280×720) il riquadro alto il minimo può sporgere: la chat scorre quanto basta
  if (corpo.getBoundingClientRect().bottom > limite) scheda.scrollIntoView({ block: "nearest", behavior: riduciMovimento() ? "auto" : "smooth" });
}
addEventListener("resize", () => document.querySelectorAll("details.punto[open], details.da-guardare[open]").forEach(adattaAltezza));

const OCCHIO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5C6.6 5 3 9.4 2 12c1 2.6 4.6 7 10 7s9-4.4 10-7c-1-2.6-4.6-7-10-7Zm0 12c-3.7 0-6.6-2.9-7.8-5C5.4 9.9 8.3 7 12 7s6.6 2.9 7.8 5c-1.2 2.1-4.1 5-7.8 5Zm0-8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/></svg>';

/** Il punto del giorno nel benvenuto (decisione 54): gli avvisi aperti non visti, il dato, le buone notizie, in un
 * riquadro col suo fondo che si apre dal titolo (con l'occhio e il numero, 08/11/2026). All'apertura è chiuso, e aperto
 * scorre al suo interno, non con la pagina (decisione 63, 09/11/2026). */
export function punto() {
  const tutti = daGuardare();
  const delGiorno = tutti.filter((a) => !a.riassunto);
  const settimana = tutti.filter((a) => a.riassunto);
  const titolo = crea("summary", { class: "punto-titolo" });
  titolo.innerHTML = OCCHIO;
  titolo.append(crea("span", { testo: "Da guardare" }));
  if (tutti.length) titolo.append(crea("span", { class: "conta-titolo", "aria-label": `${tutti.length} ${tutti.length === 1 ? "avviso" : "avvisi"}`, testo: String(tutti.length) }));
  titolo.append(crea("span", { class: "freccia-apri", "aria-hidden": "true" }));
  const corpo = crea("div", { class: "punto-corpo" });
  const scheda = crea("details", { class: "punto" }, titolo, corpo);   // chiuso all'apertura (decisione 63)
  scheda.addEventListener("toggle", () => adattaAltezza(scheda));
  const box = corpo;   // il contenuto va nel corpo del riquadro
  if (!tutti.length) box.append(crea("p", { class: "niente", testo: "Niente da guardare: gli avvisi dei giorni scorsi sono chiusi o li hai già visti." }));
  if (delGiorno.length) {
    box.append(lista(delGiorno.slice(0, MAX_APERTURA)));
    if (delGiorno.length > MAX_APERTURA) {
      box.append(crea("button", { type: "button", class: "altri", onclick: () => emetti("apri-avvisi") },
        `Altri ${delGiorno.length - MAX_APERTURA} nel menù «Da guardare»`));
    }
  }
  if (settimana.length) {
    // chiusa all'inizio, come il riquadro (decisione 63)
    const d = crea("details", { class: "settimana-breve" },
      crea("summary", {}, `La settimana in breve (${settimana.length})`), lista(settimana));
    box.append(d);
  }
  const dato = righeBrevi(aperti("dato").filter((a) => !a.urgente || a.data === elenco.fino_al), "dato", "Da verificare nei dati");
  const buone = righeBrevi(aperti("informa"), "buone", "Buone notizie e rientri");
  if (dato || buone) box.append(crea("div", { class: "righe-brevi-coppia" }, dato, buone));
  return scheda;
}

// ---------- in testa al report ----------
const TITOLI = { seduta: "Da guardare oggi", settimana: "Ancora da guardare", giocatore: "I suoi avvisi" };

/** Il riquadro degli avvisi di un report (evento `avvisi`). Gli avvisi sul dato vanno nella «Qualità del dato».
 * È un riquadro da aprire, chiuso all'inizio, così in evidenza restano la sintesi e le risposte (decisione 63); si apre da
 * solo solo se il file caricato ha un valore impossibile, che va visto subito. */
export function riquadroReport(dati) {
  const avvisi = dati?.avvisi || [];
  const inTesta = avvisi.filter((a) => a.categoria !== "dato" || a.urgente);
  const urgenti = inTesta.filter((a) => a.urgente);
  const giorno = inTesta.filter((a) => !a.urgente && !a.riassunto);
  const settimana = inTesta.filter((a) => !a.urgente && a.riassunto);
  const nome = TITOLI[dati?.tipo] || "Da guardare";
  const titolo = crea("summary", { class: "punto-titolo" });
  titolo.innerHTML = OCCHIO;
  titolo.append(crea("span", { testo: nome }));
  const quanti = urgenti.length + giorno.length;
  if (quanti) titolo.append(crea("span", { class: "conta-titolo", "aria-label": `${quanti} ${quanti === 1 ? "avviso" : "avvisi"}`, testo: String(quanti) }));
  titolo.append(crea("span", { class: "freccia-apri", "aria-hidden": "true" }));
  const corpo = crea("div", { class: "punto-corpo" });
  const box = crea("details", { class: "da-guardare", open: urgenti.length > 0 }, titolo, corpo);
  box.addEventListener("toggle", () => adattaAltezza(box));
  if (!inTesta.length) corpo.append(crea("p", { class: "niente", testo: dati?.tipo === "seduta" ? "Nessun avviso nuovo oggi." : "Nessun avviso aperto." }));
  if (urgenti.length) corpo.append(lista(urgenti));
  if (giorno.length) corpo.append(lista(giorno));
  if (settimana.length) {
    corpo.append(crea("details", { class: "settimana-breve" },
      crea("summary", {}, `La settimana in breve (${settimana.length})`), lista(settimana)));
  }
  return box;
}

/** Gli avvisi sul dato sotto il titolo «Qualità del dato» del report (o in fondo al riquadro, se manca). */
export function mettiDato(voceEl, riquadro, dati) {
  const dato = (dati?.avvisi || []).filter((a) => a.categoria === "dato" && !a.urgente);
  voceEl.querySelector(".dato-avvisi")?.remove();
  if (!dato.length) return;
  const ul = crea("ul", { class: "dato-avvisi" }, dato.map((a) => {
    const li = crea("li");
    li.innerHTML = testoConNome(a);
    return li;
  }));
  const titolo = [...voceEl.querySelectorAll("h4, h5")].find((h) => /^qualità del dato/i.test(h.textContent.trim()));
  if (titolo) titolo.after(ul); else (riquadro?.querySelector(".punto-corpo") || riquadro)?.append(ul);
}

// ---------- il menù «Da guardare» ----------
let tuttaLaStagione = false;
let passateAperte = false;      // le «segnalazioni passate» restano aperte se le hai aperte

function conta() {
  const n = daGuardare().length;
  // anche il numero nel riquadro dell'apertura segue i «Visto»
  document.querySelectorAll(".punto .conta-titolo").forEach((c) => {
    c.textContent = String(n);
    c.hidden = n === 0;
    c.setAttribute("aria-label", `${n} ${n === 1 ? "avviso" : "avvisi"}`);
  });
  const el = $("#conta-avvisi");
  if (!el) return;
  el.textContent = String(n);
  el.hidden = n === 0;
  $("#apri-avvisi").setAttribute("aria-label", n ? `Da guardare: ${n} ${n === 1 ? "avviso" : "avvisi"}` : "Da guardare: niente di nuovo");
}

// in alto nel menù: gli avvisi aperti che nessuno ha segnato come visti (dati e buone notizie non si segnano)
const nuovo = (a) => a.stato === "aperto" && !(a.categoria === "azione" && visto(a));

function disegnaPannello() {
  const el = $("#avvisi-elenco");
  if (!el) return;
  el.replaceChildren();
  const sezione = (titolo, ...figli) => crea("section", {}, crea("h3", { testo: titolo }), ...figli);
  const ora = daGuardare();
  el.append(sezione("Da guardare", ora.length ? lista(ora, { report: true })
    : crea("p", { class: "vuoto", testo: "Niente di nuovo da guardare." })));
  const dato = aperti("dato"), buone = aperti("informa");
  if (dato.length) el.append(sezione("Da verificare nei dati", lista(dato, { report: true })));
  if (buone.length) el.append(sezione("Buone notizie e rientri", lista(buone, { report: true })));
  // le segnalazioni passate (viste, chiuse, aggiornate, scadute), giorno per giorno dal più recente, da aprire
  const limite = elenco.fino_al ? new Date(new Date(`${elenco.fino_al}T12:00:00`).getTime() - GIORNI_STORICO * 864e5).toISOString().slice(0, 10) : "";
  const passate = elenco.avvisi.filter((a) => !nuovo(a));
  const mostrate = passate.filter((a) => tuttaLaStagione || a.data >= limite);
  if (!passate.length) return;
  const perGiorno = new Map();
  for (const a of mostrate) { if (!perGiorno.has(a.data)) perGiorno.set(a.data, []); perGiorno.get(a.data).push(a); }
  const blocchi = [...perGiorno].map(([d, avv]) => crea("div", { class: "storico-giorno" },
    crea("h4", { testo: `${giornoSettimana(d)} ${dataBreve(d)}${avv[0].giorno_md ? `, ${avv[0].giorno_md}` : ""}` }),
    lista(avv, { stato: true, report: true })));
  const quante = tuttaLaStagione ? `${passate.length} nella stagione` : `${mostrate.length} nelle ultime tre settimane`;
  const box = crea("details", { class: "passate", open: passateAperte },
    crea("summary", {}, crea("span", { testo: "Vedi segnalazioni passate" }), crea("span", { class: "passate-quante", testo: quante })),
    crea("p", { class: "diario-nota", testo: "Viste, chiuse, aggiornate o scadute: restano qui per ritrovarle." }),
    ...blocchi,
    !tuttaLaStagione && passate.length > mostrate.length
      ? crea("button", { type: "button", class: "altri", onclick: () => { tuttaLaStagione = true; disegnaPannello(); } },
        `Tutta la stagione (${passate.length} segnalazioni)`) : null);
  box.addEventListener("toggle", () => { passateAperte = box.open; });
  el.append(box);
}

export function avviaAvvisi() {
  const pannello = $("#avvisi"), velo = $("#velo"), apri = $("#apri-avvisi");
  const mostra = (si) => {
    if (pannello.hidden === !si) return;
    if (si) { emetti("pannello", "avvisi"); disegnaPannello(); }
    pannello.hidden = !si; velo.hidden = !si;
    apri.setAttribute("aria-expanded", String(si));
    if (si) $("#chiudi-avvisi").focus();
  };
  apri.addEventListener("click", () => mostra(pannello.hidden));
  $("#chiudi-avvisi").addEventListener("click", () => mostra(false));
  velo.addEventListener("click", () => mostra(false));
  addEventListener("keydown", (e) => { if (e.key === "Escape") mostra(false); });
  return { chiudi: () => mostra(false), apri: () => mostra(true) };
}
