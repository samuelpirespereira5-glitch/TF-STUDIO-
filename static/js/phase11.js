/**
 * JARVIS Phase 11 — Educação expandida
 * Reutiliza phase10 onde existir; adiciona vídeos, trilha zero, lab, desafios.
 */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  const LS = {
    get(k, def) {
      try {
        const v = localStorage.getItem("jarvis_edu_" + k);
        return v ? JSON.parse(v) : def;
      } catch {
        return def;
      }
    },
    set(k, v) {
      try {
        localStorage.setItem("jarvis_edu_" + k, JSON.stringify(v));
      } catch (_) {}
    },
  };

  function progress() {
    return LS.get("progress", {
      videos: {},
      lessons: {},
      challenges: {},
      zero: {},
      achievements: [],
      projects: [],
    });
  }
  function saveProgress(p) {
    LS.set("progress", p);
  }

  function unlockAch(id) {
    const p = progress();
    if (!p.achievements.includes(id)) {
      p.achievements.push(id);
      saveProgress(p);
      flash("Conquista: " + id);
    }
  }

  function flash(msg) {
    const el = document.createElement("div");
    el.className = "edu-toast";
    el.textContent = msg;
    el.style.cssText =
      "position:fixed;bottom:20px;right:20px;background:#22c55e;color:#fff;padding:10px 16px;border-radius:8px;z-index:9999";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  // Tabs
  function switchTab(name) {
    $$(".edu-tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    $$(".edu-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
    if (name === "cursos") loadCursos();
    if (name === "videos") loadVideos();
    if (name === "overview") loadOverview();
    if (name === "desafios") loadChallenges();
    if (name === "progresso") loadProgresso && loadProgresso();
    if (name === "mentor") {
      try {
        const ctx = LS.get("current_context", null);
        const q = $("#mentor-q");
        if (ctx && q && !q.value) {
          q.placeholder = "Contexto: " + (ctx.titulo || ctx.type) + " — pergunte ao JARVIS Professor…";
        }
      } catch (_) {}
    }
  }
  $$(".edu-tab").forEach((btn) =>
    btn.addEventListener("click", () => switchTab(btn.dataset.tab))
  );
  $$("[data-goto]").forEach((btn) =>
    btn.addEventListener("click", () => switchTab(btn.dataset.goto))
  );

  $("#btn-zero")?.addEventListener("click", () => {
    switchTab("zero");
    loadBeginner();
  });

  // ---------- Overview ----------
  async function loadOverview() {
    try {
      const r = await fetch("/api/cyber/phase11/overview");
      const d = await r.json();
      const stats = $("#edu-stats");
      if (stats) {
        stats.innerHTML = [
          ["Vídeos", d.videos_count],
          ["Aulas do zero", d.beginner_lessons],
          ["Desafios", d.challenges_count],
          ["Conquistas", d.achievements_count],
        ]
          .map(
            ([l, v]) =>
              `<div class="card" style="text-align:center"><div style="font-size:1.6em;font-weight:700">${v}</div><div class="muted small">${l}</div></div>`
          )
          .join("");
      }
      const daily = $("#edu-daily");
      if (daily && d.daily) {
        daily.innerHTML = `<strong>${d.daily.titulo}</strong><p class="muted small">${d.daily.descricao}</p>
          <button type="button" class="btn" id="go-daily">Fazer desafio</button>`;
        $("#go-daily")?.addEventListener("click", () => {
          switchTab("desafios");
          openChallenge(d.daily.id);
        });
      }
      // home videos
      const hv = $("#edu-home-videos");
      if (hv) {
        const vr = await fetch("/api/cyber/phase11/videos");
        const vd = await vr.json();
        hv.innerHTML = (vd.videos || [])
          .slice(0, 4)
          .map(
            (v) =>
              `<button type="button" class="btn ghost" data-vid="${v.id}">${v.titulo.slice(0, 40)}…</button>`
          )
          .join("");
        hv.querySelectorAll("[data-vid]").forEach((b) =>
          b.addEventListener("click", () => {
            switchTab("videos");
            openVideo(b.dataset.vid);
          })
        );
      }
      const cont = $("#edu-continue");
      if (cont) {
        const p = progress();
        const keys = Object.keys(p.zero || {});
        cont.innerHTML =
          keys.length > 0
            ? `<button type="button" class="btn" data-goto="zero">Continuar trilha do zero</button>`
            : `<button type="button" class="btn" id="start-zero2">COMEÇAR DO ZERO</button>`;
        $("#start-zero2")?.addEventListener("click", () => {
          switchTab("zero");
          loadBeginner();
        });
      }
    } catch (e) {
      console.warn("phase11 overview", e);
    }
  }

  // ---------- Beginner track ----------
  let beginnerCache = [];
  async function loadBeginner() {
    const list = $("#zero-list");
    const view = $("#zero-view");
    if (!list) return;
    try {
      const r = await fetch("/api/cyber/phase11/beginner");
      const d = await r.json();
      beginnerCache = d.track || [];
      const p = progress();
      list.innerHTML = beginnerCache
        .map((L, i) => {
          const done = p.zero[L.id];
          return `<button type="button" class="edu-item ${done ? "done" : ""}" data-lid="${L.id}">${i + 1}. ${L.title}${done ? " ✓" : ""}</button>`;
        })
        .join("");
      list.querySelectorAll("[data-lid]").forEach((b) =>
        b.addEventListener("click", () => showBeginnerLesson(b.dataset.lid))
      );
      if (beginnerCache[0]) showBeginnerLesson(beginnerCache[0].id);
    } catch (e) {
      list.innerHTML = "<p class='muted'>Não foi possível carregar a trilha.</p>";
    }
  }

  function showBeginnerLesson(id) {
    const L = beginnerCache.find((x) => x.id === id);
    const view = $("#zero-view");
    if (!L || !view) return;
    $$("#zero-list .edu-item").forEach((el) =>
      el.classList.toggle("active", el.dataset.lid === id)
    );
    let visual = "";
    if (L.visual) {
      visual = `<div class="edu-visual-box"><div>${L.visual.box}</div><div class="arrow">↓</div><div>${L.visual.value}</div></div>`;
    }
    const easy = L.easy_explain
      ? `<div class="edu-easy card" style="margin:10px 0;padding:12px;border-left:4px solid #3b82f6">
           <strong>🧒 Explicando fácil</strong>
           <p style="margin:6px 0 0">${esc(L.easy_explain)}</p>
           ${L.analogy ? `<p class="muted" style="margin:6px 0 0"><em>Analogia:</em> ${esc(L.analogy)}</p>` : ""}
           ${Array.isArray(L.steps_kid) && L.steps_kid.length
             ? `<ol style="margin:8px 0 0;padding-left:18px">${L.steps_kid.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>`
             : ""}
         </div>`
      : "";
    view.innerHTML = `
      <h2>${esc(L.title)}</h2>
      <p>${esc(L.explanation || "")}</p>
      ${easy}
      ${visual}
      <h3>Exemplo</h3>
      <pre class="edu-out">${esc(L.example || "")}</pre>
      <h3>Código</h3>
      <textarea class="code-area" id="zero-code" rows="8">${esc(L.code || "")}</textarea>
      <div class="edu-toolbar">
        <button type="button" class="btn primary" id="zero-run">Executar</button>
        <button type="button" class="btn ghost" id="zero-hint">Dica</button>
        <button type="button" class="btn" id="zero-done">Marcar concluída</button>
        ${L.next ? `<button type="button" class="btn" id="zero-next">Próxima aula</button>` : ""}
      </div>
      <pre class="edu-out" id="zero-out"></pre>
      <h3>Exercício</h3><p>${esc(L.exercise || "")}</p>
      <h3>Desafio</h3><p>${esc(L.challenge || "")}</p>
    `;
    $("#zero-run")?.addEventListener("click", () => {
      const code = $("#zero-code").value;
      runClientPythonish(code, $("#zero-out"));
      unlockAch("first_code");
      unlockAch("first_run");
    });
    $("#zero-hint")?.addEventListener("click", () => {
      $("#zero-out").textContent = "💡 " + (L.hint || "Tente modificar o exemplo.");
    });
    $("#zero-done")?.addEventListener("click", () => {
      const p = progress();
      p.zero[id] = true;
      saveProgress(p);
      if (Object.keys(p.zero).length >= beginnerCache.length) unlockAch("zero_track");
      flash("Aula concluída!");
      loadBeginner();
    });
    $("#zero-next")?.addEventListener("click", () => {
      if (L.next) showBeginnerLesson(L.next);
    });
  }

  // Very limited client-side Python-like evaluator for education (print only)
  function runClientPythonish(code, outEl) {
    if (!outEl) return;
    const lines = [];
    const print = (...args) => lines.push(args.map(String).join(" "));
    try {
      // Only allow simple print / assignments demos — no eval of arbitrary python on server
      // For JS-like teaching we transpile a tiny subset
      let js = code
        .replace(/#.*/g, "")
        .replace(/print\s*\(/g, "print(")
        .replace(/\bTrue\b/g, "true")
        .replace(/\bFalse\b/g, "false")
        .replace(/\bNone\b/g, "null");
      // range helper
      const range = (a, b) => {
        if (b === undefined) {
          b = a;
          a = 0;
        }
        const arr = [];
        for (let i = a; i < b; i++) arr.push(i);
        return arr;
      };
      // naive: if it looks like pure JS-ish after replace, run in Function sandbox
      // Restrict: no access to window/document/fetch
      const fn = new Function("print", "range", `"use strict";\n${js}`);
      fn(print, range);
      outEl.textContent = lines.join("\n") || "(sem saída)";
    } catch (e) {
      outEl.textContent = "Erro: " + e.message + "\n\n(Nota: este laboratório simula apenas print/for simples no navegador. Para Python completo use um ambiente local ou o editor avançado.)";
    }
  }

  // ---------- Videos ----------
  async function loadVideos(lang) {
    const grid = $("#edu-videos-grid");
    if (!grid) return;
    const url = "/api/cyber/phase11/videos" + (lang ? "?lang=" + encodeURIComponent(lang) : "");
    const r = await fetch(url);
    const d = await r.json();
    const p = progress();
    grid.innerHTML = (d.videos || [])
      .map((v) => {
        const done = p.videos[v.id];
        return `<div class="card">
          <strong>${esc(v.titulo)}</strong>
          <p class="muted small">${esc(v.descricao || "")} · ${v.duracao || ""} · ${v.fonte}</p>
          <button type="button" class="btn" data-open-vid="${v.id}">Assistir ${done ? "✓" : ""}</button>
        </div>`;
      })
      .join("");
    grid.querySelectorAll("[data-open-vid]").forEach((b) =>
      b.addEventListener("click", () => openVideo(b.dataset.openVid))
    );
  }

  async function openVideo(id) {
    // Phase 13 Video Engine 2.0 — prefer enhanced player when available
    if (window.JarvisVideoEngine && typeof window.JarvisVideoEngine.openVideo === "function") {
      return window.JarvisVideoEngine.openVideo(id);
    }
    const r = await fetch("/api/cyber/phase11/videos/" + encodeURIComponent(id));
    if (!r.ok) return;
    const v = await r.json();
    const card = $("#video-player-card");
    card.hidden = false;
    $("#video-title").textContent = v.titulo;
    $("#video-desc").textContent = v.descricao || "";
    $("#video-learn").innerHTML = (v.o_que_aprendo || [])
      .map((x) => `<span class="chip">${esc(x)}</span>`)
      .join("");
    let easyEl = $("#video-easy");
    if (!easyEl) {
      easyEl = document.createElement("div");
      easyEl.id = "video-easy";
      easyEl.className = "edu-easy";
      const learn = $("#video-learn");
      if (learn && learn.parentNode) learn.parentNode.insertBefore(easyEl, learn.nextSibling);
    }
    if (easyEl) {
      if (v.easy_explain) {
        easyEl.hidden = false;
        easyEl.innerHTML = `<strong>🧒 Explicando fácil</strong><p>${esc(v.easy_explain)}</p>`;
      } else {
        easyEl.hidden = true;
        easyEl.innerHTML = "";
      }
    }
    const wrap = $("#video-embed-wrap");
    const iframe = $("#video-iframe");
    const loading = $("#video-loading");
    const errBox = $("#video-error");
    const ytUrl = v.url_oficial || "https://www.youtube.com/watch?v=" + v.video_id;
    const yt = $("#video-yt");
    yt.href = ytUrl;
    const errYt = $("#video-error-yt");
    if (errYt) errYt.href = ytUrl;

    // Estados: carregando / carregado / erro
    function setState(s) {
      if (!wrap) return;
      wrap.classList.remove("loading", "loaded", "error");
      wrap.classList.add(s);
      if (loading) loading.hidden = s !== "loading";
      if (errBox) errBox.hidden = s !== "error";
    }
    setState("loading");
    iframe.onload = () => setState("loaded");
    iframe.onerror = () => setState("error");
    // Timeout de segurança: se em 8s ainda não carregou, mostra fallback
    const loadTimer = setTimeout(() => {
      if (wrap && wrap.classList.contains("loading")) setState("error");
    }, 8000);
    if (v.playlist_id && (v.tipo === "playlist" || !v.video_id)) {
      iframe.src = "https://www.youtube.com/embed/videoseries?list=" + encodeURIComponent(v.playlist_id) + "&rel=0";
    } else if (v.video_id) {
      iframe.src = "https://www.youtube.com/embed/" + encodeURIComponent(v.video_id) + "?rel=0";
    } else {
      iframe.src = "";
    }
    // Alguns ambientes bloqueiam embed; após load ainda pode ficar branco — fallback manual
    iframe.addEventListener("load", () => clearTimeout(loadTimer), { once: true });

    const p = progress();
    const pct = p.videos[id] ? 100 : 0;
    $("#video-progress").style.width = pct + "%";
    // Context for JARVIS Professor
    try {
      LS.set("current_context", {
        type: "video",
        id: id,
        titulo: v.titulo,
        curso: v.linguagem || v.modulo || "",
        fonte: v.fonte || "Curso em Vídeo",
        video_id: v.video_id,
      });
    } catch (_) {}
    $("#video-done").onclick = () => {
      p.videos[id] = true;
      saveProgress(p);
      $("#video-progress").style.width = "100%";
      const n = Object.keys(p.videos).length;
      if (n >= 5) unlockAch("video_5");
      flash("Vídeo marcado como concluído");
    };
    $("#video-exercise").onclick = () => switchTab("desafios");
    $("#video-lab").onclick = () => switchTab("lab");
    $("#video-ask").onclick = () => {
      switchTab("mentor");
      const q = $("#mentor-q");
      if (q) q.value = "Estou na aula: " + v.titulo + " (Curso em Vídeo / " + (v.fonte || "Guanabara") + "). Explique essa aula de forma clara e dê um exemplo prático.";
    };
    $("#video-close").onclick = () => {
      card.hidden = true;
      iframe.src = "";
      setState("loading");
      clearTimeout(loadTimer);
    };
  }

  $$("[data-vlang]").forEach((b) =>
    b.addEventListener("click", () => {
      $$("[data-vlang]").forEach((x) => x.classList.toggle("btn", true));
      loadVideos(b.dataset.vlang || null);
    })
  );


  // ---------- Cursos (Fase 12 — agrupados por linguagem/módulo = playlist) ----------
  async function loadCursos() {
    const grid = $("#edu-cursos-grid");
    if (!grid) return;
    try {
      const r = await fetch("/api/cyber/phase11/videos");
      const d = await r.json();
      const videos = d.videos || [];
      // Agrupar por linguagem / módulo
      const byLang = {};
      videos.forEach((v) => {
        const lang = (v.linguagem || "outros").toLowerCase();
        if (!byLang[lang]) byLang[lang] = { lang, videos: [], modules: {} };
        byLang[lang].videos.push(v);
        const mod = v.modulo || "geral";
        if (!byLang[lang].modules[mod]) byLang[lang].modules[mod] = [];
        byLang[lang].modules[mod].push(v);
      });
      const p = progress();
      const names = {
        python: "Python — Curso em Vídeo",
        html: "HTML5 — Curso em Vídeo",
        css: "CSS3 — Curso em Vídeo",
        javascript: "JavaScript — Curso em Vídeo",
        php: "PHP — Curso em Vídeo",
        mysql: "MySQL / Banco de Dados",
        java: "Java — Curso em Vídeo",
        algoritmos: "Algoritmos",
        git: "Git e GitHub",
        outros: "Outros",
      };
      grid.innerHTML = Object.keys(byLang)
        .sort()
        .map((lang) => {
          const g = byLang[lang];
          const done = g.videos.filter((v) => p.videos[v.id]).length;
          const pct = g.videos.length ? Math.round((done / g.videos.length) * 100) : 0;
          const mods = Object.keys(g.modules).length;
          return `<button type="button" class="card edu-curso-card" data-curso="${lang}" style="text-align:left;cursor:pointer">
            <h3>${names[lang] || lang}</h3>
            <p class="muted small">Fonte: Curso em Vídeo · Gustavo Guanabara</p>
            <p>${g.videos.length} aulas · ${mods} playlists/módulos</p>
            <div class="progress-bar"><div style="width:${pct}%"></div></div>
            <p class="muted small">${pct}% concluído · ${done}/${g.videos.length}</p>
            <span class="btn btn-sm primary" style="margin-top:8px">Abrir curso</span>
          </button>`;
        })
        .join("");
      grid.querySelectorAll("[data-curso]").forEach((b) =>
        b.addEventListener("click", () => openCurso(b.dataset.curso, byLang[b.dataset.curso]))
      );
    } catch (e) {
      grid.innerHTML = "<p class='muted'>Não foi possível carregar os cursos.</p>";
    }
  }

  function openCurso(lang, group) {
    const detail = $("#curso-detail");
    const grid = $("#edu-cursos-grid");
    if (!detail || !group) return;
    if (grid) grid.hidden = true;
    detail.hidden = false;
    const names = {
      python: "Python — Curso em Vídeo",
      html: "HTML5 — Curso em Vídeo",
      css: "CSS3 — Curso em Vídeo",
      javascript: "JavaScript — Curso em Vídeo",
      php: "PHP — Curso em Vídeo",
      mysql: "MySQL / Banco de Dados",
      java: "Java — Curso em Vídeo",
      algoritmos: "Algoritmos",
      git: "Git e GitHub",
    };
    $("#curso-detail-title").textContent = names[lang] || lang;
    $("#curso-detail-desc").textContent =
      "Conteúdo oficial do Curso em Vídeo (Gustavo Guanabara). Organize-se por playlists/módulos. Use embeds do YouTube — crédito à fonte.";
    const p = progress();
    const done = group.videos.filter((v) => p.videos[v.id]).length;
    const pct = group.videos.length ? Math.round((done / group.videos.length) * 100) : 0;
    $("#curso-detail-progress").style.width = pct + "%";
    $("#curso-detail-meta").textContent = `${group.videos.length} aulas · ${done} concluídas · ${pct}%`;
    const pl = $("#curso-playlists");
    pl.innerHTML = Object.entries(group.modules)
      .map(([mod, vids]) => {
        const md = vids.filter((v) => p.videos[v.id]).length;
        const mp = vids.length ? Math.round((md / vids.length) * 100) : 0;
        const list = vids
          .sort((a, b) => (a.ordem || 0) - (b.ordem || 0))
          .map(
            (v) =>
              `<button type="button" class="edu-item" data-open-vid="${v.id}">${p.videos[v.id] ? "✓ " : "▶ "}${esc(v.titulo)} <span class="muted small">${v.duracao || ""}</span></button>`
          )
          .join("");
        return `<div class="card" style="margin-bottom:10px">
          <strong>${esc(mod)}</strong>
          <div class="progress-bar" style="margin:6px 0"><div style="width:${mp}%"></div></div>
          <p class="muted small">${md}/${vids.length} · ${mp}%</p>
          ${list}
        </div>`;
      })
      .join("");
    pl.querySelectorAll("[data-open-vid]").forEach((b) =>
      b.addEventListener("click", () => {
        switchTab("videos");
        openVideo(b.dataset.openVid);
      })
    );
    $("#curso-detail-close").onclick = () => {
      detail.hidden = true;
      if (grid) grid.hidden = false;
    };
    $("#curso-continue").onclick = () => {
      const next = group.videos.find((v) => !p.videos[v.id]) || group.videos[0];
      if (next) {
        switchTab("videos");
        openVideo(next.id);
      }
    };
    $("#curso-ask-jarvis").onclick = () => {
      switchTab("mentor");
      const q = $("#mentor-q");
      if (q)
        q.value =
          "Estou estudando o curso de " +
          (names[lang] || lang) +
          " do Curso em Vídeo. Me ajude como professor: resuma o que já deveria saber e o que vem a seguir.";
    };
    try {
      LS.set("current_context", { type: "curso", lang, titulo: names[lang] || lang });
    } catch (_) {}
  }

  // ---------- Challenges ----------
  let chCache = [];
  async function loadChallenges() {
    const list = $("#ch-list");
    if (!list) return;
    const r = await fetch("/api/cyber/phase11/challenges");
    const d = await r.json();
    chCache = d.challenges || [];
    const p = progress();
    list.innerHTML = chCache
      .map(
        (c) =>
          `<button type="button" class="edu-item" data-cid="${c.id}">${p.challenges[c.id] ? "✓ " : ""}${esc(c.titulo)}</button>`
      )
      .join("");
    list.querySelectorAll("[data-cid]").forEach((b) =>
      b.addEventListener("click", () => openChallenge(b.dataset.cid))
    );
  }

  async function openChallenge(id) {
    const r = await fetch("/api/cyber/phase11/challenges/" + encodeURIComponent(id));
    if (!r.ok) return;
    const c = await r.json();
    const view = $("#ch-view");
    let hintIdx = 0;
    view.innerHTML = `
      <h2>${esc(c.titulo)}</h2>
      <p>${esc(c.descricao)}</p>
      <p class="muted small">${c.linguagem} · ${c.nivel} · ${c.categoria}</p>
      <textarea class="code-area" id="ch-code" rows="10">${esc(c.starter_code || "")}</textarea>
      <div class="edu-toolbar">
        <button type="button" class="btn primary" id="ch-run">Executar</button>
        <button type="button" class="btn ghost" id="ch-hint">Dica</button>
        <button type="button" class="btn" id="ch-check">Validar</button>
      </div>
      <pre class="edu-out" id="ch-out"></pre>
    `;
    $("#ch-run")?.addEventListener("click", () => {
      runClientPythonish($("#ch-code").value, $("#ch-out"));
    });
    $("#ch-hint")?.addEventListener("click", () => {
      const hints = c.hints || [];
      if (hintIdx < hints.length) {
        $("#ch-out").textContent = "💡 Dica " + (hintIdx + 1) + ": " + hints[hintIdx];
        hintIdx++;
      } else {
        $("#ch-out").textContent = "Não há mais dicas. Tente de novo ou peça ajuda ao Professor.";
      }
    });
    $("#ch-check")?.addEventListener("click", () => {
      const code = $("#ch-code").value;
      const outEl = $("#ch-out");
      runClientPythonish(code, outEl);
      const out = outEl.textContent || "";
      const tests = c.tests || [];
      let ok = tests.length > 0;
      for (const t of tests) {
        if (t.expect_contains && !out.includes(t.expect_contains)) ok = false;
      }
      if (ok) {
        outEl.textContent = out + "\n\n✅ Desafio concluído!";
        const p = progress();
        p.challenges[id] = true;
        saveProgress(p);
        const n = Object.keys(p.challenges).length;
        if (n >= 10) unlockAch("challenges_10");
        if (n >= 50) unlockAch("challenges_50");
        if (c.categoria === "debug") unlockAch("first_bug");
        if (c.categoria === "loops") unlockAch("first_loop");
        if (c.categoria === "funções") unlockAch("first_function");
        flash("Desafio concluído!");
      } else {
        outEl.textContent =
          out +
          "\n\n❌ O resultado não bateu porque a saída esperada não foi encontrada. Use as dicas ou revise o enunciado.";
      }
    });
  }

  // ---------- Lab ----------
  let labLang = "html";
  const labDefaults = {
    html: "<!DOCTYPE html>\n<html><body>\n<h1>Olá JARVIS</h1>\n<p>Edite e execute.</p>\n</body></html>",
    css: "body { font-family: system-ui; background: #111; color: #eee; }\nh1 { color: #3b82f6; }",
    js: 'console.log("Olá do JS");\ndocument.body.innerHTML = "<h1>JS OK</h1>";',
    python: 'print("Olá, Python!")\nfor i in range(3):\n    print(i)',
  };
  $$("[data-lab-lang]").forEach((b) =>
    b.addEventListener("click", () => {
      labLang = b.dataset.labLang;
      $("#lab-code").value = labDefaults[labLang] || "";
      $$("[data-lab-lang]").forEach((x) => x.classList.toggle("primary", x === b));
    })
  );
  if ($("#lab-code") && !$("#lab-code").value) $("#lab-code").value = labDefaults.html;

  $("#lab-run")?.addEventListener("click", () => {
    const code = $("#lab-code").value;
    const out = $("#lab-out");
    const prev = $("#lab-preview");
    if (labLang === "python") {
      runClientPythonish(code, out);
      prev.srcdoc = "";
      return;
    }
    if (labLang === "html") {
      prev.srcdoc = code;
      out.textContent = "Preview atualizado.";
      unlockAch("first_site");
      return;
    }
    if (labLang === "css") {
      prev.srcdoc = `<style>${code}</style><h1>Título</h1><p>Parágrafo de exemplo.</p>`;
      out.textContent = "CSS aplicado no preview.";
      return;
    }
    if (labLang === "js") {
      prev.srcdoc = `<body></body><script>${code.replace(/<\/script/gi, "<\\/script")}</script>`;
      out.textContent = "JS executado no preview isolado (sandbox).";
      unlockAch("first_run");
    }
  });
  $("#lab-clear")?.addEventListener("click", () => {
    $("#lab-code").value = "";
    $("#lab-out").textContent = "";
    $("#lab-preview").srcdoc = "";
  });
  $("#lab-save")?.addEventListener("click", () => {
    const p = progress();
    p.projects = p.projects || [];
    p.projects.unshift({
      name: "Lab " + labLang + " " + new Date().toLocaleString(),
      lang: labLang,
      code: $("#lab-code").value,
      at: new Date().toISOString(),
    });
    p.projects = p.projects.slice(0, 20);
    saveProgress(p);
    unlockAch("first_project");
    flash("Projeto salvo localmente");
    renderProjects();
  });

  // ---------- Projects ----------
  async function loadTemplates() {
    const el = $("#proj-templates");
    if (!el) return;
    try {
      const r = await fetch("/api/cyber/phase11/templates");
      const d = await r.json();
      el.innerHTML = (d.templates || [])
        .map(
          (t) =>
            `<div class="card"><strong>${esc(t.name)}</strong><p class="muted small">${t.lang} · ${t.level}</p>
            <button type="button" class="btn" data-tpl="${t.id}">Criar</button></div>`
        )
        .join("");
      el.querySelectorAll("[data-tpl]").forEach((b) =>
        b.addEventListener("click", () => {
          switchTab("lab");
          const map = { calc: "html", quiz: "html", todo: "html", site: "html", portfolio: "html", game: "js", dashboard: "html", bot: "python", interactive: "html", "api-demo": "python" };
          labLang = map[b.dataset.tpl] || "html";
          $("#lab-code").value = labDefaults[labLang];
          flash("Template: edite no laboratório");
        })
      );
    } catch (_) {}
  }
  function renderProjects() {
    const el = $("#proj-mine");
    if (!el) return;
    const p = progress();
    const list = p.projects || [];
    el.innerHTML =
      list.length === 0
        ? "<span class='muted'>Nenhum ainda.</span>"
        : list
            .map(
              (x, i) =>
                `<button type="button" class="btn ghost" data-proj="${i}">${esc(x.name)}</button>`
            )
            .join("");
    el.querySelectorAll("[data-proj]").forEach((b) =>
      b.addEventListener("click", () => {
        const item = list[+b.dataset.proj];
        if (!item) return;
        switchTab("lab");
        labLang = item.lang || "html";
        $("#lab-code").value = item.code || "";
      })
    );
  }

  // ---------- Progress & achievements ----------
  async function loadProgressUI() {
    const bars = $("#prog-bars");
    const list = $("#prog-list");
    const p = progress();
    const zeroPct = Math.round((Object.keys(p.zero || {}).length / 10) * 100);
    const vidPct = Math.min(100, Object.keys(p.videos || {}).length * 20);
    const chPct = Math.min(100, Object.keys(p.challenges || {}).length * 10);
    if (bars) {
      bars.innerHTML = [
        ["Trilha do zero", zeroPct],
        ["Vídeos", vidPct],
        ["Desafios", chPct],
      ]
        .map(
          ([n, pct]) =>
            `<div class="prog-row"><span style="width:110px">${n}</span><div class="bar"><i style="width:${pct}%"></i></div><span>${pct}%</span></div>`
        )
        .join("");
    }
    if (list) {
      list.innerHTML = `
        <li>Aulas zero: ${Object.keys(p.zero || {}).length}</li>
        <li>Vídeos: ${Object.keys(p.videos || {}).length}</li>
        <li>Desafios: ${Object.keys(p.challenges || {}).length}</li>
        <li>Projetos locais: ${(p.projects || []).length}</li>
        <li>Conquistas: ${(p.achievements || []).length}</li>
      `;
    }
    try {
      const r = await fetch("/api/cyber/phase11/achievements");
      const d = await r.json();
      const grid = $("#ach-grid");
      if (grid) {
        const unlocked = new Set(p.achievements || []);
        grid.innerHTML = (d.achievements || [])
          .map(
            (a) =>
              `<div class="ach-card ${unlocked.has(a.id) ? "unlocked" : "locked"}">
                <strong>${unlocked.has(a.id) ? "🏆" : "🔒"} ${esc(a.title)}</strong>
                <p class="muted small">${esc(a.desc)}</p>
              </div>`
          )
          .join("");
      }
    } catch (_) {}
  }

  // ---------- Professor ----------
  async function loadProfessor() {
    const box = $("#prof-btns");
    if (!box) return;
    try {
      const r = await fetch("/api/cyber/phase11/professor");
      const d = await r.json();
      box.innerHTML = (d.buttons || [])
        .map((b) => `<button type="button" class="btn ghost" data-prof="${b.id}">${esc(b.label)}</button>`)
        .join("");
      box.querySelectorAll("[data-prof]").forEach((btn) =>
        btn.addEventListener("click", () => {
          const q = $("#mentor-q");
          const map = {
            simple: "Explique de forma bem simples: ",
            example: "Mostre um exemplo de: ",
            steps: "Explique passo a passo: ",
            code: "Mostre o código de: ",
            hint: "Me dê uma dica sobre: ",
            where_wrong: "Onde estou errando neste código? ",
            another_way: "Explique de outro jeito: ",
          };
          q.value = (map[btn.dataset.prof] || "") + (q.value || "variáveis");
        })
      );
    } catch (_) {}
  }

  $("#mentor-go")?.addEventListener("click", async () => {
    const q = ($("#mentor-q")?.value || "").trim();
    const attempt = ($("#mentor-attempt")?.value || "").trim();
    const out = $("#mentor-out");
    if (!q) {
      out.textContent = "Digite uma pergunta.";
      return;
    }
    out.textContent = "JARVIS Professor está processando…";
    let ctx = null;
    try { ctx = LS.get("current_context", null); } catch (_) {}
    const contextNote = ctx
      ? ` [Contexto atual: ${ctx.type || ""} — ${ctx.titulo || ctx.lang || ctx.id || ""}]`
      : "";
    try {
      // Prefer phase10 mentor if available
      const r = await fetch("/api/cyber/phase10/mentor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q + contextNote,
          attempt,
          stage: "pergunta",
          context: ctx || {},
        }),
      });
      if (r.ok) {
        const d = await r.json();
        out.textContent = typeof d === "string" ? d : (d.reply || d.answer || JSON.stringify(d, null, 2));
        return;
      }
    } catch (_) {}
    // Fallback: use main JARVIS chat API with education context
    try {
      const history = [
        { role: "system", content: "Você é o JARVIS Professor. Responda de forma didática, clara e em português. Foque em ensinar programação. Contexto do aluno: " + (contextNote || "geral") },
        { role: "user", content: q + (attempt ? "\n\nMeu código/tentativa:\n" + attempt : "") },
      ];
      const r2 = await fetch("/api/jarvis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history, context: "PROGRAMMING / AULA / EDUCACAO", mode: "programacao" }),
      });
      const d2 = await r2.json();
      if (d2.reply) {
        out.textContent = d2.reply;
        return;
      }
      if (d2.error) {
        out.textContent = "Não consegui responder agora: " + d2.error + "\n\nTente pelo chat principal do JARVIS ou reformule a pergunta.";
        return;
      }
    } catch (e) {
      out.textContent = "Falha de conexão com o JARVIS. Verifique se o servidor está online e se há API key configurada.";
      return;
    }
    // Fallback local simple answers for common concepts
    const lower = q.toLowerCase();
    if (lower.includes("variáv")) {
      out.textContent =
        "Uma variável é como uma caixinha com nome onde você guarda uma informação.\n\nnome = \"João\"\n\nnome\n  ↓\n\"João\"\n\nDepois você pode usar print(nome) para ver o valor.";
    } else if (lower.includes("loop") || lower.includes("for") || lower.includes("while")) {
      out.textContent =
        "Loop (repetição) executa o mesmo bloco várias vezes.\n\nfor i in range(3):\n    print(i)\n\nIsso imprime 0, 1, 2.";
    } else {
      out.textContent =
        "Abra o chat principal do JARVIS e pergunte com o contexto da aula — ou tente reformular (ex: \"o que é uma variável?\").";
    }
  });

  // ---------- Search ----------
  $("#edu-search-btn")?.addEventListener("click", doSearch);
  $("#edu-search")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
  async function doSearch() {
    const q = ($("#edu-search")?.value || "").trim();
    if (!q) return;
    try {
      const r = await fetch("/api/cyber/phase11/search?q=" + encodeURIComponent(q));
      const d = await r.json();
      const results = d.results || [];
      alert(
        results.length
          ? results.map((x) => x.type + ": " + x.title).join("\n")
          : "Nada encontrado. Tente: variável, loop, python, html"
      );
    } catch (_) {
      alert("Busca indisponível no momento.");
    }
  }

  $("#lib-q")?.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    const q = e.target.value.trim();
    const box = $("#lib-results");
    if (!q || !box) return;
    const r = await fetch("/api/cyber/phase11/search?q=" + encodeURIComponent(q));
    const d = await r.json();
    box.innerHTML = (d.results || [])
      .map((x) => `<div class="card"><strong>${esc(x.type)}</strong> — ${esc(x.title)}</div>`)
      .join("") || "<p class='muted'>Nada encontrado.</p>";
  });

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Init
  loadOverview();
  loadBeginner();
  loadVideos();
  loadChallenges();
  loadTemplates();
  renderProjects();
  loadProgressUI();
  loadProfessor();

  // If phase10.js also binds tabs, our data-tab names may differ — ensure coexistence
  document.addEventListener("DOMContentLoaded", () => {
    loadOverview();
  });
})();
