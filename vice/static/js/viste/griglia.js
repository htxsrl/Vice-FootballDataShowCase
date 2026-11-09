// Forma "griglia" (V1 la settimana): giocatori × sedute del microciclo, ogni cella con colore e freccia
// della posizione rispetto alla fascia. Clic su un giocatore: diventa il soggetto della chat;
// clic su una cella: la seduta di quel giorno sulla lavagna.
import { crea, escapeHtml, FRECCIA, POSIZIONI, rigaTip, VAR_POS } from "../util.js";

export function disegnaGriglia(contenitore, spec, { onScelta, onCella } = {}) {
  const g = crea("div", { class: "griglia", role: "table", "aria-label": spec.titolo });
  // la colonna dei nomi larga quanto serve, i giorni si dividono il resto della larghezza: niente spazio
  // vuoto né celle schiacciate, con pochi o con tanti giorni. Ogni cella mostra il valore e la freccia; se è
  // stretta (telefono, settimana lunga) resta la freccia (vice.css, @container).
  g.style.gridTemplateColumns = `minmax(104px, max-content) repeat(${spec.giorni.length}, minmax(40px, 1fr))`;
  g.append(crea("div", { class: "intestazione", role: "columnheader" }));
  for (const d of spec.giorni) {
    g.append(crea("div", { class: `intestazione${d.oggi ? " oggi-col" : ""}`, role: "columnheader" },
      crea("b", { testo: d.md }), crea("span", { testo: d.oggi ? "oggi" : d.data_testo })));
  }
  const righe = [];
  for (const r of spec.righe) {
    const riga = crea("div", { class: "riga", role: "row", style: "display: contents" });
    riga.append(crea("button", { type: "button", class: "nome", "aria-label": `${r.giocatore.nome}: chiedi a Vice di lui`,
      dataset: { tip: `<div class="tip"><strong>${escapeHtml(r.giocatore.nome)}</strong>clicca per chiedere a Vice di lui</div>` },
      onclick: () => onScelta && onScelta(r) },
      crea("span", { class: "gettone", testo: String(r.giocatore.numero) }), r.giocatore.cognome));
    for (const d of spec.giorni) {
      const c = r.celle[d.data];
      if (!c) {
        riga.append(crea("div", { class: "cella vuota", dataset: { tip: `<div class="tip"><strong>${escapeHtml(r.giocatore.nome)}</strong>`
          + `<b>${escapeHtml(`${d.md} ${d.data_testo}`)}</b>: non in seduta</div>` } }));
        continue;
      }
      riga.append(crea("button", {
        type: "button", class: "cella",
        "aria-label": `${r.giocatore.nome}, ${c.dettaglio}`,
        dataset: { pos: c.posizione, evidenza: c.evidenza,
          tip: `<div class="tip"><strong>${escapeHtml(r.giocatore.nome)}</strong>${rigaTip(c.dettaglio)}</div>` },
        onclick: () => onCella && onCella(r, d, c),
      }, crea("span", { class: "v", testo: c.valore_testo }),
      FRECCIA[c.posizione] && c.posizione !== "dentro" ? crea("span", { class: "freccia", testo: FRECCIA[c.posizione] }) : null,
      crea("span", { class: "solo-segno", "aria-hidden": "true", testo: FRECCIA[c.posizione] || "" })));
    }
    g.append(riga);
    righe.push({ r, riga });
  }
  contenitore.append(g);

  return {
    accendi(sel) {
      let trovato = false;
      for (const { r, riga } of righe) {
        const suo = Boolean(sel) && ((sel.giocatore_id != null && r.giocatore.id === sel.giocatore_id)
          || Object.values(r.celle).some((c) => (sel.chiave && c.chiave === sel.chiave) || (sel.evidenza && c.evidenza === sel.evidenza)));
        riga.classList.toggle("riga-accesa", suo);
        riga.querySelectorAll(".cella").forEach((c) => c.classList.toggle("accesa", Boolean(sel?.evidenza) && c.dataset.evidenza === sel.evidenza));
        trovato ||= suo;
      }
      return trovato;
    },
    ridisegna() {}, ridimensiona() {}, distruggi() {},
  };
}

export function legendaGriglia() {
  const ul = document.createElement("ul");
  ul.className = "legenda";
  for (const p of POSIZIONI) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="punto" style="background:var(${VAR_POS[p]})"></span><span class="freccia">${FRECCIA[p]}</span>${p === "dentro" ? "dentro la fascia" : p}`;
    ul.append(li);
  }
  const li = document.createElement("li");
  li.innerHTML = `<span class="punto vuoto"></span>non in seduta`;
  ul.append(li);
  return ul;
}
