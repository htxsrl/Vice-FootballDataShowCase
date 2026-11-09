// La lavagna (M4.2-M4.6): chiede al server la specifica di una vista, la disegna con la forma giusta e
// accende gli elementi citati nella chat. Una vista alla volta; si apre (seconda colonna) alla prima vista
// del giorno (decisione 39). Il clic su un giocatore lo rende il soggetto della prossima domanda.
// Una citazione cliccata lascia sopra il grafico la sua «prova»: il valore, cosa misura e dove sta nel grafico
// (una riga, tutta la squadra o nessun punto), così ogni clic ha una risposta visibile (08/11/2026).
import { $, crea, emetti, escapeHtml } from "./util.js";
import { contestoRichiesta, fileScaduto } from "./stato.js";
import { disegnaFasce, legendaFasce } from "./viste/fasce.js";
import { disegnaGriglia, legendaGriglia } from "./viste/griglia.js";
import { disegnaCurva, legendaCurva } from "./viste/curva.js";
import { disegnaVerifica } from "./viste/verifica.js";

const FORME = {
  fasce: { disegna: disegnaFasce, legenda: legendaFasce },
  griglia: { disegna: disegnaGriglia, legenda: legendaGriglia },
  curva: { disegna: disegnaCurva, legenda: legendaCurva },
  verifica: { disegna: disegnaVerifica, legenda: () => null },
};
const posti = {
  principale: { el: () => $("#vista-principale"), spec: null, disegno: null, richiesta: null },
};
// {evidenza, chiave, giocatore_id, prova?}: `prova` è l'evidenza della citazione cliccata, `provaVista` la vista in cui
// vale (cambiando metrica o grafico la striscia sparisce), `provaInArrivo` finché la sua vista non è disegnata
let selezione = null;

export const vistaCorrente = () => posti.principale.spec;

async function chiedi(richiesta) {
  const contesto = contestoRichiesta();
  const r = await fetch("/api/vista", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vista: richiesta.vista, parametri: richiesta.parametri || {}, ...contesto }),
  });
  const j = await r.json();
  if (!r.ok && contesto.caricamento && /ricaricalo/.test(j.detail || "") && fileScaduto(contesto.caricamento)) {
    // il server non ha più il file caricato (lo tiene due ore)
    emetti("file-scaduto");
    return chiedi(richiesta);
  }
  if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
  return j;
}

function chiave(richiesta) {
  return JSON.stringify([richiesta.vista, richiesta.parametri || {}]);
}

/** Porta una vista sulla lavagna (e la apre, se era chiusa). `richiesta` = {vista, parametri}. */
let ultimaRichiesta = 0;   // si disegna solo l'ultima vista chiesta: una risposta lenta non copre una più recente

export async function mostra(richiesta) {
  const p = posti.principale;
  const el = p.el();
  const numero = ++ultimaRichiesta;
  emetti("lavagna", true);
  // mentre arriva il nuovo grafico, il vecchio si spegne: non deve sembrare la risposta alla nuova domanda
  if (!p.spec) el.replaceChildren(crea("div", { class: "pannello carica", testo: "Preparo il grafico…" }));
  else el.classList.add("in-arrivo");
  el.setAttribute("aria-busy", "true");
  let spec;
  try {
    spec = await chiedi(richiesta);
  } catch (e) {
    if (numero !== ultimaRichiesta) return null;
    el.classList.remove("in-arrivo");
    el.removeAttribute("aria-busy");
    // una vista non disponibile non cancella quella che c'è
    if (!p.spec) el.replaceChildren(crea("div", { class: "pannello vuota errore-vista", testo: `Non riesco a mostrare questa vista: ${e.message}` }));
    console.info("vista non mostrata:", richiesta.vista, e.message);
    return null;
  }
  if (numero !== ultimaRichiesta) return null;   // nel frattempo è stata chiesta un'altra vista
  el.classList.remove("in-arrivo");
  el.removeAttribute("aria-busy");
  p.disegno?.distruggi();
  p.spec = spec;
  p.richiesta = { vista: spec.vista, parametri: spec.parametri };
  p.disegno = disegnaSpec(el, spec);
  if (selezione?.provaInArrivo) { selezione.provaVista = chiave(p.richiesta); selezione.provaInArrivo = false; }
  else if (selezione?.prova && selezione.provaVista !== chiave(p.richiesta)) { selezione.prova = null; emetti("prova-tolta"); }   // un altro grafico
  const trovato = selezione ? Boolean(p.disegno?.accendi(selezione)) : false;
  mettiProva(trovato);
  return spec;
}

