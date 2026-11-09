// Il divisore tra chat e lavagna (decisione 50): si trascina col mouse o col dito, si sposta con le frecce
// della tastiera (Home ed End agli estremi) e torna alla larghezza iniziale col doppio clic. La larghezza resta
// salvata in questo browser. Sotto i 980 px chat e lavagna stanno una sopra l'altra e il divisore non c'è.
import { $ } from "./util.js";

const CHIAVE = "vice-larghezza-chat";
const MIN_CHAT = 300;          // px
const MIN_LAVAGNA = 380;       // px
const PASSO = 24;              // px per freccia

export function avviaDivisore(ridimensiona) {
  const area = $("#area"), div = $("#divisore");
  let larghezza = null;
  try { larghezza = Number(localStorage.getItem(CHIAVE)) || null; } catch { larghezza = null; }

  const limiti = () => [MIN_CHAT, Math.max(MIN_CHAT, area.clientWidth - MIN_LAVAGNA - div.offsetWidth)];
  let attesa = 0;
  const ridisegna = () => { cancelAnimationFrame(attesa); attesa = requestAnimationFrame(ridimensiona); };

  const imposta = (px, { salva = false } = {}) => {
    if (px === null) {
      area.style.removeProperty("--chat");
      larghezza = null;
    } else {
      const [min, max] = limiti();
      larghezza = Math.round(Math.min(max, Math.max(min, px)));
      area.style.setProperty("--chat", `${larghezza}px`);
    }
    const attuale = $(".chat").getBoundingClientRect().width;
    div.setAttribute("aria-valuenow", String(Math.round((attuale / Math.max(1, area.clientWidth)) * 100)));
    if (salva) {
      try { if (larghezza === null) localStorage.removeItem(CHIAVE); else localStorage.setItem(CHIAVE, String(larghezza)); } catch { /* resta per questa visita */ }
    }
    ridisegna();
  };

  div.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    div.setPointerCapture(e.pointerId);
    document.body.classList.add("trascino");
    const sinistra = area.getBoundingClientRect().left;
    const muovi = (ev) => imposta(ev.clientX - sinistra - div.offsetWidth / 2);
    const fine = () => {
      document.body.classList.remove("trascino");
      div.removeEventListener("pointermove", muovi);
      imposta(larghezza, { salva: true });
    };
    div.addEventListener("pointermove", muovi);
    div.addEventListener("pointerup", fine, { once: true });
    div.addEventListener("pointercancel", fine, { once: true });
  });
  div.addEventListener("keydown", (e) => {
    const attuale = larghezza ?? $(".chat").getBoundingClientRect().width;
    const [min, max] = limiti();
    const nuovo = { ArrowLeft: attuale - PASSO, ArrowRight: attuale + PASSO, Home: min, End: max }[e.key];
    if (nuovo === undefined) return;
    e.preventDefault();
    imposta(nuovo, { salva: true });
  });
  div.addEventListener("dblclick", () => imposta(null, { salva: true }));
  // la larghezza salvata vale anche dopo un ridimensionamento della finestra, entro i limiti
  addEventListener("resize", () => { if (larghezza !== null) imposta(larghezza); });
  if (larghezza !== null) imposta(larghezza);
}
