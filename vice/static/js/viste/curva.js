// Forma "curva" (V5 la forma della settimana): un giorno del microciclo per colonna. Bande delle settimane
// passate, linea tratteggiata della settimana tipo, linea piena della settimana in corso con i punti colorati
// per posizione. I giorni non ancora arrivati mostrano solo la settimana tipo; i giorni senza seduta interrompono
// la linea della settimana in corso.
import { css, FRECCIA, numero, posizioneTip, POSIZIONI, riduciMovimento, rigaTip, VAR_POS } from "../util.js";
import { temaCorrente } from "../tema.js";

export function disegnaCurva(contenitore, spec, { onAzione } = {}) {
  const giorni = spec.giorni;
  let acceso = null;
  const div = document.createElement("div");
  div.className = "grafico";
  div.style.height = "440px";
  div.setAttribute("role", "img");
  div.setAttribute("aria-label", `${spec.titolo}. ` + giorni.filter((g) => g.valore != null)
    .map((g) => `${g.md} ${g.valore_testo}, ${g.posizione === "dentro" ? "dentro la fascia" : g.posizione}`).join("; "));
  contenitore.append(div);
  const grafico = echarts.init(div, null, { renderer: "canvas" });

  function opzione() {
    const C = {
      inchiostro: css("--inchiostro"), secondario: css("--secondario"), tenue: css("--tenue"), linea: css("--linea"),
      superficie: css("--superficie"), larga: css("--banda-larga"), centrale: css("--banda-centrale"),
      velo: css("--evidenzia-velo"), evidenzia: css("--evidenzia"), ui: css("--font-ui"), numeri: css("--font-numeri"),
    };
    const colore = Object.fromEntries(POSIZIONI.map((p) => [p, css(VAR_POS[p])]));
    const scuro = temaCorrente() === "scuro";
    const a = spec.asse;
    const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const tip = (g) => `<div class="tip"><strong>${esc(g.md)}${g.data_testo ? ` ${esc(g.data_testo)}` : ""}</strong>`
      + (g.valore != null ? `<span class="val">${esc(g.valore_testo)}</span> ${FRECCIA[g.posizione] || ""} ${posizioneTip(g.posizione)}<br>` : "")
      + (g.tipico != null ? `<b>settimana tipo</b>: ${numero(g.tipico)}<br>` : "")
      + (g.dettagli || []).map(rigaTip).join("<br>") + "</div>";
    return {
      animation: !riduciMovimento(), animationDuration: 450,
      grid: { left: 64, right: 24, top: 24, bottom: 56 },
      textStyle: { fontFamily: C.ui },
      xAxis: {
        type: "category", data: giorni.map((g) => g.md),
        axisLabel: { color: C.inchiostro, fontFamily: C.numeri, fontWeight: 700, fontSize: 13,
          formatter: (v, i) => (giorni[i].data_testo ? `${v}\n{d|${giorni[i].data_testo}}` : `${v}\n{d|${giorni[i].futuro ? "da venire" : "—"}}`),
          rich: { d: { color: C.tenue, fontWeight: 400, fontSize: 12, padding: [4, 0, 0, 0] } } },
        axisLine: { lineStyle: { color: C.linea } }, axisTick: { show: false },
      },
      yAxis: {
        type: "value", min: a.min, max: a.max, interval: a.passo, name: a.nome, nameLocation: "middle", nameGap: 48,
        nameTextStyle: { color: C.secondario, fontSize: 12 },
        axisLabel: { color: C.tenue, fontFamily: C.numeri, formatter: (v) => numero(v) },
        splitLine: { lineStyle: { color: C.linea } },
      },
      tooltip: {
        trigger: "item", confine: true, backgroundColor: C.superficie, borderColor: C.linea, borderWidth: 1, padding: [8, 12],
        textStyle: { color: C.inchiostro, fontFamily: C.ui }, extraCssText: `box-shadow: ${css("--ombra-suggerimento")}; border-radius: 6px;`,
        formatter: (p) => tip(giorni[p.dataIndex]),
      },
      series: [
        {
          type: "custom", z: 1,
          data: giorni.map((g, i) => [i, g.fascia?.p10 ?? g.tipico ?? 0, g.fascia?.p90 ?? g.tipico ?? 0]),
          encode: { x: 0, y: [1, 2] },
          renderItem: (params, api) => {
            const i = api.value(0);
            const g = giorni[i];
            const x = api.coord([i, 0])[0];
            const passo = api.size([1, 0])[0];
            const cs = params.coordSys;
            const figli = [];
            if (i === acceso) figli.push({ type: "rect", silent: true, shape: { x: x - passo / 2 + 2, y: cs.y, width: passo - 4, height: cs.height, r: 3 }, style: { fill: C.velo } });
            figli.push({ type: "rect", shape: { x: x - passo / 2, y: cs.y, width: passo, height: cs.height }, style: { fill: "rgba(0,0,0,0)" } });
            if (g.fascia) {
              const Y = (v) => api.coord([i, v])[1];
              const w = Math.min(30, passo * 0.45);
              figli.push({ type: "rect", shape: { x: x - w / 2, y: Y(g.fascia.p90), width: w, height: Math.max(Y(g.fascia.p10) - Y(g.fascia.p90), 1), r: 3 }, style: { fill: C.larga } });
              figli.push({ type: "rect", shape: { x: x - w / 2, y: Y(g.fascia.p75), width: w, height: Math.max(Y(g.fascia.p25) - Y(g.fascia.p75), 1), r: 2 }, style: { fill: C.centrale } });
            }
            return { type: "group", children: figli };
          },
        },
        {
          type: "line", name: "settimana tipo", z: 2, connectNulls: true, symbol: "circle", symbolSize: 7,
          data: giorni.map((g) => g.tipico ?? null),
          lineStyle: { color: C.secondario, width: 1.5, type: [5, 4] },
          itemStyle: { color: C.superficie, borderColor: C.secondario, borderWidth: 1.5 },
          tooltip: { show: true },
        },
        {
          // niente linea sopra i giorni senza seduta: sembrerebbe che lì ci siano dati (08/11/2026)
          type: "line", name: "questa settimana", z: 3, connectNulls: false, symbol: "circle", symbolSize: 14,
          data: giorni.map((g) => (g.valore != null ? {
            value: g.valore,
            itemStyle: { color: colore[g.posizione] || C.inchiostro, borderColor: C.superficie, borderWidth: 2 },
            label: g.posizione !== "dentro" ? { show: true, position: "right", distance: 10, formatter: `${numero(g.valore)} ${FRECCIA[g.posizione]}`,
              color: C.inchiostro, fontFamily: C.numeri, fontWeight: 700, fontSize: 13 } : { show: false },
          } : null)),
          lineStyle: { color: C.inchiostro, width: 2 },
          markPoint: scuro ? { silent: true, symbol: "circle", symbolSize: 26, itemStyle: { color: "transparent", borderColor: C.evidenzia, borderWidth: 1.2, borderType: [3, 2] },
            data: giorni.map((g, i) => (g.valore != null && g.posizione !== "dentro" ? { coord: [i, g.valore] } : null)).filter(Boolean) } : undefined,
        },
      ],
    };
  }

  grafico.setOption(opzione());
  grafico.on("click", (p) => { const g = giorni[p.dataIndex]; if (g?.azione && onAzione) onAzione(g); });
  return {
    accendi(sel) {
      const i = sel ? giorni.findIndex((g) => (sel.evidenza && g.evidenza === sel.evidenza) || (sel.chiave && g.chiave === sel.chiave)) : -1;
      acceso = i >= 0 ? i : null;
      grafico.setOption(opzione(), true);
      return i >= 0;
    },
    ridisegna() { grafico.setOption(opzione(), true); },
    ridimensiona() { grafico.resize(); },
    distruggi() { grafico.dispose(); },
  };
}

export function legendaCurva() {
  const ul = document.createElement("ul");
  ul.className = "legenda";
  const voce = (html) => { const li = document.createElement("li"); li.innerHTML = html; ul.append(li); };
  voce(`<span class="barra" style="background:var(--banda-larga)"></span>settimane passate, P10-P90`);
  voce(`<span class="barra" style="background:var(--banda-centrale)"></span>P25-P75`);
  voce(`<span class="tacca" style="background:none;border-left:2px dashed var(--secondario);transform:rotate(90deg)"></span>settimana tipo`);
  for (const p of POSIZIONI) voce(`<span class="punto" style="background:var(${VAR_POS[p]})"></span><span class="freccia">${FRECCIA[p]}</span>${p === "dentro" ? "dentro la fascia" : p}`);
  return ul;
}
