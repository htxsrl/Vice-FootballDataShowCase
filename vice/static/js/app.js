// Vice — avvio del front-end (decisioni 39-43, 47-50 e 54): all'apertura una conversazione nuova, solo chat, con
// quello che resta da guardare; alla prima vista la pagina si divide in chat e lavagna, con un divisore da
// trascinare. Vice ragiona sempre da oggi, e la seduta di oggi arriva col file; ogni conversazione ha il suo giorno
// in esame, scelto dal calendario. Architettura e regole: wiki/tecnica/frontend-e-viste.md.
import { $, ascolta, dataBreve, dataLunga, giornoSettimana } from "./util.js";
import { caricamentoSalvato, salvaCaricamento, stato, togliCaricamento } from "./stato.js";
import { avviaTema, fontPronti } from "./tema.js";
import * as diario from "./diario.js";
import { apriConversazione, avviaChat, conversazioneAperta, impostaLavagna, inCorso, invia, nota, report, titoloReport } from "./chat.js";
import { mostra, ridimensionaTutto, ridisegnaTutto, svuota } from "./lavagna.js";
import { avviaVoce } from "./voce.js";
import { avviaGlossario } from "./glossario.js";
import { avviaCalendario, impostaStagione } from "./calendario.js";
import { avviaDivisore } from "./divisore.js";
import { avviaSuggerimenti } from "./suggerimenti.js";
import { aggiorna as aggiornaAvvisi, avviaAvvisi } from "./avvisi.js";

let pannelloDiario = null;
let pannelloCalendario = null;
let pannelloAvvisi = null;

async function contesto(giorno) {
  const c = giorno && stato.caricamenti[giorno]?.caricamento;
  const q = new URLSearchParams({ ...(giorno ? { oggi: giorno } : {}), ...(c ? { caricamento: c } : {}) });
  const qs = q.toString();
  const r = await fetch(`/api/contesto${qs ? `?${qs}` : ""}`);
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
  return j;
}

function intestazione(c) {
  $("#giorno-titolo").textContent = `${giornoSettimana(c.oggi)} ${dataLunga(c.oggi)}`;
  const pezzi = [c.giorno_md === "MD" ? "giorno di partita" : c.giorno_md];
  if (c.prossima_partita && c.prossima_partita !== c.oggi) pezzi.push(`partita ${giornoSettimana(c.prossima_partita)} ${dataBreve(c.prossima_partita)}`);
  if (c.oggi !== stato.oggi) pezzi.push(`giorno in esame, oggi è ${giornoSettimana(stato.oggi)} ${dataBreve(stato.oggi)}`);
  else if (c.seduta_prevista && !c.seduta_caricata) pezzi.push("seduta da caricare");
  $("#giorno-sotto").textContent = pezzi.join(", ");
}

/** Apre una conversazione nel suo giorno in esame (Vice ragiona sempre da oggi). `c` = salvata, oppure {giorno} per una nuova. */
async function apri(c) {
  if (inCorso()) { nota("Aspetta che Vice finisca la risposta, poi cambia conversazione."); return null; }
  let info;
  try {
    info = await contesto(c.giorno);
  } catch (e) {
    nota(`Non riesco ad aprire quel giorno: ${e.message}`);
    return null;
  }
  const conv = c.id ? c : { id: diario.nuovoId(), giorno: info.oggi, titolo: null, messaggi: [], storia: [] };
  stato.giorno = info.oggi;
  // il file di un giorno passato vale solo per quel giorno; quello di oggi vale sempre (decisione 54)
  for (const g of Object.keys(stato.caricamenti)) if (g !== info.oggi && g !== stato.oggi) togliCaricamento(g);
  intestazione(info);
  diario.segnaAperta(conv.id);
  svuota();
  impostaLavagna(null);
  const ultima = apriConversazione(conv, info);
  if (ultima) mostra(ultima);
  aggiornaIndirizzo(c.id ? conv.id : null, info.oggi);
  aggiornaHome();
  return info;
}

const nuova = (giorno) => apri({ giorno: giorno || stato.oggi });

// ---------- la pagina iniziale (decisione 63) ----------
/** Si è sulla pagina iniziale quando la conversazione di oggi è ancora vuota e la lavagna è chiusa. */
const aCasa = () => !document.body.classList.contains("con-lavagna") && !conversazioneAperta().messaggi.length && stato.giorno === stato.oggi;
function aggiornaHome() { $("#home").hidden = aCasa(); }
/** «Home» e il marchio: una conversazione nuova di oggi, con la demo e «Da guardare». Le altre restano nell'elenco. */
async function vaiHome() {
  if (aCasa()) return;
  await nuova(stato.oggi);
  aggiornaHome();
  $("#messaggi").scrollTop = 0;
}

