// Il glossario (decisione 46): pannello a destra con le sigle e le parole di Vice, dalla pagina
// wiki/metodi/glossario.md (vice/glossario.py). Senza velo: sullo schermo largo la chat resta visibile e si
// può leggere una risposta col glossario aperto. Si chiude con × o con Esc.
import { $, riduciMovimento } from "./util.js";

export function avviaGlossario() {
  const pannello = $("#glossario"), apri = $("#apri-glossario");
  const mostra = (si) => {
    if (pannello.hidden === !si) return;
    const dentro = pannello.contains(document.activeElement);
    pannello.hidden = !si;
    apri.setAttribute("aria-expanded", String(si));
    if (si) $("#chiudi-glossario").focus();
    else if (dentro) apri.focus();            // il fuoco torna al pulsante solo se era nel pannello
  };
  apri.addEventListener("click", () => mostra(pannello.hidden));
  $("#chiudi-glossario").addEventListener("click", () => mostra(false));
  addEventListener("keydown", (e) => { if (e.key === "Escape") mostra(false); });
  // l'indice scorre solo il pannello (non la pagina), senza cambiare l'indirizzo
  const corpo = $("#glossario-corpo");
  pannello.querySelectorAll(".glossario-indice a").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    const sezione = pannello.querySelector(a.getAttribute("href"));
    if (!sezione || !corpo) return;
    const alto = sezione.getBoundingClientRect().top - corpo.getBoundingClientRect().top + corpo.scrollTop - 8;
    corpo.scrollTo({ top: alto, behavior: riduciMovimento() ? "auto" : "smooth" });
    sezione.setAttribute("tabindex", "-1");
    sezione.focus({ preventScroll: true });
  }));
  return { chiudi: () => mostra(false) };
}
