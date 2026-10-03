// Tabs
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.querySelector(`[data-panel="${btn.dataset.tab}"]`).classList.remove("hidden");
  });
});

// Editar com IA
document.getElementById("ai-edit-btn").addEventListener("click", async () => {
  const instruction = document.getElementById("ai-instruction").value.trim();
  const status = document.getElementById("ai-edit-status");
  if (!instruction) { alert("Escreva o que deseja mudar."); return; }

  const btn = document.getElementById("ai-edit-btn");
  btn.disabled = true;
  status.textContent = "Enviando instrução...";

  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/editor/ai-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => { status.textContent = job.message || "Aplicando..."; });
    if (job.status === "error") throw new Error(job.error);

    status.textContent = "✅ Alteração aplicada!";
    setTimeout(() => window.location.reload(), 800);
  } catch (err) {
    status.textContent = "❌ " + err.message;
  } finally {
    btn.disabled = false;
  }
});

// Melhorar automaticamente (a IA decide sozinha o que corrigir)
document.getElementById("ai-improve-btn").addEventListener("click", async () => {
  const status = document.getElementById("ai-improve-status");
  const btn = document.getElementById("ai-improve-btn");
  btn.disabled = true;
  status.textContent = "Analisando o arquivo...";

  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/editor/ai-improve`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => { status.textContent = job.message || "Melhorando..."; });
    if (job.status === "error") throw new Error(job.error);

    status.textContent = "✅ Melhorias aplicadas!";
    setTimeout(() => window.location.reload(), 800);
  } catch (err) {
    status.textContent = "❌ " + err.message;
  } finally {
    btn.disabled = false;
  }
});

// Traduzir
const translateBtn = document.getElementById("translate-btn");
if (translateBtn) translateBtn.addEventListener("click", async () => {
  const country = document.getElementById("translate-country").value;
  const status = document.getElementById("translate-status");
  const btn = document.getElementById("translate-btn");
  btn.disabled = true;
  status.textContent = "Traduzindo...";

  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "country=" + encodeURIComponent(country),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => { status.textContent = job.message || "Traduzindo..."; });
    if (job.status === "error") throw new Error(job.error);

    status.textContent = "✅ Site traduzido! Redirecionando...";
    setTimeout(() => window.location.href = `/sites/${job.result}/editor`, 800);
  } catch (err) {
    status.textContent = "❌ " + err.message;
  } finally {
    btn.disabled = false;
  }
});

// Depurador (análise estática real, sem IA, + correção opcional com IA)
let lastIssues = [];
const debugScanBtn = document.getElementById("debug-scan-btn");
const debugFixBtn = document.getElementById("debug-fix-btn");
const debugResults = document.getElementById("debug-results");
const debugStatus = document.getElementById("debug-status");

const SEVERIDADE_ICON = { alto: "🔴", "médio": "🟠", medio: "🟠", baixo: "🟡" };

function renderIssues(issues) {
  if (!issues.length) {
    debugResults.innerHTML = '<p class="muted">✅ Nenhum problema encontrado.</p>';
    debugFixBtn.style.display = "none";
    return;
  }
  debugResults.innerHTML = issues.map((it) => {
    const icone = SEVERIDADE_ICON[it.severidade] || "⚪";
    return `<div class="debug-issue">${icone} <strong>${it.tipo}</strong> — ${it.descricao}</div>`;
  }).join("");
  debugFixBtn.style.display = "inline-block";
}

debugScanBtn.addEventListener("click", async () => {
  debugScanBtn.disabled = true;
  debugResults.innerHTML = '<p class="muted">Analisando...</p>';
  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/editor/debug`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    lastIssues = data.issues;
    renderIssues(lastIssues);
  } catch (err) {
    debugResults.innerHTML = "";
    debugStatus.textContent = "❌ " + err.message;
  } finally {
    debugScanBtn.disabled = false;
  }
});

debugFixBtn.addEventListener("click", async () => {
  debugFixBtn.disabled = true;
  debugStatus.textContent = "Corrigindo...";
  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/editor/debug/fix`, { method: "POST" });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => { debugStatus.textContent = job.message || "Corrigindo..."; });
    if (job.status === "error") throw new Error(job.error);

    debugStatus.textContent = "✅ Correções aplicadas!";
    setTimeout(() => window.location.reload(), 800);
  } catch (err) {
    debugStatus.textContent = "❌ " + err.message;
  } finally {
    debugFixBtn.disabled = false;
  }
});

// Imagens (upload/lista/exclusão de assets do site)
const imageUploadInput = document.getElementById("image-upload-input");
const imageUploadStatus = document.getElementById("image-upload-status");
const imageGallery = document.getElementById("image-gallery");

async function loadImageGallery() {
  imageGallery.innerHTML = '<p class="muted small">Carregando...</p>';
  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/editor/images`);
    const data = await res.json();
    if (!data.images || !data.images.length) {
      imageGallery.innerHTML = '<p class="muted small">Nenhuma imagem enviada ainda.</p>';
      return;
    }
    imageGallery.innerHTML = data.images.map((name) => `
      <div class="image-item" data-name="${name}">
        <img src="/sites/${window.SITE_SLUG}/preview/assets/${name}" alt="${name}">
        <div class="image-item-name">${name}</div>
        <button type="button" class="btn small copy-path-btn" data-path="assets/${name}">Copiar caminho</button>
        <button type="button" class="btn small danger delete-image-btn" data-name="${name}">Excluir</button>
      </div>
    `).join("");
  } catch (err) {
    imageGallery.innerHTML = '<p class="muted small">❌ Não consegui carregar as imagens.</p>';
  }
}

