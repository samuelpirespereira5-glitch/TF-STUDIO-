const CyberLab = {};

let _cyberSelectedScan = null;
let _cyberRunController = null;

async function _api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

// ---------------------------------------------------------------- alvos
CyberLab.loadTargets = async function () {
  const data = await _api("/api/cyber/targets");
  const tbody = document.querySelector("#cyber-targets-table tbody");
  tbody.innerHTML = "";
  (data.targets || []).forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${t.host || t.target || ""}</td><td>${t.note || ""}</td>
      <td>${t.added_by || ""}</td>
      <td><button class="btn btn-small" onclick="CyberLab.removeTarget('${(t.host || t.target || "").replace(/'/g, "\\'")}')">remover</button></td>`;
    tbody.appendChild(tr);
  });
};

CyberLab.addTarget = async function () {
  const target = document.getElementById("cyber-new-target").value.trim();
  const note = document.getElementById("cyber-new-note").value.trim();
  const confirm_ownership = document.getElementById("cyber-confirm-owner").checked;
  const msg = document.getElementById("cyber-target-msg");
  if (!target) { msg.textContent = "Informe um alvo."; return; }
  try {
    await _api("/api/cyber/targets", { method: "POST", body: JSON.stringify({ target, note, confirm_ownership }) });
    msg.textContent = `Alvo '${target}' adicionado.`;
    document.getElementById("cyber-new-target").value = "";
    CyberLab.loadTargets();
  } catch (e) {
    msg.textContent = "Erro: " + e.message;
  }
};

CyberLab.removeTarget = async function (target) {
  if (!confirm(`Remover o alvo autorizado "${target}"? O histórico de scans dele não é apagado.`)) return;
  await _api(`/api/cyber/targets?target=${encodeURIComponent(target)}`, { method: "DELETE" });
  CyberLab.loadTargets();
};

// ------------------------------------------------------------ dashboard
CyberLab.loadDashboard = async function () {
  const data = await _api("/api/cyber/dashboard");
  const totals = data.totals || {};
  document.getElementById("sum-targets").textContent = (data.targets || []).length;
  document.getElementById("sum-critical").textContent = totals.critical || 0;
  document.getElementById("sum-high").textContent = totals.high || 0;
  document.getElementById("sum-medium").textContent = totals.medium || 0;
  document.getElementById("sum-low").textContent = totals.low || 0;

  const grid = document.getElementById("cyber-dashboard-grid");
  grid.innerHTML = "";
  (data.targets || []).forEach((t) => {
    const div = document.createElement("div");
    div.className = "card tool";
    div.innerHTML = `<h3>${t.target}</h3>
      <div class="result">Risco: <strong>${t.label}</strong> (${t.score}/100)<br>
      crítico ${t.counts.critical} · alto ${t.counts.high} · médio ${t.counts.medium} ·
      baixo ${t.counts.low} · info ${t.counts.info}<br>
      ferramentas: ${(t.tools || []).join(", ") || "—"}</div>
      <button class="btn btn-small" onclick="CyberLab.loadHistory('${t.target}')">Ver histórico</button>`;
    grid.appendChild(div);
  });
};

// -------------------------------------------------------- status ferram.
let _cyberToolsCache = [];

