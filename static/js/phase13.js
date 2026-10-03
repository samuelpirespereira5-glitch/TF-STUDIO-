/**
 * JARVIS Phase 13 — Video Engine 2.0 + Command Center + Tools Central + Continue Studying
 * Incremental: enhances phase11/phase12 without rewriting.
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

  // ---------- Video Engine 2.0 states ----------
  const VSTATE = {
    LOADING: "LOADING",
    READY: "READY",
    PLAYING: "PLAYING",
    PAUSED: "PAUSED",
    BUFFERING: "BUFFERING",
    ERROR: "ERROR",
    UNAVAILABLE: "UNAVAILABLE",
    OFFLINE: "OFFLINE",
  };

  let activePlayerId = null;
  let loadTimer = null;
  let lastVideoList = [];

  function isOffline() {
    return typeof navigator !== "undefined" && navigator.onLine === false;
  }

  function setPlayerState(wrap, state, msg) {
    if (!wrap) return;
    const states = Object.values(VSTATE);
    states.forEach((s) => wrap.classList.remove("vs-" + s.toLowerCase(), "loading", "loaded", "error"));
    wrap.classList.add("vs-" + String(state).toLowerCase());
    if (state === VSTATE.LOADING || state === VSTATE.BUFFERING) wrap.classList.add("loading");
    if (state === VSTATE.READY || state === VSTATE.PLAYING || state === VSTATE.PAUSED) wrap.classList.add("loaded");
    if (state === VSTATE.ERROR || state === VSTATE.UNAVAILABLE || state === VSTATE.OFFLINE) wrap.classList.add("error");

    const loading = $("#video-loading");
    const errBox = $("#video-error");
    const statusEl = $("#video-status-label");
    if (loading) loading.hidden = !(state === VSTATE.LOADING || state === VSTATE.BUFFERING);
    if (errBox) errBox.hidden = !(state === VSTATE.ERROR || state === VSTATE.UNAVAILABLE || state === VSTATE.OFFLINE);
    if (statusEl) {
      const labels = {
        LOADING: "Carregando…",
        READY: "Pronto",
        PLAYING: "Reproduzindo",
        PAUSED: "Pausado",
        BUFFERING: "Buffering…",
        ERROR: "Não foi possível carregar o vídeo.",
        UNAVAILABLE: "Vídeo indisponível.",
        OFFLINE: "Você está offline.",
      };
      statusEl.textContent = msg || labels[state] || state;
    }
  }

  function destroyActiveIframe() {
    const iframe = $("#video-iframe");
    if (iframe) {
      try {
        iframe.onload = null;
        iframe.onerror = null;
        iframe.src = "about:blank";
      } catch (_) {}
    }
    if (loadTimer) {
      clearTimeout(loadTimer);
      loadTimer = null;
    }
    activePlayerId = null;
  }

  function thumbUrl(v) {
    if (v.thumbnail) return v.thumbnail;
    if (v.video_id) return "https://i.ytimg.com/vi/" + encodeURIComponent(v.video_id) + "/hqdefault.jpg";
    return "";
  }

  function lessonStatusIcon(id, currentId, doneMap) {
    if (doneMap && doneMap[id]) return "✓";
    if (id === currentId) return "▶";
    return "○";
  }

  // Enhanced video cards with thumbnails + status (playlist performance: cards only)
  window.JarvisVideoEngine = {
    VSTATE,
    destroyActiveIframe,
    setPlayerState,
    renderVideoCards(videos, gridSel, opts) {
      const grid = $(gridSel || "#edu-videos-grid");
      if (!grid) return;
      opts = opts || {};
      const p = LS.get("progress", { videos: {} });
      const done = p.videos || {};
      const current = opts.currentId || LS.get("continue_video", null);
      lastVideoList = videos || [];
      // Progressive: limit initial DOM if huge list
      const pageSize = opts.pageSize || 48;
      const page = opts.page || 0;
      const slice = lastVideoList.slice(0, (page + 1) * pageSize);

      grid.innerHTML = slice
        .map((v, i) => {
          const doneFlag = !!done[v.id];
          const isCur = current === v.id;
          const icon = lessonStatusIcon(v.id, current, done);
          const th = thumbUrl(v);
          const num = v.ordem != null ? String(v.ordem).padStart(2, "0") : String(i + 1).padStart(2, "0");
          const statusCls = doneFlag ? "done" : isCur ? "current" : "todo";
          return `<article class="edu-vid-card ${statusCls}" data-vid="${esc(v.id)}" data-ordem="${esc(num)}">
            <div class="edu-vid-thumb-wrap">
              ${th ? `<img class="edu-vid-thumb" src="${esc(th)}" alt="" loading="lazy" decoding="async" width="320" height="180" />` : `<div class="edu-vid-thumb placeholder">▶️</div>`}
              <span class="edu-vid-dur">${esc(v.duracao || "")}</span>
              <span class="edu-vid-status" title="${doneFlag ? "Concluída" : isCur ? "Atual" : "Pendente"}">${icon}</span>
            </div>
            <div class="edu-vid-meta">
              <strong class="edu-vid-title">Aula ${esc(num)} — ${esc(v.titulo || "")}</strong>
              <p class="muted small">${esc(v.linguagem || "")} · ${esc(v.fonte || "")}</p>
              <button type="button" class="btn btn-sm" data-open-vid="${esc(v.id)}">${isCur ? "Continuar" : "Assistir"} ${doneFlag ? "✓" : ""}</button>
            </div>
          </article>`;
        })
        .join("");

      if (lastVideoList.length > slice.length) {
        const more = document.createElement("button");
        more.type = "button";
        more.className = "btn";
        more.textContent = "Carregar mais aulas…";
        more.onclick = () =>
          window.JarvisVideoEngine.renderVideoCards(lastVideoList, gridSel, { ...opts, page: page + 1, currentId: current });
        grid.appendChild(more);
      }

      grid.querySelectorAll("[data-open-vid]").forEach((b) =>
        b.addEventListener("click", () => openVideoEnhanced(b.dataset.openVid))
      );
    },

    openVideo: openVideoEnhanced,
    markContinue(id, meta) {
      LS.set("continue_video", id);
      if (meta) LS.set("continue_meta", meta);
    },
    getContinue() {
      return { id: LS.get("continue_video", null), meta: LS.get("continue_meta", null) };
    },
  };

  async function openVideoEnhanced(id) {
    if (isOffline()) {
      const wrap = $("#video-embed-wrap");
      const card = $("#video-player-card");
      if (card) card.hidden = false;
      setPlayerState(wrap, VSTATE.OFFLINE);
      return;
    }
    // Single active player: destroy previous
    destroyActiveIframe();

    const r = await fetch("/api/cyber/phase11/videos/" + encodeURIComponent(id));
    if (!r.ok) {
      const wrap = $("#video-embed-wrap");
      setPlayerState(wrap, VSTATE.UNAVAILABLE);
      return;
    }
    const v = await r.json();
    const card = $("#video-player-card");
    if (card) card.hidden = false;
    if ($("#video-title")) $("#video-title").textContent = v.titulo || "";
    if ($("#video-desc")) $("#video-desc").textContent = v.descricao || "";
    if ($("#video-learn")) {
      $("#video-learn").innerHTML = (v.o_que_aprendo || []).map((x) => `<span class="chip">${esc(x)}</span>`).join("");
    }

    const wrap = $("#video-embed-wrap");
    const iframe = $("#video-iframe");
    const ytUrl = v.url_oficial || "https://www.youtube.com/watch?v=" + (v.video_id || "");
    const yt = $("#video-yt");
    if (yt) yt.href = ytUrl;
    const errYt = $("#video-error-yt");
    if (errYt) errYt.href = ytUrl;

    // Retry button
    const retryBtn = $("#video-retry");
    if (retryBtn) {
      retryBtn.onclick = () => openVideoEnhanced(id);
    }

    setPlayerState(wrap, VSTATE.LOADING);
    activePlayerId = id;

    if (!iframe) {
      setPlayerState(wrap, VSTATE.ERROR);
      return;
    }

    iframe.onload = () => {
      if (activePlayerId === id) setPlayerState(wrap, VSTATE.READY);
    };
    iframe.onerror = () => {
      if (activePlayerId === id) setPlayerState(wrap, VSTATE.ERROR);
    };
    loadTimer = setTimeout(() => {
      if (wrap && wrap.classList.contains("loading") && activePlayerId === id) {
        setPlayerState(wrap, VSTATE.ERROR);
      }
    }, 10000);

    // Load iframe only now (not on playlist)
    iframe.src =
      "https://www.youtube.com/embed/" +
      encodeURIComponent(v.video_id || "") +
      "?rel=0&modestbranding=1";

    // Progress + continue
    const p = LS.get("progress", { videos: {} });
    const pct = p.videos && p.videos[id] ? 100 : 0;
    if ($("#video-progress")) $("#video-progress").style.width = pct + "%";
    window.JarvisVideoEngine.markContinue(id, {
      titulo: v.titulo,
      curso: v.linguagem || v.modulo || "",
      playlist: v.playlist_id || v.modulo || "",
      aula: v.titulo,
      linguagem: v.linguagem,
    });
    try {
      LS.set("current_context", {
        type: "video",
        id,
        titulo: v.titulo,
        curso: v.linguagem || v.modulo || "",
        fonte: v.fonte || "Curso em Vídeo",
        video_id: v.video_id,
      });
    } catch (_) {}

    // Next / prev lesson within lastVideoList or same linguagem
    wireNavButtons(id, v);

    const doneBtn = $("#video-done");
    if (doneBtn) {
      doneBtn.onclick = () => {
        const pr = LS.get("progress", { videos: {} });
        pr.videos = pr.videos || {};
        pr.videos[id] = true;
        LS.set("progress", pr);
        if ($("#video-progress")) $("#video-progress").style.width = "100%";
        flash("Aula marcada como concluída");
        // auto next hint
        const next = findNext(id);
        if (next && $("#video-next-hint")) {
          $("#video-next-hint").textContent = "Próxima: " + (next.titulo || next.id);
        }
      };
    }
  }

  function findNext(id) {
    const list = lastVideoList.length ? lastVideoList : [];
    const idx = list.findIndex((x) => x.id === id);
    if (idx >= 0 && idx + 1 < list.length) return list[idx + 1];
    return null;
  }
  function findPrev(id) {
    const list = lastVideoList.length ? lastVideoList : [];
    const idx = list.findIndex((x) => x.id === id);
    if (idx > 0) return list[idx - 1];
    return null;
  }

  function wireNavButtons(id, v) {
    const next = findNext(id);
    const prev = findPrev(id);
    const nextBtn = $("#video-next");
    const prevBtn = $("#video-prev");
    const listBtn = $("#video-list");
    if (nextBtn) {
      nextBtn.disabled = !next;
      nextBtn.onclick = () => next && openVideoEnhanced(next.id);
    }
    if (prevBtn) {
      prevBtn.disabled = !prev;
      prevBtn.onclick = () => prev && openVideoEnhanced(prev.id);
    }
    if (listBtn) {
      listBtn.onclick = () => {
        destroyActiveIframe();
        const card = $("#video-player-card");
        if (card) card.hidden = true;
        const tab = document.querySelector('.edu-tab[data-tab="videos"]');
        if (tab) tab.click();
      };
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

  // ---------- Continuar Estudando panel ----------
  function renderContinuePanel() {
    const box = $("#continue-studying");
    if (!box) return;
    const c = window.JarvisVideoEngine.getContinue();
    if (!c.id) {
      box.innerHTML = `<p class="muted">Nenhum estudo em andamento. Escolha uma aula.</p>`;
      return;
    }
    const m = c.meta || {};
    box.innerHTML = `
      <div class="continue-card">
        <h3>Continuar estudando</h3>
        <p><strong>${esc(m.curso || "Curso")}</strong></p>
        <p class="muted">${esc(m.playlist || "")}</p>
        <p>→ ${esc(m.aula || c.id)}</p>
        <button type="button" class="btn primary" id="btn-continue-study">Continuar</button>
      </div>`;
    const b = $("#btn-continue-study");
    if (b) b.onclick = () => openVideoEnhanced(c.id);
  }

  // ---------- Command Center Ctrl+K ----------
  function ensureCommandPalette() {
    if ($("#jarvis-cmd-palette")) return;
    const div = document.createElement("div");
    div.id = "jarvis-cmd-palette";
    div.className = "jarvis-cmd-palette";
    div.hidden = true;
    div.innerHTML = `
      <div class="jarvis-cmd-backdrop" data-close-cmd></div>
      <div class="jarvis-cmd-panel" role="dialog" aria-label="Command Center">
        <input type="search" id="jarvis-cmd-input" placeholder="Buscar páginas, ferramentas, cursos, aulas…" autocomplete="off" />
        <ul id="jarvis-cmd-results" class="jarvis-cmd-results"></ul>
        <p class="muted small jarvis-cmd-hint">Ctrl+K · Esc fecha</p>
      </div>`;
    document.body.appendChild(div);
    div.querySelector("[data-close-cmd]").addEventListener("click", () => closeCmd());
    const input = $("#jarvis-cmd-input");
    let t = null;
    input.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => runCmdSearch(input.value), 200);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeCmd();
      if (e.key === "Enter") {
        const first = $("#jarvis-cmd-results li button");
        if (first) first.click();
      }
    });
  }

  function openCmd() {
    ensureCommandPalette();
    const el = $("#jarvis-cmd-palette");
    el.hidden = false;
    const input = $("#jarvis-cmd-input");
    input.value = "";
    $("#jarvis-cmd-results").innerHTML = defaultCmdItems();
    setTimeout(() => input.focus(), 30);
  }
  function closeCmd() {
    const el = $("#jarvis-cmd-palette");
    if (el) el.hidden = true;
  }

  function defaultCmdItems() {
    const items = [
      { label: "Educação", href: "/education" },
      { label: "Game Lab", href: "/game-lab" },
      { label: "Editor", href: "/editor" },
      { label: "Certificados", href: "/certificados" },
      { label: "Qualidade / Health", href: "/qualidade" },
      { label: "JARVIS Chat", href: "/jarvis" },
      { label: "Cyber Hub", href: "/cyber" },
    ];
    return items
      .map(
        (i) =>
          `<li><button type="button" data-href="${esc(i.href)}">${esc(i.label)}</button></li>`
      )
      .join("");
  }

  async function runCmdSearch(q) {
    const list = $("#jarvis-cmd-results");
    if (!list) return;
    if (!q || q.length < 2) {
      list.innerHTML = defaultCmdItems();
      bindCmdResults();
      return;
    }
    list.innerHTML = `<li class="muted">Buscando…</li>`;
    try {
      const r = await fetch("/api/cyber/phase13/search?q=" + encodeURIComponent(q));
      const d = await r.json();
      const rows = d.results || [];
      if (!rows.length) {
        list.innerHTML = `<li class="muted">Nenhum resultado</li>`;
        return;
      }
      list.innerHTML = rows
        .map((x) => {
          let href = "/education";
          if (x.type === "tool") href = "/jarvis";
          if (x.type === "game") href = "/game-lab";
          if (x.type === "project") href = "/education";
          if (x.type === "video") href = "/education#videos";
          return `<li><button type="button" data-href="${esc(href)}" data-vid="${esc(x.id || "")}" data-type="${esc(x.type)}"><span class="chip">${esc(x.type)}</span> ${esc(x.title)}</button></li>`;
        })
        .join("");
      bindCmdResults();
    } catch {
      list.innerHTML = `<li class="muted">Falha na busca</li>`;
    }
  }

  function bindCmdResults() {
    $$("#jarvis-cmd-results [data-href]").forEach((b) => {
      b.onclick = () => {
        const type = b.dataset.type;
        const vid = b.dataset.vid;
        if (type === "video" && vid && typeof openVideoEnhanced === "function") {
          closeCmd();
          openVideoEnhanced(vid);
          return;
        }
        closeCmd();
        window.location.href = b.dataset.href;
      };
    });
  }

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const el = $("#jarvis-cmd-palette");
      if (el && !el.hidden) closeCmd();
      else openCmd();
    }
    if (e.key === "Escape") closeCmd();
  });

  // Hook phase11 loadVideos if present
  const origFetch = window.fetch;
  // After DOM ready, enhance education page
  function boot() {
    ensureCommandPalette();
    renderContinuePanel();
    // Patch: if phase11 loadVideos exists, wrap to use thumbnails
    if (window.__phase11LoadVideosPatched) return;
    // Observe video grid updates from phase11
    const grid = $("#edu-videos-grid");
    if (grid) {
      // Intercept after phase11 fills — re-enhance on tab videos
      document.querySelectorAll('.edu-tab[data-tab="videos"]').forEach((tab) => {
        tab.addEventListener("click", () => {
          setTimeout(async () => {
            try {
              const r = await fetch("/api/cyber/phase11/videos");
              const d = await r.json();
              window.JarvisVideoEngine.renderVideoCards(d.videos || [], "#edu-videos-grid", {
                currentId: LS.get("continue_video", null),
              });
            } catch (_) {}
          }, 400);
        });
      });
    }
    // Expose open for phase11 compatibility
    window.openVideoPhase13 = openVideoEnhanced;
    // Replace phase11 openVideo if it left a global — soft override via event
    document.addEventListener("click", (e) => {
      const btn = e.target.closest && e.target.closest("[data-open-vid]");
      if (!btn) return;
      // Let phase13 handle if VideoEngine is active
      if (window.JarvisVideoEngine && btn.closest("#edu-videos-grid, #curso-playlists, #video-player-card")) {
        e.preventDefault();
        e.stopPropagation();
        openVideoEnhanced(btn.dataset.openVid);
      }
    }, true);

    // Online/offline
    window.addEventListener("offline", () => {
      const wrap = $("#video-embed-wrap");
      if (wrap && activePlayerId) setPlayerState(wrap, VSTATE.OFFLINE);
    });
    window.addEventListener("online", () => {
      if (activePlayerId) openVideoEnhanced(activePlayerId);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
