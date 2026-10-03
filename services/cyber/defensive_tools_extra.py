"""Parte 2 — ferramentas defensivas adicionais / aprofundadas.

Subdomínios (allowlist), HTTP scanner, config checker, code scanner,
service banner, cookie analyzer — todos com validation + scope.
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import time
from urllib.parse import urlparse

from services.cyber.validation import (
    ValidationError,
    preflight,
    safe_finding,
    audit_params,
    validate_host,
    validate_url,
    validate_text,
)
from services.cyber.tool_limits import get_limits
from services.scope import create_connection, ScopeError

# Wordlist curta e segura — apenas nomes comuns, sem brute force massivo
_SUBDOMAIN_WORDLIST = [
    "www", "mail", "api", "dev", "staging", "test", "admin", "app",
    "cdn", "static", "blog", "shop", "portal", "vpn", "docs", "status",
]


def _user_ctx(ctx):
    user = (ctx or {}).get("user") or (ctx or {}).get("username") or "anonymous"
    role = (ctx or {}).get("role") or "user"
    return str(user), str(role)


def _error_result(exc):
    if isinstance(exc, ValidationError):
        return {"ok": False, "error": exc.message, "code": getattr(exc, "code", "invalid_input"),
                "findings": [], "summary": exc.message}
    if isinstance(exc, ScopeError):
        return {"ok": False, "error": "Alvo não autorizado", "code": "unauthorized_target",
                "findings": [], "summary": "Alvo não autorizado"}
    return {"ok": False, "error": "Operação bloqueada pela política de segurança",
            "code": "blocked_policy", "findings": [], "summary": str(exc)[:300]}


def subdomain_enum(p, ctx):
    """Enumeração limitada de subdomínios — somente domínio autorizado na allowlist."""
    user, role = _user_ctx(ctx)
    try:
        domain = validate_host(str(p.get("domain") or p.get("host") or ""), require_authorized=True, context="subdomain_enum")
        # domínio base (sem sub)
        if domain.count(".") < 1 and not domain.replace(".", "").isdigit():
            raise ValidationError("Entrada inválida: informe um domínio autorizado (ex.: example.com).")
        preflight("subdomain_enum", {"host": domain}, user_key=user, role=role, context="subdomain_enum")
        limits = get_limits("subdomain_enum")
        max_q = int(limits.get("max_queries") or 50)
        wordlist = list(_SUBDOMAIN_WORDLIST)[:max_q]
        custom = str(p.get("wordlist") or "").strip()
        if custom:
            extra = [w.strip().lower() for w in re.split(r"[\s,;]+", custom) if w.strip()]
            if len(extra) > 20:
                raise ValidationError("Limite de requisições: no máximo 20 nomes customizados.")
            for w in extra:
                if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", w):
                    raise ValidationError(f"Entrada inválida: nome de subdomínio inválido: {w}")
            wordlist = (extra + wordlist)[:max_q]

        found = []
        findings = []
        start = time.time()
        timeout = float(limits.get("timeout_sec") or 10)
        for name in wordlist:
            if time.time() - start > timeout:
                findings.append(safe_finding("info", "Timeout", "Enumeração interrompida por limite de tempo."))
                break
            fqdn = f"{name}.{domain}"
            try:
                # Requer que o FQDN também passe no guard se for conectar;
                # aqui só resolução DNS local — ainda validamos o nome.
                validate_host(fqdn, require_authorized=True, context="subdomain_enum")
                infos = socket.getaddrinfo(fqdn, None)
                ips = sorted({i[4][0] for i in infos})
                found.append({"host": fqdn, "ips": ips})
                findings.append(safe_finding("info", f"Subdomínio: {fqdn}", ", ".join(ips)))
            except (ValidationError, ScopeError, socket.gaierror, OSError):
                continue
        summary = f"Subdomínios em {domain}: {len(found)} encontrado(s) de {len(wordlist)} testados (allowlist)."
        return {
            "ok": True, "summary": summary, "findings": findings,
            "raw": {"domain": domain, "found": found, "tested": len(wordlist)},
            "audit": audit_params({"domain": domain, "tested": len(wordlist)}),
        }
    except Exception as e:
        return _error_result(e)


def http_scanner(p, ctx):
    """Scanner HTTP defensivo: status, redirects, tamanho, headers básicos."""
    user, role = _user_ctx(ctx)
    try:
        from services.cyber.validation import preflight as pf
        norm = pf("http_scanner", p, user_key=user, role=role, context="http_scanner")
        url = norm.get("url")
        if not url:
            raise ValidationError("Entrada inválida: informe URL autorizada.")
        limits = norm["limits"]
        timeout = float(norm["timeout"])
        max_bytes = int(limits.get("max_response_bytes") or 512_000)
        parsed = urlparse(url)
        host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        findings = []
        status = None
        headers = {}
        body_len = 0
        try:
            sock = create_connection(host, port, timeout=timeout, mode="lab", context="http_scanner")
            if parsed.scheme == "https":
                ctx_ssl = ssl.create_default_context()
                sock = ctx_ssl.wrap_socket(sock, server_hostname=host)
            req = (
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                f"User-Agent: JARVIS-CyberLab/1.0 (defensive-http-scanner)\r\n"
                f"Accept: */*\r\nConnection: close\r\n\r\n"
            )
            sock.sendall(req.encode("ascii", errors="ignore"))
            sock.settimeout(timeout)
            chunks, total = [], 0
            while total < max_bytes:
                try:
                    data = sock.recv(8192)
                except Exception:
                    break
                if not data:
                    break
                chunks.append(data)
                total += len(data)
            sock.close()
            raw = b"".join(chunks).decode("iso-8859-1", errors="replace")
            head, _, body = raw.partition("\r\n\r\n")
            body_len = len(body)
            lines = head.split("\r\n")
            m = re.match(r"HTTP/\d\.\d\s+(\d+)", lines[0] if lines else "")
            if m:
                status = int(m.group(1))
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()[:400]
        except ScopeError:
            raise
        except Exception as e:
            return {"ok": False, "error": f"Falha HTTP: {e}", "code": "http_error",
                    "findings": [], "summary": "Scanner HTTP falhou."}

        findings.append(safe_finding("info", f"HTTP {status}", f"{url} — corpo ~{body_len} bytes"))
        if status and 300 <= status < 400:
            loc = headers.get("Location") or headers.get("location")
            findings.append(safe_finding("info", "Redirect", loc or "Location não informado"))
        if status and status >= 500:
            findings.append(safe_finding("high", "Erro de servidor", f"Status {status}"))
        elif status and status >= 400:
            findings.append(safe_finding("medium", "Erro de cliente", f"Status {status}"))
        server = headers.get("Server") or headers.get("server")
        if server:
            findings.append(safe_finding("low", "Server header", server[:200]))
        if "content-security-policy" not in {k.lower() for k in headers}:
            findings.append(safe_finding("medium", "CSP ausente", "Considere Content-Security-Policy."))
        return {
            "ok": True,
            "summary": f"HTTP scan {url} → {status} ({body_len} B)",
            "findings": findings,
            "raw": {"url": url, "status": status, "headers": headers, "body_bytes": body_len},
            "audit": audit_params({"url": url}),
        }
    except Exception as e:
        return _error_result(e)


def config_checker(p, ctx):
    """Análise estática de configs (nginx, apache, .env.example, docker-compose) sem secrets reais."""
    user, role = _user_ctx(ctx)
    try:
        preflight("code_scanner", p, user_key=user, role=role, context="config_checker")
        text = validate_text(p.get("content") or p.get("text") or p.get("code"), field="config", max_len=2_000_000)
        filename = str(p.get("filename") or "config")
        findings = []
        low = text.lower()
        checks = [
            (r"ssl_protocols\s+.*tlsv1[^\.2]", "high", "TLS legado", "Evite TLSv1/TLSv1.1 em ssl_protocols."),
            (r"server_tokens\s+on", "low", "server_tokens on", "Oculte versão do nginx (server_tokens off)."),
            (r"autoindex\s+on", "medium", "autoindex on", "Listagem de diretório habilitada."),
            (r"(?i)password\s*=\s*['\"]?(admin|123456|password|root)\b", "critical", "Senha fraca em config", "Credencial padrão/fraca detectada (padrão)."),
            (r"(?i)debug\s*=\s*true", "high", "Debug habilitado", "Debug não deve estar ativo em produção."),
            (r"(?i)allow.?origin\s*[:=]\s*['\"]?\*", "high", "CORS *", "Access-Control-Allow-Origin permissivo demais."),
            (r"privileged:\s*true", "high", "Container privilegiado", "Evite privileged: true em produção."),
            (r"(?i)aws_secret|private_key|api_key\s*=\s*\S{8,}", "critical", "Possível secret em config", "Remova secrets do arquivo versionado."),
        ]
        for pat, sev, title, detail in checks:
            if re.search(pat, text, re.I):
                findings.append(safe_finding(sev, title, detail))
        if not findings:
            findings.append(safe_finding("info", "Sem achados óbvios", f"Nenhum padrão clássico em {filename}."))
        findings.insert(0, safe_finding("info", "Arquivo", filename[:200]))
        return {
            "ok": True,
            "summary": f"Config check {filename}: {len([f for f in findings if f['severity'] in ('critical','high','medium')])} riscos.",
            "findings": findings,
            "raw": {"filename": filename, "length": len(text)},
            "audit": audit_params({"filename": filename}),
        }
    except Exception as e:
        return _error_result(e)


def code_scanner(p, ctx):
    """SAST leve — padrões inseguros sem executar código."""
    user, role = _user_ctx(ctx)
    try:
        preflight("code_scanner", p, user_key=user, role=role, context="code_scanner")
        text = validate_text(p.get("code") or p.get("text") or p.get("content"), field="code", max_len=2_000_000)
        patterns = [
            (r"\beval\s*\(", "high", "Uso de eval()", "eval permite execução dinâmica e é perigoso com entrada externa."),
            (r"\bexec\s*\(", "high", "Uso de exec()", "exec com dados não confiáveis é risco de RCE."),
            (r"innerHTML\s*=", "medium", "innerHTML", "Prefira textContent ou sanitização para evitar XSS."),
            (r"document\.write\s*\(", "medium", "document.write", "Pode introduzir XSS."),
            (r"pickle\.loads?\s*\(", "high", "pickle.load", "Deserialização pickle é insegura com dados não confiáveis."),
            (r"shell\s*=\s*True", "high", "shell=True", "Evite shell=True com entrada do usuário (command injection)."),
            (r"verify\s*=\s*False", "medium", "TLS verify=False", "Desabilitar verificação TLS facilita MITM."),
            (r"(?i)md5\s*\(", "low", "MD5", "MD5 não é adequado para senhas/integridade crítica."),
            (r"SELECT\s+.+\s+FROM\s+.+\s*\+|f[\"'].*SELECT|%s.*SELECT", "high", "SQL concatenado", "Use queries parametrizadas."),
            (r"password\s*=\s*['\"][^'\"]+['\"]", "high", "Senha hardcoded", "Não armazene senhas no código."),
        ]
        findings = []
        for pat, sev, title, detail in patterns:
            for m in re.finditer(pat, text, re.I | re.M):
                line = text.count("\n", 0, m.start()) + 1
                findings.append(safe_finding(sev, title, f"{detail} (linha ~{line})", line=line))
                if len(findings) >= 40:
                    break
            if len(findings) >= 40:
                break
        if not findings:
            findings.append(safe_finding("info", "Sem padrões críticos", "Nenhum padrão SAST clássico encontrado (heurística)."))
        return {
            "ok": True,
            "summary": f"Code scan: {len(findings)} observação(ões).",
            "findings": findings,
            "raw": {"matches": len(findings)},
            "audit": audit_params({"length": len(text)}),
        }
    except Exception as e:
        return _error_result(e)


def service_banner(p, ctx):
    """Banner grab passivo em porta autorizada (poucos bytes, timeout curto)."""
    user, role = _user_ctx(ctx)
    try:
        host = validate_host(str(p.get("host") or p.get("target") or ""), require_authorized=True, context="service_banner")
        from services.cyber.validation import validate_port
        port = validate_port(p.get("port") or 80)
        preflight("port_scanner", {"host": host, "port": port}, user_key=user, role=role, context="service_banner")
        banner = ""
        try:
            sock = create_connection(host, port, timeout=5.0, mode="lab", context="service_banner")
            sock.settimeout(3.0)
            try:
                sock.sendall(b"\r\n")
            except Exception:
                pass
            try:
                banner = sock.recv(256).decode("utf-8", errors="replace").strip()
            except Exception:
                banner = ""
            sock.close()
        except ScopeError:
            raise
        except Exception as e:
            return {"ok": False, "error": f"Falha ao conectar: {e}", "code": "connect_error",
                    "findings": [], "summary": "Banner não obtido."}
        findings = [
            safe_finding("info", f"{host}:{port}", banner[:200] if banner else "Sem banner (serviço silencioso ou filtrado)"),
        ]
        if banner and re.search(r"(?i)(openssh|apache|nginx|iis|mysql|postfix)", banner):
            findings.append(safe_finding("low", "Serviço identificado", "Versões em banners podem auxiliar inventário — oculte em produção quando possível."))
        return {
            "ok": True,
            "summary": f"Banner {host}:{port}: {(banner[:60] + '…') if len(banner) > 60 else (banner or 'vazio')}",
            "findings": findings,
            "raw": {"host": host, "port": port, "banner": banner[:300]},
            "audit": audit_params({"host": host, "port": port}),
        }
    except Exception as e:
        return _error_result(e)


def cookie_analyzer(p, ctx):
    """Analisa string Set-Cookie / Cookie de forma passiva (sem enviar)."""
    user, role = _user_ctx(ctx)
    try:
        preflight("header_analyzer", p, user_key=user, role=role, context="cookie_analyzer")
        raw = validate_text(p.get("cookie") or p.get("text") or p.get("headers") or "", field="cookie", max_len=50_000)
        findings = []
        # Parse cookies simples
        parts = re.split(r",(?=\s*[^;]+=)|(?=\n)", raw) if raw else []
        if not parts:
            parts = [raw]
        for block in parts:
            block = block.strip()
            if not block or "=" not in block:
                continue
            name = block.split("=", 1)[0].strip()[:80]
            low = block.lower()
            if "httponly" not in low:
                findings.append(safe_finding("medium", f"Cookie {name}: sem HttpOnly", "HttpOnly reduz roubo via XSS."))
            if "secure" not in low:
                findings.append(safe_finding("medium", f"Cookie {name}: sem Secure", "Secure evita envio em HTTP claro."))
            if "samesite" not in low:
                findings.append(safe_finding("low", f"Cookie {name}: sem SameSite", "SameSite mitiga CSRF."))
            if "samesite=none" in low and "secure" not in low:
                findings.append(safe_finding("high", f"Cookie {name}: SameSite=None sem Secure", "Inválido/inseguro na maioria dos browsers."))
        if not findings:
            findings.append(safe_finding("info", "Cookies", "Nenhum problema óbvio ou nenhum cookie informado."))
        return {
            "ok": True,
            "summary": f"Cookie analyzer: {len(findings)} observação(ões).",
            "findings": findings,
            "raw": {"input_length": len(raw)},
            "audit": audit_params({"length": len(raw)}),
        }
    except Exception as e:
        return _error_result(e)


def hardening_checklist(p, ctx):
    """Checklist interativo de hardening (respostas do usuário)."""
    user, role = _user_ctx(ctx)
    try:
        preflight("code_scanner", p, user_key=user, role=role, context="hardening_checklist")
        items = [
            ("https_only", "HTTPS obrigatório / redirect HTTP→HTTPS"),
            ("hsts", "HSTS configurado"),
            ("csp", "Content-Security-Policy"),
            ("mfa", "MFA em contas administrativas"),
            ("backups", "Backups testados e criptografados"),
            ("updates", "Atualizações de SO e dependências em dia"),
            ("least_privilege", "Princípio do menor privilégio"),
            ("logging", "Logs centralizados e retenção definida"),
            ("secrets", "Secrets fora do código (vault/env)"),
            ("waf_or_rate", "Rate limit / WAF em endpoints públicos"),
        ]
        answers = p.get("answers") or {}
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except Exception:
                answers = {}
        findings = []
        done = 0
        for key, label in items:
            val = str(answers.get(key, "")).lower() in ("1", "true", "yes", "sim", "ok")
            if val:
                done += 1
                findings.append(safe_finding("info", f"OK: {label}", "Marcado como implementado."))
            else:
                findings.append(safe_finding("medium", f"Pendente: {label}", "Inclua no plano de correção."))
        score = int(100 * done / len(items))
        findings.insert(0, safe_finding("info", "Score de hardening", f"{score}% ({done}/{len(items)})"))
        return {
            "ok": True,
            "summary": f"Hardening checklist: {score}% completo.",
            "findings": findings,
            "raw": {"score": score, "done": done, "total": len(items)},
            "audit": audit_params({"score": score}),
        }
    except Exception as e:
        return _error_result(e)


def register_defensive_extra(registry):
    R = registry

    def _reg(id, name, category, description, handler, cap="cyber", **kw):
        R.register(
            id=id, name=name, category=category, description=description,
            handler=handler, cap=cap, kind="analysis", persist=True,
            needs_target=kw.get("needs_target", False),
            params=kw.get("params") or {}, keywords=kw.get("keywords") or [],
            explain=kw.get("explain") or description,
        )

    _reg("subdomain_enum", "Subdomain Enumeration (autorizado)", "reconhecimento",
         "Enumeração limitada de subdomínios somente em domínio da allowlist.",
         subdomain_enum, needs_target=True,
         params={"domain": {"required": True}, "wordlist": {"required": False}},
         keywords=["subdomínio", "subdomain", "enum", "recon"])
    _reg("http_scanner", "HTTP Scanner", "web",
         "Status, redirects e headers básicos em URL autorizada.",
         http_scanner, needs_target=True,
         params={"url": {"required": True}},
         keywords=["http", "scan", "status", "web"])
    _reg("config_checker", "Config Checker", "blue_team",
         "Análise estática de configs (nginx, env, compose) em busca de misconfigurações.",
         config_checker, cap="cyber",
         params={"content": {"required": True}, "filename": {"required": False}},
         keywords=["config", "nginx", "hardening", "misconfig"])
    _reg("code_scanner", "Code Scanner (SAST)", "blue_team",
         "Análise estática de código — sem execução.",
         code_scanner, cap="cyber",
         params={"code": {"required": True}},
         keywords=["sast", "código", "code", "eval", "xss"])
    _reg("service_banner", "Service Banner", "rede",
         "Captura de banner em porta de alvo autorizado.",
         service_banner, needs_target=True,
         params={"host": {"required": True}, "port": {"required": True}},
         keywords=["banner", "serviço", "porta"])
    _reg("cookie_analyzer", "Cookie Analyzer", "web",
         "Análise passiva de flags Secure/HttpOnly/SameSite.",
         cookie_analyzer, cap="tools_basic",
         params={"cookie": {"required": True}},
         keywords=["cookie", "httponly", "samesite", "secure"])
    _reg("hardening_checklist", "Hardening Checklist", "blue_team",
         "Checklist de hardening com score e plano de correção.",
         hardening_checklist, cap="tools_basic",
         params={"answers": {"required": False}},
         keywords=["hardening", "checklist", "baseline"])