CyberLab.loadToolStatus = async function () {
  const btn = document.querySelector('#cyber-tools-table')?.closest('.card')?.querySelector('button');
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Verificando em paralelo..."; }
  const tbody = document.querySelector("#cyber-tools-table tbody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="muted">Verificando ferramentas em paralelo…</td></tr>';
  try {
    const res = await _api("/api/jarvis/tool/tools_status", { method: "POST", body: JSON.stringify({ params: {} }) });
    _cyberToolsCache = (res.raw && res.raw.tools) || [];
    CyberLab.renderToolStatus();
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Verificar ferramentas instaladas"; }
  }
};

CyberLab.renderToolStatus = function () {
  const filterEl = document.getElementById("cyber-tools-category-filter");
  const filter = filterEl ? filterEl.value : "";
  // agrupa por categoria (ordem estável: Network, Web Security, Blue Team,
  // Forensics, Vulnerability Assessment, Reverse Engineering, OSINT/Recon, outras)
  const order = ["Network", "Web Security", "Blue Team", "Forensics",
                 "Vulnerability Assessment", "Reverse Engineering", "OSINT/Recon"];
  const tools = _cyberToolsCache
    .filter((t) => !filter || t.category === filter)
    .slice()
    .sort((a, b) => {
      const ia = order.indexOf(a.category), ib = order.indexOf(b.category);
      const ra = ia === -1 ? order.length : ia, rb = ib === -1 ? order.length : ib;
      return ra - rb || (a.label || "").localeCompare(b.label || "");
    });
  const tbody = document.querySelector("#cyber-tools-table tbody");
  tbody.innerHTML = "";
  tools.forEach((t) => {
    const tr = document.createElement("tr");
    const status = t.status === "installed"
      ? `🟢 instalada (${t.path})`
      : (t.status === "config_required" ? "🟡 configuração necessária" : "🔴 não instalada");
    const help = t.installed ? (t.note || "") : `${t.install_hint}`;
    const runnableIds = new Set(["nmap","gobuster","nikto","ffuf","whatweb","testssl"]);
    const action = t.runnable && runnableIds.has(t.id)
      ? `<button class="btn btn-small" onclick="CyberLab.selectExternalTool('${t.id}')">Executar</button>`
      : `<span class="muted small">${t.installed ? "Abrir/configurar localmente" : "Instalar primeiro"}</span>`;
    tr.innerHTML = `<td>${t.label}</td><td><span class="tool-chip">${t.category || "—"}</span></td>` +
      `<td>${status}</td><td>${t.version || "—"}</td><td class="muted small">${t.desc || "—"}</td>` +
      `<td class="muted small">${t.scope || "—"}</td>` +
      `<td class="muted small">${help}</td><td>${action}</td>`;
    tbody.appendChild(tr);
  });
};

// --------------------------------------------------------------- rodar
CyberLab.selectExternalTool = function (toolId) {
  const map = {
    nmap: "external_nmap", gobuster: "external_gobuster", nikto: "external_nikto",
    ffuf: "external_ffuf", whatweb: "external_whatweb", testssl: "external_testssl"
  };
  const select = document.getElementById("cyber-run-tool");
  if (select && map[toolId]) select.value = map[toolId];
  document.getElementById("cyber-run-target")?.focus();
  document.getElementById("exec-analise")?.scrollIntoView({behavior:"smooth", block:"start"});
};

CyberLab.runTool = async function () {
  const target = document.getElementById("cyber-run-target").value.trim();
  const tool = document.getElementById("cyber-run-tool").value;
  const out = document.getElementById("cyber-run-result");
  const progress = document.getElementById("cyber-scan-progress");
  if (!target) { out.textContent = "Informe um alvo autorizado."; return; }
  if (_cyberRunController) _cyberRunController.abort();
  _cyberRunController = new AbortController();
  progress?.classList.add("active");
  out.innerHTML = `<span class="cyber-scope-badge">● Verificando escopo…</span> Executando <strong>${tool}</strong> com o controle de escopo do servidor.`;
  try {
    const res = await _api(`/api/jarvis/tool/${tool}`, {
      method: "POST",
      body: JSON.stringify({ params: { target } }),
      signal: _cyberRunController.signal
    });
    out.textContent = (res.summary || "Concluído.") +
      (res.risk ? ` — risco ${res.risk} (${res.score}/100)` : "");
    CyberLab.loadDashboard();
    CyberLab.loadHistory();
  } catch (e) {
    if (e.name === "AbortError") out.textContent = "Scan cancelado pelo operador.";
    else out.textContent = "Erro: " + e.message;
  } finally {
    progress?.classList.remove("active");
    _cyberRunController = null;
  }
};
CyberLab.cancelTool = function () {
  if (_cyberRunController) _cyberRunController.abort();
};

// ------------------------------------------------------------ histórico
CyberLab.loadHistory = async function (target) {
  const t = target !== undefined ? target : document.getElementById("cyber-hist-target").value.trim();
  const q = t ? `?target=${encodeURIComponent(t)}` : "";
  const data = await _api(`/api/cyber/history${q}`);
  const tbody = document.querySelector("#cyber-history-table tbody");
  tbody.innerHTML = "";
  (data.scans || []).forEach((s) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.id}</td><td>${s.target}</td><td>${s.tool}</td><td>${s.score}</td>
      <td>${s.findings.length}</td><td>${new Date(s.ts).toLocaleString("pt-BR")}</td>
      <td><button class="btn btn-small" onclick="CyberLab.openScan(${s.id})">ver</button></td>`;
    tbody.appendChild(tr);
  });
};

CyberLab.openScan = async function (id) {
  const scan = await _api(`/api/cyber/scan/${id}`);
  window._cyberSelectedScan = scan;
  _cyberSelectedScan = scan;
  document.getElementById("cyber-findings-card").style.display = "";
  CyberLab.renderFindings();
};

CyberLab.renderFindings = function () {
  if (!_cyberSelectedScan) return;
  const sev = document.getElementById("cyber-findings-severity").value;
  const list = document.getElementById("cyber-findings-list");
  const findings = _cyberSelectedScan.findings.filter((f) => !sev || f.severity === sev);
  if (!findings.length) {
    list.innerHTML = `<p class="muted small">Nenhum achado com esse filtro.</p>`;
    return;
  }
  list.innerHTML = findings.map((f) => `
    <div class="card tool">
      <h3>[${f.severity.toUpperCase()}] ${f.title}</h3>
      <p class="muted small">${f.where || ""}</p>
      <p><strong>Evidência:</strong> ${f.evidence || "—"}</p>
      <p><strong>Impacto:</strong> ${f.impact || "—"}</p>
      <p><strong>Correção:</strong> ${f.fix || "—"}</p>
      <div class="card-actions"><button class="btn small" data-phase2-finding="${f.id}" data-phase2-scan="${_cyberSelectedScan.id}">🔬 Investigar</button></div>
    </div>`).join("");
};

CyberLab.retestSelected = async function () {
  if (!_cyberSelectedScan) return;
  const out = document.getElementById("cyber-retest-result");
  out.textContent = "Retestando...";
  try {
    const data = await _api("/api/cyber/retest", {
      method: "POST",
      body: JSON.stringify({ tool: _cyberSelectedScan.tool, target: _cyberSelectedScan.target }),
    });
    if (!data.comparison) {
      out.textContent = data.note || "Reteste concluído.";
      return;
    }
    const c = data.comparison;
    out.innerHTML = `Veredito: <strong>${c.verdict}</strong> (Δ score ${c.delta_score}) ·
      resolvidos: ${c.resolved.length} · persistentes: ${c.persistent.length} · novos: ${c.new.length}`;
    CyberLab.loadDashboard();
    CyberLab.loadHistory();
  } catch (e) {
    out.textContent = "Erro: " + e.message;
  }
};

CyberLab.generateReport = async function () {
  if (!_cyberSelectedScan) return;
  const out = document.getElementById("cyber-retest-result");
  try {
    const data = await _api("/api/cyber/report", {
      method: "POST",
      body: JSON.stringify({ target: _cyberSelectedScan.target }),
    });
    const blob = new Blob([data.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `relatorio_${_cyberSelectedScan.target}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    out.textContent = "Erro ao gerar relatório: " + e.message;
  }
};

