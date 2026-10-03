/**
 * JARVIS Game Studio 5.0
 * Real project editor + canvas runtime (client-side only).
 * Does not execute user code on the server.
 */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const API = {
    async j(url, opts) {
      const r = await fetch(url, {
        headers: { "Content-Type": "application/json", ...(opts && opts.headers) },
        ...opts,
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.error || d.message || r.statusText);
      return d;
    },
  };

  // -------------------- Runtime --------------------
  class GameRuntime {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.running = false;
      this.paused = false;
      this.raf = 0;
      this.keys = {};
      this.touch = { left: false, right: false, jump: false };
      this.state = null;
      this.logs = [];
      this.fps = 0;
      this._acc = 0;
      this._frames = 0;
      this._lastFps = performance.now();
      this.onHud = null;
      this.onEnd = null;
      this._boundKey = this._onKey.bind(this);
    }
    log(msg) {
      this.logs.push({ t: Date.now(), msg: String(msg) });
      if (this.logs.length > 80) this.logs.shift();
    }
    load(projectData) {
      const data = JSON.parse(JSON.stringify(projectData || {}));
      const li = data.currentLevel || 0;
      const level = (data.levels || [])[li] || { width: 640, height: 400, entities: [], events: [] };
      this.project = data;
      this.level = level;
      this.W = level.width || 640;
      this.H = level.height || 400;
      this.canvas.width = this.W;
      this.canvas.height = this.H;
      this.entities = (level.entities || []).map((e) => ({ ...e, _dead: false, _vx: 0, _vy: 0, _dir: 1 }));
      this.events = level.events || [];
      this.score = 0;
      this.flags = {};
      this.status = "PLAYING"; // PLAYING | WIN | LOSE
      this.checkpoint = null;
      const player = this.entities.find((e) => e.type === "player");
      if (player) {
        this.spawnX = player.x;
        this.spawnY = player.y;
        player._vy = 0;
        player._vx = 0;
        player.hp = player.hp != null ? player.hp : 3;
        player.maxHp = player.maxHp || player.hp;
      }
      this.log("Level loaded: " + (level.name || li));
      this._draw();
      this._hud();
    }
    start() {
      if (this.running) return;
      this.running = true;
      this.paused = false;
      window.addEventListener("keydown", this._boundKey);
      window.addEventListener("keyup", this._boundKey);
      this._last = performance.now();
      const loop = (t) => {
        if (!this.running) return;
        const dt = Math.min(0.05, (t - this._last) / 1000);
        this._last = t;
        if (!this.paused && this.status === "PLAYING") this._update(dt);
        this._draw();
        this._frames++;
        if (t - this._lastFps > 500) {
          this.fps = Math.round((this._frames * 1000) / (t - this._lastFps));
          this._frames = 0;
          this._lastFps = t;
          this._hud();
        }
        this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    }
    stop() {
      this.running = false;
      cancelAnimationFrame(this.raf);
      window.removeEventListener("keydown", this._boundKey);
      window.removeEventListener("keyup", this._boundKey);
    }
    pause() {
      this.paused = true;
      this._hud();
    }
    resume() {
      this.paused = false;
      this._last = performance.now();
      this._hud();
    }
    restart() {
      if (this.project) this.load(this.project);
      this.paused = false;
      if (!this.running) this.start();
    }
    _onKey(e) {
      const down = e.type === "keydown";
      this.keys[e.code] = down;
      if (["Space", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.code)) e.preventDefault();
    }
    _player() {
      return this.entities.find((e) => e.type === "player" && !e._dead);
    }
    _aabb(a, b) {
      return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
    }
    _solids() {
      return this.entities.filter((e) => !e._dead && e.solid && e.type !== "player");
    }
    _update(dt) {
      const p = this._player();
      if (!p) return;
      const speed = Number(p.speed) || 160;
      const jump = Number(p.jump) || 400;
      const grav = Number(this.level.gravity || p.gravity) || 1100;
      let mx = 0;
      if (this.keys.ArrowLeft || this.keys.KeyA || this.touch.left) mx -= 1;
      if (this.keys.ArrowRight || this.keys.KeyD || this.touch.right) mx += 1;
      p._vx = mx * speed;
      // ground check
      const feet = { x: p.x + 2, y: p.y + p.h, w: p.w - 4, h: 4 };
      let onGround = false;
      for (const s of this._solids()) {
        if (this._aabb(feet, s) && p._vy >= 0) {
          onGround = true;
          p.y = s.y - p.h;
          p._vy = 0;
        }
      }
      if ((this.keys.Space || this.keys.ArrowUp || this.keys.KeyW || this.touch.jump) && onGround) {
        p._vy = -jump;
      }
      p._vy += grav * dt;
      p.x += p._vx * dt;
      p.y += p._vy * dt;
      // horizontal resolve
      for (const s of this._solids()) {
        if (!this._aabb(p, s)) continue;
        if (p._vx > 0) p.x = s.x - p.w;
        else if (p._vx < 0) p.x = s.x + s.w;
      }
      // vertical resolve
      for (const s of this._solids()) {
        if (!this._aabb(p, s)) continue;
        if (p._vy > 0) {
          p.y = s.y - p.h;
          p._vy = 0;
          onGround = true;
        } else if (p._vy < 0) {
          p.y = s.y + s.h;
          p._vy = 0;
        }
      }
      // enemies patrol / chase
      for (const e of this.entities) {
        if (e._dead || e.type !== "enemy") continue;
        const sp = Number(e.speed) || 50;
        if (e.behavior === "chase" && p) {
          e.x += (p.x < e.x ? -1 : 1) * sp * dt;
        } else {
          e.x += (e._dir || 1) * sp * dt;
          const min = e.patrolMin != null ? e.patrolMin : e.x - 40;
          const max = e.patrolMax != null ? e.patrolMax : e.x + 40;
          if (e.x < min) {
            e.x = min;
            e._dir = 1;
          }
          if (e.x > max) {
            e.x = max;
            e._dir = -1;
          }
        }
      }
      // events
      this._runEvents(p);
      this._hud();
    }
    _runEvents(p) {
      for (const ev of this.events) {
        if (ev.when === "collision") {
          const targets = this.entities.filter(
            (e) => !e._dead && e.type === ev.bType && this._aabb(p, e)
          );
          for (const t of targets) this._doActions(ev.actions || [], p, t);
        } else if (ev.when === "player_y_gt" && p.y > Number(ev.value)) {
          this._doActions(ev.actions || [], p, null);
        } else if (ev.when === "player_hp_lte" && (p.hp || 0) <= Number(ev.value)) {
          this._doActions(ev.actions || [], p, null);
        }
      }
    }
    _doActions(actions, player, target) {
      for (const a of actions) {
        const t = a.type;
        if (t === "add_score") {
          let v = a.value;
          if (v === "target.points" && target) v = target.points || 10;
          this.score += Number(v) || 0;
        } else if (t === "remove_target" && target) {
          target._dead = true;
        } else if (t === "damage_player") {
          if (player._invuln && player._invuln > performance.now()) continue;
          player.hp = (player.hp || 1) - (Number(a.value) || 1);
          player._invuln = performance.now() + 800;
          this.log("Dano! HP=" + player.hp);
        } else if (t === "knockback" && player) {
          player._vy = -220;
          player.x += player._vx >= 0 ? -24 : 24;
        } else if (t === "win") {
          this.status = "WIN";
          this.log("Vitória!");
          if (this.onEnd) this.onEnd("WIN");
        } else if (t === "lose") {
          this.status = "LOSE";
          this.log("Derrota");
          if (this.onEnd) this.onEnd("LOSE");
        } else if (t === "respawn" && player) {
          const cp = this.checkpoint;
          player.x = cp ? cp.x : this.spawnX;
          player.y = cp ? cp.y : this.spawnY;
          player._vy = 0;
        } else if (t === "set_checkpoint" && target) {
          this.checkpoint = { x: target.x, y: target.y - 20 };
          this.log("Checkpoint");
        } else if (t === "set_flag") {
          this.flags[a.flag] = a.value;
        } else if (t === "require_flag") {
          if (!this.flags[a.flag]) return;
        } else if (t === "play_sound") {
          this._beep(a.sound);
        }
      }
    }
    _beep(kind) {
      try {
        const A = window.AudioContext || window.webkitAudioContext;
        if (!A) return;
        if (!this._ac) this._ac = new A();
        const o = this._ac.createOscillator();
        const g = this._ac.createGain();
        o.frequency.value = kind === "coin" ? 880 : kind === "hit" ? 160 : kind === "win" ? 520 : 400;
        o.connect(g);
        g.connect(this._ac.destination);
        g.gain.value = 0.04;
        o.start();
        o.stop(this._ac.currentTime + 0.1);
      } catch (_) {}
    }
    _draw() {
      const ctx = this.ctx;
      const bg = (this.level && this.level.background) || "#0f172a";
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, this.W, this.H);
      // grid
      if (this.project && this.project.settings && this.project.settings.showGrid) {
        ctx.strokeStyle = "rgba(148,163,184,0.12)";
        ctx.lineWidth = 1;
        for (let x = 0; x < this.W; x += 32) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, this.H);
          ctx.stroke();
        }
        for (let y = 0; y < this.H; y += 32) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(this.W, y);
          ctx.stroke();
        }
      }
      for (const e of this.entities) {
        if (e._dead || e.visible === false) continue;
        ctx.fillStyle = e.color || "#94a3b8";
        if (e.type === "coin") {
          ctx.beginPath();
          ctx.arc(e.x + e.w / 2, e.y + e.h / 2, e.w / 2, 0, Math.PI * 2);
          ctx.fill();
        } else if (e.type === "player") {
          ctx.fillRect(e.x, e.y, e.w, e.h);
          ctx.fillStyle = "#e0f2fe";
          ctx.fillRect(e.x + 6, e.y + 8, 6, 6);
          ctx.fillRect(e.x + e.w - 12, e.y + 8, 6, 6);
        } else {
          ctx.fillRect(e.x, e.y, e.w, e.h);
        }
        if (this.project && this.project.settings && this.project.settings.debug) {
          ctx.strokeStyle = "#f472b6";
          ctx.strokeRect(e.x, e.y, e.w, e.h);
          ctx.fillStyle = "#fff";
          ctx.font = "10px sans-serif";
          ctx.fillText(e.type, e.x, e.y - 2);
        }
      }
      if (this.status === "WIN" || this.status === "LOSE") {
        ctx.fillStyle = "rgba(2,6,23,0.65)";
        ctx.fillRect(0, 0, this.W, this.H);
        ctx.fillStyle = this.status === "WIN" ? "#22c55e" : "#f87171";
        ctx.font = "bold 28px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(this.status === "WIN" ? "VITÓRIA!" : "DERROTA", this.W / 2, this.H / 2);
        ctx.textAlign = "left";
      }
      if (this.paused && this.status === "PLAYING") {
        ctx.fillStyle = "rgba(2,6,23,0.45)";
        ctx.fillRect(0, 0, this.W, this.H);
        ctx.fillStyle = "#e2e8f0";
        ctx.font = "bold 22px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("PAUSADO", this.W / 2, this.H / 2);
        ctx.textAlign = "left";
      }
    }
    _hud() {
      if (this.onHud) {
        const p = this._player();
        this.onHud({
          score: this.score,
          hp: p ? p.hp : 0,
          maxHp: p ? p.maxHp || 3 : 3,
          fps: this.fps,
          status: this.status,
          paused: this.paused,
        });
      }
    }
  }

  // -------------------- Studio App --------------------
  const Studio = {
    project: null,
    selectedId: null,
    runtime: null,
    mode: "edit", // edit | play

    async boot() {
      const root = $("#gs-root");
      if (!root) return;
      this.bindTabs();
      this.bindToolbar();
      await this.refreshList();
      // auto open test if requested
      const q = new URLSearchParams(location.search);
      if (q.get("studio") === "1" || q.get("new") === "1") this.showPanel("studio");
      if (q.get("test") === "1") {
        this.showPanel("studio");
        await this.ensureTest();
      }
    },

    showPanel(name) {
      $$(".gs-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
      $$(".gs-tab").forEach((t) => t.classList.toggle("active", t.dataset.panel === name));
    },

    bindTabs() {
      $$(".gs-tab").forEach((t) =>
        t.addEventListener("click", () => {
          this.showPanel(t.dataset.panel);
          if (t.dataset.panel === "mygames") this.refreshList();
          if (t.dataset.panel === "gallery") this.refreshGallery();
        })
      );
    },

    bindToolbar() {
      const n = $("#gs-new");
      if (n) n.onclick = () => this.openNewModal();
      const t = $("#gs-ensure-test");
      if (t) t.onclick = () => this.ensureTest();
      $$("[data-gs-action]").forEach((b) => {
        b.addEventListener("click", () => {
          const a = b.dataset.gsAction;
          if (a === "new") this.openNewModal();
          if (a === "test") this.ensureTest();
          if (a === "mygames") this.showPanel("mygames");
          if (a === "gallery") this.showPanel("gallery");
        });
      });
      const save = $("#gs-save");
      if (save) save.onclick = () => this.save();
      const play = $("#gs-play");
      if (play) play.onclick = () => this.play();
      const stop = $("#gs-stop");
      if (stop) stop.onclick = () => this.stopPlay();
      const check = $("#gs-check");
      if (check) check.onclick = () => this.runCheck();
      const pub = $("#gs-publish");
      if (pub) pub.onclick = () => this.publish();
      const coder = $("#gs-coder-run");
      if (coder) coder.onclick = () => this.runCoder();
      // object add buttons
      $$("[data-gs-add]").forEach((b) =>
        b.addEventListener("click", () => this.addEntity(b.dataset.gsAdd))
      );
      // props
      const form = $("#gs-props-form");
      if (form) {
        form.addEventListener("change", () => this.applyPropsFromForm());
        form.addEventListener("input", () => this.applyPropsFromForm());
      }
      const del = $("#gs-delete-obj");
      if (del) del.onclick = () => this.deleteSelected();
      const dup = $("#gs-dup-obj");
      if (dup) dup.onclick = () => this.duplicateSelected();
      // canvas pick
      const c = $("#gs-editor-canvas");
      if (c) {
        c.addEventListener("mousedown", (e) => this.onCanvasDown(e));
        c.addEventListener("mousemove", (e) => this.onCanvasMove(e));
        c.addEventListener("mouseup", () => (this._drag = null));
        c.addEventListener("touchstart", (e) => this.onCanvasDown(e.touches[0], e), { passive: false });
        c.addEventListener("touchmove", (e) => this.onCanvasMove(e.touches[0], e), { passive: false });
        c.addEventListener("touchend", () => (this._drag = null));
      }
      // mobile nudge
      $$("[data-gs-nudge]").forEach((b) =>
        b.addEventListener("click", () => this.nudgeSelected(b.dataset.gsNudge))
      );
      // touch game controls
      ["left", "right", "jump"].forEach((k) => {
        $$(`[data-gs-touch="${k}"]`).forEach((btn) => {
          const set = (v) => {
            if (this.runtime) this.runtime.touch[k] = v;
          };
          btn.addEventListener("touchstart", (e) => {
            e.preventDefault();
            set(true);
          });
          btn.addEventListener("touchend", () => set(false));
          btn.addEventListener("mousedown", () => set(true));
          btn.addEventListener("mouseup", () => set(false));
        });
      });
    },

    async refreshList() {
      const box = $("#gs-my-games");
      if (!box) return;
      try {
        const d = await API.j("/api/cyber/game-studio/overview");
        const list = d.projects || [];
        box.innerHTML = list.length
          ? list
              .map(
                (p) => `<article class="gs-card">
            <strong>${esc(p.name)}</strong>
            <p class="muted small">${esc(p.template)} · v${p.version} · ${esc(p.status)}</p>
            <div class="gs-card-actions">
              <button type="button" class="btn primary btn-sm" data-open="${esc(p.id)}">Editar</button>
              <button type="button" class="btn btn-sm" data-play-id="${esc(p.id)}">▶ Jogar</button>
            </div>
          </article>`
              )
              .join("")
          : `<p class="muted">Nenhum projeto ainda. Clique em + Novo Jogo ou JARVIS TEST PLATFORMER.</p>`;
        box.querySelectorAll("[data-open]").forEach((b) => (b.onclick = () => this.openProject(b.dataset.open)));
        box.querySelectorAll("[data-play-id]").forEach(
          (b) =>
            (b.onclick = async () => {
              await this.openProject(b.dataset.playId);
              this.play();
            })
        );
        const tpl = $("#gs-templates");
        if (tpl && d.templates) {
          tpl.innerHTML = d.templates
            .map(
              (t) => `<button type="button" class="btn" data-tpl="${esc(t.id)}">${esc(t.name)}</button>`
            )
            .join("");
          tpl.querySelectorAll("[data-tpl]").forEach(
            (b) =>
              (b.onclick = () => {
                $("#gs-new-template").value = b.dataset.tpl;
                this.openNewModal();
              })
          );
        }
      } catch (e) {
        box.innerHTML = `<p class="muted">Erro ao listar: ${esc(e.message)}</p>`;
      }
    },

    async refreshGallery() {
      const box = $("#gs-gallery");
      if (!box) return;
      try {
        const d = await API.j("/api/cyber/game-studio/overview");
        const list = d.published || [];
        box.innerHTML = list.length
          ? list
              .map(
                (p) => `<article class="gs-card">
              <strong>${esc(p.name)}</strong>
              <p class="muted small">Publicado · v${p.version}</p>
              <button type="button" class="btn primary btn-sm" data-play-id="${esc(p.id)}">▶ Jogar</button>
            </article>`
              )
              .join("")
          : `<p class="muted">Nenhum jogo publicado ainda.</p>`;
        box.querySelectorAll("[data-play-id]").forEach(
          (b) =>
            (b.onclick = async () => {
              await this.openProject(b.dataset.playId);
              this.play();
            })
        );
      } catch (_) {}
    },

    openNewModal() {
      const m = $("#gs-new-modal");
      if (m) m.hidden = false;
    },
    closeNewModal() {
      const m = $("#gs-new-modal");
      if (m) m.hidden = true;
    },

    async createNew() {
      const name = ($("#gs-new-name") && $("#gs-new-name").value) || "Meu Jogo";
      const description = ($("#gs-new-desc") && $("#gs-new-desc").value) || "";
      const template = ($("#gs-new-template") && $("#gs-new-template").value) || "platformer";
      const gameType = ($("#gs-new-type") && $("#gs-new-type").value) || "plataforma";
      const difficulty = ($("#gs-new-diff") && $("#gs-new-diff").value) || "normal";
      try {
        const p = await API.j("/api/cyber/game-studio/projects", {
          method: "POST",
          body: JSON.stringify({ name, description, template, gameType, difficulty }),
        });
        this.closeNewModal();
        this.project = p;
        this.renderEditor();
        this.showPanel("editor");
        this.toast("Projeto criado");
        this.refreshList();
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    async ensureTest() {
      try {
        const p = await API.j("/api/cyber/game-studio/test-platformer", { method: "POST", body: "{}" });
        this.project = p;
        this.renderEditor();
        this.showPanel("editor");
        this.toast("JARVIS TEST PLATFORMER pronto");
        this.refreshList();
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    async openProject(id) {
      const p = await API.j("/api/cyber/game-studio/projects/" + encodeURIComponent(id));
      this.project = p;
      this.renderEditor();
      this.showPanel("editor");
    },

    currentLevel() {
      const data = this.project.data || {};
      const levels = data.levels || [];
      const i = data.currentLevel || 0;
      return levels[i] || null;
    },

    renderEditor() {
      if (!this.project) return;
      $("#gs-editor-title") && ($("#gs-editor-title").textContent = this.project.name || "Editor");
      $("#gs-editor-meta") &&
        ($("#gs-editor-meta").textContent = `v${this.project.version} · ${this.project.status || "DRAFT"}`);
      const lvl = this.currentLevel();
      const list = $("#gs-obj-list");
      if (list && lvl) {
        list.innerHTML = (lvl.entities || [])
          .map(
            (e) =>
              `<button type="button" class="gs-obj-item ${this.selectedId === e.id ? "active" : ""}" data-eid="${esc(e.id)}">${esc(e.type)} — ${esc(e.name || e.id)}</button>`
          )
          .join("");
        list.querySelectorAll("[data-eid]").forEach((b) => (b.onclick = () => this.selectEntity(b.dataset.eid)));
      }
      const code = $("#gs-code");
      if (code) code.value = (this.project.data && this.project.data.code) || "";
      this.drawEditorCanvas();
      this.fillProps();
    },

    selectEntity(id) {
      this.selectedId = id;
      this.renderEditor();
    },

    fillProps() {
      const form = $("#gs-props-form");
      if (!form) return;
      const lvl = this.currentLevel();
      const e = lvl && (lvl.entities || []).find((x) => x.id === this.selectedId);
      if (!e) {
        form.innerHTML = `<p class="muted small">Selecione um objeto</p>`;
        return;
      }
      const fields = [
        ["name", "Nome", e.name],
        ["x", "X", e.x],
        ["y", "Y", e.y],
        ["w", "Largura", e.w],
        ["h", "Altura", e.h],
        ["color", "Cor", e.color || "#94a3b8"],
        ["speed", "Velocidade", e.speed],
        ["jump", "Pulo", e.jump],
        ["hp", "Vida", e.hp],
        ["damage", "Dano", e.damage],
        ["points", "Pontos", e.points],
        ["behavior", "Comportamento", e.behavior || ""],
      ];
      form.innerHTML = fields
        .map(
          ([k, label, val]) =>
            `<label class="gs-prop"><span>${label}</span><input data-prop="${k}" value="${esc(val ?? "")}" /></label>`
        )
        .join("");
    },

    applyPropsFromForm() {
      const lvl = this.currentLevel();
      if (!lvl || !this.selectedId) return;
      const e = (lvl.entities || []).find((x) => x.id === this.selectedId);
      if (!e) return;
      $$("#gs-props-form [data-prop]").forEach((inp) => {
        const k = inp.dataset.prop;
        let v = inp.value;
        if (["x", "y", "w", "h", "speed", "jump", "hp", "damage", "points"].includes(k)) v = Number(v) || 0;
        e[k] = v;
      });
      this.drawEditorCanvas();
    },

    drawEditorCanvas() {
      const c = $("#gs-editor-canvas");
      if (!c) return;
      const lvl = this.currentLevel();
      if (!lvl) return;
      c.width = lvl.width || 640;
      c.height = lvl.height || 400;
      const rt = new GameRuntime(c);
      rt.load({ ...this.project.data, levels: [lvl], currentLevel: 0, settings: { ...(this.project.data.settings || {}), showGrid: true, debug: true } });
      // highlight selection
      if (this.selectedId) {
        const e = (lvl.entities || []).find((x) => x.id === this.selectedId);
        if (e) {
          const ctx = c.getContext("2d");
          ctx.strokeStyle = "#22d3ee";
          ctx.lineWidth = 2;
          ctx.strokeRect(e.x - 2, e.y - 2, e.w + 4, e.h + 4);
        }
      }
    },

    onCanvasDown(pt, ev) {
      if (ev) ev.preventDefault();
      const c = $("#gs-editor-canvas");
      const rect = c.getBoundingClientRect();
      const scaleX = c.width / rect.width;
      const scaleY = c.height / rect.height;
      const x = (pt.clientX - rect.left) * scaleX;
      const y = (pt.clientY - rect.top) * scaleY;
      const lvl = this.currentLevel();
      if (!lvl) return;
      const hit = [...(lvl.entities || [])].reverse().find((e) => x >= e.x && x <= e.x + e.w && y >= e.y && y <= e.y + e.h);
      if (hit) {
        this.selectedId = hit.id;
        this._drag = { id: hit.id, ox: x - hit.x, oy: y - hit.y };
        this.renderEditor();
      }
    },
    onCanvasMove(pt, ev) {
      if (!this._drag) return;
      if (ev) ev.preventDefault();
      const c = $("#gs-editor-canvas");
      const rect = c.getBoundingClientRect();
      const scaleX = c.width / rect.width;
      const scaleY = c.height / rect.height;
      const x = (pt.clientX - rect.left) * scaleX;
      const y = (pt.clientY - rect.top) * scaleY;
      const lvl = this.currentLevel();
      const e = (lvl.entities || []).find((x) => x.id === this._drag.id);
      if (!e) return;
      e.x = Math.round(x - this._drag.ox);
      e.y = Math.round(y - this._drag.oy);
      this.fillProps();
      this.drawEditorCanvas();
    },

    nudgeSelected(dir) {
      const lvl = this.currentLevel();
      const e = lvl && (lvl.entities || []).find((x) => x.id === this.selectedId);
      if (!e) return;
      const step = 8;
      if (dir === "left") e.x -= step;
      if (dir === "right") e.x += step;
      if (dir === "up") e.y -= step;
      if (dir === "down") e.y += step;
      this.fillProps();
      this.drawEditorCanvas();
    },

    addEntity(type) {
      const lvl = this.currentLevel();
      if (!lvl) return;
      const id = type + "_" + Math.random().toString(16).slice(2, 8);
      const defaults = {
        player: { w: 28, h: 36, color: "#38bdf8", speed: 160, jump: 400, hp: 3, maxHp: 3 },
        enemy: { w: 28, h: 28, color: "#f87171", speed: 50, damage: 1, behavior: "patrol", solid: true, patrolMin: 100, patrolMax: 400 },
        platform: { w: 120, h: 18, color: "#64748b", solid: true },
        coin: { w: 18, h: 18, color: "#fbbf24", points: 10, solid: false },
        goal: { w: 32, h: 36, color: "#22c55e", solid: false },
        checkpoint: { w: 16, h: 32, color: "#2dd4bf", solid: false },
        door: { w: 28, h: 60, color: "#a16207", solid: true, locked: true },
        key: { w: 16, h: 16, color: "#fde047", solid: false },
        obstacle: { w: 40, h: 40, color: "#78716c", solid: true },
        text: { w: 80, h: 20, color: "#e2e8f0", solid: false },
        npc: { w: 28, h: 36, color: "#c084fc", solid: true },
        item: { w: 20, h: 20, color: "#fb923c", solid: false },
      };
      const d = defaults[type] || { w: 24, h: 24, color: "#94a3b8" };
      lvl.entities = lvl.entities || [];
      lvl.entities.push({
        id,
        type,
        name: type,
        x: 80 + Math.random() * 200,
        y: 80 + Math.random() * 120,
        rotation: 0,
        scale: 1,
        visible: true,
        collision: true,
        ...d,
      });
      this.selectedId = id;
      this.renderEditor();
    },

    deleteSelected() {
      const lvl = this.currentLevel();
      if (!lvl || !this.selectedId) return;
      lvl.entities = (lvl.entities || []).filter((e) => e.id !== this.selectedId);
      this.selectedId = null;
      this.renderEditor();
    },

    duplicateSelected() {
      const lvl = this.currentLevel();
      const e = lvl && (lvl.entities || []).find((x) => x.id === this.selectedId);
      if (!e) return;
      const copy = { ...e, id: e.type + "_" + Math.random().toString(16).slice(2, 8), x: e.x + 16, y: e.y + 16 };
      lvl.entities.push(copy);
      this.selectedId = copy.id;
      this.renderEditor();
    },

    async save() {
      if (!this.project) return;
      const codeEl = $("#gs-code");
      if (codeEl && this.project.data) this.project.data.code = codeEl.value;
      try {
        const p = await API.j("/api/cyber/game-studio/projects/" + encodeURIComponent(this.project.id), {
          method: "PUT",
          body: JSON.stringify({
            data: this.project.data,
            changes: "Editor Game Studio",
            progress: 40,
          }),
        });
        this.project = p;
        this.renderEditor();
        this.toast("Salvo · v" + p.version);
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    play() {
      if (!this.project) return;
      const canvas = $("#gs-play-canvas");
      if (!canvas) return;
      this.showPanel("play");
      if (this.runtime) this.runtime.stop();
      this.runtime = new GameRuntime(canvas);
      this.runtime.onHud = (h) => {
        const el = $("#gs-hud");
        if (el)
          el.textContent = `Score ${h.score} · HP ${h.hp}/${h.maxHp} · FPS ${h.fps}` + (h.paused ? " · PAUSA" : "") + (h.status !== "PLAYING" ? " · " + h.status : "");
      };
      this.runtime.onEnd = (s) => this.toast(s === "WIN" ? "Você venceu!" : "Game Over");
      this.runtime.load(this.project.data);
      this.runtime.start();
      this.mode = "play";
    },

    stopPlay() {
      if (this.runtime) this.runtime.stop();
      this.mode = "edit";
      this.showPanel("editor");
    },

    async runCheck() {
      if (!this.project) return;
      try {
        const d = await API.j("/api/cyber/game-studio/check", {
          method: "POST",
          body: JSON.stringify({ data: this.project.data }),
        });
        const box = $("#gs-check-out");
        if (box) {
          box.innerHTML = (d.checks || [])
            .map((c) => `<div class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.label)}</div>`)
            .join("");
        }
        this.toast(d.ok ? "GAME CHECK OK" : "Há pendências no check");
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    async publish() {
      if (!this.project) return;
      if (!confirm("Publicar este jogo na galeria local do JARVIS?")) return;
      try {
        const p = await API.j(
          "/api/cyber/game-studio/projects/" + encodeURIComponent(this.project.id) + "/publish",
          { method: "POST", body: "{}" }
        );
        this.project = p;
        this.toast("Publicado");
        this.renderEditor();
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    async runCoder() {
      if (!this.project) return;
      const inp = $("#gs-coder-input");
      const text = (inp && inp.value) || "";
      if (!text.trim()) return this.toast("Descreva o que deseja", true);
      try {
        const d = await API.j(
          "/api/cyber/game-studio/projects/" + encodeURIComponent(this.project.id) + "/coder",
          { method: "POST", body: JSON.stringify({ instruction: text }) }
        );
        this.project = d.project;
        this.renderEditor();
        this.toast((d.changes || []).join(" · ") || "Coder OK");
      } catch (e) {
        this.toast(e.message, true);
      }
    },

    toast(msg, err) {
      const el = document.createElement("div");
      el.className = "edu-toast";
      el.textContent = msg;
      el.style.cssText = `position:fixed;bottom:20px;right:20px;background:${err ? "#b91c1c" : "#22c55e"};color:#fff;padding:10px 16px;border-radius:8px;z-index:9999`;
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 2800);
    },
  };

  window.JarvisGameStudio = Studio;
  window.JarvisGameRuntime = GameRuntime;

  // Wire new modal buttons when DOM ready
  function wireModal() {
    const c = $("#gs-new-create");
    if (c) c.onclick = () => Studio.createNew();
    const x = $("#gs-new-cancel");
    if (x) x.onclick = () => Studio.closeNewModal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      wireModal();
      Studio.boot();
    });
  } else {
    wireModal();
    Studio.boot();
  }
})();
