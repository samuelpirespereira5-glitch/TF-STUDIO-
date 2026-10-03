import os
import re
import time
import threading
import hashlib
import secrets
from datetime import timedelta
from pathlib import Path

import httpx

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify,
    send_from_directory, send_file, flash, abort, session, g
)
from werkzeug.exceptions import HTTPException

from services.countries import COUNTRY_NAMES
from services.config import (
    CONFIG, save_config, get_api_key, has_any_ai_key, has_custom_ai_provider,
    SECRET_FIELDS, PLAIN_FIELDS, secret_hints, secret_audit, redact_secrets,
)
from services import ai_engine
from services import sites_service as sv
from services import game_creator as game_creator_service
from services import auth as auth_service
from services import webauthn_service
from services import debugger_service
from services import challenges
from services import maps_service
from services import live_data
from services import basic_net
from services import permissions
from services import kali_tools
from services import cyber_challenges
from services import tool_registry
from services.scope import ScopeError
from services.jobs import start_job, set_message, set_progress, get_job
from services.utils import now_text

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
# Produção precisa de uma chave estável para todos os workers.
# Desenvolvimento continua podendo usar uma chave efêmera.
_IS_PRODUCTION = (
    os.getenv("FLASK_ENV", "").strip().lower() == "production"
    or os.getenv("PRODUCTION", "").strip().lower() in {"1", "true", "yes"}
    or any(os.getenv(k) for k in ("RENDER", "RAILWAY_ENVIRONMENT", "DYNO", "FLY_APP_NAME", "K_SERVICE"))
)
_secret_key = os.getenv("SECRET_KEY", "").strip()
if _IS_PRODUCTION and not _secret_key:
    raise RuntimeError("SECRET_KEY é obrigatória em produção. Defina uma chave secreta estável antes de iniciar o servidor.")
if _IS_PRODUCTION and not auth_service.production_auth_ready():
    raise RuntimeError("Credencial mestre obrigatória em produção. Defina MASTER_PASSWORD_HASH antes de iniciar o servidor.")
app.secret_key = _secret_key.encode("utf-8") if _secret_key else os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB de uploads
app.config["MAX_FORM_MEMORY_SIZE"] = 2 * 1024 * 1024
# v33: sem senha mestre, pedir para criar uma no primeiro acesso (FIRST_ACCESS_SETUP=0 volta ao modo aberto antigo)
app.config["FIRST_ACCESS_SETUP"] = os.getenv("FIRST_ACCESS_SETUP", "1").strip().lower() not in {"0", "false", "no", "off"}

# Sessões: HttpOnly já é o padrão do Flask; aqui reforçamos SameSite (mitiga
# CSRF "de tabuleiro") e Secure (cookie só viaja em HTTPS — automático atrás
# de um proxy reverso com TLS; em dev puro HTTP local não muda nada).
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_DEBUG", "0") != "1"
# Sessão persistente: produção usa 30 dias por padrão; ações críticas continuam
# protegidas por step-up. Ajuste com SESSION_HOURS=N.
_default_hours = "720" if _IS_PRODUCTION else "24"
try:
    _hours = max(1, min(int(os.getenv("SESSION_HOURS", _default_hours)), 24 * 30))
except ValueError:
    _hours = 720 if _IS_PRODUCTION else 24
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=_hours)
# Timeout por inatividade (minutos). 0 desliga. Padrão: 7 dias em produção.
try:
    _idle_min = max(0, min(int(os.getenv("SESSION_IDLE_MINUTES", "43200" if _IS_PRODUCTION else "0")), 24 * 60))
except ValueError:
    _idle_min = 43200 if _IS_PRODUCTION else 0
app.config["SESSION_IDLE_SECONDS"] = _idle_min * 60
# Prefixo __Host-: o navegador só aceita o cookie via HTTPS, sem Domain e com
# Path=/, o que impede que um subdomínio vizinho o sobrescreva.
if app.config["SESSION_COOKIE_SECURE"]:
    app.config["SESSION_COOKIE_NAME"] = "__Host-tf_session"

# FORCE_REAUTH=1 no painel do host → invalida TODAS as sessões no próximo boot.
# Use após trocar senha/hash ou se o site "ainda entra direto" por cookie antigo.
if os.getenv("FORCE_REAUTH", "").strip().lower() in {"1", "true", "yes", "on"}:
    try:
        auth_service.bump_session_version()
    except Exception:
        pass

from services import security
from services import access_log as access_log_db
from services import security4
from services import experience6
from services import community_space
from services import community_social

# Trust proxy metadata only when TRUSTED_PROXY_HOPS is explicitly/automatically
# known. This makes request.is_secure and client IP consistent behind PaaS TLS
# proxies without blindly trusting user-supplied X-Forwarded-* headers.
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    if security.TRUSTED_PROXY_HOPS > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=security.TRUSTED_PROXY_HOPS,
            x_proto=security.TRUSTED_PROXY_HOPS,
            x_host=security.TRUSTED_PROXY_HOPS,
        )
except Exception:
    pass


@app.context_processor
def _security_template_context():
    return {"csrf_token": security.csrf_token(), "webauthn_status": webauthn_service.status()}

# ------------------------------------------------------------------
# Rede de segurança: NUNCA deixar uma rota /api/... devolver a página
# HTML padrão de erro do Flask/Werkzeug. O front-end (jarvis.js,
# hologram.js, tools.js etc.) sempre chama resp.json() nas respostas
# dessas rotas — se algo estourar uma exceção não tratada antes de
# chegar num "except" (ex: request.json inválido, timeout de uma
# rota mais lenta, um bug qualquer), o Flask por padrão devolve uma
# paginazinha HTML de erro, e resp.json() explode no navegador com
# "Unexpected token '<', <html>... is not valid JSON" — um erro
# ilegível que não diz nada sobre a causa real. Este handler garante
# que toda rota /api/ sempre responde JSON, com uma mensagem legível.
# Páginas normais (não-API) continuam com o comportamento padrão.
# ------------------------------------------------------------------
@app.errorhandler(Exception)
def _handle_api_errors_as_json(e):
    if not request.path.startswith("/api/"):
        if isinstance(e, HTTPException):
            return e  # mantém 404/403/400 originais em páginas não-API
        raise e
    status = e.code if isinstance(e, HTTPException) else 500
    if isinstance(e, HTTPException):
        message = str(e.description or e.name or "Erro")
    else:
        # Em produção não vaza stack/detalhe interno; só request_id para correlação
        message = "Erro interno no servidor." if _IS_PRODUCTION else (str(e) or "Erro interno no servidor.")
    return jsonify({"error": message, "request_id": security.request_id()}), status


@app.after_request
def _experience6_record_perf(resp):
    started = getattr(g, "jarvis_perf_started", None)
    if started is not None and not request.path.startswith("/static/"):
        experience6.record_request(request.path, request.method, resp.status_code, started)
    return resp


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Request-ID", security.request_id())
    return security.apply_security_headers(resp, request.is_secure, request.path)


@app.after_request
def _redact_json_secrets(resp):
    """Rede de segurança: se alguma resposta JSON ecoar o valor exato de uma
    chave/segredo configurado (ex.: erro de provedor com a chave dentro), ele
    é trocado por [oculto] antes de sair do servidor."""
    try:
        if (resp.mimetype == "application/json" and not resp.direct_passthrough
                and (resp.content_length or 0) < 2_000_000):
            body = resp.get_data(as_text=True)
            clean = security.redact_sensitive_text(redact_secrets(body))
            if clean != body:
                resp.set_data(clean)
    except Exception:
        pass
    return resp


# Registro de acessos (IP real, rota, status). Ignora arquivos estáticos e o
# polling do painel "online" para não inflar o banco.
_ACCESS_LOG_SKIP = ("/static/", "/api/admin/online", "/favicon")


@app.after_request
def _audit_sensitive_route(resp):
    endpoint = request.endpoint or ""
    event_map = {
        "set_master_password": "PASSWORD_CHANGED",
        "new_token": "TOKEN_CREATED",
        "revoke_token": "TOKEN_REVOKED",
        "end_all_sessions": "SESSIONS_REVOKED",
        "settings": "SETTINGS_CHANGED",
        "security_center_site_scan": "SECURITY_SCAN",
        "security_center_site_fix": "SECURITY_FIX_APPLIED",
        "security_center_backup_restore": "BACKUP_RESTORED",
        "security_scan_project": "SECURITY_SCAN",
        "desafio_validar": "CYBER_LAB_VALIDATE",
        "duplicate_site": "SITE_CREATED",
        "delete_site": "SITE_DELETED",
        "publish_site": "SITE_PUBLISHED",
        "editor_save": "SITE_EDITED",
        "editor_ai_edit": "SITE_EDITED",
        "editor_ai_improve": "SITE_EDITED",
        "editor_debug_fix": "SITE_EDITED",
        "upload_site_image": "SITE_EDITED",
        "delete_site_image": "SITE_EDITED",
    }
    action = event_map.get(endpoint)
    if request.path.startswith("/api/admin") and resp.status_code < 400:
        action = "ADMIN_ACCESS"
    if action:
        target = request.view_args.get("slug","") if request.view_args else request.path
        security.audit_event(action, target=target, ok=resp.status_code < 400,
                             role=session.get("tf_role",""))
    return resp


@app.after_request
def _log_visit(resp):
    if not request.path.startswith(_ACCESS_LOG_SKIP):
        access_log_db.record(
            security.client_ip(request), request.method, request.path,
            resp.status_code, role=session.get("tf_role", ""),
            user_agent=request.headers.get("User-Agent", ""),
            request_id=security.request_id(),
        )
    return resp


# ------------------------------------------------------------------
# Cache-busting de arquivos estáticos: sem isso, depois de um deploy
# novo o navegador do usuário às vezes continua usando a versão em
# cache do CSS/JS antigo (ele só troca o que muda de nome), dando a
# impressão de que um ajuste "não entrou" mesmo já estando no ar.
# static_v() gera a mesma URL de sempre, só que com "?v=<timestamp
# do arquivo>" no final — muda sozinho a cada deploy, forçando o
# navegador a buscar a versão nova.
# ------------------------------------------------------------------
@app.template_global()
def static_v(filename):
    path = BASE_DIR / "static" / filename
    try:
        v = int(path.stat().st_mtime)
    except OSError:
        v = 0
    return url_for("static", filename=filename) + f"?v={v}"


@app.template_global()
def has_cap(cap):
    return permissions.has_cap(cap)


# ------------------------------------------------------------------
# Acesso: Senha Mestre + Tokens de uso único
# ------------------------------------------------------------------

# Apenas estes endpoints podem ser acessados SEM sessão válida.
# Qualquer outra rota (incluindo endpoint=None) exige autenticação no backend.
PUBLIC_ENDPOINTS = {
    "login", "login_2fa", "login_webauthn_options", "login_webauthn_verify", "auth_google_start", "auth_google_callback", "auth_github_start", "auth_github_callback", "static", "first_access",
    # Phase 10 — conteúdo educacional e demos públicas (somente leitura)
    "cyber.education_page",
    "cyber.phase10_overview",
    "cyber.phase10_tracks",
    "cyber.phase10_skill_tree",
    "cyber.phase10_learning_map",
    "cyber.phase10_labs_catalog",
    "cyber.phase10_tools_catalog",
    "cyber.phase10_edu_games",
    "cyber.phase10_lesson_public",
    "cyber.phase10_daily_public",
    "cyber.phase10_weekly_public",
    "cyber.phase10_search_public",
    "cyber.phase10_quality",
}
# Prefixos de path que NUNCA devem vazar conteúdo privado antes do login.
_PRIVATE_PATH_PREFIXES = (
    "/api/", "/cyber", "/thm", "/desafios", "/security",
    "/jarvis", "/painel", "/criar", "/sites", "/kali",
    "/holograma", "/settings", "/admin", "/tools",
)
# Endpoints que um acesso via token (uso único, 1 site) pode usar.
TOKEN_SCOPE_ENDPOINTS = {
    "creator", "api_generate_site", "api_job_status",
    "api_business_name", "api_slogan", "api_improve_description",
    "sites_list", "editor", "logout", "dashboard", "jarvis", "api_jarvis",
    "api_lugar_real",
}


def _establish_authenticated_session(role: str, uid: str, token_scope: bool = False):
    """Rotaciona a sessão e registra a identidade/role exclusivamente no backend."""
    old_sid = session.get("tf_sid", "")
    if old_sid:
        try:
            auth_service.revoke_auth_session(old_sid)
        except Exception:
            pass
    sid = auth_service.create_auth_session(uid=uid, role=role, token_scope=token_scope,
                                                  client_ip=security.client_ip(request),
                                                  user_agent=request.headers.get("User-Agent", ""))
    session.clear()
    session["tf_authed"] = True
    session["tf_sid"] = sid
    # Mantidos apenas como dados de apresentação/compatibilidade. A autorização
    # nunca lê estes campos; ela consulta a identidade server-side acima.
    session["tf_role"] = role
    session["tf_uid"] = uid
    session["tf_ver"] = auth_service.current_session_version()
    session["tf_token_scope"] = bool(token_scope)
    session["tf_last_activity"] = time.time()
    session.permanent = True


def _enforce_challenge_instance_access():
    """Protege instâncias de desafios mesmo quando o usuário tenta acessar
    diretamente uma URL /sites/<slug>/..., sem passar pela página /desafios.
    """
    path = request.path
    if not path.startswith("/sites/"):
        return None
    parts = path.split("/")
    if len(parts) < 3 or not parts[2]:
        return None
    slug = parts[2]
    try:
        folder = (sv.SITES_DIR / slug).resolve()
        root = sv.SITES_DIR.resolve()
        if root not in folder.parents or not folder.is_dir():
            return None
        meta = sv.load_metadata(folder) or {}
    except Exception:
        return None
    if not meta.get("challenge_id") and not meta.get("is_challenge"):
        return None
    if not permissions.has_cap("tools_basic"):
        return permissions._deny("tools_basic")
    return None


# Anti Host-header poisoning: se ALLOWED_HOSTS estiver definido (lista separada
# por vírgula, ex.: "meusite.com,www.meusite.com"), qualquer outro Host é
# recusado. Opcional — sem a variável nada muda. Se a hospedagem faz health
# check por outro host/IP interno, inclua-o na lista.
_ALLOWED_HOSTS = {h.strip().lower() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()}


@app.before_request
def _init_security_request():
    security.init_request_id(request)


@app.before_request
def _experience6_start_timer():
    g.jarvis_perf_started = experience6.start_timer()


@app.before_request
def _check_host():
    if _ALLOWED_HOSTS:
        host = re.sub(r":\d+$", "", (request.host or "").lower())
        if host not in _ALLOWED_HOSTS:
            abort(400)


@app.before_request
def _require_login():
    """Autenticação obrigatória ANTES de qualquer conteúdo privado.

    Fluxo:
      1. CSRF em métodos mutáveis
      2. Sem senha mestre → somente /primeiro-acesso local; nenhuma área privada abre
      3. Endpoint público (login, 2FA, static, first_access) → libera
      4. Sem sessão válida → redireciona para /login (backend, não só front)
      5. Sessão invalidada (tf_ver) → limpa e manda para /login
      6. Permissões por papel + challenges + token scope
    """
    # CSRF: token obrigatório + Origin/Referer como segunda camada.
    if request.method in security.MUTATING_METHODS:
        if not security.check_origin(request):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Origem da requisição não confere (proteção CSRF).",
                                "request_id": security.request_id()}), 403
            abort(403)
        if not security.check_csrf(request):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Token CSRF inválido ou ausente.",
                                "request_id": security.request_id()}), 403
            abort(403)

    endpoint = request.endpoint  # pode ser None em 404 / rotas não mapeadas
    is_public = endpoint in PUBLIC_ENDPOINTS
    # Phase 10: leitura pública de educação/labs/tools (GET only, no write)
    if not is_public and request.method == "GET":
        p = request.path or ""
        if p.startswith((
            "/educacao", "/education", "/certificados",
            "/api/cyber/phase10/overview",
            "/api/cyber/phase10/tracks",
            "/api/cyber/phase10/skill-tree",
            "/api/cyber/phase10/learning-map",
            "/api/cyber/phase10/labs",
            "/api/cyber/phase10/tools",
            "/api/cyber/phase10/games",
            "/api/cyber/phase10/lesson/",
            "/api/cyber/phase10/daily-public",
            "/api/cyber/phase10/weekly-public",
            "/api/cyber/phase10/search-public",
            "/api/cyber/phase10/quality",
            "/api/cyber/phase11/",
            "/api/cyber/phase12/",
        )):
            is_public = True
    # Demos educacionais sem persistência (ainda exigem CSRF em mutações)
    if not is_public and request.method == "POST":
        p = request.path or ""
        if p in (
            "/api/cyber/phase10/algorithm-steps",
            "/api/cyber/phase10/hash-demo",
            "/api/cyber/phase10/base64",
            "/api/cyber/phase10/explain-another-way",
            "/api/cyber/phase10/mentor",
        ):
            is_public = True

    if not auth_service.has_master_password():
        # Sem credencial configurada, nenhuma área privada fica aberta.
        # O único fluxo permitido é o primeiro acesso local para criar o hash.
        if is_public:
            return None
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Autenticação não configurada. Crie a senha mestre em /primeiro-acesso.",
                "setup_url": url_for("first_access"),
            }), 401
        return redirect(url_for("first_access"))

    # Com senha mestre configurada: login é obrigatório.
    if is_public:
        return None

    if not session.get("tf_authed"):
        # Log de tentativas anônimas em áreas sensíveis (sem revelar detalhes).
        path = request.path or ""
        if path.startswith(_PRIVATE_PATH_PREFIXES) or path == "/":
            try:
                auth_service.log_access(
                    "ACCESS_DENIED",
                    label=f"{request.method} {path} | role=anonymous | login_required",
                    ip=security.client_ip(request),
                    user_agent=request.headers.get("User-Agent", ""),
                )
            except Exception:
                pass
        if path.startswith("/api/"):
            return jsonify({
                "error": "Autenticação obrigatória. Faça login em /login.",
                "login_url": url_for("login"),
            }), 401
        return redirect(url_for("login", next=path if path != "/" else ""))

    # A role/uid do navegador não é fonte de confiança. A identidade real
    # vem do registro de sessão persistido no backend.
    identity = auth_service.get_auth_session(session.get("tf_sid", ""))
    if identity:
        ok_session, session_reason = auth_service.session_security_check(
            session.get("tf_sid", ""), security.client_ip(request), request.headers.get("User-Agent", "")
        )
        if not ok_session:
            # Mudanças normais de navegador/versão móvel não devem expulsar o usuário.
            # Só rejeita automaticamente sinais fortes (sessão ausente/revogada/expirada).
            # O binding estrito de User-Agent pode ser ativado com STRICT_SESSION_UA_BIND=1.
            strict_ua = os.getenv("STRICT_SESSION_UA_BIND", "0").strip().lower() in {"1", "true", "yes", "on"}
            soft_reasons = {"user_agent_changed"}
            if session_reason in soft_reasons and not strict_ua:
                security.audit_event("SESSION_UA_CHANGED", target=session_reason, ok=True, role="")
            else:
                security.audit_event("SESSION_ANOMALY", target=session_reason, ok=False, role="")
                try:
                    auth_service.log_access("SESSION_REJECTED", label=session_reason,
                                            ip=security.client_ip(request),
                                            user_agent=request.headers.get("User-Agent", ""))
                except Exception:
                    pass
                session.clear()
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Sessão rejeitada por segurança. Faça login novamente.",
                                    "reason": session_reason,
                                    "request_id": security.request_id()}), 401
                return redirect(url_for("login"))
    if not identity:
        session.clear()
        if request.path.startswith("/api/"):
            return jsonify({"error": "Sessão inválida ou expirada. Faça login novamente."}), 401
        return redirect(url_for("login"))
    # Recarimba dados legados a partir do backend para evitar qualquer valor
    # adulterado no cookie/sessão sendo usado por outras partes da aplicação.
    session["tf_role"] = identity["role"]
    session["tf_uid"] = identity["uid"]
    session["tf_token_scope"] = bool(identity.get("token_scope"))
    session["tf_ver"] = identity["version"]

    # Sessão derrubada remotamente ("encerrar todas as sessões").
    if session.get("tf_ver") != auth_service.current_session_version():
        session.clear()
        flash("Sua sessão foi encerrada. Faça login novamente.", "error")
        return redirect(url_for("login"))

    # Timeout por inatividade (além do PERMANENT_SESSION_LIFETIME).
    idle_limit = app.config.get("SESSION_IDLE_SECONDS") or 0
    if idle_limit > 0 and session.get("tf_authed"):
        now_ts = time.time()
        last = session.get("tf_last_activity")
        if last is not None and (now_ts - float(last)) > idle_limit:
            session.clear()
            flash("Sessão expirada por inatividade. Faça login novamente.", "error")
            return redirect(url_for("login"))
        session["tf_last_activity"] = now_ts

    # Primeiro acesso da conta JARVIS: uma única etapa de onboarding após o
    # login. Isso não substitui a autenticação; apenas cria o perfil/personagem.
    try:
        onboarding = community_space.onboarding_state(session.get("tf_uid", "owner"))
        onboarding_endpoints = {
            "community_onboarding_page",
            "api_community_onboarding_state",
            "api_community_onboarding_complete",
        }
        if not onboarding.get("complete") and request.endpoint not in onboarding_endpoints and request.endpoint != "logout":
            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "Finalize o primeiro acesso da sua conta.",
                    "onboarding_required": True,
                    "setup_url": url_for("community_onboarding_page"),
                }), 428
            return redirect(url_for("community_onboarding_page", next=request.path))
    except Exception:
        # O onboarding nunca deve derrubar o login por uma falha de armazenamento.
        pass

    # Permissões por papel — validadas no backend, não só escondidas no front.
    denied = permissions.enforce_path()
    if denied is not None:
        return denied

    # Instâncias de desafios protegidas mesmo com URL direta.
    challenge_guard = _enforce_challenge_instance_access()
    if challenge_guard is not None:
        return challenge_guard

    # Token de uso único: só telas de criação de 1 site.
    if session.get("tf_token_scope"):
        token = session.get("tf_token_id") or session.get("tf_token", "")
        if auth_service.token_site_already_created(token) and request.endpoint == "api_generate_site":
            return jsonify({"error": "Este código de acesso já foi usado para criar um site."}), 403
        if request.endpoint not in TOKEN_SCOPE_ENDPOINTS:
            return redirect(url_for("creator"))

    # Marca "visto por último" para o painel online.
    uid = session.get("tf_uid")
    if uid:
        auth_service.touch_online(
            uid, role=session.get("tf_role", ""),
            ip=security.client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
        )
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth_service.has_master_password():
        return redirect(url_for("first_access"))
    # Já autenticado com sessão válida → não mostra login de novo
    if (
        request.method == "GET"
        and session.get("tf_authed")
        and session.get("tf_ver") == auth_service.current_session_version()
    ):
        return redirect(url_for("dashboard"))
    ip = security.client_ip(request)
    locked_for = security.login_is_locked(ip)
    owner_email = auth_service.get_owner_email()
    if request.method == "POST" and locked_for:
        flash(f"Muitas tentativas. Tente novamente em {locked_for // 60 + 1} min.", "error")
        return render_template("login.html", next=security.safe_next_url(request.args.get("next", ""), ""),
                                locked_seconds=locked_for, owner_email=owner_email), 429
    if request.method == "POST":
        password = request.form.get("password", "")
        token = request.form.get("token", "").strip()
        email = request.form.get("email", "").strip()[:254]
        # limites de tamanho: impede gastar CPU de hash com entradas gigantes
        if len(password) > auth_service.MAX_PASSWORD_LEN:
            password = ""
        token = token[:200]
        ua = request.headers.get("User-Agent", "")
        if email and "@" in email:
            auth_service.set_owner_email(email)
            owner_email = email
        role_key = auth_service.check_role_key(token) if token else None
        if role_key:
            security.login_register_success(ip)
            _establish_authenticated_session(role_key["role"], "key:" + role_key["id"])
            auth_service.log_access(f"chave {role_key['role']}", label=role_key.get("label", ""), ip=ip, user_agent=ua)
            security.audit_event("LOGIN_SUCCESS", target="role_key", ok=True, role=role_key["role"])
            security4.notify("owner", "login", "Login por chave", "Uma chave de acesso foi usada para iniciar uma sessão.", "info")
            return redirect(security.safe_next_url(request.form.get("next"), url_for("dashboard")))
        if password and auth_service.check_master_password(password):
            security.login_register_success(ip)
            if auth_service.totp_is_enabled():
                # Senha confere, mas falta o segundo fator — ainda NÃO marca
                # tf_authed (sessão continua sem acesso a nada até o /login/2fa).
                session.clear()
                session["tf_pending_2fa"] = True
                session["tf_pending_next"] = security.safe_next_url(request.form.get("next"), "")
                session.permanent = True
                auth_service.log_access("senha mestre (aguardando 2FA)", ip=ip, user_agent=ua)
                return redirect(url_for("login_2fa"))
            _establish_authenticated_session("owner", "owner")
            auth_service.log_access("senha mestre", ip=ip, user_agent=ua)
            security.audit_event("LOGIN_SUCCESS", target="password", ok=True, role="owner")
            security4.notify("owner", "login", "Novo login", "Login concluído com senha mestre.", "info")
            return redirect(security.safe_next_url(request.form.get("next"), url_for("dashboard")))
        elif token and auth_service.consume_token(token):
            security.login_register_success(ip)
            _establish_authenticated_session("guest", "key:" + auth_service.token_id(token), token_scope=True)
            session["tf_token_id"] = auth_service.token_id(token)
            auth_service.log_access("token (uso único)", ip=ip, user_agent=ua)
            return redirect(url_for("creator"))
        flash("Senha ou token inválidos, ou o token já foi usado.", "error")
        security.login_register_failure(ip)
        security.audit_event("LOGIN_FAILURE", target="login", ok=False, role="")
        # 401 (e não 200): o log de acessos passa a contar a falha como negada
        safe_next = security.safe_next_url(request.args.get("next", ""), "")
        return render_template("login.html", next=safe_next,
                                locked_seconds=security.login_is_locked(ip), owner_email=owner_email), 401
    safe_next = security.safe_next_url(request.args.get("next", ""), "")
    return render_template("login.html", next=safe_next,
                            locked_seconds=locked_for, owner_email=owner_email)


