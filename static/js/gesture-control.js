// ============================================================
// FASE 4 — Controle do holograma por gestos de mão (webcam)
// ============================================================
// Módulo independente: não sabe nada sobre Jarvis nem sobre o motor 3D
// por dentro. Ele só:
//   1) pede a câmera e roda o hand tracking (MediaPipe Hands, de verdade
//      — nada de detecção inventada);
//   2) transforma landmarks da mão em deltas de rotação/pan/zoom;
//   3) chama window.jarvisHolograma.applyDelta(...) (API pública exposta
//      em hologram.js) e dispara CustomEvents 'jarvis:gesture' pra quem
//      mais quiser reagir (ex.: jarvis.js falando "Controle liberado.").
//
// Se a câmera, o WebGL ou o MediaPipe não estiverem disponíveis, cai
// para mouse/touch normalmente — este módulo nunca é obrigatório pra o
// resto do sistema funcionar.
(function () {
  "use strict";

  const btn = document.getElementById("gesture-btn");
  const previewBox = document.getElementById("gesture-preview");
  const videoEl = document.getElementById("gesture-video");
  const overlay = document.getElementById("gesture-overlay");
  const statusEl = document.getElementById("gesture-status");
  if (!btn || !videoEl || !overlay) return; // página sem esse widget

  const octx = overlay.getContext("2d");

  // ---------- Parâmetros de suavização / anti-ruído ----------
  const SMOOTH_ALPHA = 0.35; // EMA: quanto maior, mais responsivo (e mais tremido)
  const DEAD_ZONE = 0.06; // 6% do quadro a partir do centro não gera rotação
  const ROT_SENSITIVITY = 2.6; // rad/s no limite do quadro
  const PAN_SENSITIVITY = 3.2;
  const OPEN_THRESHOLD = 1.55; // razão dedos-abertos/tamanho-da-mão acima disso = mão aberta
  const CLOSED_THRESHOLD = 1.05; // abaixo disso = mão fechada (punho)
  const PINCH_THRESHOLD = 0.32; // distância polegar-indicador / tamanho da mão
  const CONFIDENCE_MIN = 0.7; // score mínimo do MediaPipe pra considerar a mão válida
  const GESTURE_COOLDOWN_MS = 700; // tempo mínimo entre eventos discretos (evita spam)
  const DEBOUNCE_FRAMES = 4; // nº de frames seguidos confirmando antes de trocar de estado

  let enabled = false;
  let hands = null;
  let camera = null;
  let mpReady = false;
  let mpPromise = null;

  let smX = 0.5, smY = 0.5; // centro da palma suavizado (0..1)
  let lastGestureAt = 0;
  let handState = "none"; // "open" | "closed" | "pinch" | "none"
  let pendingState = null;
  let pendingCount = 0;
  let pinchAnchor = null; // {x,y} no momento em que a pinça começou (pra pan relativo)

  function targetWidget() {
    // Prioriza o holograma embutido no Jarvis; se não existir, usa o
    // primeiro widget de holograma achado na página (ex.: tela de
    // Ferramentas), pra funcionar em qualquer lugar que tenha um.
    if (window.jarvisHolograma) return window.jarvisHolograma;
    const anyRoot = document.querySelector("[data-holo-widget]");
    return anyRoot && anyRoot.__holoWidget ? anyRoot.__holoWidget : null;
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function emit(type, detail) {
    window.dispatchEvent(new CustomEvent("jarvis:gesture", { detail: Object.assign({ type: type }, detail || {}) }));
  }

  // ---------- Carregamento sob demanda do MediaPipe Hands ----------
  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = url;
      s.crossOrigin = "anonymous";
      s.onload = resolve;
      s.onerror = () => reject(new Error("falha ao carregar " + url));
      document.head.appendChild(s);
    });
  }
  function ensureMediaPipe() {
    if (mpReady) return Promise.resolve(true);
    if (mpPromise) return mpPromise;
    mpPromise = loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js")
      .then(() => loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"))
      .then(() => {
        mpReady = !!(window.Hands && window.Camera);
        return mpReady;
      })
      .catch(() => {
        mpReady = false;
        return false;
      });
    return mpPromise;
  }

  // ---------- Geometria da mão ----------
  function dist(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
  }
  function classifyHand(lm) {
    const wrist = lm[0];
    const handSize = dist(wrist, lm[9]) || 0.001; // wrist -> base do dedo médio, referência de escala
    const tips = [lm[4], lm[8], lm[12], lm[16], lm[20]];
    const spread = tips.reduce((sum, tip) => sum + dist(wrist, tip), 0) / tips.length / handSize;
    const pinchDist = dist(lm[4], lm[8]) / handSize;
    return { spread: spread, pinchDist: pinchDist, handSize: handSize };
  }

  function drawOverlay(lm) {
    if (!octx) return;
    octx.clearRect(0, 0, overlay.width, overlay.height);
    if (!lm) return;
    octx.fillStyle = "#00e5ff";
    octx.strokeStyle = "rgba(0,229,255,0.5)";
    const conns = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[0,9],[9,10],[10,11],[11,12],[0,13],[13,14],[14,15],[15,16],[0,17],[17,18],[18,19],[19,20],[5,9],[9,13],[13,17]];
    octx.lineWidth = 2;
    conns.forEach(([a, b]) => {
      octx.beginPath();
      octx.moveTo(lm[a].x * overlay.width, lm[a].y * overlay.height);
      octx.lineTo(lm[b].x * overlay.width, lm[b].y * overlay.height);
      octx.stroke();
    });
    lm.forEach((p) => {
      octx.beginPath();
      octx.arc(p.x * overlay.width, p.y * overlay.height, 3, 0, Math.PI * 2);
      octx.fill();
    });
  }

  let lastConfidence = 0; // ITEM 27 do briefing: telemetria de "Gesture Confidence"

  function onResults(results) {
    const hasHand = results.multiHandLandmarks && results.multiHandLandmarks.length > 0;
    const score = hasHand && results.multiHandedness && results.multiHandedness[0] ? results.multiHandedness[0].score : 0;
    lastConfidence = score;
    if (!hasHand || score < CONFIDENCE_MIN) {
      drawOverlay(null);
      transitionState("none");
      return;
    }
    const lm = results.multiHandLandmarks[0];
    drawOverlay(lm);

    // Centro da palma (média do punho + bases dos dedos) — mais estável
    // que só a ponta de um dedo. Espelha o X: câmera frontal = "modo
    // espelho", então mover a mão pra direita do usuário move o ponto
    // pra direita na tela também.
    const cx = 1 - (lm[0].x + lm[5].x + lm[9].x + lm[13].x + lm[17].x) / 5;
    const cy = (lm[0].y + lm[5].y + lm[9].y + lm[13].y + lm[17].y) / 5;
    smX += (cx - smX) * SMOOTH_ALPHA;
    smY += (cy - smY) * SMOOTH_ALPHA;

    const geo = classifyHand(lm);
    let state = handState;
    if (geo.pinchDist < PINCH_THRESHOLD) state = "pinch";
    else if (geo.spread > OPEN_THRESHOLD) state = "open";
    else if (geo.spread < CLOSED_THRESHOLD) state = "closed";
    transitionState(state);

    const widget = targetWidget();
    if (!widget) return;

    if (handState === "pinch") {
      // Pinça + movimento = mover (pan) o objeto, não girar.
      if (!pinchAnchor) pinchAnchor = { x: smX, y: smY };
      const dPanX = (smX - pinchAnchor.x) * PAN_SENSITIVITY;
      const dPanY = (smY - pinchAnchor.y) * PAN_SENSITIVITY;
      pinchAnchor = { x: smX, y: smY };
      widget.applyDelta(0, 0, 0, dPanX, -dPanY);
    } else {
      pinchAnchor = null;
      if (handState === "open") {
        // Zona morta ao redor do centro: só gira quando a mão sai de perto
        // do meio do quadro, como um joystick.
        const ox = smX - 0.5;
        const oy = smY - 0.5;
        const dx = Math.abs(ox) > DEAD_ZONE ? ox : 0;
        const dy = Math.abs(oy) > DEAD_ZONE ? oy : 0;
        widget.applyDelta(dx * ROT_SENSITIVITY * 0.033, dy * ROT_SENSITIVITY * 0.033, 0, 0, 0);
      }
      // "closed" (punho fechado) = controle pausado, mão parada trava o
      // holograma no lugar em vez de continuar girando.
    }
  }

  function transitionState(next) {
    if (next === pendingState) {
      pendingCount++;
    } else {
      pendingState = next;
      pendingCount = 1;
    }
    if (pendingCount < DEBOUNCE_FRAMES || next === handState) return;
    const now = performance.now ? performance.now() : Date.now();
    if (now - lastGestureAt < GESTURE_COOLDOWN_MS) return;
    lastGestureAt = now;
    handState = next;
    if (next === "open") { setStatus("✋ Mão aberta — controlando o holograma"); emit("open"); }
    else if (next === "closed") { setStatus("✊ Mão fechada — controle pausado"); emit("closed"); }
    else if (next === "pinch") { setStatus("🤏 Pinça — movendo objeto"); emit("pinch"); }
    else { setStatus("Nenhuma mão detectada"); emit("lost"); }
  }

  async function start() {
    if (enabled) return;
    setStatus("Pedindo acesso à câmera...");
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, facingMode: "user" }, audio: false });
    } catch (e) {
      setStatus("❌ Câmera não liberada. Usando mouse/touch normalmente.");
      return;
    }
    videoEl.srcObject = stream;
    await videoEl.play().catch(() => {});

    setStatus("Carregando reconhecimento de mão...");
    const ok = await ensureMediaPipe();
    if (!ok) {
      setStatus("❌ Não consegui carregar o hand tracking (sem internet?). Usando mouse/touch normalmente.");
      stream.getTracks().forEach((t) => t.stop());
      return;
    }

    overlay.width = videoEl.videoWidth || 320;
    overlay.height = videoEl.videoHeight || 240;

    hands = new window.Hands({
      locateFile: (file) => "https://cdn.jsdelivr.net/npm/@mediapipe/hands/" + file,
    });
    hands.setOptions({
      maxNumHands: 1,
      modelComplexity: 1,
      minDetectionConfidence: CONFIDENCE_MIN,
      minTrackingConfidence: 0.6,
    });
    hands.onResults(onResults);

    camera = new window.Camera(videoEl, {
      onFrame: async () => {
        try { await hands.send({ image: videoEl }); } catch (e) { /* frame perdido, próximo resolve */ }
      },
      width: 320,
      height: 240,
    });
    camera.start();

    enabled = true;
    btn.classList.add("active");
    if (previewBox) previewBox.classList.remove("hidden");
    setStatus("Detectando mão...");
    emit("started");
  }

  function stop() {
    if (!enabled) return;
    enabled = false;
    try { camera && camera.stop(); } catch (e) {}
    const stream = videoEl.srcObject;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    videoEl.srcObject = null;
    btn.classList.remove("active");
    if (previewBox) previewBox.classList.add("hidden");
    if (octx) octx.clearRect(0, 0, overlay.width, overlay.height);
    handState = "none";
    pendingState = null;
    setStatus("");
    emit("stopped");
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    btn.title = "Câmera não suportada neste navegador";
    btn.disabled = true;
    return;
  }

  btn.addEventListener("click", () => {
    if (enabled) stop();
    else start();
  });

  window.addEventListener("beforeunload", stop);

  // ITEM 27 do briefing: telemetria — exposto pra um painel externo (ver
  // telemetry-panel em jarvis.js) sem precisar acoplar este módulo a ele.
  window.GestureControl = {
    isEnabled: () => enabled,
    getState: () => ({ enabled: enabled, handState: handState, confidence: lastConfidence }),
  };
})();