/** Il clic su un giorno del calendario (decisione 49): il report di quel giorno, oppure l'invito a caricare l'export. */
async function apriGiorno(giorno) {
  pannelloCalendario.chiudi();
  if (inCorso()) { nota("Aspetta che Vice finisca la risposta, poi scegli un altro giorno."); return; }
  const salvata = diario.conversazioneDelGiorno(giorno);
  if (salvata) { await apri(salvata); return; }
  const info = await nuova(giorno);
  if (info && stato.reportPronti.has(giorno)) await report("seduta", { titolo: titoloReport(giorno, info.giorno_md) });
}

function aggiornaIndirizzo(id, giorno) {
  const url = new URL(location.href);
  for (const k of ["c", "oggi", "giorno"]) url.searchParams.delete(k);
  if (id) url.searchParams.set("c", id); else if (giorno !== stato.oggi) url.searchParams.set("giorno", giorno);
  history.replaceState(null, "", url);
}

// ---------- la pagina si divide alla prima vista ----------
function lavagnaAperta(si) {
  const prima = document.body.classList.contains("con-lavagna");
  document.body.classList.toggle("con-lavagna", si);
  $("#lavagna").hidden = !si;
  if (si && !prima) requestAnimationFrame(ridimensionaTutto);
  aggiornaHome();
}

// ---------- "Dal file al report" (M4.8) ----------
async function caricaFile(file) {
  if (!file) return;
  if (inCorso()) { nota("Aspetta che Vice finisca la risposta, poi carica il file."); return; }
  if (file.size > 2_000_000) { nota(`${file.name} è troppo grande per un export di seduta.`); return; }
  let j;
  try {
    const r = await fetch("/api/carica", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: file.name, testo: await file.text() }) });
    j = await r.json();
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
  } catch (e) {
    nota(`Non posso usare ${file.name}: ${e.message}`);
    return;
  }
  salvaCaricamento(j);
  if (j.data !== stato.giorno) await nuova(j.data);
  const diversi = j.valori_diversi_dal_dataset;
  const fonte = j.formato === "zenodo" ? "righe originali del dataset Zenodo, con i codici dei giocatori tradotti nei nomi di fantasia; " : "";
  const quale = (valore) => `${valore} ${valore === 1 ? "valore è diverso" : "valori sono diversi"}`;
  if (j.prima_volta) {
    // la seduta di oggi: Vice non la conosceva (decisione 54)
    nota(`Ho letto ${file.name} (${fonte}${j.tipo} di oggi, ${j.data_it}, ${j.giorno_md}, ${j.giocatori} giocatori): è la seduta di oggi.`
      + (diversi ? ` ${quale(diversi)} dalle righe del dataset: uso quelli del file.` : ""));
  } else {
    nota(`Ho letto ${file.name} (${fonte}${j.tipo} del ${j.data_it}, ${j.giorno_md}, ${j.giocatori} giocatori). `
      + (diversi ? `${quale(diversi)} dai dati del club che conosco: uso quelli del file.` : "I valori coincidono con i dati del club."));
  }
  if (j.data === stato.giorno) { try { intestazione(await contesto(j.data)); } catch { /* resta quella di prima */ } }
  if (j.prima_volta) await aggiornaAvvisi();
  if (j.tipo === "allenamento") await report("seduta", { titolo: titoloReport(j.data, j.giorno_md) });
  else mostra({ vista: "seduta", parametri: {} });
}

/** «Carica il CSV della demo»: le righe di oggi dal CSV di Zenodo, caricate come se le avessi trascinate. */
async function usaFileProva() {
  if (inCorso()) { nota("Aspetta che Vice finisca la risposta, poi carica il file."); return; }
  try {
    const r = await fetch(`/api/export-prova?data=${stato.oggi}`);
    if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
    const nome = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "")?.[1] || `seduta-${stato.oggi}.csv`;
    await caricaFile(new File([await r.text()], nome, { type: "text/csv" }));
  } catch (e) {
    nota(`Non trovo il file di prova di oggi: ${e.message}`);
  }
}

function avviaCaricamento() {
  const input = $("#file-export");
  input.addEventListener("change", () => { caricaFile(input.files[0]); input.value = ""; });
  addEventListener("dragover", (e) => { e.preventDefault(); document.body.classList.add("trascina"); });
  addEventListener("dragleave", (e) => { if (!e.relatedTarget) document.body.classList.remove("trascina"); });
  addEventListener("drop", (e) => { e.preventDefault(); document.body.classList.remove("trascina"); caricaFile(e.dataTransfer.files[0]); });
}