CyberLab.exportJson = function () {
  if (!_cyberSelectedScan) return;
  const blob = new Blob([JSON.stringify(_cyberSelectedScan, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `scan_${_cyberSelectedScan.id}_${_cyberSelectedScan.target}.json`;
  a.click();
  URL.revokeObjectURL(url);
};

// ---------------------------------------------------------- pentest avançado
async function _runTool(toolId, params) {
  return _api(`/api/jarvis/tool/${toolId}`, { method: "POST", body: JSON.stringify({ params }) });
}

function _renderFindingsInto(el, findings) {
  if (!findings || !findings.length) { el.innerHTML = `<p class="muted small">Nenhum achado.</p>`; return; }
  el.innerHTML = findings.map((f) => `
    <div class="card tool"><h3>[${f.severity.toUpperCase()}] ${f.title}</h3>
    <p class="muted small">${f.where || ""}</p>
    <p><strong>Evidência:</strong> ${f.evidence || "—"}</p>
    <p><strong>Impacto:</strong> ${f.impact || "—"}</p>
    <p><strong>Correção:</strong> ${f.fix || "—"}</p></div>`).join("");
}

CyberLab.runOwasp = async function () {
  const target = document.getElementById("owasp-target").value.trim();
  const el = document.getElementById("owasp-result");
  if (!target) { el.textContent = "Informe a URL."; return; }
  el.textContent = "Escaneando...";
  try {
    const res = await _runTool("owasp_scanner", { target });
    if (!res.ok) { el.textContent = "Erro: " + res.error; return; }
    el.innerHTML = "";
    const p = document.createElement("p");
    p.className = "result";
    p.textContent = res.summary || `${(res.findings || []).length} achado(s).`;
    el.appendChild(p);
    const list = document.createElement("div");
    el.appendChild(list);
    _renderFindingsInto(list, res.findings);
    CyberLab.loadDashboard();
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runWhois = async function () {
  const domain = document.getElementById("whois-domain").value.trim();
  const el = document.getElementById("whois-result");
  if (!domain) { el.textContent = "Informe um domínio."; return; }
  el.textContent = "Consultando...";
  try {
    const res = await _runTool("osint_whois", { domain });
    if (!res.ok) { el.textContent = "Erro: " + res.error; return; }
    const f = (res.raw && res.raw.fields) || {};
    el.innerHTML = `<pre>${JSON.stringify(f, null, 2)}</pre>`;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runBreachCheck = async function () {
  const email = document.getElementById("breach-email").value.trim();
  const el = document.getElementById("breach-result");
  if (!email) { el.textContent = "Informe um e-mail."; return; }
  el.textContent = "Verificando...";
  try {
    const res = await _runTool("osint_email_breach", { email });
    el.textContent = res.ok ? (res.summary || "Concluído.") : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runEncoder = async function (action) {
  const text = document.getElementById("enc-text").value;
  const encoding = document.getElementById("enc-encoding").value;
  const el = document.getElementById("enc-result");
  try {
    const res = await _runTool("encoder", { text, encoding, action });
    el.textContent = res.ok ? res.raw.output : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runJwt = async function () {
  const token = document.getElementById("jwt-token").value.trim();
  const el = document.getElementById("jwt-result");
  try {
    const res = await _runTool("jwt_decoder", { token });
    el.innerHTML = res.ok
      ? `<pre>${JSON.stringify(res.raw, null, 2)}</pre>`
      : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runHashId = async function () {
  const value = document.getElementById("hash-value").value.trim();
  const el = document.getElementById("hash-result");
  try {
    const res = await _runTool("hash_identifier", { value });
    el.textContent = res.ok ? res.summary : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runCidr = async function () {
  const cidr = document.getElementById("cidr-value").value.trim();
  const el = document.getElementById("cidr-result");
  try {
    const res = await _runTool("cidr_calculator", { cidr });
    el.innerHTML = res.ok ? `<pre>${JSON.stringify(res.raw, null, 2)}</pre>` : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.runPayloads = async function () {
  const kind = document.getElementById("payload-kind").value;
  const el = document.getElementById("payload-result");
  try {
    const res = await _runTool("test_payloads", { kind });
    el.innerHTML = res.ok
      ? `<p class="muted small">${res.summary}</p><pre>${res.raw.payloads.join("\n")}</pre>`
      : "Erro: " + res.error;
  } catch (e) { el.textContent = "Erro: " + e.message; }
};

CyberLab.loadCheatsheet = async function () {
  const data = await _api("/api/cyber/cheatsheet");
  const el = document.getElementById("cheatsheet-content");
  el.innerHTML = data.sheets.map((s) => `
    <h4>${s.tool}</h4>
    <table class="table"><tbody>
      ${s.commands.map((c) => `<tr><td><code>${c.cmd}</code></td><td class="muted small">${c.desc}</td></tr>`).join("")}
    </tbody></table>`).join("");
};

CyberLab.loadAudit = async function () {
  const data = await _api("/api/cyber/audit");
  const tbody = document.querySelector("#cyber-audit-table tbody");
  tbody.innerHTML = "";
  (data.log || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${new Date(r.ts).toLocaleString("pt-BR")}</td><td>${r.role || ""}</td>
      <td>${r.tool}</td><td>${r.target || ""}</td><td>${r.ok ? "✅" : "❌"}</td>
      <td>${r.duration_ms}</td><td class="muted small">${r.error || ""}</td>`;
    tbody.appendChild(tr);
  });
};

// ------------------------------------------------------------------ init
document.addEventListener("DOMContentLoaded", () => {
  CyberLab.loadTargets();
  CyberLab.loadDashboard();
  CyberLab.loadHistory();
});

// ================================================================
// BLUE TEAM / THREAT INTELLIGENCE / FORENSE DIGITAL / IR
// ================================================================

function _term(msg) {
  const el = document.getElementById("cyber-terminal");
  if (!el) return;
  const ts = new Date().toLocaleTimeString();
  el.innerHTML += `[${ts}] ${msg}<br>`;
  el.scrollTop = el.scrollHeight;
}

function _holoState(state) {
  if (window.HoloStatus && typeof window.HoloStatus.set === "function") window.HoloStatus.set(state);
}

function _sevBadge(sev) {
  const colors = { critical: "#ff2d2d", high: "#ff7a00", medium: "#ffd000", low: "#4caf50", info: "#888" };
  return `<span style="background:${colors[sev]||'#888'};color:#000;padding:1px 6px;border-radius:4px;font-size:11px;text-transform:uppercase">${sev}</span>`;
}

function _findingsHtml(findings) {
  if (!findings || !findings.length) return `<p class="muted small">Nenhum achado. ✅</p>`;
  return findings.map(f => `<div class="finding">
      ${_sevBadge(f.severity)} <strong>${f.title}</strong><br>
      <span class="muted small">${f.evidence || ""}</span>
      ${f.impact ? `<div class="small">Impacto: ${f.impact}</div>` : ""}
      ${f.fix ? `<div class="small">Correção: ${f.fix}</div>` : ""}
    </div>`).join("");
}

// ---------------------------------------------------------------- MITRE ATT&CK
CyberLab.mitreLookup = async function () {
  _holoState("scanning"); _term("Consultando MITRE ATT&CK...");
  const q = document.getElementById("mitre-query").value.trim();
  const el = document.getElementById("mitre-result");
  try {
    const data = await _api(`/api/cyber/mitre?q=${encodeURIComponent(q)}`);
    el.innerHTML = (data.tactics || []).map(t => `
      <div class="card" style="margin-top:8px">
        <h4>${t.id} — ${t.pt} (${t.name})</h4>
        ${t.techniques.map(tc => `
          <div style="margin:6px 0;padding-left:8px;border-left:2px solid #444">
            <strong>${tc.id} ${tc.name}</strong>
            <div class="small">🔍 Detecção: ${tc.detect}</div>
            <div class="small">🛡 Mitigação: ${tc.mitigate}</div>
          </div>`).join("")}
      </div>`).join("") || `<p class="muted small">Nada encontrado.</p>`;
    _holoState("waiting"); _term(`MITRE: ${data.tactics.length} tática(s).`);
  } catch (e) { el.textContent = e.message; _holoState("alert"); _term("Erro MITRE: " + e.message); }
};

// ---------------------------------------------------------------- IoC feed
CyberLab.iocCheck = async function () {
  const hash = document.getElementById("ioc-hash").value.trim();
  const el = document.getElementById("ioc-result");
  try {
    const data = await _api("/api/cyber/ioc/check", { method: "POST", body: JSON.stringify({ hash }) });
    el.innerHTML = `Encontrado no feed local: <strong>${data.found_in_local_feed ? "SIM" : "não"}</strong><br><span class="muted small">${data.note}</span>`;
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Logs
CyberLab.analyzeLogs = async function () {
  _holoState("scanning"); _term("Analisando logs...");
  const text = document.getElementById("logs-input").value;
  const el = document.getElementById("logs-result");
  try {
    const data = await _api("/api/jarvis/tool/log_analyzer", { method: "POST", body: JSON.stringify({ params: { text } }) });
    const findings = data.findings || (data.result && data.result.findings) || [];
    el.innerHTML = _findingsHtml(findings);
    if (findings.some(f => f.severity === "critical" || f.severity === "high")) { _holoState("alert"); _term("⚠ Padrão de ataque detectado nos logs!"); }
    else { _holoState("waiting"); _term(`Logs analisados: ${findings.length} achado(s).`); }
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

// ---------------------------------------------------------------- WAF
CyberLab.wafGenerate = async function () {
  const engine = document.getElementById("waf-engine").value;
  const el = document.getElementById("waf-result");
  try {
    const data = await _api("/api/cyber/waf/generate", { method: "POST", body: JSON.stringify({ engine, patterns: ["sqli", "xss", "traversal", "scanner"] }) });
    el.innerHTML = `<pre style="white-space:pre-wrap;background:#111;color:#0f0;padding:10px;border-radius:6px">${(data.rules||"").replace(/</g,"&lt;")}</pre>`;
    _term(`Regras WAF (${engine}) geradas.`);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Headers HTTP
CyberLab.headersAudit = async function () {
  const headers = document.getElementById("headers-input").value;
  const el = document.getElementById("headers-result");
  try {
    const data = await _api("/api/cyber/headers/audit", { method: "POST", body: JSON.stringify({ headers }) });
    el.innerHTML = _findingsHtml(data.findings);
    _term(`Cabeçalhos: ${data.findings.length} achado(s).`);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Config audit (usa endpoint já existente)
CyberLab.configAudit = async function () {
  const text = document.getElementById("cfg-input").value;
  const el = document.getElementById("cfg-result");
  try {
    const data = await _api("/api/jarvis/tool/config_audit", { method: "POST", body: JSON.stringify({ params: { text, kind: "auto" } }) });
    const findings = (data.result && data.result.findings) || data.findings || [];
    el.innerHTML = _findingsHtml(findings);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- E-mail anti-phishing
CyberLab.emailAnalyze = async function () {
  _holoState("thinking");
  const headers = document.getElementById("email-input").value;
  const el = document.getElementById("email-result");
  try {
    const data = await _api("/api/cyber/email/analyze", { method: "POST", body: JSON.stringify({ headers }) });
    el.innerHTML = `<div class="small">SPF: <strong>${data.raw.spf||'?'}</strong> · DKIM: <strong>${data.raw.dkim||'?'}</strong> · DMARC: <strong>${data.raw.dmarc||'?'}</strong></div>` + _findingsHtml(data.findings);
    if (data.findings.some(f => f.severity === "high")) { _holoState("alert"); _term("⚠ Possível phishing detectado!"); }
    else _holoState("waiting");
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

// ---------------------------------------------------------------- FIM
let _fimBaseline = null;
CyberLab.fimSnapshot = async function (mode) {
  const el = document.getElementById("fim-result");
  // usa os arquivos atualmente carregados no editor de sites, se existirem globalmente (window.CurrentSiteFiles)
  const files = (window.CurrentSiteFiles && typeof window.CurrentSiteFiles === "object") ? window.CurrentSiteFiles : { "exemplo.txt": document.title || "" };
  try {
    const data = await _api("/api/cyber/fim/hash", { method: "POST", body: JSON.stringify({ files }) });
    if (mode === "baseline") {
      _fimBaseline = data.hashes;
      el.innerHTML = `<p class="muted small">Baseline salvo com ${data.count} arquivo(s) em ${data.generated_at}.</p>`;
      _term(`FIM: baseline com ${data.count} arquivo(s).`);
    } else {
      if (!_fimBaseline) { el.innerHTML = `<p class="muted small">Salve um baseline primeiro.</p>`; return; }
      const cmp = await _api("/api/cyber/fim/compare", { method: "POST", body: JSON.stringify({ baseline: _fimBaseline, current: data.hashes }) });
      el.innerHTML = _findingsHtml(cmp.findings);
      if (cmp.findings.length) { _holoState("alert"); _term("⚠ FIM: alterações detectadas!"); }
      else { _term("FIM: nenhuma alteração."); }
    }
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- IR Playbooks
CyberLab.loadIrPlaybooks = async function () {
  try {
    const data = await _api("/api/cyber/ir/playbooks");
    const sel = document.getElementById("ir-select");
    sel.innerHTML = data.playbooks.map(p => `<option value="${p.key}">${p.title}</option>`).join("");
  } catch (e) {}
};
CyberLab.irShow = async function () {
  const key = document.getElementById("ir-select").value;
  const el = document.getElementById("ir-result");
  try {
    const pb = await _api(`/api/cyber/ir/playbooks/${key}`);
    el.innerHTML = `<h4>${pb.title}</h4>` + pb.steps.map(s => `<div style="margin:6px 0"><strong>${s.phase}</strong>: ${s.text}</div>`).join("");
    _term(`Playbook aberto: ${pb.title}`);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Relatório + Security Score
CyberLab.auditReport = async function () {
  _holoState("thinking");
  const target = document.getElementById("audit-target").value.trim() || "aplicação";
  const format = document.getElementById("audit-format").value;
  const el = document.getElementById("audit-report-result");
  try {
    const data = await _api("/api/cyber/audit/report", { method: "POST", body: JSON.stringify({ target, format }) });
    const sc = data.security_score;
    const report = data.report || "";
    el.innerHTML = `<div class="small">Security Score: <strong>${sc.score}/100</strong> (risco ${sc.risk}) · ${sc.total_findings} achado(s)</div>
      <div class="inline" style="margin:8px 0"><button class="btn small" type="button" id="download-audit-report">⬇ Baixar ${format.toUpperCase()}</button></div>
      <pre style="white-space:pre-wrap;background:#08111e;color:#dce8f8;padding:10px;border-radius:8px;max-height:400px;overflow:auto">${report.replace(/</g,"&lt;")}</pre>`;
    document.getElementById("download-audit-report").onclick=()=>{
      const mime=format==="html"?"text/html":format==="json"?"application/json":"text/markdown";
      const blob=new Blob([report],{type:mime}), url=URL.createObjectURL(blob), a=document.createElement("a");
      a.href=url; a.download=`auditoria_${target.replace(/[^a-z0-9._-]+/gi,"_")}.${format==="markdown"?"md":format}`;
      a.click(); URL.revokeObjectURL(url);
    };
    _holoState(sc.risk === "crítico" || sc.risk === "alto" ? "alert" : "waiting");
    _term(`Relatório gerado: score ${sc.score}/100.`);
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

// ---------------------------------------------------------------- CTF educacional
CyberLab.loadCtfChallenges = async function () {
  try {
    const data = await _api("/api/cyber/ctf/challenges");
    const sel = document.getElementById("ctf-select");
    sel.innerHTML = data.challenges.map(c => `<option value="${c.id}">${c.title} (${c.difficulty})</option>`).join("");
  } catch (e) {}
};
CyberLab.ctfShow = async function () {
  const id = document.getElementById("ctf-select").value;
  const el = document.getElementById("ctf-challenge");
  try {
    const c = await _api(`/api/cyber/ctf/challenges/${id}`);
    el.innerHTML = `<h4>${c.title}</h4><p class="small">💡 ${c.hint}</p>
      <pre style="white-space:pre-wrap;background:#111;color:#eee;padding:10px;border-radius:6px">${c.vulnerable_code.replace(/</g,"&lt;")}</pre>`;
  } catch (e) { el.textContent = e.message; }
};
CyberLab.ctfReveal = async function () {
  const id = document.getElementById("ctf-select").value;
  const el = document.getElementById("ctf-challenge");
  try {
    const c = await _api(`/api/cyber/ctf/challenges/${id}?reveal=1`);
    el.innerHTML += `<h4>✅ Solução</h4><pre style="white-space:pre-wrap;background:#052;color:#9f9;padding:10px;border-radius:6px">${c.fixed_code.replace(/</g,"&lt;")}</pre>`;
  } catch (e) { el.textContent = e.message; }
};
CyberLab.ctfCheck = async function () {
  const id = document.getElementById("ctf-select").value;
  const code = document.getElementById("ctf-answer").value;
  const el = document.getElementById("ctf-result");
  try {
    const data = await _api(`/api/cyber/ctf/challenges/${id}/check`, { method: "POST", body: JSON.stringify({ code }) });
    el.innerHTML = `<p class="${data.solved ? '' : 'muted'}">${data.solved ? '✅' : '❌'} ${data.message}</p>` + _findingsHtml(data.remaining_findings);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Gerador de testes de segurança
CyberLab.testsGenerate = async function () {
  const language = document.getElementById("tests-lang").value;
  const path = document.getElementById("tests-path").value.trim() || "/api/exemplo";
  const method = document.getElementById("tests-method").value;
  const el = document.getElementById("tests-result");
  try {
    const data = await _api("/api/cyber/tests/generate", { method: "POST", body: JSON.stringify({ language, endpoints: [{ path, method }] }) });
    el.innerHTML = `<pre style="white-space:pre-wrap;background:#111;color:#0f0;padding:10px;border-radius:6px;max-height:400px;overflow:auto">${data.code.replace(/</g,"&lt;")}</pre>
      <p class="muted small">Arquivo sugerido: ${data.filename}</p>`;
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Força de senha
CyberLab.pwdStrength = async function () {
  const password = document.getElementById("pwd-input").value;
  const el = document.getElementById("pwd-result");
  try {
    const data = await _api("/api/cyber/password/strength", { method: "POST", body: JSON.stringify({ password }) });
    el.innerHTML = `Força: <strong>${data.label}</strong> (${data.score}/100) · entropia ~${data.approx_entropy_bits} bits` + _findingsHtml(data.findings);
  } catch (e) { el.textContent = e.message; }
};

// ---------------------------------------------------------------- Scanner de malware (forense)
CyberLab.malwareScan = async function () {
  _holoState("scanning");
  const text = document.getElementById("malware-input").value;
  const el = document.getElementById("malware-result");
  try {
    const data = await _api("/api/cyber/malware/scan", { method: "POST", body: JSON.stringify({ text }) });
    el.innerHTML = _findingsHtml(data.findings);
    if (data.findings.length) { _holoState("alert"); _term(`⚠ ${data.findings.length} padrão(ões) de malware detectado(s)!`); }
    else { _holoState("waiting"); _term("Scanner de malware: nada suspeito."); }
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

// ---------------------------------------------------------------- Vulnerability Doctor
function _esc(t) { return String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function _vdRender(data) {
  const el = document.getElementById("vd-result");
  const fs = data.findings || [];
  let html = `<div class="small" style="margin:8px 0"><strong>${_esc(data.summary || "")}</strong></div>`;
  if (!fs.length) { el.innerHTML = html + `<p class="muted small">Nenhuma vulnerabilidade encontrada pelas regras atuais. ✅ (Isso não prova que está 100% seguro.)</p>`; return; }
  html += fs.map((f) => {
    const r = f.remediation;
    return `<div class="finding" style="margin:10px 0;padding:8px;border-left:3px solid #555">
      ${_sevBadge(f.severity)} <strong>${_esc(f.title)}</strong><br>
      <span class="muted small">${_esc(f.evidence)}</span>
      ${f.impact ? `<div class="small">⚠ Por que é ruim: ${_esc(f.impact)}</div>` : ""}
      ${r ? `<div class="small" style="margin-top:6px">🔧 <strong>Como corrigir:</strong> ${_esc(r.how)}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px">
          <pre style="white-space:pre-wrap;background:#2a0f0f;color:#f99;padding:8px;border-radius:6px;margin:0;font-size:12px">❌ Antes\n${_esc(r.before)}</pre>
          <pre style="white-space:pre-wrap;background:#0f2a15;color:#9f9;padding:8px;border-radius:6px;margin:0;font-size:12px">✅ Depois\n${_esc(r.after)}</pre>
        </div>`
        : (f.fix ? `<div class="small" style="margin-top:6px">🔧 <strong>Como corrigir:</strong> ${_esc(f.fix)}</div>` : "")}
    </div>`;
  }).join("");
  el.innerHTML = html;
}

CyberLab.vdLoadSites = async function () {
  try {
    const data = await _api("/api/cyber/vulndoctor/sites");
    const sel = document.getElementById("vd-site");
    if (!sel) return;
    sel.innerHTML = `<option value="">— escolher site criado pelo app —</option>` +
      (data.sites || []).map((s) => `<option value="${_esc(s.slug)}">${_esc(s.name)}</option>`).join("");
  } catch (e) {}
};

CyberLab.vdScanSite = async function () {
  const slug = document.getElementById("vd-site").value;
  const el = document.getElementById("vd-result");
  if (!slug) { el.innerHTML = `<p class="muted small">Escolha um site.</p>`; return; }
  _holoState("scanning"); _term(`Vulnerability Doctor: analisando site '${slug}'...`);
  try {
    const data = await _api("/api/cyber/vulndoctor/site", { method: "POST", body: JSON.stringify({ slug }) });
    _vdRender(data);
    const bad = (data.findings || []).some((f) => f.severity === "critical" || f.severity === "high");
    _holoState(bad ? "alert" : "waiting"); _term(data.summary);
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

CyberLab.vdScanText = async function () {
  const text = document.getElementById("vd-input").value;
  const filename = document.getElementById("vd-filename").value.trim();
  const el = document.getElementById("vd-result");
  if (!text.trim()) { el.innerHTML = `<p class="muted small">Cole algum conteúdo para analisar.</p>`; return; }
  _holoState("scanning"); _term("Vulnerability Doctor: analisando texto colado...");
  try {
    const data = await _api("/api/cyber/vulndoctor", { method: "POST", body: JSON.stringify({ text, filename }) });
    _vdRender(data);
    const bad = (data.findings || []).some((f) => f.severity === "critical" || f.severity === "high");
    _holoState(bad ? "alert" : "waiting"); _term(data.summary);
  } catch (e) { el.textContent = e.message; _holoState("alert"); }
};

// ---------------------------------------------------------------- boot
document.addEventListener("DOMContentLoaded", () => {
  CyberLab.loadIrPlaybooks && CyberLab.loadIrPlaybooks();
  CyberLab.loadCtfChallenges && CyberLab.loadCtfChallenges();
  CyberLab.vdLoadSites && CyberLab.vdLoadSites();
});
