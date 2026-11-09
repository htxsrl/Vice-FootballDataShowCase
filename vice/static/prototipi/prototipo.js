// Vice — prototipo della lavagna (M4.0), temi chiaro e scuro (decisione 38). Dati veri del 18/04/2024 da dati.json;
// la risposta di Vice è un esempio scritto a mano con gli stessi numeri.

const POSIZIONI = ["molto sotto", "sotto", "dentro", "sopra", "molto sopra"];
const FRECCIA = { "molto sotto": "↓↓", sotto: "↓", dentro: "", sopra: "↑", "molto sopra": "↑↑" };
const VAR_POS = { "molto sotto": "--molto-sotto", sotto: "--sotto", dentro: "--dentro", sopra: "--sopra", "molto sopra": "--molto-sopra" };
const FONT = ["400 16px 'Schibsted Grotesk'", "700 16px 'Schibsted Grotesk'", "400 16px Newsreader", "600 16px Newsreader"];
const TEMI = ["chiaro", "scuro"];   // decisione 38: chiaro predefinito

let D = null;          // dati.json
let grafico = null;    // istanza ECharts
let scelto = null;     // id del giocatore evidenziato (da citazione o clic)
let linguaggio = "preparatore";

const $ = (s) => document.querySelector(s);
const css = (nome) => getComputedStyle(document.body).getPropertyValue(nome).trim();
const cognome = (nome) => nome.split(" ").slice(1).join(" ");
const dataIt = (iso) => { const [a, m, g] = iso.split("-"); return `${g}/${m}`; };
const giornoSettimana = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("it-IT", { weekday: "long" });
const mdIt = (md) => (md === 0 ? "MD" : md > 0 ? `MD+${md}` : `MD${md}`);
const num = (x) => x.toLocaleString("it-IT");

// ---------- risposte d'esempio: testo a segmenti, citazioni legate ai giocatori ----------
const EVIDENZE = {
  E1: { id: 9, descr: "Cortese, HSR del 18/04/2024: 658 m; fascia abituale MD-2 tra 100 e 550 m (P10-P90)" },
  E2: { id: 15, descr: "Tosi, HSR del 18/04/2024: 594 m; fascia abituale MD-2 tra 118 e 496 m (P10-P90)" },
  E3: { id: 11, descr: "Melis, HSR del 18/04/2024: 449 m; fascia abituale MD-2 tra 76 e 422 m (P10-P90)" },
  E4: { id: 14, descr: "Longo, HSR del 18/04/2024: 430 m; fascia abituale MD-2 tra 80 e 403 m (P10-P90)" },
  E5: { id: 12, descr: "Ghio, HSR del 18/04/2024: 183 m; fascia abituale MD-2 tra 40 e 161 m (P10-P90)" },
  E6: { id: 6, descr: "Benedetti, HSR del 18/04/2024: 24 m; fascia abituale MD-2 tra 47 e 230 m (P10-P90)" },
  E7: { id: 19, descr: "Porcu, HSR del 18/04/2024: 107 m; fascia abituale MD-2 tra 118 e 511 m (P10-P90)" },
  E8: { id: 9, descr: "Cortese, fascia centrale MD-2 (P25-P75): tra 172 e 490 m" },
};

// [testo, citazione?] — il numero davanti alla citazione si evidenzia insieme alla riga del grafico
const RISPOSTE = {
  preparatore: {
    numeri: 7,
    paragrafi: [
      [["Oggi è MD-2: mancano due giorni alla partita del 20/04. In alta velocità, cioè i metri oltre 19,8 km/h, cinque giocatori sono molto sopra la loro fascia abituale per questo giorno: Cortese con "],
       ["658 m", "E1"], [", Tosi con "], ["594 m", "E2"], [", Melis con "], ["449 m", "E3"], [", Longo con "], ["430 m", "E4"], [" e Ghio con "], ["183 m", "E5"], ["."]],
      [["Dall'altra parte Benedetti è molto sotto, con "], ["24 m", "E6"], [", e Porcu è sotto, con "], ["107 m", "E7"], [". Gli altri otto sono dentro la fascia."]],
      [["Sopra non vuol dire meglio: è la distanza dal carico abituale di ciascuno, non dal programma della seduta, che Vice non conosce."], null, "metodo"],
    ],
  },
  allenatore: {
    numeri: 0,
    paragrafi: [
      [["Oggi cinque giocatori hanno fatto molti più metri veloci del solito: "], ["Cortese", "E1"], [", "], ["Tosi", "E2"], [", "], ["Melis", "E3"], [", "], ["Longo", "E4"], [" e "], ["Ghio", "E5"],
       [". "], ["Benedetti", "E6"], [" ne ha fatti molti meno. Gli altri sono vicini al loro solito."]],
      [["Il solito è quello di ciascuno in questo giorno della settimana, non un obiettivo."], null, "metodo"],
    ],
  },
  giocatore: {
    numeri: 3,
    paragrafi: [
      [["Versione per un giocatore solo, senza confronti con i compagni: qui Lorenzo Cortese."], null, "metodo"],
      [["Lorenzo, oggi hai fatto "], ["658 m", "E1"], [" oltre i 19,8 km/h. Nei tuoi allenamenti a due giorni dalla partita, la metà centrale delle sedute sta tra "], ["172 e 490 m", "E8"], [": oggi sei andato oltre il tuo solito."]],
      [["Non è un giudizio: è un dato da guardare insieme al preparatore."]],
    ],
  },
};

