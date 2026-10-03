// Fundo animado tipo "rede neural com profundidade": uma camada distante
// de estrelas cintilando bem devagar (sensação de espaço/profundidade),
// uma camada de nós conectados por linhas finas com brilho (glow) real
// via canvas shadow, e pulsos de "dado" ocasionais viajando por uma
// conexão — como se informação estivesse fluindo pela rede. Tudo roda em
// <canvas> por baixo de tudo (pointer-events: none no CSS), então nunca
// atrapalha a leitura do conteúdo por cima.
(function () {
  const canvas = document.getElementById("neural-bg");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Mesmas cores do tema (ciano / roxo / azul) já usadas no resto do site.
  const COLORS = ["0, 229, 255", "176, 38, 255", "59, 107, 255"];
  const LINK_DIST = 165;

  // Caracteres usados nos "readouts" de dados (camada nova) — hex e
  // binário, como um painel técnico de verdade, não decoração aleatória.
  const DATA_CHARS = "0123456789ABCDEF";

  let w = 0, h = 0, nodes = [], stars = [], pulses = [], glyphs = [], nebulae = [];
  let circuits = [], radars = [];
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let frameCount = 0;
  let lastEdgeCount = 0;

  // Feixe de varredura vertical, tipo scanner de painel de nave — passa
  // pela tela de vez em quando, reforçando a sensação "sistema ativo".
  let scanY = -200;
  let scanSpeed = 0;
  function maybeStartScan() {
    if (scanSpeed !== 0) return;
    if (Math.random() > 0.0035 * energy) return;
    scanY = -120;
    scanSpeed = Math.max(h, 400) * 0.0026;
  }

  // Paralaxe suave: o fundo reage de leve ao mouse/toque, dando sensação
  // real de profundidade (camadas mais distantes se movem menos) em vez
  // de um fundo totalmente estático atrás do conteúdo.
  let mouseX = 0, mouseY = 0, parallaxX = 0, parallaxY = 0;
  window.addEventListener("pointermove", (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  function resize() {
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Menos elementos em telas pequenas (celular), pra não pesar a bateria.
    // Densidade maior e mais movimento que antes — fundo mais "vivo" e
    // tecnológico, como pedido (mais nós, mais rápido, mais brilho).
    const nodeCount = Math.min(220, Math.max(52, Math.round((w * h) / 11200)));
    nodes = Array.from({ length: nodeCount }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.34,
      vy: (Math.random() - 0.5) * 0.34,
      r: 1.3 + Math.random() * 1.3,
      c: COLORS[Math.floor(Math.random() * COLORS.length)],
    }));

    const starCount = Math.min(260, Math.max(78, Math.round((w * h) / 9200)));
    stars = Array.from({ length: starCount }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.2 + 0.3,
      phase: Math.random() * Math.PI * 2,
      speed: 0.01 + Math.random() * 0.018,
    }));

    // ---- Camada nova: "readouts" de dados subindo devagar ----
    // Pequenas colunas de hex/binário, bem discretas (opacidade baixa),
    // que sobem lentamente — dá a sensação de painel de sistema ativo,
    // tipo terminal de fundo, sem virar poluição visual.
    const glyphCount = Math.min(26, Math.max(8, Math.round((w * h) / 90000)));
    glyphs = Array.from({ length: glyphCount }, () => makeGlyphColumn());

    // ---- Camada de fundo: nébulas grandes e bem suaves para profundidade ----
    // Manchas grandes, quase imperceptíveis, que derivam bem devagar —
    // dão a sensação de um fundo "vivo" com volume em vez de um plano
    // liso atrás dos nós, sem nunca competir com o conteúdo por cima.
    const nebulaCount = w < 700 ? 2 : 3;
    nebulae = Array.from({ length: nebulaCount }, (_, i) => ({
      x: (0.2 + 0.6 * Math.random()) * w,
      y: (0.15 + 0.7 * Math.random()) * h,
      r: Math.max(w, h) * (0.35 + Math.random() * 0.25),
      c: COLORS[i % COLORS.length],
      driftX: (Math.random() - 0.5) * 0.08,
      driftY: (Math.random() - 0.5) * 0.08,
      phase: Math.random() * Math.PI * 2,
    }));

    // ---- Camada nova: "trilhas de circuito" (placa de circuito) ----
    // Linhas em ângulo reto (estilo trilha de PCB) com "pads" nas
    // dobras e um brilho que percorre a trilha de vez em quando — dá
    // sensação de placa/hardware de verdade por trás da interface.
    const circuitCount = Math.min(16, Math.max(5, Math.round((w * h) / 130000)));
    circuits = Array.from({ length: circuitCount }, () => makeCircuitTrace());

    // ---- Camada nova: "radares" varrendo — HUD tipo painel de nave ----
    const radarCount = w < 700 ? 1 : 2;
    radars = Array.from({ length: radarCount }, (_, i) => ({
      x: i === 0 ? w * 0.09 : w * 0.91,
      y: i === 0 ? h * 0.88 : h * 0.14,
      r: Math.min(w, h) * (0.07 + Math.random() * 0.03),
      angle: Math.random() * Math.PI * 2,
      speed: (Math.random() < 0.5 ? -1 : 1) * (0.012 + Math.random() * 0.008),
      c: COLORS[i % COLORS.length],
    }));
  }

  function makeCircuitTrace() {
    const segments = 2 + Math.floor(Math.random() * 3);
    let x = Math.random() * w;
    let y = Math.random() * h;
    let horizontal = Math.random() < 0.5;
    const points = [{ x, y }];
    for (let i = 0; i < segments; i++) {
      const len = 40 + Math.random() * 100;
      if (horizontal) x += (Math.random() < 0.5 ? -1 : 1) * len;
      else y += (Math.random() < 0.5 ? -1 : 1) * len;
      x = Math.max(0, Math.min(w, x));
      y = Math.max(0, Math.min(h, y));
      points.push({ x, y });
      horizontal = !horizontal;
    }
    return {
      points,
      c: COLORS[Math.floor(Math.random() * COLORS.length)],
      alpha: 0.05 + Math.random() * 0.05,
      glintT: Math.random(),
      glintSpeed: 0.0025 + Math.random() * 0.0035,
    };
  }

  function pointAlongPath(points, t) {
    let total = 0;
    const lens = [];
    for (let i = 1; i < points.length; i++) {
      const dx = points[i].x - points[i - 1].x;
      const dy = points[i].y - points[i - 1].y;
      const len = Math.sqrt(dx * dx + dy * dy);
      lens.push(len);
      total += len;
    }
    if (total === 0) return points[0];
    let target = t * total;
    for (let i = 0; i < lens.length; i++) {
      if (target <= lens[i] || i === lens.length - 1) {
        const f = lens[i] === 0 ? 0 : target / lens[i];
        const a = points[i], b = points[i + 1];
        return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
      }
      target -= lens[i];
    }
    return points[points.length - 1];
  }

  function randomGlyphText(len) {
    let s = "";
    for (let i = 0; i < len; i++) s += DATA_CHARS[Math.floor(Math.random() * DATA_CHARS.length)];
    return s;
  }

  function makeGlyphColumn() {
    return {
      x: Math.random() * w,
      y: Math.random() * h + h * 0.3,
      speed: 0.08 + Math.random() * 0.14,
      text: randomGlyphText(3 + Math.floor(Math.random() * 5)),
      c: COLORS[Math.floor(Math.random() * COLORS.length)],
      alpha: 0.10 + Math.random() * 0.12,
      changeTimer: Math.random() * 120,
    };
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 200);
  });
  resize();

  // ---- Reatividade ao estado do Jarvis e ao áudio ----
  // window.NeuralBg.setState("listening"|"thinking"|"processing"|"executing"|
  // "speaking"|"success"|"error"|null) muda cor/energia; setLevel(0..1)
  // recebe o volume do microfone. Sem áudio, "speaking" simula ondas suaves.
  const STATE_STYLE = {
    idle:       { rgb: "0, 229, 255",  energy: 1 },
    listening:  { rgb: "0, 255, 170",  energy: 1.9 },
    thinking:   { rgb: "255, 196, 61", energy: 2.8 },
    processing: { rgb: "255, 196, 61", energy: 3.2 },
    executing:  { rgb: "176, 38, 255", energy: 3.4 },
    speaking:   { rgb: "0, 229, 255",  energy: 2.2 },
    success:    { rgb: "57, 255, 120", energy: 2.2 },
    error:      { rgb: "255, 59, 59",  energy: 2.6 },
  };
  let stateName = "idle", energy = 1, targetEnergy = 1;
  let level = 0, targetLevel = 0, lastLevelAt = 0, coreRGB = STATE_STYLE.idle.rgb, ringT = 0;
  window.NeuralBg = {
    setState(name) {
      stateName = STATE_STYLE[name] ? name : "idle";
      targetEnergy = STATE_STYLE[stateName].energy;
    },
    setLevel(v) {
      targetLevel = Math.max(0, Math.min(1, +v || 0));
      lastLevelAt = performance.now();
    },
  };

  function maybeSpawnPulse(edges) {
    // De vez em quando, manda um "pacote de dado" viajar por uma conexão
    // já visível na tela — dá a sensação de rede realmente ativa.
    // (Frequência e limite maiores que antes: mais tráfego de dados.)
    if (pulses.length > 10 * energy || edges.length === 0) return;
    if (Math.random() > 0.045 * energy) return;
    const edge = edges[Math.floor(Math.random() * edges.length)];
    pulses.push({ a: edge.a, b: edge.b, t: 0, speed: 0.012 + Math.random() * 0.012, c: edge.a.c });
  }

  function tick() {
    ctx.clearRect(0, 0, w, h);

    // Paralaxe suavizada (interpola até a posição do mouse em vez de
    // saltar direto), pra sensação ficar fluida e não robótica.
    parallaxX += (mouseX - parallaxX) * 0.03;
    parallaxY += (mouseY - parallaxY) * 0.03;

    // ---- Camada 0: nébulas grandes ao fundo (mais profundas = menos paralaxe) ----
    for (const neb of nebulae) {
      neb.phase += 0.0028;
      neb.x += neb.driftX;
      neb.y += neb.driftY;
      if (neb.x < -neb.r * 0.3) neb.x = w + neb.r * 0.3;
      if (neb.x > w + neb.r * 0.3) neb.x = -neb.r * 0.3;
      if (neb.y < -neb.r * 0.3) neb.y = h + neb.r * 0.3;
      if (neb.y > h + neb.r * 0.3) neb.y = -neb.r * 0.3;

      const ox = neb.x + parallaxX * 12;
      const oy = neb.y + parallaxY * 12;
      const pulse = 0.5 + 0.5 * Math.sin(neb.phase);
      const grad = ctx.createRadialGradient(ox, oy, 0, ox, oy, neb.r);
      grad.addColorStop(0, `rgba(${neb.c}, ${(0.075 + 0.055 * pulse).toFixed(3)})`);
      grad.addColorStop(1, `rgba(${neb.c}, 0)`);
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);
    }

    // ---- Camada de trilhas de circuito (placa de circuito de fundo) ----
    const cpx = parallaxX * 3, cpy = parallaxY * 3;
    for (const c of circuits) {
      ctx.strokeStyle = `rgba(${c.c}, ${c.alpha.toFixed(3)})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      c.points.forEach((p, i) => {
        if (i === 0) ctx.moveTo(p.x + cpx, p.y + cpy);
        else ctx.lineTo(p.x + cpx, p.y + cpy);
      });
      ctx.stroke();
      ctx.fillStyle = `rgba(${c.c}, ${(c.alpha * 1.8).toFixed(3)})`;
      for (const p of c.points) {
        ctx.beginPath();
        ctx.arc(p.x + cpx, p.y + cpy, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!reduceMotion) {
        c.glintT += c.glintSpeed;
        if (c.glintT > 1) c.glintT -= 1;
      }
      const gp = pointAlongPath(c.points, c.glintT);
      if (gp) {
        ctx.save();
        ctx.shadowBlur = 6;
        ctx.shadowColor = `rgba(${c.c}, 0.85)`;
        ctx.fillStyle = `rgba(${c.c}, 0.85)`;
        ctx.beginPath();
        ctx.arc(gp.x + cpx, gp.y + cpy, 1.7, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // ---- Camada 1: estrelas distantes cintilando (profundidade) ----
    for (const s of stars) {
      s.phase += s.speed;
      const alpha = 0.15 + 0.35 * (0.5 + 0.5 * Math.sin(s.phase));
      ctx.fillStyle = `rgba(238, 244, 255, ${alpha.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(s.x + parallaxX * 4, s.y + parallaxY * 4, s.r, 0, Math.PI * 2);
      ctx.fill();
    }

    // ---- Camada 2: nós que se movem e se conectam ----
    for (const n of nodes) {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x <= 0 || n.x >= w) n.vx *= -1;
      if (n.y <= 0 || n.y >= h) n.vy *= -1;
    }

    const px = parallaxX * 8, py = parallaxY * 8;
    const edges = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DIST) {
          const alpha = 0.15 * (1 - dist / LINK_DIST);
          ctx.strokeStyle = `rgba(${a.c}, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x + px, a.y + py);
          ctx.lineTo(b.x + px, b.y + py);
          ctx.stroke();
          edges.push({ a, b });
        }
      }
    }

    // ---- Pulsos de "dado" viajando por uma conexão ----
    if (!reduceMotion) maybeSpawnPulse(edges);
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      p.t += p.speed;
      if (p.t >= 1) { pulses.splice(i, 1); continue; }
      const pulseX = p.a.x + (p.b.x - p.a.x) * p.t + px;
      const pulseY = p.a.y + (p.b.y - p.a.y) * p.t + py;
      ctx.save();
      ctx.shadowBlur = 8;
      ctx.shadowColor = `rgba(${p.c}, 0.9)`;
      ctx.fillStyle = `rgba(${p.c}, 0.95)`;
      ctx.beginPath();
      ctx.arc(pulseX, pulseY, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // ---- Nós em si, com brilho real (glow) ----
    for (const n of nodes) {
      ctx.save();
      ctx.shadowBlur = 6;
      ctx.shadowColor = `rgba(${n.c}, 0.8)`;
      ctx.fillStyle = `rgba(${n.c}, 0.85)`;
      ctx.beginPath();
      ctx.arc(n.x + px, n.y + py, n.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // ---- Radares varrendo — HUD tipo painel de nave/sistema ----
    for (const r of radars) {
      if (!reduceMotion) r.angle += r.speed;
      const ox = r.x + parallaxX * 5;
      const oy = r.y + parallaxY * 5;

      ctx.strokeStyle = `rgba(${r.c}, 0.10)`;
      ctx.lineWidth = 1;
      for (let ring = 1; ring <= 3; ring++) {
        ctx.beginPath();
        ctx.arc(ox, oy, (r.r * ring) / 3, 0, Math.PI * 2);
        ctx.stroke();
      }

      const trailSteps = 16;
      for (let s = 0; s < trailSteps; s++) {
        const a = r.angle - s * 0.05 * Math.sign(r.speed || 1);
        const alpha = (1 - s / trailSteps) * 0.12;
        ctx.strokeStyle = `rgba(${r.c}, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.lineTo(ox + Math.cos(a) * r.r, oy + Math.sin(a) * r.r);
        ctx.stroke();
      }

      ctx.strokeStyle = `rgba(${r.c}, 0.4)`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(ox, oy);
      ctx.lineTo(ox + Math.cos(r.angle) * r.r, oy + Math.sin(r.angle) * r.r);
      ctx.stroke();

      ctx.fillStyle = `rgba(${r.c}, 0.55)`;
      ctx.beginPath();
      ctx.arc(ox, oy, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    // ---- Camada 3: readouts de dados (hex/binário) subindo devagar ----
    ctx.font = "10px 'Consolas', monospace";
    ctx.textBaseline = "middle";
    for (const g of glyphs) {
      g.y -= g.speed;
      g.changeTimer -= 1;
      if (g.changeTimer <= 0) {
        g.text = randomGlyphText(3 + Math.floor(Math.random() * 5));
        g.changeTimer = 60 + Math.random() * 120;
      }
      if (g.y < -20) {
        g.y = h + 20;
        g.x = Math.random() * w;
      }
      ctx.fillStyle = `rgba(${g.c}, ${g.alpha.toFixed(3)})`;
      ctx.fillText(g.text, g.x, g.y);
    }

    // ---- HUD de status no canto — painel de sistema tipo nave/terminal ----
    // Puramente decorativo (não é telemetria real), só reforça a
    // sensação de "painel de tecnologia" no fundo do app inteiro.
    frameCount++;
    lastEdgeCount = edges.length;
    if (w > 480) { // esconde em telas muito estreitas pra não poluir
      const sync = (94 + 5 * Math.sin(frameCount / 90)).toFixed(1);
      const lines = [
        `NODES ${nodes.length.toString().padStart(3, "0")}`,
        `LINKS ${lastEdgeCount.toString().padStart(3, "0")}`,
        `CKTS  ${circuits.length.toString().padStart(3, "0")}`,
        `SYNC  ${sync}%`,
      ];
      ctx.font = "10px 'Consolas', monospace";
      ctx.textBaseline = "top";
      lines.forEach((line, i) => {
        ctx.fillStyle = "rgba(0, 229, 255, 0.22)";
        ctx.fillText(line, 14, 14 + i * 14);
      });
    }

    // ---- Feixe de varredura vertical (scanner de sistema) ----
    if (!reduceMotion) {
      maybeStartScan();
      if (scanSpeed !== 0) {
        scanY += scanSpeed;
        const beamGrad = ctx.createLinearGradient(0, scanY - 90, 0, scanY + 90);
        beamGrad.addColorStop(0, "rgba(0, 229, 255, 0)");
        beamGrad.addColorStop(0.5, "rgba(0, 229, 255, 0.05)");
        beamGrad.addColorStop(1, "rgba(0, 229, 255, 0)");
        ctx.fillStyle = beamGrad;
        ctx.fillRect(0, scanY - 90, w, 180);
        ctx.strokeStyle = "rgba(0, 229, 255, 0.16)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, scanY);
        ctx.lineTo(w, scanY);
        ctx.stroke();
        if (scanY - 90 > h) scanSpeed = 0;
      }
    }

    // ---- Núcleo reativo: brilho + anéis que respondem ao estado/áudio ----
    energy += (targetEnergy - energy) * 0.04;
    const nowMs = performance.now();
    if (stateName === "speaking" && nowMs - lastLevelAt > 400) {
      targetLevel = 0.35 + 0.25 * Math.sin(nowMs / 130) + 0.15 * Math.sin(nowMs / 47);
    } else if (nowMs - lastLevelAt > 400 && stateName !== "speaking") {
      targetLevel = 0;
    }
    level += (targetLevel - level) * 0.18;
    const st = STATE_STYLE[stateName];
    if (stateName !== "idle" || level > 0.02) {
      const cx = w / 2 + parallaxX * 8, cy = h / 2 + parallaxY * 8;
      const R = Math.min(w, h) * (0.28 + level * 0.22);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
      g.addColorStop(0, `rgba(${st.rgb}, ${(0.05 + level * 0.14).toFixed(3)})`);
      g.addColorStop(1, `rgba(${st.rgb}, 0)`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      ringT = (ringT + 0.004 * energy) % 1;
      ctx.lineWidth = 1.2;
      for (let k = 0; k < 3; k++) {
        const t = (ringT + k / 3) % 1;
        ctx.strokeStyle = `rgba(${st.rgb}, ${((1 - t) * (0.10 + level * 0.25)).toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(cx, cy, Math.min(w, h) * (0.08 + t * 0.34), 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    if (!reduceMotion) requestAnimationFrame(tick);
  }

  // Se o usuário prefere menos animação, desenha um quadro só e para.
  tick();
})();
