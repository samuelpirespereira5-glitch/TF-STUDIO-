"""Papéis e permissões — validados SEMPRE no backend.

Papéis:
  owner  -> acesso total (senha mestre)
  admin  -> ferramentas avançadas, Cyber Lab, Creator, diagnósticos
  user   -> só ferramentas básicas liberadas
  guest  -> acesso por token de uso único (só criação de 1 site)

Esconder botão no front NÃO protege nada: toda rota sensível passa por
`require_cap(...)` ou pelo mapa de prefixos em `enforce_path()`.
"""
from functools import wraps

from flask import request, session, jsonify

ROLES = ("owner", "admin", "user", "guest")

CAPS = {
    "owner": {
        "chat", "tools_basic", "tools_advanced", "cyber", "cyber_targets", "cyber_advanced",
        "creator", "settings", "diagnostics", "manage_tools", "manage_access",
        "workspace_write", "workspace_exec", "thm_lab", "developer",
    },
    # Admin continua existindo para tarefas não sensíveis, mas não recebe
    # nenhuma capacidade de proprietário. Funções Cyber/diagnóstico/
    # desenvolvimento/configuração avançada são exclusivas do owner.
    "admin": {
        "chat", "tools_basic", "creator",
    },
    "user": {"chat", "tools_basic"},
    "guest": {"chat"},
}

# Prefixo de rota -> capacidade exigida. O primeiro que casar vale.
PATH_CAPS = (
    ("/api/jarvis/developer", "developer"),
    ("/api/admin", "manage_access"),
    ("/api/cyber", "cyber"),
    ("/cyber", "cyber"),
    ("/api/security/scan-project", "cyber_advanced"),
    ("/api/security", "cyber"),
    ("/api/thm", "thm_lab"),
    ("/api/kali", "cyber_advanced"),
    ("/thm", "thm_lab"),
    ("/api/creator", "creator"),
    ("/api/workspace/write", "workspace_write"),
    ("/api/workspace/exec", "workspace_exec"),
    ("/api/diagnostics", "diagnostics"),
    ("/desafios", "tools_basic"),
    ("/security-center", "cyber_advanced"),
    ("/api/security-center", "cyber_advanced"),
    ("/security-scan", "cyber_advanced"),
    ("/configuracoes", "settings"),
    ("/api/settings", "settings"),
)


def _is_local_request():
    """Loopback direto, sem proxy na frente (proxy reverso no mesmo host
    também chega como 127.0.0.1 — por isso X-Forwarded-For desqualifica)."""
    if request.headers.get("X-Forwarded-For") or request.headers.get("Forwarded"):
        return False
    return (request.remote_addr or "") in ("127.0.0.1", "::1")


def current_role():
    from services import auth as auth_service

    # Não existe mais modo aberto/local. Papel é resolvido exclusivamente
    # pela identidade de sessão armazenada no backend. Valores como
    # tf_role/isOwner enviados ou adulterados no cliente não são fonte de
    # autorização.
    if not auth_service.has_master_password():
        return None
    if not session.get("tf_authed"):
        return None
    identity = auth_service.get_auth_session(session.get("tf_sid", ""))
    if not identity:
        return None
    return identity.get("role")


def has_cap(cap, role=None):
    role = role or current_role()
    return bool(role) and cap in CAPS.get(role, set())


def caps_for(role):
    return sorted(CAPS.get(role, set()))


def _deny(cap):
    role = current_role()
    msg = f"Permissão negada: seu papel ({role or 'anônimo'}) não tem acesso a '{cap}'."
    # Registrar toda tentativa negada no backend. Não confiar em logs do
    # frontend, pois o cliente pode ser adulterado. Falha de logging nunca
    # deve transformar uma negativa de autorização em erro 500.
    try:
        from services import auth as auth_service
        from services import security
        auth_service.log_access(
            "ACCESS_DENIED",
            label=f"{request.method} {request.path} | cap={cap} | role={role or 'anonymous'}",
            ip=security.client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
        )
    except Exception:
        pass
    if request.path.startswith("/api/"):
        return jsonify({"error": msg, "capability": cap, "role": role}), 403
    return msg, 403


def require_cap(cap):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not has_cap(cap):
                return _deny(cap)
            return fn(*a, **kw)
        return wrapper
    return deco


def enforce_path():
    """Chamado em before_request: aplica PATH_CAPS a qualquer rota."""
    path = request.path
    for prefix, cap in PATH_CAPS:
        if path.startswith(prefix):
            if not has_cap(cap):
                return _deny(cap)
            return None
    return None
