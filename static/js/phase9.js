(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function toast(msg) {
    const t = $('#p9toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(t._tm);
    t._tm = setTimeout(() => t.classList.add('hidden'), 3200);
  }

  async function api(url, opts = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      credentials: 'same-origin',
      ...opts,
    });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
    return data;
  }

  let state = { overview: null, algo: null, step: 0, playing: false, timer: null, mentorStage: 'pergunta', dbgId: null, hintLevel: 1 };

  function tabs() {
    $$('#tabs button').forEach((b) => {
      b.onclick = () => {
        $$('#tabs button').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        $$('[data-panel]').forEach((p) => p.classList.toggle('active', p.dataset.panel === b.dataset.tab));
      };
    });
  }

  function renderModes() {
    const bar = $('#modeBar');
    const modes = state.overview?.modes || [];
    const cur = state.overview?.mode?.id;
    bar.innerHTML = modes.map((m) =>
      `<button data-mode="${esc(m.id)}" class="${m.id === cur ? 'active' : ''}">${esc(m.icon)} ${esc(m.title)}</button>`
    ).join('');
    $$('[data-mode]').forEach((b) => {
      b.onclick = async () => {
        try {
          await api('/api/cyber/phase9/mode', { method: 'POST', body: JSON.stringify({ mode: b.dataset.mode }) });
          await load();
          toast('Modo atualizado: ' + b.dataset.mode);
        } catch (e) { toast(e.message); }
      };
    });
  }

  function renderDash() {
    const d = state.overview;
    $('#dashCards').innerHTML = (d.dashboard || []).map((c) =>
      `<article class="card"><h3>${esc(c.icon)} ${esc(c.title)}</h3><p class="muted">${esc(c.id)}</p></article>`
    ).join('');
    $('#trackList').innerHTML = (d.track || []).map((t) => `<li>${esc(t.order)}. ${esc(t.title)}</li>`).join('');
  }

  async function loadDailyWeekly() {
    try {
      const day = await api('/api/cyber/phase9/daily');
      $('#dailyBox').innerHTML = `<strong>${esc(day.title)}</strong><p>${esc((day.tasks || []).filter(Boolean).join(' · '))}</p><p class="muted">Meta: ${esc(day.goal || '')}</p>`;
    } catch (e) { $('#dailyBox').textContent = e.message; }
    try {
      const w = await api('/api/cyber/phase9/weekly');
      $('#weeklyBox').innerHTML = `<strong>${esc(w.title)}</strong><ul>${(w.tasks || []).map((t) => `<li>${esc(t)}</li>`).join('')}</ul>`;
    } catch (e) { $('#weeklyBox').textContent = e.message; }
  }

  function renderLabs() {
    const labs = state.overview?.labs || [];
    $('#labsGrid').innerHTML = labs.map((l) =>
      `<article class="card"><h3>${esc(l.icon)} ${esc(l.title)}</h3><p class="muted">${esc(l.desc)}</p>
       <button class="btn primary" data-lab="${esc(l.id)}">Abrir</button></article>`
    ).join('');
    $$('[data-lab]').forEach((b) => {
      b.onclick = async () => {
        try {
          const d = await api('/api/cyber/phase9/labs/' + encodeURIComponent(b.dataset.lab));
          const box = $('#labDetail');
          box.classList.remove('hidden');
          box.innerHTML = `<h3>${esc(d.icon || '')} ${esc(d.title)}</h3><p>${esc(d.desc)}</p>
            ${(d.items || []).map((i) => `<span class="p9-chip">${esc(i)}</span>`).join('')}
            ${(d.challenges || []).map((c) => `<div class="muted" style="margin-top:8px"><b>${esc(c.title)}</b> — ${esc(c.error)}</div>`).join('')}`;
        } catch (e) { toast(e.message); }
      };
    });
  }

  function setupAlgo() {
    const demos = ['linear_search', 'binary_search', 'bubble_sort', 'insertion_sort', 'selection_sort', 'recursion', 'bfs', 'dfs'];
    $('#algoSelect').innerHTML = demos.map((id) => `<option value="${id}">${id}</option>`).join('');
    $('#algoStart').onclick = () => runAlgo(true);
    $('#algoPause').onclick = () => { state.playing = false; clearInterval(state.timer); };
    $('#algoStep').onclick = () => stepAlgo();
    $('#algoReset').onclick = () => { state.playing = false; clearInterval(state.timer); state.step = 0; paintAlgo(); };
    const ds = ['array', 'stack', 'queue', 'linked_list', 'tree', 'graph', 'hash_table'];
    $('#dsButtons').innerHTML = ds.map((id) => `<button class="btn" data-ds="${id}">${id}</button>`).join('');
    $$('[data-ds]').forEach((b) => {
      b.onclick = async () => {
        try {
          const d = await api('/api/cyber/phase9/datastructure/' + b.dataset.ds);
          $('#dsState').textContent = JSON.stringify(d, null, 2);
        } catch (e) { toast(e.message); }
      };
    });
    api('/api/cyber/phase9/architecture').then((d) => {
      $('#archView').innerHTML = `<div class="p9-flow">${(d.layers || []).map((l) => `<span title="${esc(l.resp)}">${esc(l.title)}</span>`).join('<i>→</i>')}</div>
        <p class="muted">${esc(d.flow || '')}</p>`;
    }).catch(() => {});
    api('/api/cyber/phase9/network-dns').then((d) => {
      $('#netView').innerHTML = `<p><b>Rede:</b> ${(d.network || []).join(' → ')}</p>
        <p><b>DNS:</b> ${(d.dns || []).join(' → ')}</p>
        <p class="muted">${esc(d.explain?.network || '')}</p>`;
    }).catch(() => {});
  }

  async function runAlgo(fromStart) {
    const id = $('#algoSelect').value;
    try {
      state.algo = await api('/api/cyber/phase9/algorithm/' + encodeURIComponent(id));
      if (fromStart) state.step = 0;
      state.playing = true;
      paintAlgo();
      clearInterval(state.timer);
      state.timer = setInterval(() => {
        if (!state.playing) return;
        if (state.step >= (state.algo.steps || []).length - 1) { state.playing = false; clearInterval(state.timer); return; }
        state.step++;
        paintAlgo();
      }, 900);
    } catch (e) { toast(e.message); }
  }

  function stepAlgo() {
    if (!state.algo) return runAlgo(true);
    if (state.step < (state.algo.steps || []).length - 1) state.step++;
    paintAlgo();
  }

  function paintAlgo() {
    const a = state.algo;
    if (!a) return;
    $('#algoMeta').textContent = `${a.title || ''} · ${a.complexity || ''} · ${a.desc || ''}`;
    const steps = a.steps || [];
    const cur = steps[state.step] || {};
    $('#algoMsg').textContent = cur.msg || a.desc || '';
    let arr = cur.arr || a.input;
    if (!Array.isArray(arr)) {
      if (cur.visited) arr = cur.visited;
      else if (Array.isArray(a.input)) arr = a.input;
      else arr = [1, 2, 3, 4, 5];
    }
    const max = Math.max(...arr.map(Number).filter((n) => !Number.isNaN(n)), 1);
    const hi = cur.i ?? cur.mid;
    $('#algoBars').innerHTML = arr.map((v, i) => {
      const n = Number(v);
      const h = Number.isNaN(n) ? 40 : Math.max(12, (n / max) * 100);
      const cls = i === hi ? 'hl' : (state.step >= steps.length - 1 ? 'done' : '');
      return `<span class="${cls}" style="height:${h}%">${esc(v)}</span>`;
    }).join('');
  }

  async function loadDebug() {
    try {
      const lab = await api('/api/cyber/phase9/labs/debug');
      const list = lab.challenges || [];
      $('#debugList').innerHTML = list.map((c) =>
        `<article class="card"><h3>${esc(c.title)}</h3><p class="muted">${esc(c.error)}</p>
         <button class="btn primary" data-dbg="${esc(c.id)}">Abrir desafio</button></article>`
      ).join('');
      $$('[data-dbg]').forEach((b) => {
        b.onclick = async () => {
          try {
            const d = await api('/api/cyber/phase9/debug/' + b.dataset.dbg);
            state.dbgId = d.id;
            state.hintLevel = 1;
            $('#debugDetail').classList.remove('hidden');
            $('#dbgTitle').textContent = d.title;
            $('#dbgError').textContent = d.error + ' · ' + (d.language || '');
            $('#dbgBroken').textContent = d.broken || '';
            $('#dbgHintBox').textContent = '';
            $('#dbgFixed').classList.add('hidden');
            $('#dbgFixed').textContent = '';
          } catch (e) { toast(e.message); }
        };
      });
    } catch (e) { $('#debugList').innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
  }

  $('#dbgHint')?.addEventListener('click', async () => {
    if (!state.dbgId) return;
    try {
      const d = await api('/api/cyber/phase9/debug/' + state.dbgId + '/hint', {
        method: 'POST', body: JSON.stringify({ level: state.hintLevel }),
      });
      $('#dbgHintBox').textContent = `Nível ${d.level}: ${d.hint}`;
      state.hintLevel = Math.min(3, state.hintLevel + 1);
    } catch (e) { toast(e.message); }
  });

  $('#dbgReveal')?.addEventListener('click', async () => {
    if (!state.dbgId) return;
    try {
      const d = await api('/api/cyber/phase9/debug/' + state.dbgId + '/reveal', { method: 'POST', body: '{}' });
      $('#dbgFixed').classList.remove('hidden');
      $('#dbgFixed').textContent = d.fixed + '\n\n// ' + (d.explain || '');
    } catch (e) { toast(e.message); }
  });

  function renderGames() {
    const games = state.overview?.edu_games || [];
    $('#gamesGrid').innerHTML = games.map((g) =>
      `<article class="card"><h3>${esc(g.icon)} ${esc(g.title)}</h3><p class="muted">${esc(g.desc)}</p>
       <div>${(g.concepts || []).map((c) => `<span class="p9-chip">${esc(c)}</span>`).join('')}</div>
       <button class="btn primary" data-game="${esc(g.id)}">Detalhes</button></article>`
    ).join('');
    $$('[data-game]').forEach((b) => {
      b.onclick = async () => {
        try {
          const d = await api('/api/cyber/phase9/games/' + b.dataset.game);
          const box = $('#gameDetail');
          box.classList.remove('hidden');
          box.innerHTML = `<h3>${esc(d.icon)} ${esc(d.title)}</h3><p>${esc(d.desc)}</p>
            <p><b>Conceitos:</b> ${(d.concepts || []).join(', ')}</p>
            ${d.commands ? `<p><b>Comandos:</b> ${d.commands.join(' · ')}</p>` : ''}
            <p class="muted">Jogo educacional — use junto com o Game Lab existente para implementar controles, colisão e pontuação.</p>`;
        } catch (e) { toast(e.message); }
      };
    });
  }

  $('#buildProject')?.addEventListener('click', async () => {
    try {
      const idea = $('#ideaInput').value;
      const d = await api('/api/cyber/phase9/project-builder', { method: 'POST', body: JSON.stringify({ idea }) });
      $('#projectOut').innerHTML = `
        <h4>Objetivo</h4><p>${esc(d.objetivo)}</p>
        <h4>Arquitetura</h4><ul>${(d.arquitetura || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
        <h4>Tarefas</h4><ol>${(d.tarefas || []).map((t) => `<li>${esc(t.title)}</li>`).join('')}</ol>
        <h4>Etapas</h4><div class="p9-flow">${(d.etapas || []).map((e) => `<span>${esc(e)}</span>`).join('<i>→</i>')}</div>
        <h4>Testes</h4><ul>${(d.testes || []).map((t) => `<li>${esc(t)}</li>`).join('')}</ul>
        <p class="muted">${esc(d.ensino)}</p>`;
    } catch (e) { toast(e.message); }
  });

  $('#mentorNext')?.addEventListener('click', async () => {
    try {
      const d = await api('/api/cyber/phase9/mentor', {
        method: 'POST',
        body: JSON.stringify({ stage: state.mentorStage, context: $('#mentorCtx').value }),
      });
      $('#mentorOut').innerHTML = `<strong>${esc(d.stage.toUpperCase())}</strong><p>${esc(d.message)}</p>`;
      state.mentorStage = d.next || 'solucao';
    } catch (e) { toast(e.message); }
  });
  $('#mentorReset')?.addEventListener('click', () => {
    state.mentorStage = 'pergunta';
    $('#mentorOut').textContent = 'Reiniciado. Clique em Próxima etapa.';
  });

  $('#revRun')?.addEventListener('click', async () => {
    try {
      const d = await api('/api/cyber/phase9/code-review', {
        method: 'POST',
        body: JSON.stringify({ code: $('#revCode').value, language: $('#revLang').value }),
      });
      $('#revOut').innerHTML = `<p><b>Score:</b> ${d.score}/100</p>
        <ul>${(d.issues || []).map((i) => `<li><span class="p9-chip">${esc(i.severity)}</span> ${esc(i.msg)}</li>`).join('')}</ul>
        <p class="muted">${esc(d.refactor_hint)}</p>`;
    } catch (e) { toast(e.message); }
  });

  $('#searchBtn')?.addEventListener('click', async () => {
    try {
      const d = await api('/api/cyber/phase9/search?q=' + encodeURIComponent($('#searchQ').value));
      $('#searchOut').innerHTML = (d.results || []).map((r) =>
        `<article class="card"><h3>${esc(r.type)} · ${esc(r.title || r.id)}</h3><p class="muted">${esc(r.desc || '')}</p></article>`
      ).join('') || '<p class="muted">Nenhum resultado.</p>';
    } catch (e) { toast(e.message); }
  });

  async function load() {
    state.overview = await api('/api/cyber/phase9/overview');
    renderModes();
    renderDash();
    renderLabs();
    renderGames();
    await loadDailyWeekly();
  }

  tabs();
  setupAlgo();
  loadDebug();
  load().catch((e) => toast(e.message || 'Falha ao carregar Fase 9'));
})();