// ---------- menu ----------
function avviaMenu() {
  const apri = $("#apri-menu"), pannello = $("#menu");
  const mostraMenu = (si) => { pannello.hidden = !si; apri.setAttribute("aria-expanded", String(si)); };
  apri.addEventListener("click", (e) => { e.stopPropagation(); mostraMenu(pannello.hidden); });
  addEventListener("click", (e) => { if (!pannello.contains(e.target)) mostraMenu(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") mostraMenu(false); });
  $("#palco").addEventListener("click", (e) => {
    const on = document.body.classList.toggle("modo-palco");
    e.currentTarget.setAttribute("aria-pressed", String(on));
    requestAnimationFrame(ridimensionaTutto);
  });
  $("#elimina-conversazione").addEventListener("click", () => {
    mostraMenu(false);
    const c = conversazioneAperta();
    if (inCorso() || !c.messaggi.length) return;
    if (!confirm(`Eliminare la conversazione «${c.titolo || "senza titolo"}»? Le altre restano.`)) return;
    diario.elimina(c.id);
    nuova(c.giorno);
  });
}

async function avvia() {
  avviaTema();
  pannelloDiario = diario.avviaDiario();
  const { area, ridimensiona } = avviaChat();
  avviaVoce({ area, ridimensiona, invia });
  avviaCaricamento();
  avviaMenu();
  avviaGlossario();
  pannelloCalendario = avviaCalendario();
  pannelloAvvisi = avviaAvvisi();
  avviaDivisore(ridimensionaTutto);
  avviaSuggerimenti();
  await fontPronti();
  ascolta("tema", ridisegnaTutto);
  ascolta("lavagna", lavagnaAperta);
  ascolta("apri-conversazione", (id) => { pannelloDiario.chiudi(); const c = diario.leggi(id); if (c) apri(c); });
  ascolta("nuova-conversazione", (g) => { pannelloDiario.chiudi(); nuova(g); });
  ascolta("apri-giorno", (g) => { pannelloAvvisi.chiudi(); apriGiorno(g); });
  ascolta("pannello", (nome) => {
    if (nome !== "conversazioni") pannelloDiario.chiudi();
    if (nome !== "calendario") pannelloCalendario.chiudi();
    if (nome !== "avvisi") pannelloAvvisi.chiudi();
  });
  ascolta("apri-avvisi", () => pannelloAvvisi.apri());
  ascolta("usa-file-prova", usaFileProva);
  // «Chiedi a Vice» da un avviso: la domanda nella conversazione aperta
  ascolta("chiedi", (domanda) => {
    pannelloAvvisi.chiudi();
    if (inCorso()) { nota("Aspetta che Vice finisca la risposta, poi chiedi dell'avviso."); return; }
    invia(domanda);
  });
  ascolta("conversazione-salvata", (id) => { aggiornaIndirizzo(id, stato.giorno); pannelloCalendario.ridisegna(); aggiornaHome(); });
  $("#home").addEventListener("click", vaiHome);
  $("#marchio").addEventListener("click", (e) => { e.preventDefault(); vaiHome(); });
  ascolta("memoria-piena", () => nota("Il browser non ha più spazio per salvare le conversazioni: elimina qualche conversazione vecchia dal menu."));
  $("#nuova").addEventListener("click", () => nuova(stato.giorno));
  ascolta("scelta", (s) => impostaLavagna({ giocatore: s.giocatore, vista: s.vista, parametri: s.parametri, titolo: s.titolo }));
  ascolta("file-scaduto", () => {
    nota("Il file caricato non è più in memoria sul server (lo tiene due ore): ricaricalo per avere di nuovo la sua seduta.");
    aggiornaAvvisi();
  });
  let attesa;
  addEventListener("resize", () => { clearTimeout(attesa); attesa = setTimeout(ridimensionaTutto, 120); });

  // il giorno della demo e il calendario delle sedute fino a quel giorno
  try {
    const demo = await contesto(null);
    stato.oggi = demo.oggi;
    stato.reportPronti = new Set(demo.report_pronti || []);
    // la seduta di oggi già caricata in questo browser (decisione 54): un file modificato può non esserci più sul server
    const salvato = caricamentoSalvato();
    if (salvato) {
      stato.caricamenti[stato.oggi] = salvato;
      try { await contesto(stato.oggi); } catch { togliCaricamento(stato.oggi); }
    }
    await aggiornaAvvisi();
    stato.sigle = demo.sigle || null;
    diario.impostaSedute(demo.calendario.sedute, demo.oggi);
    impostaStagione(demo.calendario.sedute, demo.stagione.inizio);
  } catch (e) {
    $("#messaggi").textContent = `Non riesco a leggere la stagione: ${e.message}`;
    return;
  }
  const p = new URLSearchParams(location.search);
  if (p.get("palco")) $("#palco").click();
  // l'indirizzo può riaprire una conversazione salvata (?c=…) o un giorno in esame (?giorno=…); altrimenti una nuova di oggi
  const salvata = p.get("c") && diario.leggi(p.get("c"));
  await (salvata ? apri(salvata) : nuova(p.get("giorno") || p.get("oggi")));
}

avvia();
