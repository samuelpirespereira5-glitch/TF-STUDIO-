"""Analisadores web (somente leitura, alvo autorizado).

Faz UMA requisição GET (+ uma com Origin de teste para CORS) e extrai:
Security Headers, Cookies, CSP, CORS, tecnologias e informações HTTP.
"""
import re
import time
from urllib.parse import urlparse, urljoin

from services import scope
from services.evidence import make_finding as F

UA = "TF-Studio-CyberLab/1.0 (authorized-security-testing)"
MAX_BODY = 400_000
MAX_REDIRECTS = 5
MAX_TOTAL_SECONDS = 45      # teto para a cadeia inteira de redirects
TEST_ORIGIN = "https://origin-de-teste.invalid"


def normalize_url(target):
    t = (target or "").strip()
    if not t:
        raise ValueError("Informe um alvo (URL ou domínio).")
    if "://" not in t:
        t = "https://" + t
    return t


class Resp:
    """Resposta mínima (compatível com o que os analisadores usam)."""
    def __init__(self, status, headers_list, body):
        self.status_code = status
        self.headers = _Headers(headers_list)
        self.content = body
        ctype = self.headers.get("content-type", "") or ""
        m = re.search(r"charset=([\w-]+)", ctype)
        self.text = body.decode(m.group(1) if m else "utf-8", errors="replace")


class _Headers:
    def __init__(self, pairs):
        self._pairs = [(k, v) for k, v in pairs]

    def get(self, name, default=None):
        n = name.lower()
        for k, v in self._pairs:
            if k.lower() == n:
                return v
        return default

    def get_list(self, name):
        n = name.lower()
        return [v for k, v in self._pairs if k.lower() == n]

    def items(self):
        seen = {}
        for k, v in self._pairs:
            seen[k] = v if k not in seen else seen[k] + ", " + v
        return seen.items()

    def __contains__(self, name):
        return self.get(name) is not None

    def __getitem__(self, name):
        v = self.get(name)
        if v is None:
            raise KeyError(name)
        return v

    def __iter__(self):
        return iter(dict(self.items()))


def _request_once(url, headers, timeout, method="GET", max_body=MAX_BODY):
    p = urlparse(url)
    port = p.port or (443 if p.scheme == "https" else 80)
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    # Conexão "fixada": o SSRF Guard resolve/valida uma vez e conecta no IP
    # validado (sem 2ª resolução DNS => sem DNS rebinding).
    timeout = scope.clamp_timeout(timeout)
    if p.scheme == "https":
        conn = scope.PinnedHTTPSConnection(p.hostname, port, timeout=timeout, mode="lab")
    else:
        conn = scope.PinnedHTTPConnection(p.hostname, port, timeout=timeout, mode="lab")
    try:
        conn.request(method, path, headers={"Host": p.netloc, **headers})
        r = conn.getresponse()
        body = r.read(max_body) if method != "HEAD" else b""
        return Resp(r.status, r.getheaders(), body)
    finally:
        conn.close()