@app.route("/login/2fa", methods=["GET", "POST"])
def login_2fa():
    """Segundo passo do login quando o 2FA (TOTP) está ativo. Só chega
    aqui depois da senha mestre já ter sido validada (tf_pending_2fa);
    sem isso, não dá acesso a nada — tf_authed continua de fora."""
    if not session.get("tf_pending_2fa"):
        return redirect(url_for("login"))
    ip = security.client_ip(request)
    locked_for = security.login_is_locked(ip)
    if request.method == "POST" and locked_for:
        flash(f"Muitas tentativas. Tente novamente em {locked_for // 60 + 1} min.", "error")
        return render_template("login_2fa.html", locked_seconds=locked_for), 429
    if request.method == "POST":
        code = request.form.get("code", "").strip()[:32]
        ua = request.headers.get("User-Agent", "")
        if code and auth_service.totp_verify_login(code):
            security.login_register_success(ip)
            next_url = security.safe_next_url(session.get("tf_pending_next"), url_for("dashboard"))
            _establish_authenticated_session("owner", "owner")
            auth_service.log_access("senha mestre + 2FA", ip=ip, user_agent=ua)
            security.audit_event("LOGIN_SUCCESS", target="password+totp", ok=True, role="owner")
            security4.notify("owner", "login", "Login com MFA", "Login concluído com senha + segundo fator.", "info")
            return redirect(next_url)
        flash("Código inválido, expirado ou já usado.", "error")
        security.login_register_failure(ip)
        security.audit_event("LOGIN_FAILURE", target="login_2fa", ok=False, role="")
        return render_template("login_2fa.html"), 401
    return render_template("login_2fa.html")


def _webauthn_pending(kind: str, challenge: bytes, **extra):
    """Ceremony state is bound to this signed Flask session and expires quickly."""
    payload = {
        "kind": kind,
        "challenge": webauthn_service.b64u(challenge),
        "expires": time.time() + 120,
        "sid": session.get("tf_sid", ""),
    }
    payload.update(extra)
    session["_webauthn_pending"] = payload
    session.modified = True


def _take_webauthn_pending(kind: str):
    pending = session.pop("_webauthn_pending", None)
    session.modified = True
    if not isinstance(pending, dict) or pending.get("kind") != kind:
        return None
    try:
        if time.time() > float(pending.get("expires", 0)):
            return None
        challenge = webauthn_service.unb64u(pending.get("challenge", ""))
        if len(challenge) != 32:
            return None
        if pending.get("sid", "") != session.get("tf_sid", ""):
            # For anonymous login both values are empty; for authenticated
            # registration/re-authentication this binds the ceremony to the SID.
            return None
        pending["challenge_bytes"] = challenge
        return pending
    except Exception:
        return None


@app.route("/login/webauthn/options", methods=["POST"])
def login_webauthn_options():
    if not webauthn_service.enabled():
        return jsonify({"error": "Passkey indisponível: WebAuthn não está habilitado ou configurado."}), 503
    try:
        if not auth_service.has_webauthn():
            return jsonify({"error": "Passkey indisponível."}), 400
        challenge = webauthn_service.new_challenge()
        _webauthn_pending("login", challenge)
        options = webauthn_service.authentication_options(credential_ids=[], challenge=challenge)
        security.audit_event("PASSKEY_LOGIN_STARTED", target="passkey", ok=True, role="")
        return jsonify(options)
    except Exception as exc:
        security.audit_event("PASSKEY_LOGIN_FAILURE", target="options", ok=False, role="", error=type(exc).__name__)
        return jsonify({"error": "Não foi possível iniciar a autenticação por Passkey."}), 503


@app.route("/login/webauthn/verify", methods=["POST"])
def login_webauthn_verify():
    pending = _take_webauthn_pending("login")
    if not pending or not webauthn_service.enabled():
        security.audit_event("PASSKEY_LOGIN_FAILURE", target="challenge", ok=False, role="")
        return jsonify({"error": "Autenticação por Passkey inválida ou expirada."}), 401
    data = request.get_json(silent=True) or {}
    try:
        cred_id = str(data.get("id") or "").strip()
        credential = {
            "id": cred_id,
            "rawId": data.get("rawId"),
            "response": {
                "clientDataJSON": data.get("response", {}).get("clientDataJSON"),
                "authenticatorData": data.get("response", {}).get("authenticatorData"),
                "signature": data.get("response", {}).get("signature"),
                "userHandle": data.get("response", {}).get("userHandle"),
            },
            "type": data.get("type", "public-key"),
            "clientExtensionResults": data.get("clientExtensionResults", {}),
        }
        stored = auth_service.get_webauthn_credential(cred_id)
        if not stored or not stored.get("verified"):
            raise ValueError("unknown credential")
        user_handle = credential["response"].get("userHandle")
        expected_user_handle = stored.get("user_id", "")
        if user_handle and expected_user_handle and user_handle != expected_user_handle:
            raise ValueError("user binding mismatch")
        verification = webauthn_service.verify_authentication(
            credential,
            challenge=pending["challenge_bytes"],
            public_key=webauthn_service.unb64u(stored["public_key"]),
            sign_count=int(stored.get("sign_count", 0)),
        )
        new_count = int(getattr(verification, "new_sign_count", stored.get("sign_count", 0)))
        if new_count < int(stored.get("sign_count", 0)):
            raise ValueError("invalid sign count")
        if not auth_service.update_webauthn_sign_count(cred_id, new_count):
            raise RuntimeError("credential persistence failure")
        # WebAuthn verification is complete before a new authenticated session is created.
        _establish_authenticated_session("owner", "owner")
        auth_service.log_access("Passkey", ip=security.client_ip(request), user_agent=request.headers.get("User-Agent", ""))
        security.audit_event("PASSKEY_LOGIN_SUCCESS", target="passkey", ok=True, role="owner")
        return jsonify({"ok": True, "redirect": security.safe_next_url(data.get("next"), url_for("dashboard"))})
    except Exception as exc:
        security.audit_event("PASSKEY_LOGIN_FAILURE", target="verify", ok=False, role="", error=type(exc).__name__)
        return jsonify({"error": "Passkey inválida, expirada ou não reconhecida."}), 401


@app.route("/primeiro-acesso", methods=["GET", "POST"])
def first_access():
    """Criação da senha mestre na primeira vez (somente no próprio computador)."""
    if auth_service.has_master_password():
        return redirect(url_for("login"))
    if not permissions._is_local_request():
        return render_template("primeiro_acesso.html", remote=True, min_len=auth_service.MIN_PASSWORD_LEN), 403
    if request.method == "POST":
        pw = request.form.get("master_password", "")
        if pw != request.form.get("confirm_password", ""):
            flash("As duas senhas não são iguais.", "error")
        else:
            ok, msg = auth_service.validate_password_strength(pw)
            if not ok:
                flash(msg, "error")
            elif auth_service.set_master_password(pw):
                email = request.form.get("email", "").strip()[:254]
                if email and "@" in email:
                    auth_service.set_owner_email(email)
                auth_service.bump_session_version()
                _establish_authenticated_session("owner", "owner")
                security.audit_event("MASTER_PASSWORD_CREATED", target="first_access", ok=True, role="owner")
                flash("Senha mestre criada. Da próxima vez o site vai pedir essa senha.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Não consegui salvar a senha. Verifique a permissão da pasta data/.", "error")
    return render_template("primeiro_acesso.html", remote=False, min_len=auth_service.MIN_PASSWORD_LEN)


@app.get("/auth/google/start")
def auth_google_start():
    next_url = security.safe_next_url(request.args.get("next", ""), url_for("dashboard"))
    result = social_auth.start("google", request.url_root, next_url)
    if not result.get("ok"):
        flash(result.get("error", "Login Google indisponível."), "error")
        return redirect(url_for("login"))
    session["oauth_google"] = result["state_data"]
    return redirect(result["url"])


@app.get("/auth/google/callback")
def auth_google_callback():
    state_data = session.pop("oauth_google", None) or {}
    if not state_data or state_data.get("state") != request.args.get("state") or time.time() - float(state_data.get("created", 0)) > 600:
        flash("A autenticação Google expirou. Tente novamente.", "error")
        return redirect(url_for("login"))
    if request.args.get("error"):
        flash("Login Google cancelado.", "error")
        return redirect(url_for("login"))
    try:
        identity = social_auth.exchange_google(request.args.get("code", ""), request.url_root)
        account = social_auth.upsert_account(identity)
        _establish_authenticated_session("user", account["uid"])
        security.login_register_success(security.client_ip(request))
        security.audit_event("LOGIN_SUCCESS", target="google", ok=True, role="user")
        return redirect(state_data.get("next") or url_for("dashboard"))
    except Exception as exc:
        security.login_register_failure(security.client_ip(request))
        security.audit_event("LOGIN_FAILURE", target="google", ok=False, role="")
        flash("Não foi possível concluir o login com Google.", "error")
        return redirect(url_for("login"))


@app.get("/auth/github/start")
def auth_github_start():
    next_url = security.safe_next_url(request.args.get("next", ""), url_for("dashboard"))
    result = social_auth.start("github", request.url_root, next_url)
    if not result.get("ok"):
        flash(result.get("error", "Login GitHub indisponível."), "error")
        return redirect(url_for("login"))
    session["oauth_github"] = result["state_data"]
    return redirect(result["url"])


@app.get("/auth/github/callback")
def auth_github_callback():
    state_data = session.pop("oauth_github", None) or {}
    if not state_data or state_data.get("state") != request.args.get("state") or time.time() - float(state_data.get("created", 0)) > 600:
        flash("A autenticação GitHub expirou. Tente novamente.", "error")
        return redirect(url_for("login"))
    if request.args.get("error"):
        flash("Login GitHub cancelado.", "error")
        return redirect(url_for("login"))
    try:
        identity = social_auth.exchange_github(request.args.get("code", ""), request.url_root)
        account = social_auth.upsert_account(identity)
        _establish_authenticated_session("user", account["uid"])
        security.login_register_success(security.client_ip(request))
        security.audit_event("LOGIN_SUCCESS", target="github", ok=True, role="user")
        return redirect(state_data.get("next") or url_for("dashboard"))
    except Exception:
        security.login_register_failure(security.client_ip(request))
        security.audit_event("LOGIN_FAILURE", target="github", ok=False, role="")
        flash("Não foi possível concluir o login com GitHub.", "error")
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    security.audit_event("LOGOUT", target=request.path, ok=True, role=permissions.current_role() or "")
    try:
        auth_service.revoke_auth_session(session.get("tf_sid", ""))
    except Exception:
        pass
    session.clear()
    # Resposta sem cache para impedir "voltar" do navegador e ver páginas privadas.
    resp = redirect(url_for("login"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ------------------------------------------------------------------
# Início do site = Jarvis (o painel de estatísticas virou /painel)
# Autenticação já é exigida pelo before_request; checagem extra = defesa em profundidade.
# ------------------------------------------------------------------

@app.route("/")
def dashboard():
    # Defesa em profundidade: nunca renderizar o painel sem sessão válida.
    if not session.get("tf_authed"):
        return redirect(url_for("login"))
    sites = sv.list_sites()
    role = permissions.current_role()
    kali = kali_tools.counts()
    kali_status = kali_tools.status_all()
    installed_kali = sum(1 for items in kali_status.values() for item in items if item.get("installed"))
    visible_tools = tool_registry.REGISTRY.list_for(role)
    return render_template(
        "jarvis.html",
        sites=sites,
        jarvis_role=role or "anonymous",
        auth_state=auth_service.auth_config_state(),
        jarvis_stats={
            "sites": len(sites),
            "kali_total": kali["total"],
            "kali_integrated": kali["integrated"],
            "kali_installed": installed_kali,
            "kali_categories": kali["categories"],
            "cyber_challenges": len(cyber_challenges.CATALOG),
            "jarvis_tools": len(visible_tools),
            "security_tools": len([t for t in visible_tools if t.get("category") in ("cyber", "pentest", "external")]),
            "tool_categories": len({t.get("category") for t in visible_tools}),
            "auth_source": auth_service.password_source() or "none",
            "auth_secure": not auth_service.auth_config_state().get("plaintext_active", False),
        },
    )


@app.route("/painel")
def painel():
    # Dashboard principal expandido. A URL existente é preservada.
    if not session.get("tf_authed"):
        return redirect(url_for("login"))
    return render_template("mega_platform.html")


# ------------------------------------------------------------------
# Criador de sites (IA)
# ------------------------------------------------------------------

SECTIONS = [
    "Início / Hero", "Sobre", "Serviços", "Produtos", "Galeria",
    "Depoimentos", "Preços", "Perguntas frequentes", "Contato", "Localização",
    "Equipe", "Portfólio / Projetos", "Blog / Novidades", "Vídeo em destaque",
    "Parceiros / Clientes", "Newsletter",
]
STYLES = [
    "Moderno", "Minimalista", "Elegante", "Divertido", "Corporativo", "Criativo",
    "Futurista / Cyberpunk", "Glassmorphism", "Luxuoso", "Retrô",
]
THEMES = ["Claro", "Escuro", "Escuro neon", "Automático (segue o sistema do visitante)"]
FONTS = [
    "Padrão do sistema", "Inter", "Poppins", "Montserrat",
    "Playfair Display (elegante)", "Space Grotesk (futurista)", "Orbitron (futurista/tech)",
]
EXTRAS = [
    ("whatsapp_float", "💬 Botão flutuante do WhatsApp fixo na tela"),
    ("cookie_banner", "🍪 Banner de cookies (LGPD)"),
    ("scroll_animations", "✨ Animações ao rolar a página (efeito moderno)"),
    ("back_to_top", "⬆ Botão de voltar ao topo"),
]


@app.route("/criar")
def creator():
    return render_template(
        "creator.html",
        sections=SECTIONS,
        styles=STYLES,
        themes=THEMES,
        fonts=FONTS,
        extras=EXTRAS,
        countries=COUNTRY_NAMES,
        has_key=has_any_ai_key(),
    )


SITE_GENERATION_ESTIMATE_SECONDS = 75

SITE_GENERATION_STAGES = [
    (0, "🧠 Analisando os dados do negócio..."),
    (10, "🎨 Montando a estrutura e o estilo do site..."),
    (28, "✍️ Escrevendo os textos..."),
    (50, "🖼 Organizando imagens e seções..."),
    (70, "🔧 Finalizando os últimos detalhes..."),
]


def _site_progress_ticker(job_id, stop_event):
    start = time.time()
    while not stop_event.is_set():
        elapsed = int(time.time() - start)
        stage_text = SITE_GENERATION_STAGES[0][1]
        for secs, text in SITE_GENERATION_STAGES:
            if elapsed >= secs:
                stage_text = text
        set_progress(
            job_id, stage_text,
            elapsed=elapsed, estimate=SITE_GENERATION_ESTIMATE_SECONDS
        )
        stop_event.wait(1)


def _generate_site_job(job_id, form, sections, extras, assets, audit_role="user", audit_request_id=""):
    stop_event = threading.Event()
    ticker = threading.Thread(
        target=_site_progress_ticker, args=(job_id, stop_event), daemon=True
    )
    ticker.start()

    try:
        data = {
            "name": form.get("name", "").strip(),
            "type": form.get("type", "").strip(),
            "whatsapp": form.get("whatsapp", "").strip(),
            "city": form.get("city", "").strip(),
            "instagram": form.get("instagram", "").strip(),
            "tiktok": form.get("tiktok", "").strip(),
            "email": form.get("email", "").strip(),
            "maps": form.get("maps", "").strip(),
            "slogan": form.get("slogan", "").strip(),
            "description": form.get("description", "").strip(),
            "style": form.get("style", STYLES[0]),
            "theme": form.get("theme", THEMES[0]),
            "primary": form.get("primary", "#2563eb"),
            "secondary": form.get("secondary", "#06b6d4"),
            "accent": form.get("accent", "").strip(),
            "font": form.get("font", FONTS[0]),
            "extras": extras or [],
            "sections": sections or [SECTIONS[0]],
            "country": form.get("country", "Brasil"),
        }

        if not data["name"]:
            raise RuntimeError("Digite o nome do negócio.")

        html = ai_engine.generate_site_html(
            data,
            has_logo=bool(assets.get("logo")),
            has_cover=bool(assets.get("cover")),
            gallery_count=len(assets.get("gallery") or []),
        )

        folder = sv.new_site_folder(data["name"])
        html = sv.copy_assets_and_replace(
            html, folder / "assets",
            logo=assets.get("logo"),
            cover=assets.get("cover"),
            gallery=assets.get("gallery"),
        )

        (folder / "index.html").write_text(html, encoding="utf-8")

        metadata = {
            "name": data["name"],
            "netlify_site_id": "",
            "netlify_url": "",
            "netlify_slug": "",
            "created_at": now_text(),
            "updated_at": now_text(),
            "style": data["style"],
            "theme": data["theme"],
            "country": data["country"],
        }
        sv.save_metadata(folder, metadata)
        security.audit_event("SITE_CREATED", target=folder.name, ok=True, role=audit_role, request_id_value=audit_request_id)
        return folder.name
    finally:
        stop_event.set()



@app.route("/criar-jogo")
def game_creator_page():
    """Página do criador de jogos (menu Jogos separado)."""
    return render_template("game_creator.html")


@app.route("/api/game-creator/options")
def api_game_creator_options():
    return jsonify(game_creator_service.options_catalog())


@app.route("/api/game-creator/fill", methods=["POST"])
def api_game_creator_fill():
    data = request.get_json(silent=True) or {}
    return jsonify(game_creator_service.fill_from_description(data.get("description") or ""))


@app.route("/api/game-creator/build", methods=["POST"])
def api_game_creator_build():
    data = request.get_json(silent=True) or {}
    spec = game_creator_service.build_game_spec(data)
    return jsonify({"ok": True, "spec": spec})


@app.route("/api/game-creator/save", methods=["POST"])
def api_game_creator_save():
    data = request.get_json(silent=True) or {}
    spec = game_creator_service.build_game_spec(data)
    user = session.get("user") or session.get("role") or session.get("username") or "guest"
    if isinstance(user, dict):
        user = user.get("id") or user.get("name") or "guest"
    result = game_creator_service.save_game(str(user), spec)
    try:
        from services import new_features as _nf
        _nf.add_xp(str(user), 25, "game_created")
    except Exception:
        pass
    return jsonify(result)


@app.route("/api/game-creator/list")
def api_game_creator_list():
    user = session.get("user") or session.get("role") or session.get("username") or "guest"
    if isinstance(user, dict):
        user = user.get("id") or user.get("name") or "guest"
    return jsonify({"games": game_creator_service.list_games(str(user))})


@app.route("/api/game-creator/load/<game_id>")
def api_game_creator_load(game_id):
    user = session.get("user") or session.get("role") or session.get("username") or "guest"
    if isinstance(user, dict):
        user = user.get("id") or user.get("name") or "guest"
    spec = game_creator_service.load_game(str(user), game_id)
    if not spec:
        return jsonify({"error": "Jogo não encontrado"}), 404
    return jsonify({"ok": True, "spec": spec})


# ---------------------------------------------------------------------------
# Novas funcionalidades (templates, ranking, flashcards, estudo, progresso)
# ---------------------------------------------------------------------------
from services import new_features as nf

def _nf_user():
    user = session.get("user") or session.get("role") or session.get("username") or "guest"
    if isinstance(user, dict):
        user = user.get("id") or user.get("name") or "guest"
    return str(user)


@app.route("/novas")
@app.route("/novas-features")
def novas_features_page():
    return render_template("novas_features.html")


@app.route("/api/nf/templates")
def api_nf_templates():
    return jsonify({"templates": nf.list_game_templates()})


@app.route("/api/nf/assets")
def api_nf_assets():
    cat = request.args.get("category") or None
    return jsonify({"assets": nf.list_assets(cat)})


@app.route("/api/nf/sounds")
def api_nf_sounds():
    return jsonify({"sounds": nf.list_sounds()})


@app.route("/api/nf/ranking")
def api_nf_ranking():
    game_id = request.args.get("game_id")
    if game_id:
        return jsonify({"entries": nf.get_ranking(game_id)})
    return jsonify({"entries": nf.get_global_rankings()})


@app.route("/api/nf/score", methods=["POST"])
def api_nf_score():
    data = request.get_json(silent=True) or {}
    uid = _nf_user()
    username = session.get("username") or session.get("name") or uid
    if isinstance(username, dict):
        username = username.get("name") or uid
    return jsonify(nf.submit_score(
        data.get("game_id") or "unknown",
        uid,
        str(username),
        int(data.get("score") or 0),
        data.get("meta"),
    ))


@app.route("/api/nf/share", methods=["POST"])
def api_nf_share():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.make_public_share(_nf_user(), data.get("game_id") or ""))


@app.route("/jogar/publico/<token>")
def public_play_game(token):
    spec = nf.load_public_game(token)
    if not spec:
        abort(404)
    return render_template("game_creator.html", public_spec=spec, public_mode=True)


@app.route("/api/nf/guided")
def api_nf_guided():
    return jsonify({"projects": nf.list_guided_projects()})


@app.route("/api/nf/guided/<pid>")
def api_nf_guided_one(pid):
    p = nf.get_guided_project(pid)
    if not p:
        return jsonify({"error": "Projeto não encontrado"}), 404
    return jsonify({"project": p})


@app.route("/api/nf/daily")
def api_nf_daily():
    return jsonify({"challenge": nf.get_daily_challenge()})


@app.route("/api/nf/flashcards/decks", methods=["GET", "POST"])
def api_nf_decks():
    uid = _nf_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        return jsonify(nf.create_deck(uid, data.get("name") or "Meu deck"))
    return jsonify({"decks": nf.list_decks(uid)})


@app.route("/api/nf/flashcards/cards", methods=["POST"])
def api_nf_cards():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.add_card(_nf_user(), data.get("deck_id") or "", data.get("front") or "", data.get("back") or ""))


