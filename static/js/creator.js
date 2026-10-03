document.getElementById("chat-creator-btn").addEventListener("click", async () => {
  const input = document.getElementById("chat-creator-input");
  const status = document.getElementById("chat-creator-status");
  const btn = document.getElementById("chat-creator-btn");
  const message = input.value.trim();
  if (!message) {
    status.textContent = "Escreve uma frase contando sobre o negócio primeiro.";
    return;
  }
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "⏳ Pensando...";
  status.textContent = "A IA está lendo sua descrição...";

  try {
    const res = await fetch("/api/ai/chat-to-site", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const r = data.result;
    const form = document.getElementById("creator-form");
    const setVal = (name, value) => {
      const el = form.querySelector(`[name=${name}]`);
      if (el && value) el.value = value;
    };
    setVal("name", r.name);
    setVal("type", r.type);
    setVal("city", r.city);
    setVal("slogan", r.slogan);
    setVal("description", r.description);
    if (r.primary) setVal("primary", r.primary);
    if (r.secondary) setVal("secondary", r.secondary);

    // Estilo: seleciona a opção correspondente, se existir
    const styleSelect = form.querySelector("[name=style]");
    if (styleSelect && r.style) {
      [...styleSelect.options].forEach((opt) => { if (opt.value === r.style) styleSelect.value = r.style; });
    }

    // Seções e extras: marca as sugeridas, desmarca o resto
    form.querySelectorAll("input[name=sections]").forEach((cb) => {
      cb.checked = (r.sections || []).includes(cb.value);
    });
    form.querySelectorAll("input[name=extras]").forEach((cb) => {
      cb.checked = (r.extras || []).includes(cb.value);
    });

    status.textContent = "✅ Formulário preenchido — revise os campos e clique em \"Gerar site com IA\".";
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    status.textContent = "❌ " + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

document.getElementById("creator-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("generate-btn");
  const status = document.getElementById("generate-status");
  const progressWrap = document.getElementById("generate-progress-wrap");
  const progressBar = document.getElementById("generate-progress-bar");
  btn.disabled = true;
  btn.textContent = "⏳ Gerando...";
  status.textContent = "Enviando dados...";
  progressWrap.style.display = "block";
  progressBar.style.width = "3%";

  try {
    const formData = new FormData(e.target);
    const res = await fetch("/api/sites/generate", { method: "POST", body: formData });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const job = await pollJob(data.job_id, (job) => {
      const elapsed = job.elapsed || 0;
      const estimate = job.estimate || 75;
      const pct = Math.max(3, Math.min(96, Math.round((elapsed / estimate) * 100)));
      progressBar.style.width = pct + "%";
      status.textContent = `${job.message || "Gerando..."} — ⏱ ${elapsed}s (estimativa: até ${estimate}s)`;
    });

    if (job.status === "error") throw new Error(job.error);

    progressBar.style.width = "100%";
    status.textContent = "✅ Site criado com sucesso!";
    window.location.href = `/sites/${job.result}/editor`;
  } catch (err) {
    status.textContent = "❌ " + err.message;
    progressWrap.style.display = "none";
    btn.disabled = false;
    btn.textContent = "🤖 Gerar site com IA";
  }
});

document.querySelectorAll("[data-ai]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const kind = btn.dataset.ai;
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "⏳";
    try {
      let url, body;
      if (kind === "business-name") {
        url = "/api/ai/business-name";
        body = { description: document.querySelector("[name=description]").value };
      } else if (kind === "slogan") {
        url = "/api/ai/slogan";
        body = { name: document.getElementById("f-name").value, description: document.querySelector("[name=description]").value };
      } else if (kind === "improve-description") {
        url = "/api/ai/improve-description";
        body = { text: document.getElementById("f-description").value };
      }
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      if (kind === "business-name") {
        const options = data.result.split("\n").filter(Boolean);
        alert("Sugestões de nome:\n\n" + options.join("\n"));
      } else if (kind === "slogan") {
        const options = data.result.split("\n").filter(Boolean);
        if (options[0]) document.getElementById("f-slogan").value = options[0].replace(/^[-*\d.\s]+/, "");
        alert("Sugestões de slogan:\n\n" + options.join("\n"));
      } else if (kind === "improve-description") {
        document.getElementById("f-description").value = data.result;
      }
    } catch (err) {
      alert("Erro: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  });
});