function disegnaRisposta() {
  const r = RISPOSTE[linguaggio];
  const box = $("#risposta");
  box.replaceChildren();
  let citazioni = 0;
  for (const par of r.paragrafi) {
    const p = document.createElement("p");
    if (par[2] === "metodo") p.className = "metodo";
    const segmenti = par[1] === null ? [par[0]] : par;
    for (const seg of segmenti) {
      if (!Array.isArray(seg)) continue;
      const [testo, e] = seg;
      if (!e) { p.append(testo); continue; }
      citazioni += 1;
      const dato = document.createElement("span");
      dato.className = "dato";
      dato.dataset.e = e;
      dato.textContent = testo;
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cita";
      chip.dataset.e = e;
      chip.textContent = e;
      chip.title = EVIDENZE[e].descr;
      chip.setAttribute("aria-pressed", "false");
      chip.addEventListener("click", () => scegli(scelto === EVIDENZE[e].id ? null : EVIDENZE[e].id));
      p.append(dato, " ", chip);
    }
    box.append(p);
  }
  $("#badge").textContent = r.numeri > 0
    ? `${r.numeri} numeri su ${r.numeri} verificati sui dati, ${citazioni} citazioni`
    : `Nessun numero da verificare, ${citazioni} citazioni ai dati`;
  aggiornaScelto();
}

// ---------- selezione condivisa: citazione ↔ grafico ↔ griglia ----------
function scegli(id) {
  scelto = id;
  aggiornaScelto();
  disegnaSeduta();
}
function aggiornaScelto() {
  document.querySelectorAll(".cita").forEach((c) => {
    const on = scelto !== null && EVIDENZE[c.dataset.e].id === scelto;
    c.setAttribute("aria-pressed", String(on));
  });
  document.querySelectorAll(".dato").forEach((d) => {
    d.classList.toggle("segnato", scelto !== null && EVIDENZE[d.dataset.e].id === scelto);
  });
  document.querySelectorAll(".riga-griglia").forEach((r) => {
    r.classList.toggle("acceso", Number(r.dataset.id) === scelto);
  });
}

// ---------- testata: oggi e striscia della stagione ----------
function disegnaOggi() {
  $("#oggi-giorno").textContent = `${giornoSettimana(D.oggi)} ${dataIt(D.oggi)}/${D.oggi.slice(0, 4)}`;
  $("#oggi-md").textContent = mdIt(D.giorno_md);
  $("#oggi-partita").textContent = `Ultima partita ${dataIt(D.ultima_partita)}, prossima ${giornoSettimana(D.prossima_partita)} ${dataIt(D.prossima_partita)}`;
}