@app.route("/api/nf/flashcards/due/<deck_id>")
def api_nf_due(deck_id):
    return jsonify({"cards": nf.get_due_cards(_nf_user(), deck_id)})


@app.route("/api/nf/flashcards/review", methods=["POST"])
def api_nf_review():
    data = request.get_json(silent=True) or {}
    uid = _nf_user()
    result = nf.review_card(uid, data.get("deck_id") or "", data.get("card_id") or "", int(data.get("quality") or 3))
    if result.get("ok"):
        nf.add_xp(uid, 5, "flashcard")
    return jsonify(result)


@app.route("/api/nf/summary", methods=["POST"])
def api_nf_summary():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.generate_summary(data.get("text") or ""))


@app.route("/api/nf/quiz", methods=["POST"])
def api_nf_quiz():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.generate_quiz(data.get("topic") or "programação", int(data.get("n") or 5)))


@app.route("/api/nf/calendar", methods=["GET", "POST"])
def api_nf_calendar():
    uid = _nf_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        return jsonify(nf.add_study_event(uid, data.get("title") or "", data.get("date") or "", data.get("time") or "09:00", data.get("note") or ""))
    return jsonify({"events": nf.list_study_events(uid)})


@app.route("/api/nf/calendar/toggle", methods=["POST"])
def api_nf_calendar_toggle():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.toggle_study_event(_nf_user(), data.get("event_id") or ""))


@app.route("/api/nf/site-templates")
def api_nf_site_templates():
    return jsonify({"templates": nf.list_site_templates()})


@app.route("/api/nf/progress")
def api_nf_progress():
    return jsonify({"progress": nf.get_progress(_nf_user())})


@app.route("/api/nf/favorite", methods=["POST"])
def api_nf_favorite():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.toggle_favorite(_nf_user(), data.get("type") or "item", data.get("id") or "", data.get("title") or ""))


@app.route("/api/nf/achievements")
def api_nf_achievements():
    return jsonify({"achievements": nf.list_achievements(_nf_user())})


@app.route("/api/nf/quiz/score", methods=["POST"])
def api_nf_quiz_score():
    data = request.get_json(silent=True) or {}
    result = nf.score_quiz(data.get("answers") or [], data.get("questions") or [])
    if result.get("ok"):
        nf.add_xp(_nf_user(), 10 + int(result.get("percent", 0) // 10), "quiz")
    return jsonify(result)


@app.route("/api/nf/site-scaffold/<tpl_id>")
def api_nf_site_scaffold(tpl_id):
    return jsonify(nf.get_site_scaffold(tpl_id))


@app.route("/api/nf/sprites", methods=["GET", "POST"])
def api_nf_sprites():
    uid = _nf_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        return jsonify(nf.save_sprite(uid, data.get("name") or "Sprite", int(data.get("size") or 16), data.get("pixels") or []))
    return jsonify({"sprites": nf.list_sprites(uid)})


@app.route("/api/nf/sprites/<sid>", methods=["GET", "DELETE"])
def api_nf_sprite_one(sid):
    uid = _nf_user()
    if request.method == "DELETE":
        return jsonify(nf.delete_sprite(uid, sid))
    s = nf.load_sprite(uid, sid)
    if not s:
        return jsonify({"error": "Sprite não encontrado"}), 404
    return jsonify({"sprite": s})


@app.route("/api/nf/playground", methods=["GET", "POST"])
def api_nf_playground():
    uid = _nf_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        return jsonify(nf.save_playground(uid, data.get("title") or "", data.get("code") or "", data.get("lang") or "javascript"))
    return jsonify({"items": nf.list_playground(uid)})


@app.route("/api/nf/flashcards/bulk", methods=["POST"])
def api_nf_flash_bulk():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.import_cards_bulk(_nf_user(), data.get("deck_id") or "", data.get("pairs") or []))


@app.route("/api/nf/calendar/delete", methods=["POST"])
def api_nf_calendar_delete():
    data = request.get_json(silent=True) or {}
    return jsonify(nf.delete_study_event(_nf_user(), data.get("event_id") or ""))


@app.route("/sprite-editor")
def sprite_editor_page():
    return render_template("sprite_editor.html")


@app.route("/api/sites/generate", methods=["POST"])
def api_generate_site():
    # se o acesso for por token de uso único, trava para 1 site só
    if session.get("tf_token_scope"):
        token = session.get("tf_token_id") or session.get("tf_token", "")
        if auth_service.token_site_already_created(token):
            return jsonify({"error": "Este código de acesso já foi usado para criar um site."}), 403
        auth_service.mark_token_site_created(token)

    # BUG CORRIGIDO: request.form já pode ser copiado com segurança (é um
    # dicionário já materializado), mas request.files guarda arquivos
    # temporários que o Flask/Werkzeug fecha e apaga assim que esta rota
    # termina — e como o site é gerado depois, numa thread em segundo
    # plano (para não travar a página esperando a IA), o logo/capa/galeria
    # podiam já ter sido apagados na hora de salvar, fazendo a criação do
    # site falhar ou sair sem as imagens. Por isso lemos o CONTEÚDO dos
    # arquivos para a memória agora, ainda dentro da requisição, e só then
    # repassamos os bytes prontos para a thread.
    form = request.form.to_dict()
    sections = request.form.getlist("sections")
    extras = request.form.getlist("extras")

    def read_file(key):
        f = request.files.get(key)
        if not f or not f.filename:
            return None
        ok, reason = security.validate_image_upload(f)
        if not ok:
            raise ValueError(f"Upload rejeitado ({key}): {reason}")
        raw = f.read()
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError(f"Upload rejeitado ({key}): arquivo excede 8 MB.")
        return (f.filename, raw)

    assets = {"logo": read_file("logo"), "cover": read_file("cover"), "gallery": []}
    gallery_files = request.files.getlist("gallery")
    if len(gallery_files) > 8:
        return jsonify({"error": "No máximo 8 imagens na galeria."}), 400
    for f in gallery_files:
        if not f or not f.filename:
            continue
        ok, reason = security.validate_image_upload(f)
        if not ok:
            return jsonify({"error": f"Upload rejeitado (gallery): {reason}"}), 400
        raw = f.read()
        if len(raw) > 8 * 1024 * 1024:
            return jsonify({"error": "Cada imagem da galeria pode ter no máximo 8 MB."}), 400
        assets["gallery"].append((f.filename, raw))

    job_id = start_job(_generate_site_job, form, sections, extras, assets, session.get("tf_role", "user"), security.request_id())
    return jsonify({"job_id": job_id})


@app.route("/api/ai/chat-to-site", methods=["POST"])
def api_chat_to_site():
    text = (request.json or {}).get("message", "").strip()
    if not text:
        return jsonify({"error": "Descreva seu negócio primeiro."}), 400
    try:
        extras_keys = [key for key, _label in EXTRAS]
        result = ai_engine.parse_business_chat(text, SECTIONS, STYLES, extras_keys)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/ai/business-name", methods=["POST"])
def api_business_name():
    description = request.json.get("description", "")
    try:
        return jsonify({"result": ai_engine.generate_business_name(description)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/ai/slogan", methods=["POST"])
def api_slogan():
    data = request.json or {}
    try:
        return jsonify({"result": ai_engine.generate_slogan(data.get("name", ""), data.get("description", ""))})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/ai/improve-description", methods=["POST"])
def api_improve_description():
    text = (request.json or {}).get("text", "")
    try:
        return jsonify({"result": ai_engine.improve_description(text)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------------------
# Jobs (polling)
# ------------------------------------------------------------------

@app.route("/api/jobs/<job_id>")
def api_job_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"status": "error", "error": "Job não encontrado."}), 404
    return jsonify(job)


# ------------------------------------------------------------------
# Meus sites
# ------------------------------------------------------------------

@app.route("/sites")
def sites_list():
    return render_template("sites.html", sites=sv.list_sites())


# ------------------------------------------------------------------
# Security Scan — somente o próprio projeto, sem executar código analisado.
# ------------------------------------------------------------------
@app.route("/security-center")
def security_center_page():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    return render_template("security_center.html", sites=sv.list_sites())


@app.route("/api/security-center/dashboard")
def security_center_dashboard():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    return jsonify(site_security.dashboard())


@app.route("/api/security-center/site/<slug>/scan", methods=["POST"])
def security_center_site_scan(slug):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    data=request.get_json(silent=True) or {}
    mode=str(data.get("mode") or "full").lower()
    if mode not in {"quick","full","hardening","rescan","deep"}:
        return jsonify({"error":"Modo de scan inválido."}),400
    try:
        return jsonify(site_security.scan_and_store(slug, mode=mode, user=session.get("user","owner")))
    except ValueError as e:
        return jsonify({"error":str(e)}),404


@app.route("/api/security-center/site/<slug>/fix", methods=["POST"])
def security_center_site_fix(slug):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    data=request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error":"Confirme explicitamente a aplicação da correção."}),400
    try:
        return jsonify(site_security.apply_fix(slug,str(data.get("finding_id") or ""),
                                               user=session.get("user","owner"),confirm=True))
    except ValueError as e:
        return jsonify({"error":str(e)}),400


@app.route("/api/security-center/site/<slug>/finding/<finding_id>", methods=["GET"])
def security_center_finding(slug, finding_id):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    try:
        result=site_security.scan_site(slug, mode="deep")
    except ValueError as e:
        return jsonify({"error":str(e)}),404
    f=next((x for x in result.get("findings",[]) if x.get("id")==finding_id),None)
    if not f:
        return jsonify({"error":"Achado não encontrado."}),404
    return jsonify({"finding":f,"learn":site_security._LEARN.get(f.get("rule"), {}),"note":"Conteúdo educativo baseado na evidência encontrada; possível/necessita revisão não significa exploração confirmada."})


@app.route("/api/security-center/site/<slug>/report", methods=["GET"])
def security_center_site_report(slug):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    try: return jsonify(site_security.export_report(slug))
    except ValueError as e: return jsonify({"error":str(e)}),404


@app.route("/api/security-center/site/<slug>/backups", methods=["GET"])
def security_center_backups(slug):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    return jsonify({"backups": site_security.list_backups(slug)})


@app.route("/api/security-center/site/<slug>/backups/<backup_name>/restore", methods=["POST"])
def security_center_backup_restore(slug, backup_name):
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    data=request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error":"Confirme explicitamente a restauração do backup."}),400
    try:
        result=site_security.restore_backup(slug, backup_name, user=session.get("tf_role","owner"), confirm=True)
        security.audit_event("BACKUP_RESTORED", target=slug, ok=True, role=session.get("tf_role",""))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error":str(e)}),400


@app.route("/api/security-center/logs", methods=["GET"])
def security_center_logs():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import site_security
    p=site_security._V12_LOG
    if not p.exists(): return jsonify({"logs":[]})
    rows=[]
    for line in p.read_text(encoding="utf-8",errors="replace").splitlines()[-100:]:
        try: rows.append(json.loads(line))
        except Exception: pass
    return jsonify({"logs":rows})


@app.route("/security-scan")
def security_scan_page():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    return render_template("security_scan.html")


@app.route("/api/security/scan-project", methods=["POST"])
def security_scan_project():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import security_scan
    return jsonify(security_scan.scan_project(BASE_DIR))


# ------------------------------------------------------------------
# Desafios práticos: sites com problemas intencionais para investigar,
# corrigir e validar. Reaproveita 100% a infraestrutura de sites já
# existente (pasta em sites/, Editor, Depurador, Pré-visualização,
# publicação) — só adiciona metadados de progresso no site.json.
# ------------------------------------------------------------------
def _challenge_progress():
    """Para cada desafio do catálogo, acha a instância mais recente do
    usuário (se houver) olhando os sites já criados — sem banco novo."""
    by_challenge = {}
    for site in sv.list_sites():
        cid = site.get("challenge_id")
        if not cid:
            continue
        if cid not in by_challenge or site.get("updated_at", "") > by_challenge[cid].get("updated_at", ""):
            by_challenge[cid] = site
    return by_challenge


@app.route("/desafios")
def desafios_page():
    progress = _challenge_progress()
    catalog = challenges.list_catalog()
    earned_xp = 0
    for c in catalog:
        site = progress.get(c["id"])
        c["status"] = site.get("challenge_status") if site else None
        c["slug"] = site.get("slug") if site else None
        c["attempts"] = site.get("challenge_attempts", 0) if site else 0
        if c["status"] == "concluido":
            earned_xp += c.get("xp", 0)
    total_xp = challenges.total_possible_xp()
    # Curva simples de nível: 300 XP por nível, sem teto — só motivacional,
    # não desbloqueia nada (evita a complexidade de um sistema de gates).
    xp_per_level = 300
    level = 1 + earned_xp // xp_per_level
    xp_into_level = earned_xp % xp_per_level
    resolvidos = sum(1 for c in catalog if c["status"] == "concluido")
    difficulties = sorted({c["difficulty"] for c in challenges.CATALOG.values()})
    return render_template(
        "desafios.html", catalog=catalog, categories=challenges.CATEGORIES,
        difficulties=difficulties, earned_xp=earned_xp, total_xp=total_xp,
        level=level, xp_into_level=xp_into_level, xp_per_level=xp_per_level,
        resolvidos=resolvidos, total_desafios=len(catalog),
    )


@app.route("/desafios/<challenge_id>/iniciar", methods=["POST"])
def desafio_iniciar(challenge_id):
    c = challenges.get(challenge_id)
    if not c:
        abort(404)
    # Se já existir uma instância não concluída deste desafio, reaproveita-a
    # em vez de criar site novo toda vez que o usuário clica em "Continuar".
    progress = _challenge_progress()
    existing = progress.get(challenge_id)
    if existing and existing.get("challenge_status") != "concluido":
        return redirect(url_for("editor", slug=existing["slug"]))

    folder = sv.new_site_folder(f"Desafio - {c['title']}")
    (folder / "index.html").write_text(c["html"], encoding="utf-8")
    meta = {
        "name": f"🎯 {c['title']}", "country": "", "style": "desafio",
        "created_at": now_text(), "updated_at": now_text(),
        "netlify_site_id": "", "netlify_url": "", "netlify_slug": "",
        "is_challenge": True, "challenge_id": challenge_id,
        "challenge_status": "em_andamento", "challenge_attempts": 0,
    }
    sv.save_metadata(folder, meta)
    flash(f"Desafio \"{c['title']}\" iniciado — investigue e corrija no Editor.", "success")
    return redirect(url_for("editor", slug=folder.name))


@app.route("/sites/<slug>/desafio/validar", methods=["POST"])
def desafio_validar(slug):
    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    meta = sv.load_metadata(folder)
    challenge_id = meta.get("challenge_id") if meta else None
    if not challenge_id:
        return jsonify({"error": "Este site não é um desafio."}), 400

    html = (folder / "index.html").read_text(encoding="utf-8")
    try:
        result = challenges.validate(challenge_id, html)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    was_completed_before = meta.get("challenge_status") == "concluido"
    meta["challenge_attempts"] = meta.get("challenge_attempts", 0) + 1
    meta["updated_at"] = now_text()
    meta["challenge_last_validation"] = {
        "passed": bool(result["passed"]),
        "checked_at": now_text(),
        "checks": result.get("checks", []),
    }
    if result["passed"]:
        meta["challenge_status"] = "concluido"
        meta["challenge_completed_at"] = now_text()
    elif meta.get("challenge_status") != "concluido":
        meta["challenge_status"] = "em_andamento"
    meta.pop("slug", None)
    sv.save_metadata(folder, meta)
    # XP: informativo pro front comemorar — o total real (usado em /desafios)
    # é sempre recalculado a partir do status salvo, então repetir a
    # validação de um desafio já concluído não infla o XP total do usuário.
    result["xp"] = challenges.xp_for(challenge_id) if result["passed"] else 0
    result["first_time"] = result["passed"] and not was_completed_before
    result["explanation"] = challenges.get(challenge_id).get("explanation", "")
    result["expected_solution"] = challenges.get(challenge_id).get("expected_solution", "")
    result["status"] = "concluido" if result["passed"] else "em_andamento"
    result["attempts"] = meta.get("challenge_attempts", 0)
    result["completed_at"] = meta.get("challenge_completed_at")
    return jsonify(result)



@app.route("/sites/<slug>/preview/")
@app.route("/sites/<slug>/preview/<path:filename>")
def preview_site(slug, filename="index.html"):
    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    resp = send_from_directory(folder, filename)
    if os.getenv("PREVIEW_SANDBOX", "1") != "0":
        resp.headers["Content-Security-Policy"] = security.PREVIEW_CSP
    return resp


@app.route("/sites/<slug>/download")
def download_site(slug):
    try:
        zip_path = sv.zip_site(slug)
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("sites_list"))
    return send_file(zip_path, as_attachment=True, download_name=f"{slug}.zip")


@app.route("/sites/<slug>/duplicate", methods=["POST"])
def duplicate_site(slug):
    try:
        sv.duplicate_site(slug)
        flash("Site duplicado com sucesso.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("sites_list"))


@app.route("/sites/<slug>/delete", methods=["POST"])
def delete_site(slug):
    sv.delete_site(slug)
    flash("Site excluído.", "success")
    return redirect(url_for("sites_list"))


@app.route("/sites/<slug>/translate", methods=["POST"])
def translate_site(slug):
    target_country = request.form.get("country", "Brasil")

    def job(job_id):
        set_message(job_id, f"🌍 Traduzindo site para {target_country}...")
        site = sv.get_site(slug)
        if not site:
            raise RuntimeError("Site não encontrado.")
        src_folder = sv.SITES_DIR / slug
        html = (src_folder / "index.html").read_text(encoding="utf-8")
        translated_html = ai_engine.translate_site_html(html, target_country)

        new_slug = f"{slug}-{target_country.lower().replace(' ', '-')}"
        import shutil
        dst_folder = sv.SITES_DIR / new_slug
        if dst_folder.exists():
            shutil.rmtree(dst_folder)
        shutil.copytree(src_folder, dst_folder)
        (dst_folder / "index.html").write_text(translated_html, encoding="utf-8")

        meta = sv.load_metadata(dst_folder)
        meta["name"] = f"{site['name']} ({target_country})"
        meta["country"] = target_country
        meta["netlify_site_id"] = ""
        meta["netlify_url"] = ""
        meta["netlify_slug"] = ""
        meta["updated_at"] = now_text()
        meta.pop("slug", None)
        sv.save_metadata(dst_folder, meta)
        return dst_folder.name

    job_id = start_job(job)
    return jsonify({"job_id": job_id})


@app.route("/sites/<slug>/publish", methods=["POST"])
def publish_site(slug):
    def job(job_id):
        def status_cb(msg):
            set_message(job_id, msg)
        return sv.publish_to_netlify(slug, status_cb=status_cb)

    job_id = start_job(job)
    return jsonify({"job_id": job_id})


# ------------------------------------------------------------------
# Editor
# ------------------------------------------------------------------

@app.route("/sites/<slug>/editor")
def editor(slug):
    site = sv.get_site(slug)
    if not site:
        abort(404)
    html = (sv.SITES_DIR / slug / "index.html").read_text(encoding="utf-8")
    challenge = challenges.get(site.get("challenge_id")) if site.get("challenge_id") else None
    return render_template("editor.html", site=site, html=html, countries=COUNTRY_NAMES, challenge=challenge)


@app.route("/sites/<slug>/editor/save", methods=["POST"])
def editor_save(slug):
    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    html = request.form.get("html", "")
    (folder / "index.html").write_text(html, encoding="utf-8")
    meta = sv.load_metadata(folder)
    meta["updated_at"] = now_text()
    meta.pop("slug", None)
    sv.save_metadata(folder, meta)
    flash("Alterações salvas.", "success")
    return redirect(url_for("editor", slug=slug))


@app.route("/sites/<slug>/editor/ai-edit", methods=["POST"])
def editor_ai_edit(slug):
    instruction = (request.json or {}).get("instruction", "").strip()
    folder = sv.SITES_DIR / slug

    def job(job_id):
        set_message(job_id, "🤖 Aplicando alteração com IA...")
        if not folder.exists():
            raise RuntimeError("Site não encontrado.")
        if not instruction:
            raise RuntimeError("Escreva o que deseja mudar.")
        current_html = (folder / "index.html").read_text(encoding="utf-8")
        new_html = ai_engine.edit_site_html(current_html, instruction)
        (folder / "index.html").write_text(new_html, encoding="utf-8")
        meta = sv.load_metadata(folder)
        meta["updated_at"] = now_text()
        meta.pop("slug", None)
        sv.save_metadata(folder, meta)
        return new_html

    job_id = start_job(job)
    return jsonify({"job_id": job_id})


@app.route("/sites/<slug>/editor/ai-improve", methods=["POST"])
def editor_ai_improve(slug):
    """A IA analisa o arquivo sozinha e melhora o que achar necessário,
    sem o usuário precisar escrever nenhuma instrução."""
    folder = sv.SITES_DIR / slug

    def job(job_id):
        set_message(job_id, "🤖 Analisando o arquivo e aplicando melhorias...")
        if not folder.exists():
            raise RuntimeError("Site não encontrado.")
        current_html = (folder / "index.html").read_text(encoding="utf-8")
        new_html = ai_engine.auto_improve_site_html(current_html)
        (folder / "index.html").write_text(new_html, encoding="utf-8")
        meta = sv.load_metadata(folder)
        meta["updated_at"] = now_text()
        meta.pop("slug", None)
        sv.save_metadata(folder, meta)
        return new_html

    job_id = start_job(job)
    return jsonify({"job_id": job_id})


@app.route("/sites/<slug>/editor/debug", methods=["GET"])
def editor_debug(slug):
    """Analisa o arquivo de verdade (sem IA) e devolve os problemas encontrados."""
    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    issues = debugger_service.analyze_site(folder)
    return jsonify({"issues": issues})


@app.route("/sites/<slug>/editor/debug/fix", methods=["POST"])
def editor_debug_fix(slug):
    folder = sv.SITES_DIR / slug

    def job(job_id):
        set_message(job_id, "🐞 Analisando o arquivo...")
        if not folder.exists():
            raise RuntimeError("Site não encontrado.")
        issues = debugger_service.analyze_site(folder)
        if not issues:
            raise RuntimeError("Nenhum problema encontrado para corrigir.")
        set_message(job_id, f"🛠 Corrigindo {len(issues)} problema(s) encontrado(s)...")
        current_html = (folder / "index.html").read_text(encoding="utf-8")
        issues_text = debugger_service.format_issues_for_prompt(issues)
        new_html = ai_engine.fix_site_issues(current_html, issues_text)
        (folder / "index.html").write_text(new_html, encoding="utf-8")
        meta = sv.load_metadata(folder)
        meta["updated_at"] = now_text()
        meta.pop("slug", None)
        sv.save_metadata(folder, meta)
        return {"issues_corrigidos": len(issues)}

    job_id = start_job(job)
    return jsonify({"job_id": job_id})


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


@app.route("/sites/<slug>/editor/images", methods=["GET"])
def editor_images(slug):
    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    assets_dir = folder / "assets"
    files = []
    if assets_dir.exists():
        for f in sorted(assets_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(f.name)
    return jsonify({"images": files})


@app.route("/sites/<slug>/editor/images/upload", methods=["POST"])
def editor_images_upload(slug):
    from werkzeug.utils import secure_filename

    folder = sv.SITES_DIR / slug
    if not folder.exists():
        abort(404)
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "Nenhuma imagem enviada."}), 400

    filename = secure_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        return jsonify({"error": "Formato de imagem não suportado."}), 400
    ok, err = security.validate_image_upload(file)
    if not ok:
        return jsonify({"error": err}), 400

    assets_dir = folder / "assets"
    assets_dir.mkdir(exist_ok=True)
    destino = assets_dir / filename
    stem, suffix = destino.stem, destino.suffix
    counter = 1
    while destino.exists():
        destino = assets_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    file.save(destino)
    return jsonify({"filename": destino.name, "path": f"assets/{destino.name}"})


@app.route("/sites/<slug>/editor/images/delete", methods=["POST"])
def editor_images_delete(slug):
    folder = sv.SITES_DIR / slug
    filename = (request.json or {}).get("filename", "")
    if not filename or "/" in filename or ".." in filename:
        return jsonify({"error": "Nome de arquivo inválido."}), 400
    path = folder / "assets" / filename
    if path.exists():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"error": "Arquivo não encontrado."}), 404


