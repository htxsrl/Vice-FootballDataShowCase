// Voce (wiki/tecnica/voce.md): microfono push-to-talk con la Web Speech API di Chrome, testo che compare
// mentre si parla, invio automatico al rilascio (Vice è in sola lettura). La lettura ad alta voce delle risposte
// («Ascolta») è stata tolta il 09/11/2026 (decisione 64).
import { $ } from "./util.js";

export function avviaVoce({ area, ridimensiona, invia }) {
  const mic = $("#mic"), aiuto = $("#suggerimento");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    mic.disabled = true;
    mic.title = "Il riconoscimento vocale richiede Chrome";
    aiuto.textContent = "Per parlare con Vice apri la pagina in Chrome. La chat scritta funziona ovunque.";
    return;
  }
  const r = new SR();
  r.lang = "it-IT";
  r.interimResults = true;   // le parole compaiono mentre parli
  r.continuous = true;       // finché tieni premuto
  let attivo = false, finale = "";

  r.onresult = (e) => {
    let provvisorio = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finale += t; else provvisorio += t;
    }
    area.value = (finale + provvisorio).trim();
    ridimensiona();
  };
  const spegni = () => { attivo = false; mic.classList.remove("ascolto"); };
  r.onerror = (e) => {
    spegni();
    if (e.error === "not-allowed") aiuto.textContent = "Permesso del microfono negato: abilitalo dalle impostazioni del sito.";
  };
  r.onend = () => {
    spegni();
    const t = area.value.trim();
    if (t) { area.value = ""; ridimensiona(); invia(t); }
  };
  const inizia = (e) => {
    e.preventDefault();
    if (attivo) return;
    attivo = true; finale = ""; area.value = "";
    mic.classList.add("ascolto");
    try { r.start(); } catch { /* già avviato */ }
  };
  const ferma = () => { if (attivo) r.stop(); };
  mic.addEventListener("pointerdown", inizia);
  ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => mic.addEventListener(ev, ferma));
  mic.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) inizia(e); });
  mic.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") ferma(); });
}
