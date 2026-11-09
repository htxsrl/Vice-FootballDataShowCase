// Forma "fasce" (V2 la seduta): una riga per giocatore, fascia larga e centrale come barre, mediana come
// trattino, valore del giorno come punto colorato per posizione. Etichette dirette solo sui fuori fascia.
// I numeri arrivano già calcolati dal server: qui si disegna e basta. Una citazione di squadra (una chiave in
// `spec.chiavi_squadra`) accende tutte le righe; con `spec.etichette === "tutte"` anche i valori dentro la fascia
// hanno l'etichetta, più tenue (la vista allenamento ↔ partita, dove la percentuale è la risposta).
import { css, FRECCIA, numero, posizioneTip, POSIZIONI, riduciMovimento, rigaTip, VAR_POS } from "../util.js";
import { temaCorrente } from "../tema.js";

const ALTEZZA_RIGA = 32;

export function disegnaFasce(contenitore, spec, { onScelta } = {}) {
  const righe = spec.righe;
  let acceso = righe.findIndex((r) => r.acceso);   // la riga accesa (indice, o "tutte"), anche dalla specifica
  if (acceso < 0) acceso = null;
  const tutteLeEtichette = spec.etichette === "tutte";
  const div = document.createElement("div");
  div.className = "grafico";
  div.style.height = `${righe.length * ALTEZZA_RIGA + 70}px`;
  div.setAttribute("role", "img");
  div.setAttribute("aria-label", `${spec.titolo}. ${righe.map((r) => `${r.giocatore ? r.giocatore.cognome : r.etichetta} ${r.valore_testo}${r.posizione === "neutra" ? "" : `, ${r.posizione}`}`).join("; ")}`);
  contenitore.append(div);
  const grafico = echarts.init(div, null, { renderer: "canvas" });

  function opzione() {
    const C = {
      inchiostro: css("--inchiostro"), secondario: css("--secondario"), tenue: css("--tenue"), linea: css("--linea"),
      superficie: css("--superficie"), larga: css("--banda-larga"), centrale: css("--banda-centrale"), mediana: css("--mediana"),
      gettone: css("--gettone"), gettoneTesto: css("--gettone-testo"), velo: css("--evidenzia-velo"), evidenzia: css("--evidenzia"),
      ui: css("--font-ui"), numeri: css("--font-numeri"),
    };
    const colore = Object.fromEntries([...POSIZIONI, "senza fascia"].map((p) => [p, css(VAR_POS[p])]));
    const scuro = temaCorrente() === "scuro";
    const stretto = div.clientWidth < 560;
    const sinistra = stretto ? 132 : 178;
    const a = spec.asse;
    const intervallo = stretto ? a.passo * 2 : a.passo;
    // l'ultima etichetta solo se cade su una tacca: altrimenti «400 500» finiscono attaccate sul telefono
    const ultima = Math.abs(a.max / intervallo - Math.round(a.max / intervallo)) < 1e-9;
    return {
      animation: !riduciMovimento(), animationDuration: 450,
      grid: { left: sinistra, right: stretto ? 12 : 24, top: spec.riferimenti ? 30 : 14, bottom: 46 },
      textStyle: { fontFamily: C.ui },
      xAxis: {
        type: "value", min: a.min, max: a.max, interval: intervallo,
        name: a.nome, nameLocation: "middle", nameGap: 30,
        nameTextStyle: { color: C.secondario, fontSize: 12, fontFamily: C.ui },
        axisLabel: { color: C.tenue, fontSize: 12, fontFamily: C.numeri, formatter: (v) => numero(v), showMaxLabel: ultima },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: C.linea, width: 1 } },
      },
      yAxis: { type: "category", inverse: true, data: righe.map((_, i) => String(i)), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false } },
      tooltip: {
        trigger: "item", confine: true, backgroundColor: C.superficie, borderColor: C.linea, borderWidth: 1, padding: [8, 12],
        textStyle: { color: C.inchiostro, fontFamily: C.ui },
        extraCssText: `box-shadow: ${css("--ombra-suggerimento")}; border-radius: 6px;`,
        formatter: (p) => {
          const r = righe[p.data[0]];
          const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
          const chi = r.giocatore ? `${r.giocatore.numero} ${esc(r.giocatore.nome)}` : `${esc(r.etichetta)} ${esc(r.sotto || "")}`;
          return `<div class="tip"><strong>${chi}</strong>`
            + `<span class="val">${esc(r.valore_testo)}</span> ${FRECCIA[r.posizione] || ""} ${r.posizione === "neutra" ? "" : posizioneTip(r.posizione)}<br>`
            + r.dettagli.map(rigaTip).join("<br>") + "</div>";
        },
      },
      series: [{
        type: "custom",
        markLine: spec.riferimenti ? {
          silent: true, symbol: "none", animation: false,
          lineStyle: { color: C.secondario, type: [4, 3], width: 1.5 },
          // in alto (l'asse delle righe è rovesciato: l'inizio della linea è in cima)
          label: { position: "start", distance: 6, color: C.secondario, fontFamily: C.ui, fontSize: 12, formatter: (p) => p.name },
          data: spec.riferimenti.map((x) => ({ xAxis: x.valore, name: x.testo })),
        } : undefined,
        data: righe.map((r, i) => [i, r.fascia?.p10 ?? r.valore, r.fascia?.p90 ?? r.valore, r.valore]),
        encode: { x: [1, 2, 3], y: 0 },
        renderItem: (params, api) => {
          const i = api.value(0);
          const r = righe[i];
          const cs = params.coordSys;
          const y = api.coord([0, i])[1];
          const passo = api.size([0, 1])[1];
          const X = (v) => api.coord([v, i])[0];
          const h = 10, figli = [];
          const xg = cs.x - sinistra + 18;
          const largo = cs.x + cs.width - xg + 14;
          if (i === acceso) figli.push({ type: "rect", silent: true, shape: { x: xg - 14, y: y - passo / 2 + 1, width: largo, height: passo - 2, r: 3 }, style: { fill: C.velo } });
          // un dato di tutta la squadra: un segno dell'evidenziatore su ogni riga, senza coprire il grafico
          if (acceso === "tutte") figli.push({ type: "rect", silent: true, shape: { x: xg - 16, y: y - passo / 2 + 4, width: 4, height: passo - 8, r: 2 }, style: { fill: C.evidenzia } });
          figli.push({ type: "rect", shape: { x: xg - 14, y: y - passo / 2, width: largo, height: passo }, style: { fill: "rgba(0,0,0,0)" } });
          if (r.giocatore) {
            figli.push({ type: "circle", shape: { cx: xg, cy: y, r: 10.5 }, style: { fill: C.gettone } });
            figli.push({ type: "text", style: { text: String(r.giocatore.numero), x: xg, y: y + 0.5, align: "center", verticalAlign: "middle", fill: C.gettoneTesto, font: `700 11px ${C.numeri}` } });
            figli.push({ type: "text", style: { text: r.giocatore.cognome, x: xg + 19, y, align: "left", verticalAlign: "middle", fill: C.inchiostro, font: `${i === acceso ? 700 : 400} 13.5px ${C.ui}` } });
          } else {
            figli.push({ type: "text", style: { text: r.etichetta, x: xg - 10, y, align: "left", verticalAlign: "middle", fill: C.inchiostro, font: `${i === acceso ? 700 : 400} 13.5px ${C.numeri}` } });
            if (r.sotto) figli.push({ type: "text", style: { text: r.sotto, x: xg + 38, y, align: "left", verticalAlign: "middle", fill: C.secondario, font: `500 12px ${C.numeri}` } });
          }
          if (r.fascia) {
            const f = r.fascia;
            figli.push({ type: "rect", shape: { x: X(f.p10), y: y - h / 2, width: Math.max(X(f.p90) - X(f.p10), 1), height: h, r: h / 2 }, style: { fill: C.larga } });
            if (f.p25 != null) figli.push({ type: "rect", shape: { x: X(f.p25), y: y - h / 2, width: Math.max(X(f.p75) - X(f.p25), 1), height: h, r: 2 }, style: { fill: C.centrale, opacity: r.provvisoria ? 0.6 : 1 } });
            if (f.p50 != null) figli.push({ type: "line", shape: { x1: X(f.p50), y1: y - 9, x2: X(f.p50), y2: y + 9 }, style: { stroke: C.mediana, lineWidth: 2 } });
          }
          const xv = X(r.valore);
          const fuori = POSIZIONI.includes(r.posizione) && r.posizione !== "dentro";
          if (scuro && fuori) figli.push({ type: "circle", shape: { cx: xv, cy: y, r: 11 }, style: { fill: "none", stroke: C.evidenzia, lineWidth: 1.2, lineDash: [3, 2] } });
          figli.push({ type: "circle", shape: { cx: xv, cy: y, r: 6.5 }, style: r.posizione === "senza fascia"
            ? { fill: C.superficie, stroke: C.secondario, lineWidth: 1.5 }
            : r.posizione === "neutra" ? { fill: C.inchiostro, stroke: C.superficie, lineWidth: 2 }
              : { fill: colore[r.posizione], stroke: C.superficie, lineWidth: 2 } });
          if (r.posizione === "neutra") figli.push({ type: "text", style: { text: r.valore_testo, x: xv + 11, y, align: "left", verticalAlign: "middle", fill: C.inchiostro, font: `600 12px ${C.numeri}`, stroke: C.superficie, lineWidth: 4, strokeFirst: true } });
          const quieta = tutteLeEtichette && r.posizione === "dentro";
          if (fuori || quieta) {
            // l'etichetta in un piccolo riquadro col fondo del grafico: resta leggibile anche sopra bande e mediana
            const testo = fuori ? `${r.valore_testo ?? numero(r.valore)} ${FRECCIA[r.posizione]}` : (r.valore_testo ?? numero(r.valore));
            const ingombro = testo.length * 8 + 22;
            const sotto = r.posizione.endsWith("sotto");
            const aSinistra = (sotto && xv - cs.x > ingombro) || xv + ingombro > cs.x + cs.width + 12;
            const scarto = scuro && fuori ? 16 : 12;
            figli.push({ type: "text", z2: 5, style: { text: testo, x: aSinistra ? xv - scarto : xv + scarto, y, align: aSinistra ? "right" : "left", verticalAlign: "middle",
              fill: fuori ? C.inchiostro : C.secondario, font: `${fuori ? 700 : 500} ${fuori ? 13 : 12}px ${C.numeri}`,
              backgroundColor: C.superficie, borderColor: fuori ? C.linea : "transparent", borderWidth: 1, borderRadius: 4, padding: [2, 5, 1, 5] } });
          }
          return { type: "group", children: figli };
        },
      }],
    };
  }

  grafico.setOption(opzione());
  grafico.on("click", (p) => onScelta && onScelta(righe[p.data[0]]));
  return {
    accendi(sel) {
      if (sel?.chiave && (spec.chiavi_squadra || []).includes(sel.chiave)) {   // un dato di tutta la squadra
        acceso = "tutte";
        grafico.setOption(opzione(), true);
        return true;
      }
      const i = sel ? righe.findIndex((r) => (sel.evidenza && r.evidenza === sel.evidenza)
        || (r.giocatore && ((sel.chiave && r.chiave === sel.chiave) || (sel.giocatore_id != null && r.giocatore.id === sel.giocatore_id)))) : -1;
      acceso = i >= 0 ? i : null;
      grafico.setOption(opzione(), true);
      return i >= 0;
    },
    ridisegna() { grafico.setOption(opzione(), true); },
    ridimensiona() { grafico.resize(); grafico.setOption(opzione(), true); },
    distruggi() { grafico.dispose(); },
  };
}