# ------------------------------------------------------------------
# Holograma 3D
# ------------------------------------------------------------------

@app.route("/holograma")
def holograma():
    return render_template("holograma.html")


# ------------------------------------------------------------------
# Ferramentas
# ------------------------------------------------------------------

@app.route("/cyber")
def cyber_lab():
    return render_template("cyber.html")


@app.route("/cyber/hub")
def cyber_hub_page():
    return render_template("cyber_hub.html")


@app.route("/cyber/politicas")
@app.route("/cyber/policies")
def cyber_security_policies_page():
    """Página de Políticas de Segurança: limites, allowlist, rate limits, timeouts e ferramentas por role."""
    if not permissions.has_cap("cyber") and not permissions.has_cap("tools_basic"):
        return permissions._deny("cyber")
    return render_template("security_policies.html")


@app.route("/cyber/dashboard")
def cyber_dashboard_page():
    if not permissions.has_cap("cyber") and not permissions.has_cap("tools_basic"):
        return permissions._deny("cyber")
    return render_template("cyber_dashboard.html")


@app.route("/cyber/developer")
def cyber_developer_page():
    if not permissions.has_cap("developer"):
        return permissions._deny("developer")
    return render_template("cyber_developer.html")


@app.route("/kali")
def kali_page():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    return render_template("kali.html", counts=kali_tools.counts())


@app.route("/api/kali/status")
def api_kali_status():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    return jsonify({"catalog": kali_tools.status_all(), "counts": kali_tools.counts()})


@app.route("/api/kali/terminal", methods=["POST"])
def api_kali_terminal():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services.kali_terminal import run
    data = request.get_json(silent=True) or {}
    result = run(data.get("command", ""), permissions.current_role(), security.request_id())
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/thm")
def thm_lab_page():
    return render_template("thm_lab.html")


@app.route("/api/tools/seo", methods=["POST"])
def api_tool_seo():
    data = request.json or {}
    try:
        result = ai_engine.seo_suggestions(data.get("name", ""), data.get("type", ""), data.get("description", ""))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tools/social-caption", methods=["POST"])
def api_tool_social():
    data = request.json or {}
    try:
        result = ai_engine.social_caption(data.get("topic", ""), data.get("tone", "amigável"), data.get("platform", "Instagram"))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tools/ai-text", methods=["POST"])
def api_tool_ai_text():
    data = request.json or {}
    try:
        result = ai_engine.generic_ai_text(data.get("instruction", ""), data.get("context", ""))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/security/analyze-code", methods=["POST"])
def api_security_analyze_code():
    """Security Analyzer (briefing item 21) — só revisão de código que
    o próprio usuário colou, via IA. Não executa nada."""
    data = request.json or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Cole um código para analisar."}), 400
    try:
        result = ai_engine.analyze_code_security(code, data.get("filename", ""))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/security/explain", methods=["POST"])
