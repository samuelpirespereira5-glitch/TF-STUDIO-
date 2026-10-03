/**
 * JARVIS Phase 12 — Trilhas, Labs, XP, Certificados, Notas, Progresso
 */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  const LS = {
    get(k, def) {
      try { const v = localStorage.getItem("jarvis_edu_" + k); return v ? JSON.parse(v) : def; } catch { return def; }
    },
    set(k, v) { try { localStorage.setItem("jarvis_edu_" + k, JSON.stringify(v)); } catch (_) {} },
  };

  function progress() {
    return LS.get("progress", { videos: {}, lessons: {}, challenges: {}, zero: {}, achievements: [], projects: [], tracks: {}, debug: {}, xp: 0, streak: 0, notes: [] });
  }
  function saveProgress(p) { LS.set("progress", p); }
  function addXp(n) {
    const p = progress();
    p.xp = (p.xp || 0) + (n || 0);
    saveProgress(p);
    updateXpUi();
    return p.xp;
  }
  function flash(msg) {
    const el = document.createElement("div");
    el.className = "edu-toast";
    el.textContent = msg;
    el.style.cssText = "position:fixed;bottom:20px;right:20px;background:#22c55e;color:#fff;padding:10px 16px;border-radius:8px;z-index:9999";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  async function updateXpUi() {
    const p = progress();
    try {
      const r = await fetch("/api/cyber/phase12/xp?xp=" + (p.xp || 0));
      const d = await r.json();
      const el = $("#edu-xp-badge");
      if (el) el.textContent = `⭐ ${d.xp} XP · Nv ${d.level} — ${d.title}`;
    } catch (_) {}
  }

  async function loadTracks() {
    const grid = $("#edu-tracks-grid") || $("#edu-tracks");
    if (!grid) return;
    try {
      const r = await fetch("/api/cyber/phase12/tracks");
      const d = await r.json();
      const p = progress();
      grid.innerHTML = (d.tracks || []).map((t) => {
        const done = (p.tracks && p.tracks[t.id] && p.tracks[t.id].done) || 0;
        const pct = t.modulos_count ? Math.round((done / t.modulos_count) * 100) : 0;
        return `<button type="button" class="card edu-curso-card" data-track="${t.id}" style="text-align:left;cursor:pointer">
          <h3>${t.icon || ""} ${esc(t.titulo)}</h3>
          <p class="muted small">${esc(t.descricao)}</p>
          <p class="muted small">${t.modulos_count} módulos · ${t.carga_horas || 0}h · ${t.nivel || ""}</p>
          <div class="progress-bar"><div style="width:${pct}%"></div></div>
        </button>`;
      }).join("");
      grid.querySelectorAll("[data-track]").forEach((b) => b.addEventListener("click", () => openTrack(b.dataset.track)));
    } catch (_) {
      grid.innerHTML = "<p class='muted'>Trilhas indisponíveis.</p>";
    }
  }

  async function openTrack(tid) {
    const r = await fetch("/api/cyber/phase12/tracks/" + encodeURIComponent(tid));
    if (!r.ok) return;
    const t = await r.json();
    let detail = $("#track-detail");
    if (!detail) {
      detail = document.createElement("div");
      detail.id = "track-detail";
      detail.className = "card";
      ($("#edu-tracks-grid") || $("#edu-tracks") || $("#edu-root")).appendChild(detail);
    }
    detail.hidden = false;
    const p = progress();
    const doneMods = (p.tracks && p.tracks[tid] && p.tracks[tid].modules) || {};
    const doneCount = Object.keys(doneMods).filter((k) => doneMods[k]).length;
    const pct = t.modulos ? Math.round((doneCount / t.modulos.length) * 100) : 0;
    detail.innerHTML = `
      <div class="edu-toolbar"><h2>${esc((t.icon || "") + " " + t.titulo)}</h2>
      <button type="button" class="btn ghost" id="track-close">Fechar</button>
      <a class="btn" href="/certificados">Certificado JARVIS</a></div>
      <p class="muted">${esc(t.descricao || "")}</p>
      <div class="progress-bar"><div style="width:${pct}%"></div></div>
      <div id="track-modules"></div>`;
    const box = detail.querySelector("#track-modules");
    box.innerHTML = (t.modulos || []).map((m, i) => {
      const ok = !!doneMods[m.id];
      return `<div class="card" style="margin:8px 0"><strong>${ok ? "✓ " : i + 1 + ". "}${esc(m.titulo)}</strong>
        <p class="muted small">${(m.aulas || []).join(" · ")}</p>
        <button type="button" class="btn btn-sm" data-mod="${m.id}">${ok ? "Concluído" : "Marcar módulo"}</button></div>`;
    }).join("");
    box.querySelectorAll("[data-mod]").forEach((b) => b.addEventListener("click", () => {
      const pr = progress();
      pr.tracks = pr.tracks || {};
      pr.tracks[tid] = pr.tracks[tid] || { modules: {}, done: 0 };
      pr.tracks[tid].modules[b.dataset.mod] = true;
      pr.tracks[tid].done = Object.keys(pr.tracks[tid].modules).length;
      saveProgress(pr);
      addXp(10);
      flash("Módulo +10 XP");
      openTrack(tid);
    }));
    detail.querySelector("#track-close").onclick = () => { detail.hidden = true; };
  }

  async function loadDebugLab() {
    const list = $("#debug-list");
    if (!list) return;
    const r = await fetch("/api/cyber/phase12/debug");
    const d = await r.json();
    const p = progress();
    list.innerHTML = (d.exercises || []).map((e) =>
      `<button type="button" class="edu-item" data-dbg="${e.id}">${p.debug && p.debug[e.id] ? "✓ " : "🐛 "}${esc(e.titulo)}</button>`
    ).join("");
    list.querySelectorAll("[data-dbg]").forEach((b) => b.addEventListener("click", () => openDebug(b.dataset.dbg)));
  }

  async function openDebug(id) {
    const r = await fetch("/api/cyber/phase12/debug/" + encodeURIComponent(id));
    if (!r.ok) return;
    const e = await r.json();
    const view = $("#debug-view");
    if (!view) return;
    let hintIdx = 0;
    view.innerHTML = `<h2>🐛 ${esc(e.titulo)}</h2><p>${esc(e.objetivo)}</p>
      <textarea class="code-area" id="dbg-code" rows="8">${esc(e.codigo_quebrado || "")}</textarea>
      <div class="edu-toolbar">
        <button type="button" class="btn primary" id="dbg-check">Verificar</button>
        <button type="button" class="btn" id="dbg-hint">Dica</button>
        <button type="button" class="btn ghost" id="dbg-reset">Restaurar</button>
      </div><pre id="dbg-out" class="edu-out"></pre>`;
    const hints = e.dicas || [];
    $("#dbg-hint").onclick = () => { $("#dbg-out").textContent = hintIdx < hints.length ? "💡 " + hints[hintIdx++] : "Sem mais dicas."; };
    $("#dbg-reset").onclick = () => { $("#dbg-code").value = e.codigo_quebrado || ""; };
    $("#dbg-check").onclick = async () => {
      const rr = await fetch("/api/cyber/phase12/debug/" + encodeURIComponent(id) + "/check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: $("#dbg-code").value }),
      });
      const res = await rr.json();
      $("#dbg-out").textContent = res.message || "";
      if (res.ok) {
        const p = progress();
        p.debug = p.debug || {};
        p.debug[id] = true;
        saveProgress(p);
        addXp(res.xp || e.xp || 10);
        flash("Debug OK");
      } else if (res.hint) $("#dbg-out").textContent += "\n💡 " + res.hint;
    };
  }

  async function loadAlgoLab() {
    const list = $("#algo-list");
    if (!list) return;
    const r = await fetch("/api/cyber/phase12/algorithms");
    const d = await r.json();
    list.innerHTML = (d.algorithms || []).map((a) =>
      `<button type="button" class="edu-item" data-algo="${a.id}">${esc(a.titulo)} <span class="muted small">${a.complexidade}</span></button>`
    ).join("");
    list.querySelectorAll("[data-algo]").forEach((b) => b.addEventListener("click", async () => {
      const rr = await fetch("/api/cyber/phase12/algorithms/" + b.dataset.algo);
      const a = await rr.json();
      const view = $("#algo-view");
      if (!view) return;
      const arr = Array.isArray(a.passos_demo) ? a.passos_demo : [];
      view.innerHTML = `<h2>⚙️ ${esc(a.titulo)}</h2><p class="muted">${esc(a.descricao)}</p>
        <div class="algo-bars">${arr.map((v) => `<div class="algo-bar" style="height:${typeof v === "number" ? Math.max(20, v * 8) : 40}px"><span>${esc(String(v))}</span></div>`).join("")}</div>
        <pre class="edu-out">${esc(a.pseudocodigo || "")}</pre>`;
    }));
  }

  async function loadApiLab() {
    const list = $("#api-list");
    if (!list) return;
    const r = await fetch("/api/cyber/phase12/api-lab");
    const d = await r.json();
    list.innerHTML = (d.scenarios || []).map((s) =>
      `<button type="button" class="edu-item" data-api="${s.id}"><span class="chip">${s.metodo}</span> ${esc(s.titulo)}</button>`
    ).join("");
    list.querySelectorAll("[data-api]").forEach((b) => b.addEventListener("click", () => {
      const s = (d.scenarios || []).find((x) => x.id === b.dataset.api);
      if (!s) return;
      const view = $("#api-view");
      if (!view) return;
      view.innerHTML = `<h2>🔌 ${esc(s.titulo)}</h2>
        <div class="card"><strong>REQUEST</strong><pre class="edu-out">${esc(JSON.stringify(s.request, null, 2))}</pre></div>
        <p style="text-align:center">↓</p>
        <div class="card"><strong>RESPONSE</strong><pre class="edu-out" id="api-res">${esc(JSON.stringify(s.response, null, 2))}</pre></div>
        <p class="muted small">Ensina: ${(s.ensina || []).join(", ")}</p>`;
      addXp(5);
    }));
  }

  async function loadDbLab() {
    const r = await fetch("/api/cyber/phase12/db-lab");
    const d = await r.json();
    const schema = $("#db-schema");
    if (schema && d.tables) {
      schema.innerHTML = Object.keys(d.tables).map((t) => `<span class="chip">📋 ${t}</span>`).join("");
    }
    const ex = $("#db-examples");
    if (ex && d.examples) {
      ex.innerHTML = d.examples.map((e) => `<button type="button" class="btn btn-sm" data-sql>${esc(e.titulo)}</button>`).join("");
      ex.querySelectorAll("[data-sql]").forEach((b, i) => b.addEventListener("click", () => { if ($("#db-sql")) $("#db-sql").value = d.examples[i].sql; }));
    }
  }

  $("#db-run")?.addEventListener("click", async () => {
    const out = $("#db-out");
    if (!out) return;
    try {
      const r = await fetch("/api/cyber/phase12/db-lab/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: $("#db-sql")?.value || "" }),
      });
      const d = await r.json();
      out.textContent = d.ok ? (d.message + "\n" + JSON.stringify(d.rows || [], null, 2)) : (d.error || "Erro");
      if (d.ok) addXp(5);
    } catch (_) { out.textContent = "Falha de conexão"; }
  });

  function loadProgressPanel() {
    const el = $("#edu-progress-panel") || $("#tab-progresso .card");
    if (!el) return;
    const p = progress();
    const videos = Object.keys(p.videos || {}).length;
    const dbg = Object.keys(p.debug || {}).length;
    const tracks = Object.keys(p.tracks || {}).length;
    const projects = (p.projects || []).length;
    el.innerHTML = `
      <h2>📊 Meu progresso</h2>
      <div class="edu-grid stats">
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${videos}</div><div class="muted small">Vídeos</div></div>
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${tracks}</div><div class="muted small">Trilhas iniciadas</div></div>
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${dbg}</div><div class="muted small">Debug resolvidos</div></div>
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${projects}</div><div class="muted small">Projetos</div></div>
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${p.xp || 0}</div><div class="muted small">XP</div></div>
        <div class="card" style="text-align:center"><div style="font-size:1.4em">${(p.achievements || []).length}</div><div class="muted small">Conquistas</div></div>
      </div>
      <div class="edu-toolbar" style="margin-top:12px">
        <button type="button" class="btn primary" data-goto-tab="cursos">Continue estudando</button>
        <a class="btn" href="/certificados">Certificados JARVIS</a>
      </div>`;
    el.querySelector("[data-goto-tab]")?.addEventListener("click", (ev) => {
      const tab = document.querySelector(`.edu-tab[data-tab="${ev.currentTarget.dataset.gotoTab}"]`);
      if (tab) tab.click();
    });
  }

  async function loadNotes() {
    const box = $("#notes-list");
    if (!box) return;
    try {
      const r = await fetch("/api/cyber/phase12/notes");
      const d = await r.json();
      const notes = d.notes || [];
      box.innerHTML = notes.length
        ? notes.map((n) => `<div class="card" style="margin:6px 0"><strong>${esc(n.titulo || n.tipo)}</strong>
            <p class="muted small">${esc(n.curso || "")} / ${esc(n.aula || "")}</p>
            <pre class="edu-out" style="max-height:80px">${esc(n.conteudo || "")}</pre>
            <button type="button" class="btn btn-sm ghost" data-del-note="${n.id}">Excluir</button></div>`).join("")
        : "<span class='muted'>Nenhuma nota ainda.</span>";
      box.querySelectorAll("[data-del-note]").forEach((b) => b.addEventListener("click", async () => {
        await fetch("/api/cyber/phase12/notes/" + b.dataset.delNote, { method: "DELETE" });
        loadNotes();
      }));
    } catch (_) {
      box.innerHTML = "<span class='muted'>Notas indisponíveis (login pode ser necessário).</span>";
    }
  }

  $("#note-save")?.addEventListener("click", async () => {
    const titulo = $("#note-title")?.value || "";
    const conteudo = $("#note-body")?.value || "";
    if (!conteudo.trim()) return flash("Escreva a nota");
    try {
      await fetch("/api/cyber/phase12/notes", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ titulo, conteudo, tipo: "nota", curso: LS.get("current_context", {}).titulo || "" }),
      });
      flash("Nota salva");
      loadNotes();
    } catch (_) { flash("Falha ao salvar"); }
  });

  // Professor quick prompts
  async function loadProfessorPrompts() {
    const box = $("#professor-prompts");
    if (!box) return;
    try {
      const r = await fetch("/api/cyber/phase12/professor-prompts");
      const d = await r.json();
      box.innerHTML = (d.prompts || []).map((p) =>
        `<button type="button" class="btn btn-sm" data-pp="${esc(p.prompt)}">${esc(p.label)}</button>`
      ).join("");
      box.querySelectorAll("[data-pp]").forEach((b) => b.addEventListener("click", () => {
        const q = $("#mentor-q");
        if (q) { q.value = b.dataset.pp; q.focus(); }
      }));
    } catch (_) {}
  }

  function onTab(name) {
    if (name === "tracks") loadTracks();
    if (name === "debuglab") loadDebugLab();
    if (name === "algolab") loadAlgoLab();
    if (name === "apilab") loadApiLab();
    if (name === "dblab") loadDbLab();
    if (name === "progresso") loadProgressPanel();
    if (name === "notas") loadNotes();
    if (name === "mentor") loadProfessorPrompts();
  }
  $$(".edu-tab").forEach((btn) => btn.addEventListener("click", () => onTab(btn.dataset.tab)));

  function ensureXpBadge() {
    const hero = $(".edu-hero-actions");
    if (hero && !$("#edu-xp-badge")) {
      const b = document.createElement("span");
      b.id = "edu-xp-badge";
      b.className = "chip";
      hero.appendChild(b);
    }
    updateXpUi();
  }

  // Global search enhancement
  const searchBtn = $("#edu-search-btn");
  if (searchBtn) {
    searchBtn.addEventListener("click", async () => {
      const q = ($("#edu-search")?.value || "").trim();
      if (!q) return;
      try {
        const r = await fetch("/api/cyber/phase12/search?q=" + encodeURIComponent(q));
        const d = await r.json();
        flash((d.results || []).length + " resultado(s)");
      } catch (_) {}
    });
  }

  window.jarvisGameSource = async (gid) => {
    try { return await (await fetch("/api/cyber/phase12/game-source/" + encodeURIComponent(gid))).json(); } catch { return null; }
  };

  ensureXpBadge();
  if ($(".edu-tab.active")?.dataset?.tab === "tracks") loadTracks();
})();