export function legendaFasce(spec) {
  const ul = document.createElement("ul");
  ul.className = "legenda";
  const voce = (html) => { const li = document.createElement("li"); li.innerHTML = html; ul.append(li); };
  const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  if (spec && spec.legenda) {
    for (const x of spec.legenda) {
      const segno = {
        "barra-larga": '<span class="barra" style="background:var(--banda-larga)"></span>',
        "barra-centrale": '<span class="barra" style="background:var(--banda-centrale)"></span>',
        tacca: '<span class="tacca"></span>',
        punto: `<span class="punto" style="background:var(${x.posizione === "neutra" ? "--inchiostro" : VAR_POS[x.posizione]})"></span>`
          + (FRECCIA[x.posizione] ? `<span class="freccia">${FRECCIA[x.posizione]}</span>` : ""),
        riferimento: '<span class="tacca" style="background:none;border-left:2px dashed var(--secondario)"></span>',
      }[x.tipo] || "";
      voce(`${segno}${esc(x.testo)}`);
    }
    return ul;
  }
  voce(`<span class="barra" style="background:var(--banda-larga)"></span>fascia larga P10-P90`);
  voce(`<span class="barra" style="background:var(--banda-centrale)"></span>fascia centrale P25-P75`);
  voce(`<span class="tacca"></span>mediana`);
  for (const p of POSIZIONI) voce(`<span class="punto" style="background:var(${VAR_POS[p]})"></span><span class="freccia">${FRECCIA[p]}</span>${p === "dentro" ? "dentro la fascia" : p}`);
  return ul;
}