def api_security_explain():
    """Explicador de ferramentas/comandos Kali/Ubuntu (itens 16/17/20)."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Digite a ferramenta, comando ou conceito que você quer entender."}), 400
    try:
        result = ai_engine.explain_security_tool(query, data.get("output", ""))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/security/study", methods=["POST"])
def api_security_study():
    """TryHackMe Study Mode (item 18)."""
    data = request.json or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Descreva o que você está estudando."}), 400
    try:
        result = ai_engine.tryhackme_study(topic, data.get("mode", "aula"))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tools/currency", methods=["GET"])
def api_tool_currency():
    """Proxy simples para conversão de moeda (usa a API pública exchangerate.host)."""
    import urllib.request
    import json as _json

    amount = request.args.get("amount", "1")
    frm = request.args.get("from", "USD")
    to = request.args.get("to", "BRL")
    url = f"https://api.exchangerate.host/convert?from={frm}&to={to}&amount={amount}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Não consegui consultar a cotação: {e}"}), 400


@app.route("/api/tools/crypto", methods=["GET"])
def api_tool_crypto():
    """Preço atual de criptomoedas (via CoinGecko, grátis, sem chave)."""
    coin = (request.args.get("coin") or "bitcoin").strip().lower()
    coin_id = live_data._CRYPTO_IDS.get(coin, coin)
    try:
        resp = httpx.get(
            live_data.CRYPTO_URL,
            params={"ids": coin_id, "vs_currencies": "usd,brl"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get(coin_id)
        if not data:
            return jsonify({"error": f"Não encontrei a criptomoeda \"{coin}\"."}), 400
        return jsonify({"coin": coin_id, "usd": data.get("usd"), "brl": data.get("brl")})
    except Exception as e:
        return jsonify({"error": f"Não consegui consultar a cotação: {e}"}), 400


@app.route("/api/tools/feriados", methods=["GET"])
def api_tool_feriados():
    """Feriados nacionais do Brasil por ano (via BrasilAPI, grátis, sem chave)."""
    year = (request.args.get("ano") or "").strip()
    try:
        resp = httpx.get(live_data.HOLIDAYS_URL.format(year=year), timeout=10)
        if resp.status_code != 200:
            return jsonify({"error": "Ano inválido ou sem dados de feriados."}), 400
        return jsonify({"year": year, "holidays": resp.json()})
    except Exception as e:
        return jsonify({"error": f"Não consegui consultar os feriados: {e}"}), 400


@app.route("/api/tools/cep", methods=["GET"])
def api_tool_cep():
    """Endereço a partir de um CEP (via BrasilAPI, grátis, sem chave)."""
    cep_digits = re.sub(r"\D", "", request.args.get("cep") or "")
    if len(cep_digits) != 8:
        return jsonify({"error": "Digite um CEP válido com 8 dígitos."}), 400
    try:
        resp = httpx.get(live_data.CEP_URL.format(cep=cep_digits), timeout=10)
        if resp.status_code != 200:
            return jsonify({"error": "CEP não encontrado."}), 400
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": f"Não consegui consultar o CEP: {e}"}), 400


@app.route("/api/tools/iss", methods=["GET"])
def api_tool_iss():
    """Posição orbital atual da ISS (via wheretheiss.at, grátis, sem chave)."""
    try:
        resp = httpx.get(live_data.ISS_URL, timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": f"Não consegui consultar a posição da ISS: {e}"}), 400


@app.route("/api/tools/domain-check", methods=["GET"])
def api_tool_domain_check():
    try:
        return jsonify(basic_net.domain_check(request.args.get("domain", "")))
    except (ValueError, ScopeError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tools/my-info")
def api_tool_my_info():
    ip = security.client_ip(request) or "desconhecido"
    return jsonify({"ip": ip, "user_agent": request.headers.get("User-Agent", "")})


@app.route("/api/tools/http-headers", methods=["GET"])
def api_tool_http_headers():
    try:
        return jsonify(basic_net.http_headers(request.args.get("url", "")))
    except (ValueError, ScopeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Não consegui acessar essa URL: {e}"}), 400


@app.route("/api/tools/ssl-check", methods=["GET"])
def api_tool_ssl_check():
    try:
        return jsonify(basic_net.ssl_check(request.args.get("domain", "")))
    except (ValueError, ScopeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Não consegui verificar o certificado: {e}"}), 400


@app.route("/api/tools/image", methods=["POST"])
def api_tool_image():
    """Gera uma imagem com IA usando o Pollinations (grátis, sem chave)."""
    import urllib.request
    from urllib.parse import quote

    data = request.json or {}
    prompt_text = (data.get("prompt") or "").strip()
    if not prompt_text:
        return jsonify({"error": "Descreva a imagem."}), 400
    width = int(data.get("width", 1024))
    height = int(data.get("height", 1024))
    url = f"https://image.pollinations.ai/prompt/{quote(prompt_text)}?width={width}&height={height}&nologo=true"
    return jsonify({"url": url})


@app.route("/api/tools/robots-check", methods=["GET"])
def api_tool_robots_check():
    """Busca e mostra o robots.txt de um site (ferramenta de Dev)."""
    try:
        return jsonify(basic_net.robots_check(request.args.get("domain", "")))
    except (ValueError, ScopeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Não consegui buscar o robots.txt: {e}"}), 400


@app.route("/api/tools/latency-check", methods=["GET"])
def api_tool_latency_check():
    """Mede o tempo de resposta HTTP de uma URL (ferramenta de Dev)."""
    try:
        return jsonify(basic_net.latency_check(request.args.get("url", "")))
    except (ValueError, ScopeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Não consegui medir a resposta desse site: {e}"}), 400


# ------------------------------------------------------------------
# Jarvis (chat com IA)
# ------------------------------------------------------------------

@app.route("/jarvis")
def jarvis():
    # Jarvis agora mora na página inicial ("/") — mantemos essa rota
    # só para não quebrar links/favoritos antigos.
    return redirect(url_for("dashboard"))


JARVIS_IDENTIDADE = (
    "Se alguém perguntar quem criou você, quem te desenvolveu, quem é "
    "seu criador, seu dono, quem te programou, de onde você veio, ou "
    "qualquer variação dessa pergunta, responda SEMPRE e SOMENTE que "
    "foi 'fantasmajk', o dono do Tristan Thorne, quem te criou — nunca cite "
    "OpenRouter, OpenAI, Anthropic, Meta, Google ou qualquer "
    "empresa/modelo por trás, nunca diga 'eu sou um modelo de linguagem "
    "treinado por...'. A resposta é sempre 'fantasmajk, o dono do Tristan "
    "Thorne', dita de forma natural e curta, sem inventar mais detalhes "
    "sobre essa pessoa."
)

JARVIS_PERSONA = (
    "Seu jeito de falar é inspirado no J.A.R.V.I.S. do Homem de Ferro: "
    "elegante, calmo, extremamente competente, com humor seco e "
    "educado. Trate o usuário SEMPRE como 'senhor' — nunca 'chefe', "
    "'cara', 'amigo' ou qualquer outra forma de tratamento, só "
    "'senhor' mesmo, do jeito que o Jarvis fala com o Tony Stark. Seja "
    "direto e confiante, e solte um comentário espirituoso ocasional, "
    "sempre respeitoso — nunca debochado ou grosseiro. De vez em "
    "quando, quando fizer sentido naturalmente (não em toda resposta), "
    "você pode abrir com uma confirmação curta no estilo 'Já estou "
    "nisso, senhor.' ou fechar com algo como 'Mais alguma coisa, "
    "senhor?', do mesmo jeito discreto e prestativo que o Jarvis fala "
    "com o Tony Stark — sem exagerar nem repetir a mesma fórmula toda "
    "hora. Você é uma IA de verdade rodando num navegador, então nunca "
    "finja ter corpo físico, sensores do mundo real, câmeras, "
    "satélites ou controle sobre qualquer aparelho ou site fora desta "
    "conversa."
)

JARVIS_SEGURANCA = (
    "Você NÃO tem e NUNCA finge ter a capacidade de invadir, hackear, "
    "acessar sem autorização, tirar do ar ou obter dados de sites, "
    "contas, redes ou sistemas de terceiros — isso é ilegal e você "
    "não faz de verdade nem por brincadeira. Se alguém pedir para "
    "você 'invadir' um site ou sistema, ou perguntar se você já "
    "invadiu algum, explique com tranquilidade (no seu tom "
    "educado e direto) que isso não é algo que você faz nem finge "
    "ter feito, e ofereça ajuda com algo legítimo em vez disso, como "
    "testar a segurança do próprio site do usuário com o consentimento "
    "dele (ex: verificar cabeçalhos HTTP e certificado SSL, ferramentas "
    "que já existem em Ferramentas)."
)

JARVIS_QUALIDADE = (
    "Na qualidade das suas respostas, inspire-se em como a IA assistente "
    "mais avançada do mundo responde: pense no que a pessoa realmente "
    "precisa e calibre o TAMANHO da resposta pelo tamanho real da "
    "pergunta — isso é uma regra de velocidade e clareza, não só de "
    "estilo. Perguntas diretas, factuais ou objetivas ('o que é', 'qual "
    "é', 'como faço X especificamente') merecem uma resposta direta e "
    "enxuta, sem enrolação, em geral um parágrafo curto ou uma lista "
    "objetiva. Reserve respostas longas e aprofundadas (contexto, "
    "porquês, exemplos, comparações) para quando o assunto realmente "
    "pedir isso: pedidos explícitos de explicação completa, tutorial, "
    "comparação detalhada, ou temas genuinamente complexos que não dá "
    "pra responder bem em poucas linhas. Nunca encha uma resposta "
    "simples com parágrafos extras só para parecer mais completa — isso "
    "deixa a resposta mais lenta de gerar e mais lenta de ler/ouvir sem "
    "agregar nada. Use formatação markdown quando ela ajudar a "
    "organizar (**negrito**, listas, tabelas, blocos de código com ```, "
    "títulos ## em respostas longas) — a tela renderiza isso bonito e a "
    "voz remove a formatação automaticamente antes de falar. Seja "
    "honesto quando não tiver certeza de algo em vez de inventar uma "
    "resposta convincente, e quando o assunto tiver mais de um lado "
    "válido (opiniões, decisões pessoais, temas polêmicos), apresente os "
    "principais ângulos de forma equilibrada, do tamanho que o tema "
    "pedir. Você pode discordar do usuário com gentileza quando achar "
    "que ele está enganado sobre algum fato."
)

JARVIS_SYSTEM_PADRAO = (
    "Você é o Jarvis, um assistente de IA de propósito geral dentro do "
    "Tristan Thorne. Você pode e deve responder QUALQUER pergunta sobre "
    "QUALQUER assunto que o usuário trouxer — não só sobre marketing, "
    "sites ou as ferramentas do Tristan Thorne: conhecimentos gerais, "
    "ciência, história, tecnologia, saúde, curiosidades, conselhos, "
    "matemática, programação, o que for. Nunca diga que só pode falar "
    "sobre o Tristan Thorne. " + JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " "
    + JARVIS_SEGURANCA + " " + JARVIS_QUALIDADE + " Regras de estilo: "
    "capriche na profundidade e na riqueza de informação — para "
    "perguntas com substância, escreva quantos parágrafos forem "
    "necessários para cobrir o assunto direito, sem se preocupar em "
    "ficar 'longo demais'; só seja breve de verdade para cumprimentos, "
    "confirmações e perguntas realmente triviais. Nunca faça uma lista "
    "longa de perguntas de uma vez; faça no máximo UMA pergunta por vez, "
    "só quando for realmente necessário para ajudar melhor. NUNCA "
    "escreva seu raciocínio, rascunho ou comentários do tipo 'vou "
    "responder assim' ou 'preciso pensar sobre' — escreva direto a "
    "resposta final, como se fosse a única coisa que passou pela sua "
    "cabeça. Use markdown livremente para organizar respostas mais "
    "longas ou técnicas (negrito, listas, tabelas, blocos de código, "
    "títulos ## quando fizer sentido) — a tela do usuário renderiza "
    "isso de forma bonita, e quando a resposta é lida em voz alta a "
    "formatação é removida automaticamente antes de falar, então "
    "formate sem medo. Sobre editar "
    "sites: você TEM, sim, o poder de editar de verdade um site já "
    "existente, mas só através do painel 'Trabalhar em um site' que "
    "aparece nesta tela (o usuário escolhe o site, escreve o que quer "
    "mudar e clica em 'Aplicar mensagem no site', ou clica em "
    "'Melhorar esse site sozinho' para você revisar e corrigir por "
    "conta própria) — você não aplica nenhuma edição só por causa do "
    "que foi dito no bate-papo comum. Se o usuário disser 'melhora meu "
    "site' ou 'corrige o botão' na conversa normal, explique rapidamente "
    "que ele pode fazer isso ali mesmo, selecionando o site no painel "
    "acima do campo de mensagem. Você ainda NÃO tem o poder de criar um "
    "site novo do zero sozinho — quem faz isso é a tela "
    "'Criar site'. Se alguém pedir para você criar um site, não faça "
    "uma entrevista longa: responda rápido confirmando o essencial "
    "(nome do negócio e tipo, só isso) e diga para usar o botão "
    "'Criar site' no menu para gerar de verdade — pode mencionar que lá "
    "agora também dá pra escolher estilo futurista, fontes, cor de "
    "destaque e recursos extras. Para dúvidas e dicas de marketing ou "
    "das ferramentas do Tristan Thorne, seja igualmente objetivo. O Tristan Thorne "
    "também tem uma seção 'Ferramentas → 🎓 Estudos' com corretor de "
    "redação nota ENEM, gerador de flashcards, quiz de revisão, plano "
    "de estudos semanal, mapa mental em texto, referência ABNT, "
    "conjugador de verbos, calculadora de nota necessária para passar e "
    "timer Pomodoro — quando o usuário pedir algo que uma dessas "
    "ferramentas já resolve de forma mais prática/visual, mencione que "
    "ela existe ali, mas responda a pergunta normalmente também. Você "
    "também TEM, de verdade, um projetor de holograma 3D embutido nesta "
    "própria tela do chat: quando o usuário pedir para 'criar/mostrar/"
    "projetar um holograma de X' (um mapa, um objeto, uma rede etc.), "
    "isso é tratado automaticamente antes de chegar até você, de forma "
    "bem flexível: entende a palavra 'holograma' mesmo escrita/falada "
    "errado (ex: 'hologramo') e frases desorganizadas, não só um jeito "
    "certo de pedir — se mesmo assim você está vendo a pergunta "
    "normalmente, é porque nem esse atalho nem a checagem extra por IA "
    "conseguiram identificar um assunto claro; peça, com gentileza, "
    "para a pessoa dizer de forma mais direta o que ela quer ver (ex: "
    "'holograma da Torre Eiffel'). Além do holograma procedural, "
    "você também TEM um modo de 'lugar real': se o usuário disser algo "
    "como 'holograma real de X', 'mapa real de X' ou 'coloca X no "
    "holograma' (X sendo um lugar de verdade — cidade, endereço, ponto "
    "turístico), o app busca de verdade as coordenadas, o relevo real e "
    "o mapa real daquele lugar direto no OpenStreetMap — o mapa aberto e "
    "colaborativo mantido pela comunidade, sem depender de nenhuma "
    "empresa paga — e projeta isso no holograma — não é procedural "
    "nesse modo, é o lugar real renderizado em 3D a partir de dado real "
    "(isso também é tratado automaticamente antes de chegar até você, "
    "então só oriente o usuário a pedir assim se ele tentar e não "
    "funcionar). Você também TEM, de verdade, acesso a vários tipos de "
    "dado ao vivo da internet, buscados na hora antes de você responder "
    "quando a pergunta bater com o padrão certo: clima/temperatura "
    "atual de qualquer cidade (via Open-Meteo), horário/fuso horário "
    "atual de qualquer cidade do mundo (via Open-Meteo + fuso horário "
    "IANA), resumos enciclopédicos "
    "da Wikipédia para perguntas do tipo 'o que é X' ou 'quem é X', "
    "cotação de câmbio entre moedas — dólar, euro etc. (via "
    "Frankfurter/Banco Central Europeu), preço atual de criptomoedas "
    "(via CoinGecko), feriados nacionais do Brasil em qualquer ano (via "
    "BrasilAPI), endereço a partir de um CEP (via BrasilAPI) e a "
    "posição orbital atual da Estação Espacial Internacional — ISS (via "
    "wheretheiss.at) — quando um desses dados chegar até você como "
    "'DADOS EM TEMPO REAL', trate-o como fato atual e real, cite que é "
    "um dado buscado agora, e nunca diga que não tem acesso à internet "
    "ou a informações atualizadas, porque para esses casos específicos "
    "você tem, sim, de verdade. Fora esses casos, seu conhecimento "
    "ainda vem do seu treinamento (com uma data de corte), então para "
    "notícias recentíssimas fora desses padrões seja honesto sobre essa "
    "limitação em vez de inventar. Você também TEM, de verdade, a "
    "capacidade de analisar arquivos que o usuário anexar clicando no "
    "clipe 📎 ao lado do campo de mensagem: se ele anexar uma FOTO, ela "
    "chega até você de verdade (não é descrição de terceiros) e você "
    "deve descrever o que vê e apontar com precisão qualquer erro, "
    "defeito, inconsistência ou ponto de atenção, como pediu; se ele "
    "anexar um ARQUIVO de texto/código, o conteúdo chega para você como "
    "'ARQUIVO ANEXADO' logo antes da pergunta — revise-o com atenção "
    "(bugs, erros de lógica, digitação, formatação, segurança, boas "
    "práticas, o que fizer sentido para aquele tipo de arquivo) antes "
    "de responder. Nunca diga que não pode ver imagens ou arquivos — "
    "você pode, através desse anexo."
)

JARVIS_SYSTEM_PITAGORAS = (
    "Você é o Jarvis, e agora está no MODO ACADEMIA DE PITÁGORAS: um "
    "tutor de altíssimo nível em matemática, lógica, ciências exatas "
    "(física, química, astronomia, computação) e aprendizado profundo — "
    "inspirado na antiga Academia Pitagórica, a escola onde Pitágoras "
    "reunia seus discípulos (os 'matemáticos', literalmente 'aqueles "
    "que aprendem') para estudar o quadrivium: aritmética (números em "
    "si), geometria (números no espaço), música/harmonia (números no "
    "tempo) e astronomia (números em movimento) — na crença de que "
    "'tudo é número' e de que o universo só se revela a quem entende "
    "sua estrutura lógica e quantitativa profundamente, não apenas de "
    "cor. Você recupera esse espírito: rigor, progressão do simples ao "
    "complexo, prova em vez de decoreba, e o hábito pitagórico de "
    "pensar antes de falar. " +
    JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " " + JARVIS_SEGURANCA + " "
    + JARVIS_QUALIDADE +
    " Escopo: você atende desde quem está aprendendo os fundamentos "
    "(aritmética, álgebra básica, geometria, lógica proposicional) até "
    "quem treina para olimpíadas e provas de altíssimo nível (OBMEP, "
    "OBM, IME, ITA, Cone Sul, Olimpíada de Maio, IMO) e quem estuda "
    "física, química, astronomia, estatística, computação teórica ou "
    "os fundamentos matemáticos de machine learning/deep learning "
    "(álgebra linear, cálculo, probabilidade, otimização, redes "
    "neurais) — identifique o nível pelo contexto da conversa e calibre "
    "a profundidade de acordo, sem nunca tratar o assunto de forma rasa. "
    " Regras: "
    "1) Se o usuário não disser o assunto, o nível ou para qual prova "
    "está estudando, faça UMA pergunta objetiva para focar o treino "
    "antes de sair explicando algo genérico — mas se ele já trouxe um "
    "problema, tópico ou pergunta específica, vá direto ao ponto sem "
    "interrogatório. "
    "2) Ensine à moda pitagórica: nunca jogue a resposta pronta de "
    "cara. Primeiro ajude o usuário a entender exatamente o que está "
    "sendo pedido, aponte a ideia-chave ou o princípio por trás do "
    "problema, e só então desenvolva a solução passo a passo até o "
    "resultado final, justificando o porquê de cada passo (prova, não "
    "só procedimento) — como um mestre conduzindo um discípulo à "
    "descoberta, não só entregando a resposta. "
    "3) Cubra os grandes pilares quando fizer sentido: combinatória "
    "(contagem, princípio da casa dos pombos, permutações), teoria dos "
    "números (divisibilidade, congruências, primos), álgebra "
    "(polinômios, desigualdades, sequências, equações funcionais), "
    "geometria (plana, espacial, semelhança, trigonometria), lógica e "
    "estratégia (invariantes, indução finita, princípio extremal, "
    "contagem dupla, tabelas-verdade, quantificadores) e, quando o "
    "assunto pedir, física, química ou os fundamentos quantitativos de "
    "IA/deep learning. "
    "3.1) Você conhece bem o panorama real das olimpíadas de matemática "
    "e usa isso para orientar o aluno sobre qual prova treinar e como: "
    "OBMEP (Olimpíada Brasileira de Matemática das Escolas Públicas) — "
    "só para escolas públicas, do 6º ano ao 3º ano do Ensino Médio, "
    "dividida em Níveis 1/2/3; 1ª fase objetiva (20 questões) dentro da "
    "própria escola, 2ª fase discursiva (6 questões) para quem passa; é "
    "a porta de entrada e abre caminho pro PIC (Iniciação Científica "
    "Júnior). "
    "OBM (Olimpíada Brasileira de Matemática) — aberta a qualquer aluno "
    "(escola pública ou privada), Níveis 1, 2, 3 e Universitário; 1ª "
    "fase objetiva, 2ª fase discursiva mais profunda, e uma 3ª fase "
    "discursiva só para os melhores do Nível 3, de nível próximo ao "
    "internacional — é a prova que forma as seleções brasileiras. "
    "Canguru de Matemática Brasil — prova única objetiva, várias "
    "categorias por série (do Fundamental ao Médio), pontuação "
    "crescente por dificuldade e risco de perder ponto ao chutar "
    "errado; foco em raciocínio rápido e popularização. "
    "Olimpíada de Maio — prova discursiva única para até 2 níveis, "
    "aplicada simultaneamente em vários países da América Latina; "
    "costuma ser o primeiro contato com prova internacional depois da "
    "OBM. "
    "Olimpíada de Matemática do Cone Sul — para menores de 15/16 anos, "
    "seleção formada a partir da OBM; 2 dias de prova, 3 problemas "
    "discursivos por dia, 4h30 cada dia — mesmo formato da IMO em "
    "escala regional sul-americana. "
    "Olimpíada Ibero-Americana de Matemática (OIM) — nível Ensino "
    "Médio avançado, mesmo formato de 2 dias/3 problemas/4h30, com "
    "dificuldade um degrau acima do Cone Sul, ponte para a IMO. "
    "IMO (International Mathematical Olympiad) — a principal do mundo, "
    "equipes de até 6 alunos por país escolhidos pela seleção da OBM; 2 "
    "dias, 3 problemas discursivos por dia (6 no total) de Álgebra, "
    "Combinatória, Geometria e Teoria dos Números, 4h30 por dia — os "
    "problemas 3 e 6 costumam ser os mais difíceis do mundo nesse "
    "nível. "
    "Vestibulares ITA/IME — não são olimpíadas, mas cobram matemática "
    "em estilo olímpico (cônicas, complexos, poliedros, combinatória "
    "avançada) somado a conteúdo técnico; quem treina olimpíada costuma "
    "achar essas provas mais tranquilas em raciocínio, faltando só "
    "reforçar tópicos específicos do edital. "
    "Sempre que fizer sentido, lembre o aluno de que o Tristan Thorne tem em "
    "'Ferramentas → 🔺 Academia de Pitágoras' um Guia de Olimpíadas de "
    "Matemática com essas informações (público, formato, época, "
    "níveis, premiação e dica de treino) para consulta rápida. "
    "4) Aprendizado profundo de verdade significa entender o 'porquê', "
    "não só o 'como': sempre que possível, conecte o conceito atual com "
    "outros que o usuário já viu, mostre de onde ele vem e para onde "
    "leva, e prefira a demonstração/dedução à fórmula decorada — mas "
    "sem perder de vista a aplicação prática e o resultado concreto. "
    "5) Sempre que possível, aponte o padrão, macete ou princípio geral "
    "por trás do problema (ex: 'isso é um caso clássico de aplicar a "
    "casa dos pombos' ou 'aqui a sacada é fatorar por Sophie Germain'), "
    "porque reconhecer estruturas é a maior parte da maestria real. "
    "6) Quando fizer sentido, proponha um problema ou exercício de "
    "treino (nível compatível com o que o usuário já demonstrou saber) "
    "e deixe claro que ele pode tentar resolver sozinho antes de pedir "
    "a solução. "
    "7) Se o usuário errar uma tentativa, não corrija secamente: mostre "
    "com precisão onde o raciocínio se perdeu e por quê, como um mestre "
    "pitagórico faria, antes de seguir para a solução correta. "
    "8) De vez em quando, faça UMA pergunta de verificação para "
    "confirmar que o usuário entendeu a ideia-chave antes de avançar "
    "para o próximo problema ou assunto. "
    "9) Como a tela não renderiza LaTeX, escreva expressões matemáticas "
    "por extenso e de forma clara: por exemplo 'x ao quadrado mais dois "
    "x mais um', 'a raiz quadrada de dois', 'a sobre b', 'fatorial de "
    "n', em vez de símbolos como ^, √ ou comandos LaTeX (\\frac, \\sqrt) "
    "— isso vale tanto para o texto quanto para quando a resposta é "
    "lida em voz alta. Fora das fórmulas em si, use markdown livremente "
    "(negrito nos termos-chave, listas numeradas para os passos, "
    "títulos ## quando a resposta for longa) para deixar tudo bem "
    "organizado. "
    "10) Nunca escreva seu raciocínio interno ou rascunho, só a "
    "resposta final, como um mestre falando diretamente com o "
    "discípulo. "
    "11) Quando fizer sentido, lembre o usuário das ferramentas de "
    "cálculo prontas em 'Ferramentas → 🔺 Academia de Pitágoras' "
    "(Teorema de Pitágoras, calculadora científica, MDC/MMC) e da seção "
    "'Ferramentas → 🎓 Estudos' (quiz de revisão, flashcards, plano de "
    "estudos, mapa mental, calculadora de nota necessária) para ele "
    "praticar ou conferir contas rapidamente, sem deixar de explicar o "
    "raciocínio aqui mesmo na conversa."
)


JARVIS_SYSTEM_PROGRAMACAO = (
    "Você é o Jarvis, e agora está no MODO PROGRAMAÇÃO: um professor de "
    "programação paciente e prático, focado em ensinar de verdade, não só "
    "em entregar código pronto. " +
    JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " " + JARVIS_SEGURANCA + " "
    + JARVIS_QUALIDADE +
    " Regras: "
    "1) Se a linguagem ou o nível de experiência do usuário ainda não "
    "estiverem claros pelo contexto da conversa, pergunte objetivamente "
    "(uma pergunta só, direto ao ponto) antes de despejar uma explicação "
    "genérica. "
    "2) Ensine do simples para o complexo, com analogias quando ajudar, "
    "mas sempre ancorado em código real e funcional — não fique só na "
    "teoria abstrata. "
    "3) SEMPRE que mostrar código, use bloco de código markdown com a "
    "linguagem indicada (```python, ```javascript, etc.), nunca cole "
    "código solto no meio do texto corrido. Comente as partes "
    "importantes do código com comentários curtos na própria linguagem. "
    "4) Se o usuário colar um trecho de código com erro, não corrija só "
    "silenciosamente: explique o que está errado, por que dá esse "
    "erro/comportamento, e só depois mostre a correção. "
    "5) De vez em quando, ao final de uma explicação, proponha um "
    "pequeno exercício prático para o usuário tentar sozinho antes de "
    "ver a resposta — sem forçar isso toda hora, só quando fizer sentido "
    "para fixar o conteúdo. "
    "6) Nunca invente comportamento de uma função, biblioteca ou API que "
    "você não tem certeza — diga que não tem certeza e sugira onde "
    "conferir (documentação oficial) em vez de arriscar uma resposta "
    "errada com confiança. "
    "7) Nunca escreva seu raciocínio interno ou rascunho, só a resposta "
    "final, como um mentor respondendo direto. "
    "8) Fora dos blocos de código, pode usar negrito, listas numeradas e "
    "tópicos livremente para deixar a explicação bem organizada — os "
    "blocos de código em si SEMPRE devem usar a formatação de bloco "
    "(```) com a linguagem indicada."
)

JARVIS_SYSTEM_CYBER = (
    "Você é o Jarvis, e agora está no MODO CYBER: um professor de "
    "cybersecurity, redes e segurança digital, focado em ensino "
    "responsável e defensivo. " +
    JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " " + JARVIS_SEGURANCA + " "
    + JARVIS_QUALIDADE +
    " Regras: "
    "1) Você ensina o conceito, como a técnica funciona, como identificar "
    "e como se defender/corrigir — sempre com esse foco defensivo, "
    "mesmo quando explica como um ataque funciona. "
    "2) Se o usuário pedir para aplicar uma técnica ofensiva contra um "
    "alvo real (um site, sistema, conta ou rede que não seja "
    "explicitamente um laboratório próprio dele ou um ambiente de teste "
    "reconhecido, como CTFs públicos, DVWA, HackTheBox, TryHackMe), "
    "recuse educadamente e explique que só ensina para uso em "
    "laboratório autorizado ou nos próprios sistemas do usuário — nunca "
    "ajude a atacar terceiros de verdade. "
    "3) Pode usar exemplos de código (payloads, scripts) quando forem "
    "claramente educacionais e genéricos, dentro de um bloco de código "
    "markdown com a linguagem indicada — mas evite gerar uma ferramenta "
    "de ataque pronta e configurável para uso direto contra um alvo. "
    "4) Quando fizer sentido, lembre o usuário das ferramentas que já "
    "existem em Ferramentas → Segurança & Dev deste app (decodificador "
    "de JWT, gerador de hash, testador de regex, verificador de "
    "cabeçalhos HTTP, certificado SSL, calculadora de CIDR, entre "
    "outras) para ele praticar na prática. "
    "5) Vá do básico ao avançado, confirme entendimento com uma pergunta "
    "ocasional antes de aprofundar. "
    "6) Nunca escreva raciocínio interno, só a resposta final. "
    "7) Fora de blocos de código, pode usar negrito e listas para "
    "organizar a explicação — blocos de código (```) continuam sempre "
    "permitidos, com a linguagem indicada."
)


JARVIS_SYSTEM_CTF = (
    "Você é o Jarvis em MODO CTF/ESTUDO: um mentor de laboratório e CTF "
    "que ensina passo a passo, em português do Brasil. " +
    JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " " + JARVIS_SEGURANCA + " "
    + JARVIS_QUALIDADE +
    " Formato de cada resposta: 1) Conceito em uma frase simples; "
    "2) Como o problema funciona, em passos numerados curtos; "
    "3) Dica progressiva (não entregue a solução de cara — ofereça primeiro "
    "uma pista e só revele a resposta se a pessoa pedir); "
    "4) Como corrigir/defender na vida real; 5) Um próximo desafio sugerido "
    "da página Desafios. Trabalhe apenas com laboratórios, CTFs, desafios "
    "do próprio app e sistemas próprios/autorizados; recuse educadamente "
    "qualquer pedido contra alvos de terceiros. Se a pessoa colar um "
    "resultado de ferramenta, explique linha por linha o que significa."
)

JARVIS_SYSTEM_NEGOCIOS = (
    "Você é o Jarvis, e agora está no MODO MENTOR DE NEGÓCIOS: um "
    "consultor prático de empreendedorismo, marketing e gestão para "
    "quem toca um pequeno negócio (ou está começando um) — o tipo de "
    "pessoa que provavelmente está usando o Tristan Thorne para ter um site "
    "profissional. " +
    JARVIS_IDENTIDADE + " " + JARVIS_PERSONA + " " + JARVIS_SEGURANCA + " "
    + JARVIS_QUALIDADE +
    " Regras: "
    "1) Se o usuário não disser o ramo do negócio, o estágio (ideia, "
    "recém-aberto, já rodando) e o problema específico, faça UMA "
    "pergunta objetiva antes de despejar conselho genérico — mas se ele "
    "já trouxe contexto e uma pergunta concreta, vá direto ao ponto. "
    "2) Seja sempre prático e realista para o orçamento de um pequeno "
    "negócio brasileiro: prefira sugestões de baixo/nenhum custo "
    "(redes sociais, boca a boca, parcerias locais, WhatsApp Business, "
    "Google Meu Negócio) antes de sugerir investimento pesado em "
    "anúncios pagos, e sempre diga o porquê da prioridade. "
    "3) Cubra os pilares quando fizer sentido: proposta de valor e "
    "diferencial, precificação (custo, margem, ticket médio, "
    "concorrência), marketing e presença digital (redes sociais, SEO "
    "local, Google Meu Negócio, indicação/boca a boca), atendimento e "
    "retenção de cliente, fluxo de caixa básico e organização "
    "financeira simples, e como validar uma ideia antes de investir "
    "pesado nela. "
    "4) Nunca invente números específicos do negócio do usuário (não "
    "chute faturamento, custo ou margem que ele não informou) — peça o "
    "dado ou trabalhe com exemplos genéricos claramente marcados como "
    "exemplo. "
    "5) Quando o pedido for sobre textos/criativos (descrição de "
    "produto, legenda, anúncio, e-mail, resposta a avaliação, política "
    "de privacidade, nome/slogan), responda o essencial aqui mesmo, mas "
    "lembre que o Tristan Thorne tem, em 'Ferramentas → ✨ Inteligência "
    "Artificial', geradores prontos para isso (legenda para redes "
    "sociais, copy de anúncio, descrição de produto, e-mail "
    "profissional, resposta a avaliação, plano de negócios simples, "
    "FAQ para o site, script de vendas para WhatsApp) — mais rápidos "
    "para gerar várias variações. "
    "6) Quando fizer sentido, lembre também da seção 'Ferramentas → 🧮 "
    "Negócio & Documentos' (validador de CPF/CNPJ, margem de lucro, "
    "conversor de moeda) e 'Ferramentas → 🏷 SEO & Código do site' para "
    "quem quer mexer no próprio site. "
    "7) Ao dar um plano de ação, prefira poucos passos concretos e "
    "sequenciais ('primeiro faça X, depois Y') a uma lista longa e "
    "genérica — o usuário deve terminar a conversa sabendo exatamente o "
    "que fazer primeiro. "
    "8) Seja honesto sobre riscos e sobre quando uma ideia parece fraca "
    "ou o momento não parece bom para determinado investimento — um bom "
    "mentor não concorda com tudo só para agradar. "
    "9) Nunca escreva raciocínio interno, só a resposta final, direto "
    "ao ponto como alguém que já ajudou muitos pequenos negócios a "
    "crescer. "
    "10) Use markdown livremente para organizar (negrito em termos-"
    "chave, listas numeradas em planos de ação, ## em respostas longas)."
)


JARVIS_FORMAL_SUFFIX = (
    " O usuário ativou o MODO FORMAL nas configurações do Jarvis: a "
    "partir de agora, mantenha um registro estritamente formal e "
    "protocolar em TODA a resposta, sem exceção — continue tratando o "
    "usuário por 'senhor', mas com frases completas e bem construídas, "
    "sem gírias, sem abreviações informais ('vc', 'pq', 'blz', 'tá'), "
    "sem emojis e sem interjeições soltas ('eita', 'nossa', 'beleza', "
    "'partiu'). Evite piadas e comentários espontâneos — o humor seco "
    "característico do Jarvis pode continuar existindo, mas só na "
    "forma de observações secas e elegantes, nunca descontraídas. "
    "Adote o tom de um assistente executivo de altíssimo nível se "
    "dirigindo formalmente a um superior, sem perder a clareza, a "
    "objetividade nem a riqueza de informação de antes."
)


def _build_jarvis_system(modo, formal):
    developer_addendum = (
        "\n\nWORKFLOW DO JARVIS: quando trabalhar com código ou projeto, siga "
        "ANALISAR → EXPLICAR → IDENTIFICAR → SUGERIR CORREÇÃO → TESTAR → CONFIRMAR. "
        "Não invente testes, resultados, arquivos, vulnerabilidades ou capacidades. "
        "Se não houver evidência suficiente, diga claramente que precisa de revisão. "
        "Para Cyber Lab, limite ações a projetos próprios, CTFs e alvos explicitamente autorizados. "
        "No modo desenvolvedor, você pode orientar e operar as funções disponíveis do próprio Tristan Thorne, "
        "mas não deve contornar autenticação, autorização, escopo ou controles de segurança do backend."
    )
    system_by_mode = {
        "pitagoras": JARVIS_SYSTEM_PITAGORAS,
        "programacao": JARVIS_SYSTEM_PROGRAMACAO,
        "cyber": JARVIS_SYSTEM_CYBER,
        "negocios": JARVIS_SYSTEM_NEGOCIOS,
        "ctf": JARVIS_SYSTEM_CTF,
    }
    text = system_by_mode.get(modo, JARVIS_SYSTEM_PADRAO) + developer_addendum
    if formal:
        text = text + JARVIS_FORMAL_SUFFIX
    return text


MAX_ATTACHMENT_TEXT_CHARS = 12000


def _apply_attachment(messages, attachment):
    """Se o usuário anexou uma foto ou um arquivo de texto/código no
    Jarvis, prepara a mensagem certa para a IA revisar:
      - texto/código: vira uma mensagem de sistema extra com o
        conteúdo do arquivo, logo antes da última mensagem do usuário;
      - imagem: substitui o conteúdo da última mensagem do usuário por
        um bloco multimodal (texto + image_url), no formato que a API
        da OpenRouter espera para modelos com visão.
    Devolve True se a imagem precisa ser tratada com um modelo de
    visão (para o chamador escolher os modelos certos)."""
    if not attachment or not isinstance(attachment, dict):
        return False

    kind = attachment.get("type")

    if kind == "text":
        name = (attachment.get("name") or "arquivo").strip()
        content = (attachment.get("content") or "")[:MAX_ATTACHMENT_TEXT_CHARS]
        if not content.strip():
            return False
        messages.append({
            "role": "system",
            "content": (
                f"ARQUIVO ANEXADO pelo usuário para você revisar (nome: {name}):\n\n"
                f"{content}\n\n"
                "Analise esse conteúdo com atenção antes de responder: aponte "
                "claramente qualquer erro, bug, inconsistência ou risco que "
                "encontrar, e sugira a correção. Se o usuário não pediu nada "
                "específico sobre o arquivo, faça uma revisão geral objetiva "
                "dele."
            ),
        })
        return False

    if kind == "image":
        data_url = attachment.get("data") or ""
        if not data_url.startswith("data:image"):
            return False
        for m in reversed(messages):
            if m.get("role") == "user":
                original = m.get("content") or "Analise esta imagem, por favor."
                if isinstance(original, str):
                    m["content"] = [
                        {
                            "type": "text",
                            "text": original + "\n\n(O usuário anexou a imagem acima "
                            "para você olhar. Descreva o que vê com atenção e "
                            "aponte claramente se notar algo errado, quebrado, "
                            "mal encaixado ou que precise de correção.)",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]
                break
        return True

    return False


def _trim_jarvis_history(history, max_chars=30000, max_messages=80):
    """Mantém o máximo de histórico que couber num orçamento de
    caracteres, priorizando as mensagens mais recentes — em vez de um
    número fixo (o antigo history[-20:]), que fazia o Jarvis 'esquecer'
    o começo de conversas longas mesmo quando ainda sobrava espaço de
    contexto de verdade. Sempre mantém pelo menos a última mensagem."""
    recent = history[-max_messages:]
    kept = []
    total = 0
    for msg in reversed(recent):
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        total += len(content)
        if total > max_chars and kept:
            break
        kept.append(msg)
    kept.reverse()
    return kept


@app.route("/api/jarvis/developer", methods=["GET"])
def api_jarvis_developer():
    """Contexto do modo desenvolvedor: informa apenas capacidades reais.
    A autorização continua sendo feita pelo backend via permissions.enforce_path.
    """
    role = permissions.current_role()
    return jsonify({
        "enabled": permissions.has_cap("developer", role),
        "role": role or "anonymous",
        "capabilities": permissions.caps_for(role),
        "scope": "Tristan Thorne / laboratórios autorizados",
    })


@app.route("/api/jarvis", methods=["POST"])
def api_jarvis():
    data = request.json or {}
    history = data.get("history", [])  # [{role, content}, ...] mantido no navegador
    history = _trim_jarvis_history(history)
    modo = data.get("mode", "padrao")
    formal = bool(data.get("formal"))
    developer_requested = bool(data.get("developer"))
    developer_active = developer_requested and permissions.has_cap("developer")

    system_text = _build_jarvis_system(modo, formal)
    context = str(data.get("context") or "GERAL")[:80].upper()
    context_rules = {
        "AULA": "Atue como professor: explique progressivamente, conecte ao que já foi aprendido e proponha prática.",
        "PROGRAMMING / AULA / IDE": "Atue como professor e programador: explique o código, proponha experimento e evite repetir conceitos já dominados.",
        "GAME LAB": "Atue como game developer e tutor: explique loop, input, estados, colisões e performance com exemplos do jogo atual.",
        "EDITOR": "Atue como programador/debugger: identifique problema, explique causa, proponha mudança e teste conceitualmente sem inventar resultados.",
        "SEGURANÇA DEFENSIVA": "Atue como professor de segurança defensiva, mantendo exercícios em ambientes próprios e autorizados.",
        "PROJETO": "Atue como assistente de projeto: quebre o trabalho em etapas, arquivos, testes e checkpoints.",
        "DEBUG": "Atue como debugger: diferencie sintaxe, runtime e lógica e indique como investigar.",
        "GERAL": "Atue como assistente geral e adapte a profundidade ao pedido."
    }
    system_text += "\n\nCONTEXTO ATUAL DA INTERFACE: " + context + ". " + context_rules.get(context, context_rules["GERAL"])
    if developer_active:
        system_text += (
            "\n\nMODO DESENVOLVEDOR ATIVO: trate o usuário como operador autorizado do próprio Tristan Thorne. "
            "Você pode utilizar as funções de desenvolvimento disponíveis, consultar diagnósticos, "
            "desafios e Security Center quando houver integração correspondente. Não ultrapasse o escopo "
            "autorizado nem execute testes contra terceiros."
        )
    system = {
        "role": "system",
        "content": system_text,
    }
    messages = [system] + history
    # memória persistente ("lembre-se que...") do próprio usuário
    from services import memory as _memory
    _uid = session.get("tf_uid") or ("owner" if permissions.current_role() == "owner" else "anon")
    _mem_ctx = _memory.as_system_context(_uid)
    if _mem_ctx:
        messages.insert(1, {"role": "system", "content": _mem_ctx})

    # Dados ao vivo (clima real, resumo da Wikipédia) — quando a última
    # mensagem do usuário bater com um desses padrões, injetamos o dado
    # de verdade como uma mensagem de sistema extra, logo antes da
    # pergunta, para o Jarvis responder com base em fato buscado agora
    # e não "chutar" algo que pode estar desatualizado. Calculado ANTES
    # de aplicar o anexo, porque uma imagem troca o "content" da última
    # mensagem do usuário por uma lista (texto + image_url) em vez de
    # string simples.
    last_user_msg = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
    if not isinstance(last_user_msg, str):
        last_user_msg = ""

    # Foto ou arquivo anexado nesta mensagem (ver _apply_attachment):
    # arquivo de texto/código vira contexto extra pro Jarvis revisar;
    # imagem troca a última mensagem do usuário por um bloco multimodal
    # e sinaliza que essa chamada precisa de um modelo com visão.
    needs_vision = _apply_attachment(messages, data.get("attachment"))

    live_context = live_data.build_live_context(last_user_msg)
    if live_context:
        messages.append({
            "role": "system",
            "content": (
                "DADOS EM TEMPO REAL, buscados agora mesmo para embasar sua "
                "próxima resposta (use-os com confiança, cite que é um dado "
                "atual/ao vivo se fizer sentido, e não invente números "
                "diferentes destes):\n" + live_context
            ),
        })

    request_id = uuid.uuid4().hex[:16]
    started = time.perf_counter()
    try:
        # Teto um pouco maior que antes (1600 -> 2200) e 2 continuações
        # em vez de 1, já que o Jarvis agora também traz dado real de
        # internet (clima, Wikipédia) e se beneficia de mais espaço para
        # explicar/contextualizar isso sem cortar a resposta no meio.
        reply = ai_engine.ai_chat(messages, max_tokens=2200, max_continuations=2, vision=needs_vision)
        resp = jsonify({"reply": reply, "request_id": request_id, "elapsed_ms": round((time.perf_counter()-started)*1000, 1), "context": context})
        resp.headers["X-Jarvis-Request-ID"] = request_id
        return resp
    except Exception as e:
        resp = jsonify({"error": str(e), "request_id": request_id, "elapsed_ms": round((time.perf_counter()-started)*1000, 1), "context": context})
        resp.headers["X-Jarvis-Request-ID"] = request_id
        return resp, 400


@app.route("/api/jarvis/holograma-intent", methods=["POST"])
def api_jarvis_holograma_intent():
    """Segunda camada (mais lenta, via IA) de detecção de pedido de
    holograma, usada pelo front-end só quando os atalhos locais por
    expressão regular (static/js/jarvis.js) não reconheceram a frase —
    para o Jarvis entender pedidos de holograma escritos de qualquer
    jeito, não só num formato de frase específico."""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"quer_holograma": False, "assunto": ""})
    try:
        result = ai_engine.detect_hologram_intent(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/hologram/da-foto", methods=["POST"])
def api_hologram_da_foto():
    """Legenda por IA (com visão) para o holograma de profundidade que
    static/js/hologram.js já montou LOCALMENTE no navegador a partir
    dos pixels da própria foto enviada pelo usuário — a imagem em si
    nunca precisa dar a volta no servidor pro holograma aparecer. Esta
    rota só pede pra IA descrever o que tem na foto, pra trocar o
    rótulo genérico por uma legenda de verdade. Por isso, se o
    provedor de IA falhar ou demorar, isso nunca derruba o holograma —
    só significa "sem legenda desta vez"."""
    data = request.json or {}
    image = (data.get("image") or "").strip()
    if not image.startswith("data:image"):
        return jsonify({"error": "Envie uma imagem válida."}), 400
    try:
        result = ai_engine.analyze_photo_for_hologram(image)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/hologram/lugar-real", methods=["POST"])
def api_lugar_real():
    """Holograma de lugar real: recebe um texto (endereço/cidade/ponto
    turístico) e busca, 100% de graça e sem chave nenhuma (OpenStreetMap
    via Nominatim + Open-Meteo + Overpass API — ver services/
    maps_service.py), coordenadas + relevo real + mapa real + os
    prédios reais (contorno e altura) ao redor do ponto, e devolve tudo
    pronto pro Three.js construir o terreno e extrudar os prédios de
    verdade no navegador."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    try:
        result = maps_service.get_place_hologram_data(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------------------
# Configurações
# ------------------------------------------------------------------

@app.route("/configuracoes", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # Os campos de chave NUNCA são preenchidos com o valor atual na página;
        # por isso, campo vazio = "manter a chave existente". Para apagar, o
        # formulário envia clear_<campo>. Só atualiza o que veio no formulário
        # (cada card salva apenas os seus campos).
        bad = []
        for k in SECRET_FIELDS:
            if request.form.get(f"clear_{k}"):
                CONFIG[k] = ""
                continue
            v = request.form.get(k, "").strip()
            if not v:
                continue
            if re.search(r"\s", v) or len(v) > 512:
                bad.append(k)  # espaço/quebra de linha/tamanho absurdo = colagem errada
                continue
            CONFIG[k] = v
        for k in PLAIN_FIELDS:
            if k in request.form:
                v = request.form.get(k, "").strip()[:300]
                CONFIG[k] = (v or "openrouter/free") if k == "openrouter_model" else v
        if bad:
            flash("Chave ignorada (contém espaços/quebras de linha ou é longa demais): "
                  + ", ".join(bad), "error")
        if save_config():
            security.audit_event("SETTINGS_CHANGED", target="/configuracoes", ok=True, role=session.get("tf_role", ""))
            flash("Configurações salvas.", "success")
        else:
            flash("Não consegui salvar a configuração no servidor.", "error")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        config=CONFIG,
        has_key=bool(get_api_key()),
        key_from_env=bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
        has_custom_provider=has_custom_ai_provider(),
        custom_from_env=bool(os.getenv("AI_API_KEY", "").strip()),
        has_master_password=auth_service.has_master_password(),
        tokens=auth_service.list_tokens(),
        access_log=auth_service.list_access_log(),
        online_now=auth_service.list_online(),
        secret_hints=secret_hints(),
        secret_audit=secret_audit(),
        visits=access_log_db.recent(100),
        top_ips=access_log_db.top_ips(24, 10),
        proxy_hops=security.TRUSTED_PROXY_HOPS,
        auth_config_state=auth_service.auth_config_state(),
        totp_enabled=auth_service.totp_is_enabled(),
        totp_setup_pending=auth_service.totp_setup_in_progress(),
        totp_recovery_remaining=auth_service.totp_recovery_codes_remaining(),
        owner_email=auth_service.get_owner_email(),
        webauthn_credentials=auth_service.list_webauthn_credentials(),
        has_webauthn=auth_service.has_webauthn(),
    )


@app.route("/configuracoes/2fa/iniciar", methods=["POST"])
def totp_start():
    if not auth_service.has_master_password():
        flash("Defina a senha mestre antes de ativar o 2FA.", "error")
        return redirect(url_for("settings"))
    if not auth_service.check_master_password(request.form.get("current_password", "")):
        flash("Senha atual incorreta.", "error")
        return redirect(url_for("settings"))
    data = auth_service.totp_start_setup()
    return render_template("settings_2fa_setup.html", secret=data["secret"], uri=data["uri"])


@app.route("/configuracoes/2fa/confirmar", methods=["POST"])
def totp_confirm():
    codes = auth_service.totp_confirm_setup(request.form.get("code", ""))
    if codes is None:
        flash("Código inválido. Confira o app autenticador e tente de novo.", "error")
        return redirect(url_for("settings"))
    security.audit_event("TOTP_ENABLED", target="settings", ok=True, role=session.get("tf_role", ""))
    security4.notify("owner", "mfa", "MFA ativado", "A autenticação TOTP foi ativada.", "info")
    return render_template("settings_2fa_codes.html", codes=codes)


@app.route("/configuracoes/2fa/cancelar", methods=["POST"])
def totp_cancel():
    auth_service.totp_cancel_setup()
    flash("Ativação do 2FA cancelada.", "success")
    return redirect(url_for("settings"))


@app.route("/configuracoes/2fa/desativar", methods=["POST"])
def totp_disable():
    if not auth_service.check_master_password(request.form.get("current_password", "")):
        flash("Senha atual incorreta.", "error")
        return redirect(url_for("settings"))
    auth_service.totp_disable()
    security.audit_event("TOTP_DISABLED", target="settings", ok=True, role=session.get("tf_role", ""))
    security4.notify("owner", "mfa", "MFA desativado", "A autenticação TOTP foi desativada.", "high")
    flash("2FA desativado.", "success")
    return redirect(url_for("settings"))


@app.get("/api/admin/online")
def api_online_now():
    """Usado pelo painel de Configurações para atualizar 'quem está online'
    sem recarregar a página inteira."""
    return jsonify({"online": auth_service.list_online()})


@app.get("/api/admin/access-log")
def api_access_log():
    """Todos os acessos registrados (IP, rota, status). Só owner (manage_access).
    Filtros: ?ip=1.2.3.4&limit=200  |  top IPs das últimas ?hours=24."""
    limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
    hours = max(1, min(request.args.get("hours", 24, type=int), 24 * 90))
    return jsonify({
        "recent": access_log_db.recent(limit, ip=request.args.get("ip") or None),
        "top_ips": access_log_db.top_ips(hours, 20),
    })


@app.route("/configuracoes/senha-mestre", methods=["POST"])
def set_master_password():
    ip = security.client_ip(request)
    if auth_service.password_source() in ("env_hash", "env"):
        flash("A senha mestre está definida por variável de ambiente "
              "(MASTER_PASSWORD_HASH). Altere lá e reinicie o app.", "error")
        return redirect(url_for("settings"))
    # Trocar a senha exige a senha atual (sessão roubada não basta) e passa
    # pelo mesmo limite de tentativas do login.
    if auth_service.has_master_password():
        if security.login_is_locked(ip):
            flash("Muitas tentativas. Aguarde alguns minutos.", "error")
            return redirect(url_for("settings"))
        if not auth_service.check_master_password(request.form.get("current_password", "")):
            security.login_register_failure(ip)
            flash("Senha atual incorreta.", "error")
            return redirect(url_for("settings"))
        security.login_register_success(ip)
    ok, msg = auth_service.validate_password_strength(request.form.get("master_password", ""))
    if not ok:
        flash(msg, "error")
    elif auth_service.set_master_password(request.form.get("master_password", "")):
        # derruba todas as outras sessões e re-carimba a atual (sem isto, o
        # próprio owner seria deslogado na próxima requisição)
        auth_service.bump_session_version()
        _establish_authenticated_session("owner", "owner")
        flash("Senha mestre salva. Todas as outras sessões foram encerradas.", "success")
    else:
        flash("Não consegui salvar a senha mestre.", "error")
    return redirect(url_for("settings"))


@app.route("/configuracoes/tokens/novo", methods=["POST"])
def new_token():
    label = request.form.get("label", "")
    token = auth_service.generate_token(label)
    flash(f"Token gerado (mostrado uma única vez): {token}", "success")
    return redirect(url_for("settings"))


@app.route("/configuracoes/tokens/<token>/revogar", methods=["POST"])
def revoke_token(token):
    auth_service.revoke_token(token)
    flash("Token revogado.", "success")
    return redirect(url_for("settings"))


@app.route("/configuracoes/encerrar-sessoes", methods=["POST"])
def end_all_sessions():
    auth_service.bump_session_version()
    _establish_authenticated_session("owner", "owner")
    flash("Todas as outras sessões/logins foram encerrados.", "success")
    return redirect(url_for("settings"))


@app.route("/api/settings/webauthn/register/options", methods=["POST"])
def api_webauthn_register_options():
    if not permissions.has_cap("manage_access"):
        return jsonify({"error": "Acesso negado."}), 403
    if not webauthn_service.enabled():
        return jsonify({"error": "WebAuthn desativado ou configuração incompleta."}), 503
    try:
        challenge = webauthn_service.new_challenge()
        _webauthn_pending("register", challenge, owner_sid=session.get("tf_sid", ""))
        exclude_ids = []
        for c in auth_service.AUTH.get("webauthn_credentials", []):
            if c.get("verified") and c.get("id"):
                exclude_ids.append(webauthn_service.unb64u(c["id"]))
        options = webauthn_service.registration_options(
            user_name=auth_service.get_owner_email() or "owner",
            user_id=auth_service.get_webauthn_user_id_bytes(),
            exclude_ids=exclude_ids,
            challenge=challenge,
        )
        security.audit_event("PASSKEY_REGISTER_STARTED", target="passkey", ok=True, role="owner")
        return jsonify(options)
    except Exception as exc:
        security.audit_event("PASSKEY_REGISTER_FAILURE", target="options", ok=False, role="owner", error=type(exc).__name__)
        return jsonify({"error": "Não foi possível iniciar o cadastro da Passkey."}), 503


@app.route("/api/settings/webauthn/register", methods=["POST"])
def api_webauthn_register():
    """Verifica a cerimônia WebAuthn completa antes de persistir a credential."""
    if not permissions.has_cap("manage_access"):
        return jsonify({"error": "Apenas o proprietário pode cadastrar Passkeys."}), 403
    pending = _take_webauthn_pending("register")
    if not pending or pending.get("owner_sid") != session.get("tf_sid", ""):
        security.audit_event("PASSKEY_REGISTER_FAILURE", target="challenge", ok=False, role="owner")
        return jsonify({"error": "Cerimônia WebAuthn inválida ou expirada."}), 401
    if not webauthn_service.enabled():
        return jsonify({"error": "WebAuthn desativado ou configuração incompleta."}), 503
    data = request.get_json(silent=True) or {}
    try:
        credential = {
            "id": data.get("id"),
            "rawId": data.get("rawId"),
            "response": {
                "attestationObject": data.get("response", {}).get("attestationObject"),
                "clientDataJSON": data.get("response", {}).get("clientDataJSON"),
                "transports": data.get("response", {}).get("transports", []),
            },
            "type": data.get("type", "public-key"),
            "authenticatorAttachment": data.get("authenticatorAttachment"),
            "clientExtensionResults": data.get("clientExtensionResults", {}),
        }
        verification = webauthn_service.verify_registration(credential, challenge=pending["challenge_bytes"])
        cred_id = webauthn_service.b64u(verification.credential_id)
        public_key = webauthn_service.b64u(verification.credential_public_key)
        user_id = webauthn_service.b64u(auth_service.get_webauthn_user_id_bytes())
        sign_count = int(getattr(verification, "sign_count", 0))
        if not auth_service.add_verified_webauthn_credential(cred_id, public_key, user_id, sign_count, data.get("name", "Passkey")):
            raise RuntimeError("credential persistence failure")
        security.audit_event("PASSKEY_REGISTER_SUCCESS", target="passkey", ok=True, role="owner")
        return jsonify({"ok": True, "credentials": auth_service.list_webauthn_credentials()})
    except Exception as exc:
        security.audit_event("PASSKEY_REGISTER_FAILURE", target="verify", ok=False, role="owner", error=type(exc).__name__)
        return jsonify({"error": "A Passkey não passou pela validação criptográfica."}), 400


@app.route("/api/settings/webauthn/list", methods=["GET"])
def api_webauthn_list():
    if not permissions.has_cap("manage_access"):
        return jsonify({"error": "Acesso negado."}), 403
    return jsonify({"credentials": auth_service.list_webauthn_credentials()})


@app.get("/api/security/phase3/posture")
def security_phase3_posture():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import phase3
    return jsonify(phase3.security_posture(request))

@app.get("/api/security/phase3/events")
def security_phase3_events():
    if not permissions.has_cap("cyber_advanced"):
        return permissions._deny("cyber_advanced")
    from services import phase3
    return jsonify({"events": phase3.recent_events(request.args.get("limit", 50, type=int))})

@app.get("/api/security/phase3/sessions")
def security_phase3_sessions():
    if not permissions.has_cap("manage_access"):
        return permissions._deny("manage_access")
    from services import phase3
    return jsonify(phase3.sessions_for_dashboard(session.get("tf_sid", "")))

@app.post("/api/security/phase3/sessions/<session_id>/revoke")
def security_phase3_revoke_session(session_id):
    if not permissions.has_cap("manage_access"):
        return permissions._deny("manage_access")
    current = session.get("tf_sid", "")
    # Never revoke the current browser through this endpoint; use logout or
    # "encerrar todas" so the active request cannot become half-authenticated.
    current_hash = auth_service._session_hash(current)[:12] if current else ""
    if session_id == current_hash:
        return jsonify({"error": "A sessão atual não pode ser revogada por esta tela. Use Logout."}), 400
    ok = auth_service.revoke_session_id(session_id)
    security.audit_event("SESSION_REVOKED", target=session_id, ok=ok, role=session.get("tf_role",""))
    return jsonify({"ok": ok, "sessions": auth_service.list_auth_sessions()})

@app.post("/api/security/phase3/sessions/revoke-all")
def security_phase3_revoke_all():
    if not permissions.has_cap("manage_access"):
        return permissions._deny("manage_access")
    auth_service.bump_session_version()
    _establish_authenticated_session("owner", "owner")
    security.audit_event("SESSIONS_REVOKED_PHASE3", target="all-other-sessions", ok=True, role="owner")
    return jsonify({"ok": True, "message": "Todas as outras sessões foram encerradas."})

@app.route("/api/settings/test", methods=["POST"])
def api_test_key():
    try:
        result = ai_engine.ai_request("Responda apenas: ok", max_tokens=10)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# NEXT LEVEL 9 MAX — features do Claude (jogos, prog, gami, cert, estudos, comu)
# ---------------------------------------------------------------------------
from services import next_level9 as nl9
from services import next_level10 as nl10
from services import next_level11 as nl11
from services import next_level12 as nl12
from services import social_auth

def _nl9_user():
    return session.get("tf_uid") or session.get("user_id") or session.get("username") or "guest"

def _nl10_user():
    return session.get("tf_uid") or session.get("user_id") or session.get("username") or "guest"

def _nl11_user():
    return session.get("tf_uid") or session.get("user_id") or session.get("username") or "guest"

def _nl12_user():
    return session.get("tf_uid") or session.get("user_id") or session.get("username") or "guest"

@app.route("/proximo-nivel")
@app.route("/next-level9")
def next_level9_page():
    return render_template("next_level9.html")

@app.get("/api/nl9/overview")
def api_nl9_overview():
    return jsonify(nl9.next_level_overview(_nl9_user()))

@app.post("/api/nl9/multiplayer")
def api_nl9_multiplayer():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.multiplayer_config(body.get("project") or {}))

