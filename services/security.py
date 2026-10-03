"""Camada de segurança transversal (hardening), sem framework novo e sem
tocar nas ~100 rotas existentes uma a uma.

- `login_rate_limit`: trava por IP após tentativas falhas seguidas (memória
  do processo; reinicia o contador no deploy — suficiente para o modelo de
  1 processo/1 worker já documentado no README).
- `check_csrf` + `check_origin`: token CSRF real por sessão, validado no backend,
  com Origin/Referer como segunda camada; o frontend centraliza o envio do token.
- `apply_security_headers`: CSP/HSTS/X-Frame-Options/etc. via
  `after_request`, sem quebrar o app (onclick=/scripts inline continuam
  funcionando — a maior parte da UI depende deles).
- `validate_image_upload`: valida tamanho e conteúdo real, usa allowlist de
  formatos e nunca confia na extensão enviada pelo cliente.
"""
import ipaddress
import os
import threading
import time
import re
import uuid
import secrets
from urllib.parse import urlparse

# ---------------------------------------------------------- Open-redirect guard
def safe_next_url(candidate, fallback="/"):
    """Aceita só caminhos relativos internos. Bloqueia //evil, http://, javascript: etc.

    Usado em todo redirect pós-login que aceita ?next= ou form next=.
    """
    value = (candidate or "").strip()
    if not value:
        return fallback
    # Apenas path relativo começando com / e sem protocolo/esquema embutido
    if not value.startswith("/") or value.startswith("//"):
        return fallback
    if "\\" in value or "\n" in value or "\r" in value:
        return fallback
    lower = value.lower()
    if lower.startswith("/\\") or "://" in lower or lower.startswith("/http"):
        return fallback
    # Bloqueia esquemas embutidos e path traversal óbvio para fora do app
    if any(x in lower for x in ("javascript:", "data:", "vbscript:")):
        return fallback
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return fallback
    return value


# Rate-limit genérico por IP+chave (além do login_lock específico)
_api_hits = {}
_api_lock = threading.Lock()
_API_WINDOW = 60
_API_MAX = 60  # 60 req/min por IP+chave em endpoints sensíveis


def api_rate_limited(ip, key="api", max_hits=None, window=None):
    """Retorna segundos restantes de bloqueio, ou 0 se livre."""
    max_hits = max_hits or _API_MAX
    window = window or _API_WINDOW
    now = time.time()
    bucket = f"{ip}|{key}"
    with _api_lock:
        hits = [t for t in _api_hits.get(bucket, []) if now - t < window]
        if len(hits) >= max_hits:
            oldest = min(hits) if hits else now
            return max(1, int(window - (now - oldest)))
        hits.append(now)
        _api_hits[bucket] = hits
        # poda ocasional
        if len(_api_hits) > 8000:
            for k in list(_api_hits.keys())[:2000]:
                _api_hits.pop(k, None)
    return 0


