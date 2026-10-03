/* Central CSRF protection for the existing frontend.
   The backend remains authoritative; this only supplies the session token
   to existing forms/fetch calls without changing their routes or payloads. */
(() => {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta?.content || "";
  const methods = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  document.addEventListener("DOMContentLoaded", () => {
    if (!token) return;
    document.querySelectorAll("form").forEach(form => {
      if (!methods.has((form.method || "GET").toUpperCase())) return;
      if (form.querySelector('input[name="_csrf"]')) return;
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "_csrf";
      input.value = token;
      form.appendChild(input);
    });
  });

  const originalFetch = window.fetch;
  window.fetch = function(input, init = {}) {
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    if (!methods.has(method) || !token) return originalFetch.call(this, input, init);
    const headers = new Headers(init.headers || {});
    if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", token);
    return originalFetch.call(this, input, {...init, headers});
  };
})();