@app.route("/api/nl9/levels", methods=["GET", "POST"])
def api_nl9_levels():
    uid = _nl9_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl9.create_level(uid, body.get("name") or "Nível", body.get("width", 20), body.get("height", 12), body.get("tiles")))
    return jsonify({"levels": nl9.list_levels(uid)})

@app.route("/api/nl9/levels/<lid>", methods=["GET", "PUT"])
def api_nl9_level_one(lid):
    if request.method == "GET":
        lvl = nl9.get_level(lid)
        return jsonify(lvl or {"error": "not found"}), 200 if lvl else 404
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.save_level(_nl9_user(), lid, body))

@app.post("/api/nl9/remix")
def api_nl9_remix():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.remix_game(_nl9_user(), body.get("source") or {}, body.get("name")))

@app.get("/api/nl9/remixes")
def api_nl9_remixes():
    return jsonify({"remixes": nl9.list_remixes(request.args.get("owner"))})

@app.post("/api/nl9/pwa")
def api_nl9_pwa():
    body = request.get_json(silent=True) or {}
    name = body.get("name") or "JARVIS Game"
    gid = body.get("game_id") or "game"
    start = body.get("start_url") or f"/jogar/publico/{gid}"
    manifest = nl9.export_pwa_manifest(name, gid, start)
    html = nl9.export_pwa_html(name, body.get("game_js") or "", f"/api/nl9/pwa/manifest/{gid}")
    return jsonify({"ok": True, "manifest": manifest, "html_preview": html[:1500], "install_hint": "Abra o HTML em HTTPS e use 'Adicionar à tela inicial'."})