function disegnaStriscia() {
  const svg = $("#striscia");
  const W = Math.max(svg.clientWidth, 200);
  const H = 34;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "xMinYMid meet");
  const t = (iso) => new Date(`${iso}T12:00:00`).getTime();
  const t0 = t(D.calendario[0].data);
  const t1 = t(D.calendario[D.calendario.length - 1].data);
  const x = (iso) => 4 + ((t(iso) - t0) / (t1 - t0)) * (W - 8);
  const oggi = t(D.oggi);
  const ns = "http://www.w3.org/2000/svg";
  const el = (tag, attrs) => { const e = document.createElementNS(ns, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  svg.replaceChildren();

  // la settimana di oggi: dall'ultima partita alla prossima
  svg.append(el("rect", { x: x(D.ultima_partita), y: 0, width: x(D.prossima_partita) - x(D.ultima_partita), height: 24, fill: css("--evidenzia-velo"), rx: 2 }));
  svg.append(el("line", { x1: 0, x2: W, y1: 22.5, y2: 22.5, stroke: css("--linea"), "stroke-width": 1 }));

  for (const s of D.calendario) {
    const passato = t(s.data) <= oggi;
    const xi = x(s.data);
    if (s.tipo === "partita") {
      if (passato) svg.append(el("line", { x1: xi, x2: xi, y1: 5, y2: 22, stroke: css("--inchiostro"), "stroke-width": 2, "stroke-linecap": "round" }));
      else svg.append(el("circle", { cx: xi, cy: 14, r: 2.6, fill: "none", stroke: css("--tenue"), "stroke-width": 1.4 }));
    } else if (passato) {
      svg.append(el("line", { x1: xi, x2: xi, y1: 15, y2: 22, stroke: css("--linea-forte"), "stroke-width": 1.2 }));
    }
  }
  // oggi
  const xo = x(D.oggi);
  svg.append(el("path", { d: `M${xo - 5} 0 L${xo + 5} 0 L${xo} 6 Z`, fill: css("--inchiostro") }));
  svg.append(el("line", { x1: xo, x2: xo, y1: 4, y2: 24, stroke: css("--inchiostro"), "stroke-width": 1.5, "stroke-dasharray": "2 2" }));

  // mesi
  const mesi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const d = new Date(t0); d.setDate(1); d.setMonth(d.getMonth() + 1);
  while (d.getTime() <= t1) {
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    const xm = x(iso);
    svg.append(el("line", { x1: xm, x2: xm, y1: 22, y2: 26, stroke: css("--linea-forte"), "stroke-width": 1 }));
    const tx = el("text", { x: xm + 3, y: 33, fill: css("--tenue"), "font-size": 10, "font-family": css("--font-ui") });
    tx.textContent = mesi[d.getMonth()];
    svg.append(tx);
    d.setMonth(d.getMonth() + 1);
  }
}

// ---------- V2: la seduta di oggi contro la fascia di ciascuno ----------
function disegnaSeduta() {
  const righe = D.seduta_hsr;
  const C = {
    inchiostro: css("--inchiostro"), secondario: css("--secondario"), tenue: css("--tenue"), linea: css("--linea"),
    superficie: css("--superficie"), larga: css("--banda-larga"), centrale: css("--banda-centrale"), mediana: css("--mediana"),
    gettone: css("--gettone"), gettoneTesto: css("--gettone-testo"), velo: css("--evidenzia-velo"), evidenzia: css("--evidenzia"),
    ui: css("--font-ui"), numeri: css("--font-numeri"),
  };
  const colore = Object.fromEntries(POSIZIONI.map((p) => [p, css(VAR_POS[p])]));
  const tema = document.body.dataset.tema;
  const massimo = Math.ceil(Math.max(...righe.map((r) => Math.max(r.valore, r.p90))) / 100) * 100 + 100;
  const stretto = $("#grafico-seduta").clientWidth < 560;   // telefono: meno tacche, etichette più vicine
  const sinistra = stretto ? 132 : 178;

  const opzione = {
    animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
    animationDuration: 500,
    grid: { left: sinistra, right: stretto ? 12 : 24, top: 18, bottom: 46 },
    textStyle: { fontFamily: C.ui },
    xAxis: {
      type: "value", min: 0, max: massimo, interval: stretto ? 200 : 100,
      name: "metri oltre 19,8 km/h", nameLocation: "middle", nameGap: 30,
      nameTextStyle: { color: C.secondario, fontSize: 12, fontFamily: C.ui },
      axisLabel: { color: C.tenue, fontSize: 12, fontFamily: C.numeri },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: C.linea, width: 1 } },
    },
    yAxis: {
      type: "category", inverse: true, data: righe.map((_, i) => String(i)),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { show: false },
    },
    tooltip: {
      trigger: "item", confine: true,
      backgroundColor: C.superficie, borderColor: C.linea, borderWidth: 1, padding: [8, 12],
      textStyle: { color: C.inchiostro, fontFamily: C.ui },
      extraCssText: `box-shadow: ${css("--ombra-suggerimento")}; border-radius: 6px;`,
      formatter: (p) => {
        const r = righe[p.data[0]];
        const pos = r.posizione === "dentro" ? "dentro la fascia" : r.posizione;
        return `<div class="suggerimento"><strong>${r.numero} ${r.nome}</strong>`
          + `<span class="val">${num(r.valore)} m</span> ${FRECCIA[r.posizione]} ${pos}<br>`
          + `fascia centrale P25-P75: ${num(r.p25)}-${num(r.p75)} m<br>`
          + `fascia larga P10-P90: ${num(r.p10)}-${num(r.p90)} m<br>`
          + `mediana: ${num(r.p50)} m</div>`;
      },
    },
    series: [{
      type: "custom",
      data: righe.map((r, i) => [i, r.p10, r.p25, r.p50, r.p75, r.p90, r.valore]),
      encode: { x: [1, 5, 6], y: 0 },
      renderItem: (params, api) => {
        const i = api.value(0);
        const r = righe[i];
        const cs = params.coordSys;
        const y = api.coord([0, i])[1];
        const passo = api.size([0, 1])[1];
        const X = (v) => api.coord([v, i])[0];
        const h = 10;
        const figli = [];
        const xg = cs.x - sinistra + 18;   // gettone col numero e cognome, a sinistra della riga
        if (r.id === scelto) {
          figli.push({ type: "rect", silent: true, shape: { x: xg - 14, y: y - passo / 2 + 1, width: cs.x + cs.width - xg + 14, height: passo - 2, r: 3 }, style: { fill: C.velo } });
        }
        // bersaglio per il passaggio del mouse più grande del segno: tutta la riga, nome compreso
        figli.push({ type: "rect", shape: { x: xg - 14, y: y - passo / 2, width: cs.x + cs.width - xg + 14, height: passo }, style: { fill: "rgba(0,0,0,0)" } });
        figli.push({ type: "circle", shape: { cx: xg, cy: y, r: 10.5 }, style: { fill: C.gettone } });
        figli.push({ type: "text", style: { text: String(r.numero), x: xg, y: y + 0.5, align: "center", verticalAlign: "middle", fill: C.gettoneTesto, font: `700 11px ${C.numeri}` } });
        figli.push({ type: "text", style: { text: cognome(r.nome), x: xg + 19, y, align: "left", verticalAlign: "middle", fill: C.inchiostro,
          font: `${r.id === scelto ? 700 : 400} 13.5px ${C.ui}` } });
        figli.push({ type: "rect", shape: { x: X(r.p10), y: y - h / 2, width: X(r.p90) - X(r.p10), height: h, r: h / 2 }, style: { fill: C.larga } });
        figli.push({ type: "rect", shape: { x: X(r.p25), y: y - h / 2, width: X(r.p75) - X(r.p25), height: h, r: 2 }, style: { fill: C.centrale } });
        figli.push({ type: "line", shape: { x1: X(r.p50), y1: y - 9, x2: X(r.p50), y2: y + 9 }, style: { stroke: C.mediana, lineWidth: 2 } });
        const xv = X(r.valore);
        if (tema === "scuro" && r.posizione !== "dentro") {
          // cerchio da moviola sui fuori fascia
          figli.push({ type: "circle", shape: { cx: xv, cy: y, r: 11 }, style: { fill: "none", stroke: C.evidenzia, lineWidth: 1.2, lineDash: [3, 2] } });
        }
        figli.push({ type: "circle", shape: { cx: xv, cy: y, r: 6.5 }, style: { fill: colore[r.posizione], stroke: C.superficie, lineWidth: 2 } });
        if (r.posizione !== "dentro") {
          const testo = `${num(r.valore)} ${FRECCIA[r.posizione]}`;
          const largo = testo.length * 8 + 16;   // stima della larghezza dell'etichetta
          const sotto = r.posizione.endsWith("sotto");
          const aSinistra = (sotto && xv - cs.x > largo) || xv + largo > cs.x + cs.width + 12;
          figli.push({
            type: "text",
            style: {
              text: testo, x: aSinistra ? xv - (tema === "scuro" ? 16 : 12) : xv + (tema === "scuro" ? 16 : 12), y,
              align: aSinistra ? "right" : "left", verticalAlign: "middle", fill: C.inchiostro,
              font: `700 13px ${C.numeri}`,
            },
          });
        }
        return { type: "group", children: figli };
      },
    }],
  };
  if (!grafico) {
    grafico = echarts.init($("#grafico-seduta"), null, { renderer: "canvas" });
    grafico.on("click", (p) => { const r = righe[p.data[0]]; scegli(scelto === r.id ? null : r.id); });
    addEventListener("resize", () => { grafico.resize(); disegnaStriscia(); });
  }
  grafico.setOption(opzione, true);
}

