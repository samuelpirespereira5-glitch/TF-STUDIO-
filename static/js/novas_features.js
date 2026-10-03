(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  let lastQuiz = null;

  // Web Audio sound synth
  let audioCtx = null;
  function playTone(freq, type, dur) {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const o = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      o.type = type || "sine";
      o.frequency.value = freq || 440;
      g.gain.value = 0.15;
      o.connect(g); g.connect(audioCtx.destination);
      o.start();
      g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + (dur || 0.15));
      o.stop(audioCtx.currentTime + (dur || 0.15) + 0.02);
    } catch (_) {}
  }

  $$("#nf-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("#nf-tabs button").forEach((b) => b.classList.remove("active"));
      $$(".nf-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = $(`#panel-${btn.dataset.tab}`);
      if (panel) panel.classList.add("active");
      if (btn.dataset.tab === "profile") { loadProgress(); loadAchievements(); }
      if (btn.dataset.tab === "study") { loadDecks(); loadEvents(); }
      if (btn.dataset.tab === "sprite") loadSpritesMini();
    });
  });

  async function api(url, opts) {
    const r = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(opts && opts.headers) },
      credentials: "same-origin",
      ...opts,
    });
    return r.json();
  }
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  // ---- GAMES ----
  async function loadTemplates() {
    const data = await api("/api/nf/templates");
    const el = $("#tpl-list");
    if (!el) return;
    el.innerHTML = (data.templates || []).map((t) => `
      <div class="item" data-tpl="${t.id}">
        <span class="emoji">${emojiForType(t.type)}</span>
        <div class="meta"><strong>${esc(t.name)}</strong><span>${esc(t.description)}</span></div>
      </div>`).join("");
    el.querySelectorAll(".item").forEach((item) => {
      item.addEventListener("click", () => {
        playTone(600, "square", 0.05);
        window.location.href = `/criar-jogo?template=${item.dataset.tpl}`;
      });
    });
  }
  function emojiForType(t) {
    return { platform: "🏃", race: "🏁", collect: "💎", maze: "🧩", escape: "🚪", shooter: "🔫" }[t] || "🎮";
  }

  async function loadAssets(cat) {
    const q = cat ? `?category=${encodeURIComponent(cat)}` : "";
    const data = await api("/api/nf/assets" + q);
    const el = $("#asset-list");
    if (!el) return;
    el.innerHTML = (data.assets || []).map((a) => `
      <div class="asset" title="${esc(a.name)}" data-id="${a.id}" style="border-top:3px solid ${a.color||'#333'}">
        <span class="emoji">${a.emoji}</span>${esc(a.name)}
      </div>`).join("");
    el.querySelectorAll(".asset").forEach((a) => {
      a.addEventListener("click", () => {
        navigator.clipboard?.writeText(a.dataset.id);
        playTone(880, "sine", 0.08);
        a.style.outline = "2px solid #3b82f6";
        setTimeout(() => (a.style.outline = ""), 800);
      });
    });
  }
  $$(".nf-filters .chip").forEach((c) => {
    c.addEventListener("click", () => {
      $$(".nf-filters .chip").forEach((x) => x.classList.remove("active"));
      c.classList.add("active");
      loadAssets(c.dataset.cat || "");
    });
  });

  async function loadRanking() {
    const data = await api("/api/nf/ranking");
    const el = $("#rank-list");
    if (!el) return;
    const entries = data.entries || [];
    if (!entries.length) {
      el.innerHTML = '<p class="muted small">Nenhuma pontuação ainda.</p>';
      return;
    }
    el.innerHTML = entries.map((e, i) => `
      <div class="item">
        <span class="emoji">${i < 3 ? ["🥇","🥈","🥉"][i] : "#"+(i+1)}</span>
        <div class="meta"><strong>${esc(e.username)}</strong><span>${e.score} pts · ${esc(e.game_id||"")}</span></div>
      </div>`).join("");
  }

  async function loadSounds() {
    const data = await api("/api/nf/sounds");
    const el = $("#sound-list");
    if (!el) return;
    el.innerHTML = (data.sounds || []).map((s) => `
      <div class="item" data-freq="${s.freq}" data-type="${s.type}" data-dur="${s.dur}">
        <span class="emoji">🔊</span>
        <div class="meta"><strong>${esc(s.name)}</strong><span>${esc(s.desc)} · clique para ouvir</span></div>
      </div>`).join("");
    el.querySelectorAll(".item").forEach((item) => {
      item.addEventListener("click", () => {
        playTone(+item.dataset.freq, item.dataset.type, +item.dataset.dur);
      });
    });
  }

  $("#btn-share")?.addEventListener("click", async () => {
    const gid = $("#share-game-id")?.value?.trim();
    if (!gid) return;
    const data = await api("/api/nf/share", { method: "POST", body: JSON.stringify({ game_id: gid }) });
    const out = $("#share-result");
    if (data.ok) {
      out.innerHTML = `Link público: <a href="${data.url}" target="_blank">${location.origin}${data.url}</a>`;
      playTone(523, "sine", 0.3);
    } else out.textContent = data.error || "Erro";
  });

  // ---- PROGRAMAÇÃO ----
  async function loadGuided() {
    const data = await api("/api/nf/guided");
    const el = $("#guided-list");
    if (!el) return;
    el.innerHTML = (data.projects || []).map((p) => `
      <div class="item" data-id="${p.id}">
        <span class="emoji">📋</span>
        <div class="meta"><strong>${esc(p.title)}</strong><span>${p.level} · ${p.lang} · ${p.checkpoints} checkpoints</span></div>
      </div>`).join("");
    el.querySelectorAll(".item").forEach((item) => {
      item.addEventListener("click", () => showGuided(item.dataset.id));
    });
  }
  async function showGuided(id) {
    const data = await api(`/api/nf/guided/${id}`);
    const p = data.project;
    if (!p) return;
    const box = $("#guided-detail");
    box.style.display = "block";
    $("#gd-title").textContent = p.title;
    $("#gd-meta").textContent = `${p.level} · ${p.lang}` + (p.hint ? ` · 💡 ${p.hint}` : "");
    $("#gd-checks").innerHTML = (p.checkpoints || []).map((c) => `<li>${esc(c)}</li>`).join("");
    $("#gd-starter").textContent = p.starter || "";
  }
  async function loadDaily() {
    const data = await api("/api/nf/daily");
    const el = $("#daily-challenge");
    if (!el || !data.challenge) return;
    const c = data.challenge;
    el.innerHTML = `<strong>${esc(c.title)}</strong><p class="muted small">${esc(c.desc)}</p><span class="chip">${esc(c.lang)}</span>`;
  }

  // ---- ESTUDOS ----
  let currentDeck = null, currentCard = null;

  async function loadDecks() {
    const data = await api("/api/nf/flashcards/decks");
    const el = $("#deck-list");
    if (!el) return;
    el.innerHTML = (data.decks || []).map((d) => `
      <div class="item" data-id="${d.id}">
        <span class="emoji">🃏</span>
        <div class="meta"><strong>${esc(d.name)}</strong><span>${d.count} cards · ${d.due} para revisar</span></div>
      </div>`).join("");
    el.querySelectorAll(".item").forEach((item) => {
      item.addEventListener("click", () => {
        currentDeck = item.dataset.id;
        $("#add-card-form").style.display = "block";
        startFlashStudy();
      });
    });
  }
  $("#btn-new-deck")?.addEventListener("click", async () => {
    const name = $("#deck-name")?.value?.trim();
    if (!name) return;
    await api("/api/nf/flashcards/decks", { method: "POST", body: JSON.stringify({ name }) });
    $("#deck-name").value = "";
    loadDecks();
  });
  $("#btn-add-card")?.addEventListener("click", async () => {
    if (!currentDeck) return;
    const front = $("#card-front")?.value?.trim();
    const back = $("#card-back")?.value?.trim();
    if (!front || !back) return;
    await api("/api/nf/flashcards/cards", { method: "POST", body: JSON.stringify({ deck_id: currentDeck, front, back }) });
    $("#card-front").value = ""; $("#card-back").value = "";
    loadDecks();
  });
  async function startFlashStudy() {
    if (!currentDeck) return;
    const data = await api(`/api/nf/flashcards/due/${currentDeck}`);
    const cards = data.cards || [];
    const box = $("#flash-study");
    box.style.display = "block";
    if (!cards.length) {
      $("#fc-front").textContent = "Nenhum card para revisar agora 🎉";
      $("#fc-back").style.display = "none";
      currentCard = null;
      return;
    }
    currentCard = cards[0];
    $("#fc-front").textContent = currentCard.front;
    $("#fc-back").textContent = currentCard.back;
    $("#fc-back").style.display = "none";
  }
  $("#fc-reveal")?.addEventListener("click", () => { $("#fc-back").style.display = "block"; });
  $$("#flash-study [data-q]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!currentDeck || !currentCard) return;
      await api("/api/nf/flashcards/review", {
        method: "POST",
        body: JSON.stringify({ deck_id: currentDeck, card_id: currentCard.id, quality: parseInt(btn.dataset.q, 10) }),
      });
      playTone(+btn.dataset.q >= 3 ? 523 : 200, "sine", 0.12);
      startFlashStudy();
      loadDecks();
    });
  });

  $("#btn-summary")?.addEventListener("click", async () => {
    const text = $("#summary-text")?.value || "";
    const data = await api("/api/nf/summary", { method: "POST", body: JSON.stringify({ text }) });
    const out = $("#summary-out");
    if (!data.ok) { out.textContent = data.error || "Erro"; return; }
    let mm = "";
    if (data.mindmap) {
      mm = `<div class="nf-mindmap"><div class="mm-root">🧠 ${esc(data.mindmap.label)}</div>`;
      (data.mindmap.children || []).forEach((n) => {
        mm += `<div class="mm-node">${esc(n.label)}</div>`;
        (n.children || []).forEach((c) => { mm += `<div class="mm-leaf">→ ${esc(c.label)}</div>`; });
      });
      mm += "</div>";
    }
    out.innerHTML = `
      <p><strong>Pontos-chave</strong> (${data.word_count||0} palavras):</p>
      <ul>${(data.summary_points||[]).map(s=>`<li>${esc(s)}</li>`).join("")}</ul>
      <p><strong>Keywords:</strong> ${(data.keywords||[]).map(k=>`<span class="kw">${esc(k)}</span>`).join("")}</p>
      ${mm}`;
  });

  $("#btn-quiz")?.addEventListener("click", async () => {
    const topic = $("#quiz-topic")?.value?.trim() || "programação";
    const data = await api("/api/nf/quiz", { method: "POST", body: JSON.stringify({ topic, n: 5 }) });
    lastQuiz = data;
    const out = $("#quiz-out");
    out.innerHTML = (data.questions || []).map((q, i) => `
      <div class="q" data-qid="${q.id}">
        <strong>${i+1}. ${esc(q.question)}</strong>
        <div class="opts">
          ${(q.options||[]).map((o,j)=>`<label><input type="radio" name="q${i}" value="${j}"> ${esc(o)}</label>`).join("")}
        </div>
      </div>`).join("") +
      `<button class="btn primary" id="btn-score-quiz" style="margin-top:12px">Ver pontuação</button>
       <div id="quiz-score"></div>` +
      (data.note ? `<p class="muted small">${esc(data.note)}</p>` : "");
    $("#btn-score-quiz")?.addEventListener("click", scoreCurrentQuiz);
  });

  async function scoreCurrentQuiz() {
    if (!lastQuiz) return;
    const answers = (lastQuiz.questions || []).map((q, i) => {
      const checked = document.querySelector(`input[name="q${i}"]:checked`);
      return { id: q.id, chosen: checked ? parseInt(checked.value, 10) : -1 };
    });
    const data = await api("/api/nf/quiz/score", {
      method: "POST",
      body: JSON.stringify({ answers, questions: lastQuiz.questions }),
    });
    const el = $("#quiz-score");
    if (el && data.ok) {
      el.innerHTML = `<div class="nf-score-banner">${data.grade}<br><strong>${data.correct}/${data.total}</strong> (${data.percent}%)</div>`;
      playTone(data.percent >= 70 ? 660 : 220, "sine", 0.25);
    }
  }

  async function loadEvents() {
    const data = await api("/api/nf/calendar");
    const el = $("#ev-list");
    if (!el) return;
    el.innerHTML = (data.events || []).map((e) => `
      <div class="item" data-id="${e.id}">
        <span class="emoji">${e.done ? "✅" : "📌"}</span>
        <div class="meta"><strong>${esc(e.title)}</strong><span>${e.date} ${e.time}</span></div>
      </div>`).join("");
    el.querySelectorAll(".item").forEach((item) => {
      item.addEventListener("click", async () => {
        await api("/api/nf/calendar/toggle", { method: "POST", body: JSON.stringify({ event_id: item.dataset.id }) });
        loadEvents();
      });
    });
  }
  $("#btn-add-ev")?.addEventListener("click", async () => {
    const title = $("#ev-title")?.value?.trim();
    const date = $("#ev-date")?.value;
    const time = $("#ev-time")?.value || "09:00";
    if (!title || !date) return;
    await api("/api/nf/calendar", { method: "POST", body: JSON.stringify({ title, date, time }) });
    $("#ev-title").value = "";
    loadEvents();
  });

  // ---- SITES ----
  async function loadSiteTpls() {
    const data = await api("/api/nf/site-templates");
    const el = $("#site-tpl-list");
    if (!el) return;
    el.innerHTML = (data.templates || []).map((t) => `
      <div class="item" data-id="${t.id}">
        <span class="emoji">📄</span>
        <div class="meta"><strong>${esc(t.name)}</strong><span>${esc(t.desc)} · ${(t.sections||[]).join(", ")}</span></div>
        <button class="btn" data-scaffold="${t.id}" style="font-size:.78rem">Baixar HTML</button>
      </div>`).join("");
    el.querySelectorAll("[data-scaffold]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const d = await api("/api/nf/site-scaffold/" + btn.dataset.scaffold);
        if (!d.ok) return alert(d.error || "Erro");
        const blob = new Blob([d.html], { type: "text/html" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = (btn.dataset.scaffold || "site") + ".html";
        a.click();
        playTone(523, "sine", 0.15);
      });
    });
  }

  // ---- SPRITES ----
  async function loadSpritesMini() {
    const data = await api("/api/nf/sprites");
    const el = $("#sprite-list-mini");
    if (!el) return;
    el.innerHTML = (data.sprites || []).length
      ? (data.sprites || []).map((s) => `
        <div class="item"><span class="emoji">🎨</span>
        <div class="meta"><strong>${esc(s.name)}</strong><span>${s.size}×${s.size}</span></div></div>`).join("")
      : '<p class="muted small">Nenhum sprite salvo. Abra o editor!</p>';
  }

  // ---- PROFILE ----
  async function loadProgress() {
    const data = await api("/api/nf/progress");
    const p = data.progress || {};
    const el = $("#progress-panel");
    if (!el) return;
    const pct = Math.min(100, ((p.xp_in_level || (p.xp % 300)) / 300) * 100);
    el.innerHTML = `
      <div class="stat"><span>Nível</span><strong>${p.level||1}</strong></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
      <div class="stat"><span>XP</span><strong>${p.xp||0} (faltam ${p.xp_to_next||300})</strong></div>
      <div class="stat"><span>🔥 Sequência</span><strong>${p.streak_days||0} dias</strong></div>
      <div class="stat"><span>XP hoje</span><strong>${p.daily_xp||0}</strong></div>
      <div class="stat"><span>Jogos criados</span><strong>${p.games_created||0}</strong></div>
      <div class="stat"><span>Jogos jogados</span><strong>${p.games_played||0}</strong></div>
      <div class="stat"><span>Exercícios</span><strong>${p.exercises_done||0}</strong></div>
      <div class="stat"><span>Flashcards</span><strong>${p.flashcards_reviewed||0}</strong></div>
      <div class="stat"><span>Quizzes</span><strong>${p.quizzes_done||0}</strong></div>
      <div class="stat"><span>Sprites</span><strong>${p.sprites_saved||0}</strong></div>`;
    const fav = $("#fav-list");
    if (fav) {
      const list = p.favorites || [];
      fav.innerHTML = list.length
        ? list.map((f) => `<div class="item"><span class="emoji">⭐</span><div class="meta"><strong>${esc(f.title||f.id)}</strong><span>${esc(f.type)}</span></div></div>`).join("")
        : '<p class="muted small">Nenhum favorito ainda.</p>';
    }
  }
  async function loadAchievements() {
    const data = await api("/api/nf/achievements");
    const el = $("#ach-list");
    if (!el) return;
    el.innerHTML = (data.achievements || []).map((a) => `
      <div class="ach ${a.unlocked ? "unlocked" : ""}">
        <span class="ico">${a.icon}</span>
        <strong>${esc(a.name)}</strong>
        <span>${esc(a.desc)}</span>
      </div>`).join("");
  }

  // Init
  loadTemplates();
  loadAssets("");
  loadRanking();
  loadSounds();
  loadGuided();
  loadDaily();
  loadSiteTpls();
})();
