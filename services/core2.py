"""JARVIS Ultra Core 2.0 incremental services.
Reuses existing auth, telemetry, WebAuthn, Security Center and knowledge stores.
Only defensive/local operations are exposed here.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services import auth, telemetry, security, ultra_ops, webauthn_service, mega_expansion

BASE = Path(__file__).resolve().parent.parent


def now():
    return datetime.now(timezone.utc).isoformat()


def _redact(value):
    return security.redact_sensitive_text(str(value or ""))[:500]


def access_audit(limit=150, query=""):
    """Combine existing access + security audit records without secrets."""
    q = str(query or "").strip().lower()[:120]
    rows = []
    for x in auth.list_access_log()[:500]:
        row = {
            "event": x.get("method") or "ACCESS",
            "time": x.get("time"),
            "user": x.get("label") or "account",
            "result": "SUCCESS" if "SUCCESS" in str(x.get("method", "")) else ("FAILURE" if "FAIL" in str(x.get("method", "")) else "INFO"),
            "method": x.get("method"),
            "session": "redacted",
            "device": x.get("user_agent", "")[:120],
            "ip": _mask_ip(x.get("ip", "")),
            "source": "auth",
        }
        rows.append(row)
    for x in telemetry.recent(min(500, max(50, int(limit or 150)))):
        tool = str(x.get("tool") or "AUDIT")
        target = _redact(x.get("target"))
        rows.append({
            "event": tool[:80],
            "time": x.get("ts"),
            "user": x.get("role") or "account",
            "result": "SUCCESS" if x.get("ok") else "FAILURE",
            "method": tool[:80],
            "session": "redacted",
            "device": "not stored",
            "ip": "not stored",
            "source": "security",
            "target": target,
            "request_id": str(x.get("request_id") or "")[:40],
        })
    if q:
        rows = [r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
    rows.sort(key=lambda r: r.get("time") or "", reverse=True)
    return rows[: max(1, min(int(limit or 150), 300))]


def _mask_ip(ip):
    ip = str(ip or "")
    if not ip:
        return "UNKNOWN"
    if "." in ip:
        p = ip.split(".")
        if len(p) == 4:
            return ".".join(p[:2] + ["***", "***"])
    if ":" in ip:
        return "masked-ipv6"
    return "masked"


def security_overview():
    """Use the existing real baseline where possible; never invent PASS."""
    try:
        baseline = ultra_ops.baseline()
    except Exception:
        baseline = []
    by_name = {str(x.get("control")): x for x in baseline if isinstance(x, dict)}
    controls = [
        "Authentication", "2FA", "RBAC", "CSRF", "Secure Cookies", "HttpOnly",
        "SameSite", "CSP", "Rate Limit", "Session Timeout", "Audit Logs",
        "Secret Management", "Upload Restrictions", "Error Handling", "WebAuthn",
    ]
    ws = webauthn_service.status()
    result = []
    for name in controls:
        if name == "WebAuthn":
            status = "PASS" if ws.get("enabled") and ws.get("dependency") and ws.get("configured") else "NOT TESTED"
            evidence = "Passkey disabled or runtime dependency/configuration unavailable." if status != "PASS" else "WebAuthn dependency/configuration available."
        else:
            item = by_name.get(name, {})
            status = str(item.get("status") or "NOT TESTED").upper()
            if status not in {"PASS", "WARNING", "FAIL", "NOT TESTED", "NOT CHECKED"}:
                status = "NOT TESTED"
            if status == "NOT CHECKED":
                status = "NOT TESTED"
            evidence = str(item.get("evidence") or "No local evidence available.")[:300]
        result.append({"control": name, "status": status, "evidence": evidence})
    counts = {k: sum(1 for x in result if x["status"] == k) for k in ("PASS", "WARNING", "FAIL", "NOT TESTED")}
    return {"controls": result, "counts": counts, "generated_at": now()}


def system_overview():
    try:
        services = mega_expansion.service_status()
    except Exception:
        services = []
    try:
        ws = webauthn_service.status()
    except Exception:
        ws = {"enabled": False, "configured": False, "dependency": False}
    return {
        "generated_at": now(),
        "services": services,
        "webauthn": ws,
        "audit_entries": len(telemetry.recent(1)),
        "environment": os.getenv("FLASK_ENV") or "UNKNOWN",
    }


def knowledge_search(query, limit=20):
    q = " ".join(str(query or "").lower().split())[:180]
    if not q:
        return {"query": "", "results": []}
    topics = mega_expansion.knowledge()
    # A compact internal knowledge layer. It complements, rather than replaces, existing articles.
    details = {
        "csrf": ("Web Security", "CSRF explora a confiança que um site deposita no navegador autenticado. Tokens anti-CSRF e SameSite ajudam a reduzir o risco.", "Use tokens vinculados à sessão e valide Origin/Referer quando apropriado.", "Ataques CSRF podem induzir ações autenticadas.", "Nunca confie apenas no frontend."),
        "flask": ("Flask", "Flask é um microframework Python para aplicações web com rotas, templates, sessões e extensões.", "Uma rota recebe uma requisição e retorna uma resposta.", "Configuração insegura de sessões e entradas pode introduzir falhas.", "Mantenha secrets no ambiente e valide entradas no servidor."),
        "dns": ("Networking", "DNS traduz nomes de domínio em registros como endereços IP.", "example.com pode resolver para um endereço A/AAAA.", "Configurações incorretas podem causar indisponibilidade ou exposição.", "Valide respostas e mantenha registros sob controle."),
        "webauthn": ("Authentication", "WebAuthn permite autenticação com credenciais de chave pública vinculadas a uma origem.", "O servidor gera um challenge e verifica a resposta com a chave pública cadastrada.", "A validação incorreta de origem, RP ID ou challenge compromete a cerimônia.", "Use biblioteca confiável e valide challenge, origin, RP ID e contador."),
        "api": ("APIs", "Uma API define como sistemas trocam dados e operações de forma estruturada.", "GET /items pode retornar uma coleção de recursos.", "Autorização, validação e rate limit são áreas comuns de risco.", "Valide autorização no backend e limite entradas e requisições."),
    }
    out = []
    for key, (cat, expl, ex, risk, good) in details.items():
        if q in key or q in cat.lower() or q in expl.lower():
            out.append({"id": key, "title": key.upper(), "category": cat, "concept": expl, "example": ex, "risk": risk, "best_practice": good})
    for t in topics:
        hay = " ".join(str(t.get(k, "")) for k in ("id", "title", "category", "description")).lower()
        if q in hay and not any(x.get("id") == t.get("id") for x in out):
            out.append({"id": t.get("id"), "title": t.get("title"), "category": t.get("category"), "concept": t.get("description"), "example": "Consulte o material do tópico.", "risk": "Verifique o contexto antes de aplicar mudanças.", "best_practice": "Prefira práticas documentadas e validação em ambiente de laboratório."})
    return {"query": q, "results": out[:max(1, min(int(limit or 20), 50))]}


def crypto_info():
    return {
        "status": "ACTIVE",
        "library": "Python standard library + existing WebAuthn library when enabled",
        "hashes": ["SHA-256", "SHA-512", "SHA-1 (legacy identification)", "MD5 (legacy identification)"],
        "encoding": ["Base64"],
        "generators": ["UUID", "secure random token"],
        "webauthn": webauthn_service.status(),
        "secret_values_exposed": False,
        "key_material": "NOT DISPLAYED",
    }


def crypto_operation(operation, value="", algorithm="sha256"):
    op = str(operation or "").lower().strip()
    value = str(value or "")
    if len(value.encode("utf-8")) > 256 * 1024:
        raise ValueError("Entrada excede 256 KiB.")
    if op == "hash":
        algo = algorithm.lower().replace("-", "")
        allowed = {"sha256": hashlib.sha256, "sha512": hashlib.sha512, "sha1": hashlib.sha1, "md5": hashlib.md5}
        if algo not in allowed:
            raise ValueError("Algoritmo não permitido.")
        return {"operation": "hash", "algorithm": algo.upper(), "digest": allowed[algo](value.encode()).hexdigest(), "reversible": False}
    if op == "base64_encode":
        return {"operation": op, "result": base64.b64encode(value.encode()).decode("ascii")}
    if op == "base64_decode":
        try:
            raw = base64.b64decode(value.encode("ascii"), validate=True)
            return {"operation": op, "result": raw.decode("utf-8", errors="replace")}
        except Exception as exc:
            raise ValueError("Base64 inválido.") from exc
    if op == "uuid":
        return {"operation": op, "result": str(uuid.uuid4())}
    if op == "secure_token":
        return {"operation": op, "result": secrets.token_urlsafe(32), "note": "Gerado no servidor; não é armazenado."}
    raise ValueError("Operação criptográfica não reconhecida.")


def file_hash_bytes(data: bytes, algorithm="sha256"):
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Arquivo excede 10 MiB.")
    algo = str(algorithm or "sha256").lower().replace("-", "")
    allowed = {"sha256": hashlib.sha256, "sha512": hashlib.sha512, "sha1": hashlib.sha1, "md5": hashlib.md5}
    if algo not in allowed:
        raise ValueError("Algoritmo não permitido.")
    return {"algorithm": algo.upper(), "size": len(data), "digest": allowed[algo](data).hexdigest()}
