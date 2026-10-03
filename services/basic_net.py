"""Ferramentas de rede públicas (as que já existiam em Ferramentas),
agora como funções reutilizáveis — com guard anti-SSRF: não alcançam
localhost, rede privada nem metadata de nuvem."""
import functools
import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin
from datetime import datetime as dt

from services import scope

UA = {"User-Agent": "TF-Studio-Web/1.0"}


def _url(u):
    u = (u or "").strip()
    if not u:
        raise ValueError("Informe uma URL.")
    return u if u.startswith(("http://", "https://")) else "https://" + u


def _host(d):
    d = (d or "").strip().replace("https://", "").replace("http://", "").split("/")[0]
    if not d:
        raise ValueError("Informe um domínio.")
    return d


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect poderia levar a rede interna depois do guard: seguimos
    manualmente, revalidando cada salto."""
    def redirect_request(self, *a, **k):
        return None


class _PinnedHTTP(urllib.request.HTTPHandler):
    """Conecta no IP validado pelo SSRF Guard (modo público)."""
    def http_open(self, req):
        return self.do_open(functools.partial(scope.PinnedHTTPConnection, mode="public"), req)


class _PinnedHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(functools.partial(scope.PinnedHTTPSConnection, mode="public"), req,
                            context=ssl.create_default_context())


MAX_TOTAL_SECONDS = 30


def _open(url, timeout=10, maxhops=4):
    timeout = scope.clamp_timeout(timeout)
    opener = urllib.request.build_opener(_NoRedirect, _PinnedHTTP, _PinnedHTTPS)
    started = time.monotonic()
    for hop in range(maxhops + 1):
        if time.monotonic() - started > MAX_TOTAL_SECONDS:
            raise ValueError("Tempo total excedido.")
        scope.guard_public_fetch(url, context="redirect" if hop else "request")
        try:
            return opener.open(urllib.request.Request(url, headers=UA), timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urljoin(url, e.headers["Location"])
                continue
            raise
    raise ValueError("Redirecionamentos demais.")


def http_headers(url):
    url = _url(url)
    with _open(url) as resp:
        headers = dict(resp.getheaders())
    sec = ["Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
           "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"]
    return {"headers": headers, "security_headers": {h: headers.get(h, "❌ ausente") for h in sec}}


def ssl_check(domain):
    domain = _host(domain).split(":")[0]
    ctx = ssl.create_default_context()
    with scope.create_connection(domain, 443, timeout=10, mode="public", context="ssl_check") as sock:
        with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
            cert = ssock.getpeercert()
    expires = dt.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
    issuer = dict(x[0] for x in cert.get("issuer", []))
    return {"domain": domain, "valid": True, "expires": expires.strftime("%d/%m/%Y"),
            "days_left": (expires - dt.utcnow()).days,
            "issuer": issuer.get("organizationName", issuer.get("commonName", "desconhecido"))}


def robots_check(domain):
    domain = _host(domain)
    url = f"https://{domain}/robots.txt"
    with _open(url) as resp:
        return {"url": url, "status": resp.status, "content": resp.read(20000).decode("utf-8", errors="replace")}


def latency_check(url):
    url = _url(url)
    t0 = time.perf_counter()
    with _open(url) as resp:
        status = resp.status
    return {"url": url, "status": status, "elapsed_ms": round((time.perf_counter() - t0) * 1000)}


def domain_check(domain):
    domain = (domain or "").strip()
    if not domain:
        raise ValueError("Informe um domínio.")
    try:
        scope.guard_public_fetch("https://" + domain)
        return {"domain": domain, "resolves": True}
    except scope.ScopeError as e:
        if "resolver" in str(e):
            return {"domain": domain, "resolves": False}
        raise
