// Jarvis ⇄ Tool Router.
// Recebe a frase do usuário; se ela é um pedido de ferramenta (auditar,
// DNS, TLS, portas, logs, segredos…), executa de verdade no backend
// (/api/jarvis/run, NDJSON) e mostra explicação → progresso → resultado.
// Se não for, devolve false e o chat normal segue como sempre.
//
// SEGURANÇA: todo texto que veio do alvo (headers, cookies, banners) entra
// no DOM via textContent — nunca innerHTML —, senão um servidor hostil
// poderia injetar HTML/JS no chat.
(function () {
  "use strict";

  const SEV_LABEL = { critical: "crítico", high: "alto", medium: "médio", low: "baixo", info: "info" };
  const SEV_ORDER = ["critical", "high", "medium", "low", "info"];

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res;
  }

  // Lê NDJSON em streaming; chama onEvent(obj) por linha.
  async function readNDJSON(res, onEvent) {
    if (!res.body || !res.body.getReader) {
      (await res.text()).split("\n").filter(Boolean).forEach((l) => { try { onEvent(JSON.parse(l)); } catch (e) {} });
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line) { try { onEvent(JSON.parse(line)); } catch (e) {} }
      }
    }
    if (buf.trim()) { try { onEvent(JSON.parse(buf)); } catch (e) {} }
  }

  function buildCard(chatEl, explain) {
    const row = el("div", "bubble-row assistant");
    const card = el("div", "tool-card");
    const head = el("div", "tool-card-head");
    head.appendChild(el("span", "tool-card-dot"));
    head.appendChild(el("span", "tool-card-title", explain || "Executando…"));
    const bar = el("div", "tool-progress");
    const fill = el("div", "tool-progress-fill");
    bar.appendChild(fill);
    const steps = el("div", "tool-steps");
    const out = el("div", "tool-out");
    card.append(head, bar, steps, out);
    row.appendChild(card);
    chatEl.appendChild(row);
    chatEl.scrollTop = chatEl.scrollHeight;
    return { row, card, head, fill, steps, out, chatEl };
  }

  function addStep(ui, text, state) {
    const s = el("div", "tool-step " + (state || "run"));
    s.appendChild(el("span", "tool-step-mark", state === "ok" ? "✔" : state === "err" ? "✘" : "•"));
    s.appendChild(el("span", "tool-step-text", text));
    ui.steps.appendChild(s);
    ui.chatEl.scrollTop = ui.chatEl.scrollHeight;
    return s;
  }

  function setStepState(stepEl, state, text) {
    stepEl.className = "tool-step " + state;
    stepEl.firstChild.textContent = state === "ok" ? "✔" : state === "err" ? "✘" : "•";
    if (text) stepEl.lastChild.textContent = text;
  }

  function renderFindings(ui, findings, score, risk) {
    if (!findings || !findings.length) {
      ui.out.appendChild(el("div", "tool-ok", "Nenhum problema encontrado pelas verificações executadas."));
      return;
    }
    const counts = {};
    findings.forEach((f) => { counts[f.severity] = (counts[f.severity] || 0) + 1; });
    const chips = el("div", "tool-chips");
    if (score != null) chips.appendChild(el("span", "tool-chip risk " + (risk || ""), `risco ${risk || ""} · ${score}/100`));
    SEV_ORDER.forEach((s) => { if (counts[s]) chips.appendChild(el("span", "tool-chip sev-" + s, `${counts[s]} ${SEV_LABEL[s]}`)); });
    ui.out.appendChild(chips);
    const sorted = findings.slice().sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
    sorted.slice(0, 12).forEach((f) => {
      const d = el("details", "tool-finding sev-" + f.severity);
      const sum = el("summary");
      sum.appendChild(el("span", "tool-sev", SEV_LABEL[f.severity]));
      sum.appendChild(el("span", "tool-find-title", f.title));
      d.appendChild(sum);
      [["Evidência", f.evidence], ["Impacto", f.impact], ["Correção", f.fix]].forEach(([k, v]) => {
        if (!v) return;
        const p = el("div", "tool-find-row");
        p.appendChild(el("b", null, k + ": "));
        p.appendChild(document.createTextNode(v));
        d.appendChild(p);
      });
      ui.out.appendChild(d);
    });
    if (sorted.length > 12) ui.out.appendChild(el("div", "tool-more", `+ ${sorted.length - 12} achado(s) no relatório completo.`));
  }

  function addButton(ui, label, onClick) {
    let bar = ui.card.querySelector(".tool-actions");
    if (!bar) { bar = el("div", "tool-actions"); ui.card.appendChild(bar); }
    const b = el("button", "tool-btn", label);
    b.type = "button";
    b.addEventListener("click", onClick);
    bar.appendChild(b);
  }

  function summarize(name, findings, score, risk) {
    if (!findings) return `${name}: concluído.`;
    if (!findings.length) return `${name}: nenhum problema encontrado.`;
    const top = findings.slice().sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity))[0];
    return `${name}: ${findings.length} achado(s), risco ${risk || "?"} (${score}/100). Mais grave: [${SEV_LABEL[top.severity]}] ${top.title}.`;
  }

  async function handleUIAction(ev) {
    const H = window.jarvisHolograma;
    if (!H) return;
    if (ev.type === "HOLOGRAM_SHOW" && ev.subject && H.generate) await H.generate(ev.subject);
    if (ev.type === "HOLOGRAM_SCENE" && ev.scene && H.showScene) H.showScene(ev.scene);
  }

  // ---- ponto de entrada ----
  async function handle(text, api) {
    // "lembre-se que ..." → memória persistente (backend recusa segredos)
    const mem = /\b(?:lembre-se|lembre|guarde|memorize|anote)\b(?:\s+que)?[:,]?\s+(.{4,300})/i.exec(text);
    if (mem) {
      try {
        const r = await postJSON("/api/jarvis/memory", { text: mem[1] });
        const d = await r.json();
        const reply = r.ok ? "Anotado, senhor. Vou me lembrar disso nas próximas conversas." : (d.error || "Não consegui guardar isso.");
        say(api, reply, r.ok);
        return true;
      } catch (e) { return false; }
    }

    let plan;
    try {
      const r = await postJSON("/api/jarvis/route", { text });
      if (!r.ok) return false;
      plan = await r.json();
    } catch (e) { return false; }

    if (!plan || plan.mode === "none") return false;
    // pedidos que são só "mostre um holograma" continuam com o fluxo
    // existente do Hologram (lugar real, foto, comandos de ajuste…).
    if (plan.mode === "tools" && plan.steps.every((s) => s.tool === "hologram_show")) return false;
    if (plan.mode === "denied") {
      say(api, `${plan.explain} Peça acesso a um administrador, senhor.`, false);
      return true;
    }

    api.setHudState("executing", plan.explain || "Executando ferramenta…");
    const ui = buildCard(api.chatEl, plan.explain);
    const stepEls = {};
    let final = null, lastFindings = null, lastScore = null, lastRisk = null, lastName = "", ok = true, errMsg = "";
    let reportMd = "", scene = null, target = plan.target;

    try {
      const res = await postJSON("/api/jarvis/run", { text });
      await readNDJSON(res, async (ev) => {
        switch (ev.event) {
          case "stage": stepEls[ev.stage] = stepEls[ev.stage] || addStep(ui, `${ev.stage}: ${ev.message}`, "run");
            ui.fill.style.width = Math.min(100, Math.round(((ev.index || 0) + 1) / 10 * 100)) + "%";
            if (stepEls[ev.stage]) setStepState(stepEls[ev.stage], "run", `${ev.stage}: ${ev.message}`); break;
          case "stage_done": if (stepEls[ev.stage]) setStepState(stepEls[ev.stage], "ok", `${ev.stage}: ${ev.message}`); break;
          case "tool_done": addStep(ui, `${ev.tool}: ${ev.summary}`, "ok"); break;
          case "tool_error": addStep(ui, `${ev.tool}: ${ev.error}`, "err"); break;
          case "step_start": stepEls[ev.tool] = addStep(ui, `${ev.name} — ${ev.explain}`, "run");
            ui.fill.style.width = (ev.progress || 0) + "%"; break;
          case "step_result":
            ui.fill.style.width = (ev.progress || 100) + "%";
            if (stepEls[ev.tool]) setStepState(stepEls[ev.tool], ev.ok ? "ok" : "err", ev.ok ? `${ev.name}: ${ev.summary || "ok"}` : `${ev.tool}: ${ev.error}`);
            if (ev.ok && ev.findings) { lastFindings = (lastFindings || []).concat(ev.findings); lastName = ev.name; }
            if (ev.ok && ev.score != null) { lastScore = Math.max(lastScore || 0, ev.score); lastRisk = ev.risk; }
            if (ev.ok && ev.text && !ev.findings) { const pre = el("pre", "tool-text"); pre.textContent = ev.text.slice(0, 2000); ui.out.appendChild(pre); }
            if (!ev.ok) { ok = false; errMsg = ev.error; }
            break;
          case "diagnostic": {
            const d = addStep(ui, `Diagnóstico: ${ev.cause} ${ev.advice || ""}`, "err");
            d.classList.add("diag"); break;
          }
          case "retry": addStep(ui, `Correção segura: ${ev.message}`, "run"); break;
          case "diagnostic_resolved": addStep(ui, ev.message, "ok"); ok = true; break;
          case "diagnostic_failed": addStep(ui, ev.message + " " + (ev.error || ""), "err"); break;
          case "ui_action": await handleUIAction(ev); break;
          case "error": ok = false; errMsg = ev.error + (ev.hint ? " " + ev.hint : ""); addStep(ui, errMsg, "err"); break;
          case "done":
            final = ev;
            if (ev.findings) { lastFindings = ev.findings; lastScore = ev.score; lastRisk = ev.risk; lastName = "Security Investigator"; }
            if (ev.report_md) reportMd = ev.report_md;
            if (ev.scene) scene = ev.scene;
            if (ev.target) target = ev.target;
            break;
        }
      });
    } catch (e) {
      ok = false; errMsg = String(e.message || e);
      addStep(ui, "Falha de comunicação com o servidor: " + errMsg, "err");
    }

    ui.fill.style.width = "100%";
    ui.steps.querySelectorAll(".tool-step.run:not(.diag)").forEach((n) => setStepState(n, ok ? "ok" : "err"));
    ui.card.classList.add(ok ? "done-ok" : "done-err");
    if (lastFindings) renderFindings(ui, lastFindings, lastScore, lastRisk);
    if (reportMd) addButton(ui, "Copiar relatório", () => navigator.clipboard && navigator.clipboard.writeText(reportMd));
    if (scene && window.jarvisHolograma && window.jarvisHolograma.showScene) {
      addButton(ui, "Ver em holograma", () => window.jarvisHolograma.showScene(scene));
    }
    if (target && lastFindings && plan.steps.length === 1 && plan.steps[0].tool !== "security_investigator") {
      const tool = plan.steps[0].tool;
      addButton(ui, "Retestar", async () => {
        const r = await postJSON("/api/cyber/retest", { tool, target });
        const d = await r.json();
        const c = d.comparison;
        ui.out.appendChild(el("div", "tool-retest", c
          ? `Reteste: ${c.verdict} — ${c.resolved.length} resolvido(s), ${c.new.length} novo(s), ${c.persistent.length} persistente(s) (score ${c.before.score} → ${c.after.score}).`
          : (d.note || d.error || "Sem base para comparar.")));
      });
    }

    const summary = ok ? summarize(lastName || "Ferramenta", lastFindings, lastScore, lastRisk)
                       : `Não consegui concluir: ${errMsg || "erro desconhecido"}.`;
    api.history.push({ role: "assistant", content: summary + (reportMd ? "\n\n" + reportMd.slice(0, 4000) : "") });
    api.saveHistory(api.history);
    api.flashHudState(ok ? "success" : "error", ok ? "Concluído." : "Falhou.");
    api.speak(ok ? "Pronto, senhor. " + summary : "Encontrei um problema, senhor. " + summary);
    return true;
  }

  function say(api, reply, ok) {
    api.history.push({ role: "assistant", content: reply });
    api.saveHistory(api.history);
    api.renderBubble("assistant", reply);
    api.speak(reply);
    api.flashHudState(ok ? "success" : "error", ok ? "Concluído." : "Sem permissão.");
  }

  window.JarvisTools = { handle };
})();