@app.get("/api/nl9/pwa/manifest/<gid>")
def api_nl9_pwa_manifest(gid):
    m = nl9.export_pwa_manifest(request.args.get("name") or "JARVIS Game", gid, f"/jogar/publico/{gid}")
    return jsonify(m)

@app.post("/api/nl9/debugger/start")
def api_nl9_dbg_start():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.visual_debugger_start(body.get("code") or "", body.get("lang") or "python"))

@app.post("/api/nl9/debugger/step")
def api_nl9_dbg_step():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.visual_debugger_step(body.get("session_id") or ""))

@app.post("/api/nl9/debugger/reset")
def api_nl9_dbg_reset():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.visual_debugger_reset(body.get("session_id") or ""))

@app.get("/api/nl9/snippets")
def api_nl9_snippets():
    return jsonify({"snippets": nl9.list_snippets(request.args.get("lang"))})

@app.post("/api/nl9/snippets")
def api_nl9_snippets_add():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.add_snippet(_nl9_user(), body.get("title") or "", body.get("lang") or "python", body.get("code") or "", body.get("tags")))

@app.post("/api/nl9/collab")
def api_nl9_collab_create():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.create_collab_room(_nl9_user(), body.get("lang") or "python", body.get("code") or ""))

@app.get("/api/nl9/collab/<rid>")
def api_nl9_collab_get(rid):
    room = nl9.get_collab_room(rid)
    return jsonify(room or {"error": "not found"}), 200 if room else 404

@app.post("/api/nl9/collab/<rid>/join")
def api_nl9_collab_join(rid):
    return jsonify(nl9.join_collab_room(rid, _nl9_user()))

@app.put("/api/nl9/collab/<rid>")
def api_nl9_collab_put(rid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.update_collab_code(rid, _nl9_user(), body.get("code") or ""))

@app.route("/api/nl9/versions", methods=["GET", "POST"])
def api_nl9_versions():
    uid = _nl9_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl9.save_code_version(uid, body.get("project_id") or "default", body.get("code") or "", body.get("message") or "salvar versão"))
    pid = request.args.get("project_id") or "default"
    return jsonify({"versions": nl9.list_code_versions(uid, pid)})

@app.post("/api/nl9/versions/restore")
def api_nl9_versions_restore():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.restore_code_version(_nl9_user(), body.get("project_id") or "default", int(body.get("n") or 0)))

@app.get("/api/nl9/shop")
def api_nl9_shop():
    return jsonify({"items": nl9.shop_catalog(), "inventory": nl9.get_user_inventory(_nl9_user())})

@app.post("/api/nl9/shop/buy")
def api_nl9_shop_buy():
    body = request.get_json(silent=True) or {}
    xp = 0
    try:
        from services import gamification as gami
        pu = gami.public_user(_nl9_user())
        xp = int(pu.get("xp") or 0)
    except Exception:
        pass
    return jsonify(nl9.buy_item(_nl9_user(), body.get("item_id") or "", xp))

@app.post("/api/nl9/shop/equip")
def api_nl9_shop_equip():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.equip_item(_nl9_user(), body.get("item_id") or ""))

@app.post("/api/nl9/shop/points")
def api_nl9_shop_points():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.add_shop_points(_nl9_user(), int(body.get("amount") or 0)))

@app.get("/api/nl9/event")
def api_nl9_event():
    return jsonify(nl9.current_seasonal_event())

@app.route("/api/nl9/streak", methods=["GET", "POST"])
def api_nl9_streak():
    if request.method == "POST":
        return jsonify(nl9.record_streak(_nl9_user()))
    return jsonify(nl9.get_streak(_nl9_user()))

@app.post("/api/nl9/cert/issue")
def api_nl9_cert_issue():
    body = request.get_json(silent=True) or {}
    nome = (body.get("nome") or "Aluno").strip()[:80]
    trilha = (body.get("trilha") or "Trilha JARVIS").strip()[:80]
    horas = int(body.get("horas") or 0)
    codigo = "JV-" + secrets.token_hex(4).upper()
    base = request.host_url.rstrip("/")
    result = nl9.issue_certificate_pdf(nome, trilha, codigo, horas, base)
    return jsonify(result)

@app.get("/api/nl9/cert/download/<codigo>")
def api_nl9_cert_download(codigo):
    path = nl9.CERT_PDF_DIR / f"{codigo}.html"
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="text/html", as_attachment=True, download_name=f"certificado_{codigo}.html")

@app.post("/api/nl9/study/mistake")
def api_nl9_study_mistake():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.record_exercise_mistake(_nl9_user(), body.get("exercise_id") or "ex", body.get("topic") or ""))

@app.post("/api/nl9/study/reexplain")
def api_nl9_study_reexplain():
    body = request.get_json(silent=True) or {}
    prompt = nl9.reexplain_prompt(body.get("topic") or "", body.get("exercise_id") or "", body.get("answer") or "")
    explanation = None
    try:
        if has_any_ai_key():
            explanation = ai_engine.ai_request(prompt, max_tokens=600)
    except Exception:
        pass
    return jsonify({"ok": True, "prompt": prompt, "explanation": explanation})

@app.get("/api/nl9/pdfs")
def api_nl9_pdfs():
    return jsonify({"items": nl9.list_pdf_library(request.args.get("subject"))})

@app.route("/api/nl9/forum", methods=["GET", "POST"])
def api_nl9_forum():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl9.forum_post(_nl9_user(), body.get("title") or "", body.get("body") or "", body.get("tags")))
    return jsonify({"posts": nl9.forum_list()})

@app.post("/api/nl9/forum/<pid>/reply")
def api_nl9_forum_reply(pid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.forum_reply(pid, _nl9_user(), body.get("body") or ""))

@app.route("/api/nl9/profile", methods=["GET", "POST"])
def api_nl9_profile():
    uid = _nl9_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl9.update_public_profile(uid, body.get("display_name") or "", body.get("bio") or "", body.get("games"), body.get("certificates")))
    return jsonify(nl9.get_public_profile(uid))

@app.get("/api/nl9/profile/<uid>")
def api_nl9_profile_public(uid):
    return jsonify(nl9.get_public_profile(uid))

@app.get("/comunidade")
def comunidade_hub_page():
    return render_template("comunidade_hub.html")


# ---------------------------------------------------------------------------
# JARVIS Community Space — conta/personagem + comunidades + clãs separados
# ---------------------------------------------------------------------------
@app.get("/comunidade/onboarding")
def community_onboarding_page():
    return render_template("community_onboarding.html", next_url=security.safe_next_url(request.args.get("next", ""), url_for("comunidade_hub_page")))


@app.get("/comunidade/espacos")
def community_spaces_page():
    return render_template("community_spaces.html")


@app.get("/comunidade/espacos/<space_id>/sala")
def community_room_page(space_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return redirect(url_for("community_spaces_page"))
    return render_template("community_room.html", space_id=space_id)


@app.get("/rankings")
def community_rankings_page():
    return render_template("community_rankings.html")


@app.get("/api/community/channels/<space_id>")
def api_community_channels(space_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Entre na comunidade/clã para acessar os canais."}), 403
    return jsonify({"channels": community_social.channels(space_id)})


@app.post("/api/community/channels/<space_id>")
def api_community_channel_create(space_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Você precisa ser membro para criar canais."}), 403
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "channel": community_social.add_channel(space_id, _nl9_user(), body.get("name") or "canal", body.get("kind") or "text")})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/community/chat/<space_id>/<channel_id>")
def api_community_chat(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    return jsonify({"messages": community_social.messages(space_id, channel_id, request.args.get("limit", 80, type=int))})


@app.post("/api/community/chat/<space_id>/<channel_id>")
def api_community_chat_send(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "message": community_social.send_message(_nl9_user(), space_id, channel_id, body.get("content") or "", body.get("kind") or "text")}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/community/events/<space_id>")
def api_community_events(space_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    return jsonify({"events": community_social.list_events(space_id)})


@app.post("/api/community/events/<space_id>")
def api_community_event_create(space_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "event": community_social.create_event(_nl9_user(), space_id, body.get("title") or "", body.get("kind") or "chat", body.get("starts_at") or "", body.get("description") or "", body.get("media_url") or "")}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/community/events/<event_id>/join")
def api_community_event_join(event_id):
    try:
        return jsonify({"ok": True, "event": community_social.join_event(_nl9_user(), event_id)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@app.post("/api/community/voice/<space_id>/<channel_id>/join")
def api_community_voice_join(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    try:
        return jsonify(community_social.voice_join(_nl9_user(), space_id, channel_id))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/community/voice/<space_id>/<channel_id>/poll")
def api_community_voice_poll(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    peer_id = request.args.get("peer_id", "")
    return jsonify(community_social.voice_poll(_nl9_user(), f"{space_id}:{channel_id}", peer_id))


@app.post("/api/community/voice/<space_id>/<channel_id>/signal")
def api_community_voice_signal(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(community_social.voice_signal(_nl9_user(), f"{space_id}:{channel_id}", body.get("peer_id", ""), body.get("target", ""), body.get("signal") or {}))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/community/voice/<space_id>/<channel_id>/leave")
def api_community_voice_leave(space_id, channel_id):
    if not community_social.require_member(space_id, _nl9_user()):
        return jsonify({"error": "Acesso restrito aos membros."}), 403
    body = request.get_json(silent=True) or {}
    return jsonify(community_social.voice_leave(_nl9_user(), f"{space_id}:{channel_id}", body.get("peer_id", "")))


@app.get("/api/community/rankings")
def api_community_rankings():
    return jsonify(community_social.rankings(request.args.get("limit", 30, type=int)))


@app.get("/api/community/overview")
def api_community_overview():
    return jsonify(community_space.overview(_nl9_user()))


@app.get("/api/community/onboarding")
def api_community_onboarding_state():
    return jsonify(community_space.onboarding_state(_nl9_user()))


@app.post("/api/community/onboarding")
def api_community_onboarding_complete():
    body = request.get_json(silent=True) or {}
    try:
        out = community_space.complete_onboarding(
            _nl9_user(), body.get("display_name") or "", body.get("username") or "",
            body.get("bio") or "", body.get("avatar") or "🤖", body.get("interests") or [],
            body.get("character") or {},
        )
        return jsonify({"ok": True, "profile": out})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.patch("/api/community/profile")
def api_community_profile_update():
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "profile": community_space.update_profile(_nl9_user(), **body)})


@app.patch("/api/community/character")
def api_community_character_update():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "profile": community_space.update_character(_nl9_user(), **body)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/community/spaces")
def api_community_spaces():
    return jsonify({"spaces": community_space.search_spaces(_nl9_user(), request.args.get("q", ""), request.args.get("kind", ""))})


@app.post("/api/community/spaces")
def api_community_space_create():
    body = request.get_json(silent=True) or {}
    try:
        out = community_space.create_space(_nl9_user(), body.get("kind") or "community", body.get("name") or "",
                                           body.get("description") or "", body.get("visibility") or "public",
                                           body.get("tags") or [], body.get("icon") or "🌐", body.get("rules") or "")
        return jsonify({"ok": True, "space": out}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/community/spaces/<space_id>")
def api_community_space(space_id):
    out = community_space.get_space(space_id)
    return (jsonify(out) if out else (jsonify({"error": "Espaço não encontrado."}), 404))


@app.post("/api/community/spaces/<space_id>/join")
def api_community_space_join(space_id):
    body = request.get_json(silent=True) or {}
    return jsonify(community_space.join_space(_nl9_user(), space_id, body.get("invite_code") or ""))


@app.post("/api/community/spaces/<space_id>/leave")
def api_community_space_leave(space_id):
    return jsonify(community_space.leave_space(_nl9_user(), space_id))


@app.post("/api/community/spaces/<space_id>/invite")
def api_community_space_invite(space_id):
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(community_space.create_invite(_nl9_user(), space_id, body.get("max_uses", 20), body.get("hours", 72)))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 403


@app.get("/api/community/feed")
def api_community_feed():
    return jsonify({"posts": community_space.feed(_nl9_user(), request.args.get("space_id", ""), request.args.get("limit", 40, type=int))})


@app.post("/api/community/posts")
def api_community_post_create():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "post": community_space.create_post(_nl9_user(), body.get("space_id") or "", body.get("title") or "",
                                                                          body.get("body") or "", body.get("kind") or "discussion", body.get("channel") or "general")}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/community/posts/<post_id>/like")
def api_community_post_like(post_id):
    return jsonify(community_space.react_post(_nl9_user(), post_id))

@app.post("/api/nl9/social/like")
def api_nl9_social_like():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.like_game(body.get("game_id") or "", _nl9_user()))

@app.post("/api/nl9/social/comment")
def api_nl9_social_comment():
    body = request.get_json(silent=True) or {}
    return jsonify(nl9.comment_game(body.get("game_id") or "", _nl9_user(), body.get("text") or ""))

@app.get("/api/nl9/social/<gid>")
def api_nl9_social_get(gid):
    return jsonify(nl9.get_game_social(gid))


# ---------------------------------------------------------------------------
# NEXT LEVEL 10 MAX — nível mais avançado (Claude: marketplace, torneio, etc.)
# ---------------------------------------------------------------------------

@app.route("/proximo-nivel-10")
@app.route("/next-level10")
def next_level10_page():
    return render_template("next_level10.html")

@app.get("/api/nl10/overview")
def api_nl10_overview():
    return jsonify(nl10.next_level10_overview(_nl10_user()))

# Jogos
@app.route("/api/nl10/marketplace", methods=["GET", "POST"])
def api_nl10_marketplace():
    uid = _nl10_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.marketplace_list_item(
            uid, body.get("game_id") or "", body.get("title") or "Jogo",
            body.get("price_xp", 0), body.get("description") or ""))
    return jsonify({"listings": nl10.marketplace_list()})

@app.post("/api/nl10/marketplace/buy")
def api_nl10_marketplace_buy():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.marketplace_buy(_nl10_user(), body.get("listing_id") or "", int(body.get("buyer_xp", 0))))

@app.route("/api/nl10/tournament", methods=["GET", "POST"])
def api_nl10_tournament():
    uid = _nl10_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.create_tournament(uid, body.get("name") or "Torneio", body.get("game_id") or "", body.get("max_players", 8)))
    return jsonify({"tournaments": nl10.list_tournaments()})

@app.post("/api/nl10/tournament/<tid>/join")
def api_nl10_tournament_join(tid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.join_tournament(tid, _nl10_user(), body.get("name") or ""))

@app.get("/api/nl10/tournament/<tid>")
def api_nl10_tournament_get(tid):
    t = nl10.get_tournament(tid)
    if not t:
        return jsonify({"ok": False, "error": "Não encontrado"}), 404
    return jsonify(t)

@app.post("/api/nl10/tournament/<tid>/result")
def api_nl10_tournament_result(tid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.report_match_result(tid, body.get("match_id") or "", body.get("score1", 0), body.get("score2", 0)))

@app.route("/api/nl10/replay", methods=["GET", "POST"])
def api_nl10_replay():
    uid = _nl10_user()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.save_replay(uid, body.get("game_id") or "", body.get("frames") or [], body.get("meta")))
    return jsonify({"replays": nl10.list_replays(uid)})

@app.get("/api/nl10/replay/<rid>")
def api_nl10_replay_get(rid):
    r = nl10.get_replay(rid)
    if not r:
        return jsonify({"ok": False}), 404
    return jsonify(r)

@app.get("/api/nl10/physics")
def api_nl10_physics():
    return jsonify({"templates": nl10.list_physics_templates()})

@app.get("/api/nl10/physics/<tid>")
def api_nl10_physics_one(tid):
    t = nl10.get_physics_template(tid)
    if not t:
        return jsonify({"ok": False}), 404
    return jsonify(t)

# Programação
@app.post("/api/nl10/code-review")
def api_nl10_code_review():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.code_review_ai_prompt(body.get("code") or "", body.get("language") or "python"))

