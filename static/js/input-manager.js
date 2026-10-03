// ============================================================
// ITEM 2 do briefing — InputManager: sistema central de entradas.
// ============================================================
// Este módulo NÃO reimplementa nada que já funciona (mouse/touch em
// hologram.js, gestos em gesture-control.js, palmas em clap-control.js,
// voz em jarvis.js). Ele só ESCUTA os CustomEvents que esses módulos já
// disparam no window e os traduz para um vocabulário único e estável
// (ROTATE_HOLOGRAM, ZOOM_HOLOGRAM, WAKE_JARVIS, VOICE_COMMAND...), pra
// quem quiser reagir (Jarvis, telemetria, um log de depuração, um futuro
// painel de automações) sem precisar conhecer os eventos internos de
// cada módulo de entrada.
//
// Arquitetura (só o que existe de fato hoje):
//   MouseInput / TouchInput  → hologram.js dispara "holo:*"
//   GestureInput             → gesture-control.js dispara "jarvis:gesture"
//   ClapInput                → clap-control.js dispara "jarvis:clap"
//   VoiceInput               → jarvis.js dispara "input:VOICE_COMMAND"
//   KeyboardInput            → capturado diretamente aqui (novo)
//
// Uso por outros módulos:
//   window.InputManager.on("ROTATE_HOLOGRAM", (detail) => {...});
//   window.InputManager.getLog();  // últimos eventos, pra telemetria/debug
(function () {
  "use strict";

  const listeners = Object.create(null); // { EVENT_NAME: [fn, fn, ...] }
  const LOG_MAX = 40;
  const log = [];

  function on(eventName, fn) {
    if (!listeners[eventName]) listeners[eventName] = [];
    listeners[eventName].push(fn);
    return () => off(eventName, fn); // conveniência: on() devolve a própria função de cancelar
  }
  function off(eventName, fn) {
    if (!listeners[eventName]) return;
    listeners[eventName] = listeners[eventName].filter((f) => f !== fn);
  }
  function emit(eventName, detail) {
    log.push({ event: eventName, detail: detail || {}, at: Date.now() });
    if (log.length > LOG_MAX) log.shift();
    (listeners[eventName] || []).forEach((fn) => {
      try { fn(detail || {}); } catch (e) { /* um listener quebrado nunca derruba os outros */ }
    });
    // Também republica como CustomEvent no window — quem preferir
    // addEventListener direto (em vez do pub/sub acima) também funciona.
    window.dispatchEvent(new CustomEvent("input:" + eventName, { detail: detail || {} }));
  }

  // ---------- MouseInput / TouchInput (via eventos que hologram.js já dispara) ----------
  window.addEventListener("holo:open", (e) => emit("OPEN_HOLOGRAM", e.detail));
  window.addEventListener("holo:close", (e) => emit("CLOSE_HOLOGRAM", e.detail));
  window.addEventListener("holo:rotate", (e) => emit("ROTATE_HOLOGRAM", e.detail));
  window.addEventListener("holo:pan", (e) => emit("PAN_HOLOGRAM", e.detail));
  window.addEventListener("holo:zoom", (e) => emit("ZOOM_HOLOGRAM", e.detail));
  window.addEventListener("holo:select", (e) => emit("SELECT_OBJECT", e.detail));
  window.addEventListener("holo:deselect", (e) => emit("SELECT_OBJECT", Object.assign({ cleared: true }, e.detail)));
  window.addEventListener("holo:reset-view", (e) => emit("RESET_HOLOGRAM_VIEW", e.detail));

  // ---------- GestureInput ----------
  window.addEventListener("jarvis:gesture", (e) => {
    const type = e.detail && e.detail.type;
    emit("HAND_GESTURE", e.detail);
    if (type === "open" || type === "closed" || type === "pinch") {
      // gesto discreto reconhecido = também um comando de controle do holograma
      emit("TOOL_COMMAND", { tool: "hologram", gesture: type });
    }
  });

  // ---------- ClapInput ----------
  window.addEventListener("jarvis:clap", (e) => {
    const type = e.detail && e.detail.type;
    emit("CLAP_DETECTED", e.detail);
    if (type === "wake") emit("WAKE_JARVIS", { source: "clap" });
  });

  // ---------- VoiceInput (jarvis.js já dispara "input:VOICE_COMMAND") ----------
  window.addEventListener("input:VOICE_COMMAND", (e) => {
    // Evita duplicar: só re-emite pro pub/sub interno (não redispara o
    // CustomEvent, que já existe) e alimenta o log/telemetria.
    log.push({ event: "VOICE_COMMAND", detail: e.detail || {}, at: Date.now() });
    if (log.length > LOG_MAX) log.shift();
    (listeners.VOICE_COMMAND || []).forEach((fn) => { try { fn(e.detail || {}); } catch (err) {} });
  });

  // ---------- KeyboardInput ----------
  // Só atua fora de campos de texto (senão roubaria a digitação normal).
  // Atalhos pensados pra quem está com as mãos livres pra controlar o
  // holograma sem depender de mouse/gesto/voz.
  const KEY_MAP = {
    Escape: () => { if (window.jarvisHolograma && window.jarvisHolograma.isActive()) { window.jarvisHolograma.close(); emit("CLOSE_HOLOGRAM", { source: "keyboard" }); } },
    ArrowLeft: () => applyKeyboardDelta(-0.12, 0, 0, 0, 0),
    ArrowRight: () => applyKeyboardDelta(0.12, 0, 0, 0, 0),
    ArrowUp: () => applyKeyboardDelta(0, -0.1, 0, 0, 0),
    ArrowDown: () => applyKeyboardDelta(0, 0.1, 0, 0, 0),
    "+": () => applyKeyboardDelta(0, 0, -0.6, 0, 0),
    "-": () => applyKeyboardDelta(0, 0, 0.6, 0, 0),
    "0": () => { if (window.jarvisHolograma && window.jarvisHolograma.isActive()) { window.jarvisHolograma.resetView(); emit("RESET_HOLOGRAM_VIEW", { source: "keyboard" }); } },
  };
  function applyKeyboardDelta(dRotY, dRotX, dZoom, dPanX, dPanY) {
    if (!window.jarvisHolograma || !window.jarvisHolograma.isActive()) return;
    window.jarvisHolograma.applyDelta(dRotY, dRotX, dZoom, dPanX, dPanY);
    if (dZoom) emit("ZOOM_HOLOGRAM", { source: "keyboard", dZoom: dZoom });
    else emit("ROTATE_HOLOGRAM", { source: "keyboard", dRotY: dRotY, dRotX: dRotX });
  }
  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
  }
  window.addEventListener("keydown", (e) => {
    if (isTypingTarget(document.activeElement)) return;
    const handler = KEY_MAP[e.key];
    if (!handler) return;
    e.preventDefault();
    handler();
  });

  // ---------- API pública ----------
  window.InputManager = {
    on: on,
    off: off,
    emit: emit, // permite que qualquer módulo futuro (Workspace, Cyber Lab...) publique seus próprios eventos
    getLog: () => log.slice(),
  };
})();