# ---------------------------------------------------------- IP real do cliente
def _detect_trusted_hops():
    """Quantos proxies confiáveis existem na frente do app.

    - TRUSTED_PROXY_HOPS=N no ambiente manda sempre (0 = sem proxy).
    - Sem a variável: 1 se detectarmos uma hospedagem PaaS conhecida
      (Heroku, Render, Railway, Fly, Cloud Run); senão 0 (rodando direto).
    Se houver mais de um proxy (ex.: Cloudflare + Render), use 2.
    """
    raw = os.getenv("TRUSTED_PROXY_HOPS", "").strip()
    if raw.isdigit():
        return int(raw)
    for var in ("DYNO", "RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "K_SERVICE"):
        if os.getenv(var):
            return 1
    return 0


TRUSTED_PROXY_HOPS = _detect_trusted_hops()


def client_ip(request):
    """IP real do visitante, sem confiar em X-Forwarded-For forjado.

    Cada proxy confiável ACRESCENTA o IP que viu no fim do header; então o
    valor confiável é o N-ésimo a partir do FIM (N = número de proxies).
    Tudo que estiver antes disso pode ter sido inventado pelo cliente.
    Sem proxy configurado, usa o IP da conexão e ignora o header.
    """
    peer = request.remote_addr or ""
    hops = TRUSTED_PROXY_HOPS
    if hops <= 0:
        return peer
    parts = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    if len(parts) < hops:
        return peer
    try:
        return str(ipaddress.ip_address(parts[-hops]))
    except ValueError:
        return peer


# ---------------------------------------------------------- rate limit login
_lock = threading.Lock()
_attempts = {}  # ip -> [timestamps das falhas recentes]
MAX_ATTEMPTS = 8
WINDOW_SECONDS = 5 * 60
LOCKOUT_SECONDS = 10 * 60
_locked_until = {}  # ip -> timestamp até quando fica bloqueado


MAX_LOCKOUT_SECONDS = 24 * 3600
STRIKE_MEMORY_SECONDS = 24 * 3600
_strikes = {}  # ip -> (nº de bloqueios recentes, timestamp do último)
_MAX_TRACKED = 5000


def login_is_locked(ip):
    until = _locked_until.get(ip)
    if until and time.time() < until:
        return round(until - time.time())
    return 0


def _prune(now):
    """Impede que o dicionário cresça sem limite se alguém varrer milhares de IPs."""
    if len(_attempts) + len(_locked_until) + len(_strikes) <= _MAX_TRACKED:
        return
    for ip in [i for i, u in _locked_until.items() if u < now]:
        _locked_until.pop(ip, None)
    for ip in [i for i, h in _attempts.items() if not h or now - h[-1] > WINDOW_SECONDS]:
        _attempts.pop(ip, None)
    for ip in [i for i, (_, t) in _strikes.items() if now - t > STRIKE_MEMORY_SECONDS]:
        _strikes.pop(ip, None)


def login_register_failure(ip):
    """Bloqueio por IP com escalonamento: 10 min, depois 20, 40... (máx. 24h)
    para quem volta a errar em seguida. Zera no login correto."""
    now = time.time()
    with _lock:
        hits = [t for t in _attempts.get(ip, []) if now - t < WINDOW_SECONDS]
        hits.append(now)
        _attempts[ip] = hits
        if len(hits) >= MAX_ATTEMPTS:
            count, last = _strikes.get(ip, (0, 0))
            if now - last > STRIKE_MEMORY_SECONDS:
                count = 0
            _locked_until[ip] = now + min(LOCKOUT_SECONDS * (2 ** count), MAX_LOCKOUT_SECONDS)
            _strikes[ip] = (count + 1, now)
            _attempts[ip] = []
        _prune(now)


def login_register_success(ip):
    with _lock:
        _attempts.pop(ip, None)
        _locked_until.pop(ip, None)
        _strikes.pop(ip, None)


# ---------------------------------------------------------- CSRF (token + Origin)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_SESSION_KEY = "_csrf_token"
_CSRF_HEADER = "X-CSRF-Token"
_CSRF_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _flask_state():
    try:
        from flask import has_request_context, g, session
        return has_request_context, g, session
    except Exception:
        return (lambda: False), None, {}

def csrf_token():
    """Retorna um token aleatório por sessão; nunca é gravado em logs."""
    has_ctx, _g, session_obj = _flask_state()
    if not has_ctx():
        return ""
    token = session_obj.get(_CSRF_SESSION_KEY)
    if not token or not _CSRF_RE.fullmatch(str(token)):
        token = uuid.uuid4().hex + uuid.uuid4().hex
        session_obj[_CSRF_SESSION_KEY] = token
    return token


def check_origin(request):
    """Camada adicional de defesa CSRF baseada em Origin/Referer."""
    if request.method not in MUTATING_METHODS:
        return True
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return True
    if origin.strip().lower() == "null":
        return False
    try:
        host = urlparse(origin).netloc
    except Exception:
        return False
    return (not host) or host == request.host


def check_csrf(request):
    """Valida token CSRF no backend para toda mutação.
    O token pode vir no header ou em formulário. Nunca aceita token na URL."""
    if request.method not in MUTATING_METHODS:
        return True
    has_ctx, _g, session_obj = _flask_state()
    if not has_ctx():
        return False
    expected = session_obj.get(_CSRF_SESSION_KEY)
    if not expected or not _CSRF_RE.fullmatch(str(expected)):
        return False
    supplied = request.headers.get(_CSRF_HEADER, "")
    if not supplied and request.form:
        supplied = request.form.get("_csrf", "")
    if not supplied:
        try:
            data = request.get_json(silent=True)
            if isinstance(data, dict):
                supplied = data.get("_csrf", "")
        except Exception:
            supplied = ""
    return bool(_CSRF_RE.fullmatch(str(supplied or ""))) and secrets_compare(supplied, expected)


def secrets_compare(a, b):
    import hmac
    return hmac.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))


