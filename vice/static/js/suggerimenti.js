// I suggerimenti al passaggio del mouse (decisione 52): un solo riquadro, con lo stesso stile di quelli dei
// grafici, al posto di quello del browser. Vale per ogni elemento con `data-tip` (HTML già pronto e già
// "pulito" da chi lo scrive) o con `title` (testo semplice: alla prima occasione diventa `data-tip`, così il
// browser non mostra il suo). Si apre anche col fuoco da tastiera; si chiude uscendo, con Esc o scorrendo.
import { escapeHtml } from "./util.js";

const MARGINE = 8;   // px dal bordo della finestra
const DISTANZA = 8;  // px dall'elemento

export function avviaSuggerimenti() {
  const box = document.createElement("div");
  box.className = "suggerimento-box";
  box.id = "suggerimento-box";
  box.setAttribute("role", "tooltip");
  box.hidden = true;
  document.body.append(box);
  let attuale = null;

  const daTitolo = (el) => {
    if (el.hasAttribute("title")) {
      const t = el.getAttribute("title");
      el.removeAttribute("title");
      if (t && !el.dataset.tip) el.dataset.tip = `<div class="tip">${escapeHtml(t)}</div>`;
    }
    return el.dataset.tip ? el : null;
  };
  const bersaglio = (t) => {
    const el = t?.closest?.("[data-tip], [title]");
    return el && !box.contains(el) ? daTitolo(el) : null;
  };

  const posiziona = (el) => {
    const r = el.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    let x = r.left + r.width / 2 - b.width / 2;
    x = Math.max(MARGINE, Math.min(x, innerWidth - b.width - MARGINE));
    let y = r.bottom + DISTANZA;
    if (y + b.height > innerHeight - MARGINE) y = Math.max(MARGINE, r.top - b.height - DISTANZA);   // sopra, se sotto non ci sta
    box.style.left = `${Math.round(x)}px`;
    box.style.top = `${Math.round(y)}px`;
  };
  const mostra = (el) => {
    if (attuale === el) return;
    nascondi();
    box.innerHTML = el.dataset.tip;
    box.hidden = false;
    posiziona(el);
    el.setAttribute("aria-describedby", box.id);
    attuale = el;
  };
  function nascondi() {
    if (!attuale) return;
    box.hidden = true;
    attuale.removeAttribute("aria-describedby");
    attuale = null;
  }

  document.addEventListener("pointerover", (e) => {
    const el = bersaglio(e.target);
    if (el) mostra(el); else nascondi();
  });
  document.addEventListener("pointerleave", nascondi);
  document.addEventListener("focusin", (e) => { const el = bersaglio(e.target); if (el) mostra(el); });
  document.addEventListener("focusout", nascondi);
  document.addEventListener("pointerdown", nascondi);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") nascondi(); });
  addEventListener("scroll", nascondi, true);
  addEventListener("resize", nascondi);
}
