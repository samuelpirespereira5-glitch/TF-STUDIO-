// ============================================================
// FASE 5 — Detector de palmas (Web Audio API)
// ============================================================
// Detecção real de picos de energia no áudio do microfone — nada de
// "simular" uma palma. Usa AudioContext + AnalyserNode: mede a energia
// (RMS) do sinal no domínio do tempo quadro a quadro, e só conta como
// palma um pico transitório (sobe rápido, é bem mais alto que o ruído
// de fundo, e tem energia espalhada nas frequências médias/agudas —
// bem diferente de um rumor grave constante tipo trânsito/ventilador).
//
// Não sabe nada sobre o Jarvis: só dispara CustomEvent('jarvis:clap',
// {detail:{type, count}}) no window. Quem decide o que cada contagem de
// palmas faz é o mapeamento CLAP_ACTIONS abaixo (configurável).
(function () {
  "use strict";

  const btn = document.getElementById("clap-btn");
  const statusEl = document.getElementById("clap-status");
  if (!btn) return; // página sem esse widget

  // ---------- Configuração (o usuário pode reatribuir estas ações) ----------
  // Nenhuma ação perigosa por padrão: acordar, parar de ouvir, ou
  // alternar um checkbox visível na tela — tudo reversível e visível.
  const CLAP_ACTIONS = {
    1: "wake", // 👏 acorda o Jarvis e já começa a ouvir
    2: "sleep", // 👏👏 para a fala/escuta atual (equivalente ao botão "Parar")
    3: "toggle_continuous", // 👏👏👏 liga/desliga o modo de conversa contínua
  };

  const CONFIG_KEY = "tf_clap_config";
  let config = Object.assign(
    {
      enabled: false,
      sensitivity: 1, // multiplicador; usuário pode ajustar 0.5 (mais sensível) a 2 (menos sensível)
      thresholdFloor: 0.11, // energia mínima absoluta (0..1) pra sequer considerar pico
      cooldownMs: 220, // intervalo mínimo entre dois picos contados como palmas distintas
      windowMs: 750, // janela pra agrupar várias palmas seguidas (👏👏, 👏👏👏...)
    },
    loadConfig()
  );

  function loadConfig() {
    try {
      return JSON.parse(localStorage.getItem(CONFIG_KEY) || "{}");
    } catch (e) {
      return {};
    }
  }
  function saveConfig() {
    try { localStorage.setItem(CONFIG_KEY, JSON.stringify(config)); } catch (e) {}
  }

  let audioCtx = null;
  let analyser = null;
  let micStream = null;
  let rafId = null;
  let running = false;

  let baseline = 0.02; // piso de ruído estimado, se adapta devagar
  let lastPeakAt = 0;
  let clapCount = 0;
  let windowTimer = null;
  const timeData = new Float32Array(1024);
  const freqData = new Uint8Array(1024);

  function emit(type, extra) {
    window.dispatchEvent(new CustomEvent("jarvis:clap", { detail: Object.assign({ type: type }, extra || {}) }));
  }
  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function rms(arr) {
    let sum = 0;
    for (let i = 0; i < arr.length; i++) sum += arr[i] * arr[i];
    return Math.sqrt(sum / arr.length);
  }

  function analyse() {
    if (!running) return;
    rafId = requestAnimationFrame(analyse);

    // Enquanto o Jarvis está falando, o próprio áudio dele pode vazar
    // pelo alto-falante e voltar pelo microfone (sem headset) — ignora
    // picos nesse período pra não confundir a própria voz com uma palma.
    if (window.speechSynthesis && window.speechSynthesis.speaking) return;

    analyser.getFloatTimeDomainData(timeData);
    analyser.getByteFrequencyData(freqData);
    const energy = rms(timeData);
    // Fundo neural reage ao volume do microfone (quando disponível).
    if (window.NeuralBg) window.NeuralBg.setLevel(Math.min(1, energy * 9));

    // Banda média/aguda (aprox. acima de ~1kHz num FFT de 1024 a 44.1kHz):
    // palmas têm bastante energia aí; um zumbido grave constante, não.
    const highStart = Math.floor(freqData.length * 0.25);
    let highSum = 0;
    for (let i = highStart; i < freqData.length; i++) highSum += freqData[i];
    const highAvg = highSum / (freqData.length - highStart) / 255;

    const threshold = Math.max(config.thresholdFloor, baseline * (2.6 * config.sensitivity));
    const now = performance.now ? performance.now() : Date.now();

    if (energy > threshold && highAvg > 0.12 && now - lastPeakAt > config.cooldownMs) {
      lastPeakAt = now;
      registerClap();
    } else if (energy < baseline * 1.4) {
      // Só reajusta o piso de ruído quando está "calmo" — evita que o
      // próprio pico da palma vá inflando o baseline e ficando cada vez
      // mais difícil de detectar a próxima.
      baseline += (energy - baseline) * 0.02;
    }
  }

  function registerClap() {
    clapCount++;
    setStatus("👏 x" + clapCount);
    clearTimeout(windowTimer);
    windowTimer = setTimeout(finalizeClapSequence, config.windowMs);
  }

  function finalizeClapSequence() {
    const count = clapCount;
    clapCount = 0;
    if (count <= 0) return;
    const action = CLAP_ACTIONS[Math.min(count, 3)];
    if (!action) { setStatus(""); return; }
    if (action === "wake") { setStatus("👏 acordar"); emit("wake", { count: count }); }
    else if (action === "sleep") { setStatus("👏👏 parar"); emit("sleep", { count: count }); }
    else if (action === "toggle_continuous") {
      const cb = document.getElementById("continuous-mode");
      if (cb) { cb.checked = !cb.checked; cb.dispatchEvent(new Event("change")); }
      setStatus("👏👏👏 modo contínuo " + (cb && cb.checked ? "ligado" : "desligado"));
      emit("toggle_continuous", { count: count, on: cb ? cb.checked : null });
    }
    setTimeout(() => setStatus(running ? "Ouvindo por palmas..." : ""), 1400);
  }

  async function start() {
    if (running) return;
    setStatus("Pedindo acesso ao microfone...");
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false }, video: false });
    } catch (e) {
      setStatus("❌ Microfone não liberado.");
      return;
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AC();
    const source = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.2;
    source.connect(analyser);

    running = true;
    config.enabled = true;
    saveConfig();
    btn.classList.add("active");
    setStatus("Ouvindo por palmas...");
    analyse();
  }

  function stop() {
    running = false;
    config.enabled = false;
    saveConfig();
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
    if (audioCtx) audioCtx.close().catch(() => {});
    audioCtx = null;
    analyser = null;
    micStream = null;
    btn.classList.remove("active");
    setStatus("");
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
    btn.title = "Detecção de palmas não suportada neste navegador";
    btn.disabled = true;
    return;
  }

  btn.addEventListener("click", () => { running ? stop() : start(); });
  window.addEventListener("beforeunload", stop);

  // Expõe pra uma futura tela de configurações poder ajustar sensibilidade
  // e o mapeamento de ações sem precisar mexer neste arquivo.
  window.ClapControl = {
    getConfig: () => Object.assign({}, config),
    setSensitivity: (v) => { config.sensitivity = Math.max(0.3, Math.min(3, v)); saveConfig(); },
    setAction: (count, action) => { CLAP_ACTIONS[count] = action; },
    // ITEM 27 do briefing: telemetria — ver telemetry-panel em jarvis.js
    isEnabled: () => running,
  };
})();
