// Vice — utilità comuni del front-end (moduli ES senza build, decisione 19).

export const POSIZIONI = ["molto sotto", "sotto", "dentro", "sopra", "molto sopra"];
export const FRECCIA = { "molto sotto": "↓↓", sotto: "↓", dentro: "·", sopra: "↑", "molto sopra": "↑↑", "senza fascia": "" };
export const VAR_POS = {
  "molto sotto": "--molto-sotto", sotto: "--sotto", dentro: "--dentro", sopra: "--sopra", "molto sopra": "--molto-sopra",
  "senza fascia": "--senza-fascia",
};

export const $ = (s, el = document) => el.querySelector(s);
export const css = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();

export function crea(tag, attr = {}, ...figli) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attr)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "testo") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(e.dataset, v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const f of figli.flat()) if (f !== null && f !== undefined && f !== false) e.append(f);
  return e;
}

export function svg(tag, attr = {}) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attr)) e.setAttribute(k, v);
  return e;
}

export const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// i suggerimenti (decisione 52): nelle righe «etichetta: valore» l'etichetta va in grassetto; la posizione
// rispetto alla fascia anche
export const rigaTip = (t) => {
  const s = escapeHtml(t);
  const i = s.indexOf(": ");
  return i > 0 && i < 60 ? `<b>${s.slice(0, i)}</b>${s.slice(i)}` : s;
};
export const posizioneTip = (p) => (p ? `<b>${escapeHtml(p === "dentro" ? "dentro la fascia" : p)}</b>` : "");

// date: "2024-04-18" → "18/04", "giovedì"
export const dataBreve = (iso) => { const [, m, g] = iso.split("-"); return `${g}/${m}`; };
export const dataLunga = (iso) => { const [a, m, g] = iso.split("-"); return `${g}/${m}/${a}`; };
export const giornoSettimana = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("it-IT", { weekday: "long" });
// come il server: punto delle migliaia anche a 4 cifre ("6.673"), virgola decimale
const formatoNumeri = new Intl.NumberFormat("it-IT", { useGrouping: "always", maximumFractionDigits: 2 });
export const numero = (x) => formatoNumeri.format(Number(x));
export const secondi = (ms) => (ms / 1000).toLocaleString("it-IT", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

// eventi SSE da un corpo in streaming
export async function* eventiSSE(risposta) {
  const lettore = risposta.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await lettore.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const blocco = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let evento = "message", dati = "";
      for (const riga of blocco.split("\n")) {
        if (riga.startsWith("event:")) evento = riga.slice(6).trim();
        else if (riga.startsWith("data:")) dati += riga.slice(5).trim();
      }
      if (!dati) continue;
      try { yield { evento, dati: JSON.parse(dati) }; } catch { /* blocco incompleto o non JSON: si salta */ }
    }
  }
}

// un bus minimo tra i moduli (selezione, cambio di giorno, tema)
const bus = new EventTarget();
export const emetti = (nome, dettaglio) => bus.dispatchEvent(new CustomEvent(nome, { detail: dettaglio }));
export const ascolta = (nome, f) => bus.addEventListener(nome, (e) => f(e.detail));

export const riduciMovimento = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
