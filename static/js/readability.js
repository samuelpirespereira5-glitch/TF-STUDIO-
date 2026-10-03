/* v33 · Controles de legibilidade: A−, A+ e Modo leitura. Lembra a escolha neste navegador. */
(function () {
  var root = document.documentElement, KEY = "tt_read_v33";
  var st = { size: 0, read: false };
  try { var saved = JSON.parse(localStorage.getItem(KEY) || "null"); if (saved) st = { size: +saved.size || 0, read: !!saved.read }; } catch (e) {}
  function apply() {
    if (st.size) root.setAttribute("data-tt-size", String(st.size)); else root.removeAttribute("data-tt-size");
    if (st.read) root.setAttribute("data-tt-read", "on"); else root.removeAttribute("data-tt-read");
    try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {}
  }
  apply(); // antes da pintura: evita "piscar" ao trocar de página
  function mk(label, title, fn, pressed) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = label; b.title = title; b.setAttribute("aria-label", title);
    if (pressed !== undefined) b.setAttribute("aria-pressed", String(pressed));
    b.addEventListener("click", fn); return b;
  }
  document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelector(".tt-read-tools")) return;
    var box = document.createElement("div");
    box.className = "tt-read-tools"; box.setAttribute("role", "group"); box.setAttribute("aria-label", "Legibilidade");
    var readBtn = mk("👁", "Modo leitura (sem efeitos)", function () {
      st.read = !st.read; readBtn.setAttribute("aria-pressed", String(st.read)); apply();
    }, st.read);
    box.appendChild(mk("A−", "Diminuir texto", function () { st.size = Math.max(-1, st.size - 1); apply(); }));
    box.appendChild(mk("A+", "Aumentar texto", function () { st.size = Math.min(2, st.size + 1); apply(); }));
    box.appendChild(readBtn);
    document.body.appendChild(box);
  });
})();
