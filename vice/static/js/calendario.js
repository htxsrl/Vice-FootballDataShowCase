// Il calendario (decisioni 47 e 49): i mesi della stagione fino a oggi, come un calendario da tasca. I giorni
// col pallino hanno il report di Vice (pronto sul server o salvato in questo browser); il clic su un giorno lo
// rende il giorno in esame e porta al suo report, oppure all'invito a caricare l'export. Le partite sono in
// grassetto, i giorni dopo oggi non si possono scegliere.
import { $, crea, emetti, escapeHtml } from "./util.js";
import { sedutaDiOggiCaricata, stato } from "./stato.js";
import { giorniConReport } from "./diario.js";

const MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
  "novembre", "dicembre"];
const GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
const GIORNI_LUNGHI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"];

let sedute = new Map();       // "AAAA-MM-GG" → {tipo, md}
let inizio = null;            // primo mese della stagione, "AAAA-MM"
let mese = null;              // il mese mostrato, "AAAA-MM"

const iso = (a, m, g) => `${a}-${String(m).padStart(2, "0")}-${String(g).padStart(2, "0")}`;
const meseDi = (giorno) => giorno.slice(0, 7);
const sposta = (m, n) => {
  const [a, mm] = m.split("-").map(Number);
  const d = new Date(a, mm - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export function impostaStagione(calendarioSedute, primoGiorno) {
  sedute = new Map(calendarioSedute.map((s) => [s.data, s]));
  inizio = meseDi(primoGiorno);
  disegna();
}

function disegna() {
  const el = $("#calendario-mese");
  if (!el || !stato.oggi) return;
  mese = mese || meseDi(stato.giorno || stato.oggi);
  const [a, m] = mese.split("-").map(Number);
  const conReport = new Set([...stato.reportPronti, ...giorniConReport()]);
  $("#calendario-titolo-mese").textContent = `${MESI[m - 1]} ${a}`;
  $("#mese-prima").disabled = mese <= inizio;
  $("#mese-dopo").disabled = mese >= meseDi(stato.oggi);

  const griglia = crea("div", { class: "cal-griglia", role: "grid", "aria-label": `${MESI[m - 1]} ${a}` });
  const testa = crea("div", { class: "cal-riga", role: "row" });
  GIORNI.forEach((g, i) => testa.append(crea("span", { class: "cal-testa", role: "columnheader", title: GIORNI_LUNGHI[i] }, g)));
  griglia.append(testa);
  const primo = (new Date(a, m - 1, 1).getDay() + 6) % 7;          // lunedì = 0
  const giorniNelMese = new Date(a, m, 0).getDate();
  let riga = crea("div", { class: "cal-riga", role: "row" });
  for (let i = 0; i < primo; i++) riga.append(crea("span", { class: "cal-vuoto", role: "gridcell" }));
  for (let g = 1; g <= giorniNelMese; g++) {
    const giorno = iso(a, m, g);
    const s = sedute.get(giorno);
    const futuro = giorno > stato.oggi;
    const report = conReport.has(giorno);
    const titolo = `${GIORNI_LUNGHI[(primo + g - 1) % 7]} ${g} ${MESI[m - 1]}${giorno === stato.oggi ? ", oggi" : ""}`;
    const daCaricare = giorno === stato.oggi && s && !sedutaDiOggiCaricata();   // decisione 54
    const righe = [s ? (s.tipo === "partita" ? "partita" : `allenamento, ${s.md}`) : "nessuna seduta",
      report ? "report di Vice pronto" : (futuro ? "non ancora" : daCaricare ? "seduta da caricare" : "nessun report")];
    const b = crea("button", {
      type: "button", class: "cal-giorno", disabled: futuro, "aria-label": [titolo, ...righe].join(", "),
      dataset: { giorno, tip: `<div class="tip"><strong>${escapeHtml(titolo)}</strong>${righe.map(escapeHtml).join("<br>")}</div>` },
      onclick: () => emetti("apri-giorno", giorno),
      "aria-current": giorno === stato.giorno ? "date" : null,
    }, crea("span", { class: "cal-numero" }, String(g)), crea("span", { class: "cal-punto", "aria-hidden": "true" }));
    b.classList.toggle("partita", s?.tipo === "partita");
    b.classList.toggle("con-report", report);
    b.classList.toggle("oggi", giorno === stato.oggi);
    riga.append(crea("span", { role: "gridcell" }, b));
    if ((primo + g) % 7 === 0) { griglia.append(riga); riga = crea("div", { class: "cal-riga", role: "row" }); }
  }
  if (riga.childElementCount) griglia.append(riga);
  el.replaceChildren(griglia);
}

export function avviaCalendario() {
  const pannello = $("#calendario"), velo = $("#velo"), apri = $("#apri-calendario");
  const mostra = (si) => {
    if (pannello.hidden === !si) return;
    if (si) { emetti("pannello", "calendario"); mese = meseDi(stato.giorno || stato.oggi); disegna(); }
    pannello.hidden = !si; velo.hidden = !si;
    apri.setAttribute("aria-expanded", String(si));
    if (si) (pannello.querySelector(".cal-giorno[aria-current]") || pannello.querySelector(".cal-giorno.oggi") || $("#chiudi-calendario")).focus();
  };
  apri.addEventListener("click", () => mostra(pannello.hidden));
  $("#chiudi-calendario").addEventListener("click", () => mostra(false));
  velo.addEventListener("click", () => mostra(false));
  $("#mese-prima").addEventListener("click", () => { mese = sposta(mese, -1); disegna(); });
  $("#mese-dopo").addEventListener("click", () => { mese = sposta(mese, 1); disegna(); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") mostra(false); });
  return { chiudi: () => mostra(false), ridisegna: disegna, mostra };
}