function disegnaSpec(el, spec) {
  el.replaceChildren();
  const testa = crea("div", { class: "vista-testa" },
    crea("div", {}, crea("h2", { testo: spec.titolo }), spec.spiegazione ? crea("p", { class: "spiegazione", testo: spec.spiegazione }) : null));
  // selettori: la metrica e quelli propri della vista
  const selettori = [...(spec.metriche?.length ? [{ parametro: "metrica", scelto: spec.metrica, opzioni: spec.metriche }] : []),
    ...(spec.selettori || [])];
  if (selettori.length) {
    const box = crea("div", { class: "selettori" });
    for (const sel of selettori) {
      const gruppo = crea("div", { class: "metriche", role: "group", "aria-label": sel.parametro });
      for (const o of sel.opzioni) {
        // il suggerimento con lo stesso stile dei grafici (decisione 52): sigla e significato, poi cosa misura
        const nome = o.significato || o.titolo || o.nome;
        const tip = nome && nome !== o.sigla
          ? `<div class="tip"><strong>${escapeHtml(o.sigla)}: ${escapeHtml(nome)}</strong>${o.misura ? escapeHtml(o.misura) : ""}</div>` : null;
        gruppo.append(crea("button", {
          type: "button", "aria-pressed": String(o.id === sel.scelto), "aria-label": nome ? `${o.sigla}: ${nome}` : o.sigla,
          dataset: tip ? { tip } : undefined,
          onclick: () => mostra({ vista: spec.vista, parametri: { ...spec.parametri, [sel.parametro]: o.id } }),
        }, o.sigla));
      }
      box.append(gruppo);
    }
    testa.append(box);
  }
  el.append(testa);
  const pannello = crea("div", { class: "pannello" });
  el.append(pannello);
  if (!spec.righe || !spec.righe.length) {
    pannello.classList.add("vuota");
    pannello.textContent = spec.vuota || "Nessun dato da mostrare.";
    if (spec.avvisi?.length) el.append(crea("ul", { class: "avvisi" }, spec.avvisi.map((a) => crea("li", { testo: a }))));
    return null;
  }
  const forma = FORME[spec.forma];
  if (!forma) {
    pannello.textContent = "Vista non ancora disegnabile.";
    return null;
  }
  const disegno = forma.disegna(pannello, spec, {
    onScelta: (riga) => {
      if (riga.giocatore) scegliGiocatore(riga.giocatore, spec);
      else if (riga.azione) vaiAllAzione(riga, spec);
    },
    onAzione: (riga) => vaiAllAzione(riga, spec),
    onCella: (riga, giorno, cella) => {
      scegliGiocatore(riga.giocatore, spec, cella.evidenza);
      mostra({ vista: "seduta", parametri: { data: giorno.data, metrica: spec.metrica } });
    },
  });
  // la legenda sta nel riquadro del grafico, sul suo stesso fondo: i campioni chiari si vedono (08/11/2026)
  const l = forma.legenda(spec);
  if (l) pannello.append(l);
  if (spec.avvisi?.length) el.append(crea("ul", { class: "avvisi" }, spec.avvisi.map((a) => crea("li", { testo: a }))));
  el.append(crea("p", { class: "fonte", testo: spec.fonte }));
  return disegno;
}

// clic su una riga-seduta (V3) o su un giorno (V5): la seduta di quel giorno, col giocatore acceso se c'è
function vaiAllAzione(riga, spec) {
  if (spec.giocatore) scegliGiocatore(spec.giocatore, spec, riga.evidenza);
  mostra(riga.azione);
}

function scegliGiocatore(giocatore, spec, evidenza) {
  const cera = Boolean(selezione?.prova);
  selezione = { giocatore_id: giocatore.id, evidenza };
  accendiTutto();
  if (cera) { mettiProva(false); emetti("prova-tolta"); }
  emetti("scelta", { giocatore, vista: spec.vista, parametri: spec.parametri, titolo: spec.titolo });
}

function accendiTutto() {
  let trovato = false;
  for (const p of Object.values(posti)) if (p.disegno) trovato = p.disegno.accendi(selezione) || trovato;
  return trovato;
}