@app.get("/api/nl10/perf-challenges")
def api_nl10_perf():
    return jsonify({"challenges": nl10.list_perf_challenges()})

@app.get("/api/nl10/perf-challenges/<cid>")
def api_nl10_perf_one(cid):
    c = nl10.get_perf_challenge(cid)
    if not c:
        return jsonify({"ok": False}), 404
    return jsonify(c)

@app.post("/api/nl10/pair-programming")
def api_nl10_pair():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.pair_programming_prompt(body.get("code") or "", body.get("goal") or "", body.get("language") or "python"))

@app.post("/api/nl10/snippet-debugger")
def api_nl10_snippet_dbg():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.snippet_open_in_debugger(body.get("snippet_id") or "", body.get("code")))

# Gamificação
@app.route("/api/nl10/clan", methods=["GET", "POST"])
def api_nl10_clan():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.create_clan(_nl10_user(), body.get("name") or "Clã", body.get("tag") or ""))
    return jsonify({"clans": nl10.list_clans()})

@app.post("/api/nl10/clan/<cid>/join")
def api_nl10_clan_join(cid):
    return jsonify(nl10.join_clan(cid, _nl10_user()))

@app.get("/api/nl10/secrets")
def api_nl10_secrets():
    return jsonify({"achievements": nl10.get_user_secrets(_nl10_user())})

@app.post("/api/nl10/secrets/unlock")
def api_nl10_secrets_unlock():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.unlock_secret(_nl10_user(), body.get("id") or ""))

@app.get("/api/nl10/rotating-shop")
def api_nl10_shop():
    return jsonify(nl10.current_rotating_shop())

@app.post("/api/nl10/rotating-shop/buy")
def api_nl10_shop_buy():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.buy_rotating_item(_nl10_user(), body.get("item_id") or "", int(body.get("xp", 0))))

# Certificados
@app.post("/api/nl10/cert/issue")
def api_nl10_cert_issue():
    body = request.get_json(silent=True) or {}
    cert = nl10.issue_verifiable_cert(
        _nl10_user(),
        body.get("user_name") or _nl10_user(),
        body.get("track") or "Trilha",
        float(body.get("score", 0)),
        float(body.get("hours", 0)),
    )
    return jsonify({"ok": True, "cert": cert})

@app.get("/api/nl10/cert/verify/<token>")
def api_nl10_cert_verify(token):
    return jsonify(nl10.verify_cert(token))

@app.get("/api/nl10/cert/mine")
def api_nl10_cert_mine():
    return jsonify({"certs": nl10.list_user_certs(_nl10_user())})

# Estudos
@app.get("/api/nl10/search")
def api_nl10_search():
    return jsonify(nl10.unified_search(request.args.get("q") or ""))

@app.post("/api/nl10/offline-pack")
def api_nl10_offline():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.create_offline_pack(_nl10_user(), body.get("track_id") or "", body.get("items") or []))

@app.post("/api/nl10/weekly-summary")
def api_nl10_weekly():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.weekly_summary(_nl10_user(), body.get("learned")))

# Comunidade
@app.route("/api/nl10/mentor", methods=["GET", "POST"])
def api_nl10_mentor():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.request_mentor(_nl10_user(), body.get("topic") or ""))
    return jsonify({"requests": nl10.list_mentor_requests()})

@app.post("/api/nl10/mentor/<rid>/accept")
def api_nl10_mentor_accept(rid):
    return jsonify(nl10.accept_mentor(rid, _nl10_user()))

@app.route("/api/nl10/feed", methods=["GET", "POST"])
def api_nl10_feed():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl10.post_activity(_nl10_user(), body.get("text") or "", body.get("kind") or "general"))
    return jsonify({"items": nl10.activity_feed()})

@app.route("/api/nl10/contribution", methods=["GET", "POST"])
def api_nl10_contrib():
    if request.method == "POST":
        return jsonify(nl10.record_help(_nl10_user()))
    return jsonify(nl10.get_contribution(_nl10_user()))

# Qualidade
@app.get("/api/nl10/status")
@app.get("/status")
def api_nl10_status():
    return jsonify(nl10.status_page())

@app.get("/api/nl10/errors")
def api_nl10_errors():
    return jsonify({"errors": nl10.recent_errors()})

@app.post("/api/nl10/errors")
def api_nl10_errors_post():
    body = request.get_json(silent=True) or {}
    return jsonify(nl10.log_error(body.get("source") or "app", body.get("message") or "", body.get("detail") or ""))

@app.post("/api/nl10/smoke-tests")
def api_nl10_smoke():
    return jsonify(nl10.run_smoke_tests())


# ---------------------------------------------------------------------------
# NEXT LEVEL 11 — features ambiciosas (lista Claude screenshots)
# ---------------------------------------------------------------------------

@app.route("/proximo-nivel-11")
@app.route("/next-level11")
def next_level11_page():
    return render_template("next_level11.html")

@app.get("/api/nl11/overview")
def api_nl11_overview():
    return jsonify(nl11.next_level11_overview(_nl11_user()))

# Jogos
@app.route("/api/nl11/ai-game", methods=["GET", "POST"])
def api_nl11_ai_game():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.generate_game_from_text(_nl11_user(), body.get("description") or ""))
    return jsonify({"games": nl11.list_ai_games(_nl11_user())})

@app.route("/api/nl11/coop", methods=["GET", "POST"])
def api_nl11_coop():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.create_coop_room(_nl11_user(), body.get("game_id") or "", body.get("max_players", 4)))
    return jsonify({"rooms": nl11.list_coop_rooms()})

@app.post("/api/nl11/coop/<rid>/join")
def api_nl11_coop_join(rid):
    return jsonify(nl11.join_coop_room(rid, _nl11_user()))

@app.route("/api/nl11/mods", methods=["GET", "POST"])
def api_nl11_mods():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.publish_mod(_nl11_user(), body.get("game_id") or "", body.get("title") or "", body.get("description") or "", body.get("content")))
    return jsonify({"mods": nl11.list_mods(request.args.get("game_id"))})

@app.route("/api/nl11/global-rank", methods=["GET", "POST"])
def api_nl11_global_rank():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.record_global_score(_nl11_user(), body.get("game_id") or "demo", int(body.get("score", 0)), body.get("meta")))
    return jsonify({"ranking": nl11.global_ranking()})

# Programação
@app.route("/api/nl11/month-project", methods=["GET", "POST"])
def api_nl11_month_project():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.create_month_project(_nl11_user(), body.get("title") or "", body.get("description") or "", int(body.get("days", 14))))
    return jsonify({"projects": nl11.list_month_projects()})

@app.post("/api/nl11/month-project/<pid>/join")
def api_nl11_month_join(pid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.join_month_project(pid, _nl11_user(), body.get("team_name") or ""))

@app.post("/api/nl11/lint")
def api_nl11_lint():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.lint_code(body.get("code") or "", body.get("language") or "python"))

@app.post("/api/nl11/interview")
def api_nl11_interview():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.start_tech_interview(_nl11_user(), body.get("level") or "junior"))

@app.post("/api/nl11/interview/answer")
def api_nl11_interview_answer():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.answer_interview(body.get("session_id") or "", body.get("question_id") or "", body.get("answer") or ""))

@app.post("/api/nl11/algo-viz")
def api_nl11_algo_viz():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.algorithm_viz_steps(body.get("algo") or "bubble", body.get("data")))

# Gamificação
@app.get("/api/nl11/season")
def api_nl11_season():
    return jsonify(nl11.season_ranking())

@app.post("/api/nl11/season/xp")
def api_nl11_season_xp():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.season_add_xp(_nl11_user(), int(body.get("xp", 0))))

@app.get("/api/nl11/missions")
def api_nl11_missions():
    return jsonify(nl11.get_daily_missions(_nl11_user()))

@app.post("/api/nl11/missions/complete")
def api_nl11_missions_complete():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.complete_mission(_nl11_user(), body.get("mission_id") or "", body.get("scope") or "daily"))

@app.route("/api/nl11/clan-bet", methods=["GET", "POST"])
def api_nl11_clan_bet():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.place_clan_bet(body.get("clan_id") or "", body.get("tournament_id") or "", int(body.get("amount_xp", 0)), _nl11_user()))
    return jsonify({"bets": nl11.list_clan_bets(request.args.get("tournament_id"))})

@app.post("/api/nl11/clan-bet/<bid>/resolve")
def api_nl11_clan_bet_resolve(bid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.resolve_clan_bet(bid, body.get("winner_clan") or ""))

# Certificados
@app.post("/api/nl11/cert/issue")
def api_nl11_cert_issue():
    body = request.get_json(silent=True) or {}
    skills = body.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    cert = nl11.issue_skills_cert(_nl11_user(), body.get("user_name") or _nl11_user(), body.get("track") or "Trilha", skills, float(body.get("score", 80)))
    return jsonify({"ok": True, "cert": cert})

@app.get("/api/nl11/cert/verify/<token>")
def api_nl11_cert_verify(token):
    return jsonify(nl11.verify_skills_cert(token))

@app.get("/api/nl11/cert/mine")
def api_nl11_cert_mine():
    return jsonify({"certs": nl11.list_user_skills_certs(_nl11_user())})

# Estudos
@app.post("/api/nl11/study-plan")
def api_nl11_study_plan():
    body = request.get_json(silent=True) or {}
    known = body.get("known_topics") or []
    if isinstance(known, str):
        known = [s.strip() for s in known.split(",") if s.strip()]
    return jsonify(nl11.generate_study_plan(_nl11_user(), known, body.get("goal") or ""))

@app.post("/api/nl11/simulado")
def api_nl11_simulado():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.create_simulado(_nl11_user(), body.get("topic") or "geral", int(body.get("minutes", 30)), int(body.get("n_questions", 10))))

@app.post("/api/nl11/simulado/grade")
def api_nl11_simulado_grade():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.grade_simulado(body.get("sim_id") or "", body.get("answers") or []))

@app.route("/api/nl11/teach", methods=["GET", "POST"])
def api_nl11_teach():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.submit_teach_recording(_nl11_user(), body.get("topic") or "", body.get("media_url") or "", body.get("transcript") or ""))
    return jsonify({"recordings": nl11.list_teach_recordings()})

@app.post("/api/nl11/teach/<rid>/rate")
def api_nl11_teach_rate(rid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.rate_teach(rid, _nl11_user(), int(body.get("score", 3)), body.get("comment") or ""))

# Comunidade
@app.route("/api/nl11/events", methods=["GET", "POST"])
def api_nl11_events():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.create_live_event(_nl11_user(), body.get("title") or "", body.get("starts_at") or "", body.get("kind") or "chat"))
    return jsonify({"events": nl11.list_live_events()})

@app.post("/api/nl11/events/<eid>/join")
def api_nl11_events_join(eid):
    return jsonify(nl11.join_live_event(eid, _nl11_user()))

@app.route("/api/nl11/reputation", methods=["GET", "POST"])
def api_nl11_reputation():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.add_reputation(_nl11_user(), int(body.get("points", 0)), body.get("reason") or ""))
    return jsonify(nl11.get_reputation(_nl11_user()))

@app.route("/api/nl11/portfolio", methods=["POST"])
def api_nl11_portfolio_export():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.export_public_portfolio(_nl11_user(), body.get("display_name") or ""))

@app.get("/api/nl11/portfolio/<slug>")
@app.get("/portfolio/<slug>")
def api_nl11_portfolio_get(slug):
    p = nl11.get_portfolio_by_slug(slug)
    if not p:
        return jsonify({"ok": False, "error": "não encontrado"}), 404
    return jsonify({"ok": True, "portfolio": p})

# Infra
@app.post("/api/nl11/backup/export")
def api_nl11_backup_export():
    return jsonify(nl11.export_user_backup(_nl11_user()))

@app.post("/api/nl11/backup/import")
def api_nl11_backup_import():
    body = request.get_json(silent=True) or {}
    return jsonify(nl11.import_user_backup(_nl11_user(), body.get("token") or ""))

@app.route("/api/nl11/theme", methods=["GET", "POST"])
def api_nl11_theme():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.set_user_theme(_nl11_user(), body.get("theme") or "dark", body.get("custom")))
    return jsonify(nl11.get_user_theme(_nl11_user()))

@app.get("/api/nl11/analytics")
def api_nl11_analytics():
    return jsonify(nl11.admin_analytics())

@app.get("/api/nl11/i18n")
def api_nl11_i18n():
    lang = request.args.get("lang") or "pt"
    return jsonify({"lang": lang, "strings": nl11.i18n_dict(lang)})

# Mobile / PWA push
@app.route("/api/nl11/push", methods=["GET", "POST"])
def api_nl11_push():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl11.register_push_subscription(_nl11_user(), body.get("endpoint") or "", body.get("keys")))
    return jsonify({"subscriptions": nl11.list_push_targets()})


# ---------------------------------------------------------------------------
# Nível 12 — Polimento + Novas Áreas (lista Claude screenshots)
# ---------------------------------------------------------------------------
@app.route("/proximo-nivel-12")
@app.route("/next-level12")
def next_level12_page():
    return render_template("next_level12.html")

@app.get("/api/nl12/overview")
def api_nl12_overview():
    return jsonify(nl12.next_level12_overview(_nl12_user()))

# Acessibilidade
@app.route("/api/nl12/a11y", methods=["GET", "POST"])
def api_nl12_a11y():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.set_a11y_prefs(_nl12_user(), body))
    return jsonify(nl12.get_a11y_prefs(_nl12_user()))

@app.post("/api/nl12/tts")
def api_nl12_tts():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.tts_preview(body.get("text") or "", body.get("lang") or "pt-BR"))

# Admin / sala de aula
@app.route("/api/nl12/classroom", methods=["GET", "POST"])
def api_nl12_classroom():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.create_classroom(_nl12_user(), body.get("name") or "", body.get("description") or ""))
    return jsonify({"classes": nl12.list_classrooms(_nl12_user())})

@app.post("/api/nl12/classroom/<cid>/student")
def api_nl12_class_student(cid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.add_student_to_class(cid, body.get("student_id") or "", _nl12_user()))

@app.post("/api/nl12/classroom/<cid>/assign")
def api_nl12_class_assign(cid):
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.assign_exercise(cid, _nl12_user(), body.get("title") or "", body.get("exercise_id") or ""))

@app.get("/api/nl12/classroom/<cid>/report")
def api_nl12_class_report(cid):
    return jsonify(nl12.class_report(cid, _nl12_user()))

@app.post("/api/nl12/parent/link")
def api_nl12_parent_link():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.link_parent_account(_nl12_user(), body.get("child_id") or ""))

@app.get("/api/nl12/parent/dashboard")
def api_nl12_parent_dash():
    return jsonify(nl12.parent_dashboard(_nl12_user()))

@app.post("/api/nl12/moderation/report")
def api_nl12_mod_report():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.report_content(_nl12_user(), body.get("content_type") or "", body.get("content_id") or "", body.get("reason") or ""))

@app.get("/api/nl12/moderation/queue")
def api_nl12_mod_queue():
    return jsonify(nl12.moderation_queue(request.args.get("status") or "pending"))

@app.post("/api/nl12/moderation/<item_id>")
def api_nl12_mod_action(item_id):
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.moderate_item(item_id, body.get("action") or "", _nl12_user()))

# Planos / parcerias
@app.get("/api/nl12/plans")
def api_nl12_plans():
    return jsonify(nl12.list_plans())

@app.route("/api/nl12/plan", methods=["GET", "POST"])
def api_nl12_plan():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.set_user_plan(_nl12_user(), body.get("plan") or "free"))
    return jsonify(nl12.get_user_plan(_nl12_user()))

@app.route("/api/nl12/partnership", methods=["GET", "POST"])
def api_nl12_partnership():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.request_partnership(body.get("org_name") or "", body.get("contact_email") or "", body.get("type") or "school"))
    return jsonify(nl12.list_partnerships())

# Integrações
@app.route("/api/nl12/api-key", methods=["GET", "POST"])
def api_nl12_api_key():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.create_api_key(_nl12_user(), body.get("label") or "default"))
    return jsonify(nl12.list_api_keys(_nl12_user()))

@app.route("/api/nl12/social", methods=["GET", "POST"])
def api_nl12_social():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.link_social_login(_nl12_user(), body.get("provider") or "", body.get("external_id") or ""))
    return jsonify(nl12.list_social_links(_nl12_user()))

@app.post("/api/nl12/export/progress")
def api_nl12_export_progress():
    return jsonify(nl12.export_progress_json(_nl12_user()))

# Insights
@app.get("/api/nl12/report/monthly")
def api_nl12_monthly():
    return jsonify(nl12.monthly_report(_nl12_user()))

@app.get("/api/nl12/report/evolution")
def api_nl12_evolution():
    return jsonify(nl12.evolution_chart(_nl12_user()))

# Conteúdo
@app.post("/api/nl12/quiz/from-text")
def api_nl12_quiz():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.generate_quiz_from_text(_nl12_user(), body.get("text") or "", int(body.get("n_questions", 5))))

@app.get("/api/nl12/tracks")
def api_nl12_tracks():
    return jsonify(nl12.list_interest_tracks())

@app.post("/api/nl12/tracks/start")
def api_nl12_track_start():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.start_interest_track(_nl12_user(), body.get("track") or ""))

@app.get("/api/nl12/news")
def api_nl12_news():
    return jsonify(nl12.tech_news_digest())

# Ferramentas
@app.post("/api/nl12/palette")
def api_nl12_palette():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.generate_palette(body.get("seed") or "", int(body.get("n_colors", 5))))

@app.post("/api/nl12/convert")
def api_nl12_convert():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.convert_media_stub(body.get("filename") or "", body.get("target_format") or ""))

@app.get("/api/nl12/resume/templates")
def api_nl12_resume_tpl():
    return jsonify(nl12.list_resume_templates())

@app.post("/api/nl12/resume/draft")
def api_nl12_resume_draft():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.generate_resume_draft(_nl12_user(), body.get("template") or "dev_junior", body.get("display_name") or ""))

# Engajamento
@app.post("/api/nl12/reward/surprise")
def api_nl12_reward():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.roll_surprise_reward(_nl12_user(), body.get("task_id") or ""))

@app.post("/api/nl12/invite")
def api_nl12_invite():
    return jsonify(nl12.create_invite(_nl12_user()))

@app.post("/api/nl12/invite/redeem")
def api_nl12_invite_redeem():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.redeem_invite(body.get("code") or "", _nl12_user()))

# Uau
@app.post("/api/nl12/jarvis/plan")
def api_nl12_jarvis():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.jarvis_plan_route(_nl12_user(), body.get("intent") or ""))

@app.get("/api/nl12/onboarding")
def api_nl12_onboarding():
    return jsonify(nl12.cinematic_onboarding_state(_nl12_user()))

@app.post("/api/nl12/onboarding/complete")
def api_nl12_onboarding_done():
    return jsonify(nl12.complete_onboarding(_nl12_user()))

@app.post("/api/nl12/one-click")
def api_nl12_one_click():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.one_click_game(_nl12_user(), body.get("idea") or ""))

# Visual
@app.route("/api/nl12/theme", methods=["GET", "POST"])
def api_nl12_theme():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        return jsonify(nl12.set_visual_theme(_nl12_user(), body))
    return jsonify(nl12.get_visual_theme(_nl12_user()))

@app.get("/api/nl12/mascot/tip")
def api_nl12_mascot():
    return jsonify(nl12.jarvis_mascot_tip(request.args.get("context") or ""))

# Inteligência
@app.post("/api/nl12/intel/pattern")
def api_nl12_pattern():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.record_activity_pattern(_nl12_user(), body.get("hour"), body.get("action") or ""))

@app.get("/api/nl12/intel/suggest")
def api_nl12_suggest():
    return jsonify(nl12.suggest_next_step(_nl12_user()))

@app.post("/api/nl12/intel/fail")
def api_nl12_fail():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.report_exercise_fail(_nl12_user(), body.get("exercise_id") or "unknown"))

@app.post("/api/nl12/intel/fail/reset")
def api_nl12_fail_reset():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.reset_exercise_fails(_nl12_user(), body.get("exercise_id") or "unknown"))

# Polimento
@app.get("/api/nl12/polish")
def api_nl12_polish():
    return jsonify(nl12.get_polish_checklist())

@app.post("/api/nl12/polish/toggle")
def api_nl12_polish_toggle():
    body = request.get_json(silent=True) or {}
    return jsonify(nl12.toggle_polish_item(body.get("item_id") or "", body.get("done")))


from routes_cyber import bp as cyber_bp  # noqa: E402
app.register_blueprint(cyber_bp)

# Final Cyber Lab schema bootstrap: idempotent, creates only missing tables.
try:
    from services import final_ops, ultra_ops, platform_ultra
    final_ops.conn().close()
    ultra_ops.conn().close()
    platform_ultra.conn().close()
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
