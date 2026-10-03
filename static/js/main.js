// Utilitário compartilhado: acompanha um job em segundo plano até terminar.
async function pollJob(jobId, onUpdate) {
  while (true) {
    const res = await fetch(`/api/jobs/${jobId}`);
    const job = await res.json();
    if (onUpdate) onUpdate(job);
    if (job.status === "done" || job.status === "error") return job;
    await new Promise(r => setTimeout(r, 1500));
  }
}

// Fundo "interativo": o brilho ciano do fundo segue o cursor/toque,
// dando uma sensação viva de HUD em vez de um fundo parado.
(function () {
  let raf = null;
  function setSpot(x, y) {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      document.body.style.setProperty("--mx", x + "px");
      document.body.style.setProperty("--my", y + "px");
      raf = null;
    });
  }
  window.addEventListener("mousemove", (e) => setSpot(e.clientX, e.clientY));
  window.addEventListener("touchmove", (e) => {
    if (e.touches && e.touches[0]) setSpot(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
})();


// Navegação móvel compacta: mantém Painel/Config/Cyber/Holograma acessíveis
// sem esmagar nove itens numa barra minúscula.
(function () {
  const btn = document.getElementById("mobile-more-btn");
  const panel = document.getElementById("mobile-more-panel");
  if (!btn || !panel) return;
  const close = () => {
    panel.classList.add("hidden");
    panel.setAttribute("aria-hidden", "true");
    btn.setAttribute("aria-expanded", "false");
  };
  btn.addEventListener("click", () => {
    const open = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !open);
    panel.setAttribute("aria-hidden", String(!open));
    btn.setAttribute("aria-expanded", String(open));
  });
  panel.querySelectorAll("[data-close-mobile-more]").forEach(el => el.addEventListener("click", close));
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
})();