def safe_get(url, headers=None, timeout=10.0, method="GET"):
    """GET com escopo revalidado a cada redirect. Retorna (response, chain)."""
    chain = []
    h = {"User-Agent": UA, "Accept": "*/*", "Connection": "close"}
    h.update(headers or {})
    current = url
    started = time.monotonic()
    for hop in range(MAX_REDIRECTS + 1):
        if time.monotonic() - started > MAX_TOTAL_SECONDS:
            raise scope.ScopeError("Tempo total excedido (cadeia de redirects lenta demais).")
        scope.check_url(current, context="redirect" if hop else "request")
        t0 = time.perf_counter()
        r = _request_once(current, h, timeout, method)
        chain.append({"url": current, "status": r.status_code,
                      "ms": round((time.perf_counter() - t0) * 1000)})
        loc = r.headers.get("location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            current = urljoin(current, loc)
            continue
        return r, chain
    raise scope.ScopeError("Redirecionamentos demais.")


# ---------------------------------------------------------------- headers
SEC_HEADERS = {
    "strict-transport-security": ("medium", "HSTS ausente",
        "Sem HSTS o navegador pode aceitar HTTP e ficar exposto a downgrade/sslstrip.",
        "Adicione: Strict-Transport-Security: max-age=31536000; includeSubDomains"),
    "content-security-policy": ("medium", "CSP ausente",
        "Sem CSP, um XSS injetado executa scripts de qualquer origem.",
        "Defina uma Content-Security-Policy restritiva (comece em modo Report-Only)."),
    "x-content-type-options": ("low", "X-Content-Type-Options ausente",
        "O navegador pode 'adivinhar' tipos MIME (MIME sniffing).",
        "Adicione: X-Content-Type-Options: nosniff"),
    "referrer-policy": ("low", "Referrer-Policy ausente",
        "URLs completas podem vazar para terceiros via Referer.",
        "Adicione: Referrer-Policy: strict-origin-when-cross-origin"),
    "permissions-policy": ("info", "Permissions-Policy ausente",
        "Recursos do navegador (câmera, geolocalização) não são restringidos.",
        "Adicione Permissions-Policy limitando o que o site realmente usa."),
}


def analyze_headers(resp, url):
    out = []
    h = {k.lower(): v for k, v in resp.headers.items()}
    for name, (sev, title, impact, fix) in SEC_HEADERS.items():
        if name not in h:
            out.append(F(f"headers.{name}", title, sev, evidence=f"Resposta de {url} não contém '{name}'.",
                         impact=impact, fix=fix, where=name))
    # clickjacking: X-Frame-Options OU frame-ancestors no CSP
    csp = h.get("content-security-policy", "")
    if "x-frame-options" not in h and "frame-ancestors" not in csp:
        out.append(F("headers.clickjacking", "Sem proteção contra clickjacking", "medium",
                     evidence="Nem X-Frame-Options nem CSP frame-ancestors presentes.",
                     impact="A página pode ser embutida em iframe malicioso (clickjacking).",
                     fix="Adicione X-Frame-Options: DENY ou CSP frame-ancestors 'none'.",
                     where="x-frame-options"))
    if url.startswith("http://") and "strict-transport-security" not in h:
        out.append(F("transport.plain_http", "Site servido em HTTP puro", "high",
                     evidence=f"{url} respondeu sem TLS.",
                     impact="Tráfego (incluindo sessões) pode ser lido ou alterado na rede.",
                     fix="Ative HTTPS e redirecione todo HTTP para HTTPS (301).", where="scheme"))
    hsts = h.get("strict-transport-security", "")
    m = re.search(r"max-age=(\d+)", hsts)
    if hsts and m and int(m.group(1)) < 15552000:
        out.append(F("headers.hsts_short", "HSTS com max-age curto", "low",
                     evidence=f"Strict-Transport-Security: {hsts}",
                     impact="Proteção HSTS expira rápido.",
                     fix="Use max-age de pelo menos 6 meses (15552000), idealmente 1 ano.",
                     where="strict-transport-security"))
    for leak in ("server", "x-powered-by", "x-aspnet-version"):
        v = h.get(leak, "")
        if v and re.search(r"\d", v):
            out.append(F(f"headers.leak.{leak}", f"Versão exposta em '{leak}'", "low",
                         evidence=f"{leak}: {v}",
                         impact="Facilita a busca por vulnerabilidades conhecidas da versão.",
                         fix=f"Oculte ou remova o cabeçalho '{leak}' no servidor/proxy.", where=leak))
    # isolamento de origem cruzada (Spectre/side-channel e leitura de janela)
    if "cross-origin-opener-policy" not in h:
        out.append(F("headers.coop", "Cross-Origin-Opener-Policy ausente", "low",
                     evidence=f"Resposta de {url} não contém 'cross-origin-opener-policy'.",
                     impact="Outra origem pode manter uma referência à janela (window.opener) e interagir com ela.",
                     fix="Adicione: Cross-Origin-Opener-Policy: same-origin", where="cross-origin-opener-policy"))
    if "cross-origin-resource-policy" not in h:
        out.append(F("headers.corp", "Cross-Origin-Resource-Policy ausente", "info",
                     evidence=f"Resposta de {url} não contém 'cross-origin-resource-policy'.",
                     impact="Outros sites podem embutir/ler este recurso via <script>/<img> cross-origin.",
                     fix="Adicione: Cross-Origin-Resource-Policy: same-site (ou same-origin).",
                     where="cross-origin-resource-policy"))
    xxp = h.get("x-xss-protection")
    if xxp and xxp.strip() not in ("0",):
        out.append(F("headers.xxp_deprecated", "X-XSS-Protection ativo (cabeçalho obsoleto)", "info",
                     evidence=f"x-xss-protection: {xxp}",
                     impact="Navegadores modernos ignoram; versões antigas tiveram bugs que o próprio "
                            "cabeçalho introduzia (ex.: vazamento de conteúdo via auditor de XSS).",
                     fix="Remova o cabeçalho ou defina explicitamente X-XSS-Protection: 0 e confie na CSP.",
                     where="x-xss-protection"))
    return out


# ------------------------------------------------------- Subresource Integrity
def analyze_sri(body, base_url):
    """Scripts/estilos carregados de outra origem sem atributo integrity:
    se o CDN for comprometido, o conteúdo injetado roda sem checagem."""
    out = []
    base_host = urlparse(base_url).hostname or ""
    for tag_re, kind in ((r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", "script"),
                         (r"<link\b[^>]*\brel=[\"']stylesheet[\"'][^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>", "stylesheet")):
        for m in re.finditer(tag_re, body, re.I):
            tag, src = m.group(0), m.group(1)
            full = urljoin(base_url, src)
            host = urlparse(full).hostname or ""
            if not host or host == base_host:
                continue  # mesma origem: SRI não é o mecanismo de defesa aqui
            if "integrity=" not in tag.lower():
                out.append(F(f"sri.missing.{kind}", f"{kind} externo sem Subresource Integrity",
                             "medium" if kind == "script" else "low",
                             evidence=full[:200],
                             impact=f"Se {host} for comprometido, o {kind} injetado roda sem checagem de integridade.",
                             fix='Adicione integrity="sha384-..." e crossorigin="anonymous" na tag, '
                                 "ou hospede o recurso localmente.",
                             where=full[:200]))
    return out


# ---------------------------------------------------------------- cookies
def analyze_cookies(resp, url):
    out = []
    is_https = url.startswith("https://")
    raw_list = resp.headers.get_list("set-cookie")
    cookies = []
    for raw in raw_list:
        name = raw.split("=", 1)[0].strip()
        low = raw.lower()
        flags = {
            "secure": "; secure" in low, "httponly": "; httponly" in low,
            "samesite": (re.search(r"samesite=(\w+)", low) or [None, None])[1],
        }
        cookies.append({"name": name, **flags})
        sensitive = bool(re.search(r"sess|auth|token|sid|jwt|login", name, re.I))
        if is_https and not flags["secure"]:
            out.append(F("cookies.no_secure", f"Cookie '{name}' sem Secure",
                         "high" if sensitive else "medium",
                         evidence=raw[:160], impact="O cookie pode trafegar em HTTP.",
                         fix="Adicione o atributo Secure.", where=f"cookie:{name}"))
        if not flags["httponly"]:
            out.append(F("cookies.no_httponly", f"Cookie '{name}' sem HttpOnly",
                         "medium" if sensitive else "low",
                         evidence=raw[:160], impact="JavaScript (XSS) consegue ler o cookie.",
                         fix="Adicione o atributo HttpOnly.", where=f"cookie:{name}"))
        if not flags["samesite"]:
            out.append(F("cookies.no_samesite", f"Cookie '{name}' sem SameSite", "low",
                         evidence=raw[:160], impact="Maior exposição a CSRF.",
                         fix="Defina SameSite=Lax (ou Strict).", where=f"cookie:{name}"))
        elif flags["samesite"] == "none" and not flags["secure"]:
            out.append(F("cookies.samesite_none_insecure", f"Cookie '{name}' SameSite=None sem Secure",
                         "medium", evidence=raw[:160],
                         impact="Navegadores modernos rejeitam; comportamento inconsistente.",
                         fix="SameSite=None exige Secure.", where=f"cookie:{name}"))
        if sensitive and not name.startswith(("__Host-", "__Secure-")):
            out.append(F("cookies.no_prefix", f"Cookie sensível '{name}' sem prefixo __Host-/__Secure-", "info",
                         evidence=raw[:160],
                         impact="Prefixos de cookie são reforçados pelo próprio navegador (bloqueia cookie sem "
                                "Secure, sem HTTPS ou com Domain/Path relaxados) — camada extra grátis.",
                         fix="Renomeie para __Host-<nome> (recomendado) e garanta Path=/ sem Domain, "
                             "ou __Secure-<nome> se precisar definir Domain.",
                         where=f"cookie:{name}"))
    return out, cookies


# ---------------------------------------------------------------- CSP
def analyze_csp(resp):
    csp = resp.headers.get("content-security-policy") or resp.headers.get(
        "content-security-policy-report-only")
    if not csp:
        return [], None
    report_only = "content-security-policy" not in resp.headers
    out, parsed = [], {}
    for part in csp.split(";"):
        bits = part.strip().split()
        if bits:
            parsed[bits[0].lower()] = bits[1:]
    if report_only:
        out.append(F("csp.report_only", "CSP apenas em modo Report-Only", "low",
                     evidence="Só content-security-policy-report-only presente.",
                     impact="A política não bloqueia nada, só reporta.",
                     fix="Após validar os relatórios, mude para Content-Security-Policy.", where="csp"))
    scripts = parsed.get("script-src", parsed.get("default-src", []))
    if "'unsafe-inline'" in scripts and not any(s.startswith(("'nonce-", "'sha")) for s in scripts):
        out.append(F("csp.unsafe_inline", "CSP permite 'unsafe-inline' em scripts", "medium",
                     evidence=f"script-src: {' '.join(scripts)}",
                     impact="Anula grande parte da proteção contra XSS.",
                     fix="Use nonces ou hashes em vez de 'unsafe-inline'.", where="csp:script-src"))
    if "'unsafe-eval'" in scripts:
        out.append(F("csp.unsafe_eval", "CSP permite 'unsafe-eval'", "medium",
                     evidence=f"script-src: {' '.join(scripts)}",
                     impact="Permite eval()/Function() a partir de strings.",
                     fix="Remova 'unsafe-eval' e refatore o código que depende dele.", where="csp:script-src"))
    if "*" in scripts or "https:" in scripts or "http:" in scripts:
        out.append(F("csp.wildcard", "CSP com origem curinga em scripts", "medium",
                     evidence=f"script-src: {' '.join(scripts)}",
                     impact="Qualquer host pode servir scripts.", fix="Liste apenas origens necessárias.",
                     where="csp:script-src"))
    if "object-src" not in parsed and "default-src" not in parsed:
        out.append(F("csp.no_object_src", "CSP sem object-src/default-src", "low",
                     evidence="Nenhuma restrição para <object>/<embed>.",
                     impact="Plugins podem carregar conteúdo arbitrário.",
                     fix="Defina object-src 'none'.", where="csp:object-src"))
    if "base-uri" not in parsed:
        out.append(F("csp.no_base_uri", "CSP sem base-uri", "info",
                     evidence="base-uri ausente.", impact="Injeção de <base> pode redirecionar URLs relativas.",
                     fix="Defina base-uri 'self'.", where="csp:base-uri"))
    return out, parsed


# ---------------------------------------------------------------- CORS
def analyze_cors(url):
    """Segunda requisição com Origin de teste inexistente (.invalid)."""
    out = []
    try:
        r, _ = safe_get(url, headers={"Origin": TEST_ORIGIN})
    except Exception as e:
        return [], {"error": str(e)}
    acao = r.headers.get("access-control-allow-origin")
    acac = (r.headers.get("access-control-allow-credentials") or "").lower() == "true"
    info = {"allow_origin": acao, "allow_credentials": acac}
    if acao == TEST_ORIGIN:
        out.append(F("cors.reflect_origin", "CORS reflete qualquer Origin", "high" if acac else "medium",
                     evidence=f"Origin de teste {TEST_ORIGIN} foi refletido em Access-Control-Allow-Origin"
                              + (" com credentials=true" if acac else "."),
                     impact="Qualquer site pode ler respostas desta origem"
                            + (" usando as credenciais do usuário." if acac else "."),
                     fix="Valide Origin contra uma lista fixa de origens confiáveis.", where="cors"))
    elif acao == "*":
        sev = "high" if acac else "low"
        out.append(F("cors.wildcard", "CORS com Access-Control-Allow-Origin: *", sev,
                     evidence="ACAO: *" + (" + credentials=true (inválido, mas indica má config)" if acac else ""),
                     impact="Qualquer origem lê respostas públicas desta API.",
                     fix="Restrinja às origens que realmente precisam.", where="cors"))
    elif acao == "null":
        out.append(F("cors.null_origin", "CORS aceita Origin 'null'", "medium",
                     evidence="ACAO: null", impact="Iframes sandbox/arquivos locais conseguem ler respostas.",
                     fix="Nunca permita 'null' como origem.", where="cors"))
    return out, info


# ---------------------------------------------------------------- fingerprint
TECH_PATTERNS = [
    ("WordPress", r"wp-content|wp-includes", "body"),
    ("Drupal", r"Drupal|/sites/default/files", "body"),
    ("Joomla", r"/media/jui/|Joomla!", "body"),
    ("Shopify", r"cdn\.shopify\.com", "body"),
    ("Wix", r"static\.wixstatic\.com", "body"),
    ("React", r"data-reactroot|__REACT_DEVTOOLS|react(\.production|-dom)", "body"),
    ("Next.js", r"/_next/static|__NEXT_DATA__", "body"),
    ("Vue.js", r"data-v-[0-9a-f]{6}|vue(\.runtime)?(\.min)?\.js", "body"),
    ("Angular", r"ng-version=|<app-root", "body"),
    ("jQuery", r"jquery[-.]?([0-9.]+)?(\.min)?\.js", "body"),
    ("Bootstrap", r"bootstrap(\.min)?\.(css|js)", "body"),
    ("Google Analytics", r"googletagmanager\.com|google-analytics\.com", "body"),
    ("Cloudflare", r"cloudflare", "hdr"),
    ("nginx", r"nginx", "server"),
    ("Apache", r"apache", "server"),
    ("IIS", r"microsoft-iis", "server"),
    ("Express", r"express", "x-powered-by"),
    ("PHP", r"php", "x-powered-by"),
    ("ASP.NET", r"asp\.net", "x-powered-by"),
    ("Flask/Werkzeug", r"werkzeug", "server"),
    ("Gunicorn", r"gunicorn", "server"),
]


def fingerprint(resp, body):
    hdr_text = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
    found = []
    for name, pat, src in TECH_PATTERNS:
        if src == "body":
            hay = body
        elif src == "hdr":
            hay = hdr_text
        else:
            hay = resp.headers.get(src, "")
        if re.search(pat, hay, re.I):
            found.append(name)
    gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', body, re.I)
    if gen:
        found.append(f"generator: {gen.group(1)[:60]}")
    return sorted(set(found))


# ---------------------------------------------------------------- orquestração
def run_web_analysis(target):
    """Análise HTTP completa de um alvo. Retorna dict com findings + raw."""
    url = normalize_url(target)
    t0 = time.perf_counter()
    resp, chain = safe_get(url)
    final_url = chain[-1]["url"]
    body = resp.text[:MAX_BODY] if "text" in resp.headers.get("content-type", "text") else ""
    findings = []
    findings += analyze_headers(resp, final_url)
    cookie_findings, cookies = analyze_cookies(resp, final_url)
    findings += cookie_findings
    csp_findings, csp = analyze_csp(resp)
    findings += csp_findings
    cors_findings, cors = analyze_cors(final_url)
    findings += cors_findings
    findings += analyze_sri(body, final_url)
    if final_url.startswith("https://") and chain[0]["url"].startswith("http://"):
        pass  # redirect http->https é o comportamento correto
    tech = fingerprint(resp, body)
    return {
        "findings": findings,
        "raw": {
            "url": url, "final_url": final_url, "status": resp.status_code,
            "redirect_chain": chain, "headers": dict(resp.headers.items()),
            "cookies": cookies, "csp": csp, "cors": cors, "technologies": tech,
            "response_ms": chain[-1]["ms"], "body_bytes": len(resp.content),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        },
    }


def check_links(target, max_links=40):
    """Link Checker: extrai links da página inicial e testa (HEAD/GET)
    somente os que estão DENTRO do escopo autorizado."""
    url = normalize_url(target)
    resp, chain = safe_get(url)
    base = chain[-1]["url"]
    hrefs = re.findall(r'(?:href|src)=["\']([^"\'#]+)', resp.text[:MAX_BODY], re.I)
    seen, results, findings = set(), [], []
    for h in hrefs:
        if len(results) >= max_links:
            break
        full = urljoin(base, h)
        if not full.startswith(("http://", "https://")) or full in seen:
            continue
        seen.add(full)
        try:
            scope.check_url(full)
        except scope.ScopeError:
            results.append({"url": full, "status": None, "skipped": "fora do escopo"})
            continue
        try:
            r, _ = safe_get(full, timeout=8, method="HEAD")
            if r.status_code in (405, 501):
                r, _ = safe_get(full, timeout=8)
            results.append({"url": full, "status": r.status_code})
            if r.status_code >= 400:
                findings.append(F("links.broken", f"Link quebrado ({r.status_code})", "low",
                                  evidence=full, impact="Má experiência e possível perda de SEO.",
                                  fix="Corrija ou remova o link.", where=full))
            if full.startswith("http://") and base.startswith("https://"):
                findings.append(F("links.mixed", "Conteúdo misto (HTTP em página HTTPS)", "medium",
                                  evidence=full, impact="Recurso pode ser alterado na rede; navegadores bloqueiam.",
                                  fix="Use https:// para o recurso.", where=full))
        except Exception as e:
            results.append({"url": full, "status": None, "error": str(e)[:100]})
    return {"findings": findings, "raw": {"checked": results, "base": base}}
