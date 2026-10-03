/* Phase 10 Education Hub — client tools are real (no fake buttons). */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  async function api(url, opts = {}) {
    const headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
    if (opts.method && opts.method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-CSRF-Token"] = csrf();
    }
    const res = await fetch(url, Object.assign({}, opts, { headers, credentials: "same-origin" }));
    let data = null;
    try { data = await res.json(); } catch (_) { data = { error: "Resposta inválida do servidor" }; }
    if (!res.ok) {
      const err = new Error(data.error || data.message || ("HTTP " + res.status));
      err.data = data;
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function setTab(name) {
    $$(".edu-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    $$(".edu-panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
  }

  $$(".edu-tab").forEach(btn => btn.addEventListener("click", () => setTab(btn.dataset.tab)));

  let lessonsCache = {};
  let mentorStage = "pergunta";

  function friendlyError(e) {
    const msg = e.message || "Erro";
    if (e.status === 401) return "O que aconteceu: precisa de login para esta ação.\nPossível causa: sessão ausente.\nComo tentar: faça login e repita.";
    return "O que aconteceu: " + msg + "\nPossível causa: rede, permissão ou dados inválidos.\nComo tentar: verifique a conexão e tente novamente.";
  }

  async function loadOverview() {
    const o = await api("/api/cyber/phase10/overview");
    const stats = $("#edu-stats");
    stats.innerHTML = [
      ["Aulas", o.lesson_count],
      ["Labs", o.lab_count],
      ["Ferramentas", o.tool_count],
      ["Jogos edu", o.game_count],
    ].map(([l, v]) => '<div class="edu-stat"><b>' + esc(v) + '</b><span class="muted">' + esc(l) + "</span></div>").join("");
    $("#edu-continue").innerHTML = (o.sections || []).slice(0, 8).map(s =>
      '<button type="button" class="edu-chip" data-go="' + esc(s.id) + '">' + esc(s.icon || "") + " " + esc(s.title) + "</button>"
    ).join("");
    $$("#edu-continue .edu-chip").forEach(ch => ch.addEventListener("click", () => {
      const map = { trilhas: "tracks", aulas: "lessons", laboratorios: "labs", ferramentas: "tools", mapa: "map", skilltree: "skill", mentor: "mentor", desafios: "daily", cursos: "tracks", exercicios: "lessons", projetos: "daily", progresso: "overview" };
      setTab(map[ch.dataset.go] || "overview");
    }));
    const daily = await api("/api/cyber/phase10/daily-public");
    $("#edu-daily").innerHTML = "<strong>" + esc(daily.title) + "</strong><p>" + esc(daily.prompt) + '</p><span class="muted small">' + esc(daily.date) + " · " + esc(daily.track) + "</span>";
  }

  async function loadTracks() {
    const { tracks } = await api("/api/cyber/phase10/tracks");
    $("#edu-tracks").innerHTML = tracks.map((t, i) =>
      '<div class="step">' + esc(t.icon || "") + "<div>" + esc(t.title) + "</div></div>" + (i < tracks.length - 1 ? '<span class="arrow">→</span>' : "")
    ).join("");
  }

  async function loadLessonList() {
    const map = await api("/api/cyber/phase10/learning-map");
    const list = $("#edu-lesson-list");
    list.innerHTML = (map.nodes || []).map(n =>
      '<button type="button" data-id="' + esc(n.id) + '">' + esc(n.title) + ' <span class="muted small">' + esc(n.track || "") + "</span></button>"
    ).join("");
    list.querySelectorAll("button").forEach(b => b.addEventListener("click", () => openLesson(b.dataset.id, b)));
  }

  async function openLesson(id, btn) {
    $$("#edu-lesson-list button").forEach(b => b.classList.toggle("active", b === btn));
    const L = lessonsCache[id] || await api("/api/cyber/phase10/lesson/" + encodeURIComponent(id));
    lessonsCache[id] = L;
    const view = $("#edu-lesson-view");
    const sections = [
      ["O que é?", L.what],
      ["Para que serve?", L.purpose],
      ["Por que existe?", L.why],
      ["Como funciona?", L.how],
      ["Exemplo simples", L.simple_example],
      ["Exemplo real", L.real_example],
      ["Código", L.code],
      ["Linha a linha", (L.line_by_line || []).map((x, i) => (i + 1) + ". " + x).join("\n")],
      ["Erros comuns", (L.common_errors || []).map(x => "• " + x).join("\n")],
      ["Como testar", L.how_to_test],
      ["Exercício", L.exercise],
      ["Desafio", L.challenge],
      ["Mini projeto", L.mini_project],
      ["Próximo assunto", L.next],
    ];
    view.innerHTML = "<h2>" + esc(L.title) + '</h2><p class="muted small">Nível: ' + esc(L.level || "") + " · Trilha: " + esc(L.track || "") + "</p>" +
      sections.map(([t, b]) => b ? '<div class="section"><h3>' + esc(t) + "</h3><pre>" + esc(b) + "</pre></div>" : "").join("") +
      '<div class="edu-toolbar"><label>Explicar de outro jeito<select id="explain-style"><option value="cotidiano">Cotidiano</option><option value="jogo">Jogo</option><option value="visual">Visual</option><option value="tecnica">Técnica</option></select></label>' +
      '<button type="button" class="btn" id="explain-btn">EXPLICAR DE OUTRO JEITO</button></div><pre id="explain-out" class="edu-out" hidden></pre>';
    $("#explain-btn").onclick = async () => {
      try {
        const r = await api("/api/cyber/phase10/explain-another-way", {
          method: "POST",
          body: JSON.stringify({ lesson_id: id, style: $("#explain-style").value }),
        });
        const out = $("#explain-out");
        out.hidden = false;
        out.textContent = r.explanation || r.error || "";
      } catch (e) {
        $("#explain-out").hidden = false;
        $("#explain-out").textContent = friendlyError(e);
      }
    };
  }

  async function loadLabs() {
    const { labs } = await api("/api/cyber/phase10/labs");
    const box = $("#edu-labs");
    box.innerHTML = labs.map(l =>
      '<div class="edu-card" data-lab="' + esc(l.id) + '"><h3>' + esc(l.icon) + " " + esc(l.title) + "</h3><p>" + esc(l.desc) + "</p></div>"
    ).join("");
    box.querySelectorAll(".edu-card").forEach(c => c.addEventListener("click", () => openLab(c.dataset.lab, c.querySelector("h3").textContent)));
  }

  let algoSteps = [];
  let algoIdx = 0;
  let algoTimer = null;

  function setupAlgoLab() {
    const render = (step) => {
      const arr = step && step.array ? step.array : [];
      const vis = $("#algo-vis");
      vis.innerHTML = arr.map((v, i) => {
        let cls = "lab-bar";
        if (step && (i === step.i || i === step.j)) cls += step.type === "swap" ? " swap" : " active";
        return '<div class="' + cls + '" style="height:' + (20 + v * 8) + 'px">' + v + "</div>";
      }).join("");
      $("#algo-log").textContent = step ? (step.type + " " + JSON.stringify(step)) : "Pronto.";
    };
    const load = async () => {
      let data;
      try { data = JSON.parse($("#algo-data").value || "[]"); } catch (e) { data = [5, 2, 8, 1, 9, 3]; }
      const res = await api("/api/cyber/phase10/algorithm-steps", {
        method: "POST",
        body: JSON.stringify({ algo: $("#algo-sel").value, data: data }),
      });
      algoSteps = res.steps || [];
      algoIdx = 0;
      if (algoSteps[0]) render(algoSteps[0]);
    };
    $("#algo-run").onclick = async () => {
      try {
        await load();
        clearInterval(algoTimer);
        algoTimer = setInterval(() => {
          if (algoIdx >= algoSteps.length - 1) { clearInterval(algoTimer); return; }
          algoIdx++;
          render(algoSteps[algoIdx]);
        }, 450);
      } catch (e) { $("#algo-log").textContent = friendlyError(e); }
    };
    $("#algo-pause").onclick = () => clearInterval(algoTimer);
    $("#algo-step").onclick = () => {
      if (!algoSteps.length) return;
      algoIdx = Math.min(algoIdx + 1, algoSteps.length - 1);
      render(algoSteps[algoIdx]);
    };
    $("#algo-reset").onclick = () => { clearInterval(algoTimer); algoIdx = 0; if (algoSteps[0]) render(algoSteps[0]); };
  }

  function toolJSON() {
    return '<div class="tool-grid"><div><label>JSON<textarea id="json-ta" rows="10">{"hello":"jarvis","n":1}</textarea></label>' +
      '<div class="edu-toolbar"><button type="button" class="btn" id="json-fmt">Formatar</button>' +
      '<button type="button" class="btn ghost" id="json-val">Validar</button>' +
      '<button type="button" class="btn ghost" id="json-min">Minificar</button></div></div>' +
      '<div><pre id="json-out" class="edu-out">Resultado aqui</pre></div></div>';
  }
  function wireJSON() {
    const ta = () => $("#json-ta");
    $("#json-fmt").onclick = () => {
      try { $("#json-out").textContent = JSON.stringify(JSON.parse(ta().value), null, 2); }
      catch (e) { $("#json-out").textContent = "Inválido: " + e.message; }
    };
    $("#json-val").onclick = () => {
      try { JSON.parse(ta().value); $("#json-out").textContent = "JSON válido"; }
      catch (e) { $("#json-out").textContent = e.message; }
    };
    $("#json-min").onclick = () => {
      try { $("#json-out").textContent = JSON.stringify(JSON.parse(ta().value)); }
      catch (e) { $("#json-out").textContent = "Inválido: " + e.message; }
    };
  }
  function toolRegex() {
    return '<div class="tool-grid"><div><label>Padrão <input id="re-pat" value="\\\\b\\\\w+@\\\\w+\\\\.\\\\w+\\\\b"></label>' +
      '<label>Flags <input id="re-flags" value="g"></label>' +
      '<label>Texto <textarea id="re-text" rows="6">contato: a@b.com e test@jarvis.dev</textarea></label>' +
      '<button type="button" class="btn" id="re-run">Testar</button></div><pre id="re-out" class="edu-out"></pre></div>';
  }
  function wireRegex() {
    $("#re-run").onclick = () => {
      try {
        const re = new RegExp($("#re-pat").value, $("#re-flags").value);
        const text = $("#re-text").value;
        const matches = [];
        let m;
        const r2 = new RegExp(re.source, re.flags.includes("g") ? re.flags : re.flags + "g");
        while ((m = r2.exec(text)) !== null) { matches.push(m[0]); if (!r2.global) break; }
        $("#re-out").textContent = matches.length ? ("Matches:\n" + matches.join("\n")) : "Nenhum match";
      } catch (e) { $("#re-out").textContent = "Erro na regex: " + e.message; }
    };
  }

  function openLab(id, title) {
    const ws = $("#lab-workspace");
    ws.hidden = false;
    $("#lab-title").textContent = title || id;
    const body = $("#lab-body");
    if (id === "algorithm" || id === "datastruct") {
      body.innerHTML = '<div class="tool-grid"><div><label>Algoritmo<select id="algo-sel">' +
        '<option value="bubble">Bubble Sort</option><option value="selection">Selection Sort</option>' +
        '<option value="insertion">Insertion Sort</option><option value="linear">Linear Search</option>' +
        '<option value="binary">Binary Search</option></select></label>' +
        '<label>Dados (JSON array)<input id="algo-data" value="[5,2,8,1,9,3]"></label>' +
        '<div class="edu-toolbar"><button type="button" class="btn" id="algo-run">Iniciar</button>' +
        '<button type="button" class="btn ghost" id="algo-pause">Pausar</button>' +
        '<button type="button" class="btn ghost" id="algo-step">Avançar</button>' +
        '<button type="button" class="btn ghost" id="algo-reset">Reiniciar</button></div></div>' +
        '<div><div class="lab-vis" id="algo-vis"></div><pre id="algo-log" class="edu-out">Pronto.</pre></div></div>';
      setupAlgoLab();
    } else if (id === "json") { body.innerHTML = toolJSON(); wireJSON(); }
    else if (id === "regex") { body.innerHTML = toolRegex(); wireRegex(); }
    else if (id === "http" || id === "api") {
      body.innerHTML = '<pre class="edu-out">CLIENT → REQUEST → API → BACKEND → DATABASE → RESPONSE\n\nGET POST PUT PATCH DELETE\n200 201 400 401 404 500</pre>';
    } else if (id === "architecture") {
      body.innerHTML = '<pre class="edu-out">FRONTEND → API → BACKEND → DATABASE</pre>';
    } else if (id === "network") {
      body.innerHTML = '<pre class="edu-out">COMPUTADOR → ROTEADOR → SERVIDOR\nDOMÍNIO → DNS → IP → SERVIDOR</pre>';
    } else if (id === "debug") {
      body.innerHTML = '<p>Fluxo: EXECUTAR → VER ERRO → LOCALIZAR → ENTENDER → CORRIGIR → TESTAR</p>' +
        '<pre class="edu-out">function sum(a, b) {\n  return a + b\n}\nconsole.log(sum(2, 3);\n</pre>' +
        '<button type="button" class="btn" id="debug-hint">Pista progressiva</button><pre class="edu-out" id="debug-out" hidden></pre>';
      let step = 0;
      const hints = [
        "Olhe a última linha: os parênteses de console.log estão balanceados?",
        "Falta fechar o ) da chamada console.log.",
        "Correto: console.log(sum(2, 3));",
      ];
      $("#debug-hint").onclick = () => {
        $("#debug-out").hidden = false;
        $("#debug-out").textContent = hints[Math.min(step, hints.length - 1)];
        step++;
      };
    } else {
      body.innerHTML = '<p class="muted">Lab ' + esc(id) + '. Use também Programming Universe / Phase 9.</p>' +
        '<p><a class="btn" href="/cyber/programming">Programming Universe</a> <a class="btn ghost" href="/cyber/phase9">Fase 9</a></p>';
    }
  }

  $("#lab-close") && $("#lab-close").addEventListener("click", () => { $("#lab-workspace").hidden = true; });

  async function loadTools() {
    const { tools } = await api("/api/cyber/phase10/tools");
    const box = $("#edu-tools");
    box.innerHTML = tools.map(t =>
      '<div class="edu-card" data-tool="' + esc(t.id) + '"><h3>' + esc(t.icon) + " " + esc(t.title) + "</h3></div>"
    ).join("");
    box.querySelectorAll(".edu-card").forEach(c => c.addEventListener("click", () => openTool(c.dataset.tool, c.querySelector("h3").textContent)));
  }

  function openTool(id, title) {
    const ws = $("#tool-workspace");
    ws.hidden = false;
    $("#tool-title").textContent = title || id;
    const body = $("#tool-body");
    if (id === "json-formatter" || id === "json-validator") { body.innerHTML = toolJSON(); wireJSON(); }
    else if (id === "regex-tester") { body.innerHTML = toolRegex(); wireRegex(); }
    else if (id === "base64") {
      body.innerHTML = '<div class="tool-grid"><div><label>Texto <textarea id="b64-in" rows="4">JARVIS</textarea></label>' +
        '<div class="edu-toolbar"><button type="button" class="btn" id="b64-enc">Encode</button>' +
        '<button type="button" class="btn ghost" id="b64-dec">Decode</button></div></div><pre id="b64-out" class="edu-out"></pre></div>';
      $("#b64-enc").onclick = async () => {
        try {
          const r = await api("/api/cyber/phase10/base64", { method: "POST", body: JSON.stringify({ text: $("#b64-in").value, mode: "encode" }) });
          $("#b64-out").textContent = r.result || r.error;
        } catch (e) { $("#b64-out").textContent = friendlyError(e); }
      };
      $("#b64-dec").onclick = async () => {
        try {
          const r = await api("/api/cyber/phase10/base64", { method: "POST", body: JSON.stringify({ b64: $("#b64-in").value, mode: "decode" }) });
          $("#b64-out").textContent = r.result || r.error;
        } catch (e) { $("#b64-out").textContent = friendlyError(e); }
      };
    } else if (id === "hash") {
      body.innerHTML = '<div class="tool-grid"><div><label>Texto <textarea id="hash-in" rows="3">senha-demo</textarea></label>' +
        '<label>Algoritmo <select id="hash-algo"><option>sha256</option><option>sha1</option><option>md5</option><option>all</option></select></label>' +
        '<button type="button" class="btn" id="hash-go">Gerar hash</button></div><pre id="hash-out" class="edu-out"></pre></div>';
      $("#hash-go").onclick = async () => {
        try {
          const r = await api("/api/cyber/phase10/hash-demo", { method: "POST", body: JSON.stringify({ text: $("#hash-in").value, algo: $("#hash-algo").value }) });
          $("#hash-out").textContent = JSON.stringify(r, null, 2);
        } catch (e) { $("#hash-out").textContent = friendlyError(e); }
      };
    } else if (id === "timestamp") {
      body.innerHTML = '<div class="tool-grid"><div><button type="button" class="btn" id="ts-now">Agora</button>' +
        '<label>Unix <input id="ts-unix" type="number"></label>' +
        '<button type="button" class="btn ghost" id="ts-from">Unix → Data</button></div><pre id="ts-out" class="edu-out"></pre></div>';
      $("#ts-now").onclick = () => {
        const n = Date.now();
        $("#ts-unix").value = Math.floor(n / 1000);
        $("#ts-out").textContent = new Date(n).toISOString() + "\nlocal: " + new Date(n).toString();
      };
      $("#ts-from").onclick = () => {
        const u = Number($("#ts-unix").value);
        $("#ts-out").textContent = new Date(u * 1000).toISOString();
      };
    } else if (id === "color") {
      body.innerHTML = '<div class="tool-grid"><div><label>HEX <input id="color-hex" value="#2ec5ff"></label>' +
        '<button type="button" class="btn" id="color-go">Converter</button></div><pre id="color-out" class="edu-out"></pre></div>';
      $("#color-go").onclick = () => {
        let h = $("#color-hex").value.trim().replace("#", "");
        if (h.length === 3) h = h.split("").map(c => c + c).join("");
        if (!/^[0-9a-fA-F]{6}$/.test(h)) { $("#color-out").textContent = "HEX inválido"; return; }
        const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
        $("#color-out").textContent = "rgb(" + r + ", " + g + ", " + b + ")\nrgba(" + r + ", " + g + ", " + b + ", 1)";
      };
    } else if (id === "markdown-preview") {
      body.innerHTML = '<div class="tool-grid"><div><label>Markdown <textarea id="md-in" rows="8"># Título\n\n**negrito** e codigo\n\n- item</textarea></label>' +
        '<button type="button" class="btn" id="md-go">Preview</button></div><div id="md-out" class="edu-out"></div></div>';
      $("#md-go").onclick = () => {
        let t = esc($("#md-in").value);
        t = t.replace(/^### (.*)$/gm, "<h3>$1</h3>").replace(/^## (.*)$/gm, "<h2>$1</h2>").replace(/^# (.*)$/gm, "<h1>$1</h1>");
        t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        t = t.replace(/^- (.*)$/gm, "<li>$1</li>");
        t = t.replace(/\n/g, "<br>");
        $("#md-out").innerHTML = t;
      };
    } else if (id === "html-preview") {
      body.innerHTML = '<div class="tool-grid"><div><label>HTML <textarea id="html-in" rows="8"><h1>Olá</h1><p>JARVIS</p></textarea></label>' +
        '<button type="button" class="btn" id="html-go">Preview sandbox</button></div>' +
        '<iframe id="html-out" sandbox="" style="width:100%;min-height:220px;background:#fff;border-radius:10px;border:1px solid #1e3a5f"></iframe></div>';
      $("#html-go").onclick = () => {
        const doc = $("#html-out").contentDocument;
        doc.open(); doc.write($("#html-in").value); doc.close();
      };
    } else if (id === "unit") {
      body.innerHTML = '<div class="tool-grid"><div><label>Valor <input id="unit-v" type="number" value="1"></label>' +
        '<label>De <select id="unit-from"><option>km</option><option>m</option><option>mi</option></select></label>' +
        '<label>Para <select id="unit-to"><option>m</option><option>km</option><option>mi</option></select></label>' +
        '<button type="button" class="btn" id="unit-go">Converter</button></div><pre id="unit-out" class="edu-out"></pre></div>';
      const toM = { km: 1000, m: 1, mi: 1609.344 };
      $("#unit-go").onclick = () => {
        const v = Number($("#unit-v").value);
        const meters = v * toM[$("#unit-from").value];
        $("#unit-out").textContent = String(meters / toM[$("#unit-to").value]);
      };
    } else if (id === "js-playground") {
      body.innerHTML = '<div class="tool-grid"><div><label>JavaScript<textarea id="js-in" rows="8">const x = 2 + 2;\nconsole.log(x);</textarea></label>' +
        '<button type="button" class="btn" id="js-run">Executar</button></div><pre id="js-out" class="edu-out"></pre></div>';
      $("#js-run").onclick = () => {
        const logs = [];
        const fake = { log: function () { logs.push(Array.prototype.slice.call(arguments).join(" ")); } };
        try {
          const fn = new Function("console", $("#js-in").value);
          fn(fake);
          $("#js-out").textContent = logs.join("\n") || "(sem saída)";
        } catch (e) { $("#js-out").textContent = "Erro: " + e.message; }
      };
    } else if (id === "code-diff") {
      body.innerHTML = '<div class="tool-grid"><label>A <textarea id="diff-a" rows="6">um\ndois\ntres</textarea></label>' +
        '<label>B <textarea id="diff-b" rows="6">um\ndois!\ntres</textarea></label></div>' +
        '<button type="button" class="btn" id="diff-go">Diff</button><pre id="diff-out" class="edu-out"></pre>';
      $("#diff-go").onclick = () => {
        const a = $("#diff-a").value.split("\n");
        const b = $("#diff-b").value.split("\n");
        const n = Math.max(a.length, b.length);
        const lines = [];
        for (let i = 0; i < n; i++) {
          if (a[i] === b[i]) lines.push("  " + (a[i] || ""));
          else {
            if (a[i] !== undefined) lines.push("- " + a[i]);
            if (b[i] !== undefined) lines.push("+ " + b[i]);
          }
        }
        $("#diff-out").textContent = lines.join("\n");
      };
    } else if (id === "ascii") {
      body.innerHTML = '<label>Texto <input id="ascii-in" value="JARVIS"></label>' +
        '<button type="button" class="btn" id="ascii-go">Códigos</button><pre id="ascii-out" class="edu-out"></pre>';
      $("#ascii-go").onclick = () => {
        const s = $("#ascii-in").value;
        $("#ascii-out").textContent = Array.prototype.map.call(s, function (c) { return c + " → " + c.charCodeAt(0); }).join("\n");
      };
    } else {
      body.innerHTML = '<p class="muted">Ferramenta ' + esc(id) + '. Demais demos no Programming Universe.</p>' +
        '<p><a href="/cyber/programming">Programming Universe</a></p>';
    }
  }

  $("#tool-close") && $("#tool-close").addEventListener("click", () => { $("#tool-workspace").hidden = true; });

  async function loadMap() {
    const map = await api("/api/cyber/phase10/learning-map");
    $("#edu-map").innerHTML = (map.nodes || []).map(n => {
      const ins = (map.edges || []).filter(e => e.to === n.id).map(e => e.from);
      return '<div class="edu-node"><strong>' + esc(n.title) + '</strong><div class="muted small">' +
        esc(n.track || "") + (ins.length ? " · requer: " + ins.map(esc).join(", ") : "") + "</div></div>";
    }).join("");
  }

  function renderSkill(node, depth) {
    depth = depth || 0;
    if (!node) return "";
    if (node.children && node.children.length) {
      return "<details " + (depth < 2 ? "open" : "") + "><summary>" + esc(node.title) + "</summary>" +
        node.children.map(function (c) { return renderSkill(c, depth + 1); }).join("") + "</details>";
    }
    return '<div class="edu-node" style="margin-left:' + (depth * 8) + 'px">' + esc(node.title) +
      (node.lesson ? ' <button type="button" class="edu-chip" data-lesson="' + esc(node.lesson) + '">abrir aula</button>' : "") + "</div>";
  }

  async function loadSkill() {
    const tree = await api("/api/cyber/phase10/skill-tree");
    $("#edu-skill").innerHTML = renderSkill(tree);
    $$("#edu-skill [data-lesson]").forEach(b => b.addEventListener("click", () => {
      setTab("lessons");
      openLesson(b.dataset.lesson);
    }));
  }

  async function loadDaily() {
    const d = await api("/api/cyber/phase10/daily-public");
    const w = await api("/api/cyber/phase10/weekly-public");
    $("#edu-daily-full").innerHTML = "<strong>" + esc(d.title) + "</strong><p>" + esc(d.prompt) + "</p>";
    $("#edu-weekly").innerHTML = "<strong>" + esc(w.title) + "</strong><p>" + esc(w.prompt) + '</p><span class="muted small">' + esc(w.week) + "</span>";
  }

  $("#mentor-go") && $("#mentor-go").addEventListener("click", async () => {
    mentorStage = "pista";
    try {
      const r = await api("/api/cyber/phase10/mentor", {
        method: "POST",
        body: JSON.stringify({ question: $("#mentor-q").value, attempt: $("#mentor-attempt").value, stage: mentorStage }),
      });
      mentorStage = r.next_stage || mentorStage;
      $("#mentor-out").textContent = JSON.stringify(r, null, 2);
    } catch (e) { $("#mentor-out").textContent = friendlyError(e); }
  });
  $("#mentor-next") && $("#mentor-next").addEventListener("click", async () => {
    try {
      const r = await api("/api/cyber/phase10/mentor", {
        method: "POST",
        body: JSON.stringify({ question: $("#mentor-q").value, attempt: $("#mentor-attempt").value, stage: mentorStage }),
      });
      mentorStage = r.next_stage || "solucao";
      $("#mentor-out").textContent = JSON.stringify(r, null, 2);
    } catch (e) { $("#mentor-out").textContent = friendlyError(e); }
  });

  $("#edu-search-btn") && $("#edu-search-btn").addEventListener("click", async () => {
    const q = $("#edu-search").value.trim();
    if (!q) return;
    try {
      const r = await api("/api/cyber/phase10/search-public?q=" + encodeURIComponent(q));
      setTab("overview");
      $("#edu-continue").innerHTML = (r.results || []).map(x =>
        '<button type="button" class="edu-chip" data-type="' + esc(x.type) + '" data-id="' + esc(x.id) + '">' + esc(x.type) + ": " + esc(x.title) + "</button>"
      ).join("") || "<span class='muted'>Nada encontrado</span>";
      $$("#edu-continue .edu-chip").forEach(ch => ch.addEventListener("click", () => {
        if (ch.dataset.type === "lesson") { setTab("lessons"); openLesson(ch.dataset.id); }
        else if (ch.dataset.type === "lab") { setTab("labs"); openLab(ch.dataset.id, ch.textContent); }
        else if (ch.dataset.type === "tool") { setTab("tools"); openTool(ch.dataset.id, ch.textContent); }
      }));
    } catch (e) { alert(friendlyError(e)); }
  });

  async function boot() {
    try {
      await loadOverview();
      await Promise.all([loadTracks(), loadLessonList(), loadLabs(), loadTools(), loadMap(), loadSkill(), loadDaily()]);
    } catch (e) {
      console.error(e);
      const root = $("#edu-root");
      if (root) {
        const banner = document.createElement("div");
        banner.className = "card";
        banner.innerHTML = "<strong>Não foi possível carregar tudo.</strong><pre class=\"edu-out\">" + esc(friendlyError(e)) + "</pre>";
        root.prepend(banner);
      }
    }
  }

  if ($("#edu-root")) boot();
})();