# ---------------------------------------------------------- Request ID
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,100}$")


def init_request_id(request):
    """Cria/valida um Request ID sem permitir conteúdo controlado perigoso."""
    incoming = (request.headers.get("X-Request-ID") or "").strip()
    if incoming and _REQUEST_ID_RE.fullmatch(incoming):
        rid = incoming
    else:
        rid = uuid.uuid4().hex
    has_ctx, flask_g, _session = _flask_state()
    if has_ctx():
        flask_g.request_id = rid
    return rid


def request_id():
    has_ctx, flask_g, _session = _flask_state()
    return getattr(flask_g, "request_id", "") if has_ctx() else ""


# ---------------------------------------------------------- audit helper
def audit_event(action, target="", ok=True, role="", error=None, request_id_value=None):
    """Registra evento sensível no audit log existente, sem segredos."""
    try:
        from services import telemetry
        telemetry.log(
            role=role or "",
            session_id="",
            tool=str(action)[:80],
            target=str(target or "")[:300],
            ok=bool(ok),
            duration_ms=0,
            error=(str(error or "")[:300] if error else None),
            request_id=request_id_value if request_id_value is not None else request_id(),
        )
    except Exception:
        pass



def redact_sensitive_text(text):
    """Mascara padrões de credenciais mesmo quando o valor não está no config."""
    if not text:
        return text
    patterns = [
        (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[oculto]"),
        (re.compile(r"(?i)((?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*[\"']?)[^\s\"'&,}\]]+"), r"\1[oculto]"),
        (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[oculto]"),
        (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,})\b"), "[oculto]"),
    ]
    for pattern, repl in patterns:
        text = pattern.sub(repl, text)
    return text


_ALERT_LOCK = threading.Lock()
_ALERT_LAST = {}
_ALERT_COOLDOWN = 300

def security_alerts(limit=50):
    """Deriva alertas do access/audit log existente com cooldown por tipo/alvo."""
    out=[]
    now=time.time()
    try:
        from services import telemetry, access_log
        audit=telemetry.recent(200)
        visits=access_log.recent(300)
        failures=sum(1 for x in visits if x.get("status") in (401,403) and x.get("ts","")[:10] >= time.strftime("%Y-%m-%d"))
        if failures >= 8:
            out.append({"type":"many_auth_failures","severity":"high","message":"Muitas respostas 401/403 recentes."})
        for row in audit:
            tool=str(row.get("tool",""))
            if tool == "ssrf_guard" and not row.get("ok"):
                out.append({"type":"ssrf_blocked","severity":"high","message":"Tentativa SSRF bloqueada pelo guard.","request_id":row.get("request_id","")})
            elif tool in {"ADMIN_ACCESS","API_KEY_CHANGED","PASSWORD_CHANGED"}:
                out.append({"type":tool.lower(),"severity":"high","message":f"Evento sensível: {tool}.","request_id":row.get("request_id","")})
        dedup=[]
        with _ALERT_LOCK:
            for a in out:
                key=(a["type"],a.get("request_id",""))
                if now-_ALERT_LAST.get(key,0) < _ALERT_COOLDOWN:
                    continue
                _ALERT_LAST[key]=now
                dedup.append(a)
        return dedup[-limit:]
    except Exception:
        return []

# ---------------------------------------------------------- security headers
def apply_security_headers(resp, is_https, path=""):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # câmera (gesture-control.js) e microfone (clap-control.js / reconhecimento
    # de voz do Jarvis) são usados pela própria UI, então liberados só para o
    # próprio site; o resto continua bloqueado. Iframes de terceiros não herdam.
    resp.headers.setdefault(
        "Permissions-Policy",
        "camera=(self), microphone=(self), geolocation=(), payment=(), usb=(), "
        "serial=(), bluetooth=(), magnetometer=(), gyroscope=(), accelerometer=()",
    )
    # SAMEORIGIN (não DENY): o editor usa um <iframe> de preview do próprio site.
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    # Isolamento entre origens: outra aba/site não consegue obter referência
    # à janela do painel (COOP) nem embutir/ler nossos recursos (CORP).
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    # A UI usa muito onclick="" e <script> inline nos templates (~57 handlers)
    # — um CSP sem 'unsafe-inline' quebraria praticamente todas as telas. Ainda
    # assim, restringe a origem de scripts/objetos, bloqueia plugins e limita
    # para onde formulários podem enviar dados.
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self'; "
        "frame-src 'self' https://www.youtube.com https://youtube.com https://www.youtube-nocookie.com; "
        "child-src 'self' https://www.youtube.com https://youtube.com https://www.youtube-nocookie.com; "
        "media-src 'self' data: blob: https:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )
    if is_https:
        csp += "; upgrade-insecure-requests"
    resp.headers.setdefault("Content-Security-Policy", csp)
    # Candidate CSP without inline execution. Kept in Report-Only until the
    # legacy inline handlers/scripts are migrated to nonces/hashes; this gives
    # the owner visibility without breaking existing pages.
    strict_report = (
        "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )
    if is_https:
        strict_report += "; upgrade-insecure-requests"
    resp.headers.setdefault("Content-Security-Policy-Report-Only", strict_report)
    if is_https:
        resp.headers.setdefault("Strict-Transport-Security",
                                 "max-age=31536000; includeSubDomains")
    # Páginas e APIs autenticadas não devem ficar em cache (botão "voltar"
    # após logout, computador compartilhado, proxies). Estáticos ficam de fora
    # para manter o cache-busting existente.
    if not path.startswith("/static/"):
        resp.headers.setdefault("Cache-Control", "no-store")
        resp.headers.setdefault("Pragma", "no-cache")
    return resp


# Preview de sites gerados: o HTML/JS ali pode ter sido escrito por convidado
# (token) ou pela IA. Sem sandbox ele rodaria na MESMA origem do painel e
# poderia chamar as APIs com a sessão do owner. `sandbox` (sem
# allow-same-origin) dá ao site uma origem opaca: scripts rodam, mas não
# alcançam cookies, APIs do painel nem localStorage do painel.
PREVIEW_CSP = (
    "sandbox allow-scripts allow-forms allow-popups allow-modals; "
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https:; "
    "style-src 'self' 'unsafe-inline' https:; "
    "img-src 'self' data: blob: https:; "
    "media-src 'self' data: blob: https:; "
    "font-src 'self' data: https:; "
    "connect-src 'none'; "
    "frame-src 'none'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'self'; "
    "navigate-to 'self' https:"
)


# ---------------------------------------------------------- upload de imagem
ALLOWED_IMAGE_FORMATS = {
    "PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif",
    "BMP": ".bmp", "TIFF": ".tiff",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024

def validate_image_upload(file_storage):
    """Valida conteúdo real, formato permitido e tamanho."""
    try:
        stream = file_storage.stream
        pos = stream.tell()
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        if size <= 0 or size > MAX_IMAGE_BYTES:
            return False, "arquivo vazio ou maior que 8 MB."
        from PIL import Image
        img = Image.open(stream)
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            return False, "formato de imagem não permitido."
        img.verify()
        stream.seek(pos)
        return True, None
    except Exception:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        return False, "O conteúdo do arquivo não é uma imagem válida."

def image_extension_from_bytes(content):
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(content))
    fmt = (img.format or "").upper()
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValueError("Formato de imagem não permitido.")
    return ALLOWED_IMAGE_FORMATS[fmt]

def random_asset_name(prefix, extension):
    safe = re.sub(r"[^a-z0-9_-]", "-", str(prefix).lower())[:20] or "asset"
    return f"{safe}-{secrets.token_hex(12)}{extension}"