function disegnaLegenda() {
  const ul = $("#legenda");
  ul.replaceChildren();
  const voce = (html) => { const li = document.createElement("li"); li.innerHTML = html; ul.append(li); };
  voce(`<span class="barra" style="background:${css("--banda-larga")}"></span>fascia larga P10-P90`);
  voce(`<span class="barra" style="background:${css("--banda-centrale")}"></span>fascia centrale P25-P75`);
  voce(`<span class="tacca"></span>mediana`);
  for (const p of POSIZIONI) {
    const testo = p === "dentro" ? "dentro la fascia" : p;
    voce(`<span class="punto" style="background:${css(VAR_POS[p])}"></span><span class="freccia">${FRECCIA[p] || "·"}</span>${testo}`);
  }
}

// ---------- V1: la settimana in un colpo d'occhio ----------
function disegnaGriglia() {
  const g = $("#griglia");
  g.replaceChildren();
  const giorni = D.griglia_hsr.giorni;
  const testa = document.createElement("div");
  testa.className = "intestazione";
  g.append(testa);
  for (const d of giorni) {
    const h = document.createElement("div");
    h.className = "intestazione" + (d.data === D.oggi ? " oggi-col" : "");
    h.innerHTML = `<b>${mdIt(d.md)}</b><span>${d.data === D.oggi ? "oggi" : dataIt(d.data)}</span>`;
    g.append(h);
  }
  for (const gi of D.griglia_hsr.giocatori) {
    const riga = document.createElement("div");
    riga.className = "riga-griglia";
    riga.dataset.id = gi.id;
    riga.style.display = "contents";
    const nome = document.createElement("div");
    nome.className = "nome";
    nome.innerHTML = `<span class="gettone">${gi.numero}</span>${cognome(gi.nome)}`;
    riga.append(nome);
    for (const d of giorni) {
      const c = document.createElement("div");
      const pos = gi.celle[d.data];
      c.className = "cella" + (pos ? "" : " vuota");
      if (pos) {
        c.dataset.pos = pos;
        c.textContent = FRECCIA[pos] || "·";
        c.title = `${gi.nome}, ${mdIt(d.md)} ${dataIt(d.data)}: ${pos === "dentro" ? "dentro la fascia" : pos}`;
      } else {
        c.title = `${gi.nome}, ${mdIt(d.md)} ${dataIt(d.data)}: non in seduta`;
      }
      riga.append(c);
    }
    riga.addEventListener("click", () => scegli(scelto === gi.id ? null : gi.id));
    g.append(riga);
  }
  aggiornaScelto();
}