// ---------- la prova della citazione ----------
function mettiProva(trovato) {
  const p = posti.principale;
  const el = p.el();
  el.querySelector(".prova-citata")?.remove();
  const ev = selezione?.prova;
  if (!ev || !p.spec) return;
  const squadra = Boolean(ev.grafico) && (p.spec.chiavi_squadra || []).includes(ev.grafico);
  const dove = squadra ? "È un dato di tutta la squadra: nel grafico sono accese tutte le righe."
    : trovato ? "Nel grafico è acceso il punto da cui viene."
      : "È un numero calcolato dal motore: in questo grafico non ha un punto suo.";
  const box = crea("div", { class: "prova-citata", role: "status" },
    crea("span", { class: "prova-etichetta", testo: ev.etichetta_citazione || "prova" }),
    crea("span", { class: "prova-valore", testo: String(ev.valore_testo ?? ev.valore ?? "") }),
    crea("span", { class: "prova-testo" }, crea("span", { class: "prova-cosa", testo: ev.etichetta || "" }), crea("span", { class: "prova-dove", testo: dove })),
    crea("button", { type: "button", class: "chiudi", "aria-label": "Togli la prova dal grafico", onclick: () => { togliSelezione(); emetti("prova-tolta"); } }, "×"));
  const testa = el.querySelector(".vista-testa");
  if (testa) testa.after(box); else el.prepend(box);
}

// La vista in cui un'evidenza si vede, dal suo id (es. "seduta/2024-04-18/9/hsr").
function vistaDiEvidenza(id, grafico) {
  let m = /^seduta\/(\d{4}-\d{2}-\d{2})\/(\d+)\/(\w+)$/.exec(id || "");
  if (m) return { vista: "seduta", parametri: { data: m[1], metrica: m[3] } };
  m = /^seduta\/(\d{4}-\d{2}-\d{2})\/squadra\/(\w+)$/.exec(id || "");
  if (m) return { vista: "seduta", parametri: m[2] === "fuori" ? { data: m[1] } : { data: m[1], metrica: m[2] } };
  m = /^settimana\/(\d{4}-\d{2}-\d{2})\/[^/]+\/(\w+)$/.exec(id || "");
  if (m) return { vista: "curva_settimana", parametri: { metrica: m[2] } };
  m = /^andamento\/(\d{4}-\d{2}-\d{2})\/(\d+)\/(\w+)$/.exec(id || "");
  if (m) return { vista: "giocatore", parametri: { giocatore_id: Number(m[2]), metrica: m[3] } };
  m = /^partita\/(\d{4}-\d{2}-\d{2})\/(?:\d+|squadra)\/(\w+)/.exec(id || "");
  if (m) return { vista: "allenamento_partita", parametri: { metrica: m[2] } };
  if (/^replica\//.test(id || "")) return { vista: "verifica", parametri: {} };
  return null;
}

/** Accende sulla lavagna l'evidenza citata (clic su [E3]); se serve, porta prima la vista giusta. */
export async function accendiEvidenza(ev) {
  if (!ev) { togliSelezione(); return; }
  selezione = { evidenza: ev.id, chiave: ev.grafico, giocatore_id: ev.giocatore_id ?? null, prova: ev };
  const r = vistaDiEvidenza(ev.id, ev.grafico);
  const p = posti.principale;
  const giusta = p.spec && (!r || chiave(r) === chiave(p.richiesta || {}));
  if (giusta) { selezione.provaVista = chiave(p.richiesta); mettiProva(accendiTutto()); return; }
  selezione.provaInArrivo = true;
  // la vista dove l'evidenza si vede (o, se non ne ha una, la seduta del giorno); mostra() accende la selezione
  await mostra(r || p.richiesta || { vista: "seduta", parametri: {} });
}

export function togliSelezione() { selezione = null; accendiTutto(); mettiProva(false); }

/** «Mostra sulla lavagna» di un avviso (decisione 54): la sua vista, col giocatore o la seduta già accesi. */
export function mostraAcceso(richiesta, sel) {
  selezione = sel ? { giocatore_id: sel.giocatore_id ?? null, evidenza: sel.evidenza ?? null } : null;
  return mostra(richiesta);
}

/** Chiude la lavagna e la svuota (cambio di giorno). */
export function svuota() {
  const p = posti.principale;
  p.disegno?.distruggi();
  p.spec = p.disegno = p.richiesta = null;
  p.el().replaceChildren();
  selezione = null;
  emetti("lavagna", false);
}

export function ridisegnaTutto() { for (const p of Object.values(posti)) p.disegno?.ridisegna(); }
export function ridimensionaTutto() { for (const p of Object.values(posti)) p.disegno?.ridimensiona(); }
