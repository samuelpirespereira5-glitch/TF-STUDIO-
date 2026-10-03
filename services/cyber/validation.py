"""Validação rigorosa de parâmetros para TODAS as ferramentas do Cyber Lab.

Antes de qualquer execução:
- Validar IP, domínio, URL, porta, arquivo e parâmetros
- Rejeitar entradas inválidas, ambiguidades e parâmetros perigosos
- Aplicar timeout, tamanho máximo e rate limit
- Impedir execução de comandos arbitrários
- Separar análise passiva de ativa
- Bloquear localhost/redes internas/metadata quando não autorizados
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import time
from typing import Any
from urllib.parse import urlparse

from services.scope import (
    ScopeError,
    check_host,
    check_url,
    check_name_only,
    clamp_timeout,
    canonical_url,
)
from services.cyber.tool_limits import (
    check_rate_limit,
    enforce_size,
    get_limits,
    requires_authorized_target,
)

# Padrões perigosos — nunca aceitar como comando ou path
_DANGEROUS_PATTERNS = re.compile(
    r"(;|\||&|`|\$\(|\$\{|<\(|>\(|\n|\r|\\x00|"
    r"\b(rm\s+-rf|mkfs|dd\s+if=|curl\s+.*\|.*sh|wget\s+.*\|.*sh|"
    r"python\s+-c|perl\s+-e|ruby\s+-e|nc\s+-|ncat\s+|bash\s+-i|sh\s+-i)\b)",
    re.IGNORECASE,
)

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)
_IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_PORT_RE = re.compile(r"^\d{1,5}$")

# Extensões bloqueadas para file analyzer (executáveis / scripts perigosos)
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".msi", ".scr", ".com", ".pif", ".cpl", ".jar", ".apk", ".sh", ".bash",
}


class ValidationError(Exception):
    """Erro de validação legível para o usuário."""
    def __init__(self, message: str, code: str = "invalid_input"):
        super().__init__(message)
        self.code = code
        self.message = message


def _reject_dangerous(text: str, field: str = "parâmetro") -> None:
    if not text:
        return
    if _DANGEROUS_PATTERNS.search(text):
        raise ValidationError(
            f"Operação bloqueada pela política de segurança: {field} contém padrão não permitido.",
            "blocked_policy",
        )
    if "\x00" in text:
        raise ValidationError("Entrada inválida: caractere nulo não permitido.", "invalid_input")


def validate_host(host: str, *, require_authorized: bool = True, context: str = "") -> str:
    host = (host or "").strip().lower().rstrip(".")
    if not host or len(host) > 253:
        raise ValidationError("Entrada inválida: host/domínio obrigatório e com até 253 caracteres.")
    _reject_dangerous(host, "host")
    if host in ("localhost", "localhost.localdomain"):
        if require_authorized:
            try:
                check_host(host, context=context or "validate_host")
            except ScopeError as e:
                raise ValidationError("Alvo não autorizado", "unauthorized_target") from e
        return host
    # IP literal
    try:
        ip = ipaddress.ip_address(host)
        if require_authorized:
            try:
                check_host(str(ip), context=context or "validate_host")
            except ScopeError as e:
                raise ValidationError("Alvo não autorizado", "unauthorized_target") from e
        return str(ip)
    except ValueError:
        pass
    if not _HOST_RE.match(host):
        raise ValidationError("Entrada inválida: domínio inválido.")
    if require_authorized:
        try:
            check_host(host, context=context or "validate_host")
        except ScopeError as e:
            raise ValidationError("Alvo não autorizado", "unauthorized_target") from e
    else:
        try:
            check_name_only(host, context=context or "validate_host")
        except ScopeError as e:
            raise ValidationError(str(e) or "Alvo não autorizado", "unauthorized_target") from e
    return host


def validate_url(url: str, *, require_authorized: bool = True, context: str = "") -> str:
    url = (url or "").strip()
    if not url or len(url) > 2048:
        raise ValidationError("Entrada inválida: URL obrigatória e com até 2048 caracteres.")
    _reject_dangerous(url, "url")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Entrada inválida: use apenas http:// ou https://.")
    if parsed.username or parsed.password:
        raise ValidationError("Operação bloqueada pela política de segurança: URL com credenciais não é aceita.", "blocked_policy")
    if require_authorized:
        try:
            check_url(url, context=context or "validate_url")
            return canonical_url(url, context=context or "validate_url")
        except ScopeError as e:
            raise ValidationError("Alvo não autorizado", "unauthorized_target") from e
    try:
        return canonical_url(url, context=context or "validate_url")
    except ScopeError as e:
        raise ValidationError(str(e) or "Entrada inválida", "invalid_input") from e


def validate_port(port: Any) -> int:
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValidationError("Entrada inválida: porta deve ser um número entre 1 e 65535.")
    if not 1 <= p <= 65535:
        raise ValidationError("Entrada inválida: porta deve ser um número entre 1 e 65535.")
    return p


def validate_ports(ports_raw: Any, max_ports: int = 64) -> list[int]:
    if ports_raw is None or ports_raw == "":
        return [80, 443]
    if isinstance(ports_raw, int):
        return [validate_port(ports_raw)]
    if isinstance(ports_raw, (list, tuple)):
        items = list(ports_raw)
    else:
        text = str(ports_raw).strip()
        _reject_dangerous(text, "portas")
        items = re.split(r"[\s,;]+", text)
    out = []
    for item in items:
        if not item and item != 0:
            continue
        s = str(item).strip()
        if "-" in s and s.count("-") == 1:
            a, b = s.split("-")
            lo, hi = validate_port(a), validate_port(b)
            if hi < lo:
                lo, hi = hi, lo
            if hi - lo + 1 > max_ports:
                raise ValidationError(f"Entrada inválida: intervalo de portas excede o máximo de {max_ports}.")
            out.extend(range(lo, hi + 1))
        else:
            out.append(validate_port(s))
        if len(out) > max_ports:
            raise ValidationError(f"Limite de requisições: no máximo {max_ports} portas por varredura.")
    # unique preserve order
    seen = set()
    unique = []
    for p in out:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    if not unique:
        raise ValidationError("Entrada inválida: nenhuma porta válida informada.")
    if len(unique) > max_ports:
        raise ValidationError(f"Limite de requisições: no máximo {max_ports} portas por varredura.")
    return unique


def validate_text(text: Any, *, field: str = "texto", max_len: int = 100_000, allow_empty: bool = False) -> str:
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    if not allow_empty and not text.strip():
        raise ValidationError(f"Entrada inválida: {field} é obrigatório.")
    if len(text) > max_len:
        raise ValidationError(f"Entrada inválida: {field} excede {max_len} caracteres.")
    _reject_dangerous(text, field)
    return text


def validate_file_content(
    content: bytes | str,
    *,
    tool_id: str = "file_analyzer",
    filename: str = "",
) -> bytes:
    if isinstance(content, str):
        content = content.encode("utf-8", errors="replace")
    if not isinstance(content, (bytes, bytearray)):
        raise ValidationError("Entrada inválida: conteúdo de arquivo inválido.")
    content = bytes(content)
    ok, msg = enforce_size(tool_id, len(content))
    if not ok:
        raise ValidationError(msg, "invalid_input")
    limits = get_limits(tool_id)
    if limits.get("block_executables") and filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in BLOCKED_EXTENSIONS:
            raise ValidationError(
                "Operação bloqueada pela política de segurança: tipo de arquivo não permitido para análise.",
                "blocked_policy",
            )
    # Magic bytes básicos de PE/ELF
    if limits.get("block_executables"):
        if content[:2] == b"MZ" or content[:4] == b"\x7fELF":
            raise ValidationError(
                "Operação bloqueada pela política de segurança: executável detectado.",
                "blocked_policy",
            )
    return content


def preflight(
    tool_id: str,
    params: dict,
    *,
    user_key: str = "anonymous",
    role: str = "user",
    context: str = "",
) -> dict:
    """Validação comum antes de executar qualquer ferramenta.

    Retorna dict com campos normalizados ou levanta ValidationError.
    """
    limits = get_limits(tool_id)
    ok, msg = check_rate_limit(tool_id, user_key, role)
    if not ok:
        raise ValidationError(msg, "rate_limited")

    result: dict[str, Any] = {
        "tool_id": tool_id,
        "timeout": clamp_timeout(limits.get("timeout_sec", 10)),
        "limits": limits,
        "require_auth": requires_authorized_target(tool_id),
    }

    # Host / target
    host = params.get("host") or params.get("target") or params.get("domain") or ""
    url = params.get("url") or ""
    if url:
        result["url"] = validate_url(
            url,
            require_authorized=result["require_auth"],
            context=context or tool_id,
        )
        parsed = urlparse(result["url"])
        result["host"] = parsed.hostname or ""
    elif host:
        result["host"] = validate_host(
            str(host),
            require_authorized=result["require_auth"],
            context=context or tool_id,
        )

    # Portas
    if "ports" in params or "port" in params:
        max_p = int(limits.get("max_ports") or 64)
        raw = params.get("ports", params.get("port"))
        result["ports"] = validate_ports(raw, max_ports=max_p)

    # Texto / código / log
    for key in ("text", "code", "log", "content", "headers"):
        if key in params and params[key] is not None:
            max_len = int(limits.get("max_lines") or 50_000) * 200
            max_len = min(max_len, int(limits.get("max_file_bytes") or 2_000_000))
            result[key] = validate_text(params[key], field=key, max_len=max_len, allow_empty=True)

    return result


def safe_finding(severity: str, title: str, detail: str, **extra) -> dict:
    """Cria finding sanitizado (sem secrets)."""
    def _sanitize(s: str, n: int = 2000) -> str:
        s = re.sub(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*\S+",
                   r"\1=[REDACTED]", str(s or ""))
        return s[:n]

    return {
        "severity": severity if severity in ("critical", "high", "medium", "low", "info") else "info",
        "title": _sanitize(title, 200),
        "detail": _sanitize(detail, 4000),
        **{k: v for k, v in extra.items() if k not in ("password", "token", "secret", "cookie")},
    }


def audit_params(params: dict) -> dict:
    """Cópia de parâmetros para log — nunca inclui secrets."""
    forbidden = {"password", "passwd", "secret", "token", "api_key", "apikey", "cookie", "authorization", "auth"}
    out = {}
    for k, v in (params or {}).items():
        if k.lower() in forbidden or any(f in k.lower() for f in ("password", "secret", "token", "cookie")):
            out[k] = "[REDACTED]"
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v if not isinstance(v, str) or len(v) < 500 else v[:500] + "…"
        elif isinstance(v, (list, tuple)):
            out[k] = list(v)[:50]
        else:
            out[k] = type(v).__name__
    return out


def content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    return hashlib.sha256(data).hexdigest()