// ---------- tema, linguaggi, palco ----------
async function applicaTema(t) {
  document.body.dataset.tema = t;
  document.querySelectorAll(".commutatore button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.t === t)));
  try { await Promise.all(FONT.map((f) => document.fonts.load(f))); } catch { /* il disegno va avanti coi font di riserva */ }
  disegnaTutto();
}
function disegnaTutto() {
  disegnaOggi(); disegnaStriscia(); disegnaSeduta(); disegnaLegenda(); disegnaGriglia(); disegnaRisposta();
}

document.querySelectorAll(".commutatore button").forEach((b) => b.addEventListener("click", () => {
  applicaTema(b.dataset.t);
  try { localStorage.setItem("vice-tema", b.dataset.t); } catch { /* senza memoria locale si riparte dal chiaro */ }
}));
document.querySelectorAll(".linguaggi button").forEach((b) => b.addEventListener("click", () => {
  linguaggio = b.textContent.trim().toLowerCase();
  document.querySelectorAll(".linguaggi button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  disegnaRisposta();
}));
$("#palco").addEventListener("click", (e) => {
  const on = document.body.classList.toggle("modo-palco");
  e.currentTarget.setAttribute("aria-pressed", String(on));
  requestAnimationFrame(() => { grafico.resize(); disegnaStriscia(); });
});

(async () => {
  D = await (await fetch("dati.json")).json();
  const params = new URLSearchParams(location.search);
  let t = params.get("tema");
  if (!t) { try { t = localStorage.getItem("vice-tema"); } catch { t = null; } }
  await applicaTema(TEMI.includes(t) ? t : "chiaro");
  if (params.get("scelto")) scegli(Number(params.get("scelto")));
  if (params.get("palco")) $("#palco").click();
})();
