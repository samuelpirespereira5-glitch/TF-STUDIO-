// ============================================================
// ITEM 27/28 do briefing — Painel de telemetria + Performance.
// ============================================================
// Módulo isolado: só lê APIs já públicas (window.jarvisHolograma,
// window.GestureControl, window.ClapControl) e o estado visual do
// orb do Jarvis. Não inventa nenhum dado que o navegador não
// consiga expor de forma confiável (sem "GPU:", sem "memória:").
(function () {
  "use strict";

  const btn = document.getElementById("telemetry-btn");
  const panel = document.getElementById("jarvis-telemetry-panel");
  const closeBtn = document.getElementById("telemetry-close-btn");
  const perfSelect = document.getElementById("telemetry-perf-select");
  const orb = document.getElementById("jarvis-orb");
  if (!btn || !panel) return; // página sem o painel (só existe em /jarvis)

  const HUD_STATE_LABELS = {
    listening: "🔴 Ouvindo",
    thinking: "🟡 Pensando",
    processing: "🔵 Processando",
    executing: "🟢 Executando ferramenta",
    speaking: "🔊 Falando",
    success: "✅ Sucesso",
    error: "⚠️ Erro",
  };

  function fields() {
    const out = {};
    panel.querySelectorAll("[data-tm]").forEach((el) => { out[el.getAttribute("data-tm")] = el; });
    return out;
  }
  const tm = fields();

  let pollTimer = null;

  function currentAiStatus() {
    for (const state of Object.keys(HUD_STATE_LABELS)) {
      if (orb && orb.classList.contains(state)) return HUD_STATE_LABELS[state];
    }
    return "🟢 Em espera";
  }

  function refresh() {
    const holo = window.jarvisHolograma && typeof window.jarvisHolograma.getTelemetry === "function"
      ? window.jarvisHolograma.getTelemetry()
      : null;

    if (holo) {
      tm.fps.textContent = holo.fps ? String(holo.fps) : "—";
      tm.renderer.textContent = holo.webgl ? "WebGL" : "Canvas 2D (modo compatível)";
      tm.objects.textContent = String(holo.objects || 0);
      tm.particles.textContent = String(holo.particles || 0);
      tm.postfx.textContent = holo.postFX ? "Ativo (bloom)" : "Desligado";
      tm.holotype.textContent = holo.active ? (holo.currentText || holo.currentType || "—") : "Nenhum";
    } else {
      tm.fps.textContent = "—";
      tm.renderer.textContent = "Holograma fechado";
      tm.objects.textContent = "0";
      tm.particles.textContent = "0";
      tm.postfx.textContent = "—";
      tm.holotype.textContent = "Nenhum";
    }

    const gesture = window.GestureControl && window.GestureControl.getState ? window.GestureControl.getState() : null;
    tm.camera.textContent = gesture && gesture.enabled ? "Ativa" : "Desligada";
    if (tm["gesture-confidence"]) {
      tm["gesture-confidence"].textContent = gesture && gesture.enabled
        ? Math.round((gesture.confidence || 0) * 100) + "%"
        : "—";
    }

    const clapOn = window.ClapControl && window.ClapControl.isEnabled ? window.ClapControl.isEnabled() : false;
    tm.clap.textContent = clapOn ? "Escutando" : "Desligadas";

    const micOn = !!(orb && orb.classList.contains("listening"));
    tm.mic.textContent = micOn ? "Ouvindo" : "Inativo";

    if (tm["ai-status"]) tm["ai-status"].textContent = currentAiStatus();

    if (tm["last-input"]) {
      const log = window.InputManager && window.InputManager.getLog ? window.InputManager.getLog() : [];
      const last = log[log.length - 1];
      tm["last-input"].textContent = last ? last.event : "—";
    }
  }

  function startPolling() {
    if (pollTimer) return;
    refresh();
    pollTimer = setInterval(refresh, 500);
  }
  function stopPolling() {
    if (!pollTimer) return;
    clearInterval(pollTimer);
    pollTimer = null;
  }

  btn.addEventListener("click", () => {
    const isHidden = panel.classList.contains("hidden");
    panel.classList.toggle("hidden");
    if (isHidden) startPolling(); else stopPolling();
  });
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      panel.classList.add("hidden");
      stopPolling();
    });
  }

  if (perfSelect) {
    perfSelect.addEventListener("change", () => {
      if (window.jarvisHolograma && typeof window.jarvisHolograma.setPerformanceTier === "function") {
        window.jarvisHolograma.setPerformanceTier(perfSelect.value);
      }
    });
  }

  window.addEventListener("beforeunload", stopPolling);
})();
