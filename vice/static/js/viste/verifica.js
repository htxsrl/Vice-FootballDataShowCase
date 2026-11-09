// Forma "verifica" (V9): le prove che i numeri sono giusti, cioè le schede della replica dell'articolo che
// descrive i dati del club. Fino al 06/11/2026 c'era anche il confronto con SkillCorner (tolto, decisione 57).
import { crea } from "../util.js";

export function disegnaVerifica(contenitore, spec) {
  const schede = crea("div", { class: "schede" });
  for (const s of spec.schede) {
    schede.append(crea("div", { class: "scheda", dataset: { evidenza: s.evidenza } },
      crea("span", { class: "scheda-titolo", testo: s.titolo }),
      crea("strong", { testo: s.valore }),
      crea("span", { testo: s.testo })));
  }
  contenitore.append(crea("h3", { class: "sotto-titolo", testo: `La replica dell'articolo${spec.articolo ? ` (${spec.articolo})` : ""}` }), schede);
  return {
    accendi(sel) {
      let trovato = false;
      schede.querySelectorAll(".scheda").forEach((s) => {
        const on = Boolean(sel?.evidenza) && s.dataset.evidenza === sel.evidenza;
        s.classList.toggle("accesa", on);
        trovato ||= on;
      });
      return trovato;
    },
    ridisegna() {},
    ridimensiona() {},
    distruggi() {},
  };
}
