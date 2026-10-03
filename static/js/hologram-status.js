/**
 * HoloStatus — indicador global de estado do Jarvis, materializado como um
 * orbe pulsante fixo no canto da tela (funciona em qualquer página, mesmo
 * sem o holograma 3D carregado). Não depende de Three.js.
 *
 * Estados:
 *   waiting    -> azul   (padrão, à espera de comando)
 *   thinking   -> verde  (processando/pensando)
 *   alert      -> vermelho (erro/alerta)
 *   owner      -> dourado (modo Owner autenticado, sobrepõe os outros
 *                enquanto o Jarvis está ocioso)
 *
 * Uso: window.HoloStatus.set("thinking")
 */
(function () {
  "use strict";

  const COLORS = {
    waiting: { c1: "#2fb4ff", c2: "#0a6fb8", label: "Aguardando" },
    thinking: { c1: "#37f08a", c2: "#0a9c52", label: "Processando" },
    alert: { c1: "#ff4d4d", c2: "#a30f0f", label: "Alerta" },
    owner: { c1: "#ffd700", c2: "#b8860b", label: "Modo Owner" },
    scanning: { c1: "#2ff0e0", c2: "#0a8b8b", label: "Escaneando" },
  };

  let el = null;
  let currentState = "waiting";
  let ownerActive = false;

  function ensureEl() {
    if (el) return el;
    el = document.createElement("div");
    el.id = "holo-status-orb";
    el.innerHTML = '<span class="holo-status-core"></span><span class="holo-status-ring"></span>' +
      '<span class="holo-status-label"></span>';
    document.body.appendChild(el);

    const style = document.createElement("style");
    style.textContent = `
      #holo-status-orb {
        position: fixed; right: 14px; bottom: 78px; z-index: 9998;
        width: 38px; height: 38px; display: flex; align-items: center;
        justify-content: center; pointer-events: none; user-select: none;
      }
      #holo-status-orb .holo-status-core {
        position: absolute; width: 14px; height: 14px; border-radius: 50%;
        background: var(--holo-c1, #2fb4ff);
        box-shadow: 0 0 10px 2px var(--holo-c1, #2fb4ff), 0 0 22px 6px var(--holo-c2, #0a6fb8);
        transition: background .35s ease, box-shadow .35s ease;
        animation: holoPulseCore 1.8s ease-in-out infinite;
      }
      #holo-status-orb .holo-status-ring {
        position: absolute; width: 32px; height: 32px; border-radius: 50%;
        border: 2px solid var(--holo-c1, #2fb4ff); opacity: .55;
        transition: border-color .35s ease;
        animation: holoPulseRing 1.8s ease-out infinite;
      }
      #holo-status-orb .holo-status-label {
        position: absolute; right: 46px; bottom: 8px; font-size: 11px;
        color: var(--holo-c1, #2fb4ff); white-space: nowrap; opacity: 0;
        transition: opacity .25s ease; font-family: inherit;
        text-shadow: 0 0 6px rgba(0,0,0,.6);
      }
      #holo-status-orb.holo-show-label .holo-status-label { opacity: .9; }
      #holo-status-orb.holo-state-thinking .holo-status-core { animation-duration: .9s; }
      #holo-status-orb.holo-state-thinking .holo-status-ring { animation-duration: .9s; }
      #holo-status-orb.holo-state-alert .holo-status-core,
      #holo-status-orb.holo-state-alert .holo-status-ring { animation-duration: .6s; }
      #holo-status-orb.holo-state-scanning .holo-status-ring {
        border-style: dashed; animation: holoScanSweep 1.1s linear infinite;
      }
      @keyframes holoScanSweep {
        0% { transform: rotate(0deg) scale(1); }
        100% { transform: rotate(360deg) scale(1); }
      }
      @keyframes holoPulseCore {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.25); }
      }
      @keyframes holoPulseRing {
        0% { transform: scale(0.6); opacity: .65; }
        100% { transform: scale(1.6); opacity: 0; }
      }
      @media (max-width: 640px) {
        #holo-status-orb { right: 10px; bottom: 66px; }
      }
    `;
    document.head.appendChild(style);
    return el;
  }

  function applyVisual(stateKey) {
    const cfg = COLORS[stateKey] || COLORS.waiting;
    const node = ensureEl();
    node.style.setProperty("--holo-c1", cfg.c1);
    node.style.setProperty("--holo-c2", cfg.c2);
    node.className = "holo-state-" + stateKey;
    const label = node.querySelector(".holo-status-label");
    if (label) label.textContent = cfg.label;
  }

  const HoloStatus = {
    /** Define o estado explicitamente ("waiting"|"thinking"|"alert"|"owner"). */
    set(state) {
      if (!COLORS[state]) return;
      currentState = state;
      // "owner" é tratado como um modo persistente: assim que setado,
      // substitui "waiting" até ser desligado com setOwner(false), mas
      // "thinking"/"alert" continuam podendo pulsar por cima temporariamente.
      if (state === "owner") ownerActive = true;
      applyVisual(state);
    },
    /** Liga/desliga o modo Owner (dourado quando ocioso). */
    setOwner(active) {
      ownerActive = !!active;
      if (currentState === "waiting" || currentState === "owner") {
        applyVisual(ownerActive ? "owner" : "waiting");
        currentState = ownerActive ? "owner" : "waiting";
      }
    },
    /** Volta ao estado de repouso (dourado se owner, azul caso contrário). */
    idle() {
      this.set(ownerActive ? "owner" : "waiting");
    },
    thinking() { this.set("thinking"); },
    alert() { this.set("alert"); },
    scanning() { this.set("scanning"); },
    showLabel(show) {
      ensureEl().classList.toggle("holo-show-label", !!show);
    },
    get state() { return currentState; },
  };

  window.HoloStatus = HoloStatus;

  function initOwnerGlow() {
    applyVisual("waiting");
    fetch("/api/me", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && d.role === "owner") HoloStatus.setOwner(true); })
      .catch(() => {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOwnerGlow);
  } else {
    initOwnerGlow();
  }
})();
