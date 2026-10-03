(function () {
  const $ = (s) => document.querySelector(s);
  const canvas = $("#gc-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const hud = $("#gc-hud");
  const msg = $("#gc-msg");

  let catalog = null;
  let spec = null;
  let state = null;
  let keys = {};
  let paused = false;
  let raf = null;
  let bullets = [];
  let editorTool = "platform";
  let editorCells = [];

  function initLevelEditor() {
    const grid = $("#gc-level-grid"); if (!grid) return;
    grid.innerHTML = "";
    for (let row=0; row<16; row++) for (let col=0; col<32; col++) {
      const b=document.createElement("button"); b.type="button"; b.className="gc-cell"; b.dataset.col=col; b.dataset.row=row;
      b.addEventListener("click",()=>{ const idx=editorCells.findIndex(c=>c.col===col&&c.row===row); if(editorTool==="erase"){if(idx>=0)editorCells.splice(idx,1)}else{const cell={col,row,kind:editorTool};if(idx>=0)editorCells[idx]=cell;else editorCells.push(cell)}; renderEditor(); }); grid.appendChild(b);
    }
    document.querySelectorAll("#gc-palette button").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll("#gc-palette button").forEach(x=>x.classList.remove("active"));btn.classList.add("active");editorTool=btn.dataset.tool;}));
    $("#gc-clear-level")?.addEventListener("click",()=>{editorCells=[];renderEditor()});
    $("#gc-export-spec")?.addEventListener("click",()=>{const out=$("#gc-spec-out");if(out)out.textContent=JSON.stringify(formPayload(),null,2)});
    renderEditor();
  }
  function renderEditor(){
    document.querySelectorAll("#gc-level-grid .gc-cell").forEach(b=>{const c=editorCells.find(x=>x.col==b.dataset.col&&x.row==b.dataset.row);b.textContent=c?({platform:"🧱",item:"⭐",enemy:"👾",powerup:"⚡",goal:"🏁"}[c.kind]||""):"";});
  }

  function csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : "";
  }

  async function api(url, opts = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      opts.headers || {}
    );
    const r = await fetch(url, Object.assign({}, opts, { headers, credentials: "same-origin" }));
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  }

  function fillSelect(sel, items, valueKey, labelFn) {
    if (!sel) return;
    sel.innerHTML = "";
    items.forEach((it) => {
      const o = document.createElement("option");
      o.value = it[valueKey];
      o.textContent = labelFn(it);
      sel.appendChild(o);
    });
  }

  async function loadCatalog() {
    const data = await api("/api/game-creator/options");
    catalog = data;
    fillSelect($("#gc-type"), data.types, "id", (t) => t.label + " — " + t.desc);
    fillSelect($("#gc-scenario"), data.scenarios, "id", (s) => s.emoji + " " + s.label);
    fillSelect($("#gc-hero"), data.heroes, "id", (h) => h.emoji + " " + h.label);
    fillSelect($("#gc-item"), data.items, "id", (i) => i.emoji + " " + i.label);
    fillSelect($("#gc-monster"), data.monsters, "id", (m) => m.emoji + " " + m.label);
    fillSelect($("#gc-difficulty"), data.difficulties, "id", (d) => d.label);
    const tips = $("#gc-tips");
    if (tips && data.tips) tips.innerHTML = data.tips.map((t) => "<li>" + t + "</li>").join("");
  }

  function formPayload() {
    return {
      title: $("#gc-title")?.value.trim() || "Meu jogo",
      type: $("#gc-type").value,
      scenario: $("#gc-scenario").value,
      hero: $("#gc-hero").value,
      item: $("#gc-item").value,
      monster: $("#gc-monster").value,
      difficulty: $("#gc-difficulty").value,
      description: $("#gc-desc")?.value.trim() || "",
      levels: parseInt($("#gc-levels")?.value || "1", 10) || 1,
      studio: {
        theme: $("#gc-theme")?.value || "cyber", camera: $("#gc-camera")?.value || "follow",
        time_limit: parseInt($("#gc-time")?.value || "0", 10) || 0, score_goal: parseInt($("#gc-score-goal")?.value || "0", 10) || 0,
        checkpoints: $("#gc-checkpoints")?.checked ?? true, difficulty_scaling: $("#gc-scaling")?.checked ?? false,
        save_progress: $("#gc-save-progress")?.checked ?? true, boss: $("#gc-boss")?.value || "none", music: $("#gc-music")?.value || "none",
        story: $("#gc-story")?.value.trim() || "", powerups: editorCells.filter(c=>c.kind==='powerup').map(()=>"speed").slice(0,8)
      },
      editor_cells: editorCells.slice(0, 500)
    };
  }


  function applyFields(f) {
    if (!f) return;
    if (f.title && $("#gc-title")) $("#gc-title").value = f.title;
    if (f.type) $("#gc-type").value = f.type;
    if (f.scenario) $("#gc-scenario").value = f.scenario;
    if (f.hero) $("#gc-hero").value = f.hero;
    if (f.item) $("#gc-item").value = f.item;
    if (f.monster) $("#gc-monster").value = f.monster;
    if (f.difficulty) $("#gc-difficulty").value = f.difficulty;
    if (f.levels && $("#gc-levels")) $("#gc-levels").value = String(f.levels);
    const st=f.studio||{}; if($("#gc-theme"))$("#gc-theme").value=st.theme||"cyber"; if($("#gc-camera"))$("#gc-camera").value=st.camera||"follow";
    if($("#gc-time"))$("#gc-time").value=st.time_limit||0; if($("#gc-score-goal"))$("#gc-score-goal").value=st.score_goal||0;
    if($("#gc-boss"))$("#gc-boss").value=st.boss||"none"; if($("#gc-music"))$("#gc-music").value=st.music||"none";
    if($("#gc-story"))$("#gc-story").value=st.story||""; if($("#gc-checkpoints"))$("#gc-checkpoints").checked=st.checkpoints!==false;
    if($("#gc-scaling"))$("#gc-scaling").checked=!!st.difficulty_scaling; if($("#gc-save-progress"))$("#gc-save-progress").checked=st.save_progress!==false;
    editorCells=Array.isArray(f.editor_cells)?f.editor_cells.map(c=>({col:+c.col,row:+c.row,kind:c.kind})):[]; renderEditor();
  }

  $("#gc-fill")?.addEventListener("click", async () => {
    const st = $("#gc-fill-status");
    if (st) st.textContent = "Preenchendo…";
    try {
      const data = await api("/api/game-creator/fill", {
        method: "POST",
        body: JSON.stringify({ description: $("#gc-desc").value }),
      });
      applyFields(data.fields);
      if (st) st.textContent = "Pronto! Ajuste se quiser e clique em Prévia.";
    } catch (e) {
      if (st) st.textContent = "Erro: " + e.message;
    }
  });

  function cloneEntities(ents) {
    return (ents || []).map((e) => Object.assign({}, e));
  }

  function loadLevel(index) {
    const levels = spec.levels || [{ entities: spec.entities }];
    const lv = levels[Math.min(index, levels.length - 1)];
    state.levelIndex = index;
    state.entities = cloneEntities(lv.entities);
    state.won = false;
    bullets = [];
    const p = player();
    if (p) {
      p.vx = 0;
      p.vy = 0;
    }
  }

  function startGame(s) {
    spec = s;
    canvas.width = s.width || 800;
    canvas.height = s.height || 480;
    state = {
      entities: [],
      lives: s.lives,
      score: 0,
      won: false,
      lost: false,
      time: 0,
      levelIndex: 0,
      invuln: 0,
    };
    paused = false;
    if (msg) msg.textContent = "";
    loadLevel(0);
    updateHud();
    if (raf) cancelAnimationFrame(raf);
    last = performance.now();
    loop(last);
  }

  function updateHud() {
    if (!hud || !state) return;
    const lv = (state.levelIndex || 0) + 1;
    const total = (spec.levels && spec.levels.length) || 1;
    hud.textContent = `❤️ ${state.lives}  ·  ⭐ ${state.score}  ·  Fase ${lv}/${total}`;
  }

  function player() {
    return state && state.entities.find((e) => e.kind === "player");
  }

  function aabb(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function step(dt) {
    if (!state || paused || state.won || state.lost) return;
    state.time += dt;
    if (state.invuln > 0) state.invuln -= dt;
    const p = player();
    if (!p) return;
    const speed = 200 * (spec.speed || 1);
    const gravity = spec.type === "shooter" ? 0 : 980;
    const jump = -420;

    let mx = 0, my = 0;
    if (keys.ArrowLeft || keys.a || keys.A || keys._left) mx -= 1;
    if (keys.ArrowRight || keys.d || keys.D || keys._right) mx += 1;
    if (spec.type === "shooter" || spec.type === "maze") {
      if (keys.ArrowUp || keys.w || keys.W || keys._jump) my -= 1;
      if (keys.ArrowDown || keys.s || keys.S) my += 1;
    }
    p.vx = mx * speed;
    if (spec.type === "shooter" || spec.type === "maze") {
      p.vy = my * speed;
    } else {
      p.vy += gravity * dt;
    }

    const wantJump = keys.ArrowUp || keys.w || keys.W || keys[" "] || keys._jump;
    let grounded = false;

    p.x += p.vx * dt;
    p.y += p.vy * dt;

    if (spec.type !== "shooter") {
      state.entities.forEach((e) => {
        if (e.kind !== "platform" && e.kind !== "wall") return;
        if (!aabb(p, e)) return;
        const prevBottom = p.y + p.h - p.vy * dt;
        if (p.vy >= 0 && prevBottom <= e.y + 6) {
          p.y = e.y - p.h;
          p.vy = 0;
          grounded = true;
        } else if (p.vy < 0 && p.y < e.y + e.h) {
          p.y = e.y + e.h;
          p.vy = 0;
        } else if (p.vx > 0) {
          p.x = e.x - p.w;
        } else if (p.vx < 0) {
          p.x = e.x + e.w;
        }
      });
      if (wantJump && grounded && spec.type !== "maze") p.vy = jump;
    }

    // bounds
    p.x = Math.max(0, Math.min((spec.width || 800) - p.w, p.x));
    p.y = Math.max(0, Math.min((spec.height || 480) - p.h, p.y));

    if (spec.type !== "shooter" && p.y > (spec.height || 480) + 20) {
      hurt(1);
      p.x = 50;
      p.y = (spec.height || 480) - 100;
      p.vy = 0;
    }

    // items / powerups
    state.entities.forEach((e) => {
      if (e._taken) return;
      if (e.kind === "item" && aabb(p, e)) {
        e._taken = true;
        state.score += e.points || 10;
        updateHud();
      }
      if (e.kind === "powerup" && aabb(p, e)) {
        e._taken = true;
        if (e.effect === "life") {
          state.lives += 1;
          updateHud();
        }
      }
    });

    // enemies
    state.entities.forEach((e) => {
      if (e.kind !== "enemy") return;
      if (e.patrol) {
        e._dir = e._dir || 1;
        e.x += e._dir * 70 * (spec.speed || 1) * dt;
        if (e.x < e.patrol[0] || e.x > e.patrol[1]) e._dir *= -1;
      } else if (e.chase) {
        e.x += Math.sign(p.x - e.x) * 90 * (spec.speed || 1) * dt;
        e.y += Math.sign(p.y - e.y) * 50 * (spec.speed || 1) * dt;
      } else if (e.vx) {
        e.x += e.vx * (spec.speed || 1) * dt;
        if (e.x < -40) e.x = (spec.width || 800) + 20;
      }
      if (aabb(p, e) && state.invuln <= 0) {
        hurt(1);
        if (spec.type !== "shooter") {
          p.x = Math.max(20, p.x - 40);
          p.vy = -120;
        }
      }
    });

    // shooter bullets
    if (spec.type === "shooter") {
      if ((keys[" "] || keys._jump) && !keys._shot) {
        keys._shot = true;
        bullets.push({ x: p.x + p.w, y: p.y + p.h / 2, w: 10, h: 4, vx: 400 });
      }
      if (!keys[" "] && !keys._jump) keys._shot = false;
      bullets.forEach((b) => {
        b.x += b.vx * dt;
        state.entities.forEach((e) => {
          if (e.kind === "enemy" && !e._taken && aabb(b, e)) {
            e._taken = true;
            b._dead = true;
            state.score += 25;
            updateHud();
          }
        });
      });
      bullets = bullets.filter((b) => !b._dead && b.x < (spec.width || 800) + 20);
      const left = state.entities.filter((e) => e.kind === "enemy" && !e._taken).length;
      if (left === 0) nextLevelOrWin();
    }

    // goal / win conditions
    const goal = state.entities.find((e) => e.kind === "goal");
    if (goal && aabb(p, goal)) {
      if (spec.win_mode === "collect_all") {
        const left = state.entities.filter((e) => e.kind === "item" && !e._taken).length;
        if (left === 0) nextLevelOrWin();
      } else if (spec.win_mode !== "survive_or_clear") {
        nextLevelOrWin();
      }
    }
    if (spec.win_mode === "collect_all") {
      const left = state.entities.filter((e) => e.kind === "item" && !e._taken).length;
      if (left === 0) nextLevelOrWin();
    }
  }

  function hurt(n) {
    if (state.invuln > 0) return;
    state.lives -= n;
    state.invuln = 1.2;
    updateHud();
    if (state.lives <= 0) {
      state.lost = true;
      if (msg) msg.textContent = "💀 Game over! Clique em Reiniciar.";
    }
  }

  function nextLevelOrWin() {
    const total = (spec.levels && spec.levels.length) || 1;
    if (state.levelIndex + 1 < total) {
      state.levelIndex += 1;
      loadLevel(state.levelIndex);
      if (msg) msg.textContent = "✨ Fase " + (state.levelIndex + 1) + "!";
      updateHud();
      setTimeout(() => {
        if (msg && !state.won) msg.textContent = "";
      }, 1200);
    } else {
      state.won = true;
      if (msg) msg.textContent = "🏆 Você venceu! Pontos: " + state.score;
    }
  }

  function draw() {
    if (!spec || !state) return;
    ctx.fillStyle = spec.bg || "#0b1628";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    for (let i = 0; i < 40; i++) {
      ctx.fillRect((i * 97) % canvas.width, (i * 53) % (canvas.height / 2), 2, 2);
    }
    state.entities.forEach((e) => {
      if (e._taken) return;
      if (e.kind === "platform" || e.kind === "wall") {
        ctx.fillStyle = e.kind === "wall" ? "#3a4560" : "#2d6a4f";
        ctx.fillRect(e.x, e.y, e.w, e.h);
        return;
      }
      const emoji = e.emoji || "⬜";
      ctx.font = Math.floor(e.h) + "px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      if (e.kind === "player" && state.invuln > 0 && Math.floor(state.time * 10) % 2 === 0) return;
      ctx.fillText(emoji, e.x + e.w / 2, e.y + e.h / 2);
    });
    ctx.fillStyle = "#fbbf24";
    bullets.forEach((b) => ctx.fillRect(b.x, b.y, b.w, b.h));
  }

  let last = performance.now();
  function loop(now) {
    const dt = Math.min(0.033, (now - last) / 1000);
    last = now;
    step(dt);
    draw();
    raf = requestAnimationFrame(loop);
  }

  window.addEventListener("keydown", (e) => {
    keys[e.key] = true;
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "].includes(e.key)) e.preventDefault();
  });
  window.addEventListener("keyup", (e) => {
    keys[e.key] = false;
  });

  const touch = $("#gc-touch");
  if (touch) {
    touch.addEventListener("pointerdown", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const d = btn.dataset.dir;
      if (d === "left") keys._left = true;
      if (d === "right") keys._right = true;
      if (d === "jump") keys._jump = true;
    });
    const clear = () => {
      keys._left = keys._right = keys._jump = false;
    };
    touch.addEventListener("pointerup", clear);
    touch.addEventListener("pointerleave", clear);
  }

  $("#gc-preview")?.addEventListener("click", async () => {
    const st = $("#gc-status");
    if (st) st.textContent = "Gerando jogo…";
    try {
      const data = await api("/api/game-creator/build", {
        method: "POST",
        body: JSON.stringify(formPayload()),
      });
      startGame(data.spec);
      if (st) st.textContent = "Prévia pronta — jogue!";
    } catch (e) {
      if (st) st.textContent = "Erro: " + e.message;
    }
  });

  $("#gc-save")?.addEventListener("click", async () => {
    const st = $("#gc-status");
    if (st) st.textContent = "Salvando…";
    try {
      const data = await api("/api/game-creator/save", {
        method: "POST",
        body: JSON.stringify(formPayload()),
      });
      if (st) st.textContent = "Salvo: " + (data.title || data.id);
      loadMyGames();
    } catch (e) {
      if (st) st.textContent = "Erro: " + e.message;
    }
  });

  $("#gc-restart")?.addEventListener("click", () => {
    if (spec) startGame(spec);
  });
  $("#gc-pause")?.addEventListener("click", () => {
    paused = !paused;
    $("#gc-pause").textContent = paused ? "Continuar" : "Pausar";
  });

  async function loadMyGames() {
    const box = $("#gc-my-games");
    if (!box) return;
    try {
      const data = await api("/api/game-creator/list");
      if (!data.games || !data.games.length) {
        box.textContent = "Nenhum jogo salvo ainda.";
        return;
      }
      box.innerHTML = "";
      data.games.forEach((g) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "gc-game-chip";
        b.textContent = `${g.scenario_emoji || "🎮"} ${g.hero_emoji || ""} ${g.title} · ${g.type}`;
        b.addEventListener("click", async () => {
          const full = await api("/api/game-creator/load/" + encodeURIComponent(g.id));
          if (full.spec) {
            applyFields(full.spec);
            startGame(full.spec);
            if ($("#gc-status")) $("#gc-status").textContent = "Carregado: " + full.spec.title;
          }
        });
        box.appendChild(b);
      });
    } catch (e) {
      box.textContent = "Faça login para ver jogos salvos.";
    }
  }

  initLevelEditor();
  loadCatalog()
    .then(loadMyGames)
    .catch((e) => {
      if ($("#gc-status")) $("#gc-status").textContent = "Falha: " + e.message;
    });
})();
