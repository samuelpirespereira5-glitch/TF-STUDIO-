"""Ferramentas defensivas adicionais do JARVIS Cyber Lab.

Todas passam por validation.preflight + scope. Nenhuma execução de comando
arbitrário, nenhum ataque a terceiros, nenhum storage de secrets.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from services.cyber.validation import (
    ValidationError,
    preflight,
    safe_finding,
    audit_params,
    content_hash,
    validate_file_content,
    validate_text,
    validate_host,
    validate_url,
    validate_ports,
)
from services.cyber.tool_limits import get_limits
from services.scope import create_connection, ScopeError, clamp_timeout

# Serviços conhecidos (apenas referência, não exploração)
_COMMON_SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 143: "imap", 443: "https", 445: "smb", 3306: "mysql",
    3389: "rdp", 5432: "postgres", 5900: "vnc", 6379: "redis", 8080: "http-alt",
    8443: "https-alt", 27017: "mongodb",
}


def _user_ctx(ctx: dict) -> tuple[str, str]:
    user = (ctx or {}).get("user") or (ctx or {}).get("username") or "anonymous"
    role = (ctx or {}).get("role") or "user"
    return str(user), str(role)


def _error_result(exc: Exception) -> dict:
    if isinstance(exc, ValidationError):
        return {
            "ok": False,
            "error": exc.message,
            "code": getattr(exc, "code", "invalid_input"),
            "findings": [],
            "summary": exc.message,
        }
    if isinstance(exc, ScopeError):
        return {
            "ok": False,
            "error": "Alvo não autorizado",
            "code": "unauthorized_target",
            "findings": [],
            "summary": "Alvo não autorizado",
        }
    return {
        "ok": False,
        "error": "Operação bloqueada pela política de segurança",
        "code": "blocked_policy",
        "findings": [],
        "summary": str(exc)[:300],
    }


# ------------------------------------------------------------------ Port scanner (autorizado)
def port_scanner(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        norm = preflight("port_scanner", p, user_key=user, role=role, context="port_scanner")
        host = norm.get("host")
        if not host:
            raise ValidationError("Entrada inválida: informe host ou alvo autorizado.")
        ports = norm.get("ports") or [80, 443]
        limits = norm["limits"]
        timeout = float(norm["timeout"])
        concurrency = min(int(limits.get("max_concurrency") or 8), 16)
        findings = []
        open_ports = []
        start = time.time()
        # Sequential with small batches to respect concurrency limit (no thread bomb)
        for i in range(0, len(ports), concurrency):
            batch = ports[i : i + concurrency]
            for port in batch:
                if time.time() - start > timeout * max(2, len(ports) / 8):
                    findings.append(safe_finding("info", "Timeout parcial", "Varredura interrompida por limite de tempo."))
                    break
                status = "closed"
                service = _COMMON_SERVICES.get(port, "unknown")
                try:
                    sock = create_connection(host, port, timeout=min(timeout, 3.0), mode="lab", context="port_scanner")
                    sock.close()
                    status = "open"
                    open_ports.append({"port": port, "service": service})
                    findings.append(safe_finding(
                        "medium" if port not in (80, 443) else "info",
                        f"Porta {port}/tcp aberta",
                        f"Serviço provável: {service}. Verifique se a exposição é intencional.",
                        port=port, service=service,
                    ))
                except ScopeError:
                    raise
                except Exception:
                    status = "closed_or_filtered"
            else:
                continue
            break
        summary = f"Varredura em {host}: {len(open_ports)} porta(s) aberta(s) de {len(ports)} testada(s)."
        return {
            "ok": True,
            "summary": summary,
            "findings": findings,
            "raw": {
                "host": host,
                "ports_tested": ports,
                "open": open_ports,
                "duration_sec": round(time.time() - start, 2),
            },
            "audit": audit_params({"host": host, "ports": ports}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ DNS lookup (passivo)
def dns_lookup_tool(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        # DNS passivo: não exige allowlist de laboratório para nomes públicos,
        # mas ainda bloqueia formas ambíguas e metadata via validation.
        host = validate_host(str(p.get("host") or p.get("domain") or ""), require_authorized=False, context="dns_lookup")
        preflight("dns_lookup", {"host": host}, user_key=user, role=role, context="dns_lookup")
        findings = []
        records: dict[str, list] = {"A": [], "AAAA": []}
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip = info[4][0]
                if ":" in ip:
                    if ip not in records["AAAA"]:
                        records["AAAA"].append(ip)
                else:
                    if ip not in records["A"]:
                        records["A"].append(ip)
        except socket.gaierror as e:
            return {
                "ok": False,
                "error": f"Falha na resolução DNS: {e}",
                "code": "dns_error",
                "findings": [],
                "summary": "Não foi possível resolver o domínio.",
            }
        for rr, ips in records.items():
            for ip in ips:
                findings.append(safe_finding("info", f"Registro {rr}", f"{host} → {ip}", rr=rr, ip=ip))
        if not findings:
            findings.append(safe_finding("info", "Sem registros", "Nenhum A/AAAA retornado."))
        return {
            "ok": True,
            "summary": f"DNS {host}: {len(records['A'])} A, {len(records['AAAA'])} AAAA.",
            "findings": findings,
            "raw": {"host": host, "records": records},
            "audit": audit_params({"host": host}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Header analyzer (passivo)
_SECURITY_HEADERS = [
    ("Strict-Transport-Security", "high", "HSTS ausente — recomenda-se max-age adequado."),
    ("Content-Security-Policy", "medium", "CSP ausente — mitiga XSS e injeção de conteúdo."),
    ("X-Content-Type-Options", "low", "X-Content-Type-Options ausente — use nosniff."),
    ("X-Frame-Options", "medium", "X-Frame-Options / frame-ancestors ausente — risco de clickjacking."),
    ("Referrer-Policy", "low", "Referrer-Policy ausente."),
    ("Permissions-Policy", "low", "Permissions-Policy ausente."),
]


def header_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        norm = preflight("header_analyzer", p, user_key=user, role=role, context="header_analyzer")
        url = norm.get("url")
        if not url:
            raise ValidationError("Entrada inválida: informe uma URL autorizada (https://...).")
        limits = norm["limits"]
        timeout = float(norm["timeout"])
        max_bytes = int(limits.get("max_response_bytes") or 256_000)
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        findings = []
        headers_out = {}
        status = None
        try:
            sock = create_connection(host, port, timeout=timeout, mode="lab", context="header_analyzer")
            if parsed.scheme == "https":
                ctx_ssl = ssl.create_default_context()
                sock = ctx_ssl.wrap_socket(sock, server_hostname=host)
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: JARVIS-CyberLab/1.0 (defensive-header-analyzer)\r\n"
                f"Accept: */*\r\n"
                f"Connection: close\r\n\r\n"
            )
            sock.sendall(req.encode("ascii", errors="ignore"))
            sock.settimeout(timeout)
            chunks = []
            total = 0
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
            raw = b"".join(chunks)
            text = raw.decode("iso-8859-1", errors="replace")
            if "\r\n\r\n" in text:
                head, _ = text.split("\r\n\r\n", 1)
            else:
                head = text
            lines = head.split("\r\n")
            if lines:
                m = re.match(r"HTTP/\d\.\d\s+(\d+)", lines[0])
                if m:
                    status = int(m.group(1))
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers_out[k.strip()] = v.strip()[:500]
        except ScopeError:
            raise
        except Exception as e:
            return {
                "ok": False,
                "error": f"Falha ao obter headers: {e}",
                "code": "http_error",
                "findings": [],
                "summary": "Não foi possível analisar os headers.",
            }

        lower = {k.lower(): v for k, v in headers_out.items()}
        for hname, sev, msg in _SECURITY_HEADERS:
            if hname.lower() not in lower:
                findings.append(safe_finding(sev, f"Header ausente: {hname}", msg, header=hname))
            else:
                findings.append(safe_finding("info", f"Header presente: {hname}", lower[hname.lower()][:300], header=hname))

        if "server" in lower:
            findings.append(safe_finding("low", "Header Server exposto", f"Valor: {lower['server'][:200]} — considere ocultar versão."))
        if status:
            findings.append(safe_finding("info", f"HTTP status {status}", f"Resposta inicial {status} para {url}"))

        return {
            "ok": True,
            "summary": f"Headers de {url}: {len(findings)} observações.",
            "findings": findings,
            "raw": {"url": url, "status": status, "headers": headers_out},
            "audit": audit_params({"url": url}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ SSL/TLS analyzer (passivo)
def ssl_tls_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        host = str(p.get("host") or p.get("target") or "")
        if p.get("url"):
            url = validate_url(str(p["url"]), require_authorized=True, context="ssl_tls")
            host = urlparse(url).hostname or host
        host = validate_host(host, require_authorized=True, context="ssl_tls")
        preflight("ssl_tls_analyzer", {"host": host}, user_key=user, role=role, context="ssl_tls")
        port = int(p.get("port") or 443)
        if not 1 <= port <= 65535:
            raise ValidationError("Entrada inválida: porta inválida.")
        timeout = float(get_limits("ssl_tls_analyzer").get("timeout_sec") or 15)
        findings = []
        cert_info = {}
        try:
            ctx_ssl = ssl.create_default_context()
            with create_connection(host, port, timeout=timeout, mode="lab", context="ssl_tls") as raw:
                with ctx_ssl.wrap_socket(raw, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    version = ssock.version()
                    cipher = ssock.cipher()
                    cert_info = {
                        "subject": dict(x[0] for x in (cert.get("subject") or ())),
                        "issuer": dict(x[0] for x in (cert.get("issuer") or ())),
                        "version_tls": version,
                        "cipher": cipher[0] if cipher else None,
                        "notBefore": cert.get("notBefore"),
                        "notAfter": cert.get("notAfter"),
                        "serialNumber": cert.get("serialNumber"),
                    }
                    findings.append(safe_finding("info", f"TLS {version}", f"Cipher: {cipher[0] if cipher else 'n/a'}"))
                    subj = cert_info.get("subject") or {}
                    findings.append(safe_finding("info", "Certificado", f"CN/subject: {subj}"))
                    if version in ("TLSv1", "TLSv1.1", "SSLv3", "SSLv2"):
                        findings.append(safe_finding("high", "Protocolo legado", f"{version} não é recomendado. Use TLS 1.2+."))
        except ScopeError:
            raise
        except ssl.SSLCertVerificationError as e:
            findings.append(safe_finding("high", "Falha na verificação do certificado", str(e)[:400]))
        except Exception as e:
            return {
                "ok": False,
                "error": f"Falha na análise TLS: {e}",
                "code": "tls_error",
                "findings": [],
                "summary": "Não foi possível analisar SSL/TLS.",
            }
        return {
            "ok": True,
            "summary": f"SSL/TLS {host}:{port} — {len(findings)} achados.",
            "findings": findings,
            "raw": {"host": host, "port": port, "cert": cert_info},
            "audit": audit_params({"host": host, "port": port}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Hash analyzer
def hash_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("hash_analyzer", p, user_key=user, role=role, context="hash_analyzer")
        text = p.get("text")
        content = p.get("content") or p.get("file_content")
        if content is not None:
            data = validate_file_content(content, tool_id="hash_analyzer", filename=str(p.get("filename") or ""))
        elif text is not None:
            data = validate_text(text, field="text", max_len=5_000_000).encode("utf-8", errors="replace")
        else:
            raise ValidationError("Entrada inválida: informe texto ou conteúdo de arquivo.")
        results = {
            "md5": hashlib.md5(data).hexdigest(),
            "sha1": hashlib.sha1(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "sha512": hashlib.sha512(data).hexdigest(),
            "size_bytes": len(data),
        }
        findings = [
            safe_finding("info", "MD5", results["md5"]),
            safe_finding("info", "SHA-1", results["sha1"]),
            safe_finding("info", "SHA-256", results["sha256"]),
            safe_finding("info", "SHA-512", results["sha512"]),
            safe_finding("info", "Tamanho", f"{results['size_bytes']} bytes"),
        ]
        return {
            "ok": True,
            "summary": f"Hashes calculados ({results['size_bytes']} bytes).",
            "findings": findings,
            "raw": results,
            "audit": audit_params({"size": results["size_bytes"]}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ File / metadata analyzer
def file_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("file_analyzer", p, user_key=user, role=role, context="file_analyzer")
        content = p.get("content") or p.get("file_content") or p.get("text")
        filename = str(p.get("filename") or "upload.bin")
        if content is None:
            raise ValidationError("Entrada inválida: envie o conteúdo do arquivo.")
        data = validate_file_content(content, tool_id="file_analyzer", filename=filename)
        findings = []
        findings.append(safe_finding("info", "Nome", filename[:200]))
        findings.append(safe_finding("info", "Tamanho", f"{len(data)} bytes"))
        findings.append(safe_finding("info", "SHA-256", hashlib.sha256(data).hexdigest()))
        # Magic bytes
        magic = data[:16].hex() if data else ""
        findings.append(safe_finding("info", "Magic (hex)", magic))
        kind = "desconhecido"
        if data.startswith(b"%PDF"):
            kind = "PDF"
        elif data.startswith(b"\x89PNG"):
            kind = "PNG"
        elif data[:3] == b"\xff\xd8\xff":
            kind = "JPEG"
        elif data.startswith(b"PK"):
            kind = "ZIP/OOXML"
        elif data.startswith(b"{") or data.startswith(b"["):
            kind = "JSON-like"
        elif data[:2] == b"MZ":
            kind = "PE (bloqueado em análise profunda)"
        findings.append(safe_finding("info", "Tipo aparente", kind))
        # Strings legíveis curtas (sanitizadas)
        try:
            text_sample = data[:4000].decode("utf-8", errors="ignore")
            text_sample = re.sub(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text_sample)
            if text_sample.strip():
                findings.append(safe_finding("info", "Amostra de texto", text_sample[:500]))
        except Exception:
            pass
        return {
            "ok": True,
            "summary": f"Arquivo {filename}: {kind}, {len(data)} bytes.",
            "findings": findings,
            "raw": {"filename": filename, "size": len(data), "kind": kind, "sha256": hashlib.sha256(data).hexdigest()},
            "audit": audit_params({"filename": filename, "size": len(data)}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Log analyzer
_SENSITIVE_LOG = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+"
)


def log_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("log_analyzer", p, user_key=user, role=role, context="log_analyzer")
        raw = p.get("log") or p.get("text") or p.get("content")
        if raw is None:
            raise ValidationError("Entrada inválida: cole o conteúdo do log.")
        text = validate_text(raw, field="log", max_len=10_000_000)
        lines = text.splitlines()
        max_lines = int(get_limits("log_analyzer").get("max_lines") or 50_000)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True
        else:
            truncated = False
        # Sanitizar
        clean_lines = [_SENSITIVE_LOG.sub(r"\1=[REDACTED]", ln) for ln in lines]
        error_re = re.compile(r"(?i)\b(error|exception|fail|critical|panic|fatal)\b")
        warn_re = re.compile(r"(?i)\b(warn|warning)\b")
        errors = [ln for ln in clean_lines if error_re.search(ln)]
        warns = [ln for ln in clean_lines if warn_re.search(ln)]
        findings = [
            safe_finding("info", "Linhas analisadas", str(len(clean_lines))),
            safe_finding("medium" if errors else "info", "Linhas com erro", str(len(errors))),
            safe_finding("low" if warns else "info", "Linhas com warning", str(len(warns))),
        ]
        for ln in errors[:15]:
            findings.append(safe_finding("medium", "Erro", ln[:400]))
        for ln in warns[:10]:
            findings.append(safe_finding("low", "Warning", ln[:400]))
        if truncated:
            findings.append(safe_finding("info", "Truncado", f"Apenas as primeiras {max_lines} linhas foram analisadas."))
        return {
            "ok": True,
            "summary": f"Log: {len(clean_lines)} linhas, {len(errors)} erros, {len(warns)} warnings.",
            "findings": findings,
            "raw": {
                "lines": len(clean_lines),
                "errors_count": len(errors),
                "warnings_count": len(warns),
                "sample_errors": errors[:5],
            },
            "audit": audit_params({"lines": len(clean_lines)}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Secrets scanner (estático)
_SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})", "Possível API key"),
    (r"(?i)(secret|password|passwd)\s*[:=]\s*['\"]?(\S{8,})", "Possível senha/secret"),
    (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "Chave privada PEM"),
    (r"(?i)Bearer\s+[A-Za-z0-9\-_\.]{20,}", "Token Bearer"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub PAT"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
]


def secrets_scanner(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("secrets_scanner", p, user_key=user, role=role, context="secrets_scanner")
        raw = p.get("code") or p.get("text") or p.get("content")
        if raw is None:
            raise ValidationError("Entrada inválida: cole o código ou texto a analisar.")
        text = validate_text(raw, field="code", max_len=2_000_000)
        findings = []
        for pat, label in _SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                # Não ecoar o secret completo
                findings.append(safe_finding(
                    "high",
                    label,
                    f"Padrão encontrado na posição {m.start()} (valor omitido nos logs).",
                    position=m.start(),
                ))
                if len(findings) >= 50:
                    break
            if len(findings) >= 50:
                break
        if not findings:
            findings.append(safe_finding("info", "Nenhum padrão óbvio", "Nenhum secret clássico detectado (análise heurística)."))
        return {
            "ok": True,
            "summary": f"Secrets scanner: {len([f for f in findings if f['severity']=='high'])} possíveis secrets.",
            "findings": findings,
            "raw": {"matches": len(findings)},
            "audit": audit_params({"length": len(text)}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Dependency scanner (estático)
def dependency_scanner(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("dependency_scanner", p, user_key=user, role=role, context="dependency_scanner")
        raw = p.get("content") or p.get("text") or p.get("code")
        filename = str(p.get("filename") or "requirements.txt")
        if raw is None:
            raise ValidationError("Entrada inválida: envie requirements.txt, package.json ou similar.")
        text = validate_text(raw, field="content", max_len=2_000_000)
        findings = []
        deps = []
        if "package.json" in filename.lower() or text.strip().startswith("{"):
            try:
                data = json.loads(text)
                for section in ("dependencies", "devDependencies"):
                    for name, ver in (data.get(section) or {}).items():
                        deps.append(f"{name}@{ver}")
                        findings.append(safe_finding("info", f"Dep {section}", f"{name}@{ver}"))
            except json.JSONDecodeError:
                findings.append(safe_finding("low", "JSON inválido", "Não foi possível parsear package.json."))
        else:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                deps.append(line[:200])
                findings.append(safe_finding("info", "Dependência", line[:200]))
        findings.insert(0, safe_finding("info", "Total", f"{len(deps)} dependências listadas. Compare com bases de CVE (ex.: OSV) em ambiente autorizado."))
        findings.append(safe_finding(
            "info",
            "Recomendação",
            "Mantenha dependências atualizadas; use lockfiles e scanners de CVE no CI. Este módulo não consulta bases externas automaticamente.",
        ))
        return {
            "ok": True,
            "summary": f"{len(deps)} dependências identificadas em {filename}.",
            "findings": findings,
            "raw": {"filename": filename, "dependencies": deps[:200]},
            "audit": audit_params({"filename": filename, "count": len(deps)}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ IP analyzer (classificação local)
def ip_analyzer(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("ip_analyzer", p, user_key=user, role=role, context="ip_analyzer")
        raw = str(p.get("ip") or p.get("host") or p.get("target") or "").strip()
        if not raw:
            raise ValidationError("Entrada inválida: informe um IP.")
        import ipaddress
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            # tenta resolver nome apenas se autorizado / público
            host = validate_host(raw, require_authorized=False, context="ip_analyzer")
            try:
                infos = socket.getaddrinfo(host, None)
                ip = ipaddress.ip_address(infos[0][4][0])
            except Exception:
                raise ValidationError("Entrada inválida: IP ou host não resolvível.")
        findings = []
        findings.append(safe_finding("info", "Endereço", str(ip)))
        findings.append(safe_finding("info", "Versão", f"IPv{ip.version}"))
        flags = []
        if ip.is_private:
            flags.append("privado")
        if ip.is_loopback:
            flags.append("loopback")
        if ip.is_link_local:
            flags.append("link-local")
        if ip.is_multicast:
            flags.append("multicast")
        if ip.is_reserved:
            flags.append("reservado")
        if ip.is_global:
            flags.append("global")
        findings.append(safe_finding("info", "Classificação", ", ".join(flags) or "sem flags especiais"))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            findings.append(safe_finding(
                "medium",
                "Escopo interno",
                "Este endereço é interno/link-local. Ferramentas ativas só funcionam se estiver na allowlist do laboratório.",
            ))
        return {
            "ok": True,
            "summary": f"IP {ip}: {', '.join(flags) or 'público/global'}.",
            "findings": findings,
            "raw": {"ip": str(ip), "version": ip.version, "flags": flags},
            "audit": audit_params({"ip": str(ip)}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ API tester (somente autorizados)
def api_tester_safe(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        norm = preflight("api_tester", p, user_key=user, role=role, context="api_tester")
        url = norm.get("url")
        if not url:
            raise ValidationError("Entrada inválida: URL de endpoint autorizado obrigatória.")
        method = str(p.get("method") or "GET").upper()
        if method not in ("GET", "HEAD", "OPTIONS"):
            # Apenas métodos seguros por padrão (sem body mutável)
            raise ValidationError(
                "Operação bloqueada pela política de segurança: apenas GET/HEAD/OPTIONS são permitidos neste modo defensivo.",
                "blocked_policy",
            )
        # Reutiliza header analyzer logic de forma mínima
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        timeout = float(norm["timeout"])
        max_bytes = int(norm["limits"].get("max_response_bytes") or 256_000)
        status = None
        body_sample = ""
        try:
            sock = create_connection(host, port, timeout=timeout, mode="lab", context="api_tester")
            if parsed.scheme == "https":
                ctx_ssl = ssl.create_default_context()
                sock = ctx_ssl.wrap_socket(sock, server_hostname=host)
            req = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: JARVIS-CyberLab/1.0 (defensive-api-tester)\r\n"
                f"Accept: application/json, */*\r\n"
                f"Connection: close\r\n\r\n"
            )
            sock.sendall(req.encode("ascii", errors="ignore"))
            sock.settimeout(timeout)
            chunks = []
            total = 0
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
            raw = b"".join(chunks).decode("utf-8", errors="replace")
            if "\r\n\r\n" in raw:
                head, body = raw.split("\r\n\r\n", 1)
            else:
                head, body = raw, ""
            m = re.match(r"HTTP/\d\.\d\s+(\d+)", head.split("\r\n")[0] if head else "")
            if m:
                status = int(m.group(1))
            body_sample = body[:500]
        except ScopeError:
            raise
        except Exception as e:
            return {
                "ok": False,
                "error": f"Falha na requisição: {e}",
                "code": "http_error",
                "findings": [],
                "summary": "API tester falhou.",
            }
        findings = [
            safe_finding("info", f"Status {status}", f"{method} {url}"),
        ]
        if status and status >= 500:
            findings.append(safe_finding("high", "Erro de servidor", f"HTTP {status}"))
        elif status and status >= 400:
            findings.append(safe_finding("medium", "Erro de cliente", f"HTTP {status}"))
        if body_sample:
            findings.append(safe_finding("info", "Amostra de corpo", body_sample[:300]))
        return {
            "ok": True,
            "summary": f"API {method} {url} → {status}",
            "findings": findings,
            "raw": {"url": url, "method": method, "status": status},
            "audit": audit_params({"url": url, "method": method}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Malware sandbox (stub isolado — sem execução real de malware)
def malware_sandbox(p: dict, ctx: dict) -> dict:
    user, role = _user_ctx(ctx)
    try:
        preflight("malware_sandbox", p, user_key=user, role=role, context="malware_sandbox")
        content = p.get("content") or p.get("file_content")
        filename = str(p.get("filename") or "sample.bin")
        if content is None:
            raise ValidationError("Entrada inválida: envie a amostra (análise estática apenas).")
        data = validate_file_content(content, tool_id="malware_sandbox", filename=filename)
        # Apenas análise estática — NUNCA executa o binário
        sha = hashlib.sha256(data).hexdigest()
        findings = [
            safe_finding("info", "Sandbox", "Ambiente isolado: rede desabilitada, sem execução de código."),
            safe_finding("info", "SHA-256", sha),
            safe_finding("info", "Tamanho", f"{len(data)} bytes"),
            safe_finding("info", "Modo", "Análise estática apenas (política de segurança)."),
        ]
        if data[:2] == b"MZ" or data[:4] == b"\x7fELF":
            findings.append(safe_finding(
                "medium",
                "Binário detectado",
                "Arquivo aparenta ser executável. Execução bloqueada pela política de segurança do laboratório.",
            ))
        return {
            "ok": True,
            "summary": f"Sandbox estático: {filename} ({sha[:16]}…). Nenhuma execução realizada.",
            "findings": findings,
            "raw": {"sha256": sha, "size": len(data), "network": "disabled", "execution": "blocked"},
            "audit": audit_params({"filename": filename, "sha256": sha}),
        }
    except Exception as e:
        return _error_result(e)


# ------------------------------------------------------------------ Registro no registry
def register_defensive_tools(registry) -> None:
    """Registra ferramentas defensivas na Central."""
    R = registry

    def _reg(id, name, category, description, handler, cap="cyber", **kw):
        R.register(
            id=id,
            name=name,
            category=category,
            description=description,
            handler=handler,
            cap=cap,
            kind="analysis",
            persist=True,
            needs_target=kw.get("needs_target", False),
            params=kw.get("params") or {},
            keywords=kw.get("keywords") or [],
            explain=kw.get("explain") or description,
        )

    _reg(
        "port_scanner", "Port Scanner (autorizado)", "rede",
        "Varredura de portas em alvos previamente autorizados. Limite de portas, concorrência e timeout.",
        port_scanner, cap="cyber", needs_target=True,
        params={"host": {"required": True}, "ports": {"required": False, "default": "80,443"}},
        keywords=["porta", "port", "scan", "nmap", "serviço"],
    )
    _reg(
        "dns_lookup_tool", "DNS Lookup", "reconhecimento",
        "Resolução DNS passiva (A/AAAA). Sem enumeração agressiva.",
        dns_lookup_tool, cap="tools_basic",
        params={"host": {"required": True}},
        keywords=["dns", "lookup", "domínio", "resolução"],
    )
    _reg(
        "header_analyzer", "HTTP Headers Analyzer", "web",
        "Análise passiva de headers de segurança em URL autorizada.",
        header_analyzer, cap="cyber", needs_target=True,
        params={"url": {"required": True}},
        keywords=["header", "hsts", "csp", "http", "security headers"],
    )
    _reg(
        "ssl_tls_analyzer", "SSL/TLS Analyzer", "web",
        "Análise de configuração TLS e certificado (sem exploração).",
        ssl_tls_analyzer, cap="cyber", needs_target=True,
        params={"host": {"required": True}, "port": {"required": False, "default": 443}},
        keywords=["ssl", "tls", "certificado", "https"],
    )
    _reg(
        "hash_analyzer", "Hash Analyzer", "criptografia",
        "Cálculo de MD5/SHA1/SHA256/SHA512 com limite de tamanho.",
        hash_analyzer, cap="tools_basic",
        params={"text": {"required": False}, "content": {"required": False}},
        keywords=["hash", "md5", "sha256", "integridade"],
    )
    _reg(
        "file_analyzer", "File / Metadata Analyzer", "forense",
        "Metadados e tipo de arquivo. Bloqueia executáveis perigosos.",
        file_analyzer, cap="tools_basic",
        params={"content": {"required": True}, "filename": {"required": False}},
        keywords=["arquivo", "file", "metadados", "forense"],
    )
    _reg(
        "log_analyzer", "Log Analyzer", "blue_team",
        "Análise de logs com sanitização de dados sensíveis.",
        log_analyzer, cap="cyber",
        params={"log": {"required": True}},
        keywords=["log", "erro", "siem", "blue team"],
    )
    _reg(
        "secrets_scanner", "Secrets Scanner", "blue_team",
        "Detecção heurística de secrets em código/texto (sem armazenar valores).",
        secrets_scanner, cap="cyber",
        params={"code": {"required": True}},
        keywords=["secret", "api key", "password", "vazamento"],
    )
    _reg(
        "dependency_scanner", "Dependency Scanner", "blue_team",
        "Lista dependências de requirements.txt / package.json e recomenda atualização.",
        dependency_scanner, cap="tools_basic",
        params={"content": {"required": True}, "filename": {"required": False}},
        keywords=["dependência", "cve", "npm", "pip", "supply chain"],
    )
    _reg(
        "ip_analyzer", "IP Analyzer", "reconhecimento",
        "Classificação local de IP (privado, loopback, global, etc.).",
        ip_analyzer, cap="tools_basic",
        params={"ip": {"required": True}},
        keywords=["ip", "privado", "público", "classificação"],
    )
    _reg(
        "api_tester_safe", "API Tester (seguro)", "api_security",
        "GET/HEAD/OPTIONS apenas em endpoints autorizados.",
        api_tester_safe, cap="cyber", needs_target=True,
        params={"url": {"required": True}, "method": {"required": False, "default": "GET"}},
        keywords=["api", "rest", "endpoint", "http"],
    )
    _reg(
        "malware_sandbox", "Malware Sandbox (estático)", "malware_sandbox",
        "Sandbox isolado: análise estática apenas, rede desabilitada, sem execução.",
        malware_sandbox, cap="cyber_advanced",
        params={"content": {"required": True}, "filename": {"required": False}},
        keywords=["malware", "sandbox", "amostra", "estático"],
    )