imageGallery.addEventListener("click", async (e) => {
  const copyBtn = e.target.closest(".copy-path-btn");
  if (copyBtn && navigator.clipboard) {
    navigator.clipboard.writeText(copyBtn.dataset.path);
    const original = copyBtn.textContent;
    copyBtn.textContent = "Copiado!";
    setTimeout(() => { copyBtn.textContent = original; }, 1200);
    return;
  }
  const delBtn = e.target.closest(".delete-image-btn");
  if (delBtn) {
    if (!confirm(`Excluir a imagem "${delBtn.dataset.name}"?`)) return;
    try {
      const res = await fetch(`/sites/${window.SITE_SLUG}/editor/images/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: delBtn.dataset.name }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      loadImageGallery();
    } catch (err) {
      alert("Não consegui excluir: " + err.message);
    }
  }
});

if (imageUploadInput) {
  imageUploadInput.addEventListener("change", async () => {
    const file = imageUploadInput.files[0];
    if (!file) return;
    imageUploadStatus.textContent = "Enviando...";
    const formData = new FormData();
    formData.append("image", file);
    try {
      const res = await fetch(`/sites/${window.SITE_SLUG}/editor/images/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      imageUploadStatus.textContent = `✅ Enviada! Caminho: ${data.path}`;
      imageUploadInput.value = "";
      loadImageGallery();
    } catch (err) {
      imageUploadStatus.textContent = "❌ " + err.message;
    }
  });
  loadImageGallery();
}

// Publicar no Netlify
const publishBtn = document.getElementById("publish-btn");
if (publishBtn) publishBtn.addEventListener("click", async () => {
  const status = document.getElementById("publish-status");
  const btn = document.getElementById("publish-btn");
  btn.disabled = true;
  status.textContent = "Preparando publicação...";

  try {
    const res = await fetch(`/sites/${window.SITE_SLUG}/publish`, { method: "POST" });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => { status.textContent = job.message || "Publicando..."; });
    if (job.status === "error") throw new Error(job.error);

    status.innerHTML = `✅ Publicado! <a href="${job.result.netlify_url}" target="_blank">${job.result.netlify_url}</a>`;
  } catch (err) {
    status.textContent = "❌ " + err.message;
  } finally {
    btn.disabled = false;
  }
});

// DESAFIOS: valida a solução atual do site contra o desafio dele.
// A validação é sempre feita no backend; a interface só reflete o resultado.
if (window.IS_CHALLENGE) {
  const validarBtn = document.getElementById("desafio-validar-btn");
  const retestBtn = document.getElementById("desafio-retest-btn");
  const resultadoEl = document.getElementById("desafio-resultado");
  const statusEl = document.getElementById("desafio-status");

  async function validarDesafio(btn) {
    if (!btn) return;
    btn.disabled = true;
    if (retestBtn) retestBtn.disabled = true;
    resultadoEl.innerHTML = '<p class="muted">🔎 Verificando sua solução no backend...</p>';
    try {
      const res = await fetch(`/sites/${window.SITE_SLUG}/desafio/validar`, {
        method: "POST",
        headers: { "Accept": "application/json" },
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || `Erro ${res.status}`);

      const linhas = (data.checks || []).map((c) =>
        `<div class="debug-issue">${c.ok ? "✅" : "❌"} ${c.label}${c.detail ? " — " + c.detail : ""}</div>`
      ).join("");
      if (data.passed) {
        const xpTxt = data.xp ? ` <strong>+${data.xp} XP</strong>${data.first_time ? "" : " (já contabilizado antes)"}` : "";
        statusEl.textContent = "✅ DESAFIO CONCLUÍDO";
        statusEl.style.color = "#7CFFB2";
        statusEl.style.borderColor = "#7CFFB2";
        resultadoEl.innerHTML = `<p class="muted" style="color:#7CFFB2">🎉 A verificação confirmou que está correto.${xpTxt}</p>${linhas}` +
          `<p class="muted small">Status salvo no backend. Se recarregar a página, ele continuará como concluído.</p>`;
      } else {
        statusEl.textContent = "🟡 AINDA NÃO CONCLUÍDO";
        statusEl.style.color = "";
        statusEl.style.borderColor = "";
        resultadoEl.innerHTML = '<p class="muted">❌ A verificação encontrou itens que ainda precisam de correção.</p>' + linhas;
      }
    } catch (err) {
      resultadoEl.innerHTML = `<p class="muted">❌ Não consegui verificar: ${String(err.message || err)}</p>`;
    } finally {
      btn.disabled = false;
      if (retestBtn) retestBtn.disabled = false;
    }
  }

  validarBtn?.addEventListener("click", () => validarDesafio(validarBtn));
  retestBtn?.addEventListener("click", () => validarDesafio(retestBtn));
}
