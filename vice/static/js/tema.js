// Tema chiaro o scuro (decisione 38): chiaro predefinito, la scelta resta nel browser di chi guarda.
import { emetti } from "./util.js";

const FONT = ["400 16px 'Schibsted Grotesk'", "700 16px 'Schibsted Grotesk'", "400 16px Newsreader", "600 16px Newsreader"];

export const temaCorrente = () => document.documentElement.dataset.tema || "chiaro";

export async function fontPronti() {
  try { await Promise.all(FONT.map((f) => document.fonts.load(f))); } catch { /* si disegna coi font di riserva */ }
}

function segna() {
  document.querySelectorAll(".commutatore button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tema === temaCorrente())));
}

export function avviaTema() {
  const forzato = new URLSearchParams(location.search).get("tema");
  if (forzato === "chiaro" || forzato === "scuro") document.documentElement.dataset.tema = forzato;
  segna();
  document.querySelectorAll(".commutatore button").forEach((b) => b.addEventListener("click", () => {
    document.documentElement.dataset.tema = b.dataset.tema;
    try { localStorage.setItem("vice-tema", b.dataset.tema); } catch { /* senza memoria locale si riparte dal chiaro */ }
    segna();
    emetti("tema", b.dataset.tema);   // i grafici leggono i colori dalle variabili CSS: si ridisegnano
  }));
}
