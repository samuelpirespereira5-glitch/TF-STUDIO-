import json
import os
import re
import secrets
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash, check_password_hash

from services import totp as totp_mod

BASE_DIR = Path(__file__).resolve().parent.parent
AUTH_FILE = BASE_DIR / "auth.json"

DEFAULT_AUTH = {
    "master_password_hash": "",
    "owner_email": "",          # e-mail do proprietário (identificação / recuperação)
    "tokens": {},  # sha256(token) -> metadata (never plaintext token)
    "session_version": 1,
    "sessions": {},  # sha256(session_id) -> server-side identity/session metadata
    "access_log": [],  # [{"time","ip","user_agent","method","label"}]
    "totp_enabled": False,
    "totp_secret": "",          # só existe depois de confirmado (ver totp_confirm_setup)
    "totp_pending_secret": "",  # gerado em totp_start_setup, some ao confirmar/cancelar
    "totp_recovery_hashes": [],  # hash de códigos de recuperação de uso único
    "webauthn_credentials": [], # {id, public_key, user_id, sign_count, name, created, verified}
    "webauthn_user_id": "",       # identificador aleatório estável do proprietário
}

MAX_LOG_ENTRIES = 50
_IS_PRODUCTION = (
    os.getenv("FLASK_ENV", "").strip().lower() == "production"
    or os.getenv("PRODUCTION", "").strip().lower() in {"1", "true", "yes"}
    or any(os.getenv(k) for k in ("RENDER", "RAILWAY_ENVIRONMENT", "DYNO", "FLY_APP_NAME", "K_SERVICE"))
)

def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()

def _token_id(token_hash: str) -> str:
    return (token_hash or "")[:12]

def _token_entry(token_or_id: str):
    value = (token_or_id or "").strip()
    tokens = AUTH.get("tokens", {})
    if value in tokens:
        return value, tokens[value]
    if value in {_token_id(k) for k in tokens}:
        for k, entry in tokens.items():
            if _token_id(k) == value:
                return k, entry
    h = _token_hash(value)
    if h in tokens:
        return h, tokens[h]
    return None, None


def _load():
    try:
        if AUTH_FILE.exists():
            data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = {**DEFAULT_AUTH, **data}
                if not isinstance(merged.get("sessions"), dict):
                    merged["sessions"] = {}
                return merged
    except Exception as exc:
        try:
            import logging
            logging.getLogger("jarvis.auth").exception(
                "Não foi possível ler auth.json; autenticação não será tratada como configurada: %s",
                type(exc).__name__,
            )
        except Exception:
            pass
    return DEFAULT_AUTH.copy()


AUTH = _load()



def _save():
    """Grava de forma atômica (arquivo temporário + rename, sem corromper se o
    processo cair no meio) e com permissão 600 (só o dono do processo lê —
    o arquivo guarda hash da senha, tokens e chaves)."""
    try:
        tmp = AUTH_FILE.with_suffix(".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(AUTH, ensure_ascii=False, indent=2))
        os.replace(tmp, AUTH_FILE)
        return True
    except Exception:
        return False


def _migrate_plaintext_tokens():
    tokens = AUTH.get("tokens", {})
    changed = False
    new_tokens = {}
    for key, entry in list(tokens.items()):
        if len(str(key)) == 64 and re.fullmatch(r"[0-9a-f]{64}", str(key)):
            new_tokens[key] = entry
            continue
        if key and isinstance(entry, dict):
            new_tokens[_token_hash(key)] = entry
            changed = True
    if changed:
        AUTH["tokens"] = new_tokens
        _save()

_migrate_plaintext_tokens()


# Senhas fracas mais comuns (PT/EN) e palavras-base que não devem ser a senha
# inteira mesmo com números/símbolos em volta (ex.: "Senha@2024!!").
_COMMON_PASSWORDS = {
    "123456789012", "1234567890123", "password1234", "password12345", "qwertyuiop12",
    "qwertyuiopas", "senha1234567", "senhasenhasenha", "administrator", "administrador",
    "mudar123456", "trocar123456", "iloveyou1234", "letmein123456", "welcome12345",
    "abcdefghijkl", "abc123456789", "brasil123456", "corinthians1910", "flamengo123456",
}
_BAD_BASE_WORDS = {
    "password", "senha", "senhamestre", "masterpassword", "admin", "administrator",
    "administrador", "qwerty", "qwertyuiop", "jarvis", "tristan", "thorne",
    "tristanthorne", "brasil", "mudar", "trocar", "welcome", "letmein", "iloveyou",
}
MIN_PASSWORD_LEN = 12
MAX_PASSWORD_LEN = 1024


def validate_password_strength(raw_password: str):
    """Política da senha mestre. Retorna (ok, mensagem_de_erro).

    Aceita frase-senha longa (ex.: quatro palavras soltas) — comprimento vale
    mais que símbolos exóticos. Recusa: curta demais, só números, caractere
    repetido, sequências óbvias e senhas/base-words comuns.
    """
    pw = (raw_password or "").strip()
    if len(pw) < MIN_PASSWORD_LEN:
        return False, f"A senha mestre precisa ter pelo menos {MIN_PASSWORD_LEN} caracteres (uma frase longa serve)."
    if len(pw) > MAX_PASSWORD_LEN:
        return False, f"A senha mestre pode ter no máximo {MAX_PASSWORD_LEN} caracteres."
    low = pw.lower()
    if pw.isdigit():
        return False, "Não use uma senha só com números."
    if len(set(low)) < 6:
        return False, "Senha com poucos caracteres diferentes. Misture mais (ou use uma frase longa)."
    if low in _COMMON_PASSWORDS:
        return False, "Essa senha é muito comum. Escolha outra."
    letters_only = re.sub(r"[^a-z]", "", low)
    if letters_only in _BAD_BASE_WORDS:
        return False, "Essa senha é só uma palavra previsível com números/símbolos. Use uma frase longa."
    ordered = "abcdefghijklmnopqrstuvwxyz0123456789"
    if low in ordered or low[::-1] in ordered:
        return False, "Não use sequências como abcdef ou 123456."
    return True, ""


def _env_hash() -> str:
    return _normalize_hash_value(os.getenv("MASTER_PASSWORD_HASH", ""))


def _env_plain() -> str:
    """Mantido apenas para diagnóstico de configuração legada.

    MASTER_PASSWORD nunca é usado para autenticar. O fluxo oficial aceita
    somente MASTER_PASSWORD_HASH ou o hash persistido em auth.json.
    """
    return (os.getenv("MASTER_PASSWORD", "") or os.getenv("MASTER_PASSWOR", "")).strip()


def password_source() -> str:
    """Fonte efetiva da credencial: somente hash, nunca senha em claro."""
    if _env_hash():
        return "env_hash"
    if AUTH.get("master_password_hash"):
        return "file"
    return ""


def has_master_password():
    return bool(password_source())


def auth_config_state():
    env_hash = bool(_env_hash())
    env_plain = bool(_env_plain())
    stored = bool(AUTH.get("master_password_hash"))
    return {
        "production": _IS_PRODUCTION,
        "hash_configured": env_hash or stored,
        "hash_from_environment": env_hash,
        "plaintext_configured": env_plain,
        "plaintext_active": False,
        "ambiguous_environment": bool(env_hash and env_plain),
        "plaintext_ignored": env_plain,
        "ready": production_auth_ready(),
        "source": password_source() or "none",
    }


def production_auth_ready():
    """Produção só inicia com hash configurado; nunca com senha em claro."""
    return (not _IS_PRODUCTION) or bool(_env_hash()) or bool(AUTH.get("master_password_hash"))

def set_master_password(raw_password: str):
    """Cria o hash mestre usando sempre scrypt explícito e persiste atomicamente."""
    raw_password = (raw_password or "").strip()
    if not raw_password:
        return False
    try:
        value = generate_password_hash(raw_password, method="scrypt")
        if not value.startswith("scrypt:"):
            return False
        AUTH["master_password_hash"] = value
        return _save()
    except Exception:
        return False


def _normalize_hash_value(hash_value: str) -> str:
    if not hash_value or not isinstance(hash_value, str):
        return ""
    hv = hash_value.strip().strip("'").strip('"').strip()
    hv = "".join(hv.split())
    if "\\$" in hv:
        hv = hv.replace("\\$", "$")
    return hv


def _safe_check_hash(hash_value: str, raw_password: str) -> bool:
    hv = _normalize_hash_value(hash_value)
    if not hv or ":" not in hv or "$" not in hv:
        try:
            import logging
            logging.getLogger("jarvis.auth").warning(
                "MASTER_PASSWORD_HASH inválido ou incompleto (len=%d). Gere um novo hash e cole o valor completo.",
                len(hv),
            )
        except Exception:
            pass
        return False
    try:
        return bool(check_password_hash(hv, raw_password))
    except (ValueError, TypeError, AttributeError):
        try:
            import logging
            logging.getLogger("jarvis.auth").warning(
                "Falha técnica ao verificar MASTER_PASSWORD_HASH; valor não será exposto."
            )
        except Exception:
            pass
        return False


def check_master_password(raw_password: str) -> bool:
    """Única rotina de verificação da senha mestre.

    Não há fallback para senha em claro. A prioridade é hash de ambiente;
    sem ele, usa o hash persistido. A comparação é feita exclusivamente por
    werkzeug.check_password_hash; hashes nunca são descriptografados.
    """
    raw_password = (raw_password or "").strip()
    if not raw_password or len(raw_password) > MAX_PASSWORD_LEN:
        return False
    env_hash = _env_hash()
    if env_hash:
        return _safe_check_hash(env_hash, raw_password)
    if _env_plain():
        try:
            import logging
            logging.getLogger("jarvis.auth").warning(
                "MASTER_PASSWORD/MASTER_PASSWOR está definido, mas é ignorado; configure MASTER_PASSWORD_HASH."
            )
        except Exception:
            pass
    return _safe_check_hash(AUTH.get("master_password_hash", ""), raw_password)


def _session_hash(session_id: str) -> str:
    return hashlib.sha256((session_id or "").encode("utf-8")).hexdigest()


def _safe_ip_prefix(value: str) -> str:
    """Armazena apenas um prefixo de rede para sinalização opcional, nunca o IP completo."""
    try:
        import ipaddress
        ip = ipaddress.ip_address((value or "").strip())
        if ip.version == 4:
            return ".".join(str(ip).split(".")[:3]) + ".0/24"
        parts = ip.exploded.split(":")
        return ":".join(parts[:4]) + "::/64"
    except Exception:
        return ""


def create_auth_session(uid: str, role: str, token_scope: bool = False,
                        client_ip: str = "", user_agent: str = "") -> str:
    """Cria identidade server-side com metadados mínimos para detecção de hijacking.
    O navegador recebe apenas o ID aleatório; IP completo nunca é persistido aqui.
    """
    if role not in ("owner", "admin", "user", "guest"):
        raise ValueError("papel de sessão inválido")
    sid = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    sessions = AUTH.setdefault("sessions", {})
    now_ts = time.time()
    try:
        hours = max(1, min(int(os.getenv("SESSION_HOURS", "720")), 24 * 30))
    except ValueError:
        hours = 720
    sessions[_session_hash(sid)] = {
        "uid": str(uid or "")[:120],
        "role": role,
        "token_scope": bool(token_scope),
        "created": now,
        "created_ts": now_ts,
        "expires_ts": now_ts + hours * 3600,
        "last_seen_ts": now_ts,
        "ua_hash": hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest()[:24] if user_agent else "",
        "ip_prefix": _safe_ip_prefix(client_ip),
        "version": current_session_version(),
    }
    # Limite defensivo; sessões antigas são removidas por idade aproximada.
    if len(sessions) > 5000:
        items = sorted(sessions.items(), key=lambda kv: kv[1].get("created", ""))
        for key, _ in items[:len(sessions)-5000]:
            sessions.pop(key, None)
    if not _save():
        sessions.pop(_session_hash(sid), None)
        raise RuntimeError("não foi possível persistir a sessão")
    return sid


def get_auth_session(session_id: str):
    sid = (session_id or "").strip()
    if not sid:
        return None
    entry = AUTH.get("sessions", {}).get(_session_hash(sid))
    if not isinstance(entry, dict):
        return None
    if int(entry.get("version", 0)) != current_session_version():
        return None
    role = entry.get("role")
    if role not in ("owner", "admin", "user", "guest"):
        return None
    return dict(entry)


def session_security_check(session_id: str, client_ip: str = "", user_agent: str = ""):
    """Retorna (ok, reason) e atualiza last_seen. UA mismatch é forte sinal;
    vínculo por rede é opcional para não quebrar usuários em redes móveis."""
    sid = (session_id or "").strip()
    key = _session_hash(sid)
    entry = AUTH.get("sessions", {}).get(key)
    if not isinstance(entry, dict):
        return False, "missing"
    if int(entry.get("version", 0)) != current_session_version():
        return False, "revoked"
    expires = float(entry.get("expires_ts") or 0)
    if expires and time.time() > expires:
        AUTH.get("sessions", {}).pop(key, None)
        _save()
        return False, "expired"
    expected_ua = str(entry.get("ua_hash") or "")
    current_ua = hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest()[:24] if user_agent else ""
    if expected_ua and current_ua and expected_ua != current_ua:
        AUTH.get("sessions", {}).pop(key, None)
        _save()
        return False, "user_agent_changed"
    entry["last_seen_ts"] = time.time()
    if os.getenv("SESSION_BIND_IP", "").strip().lower() in {"1","true","yes","on"}:
        expected_ip = str(entry.get("ip_prefix") or "")
        current_ip = _safe_ip_prefix(client_ip)
        if expected_ip and current_ip and expected_ip != current_ip:
            AUTH.get("sessions", {}).pop(key, None)
            _save()
            return False, "network_changed"
    return True, ""

def list_auth_sessions():
    """Metadados seguros para o Security Center; não expõe session IDs reais."""
    now = time.time()
    out = []
    for h, entry in list(AUTH.get("sessions", {}).items()):
        if not isinstance(entry, dict):
            continue
        if int(entry.get("version", 0)) != current_session_version():
            continue
        expires = float(entry.get("expires_ts") or 0)
        if expires and now > expires:
            AUTH.get("sessions", {}).pop(h, None)
            continue
        out.append({
            "id": h[:12],
            "uid": str(entry.get("uid",""))[:120],
            "role": entry.get("role",""),
            "created": entry.get("created",""),
            "last_seen_ts": entry.get("last_seen_ts"),
            "expires_ts": entry.get("expires_ts"),
            "ip_prefix": entry.get("ip_prefix",""),
            "current_version": int(entry.get("version",0)),
        })
    if out:
        _save()
    return sorted(out, key=lambda x: x.get("last_seen_ts") or 0, reverse=True)

def revoke_session_id(session_id_prefix: str) -> bool:
    prefix = str(session_id_prefix or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{8,64}", prefix):
        return False
    for h in list(AUTH.get("sessions", {})):
        if str(h).startswith(prefix):
            del AUTH["sessions"][h]
            return _save()
    return False

def revoke_auth_session(session_id: str) -> bool:
    key = _session_hash((session_id or "").strip())
    if key in AUTH.get("sessions", {}):
        del AUTH["sessions"][key]
        return _save()
    return False


def generate_token(label: str = "") -> str:
    token = secrets.token_urlsafe(32)
    h = _token_hash(token)
    AUTH.setdefault("tokens", {})[h] = {
        "created": datetime.now(timezone.utc).isoformat(),
        "used": False,
        "label": (label or "").strip()[:80],
        "site_created": False,
    }
    _save()
    return token


def list_tokens():
    """Lista somente metadados seguros; nunca devolve tokens persistidos."""
    out = {}
    for h, info in AUTH.get("tokens", {}).items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(h)):
            continue
        out[_token_id(h)] = {
            "created": info.get("created", ""),
            "used": bool(info.get("used")),
            "site_created": bool(info.get("site_created")),
            "label": info.get("label", ""),
        }
    return out


def revoke_token(token_or_id: str):
    h, entry = _token_entry(token_or_id)
    if h and entry is not None:
        del AUTH["tokens"][h]
        _save()
        return True
    return False


def consume_token(token: str) -> bool:
    """Valida token de uso único sem persistir o segredo em claro."""
    h, entry = _token_entry(token)
    if not entry or entry.get("used"):
        return False
    entry["used"] = True
    _save()
    return True


def mark_token_site_created(token_or_id: str):
    h, entry = _token_entry(token_or_id)
    if entry:
        entry["site_created"] = True
        _save()


def token_site_already_created(token_or_id: str) -> bool:
    _, entry = _token_entry(token_or_id)
    return bool(entry and entry.get("site_created"))


def token_id(token: str) -> str:
    h, entry = _token_entry(token)
    return _token_id(h) if h else ""



def log_access(method: str, label: str = "", ip: str = "", user_agent: str = "") -> None:
    """Registra login/tentativa no auth.json (últimas MAX_LOG_ENTRIES).

    Nunca deve derrubar o login: qualquer falha ao gravar é ignorada.
    """
    try:
        log = AUTH.setdefault("access_log", [])
        log.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "ip": (ip or "")[:64],
            "user_agent": (user_agent or "")[:200],
            "method": (method or "")[:60],
            "label": (label or "")[:200],
        })
        if len(log) > MAX_LOG_ENTRIES:
            del log[:-MAX_LOG_ENTRIES]
        _save()
    except Exception:
        pass


def list_access_log():
    return list(reversed(AUTH.get("access_log", [])))


# ------------------------------------------------------------------
# "Quem está online" — last-seen por sessão (não é histórico, é o
# instante mais recente de atividade de cada tf_uid). Guardado em
# memória (não precisa persistir entre restarts do processo).
# ------------------------------------------------------------------
# Limitação: isto vive em memória do processo. Com múltiplos workers
# (ex.: gunicorn -w N > 1) cada worker só vê quem bateu nele — aceitável
# para o uso deste painel (baixo tráfego), mas não é um contador exato
# em produção com vários processos.
_ONLINE_TTL_SECONDS = 5 * 60
_online = {}  # uid -> {"last_seen": iso, "ip": str, "user_agent": str, "role": str}


def touch_online(uid: str, role: str = "", ip: str = "", user_agent: str = ""):
    if not uid:
        return
    _online[uid] = {
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "ip": ip,
        "user_agent": (user_agent or "")[:200],
    }


def list_online():
    """Só quem teve atividade nos últimos _ONLINE_TTL_SECONDS."""
    now = datetime.now(timezone.utc)
    out = []
    for uid, info in list(_online.items()):
        try:
            last = datetime.fromisoformat(info["last_seen"])
        except Exception:
            continue
        age = (now - last).total_seconds()
        if age > _ONLINE_TTL_SECONDS:
            del _online[uid]
            continue
        out.append({"uid": uid, "seconds_ago": int(age), **info})
    return sorted(out, key=lambda r: r["seconds_ago"])


def current_session_version() -> int:
    return int(AUTH.get("session_version", 1))


def bump_session_version() -> int:
    AUTH["session_version"] = current_session_version() + 1
    _save()
    return AUTH["session_version"]


# ------------------------------------------------------------------
# Chaves de acesso com papel (admin/user) — reutilizáveis e revogáveis.
# A chave só aparece UMA vez (na criação); no disco fica só o hash.
# ------------------------------------------------------------------
import hashlib as _hashlib


def _kh(key: str) -> str:
    return _hashlib.sha256((key or "").encode()).hexdigest()


def create_role_key(role: str, label: str = "") -> str:
    if role not in ("admin", "user"):
        raise ValueError("Papel inválido: use 'admin' ou 'user'.")
    key = "tf_" + role[0] + "_" + secrets.token_urlsafe(24)
    AUTH.setdefault("role_keys", {})[_kh(key)] = {
        "role": role, "label": (label or "").strip()[:80],
        "created": datetime.now(timezone.utc).isoformat(),
    }
    _save()
    return key


def check_role_key(key: str):
    """Retorna {"role","label","id"} se válida, senão None."""
    key = (key or "").strip()
    if not key.startswith("tf_"):
        return None
    h = _kh(key)
    entry = AUTH.get("role_keys", {}).get(h)
    if not entry:
        return None
    return {**entry, "id": h[:10]}


def list_role_keys():
    return [{"id": h[:10], **v} for h, v in AUTH.get("role_keys", {}).items()]


def revoke_role_key(key_id: str) -> bool:
    keys = AUTH.get("role_keys", {})
    for h in list(keys):
        if h[:10] == key_id:
            del keys[h]
            _save()
            return True
    return False


# ------------------------------------------------------------------
# Segundo fator (TOTP) — opcional, só para o login com senha mestre
# (tokens de uso único e chaves de papel continuam de fator único, já
# que são segredos de uso pontual/revogável por natureza).
# ------------------------------------------------------------------
def totp_is_enabled() -> bool:
    return bool(AUTH.get("totp_enabled")) and bool(AUTH.get("totp_secret"))


def totp_setup_in_progress() -> bool:
    return bool(AUTH.get("totp_pending_secret"))


def totp_start_setup() -> dict:
    """Gera um segredo novo (ainda não ativo) e devolve segredo + URI de
    cadastro. Só vira válido para login depois de confirmado com um
    código real do app autenticador (totp_confirm_setup)."""
    secret = totp_mod.generate_secret()
    AUTH["totp_pending_secret"] = secret
    _save()
    return {
        "secret": secret,
        "uri": totp_mod.provisioning_uri(secret),
    }


def totp_cancel_setup():
    AUTH["totp_pending_secret"] = ""
    _save()


def totp_confirm_setup(code: str):
    """Confirma a ativação com um código gerado pelo app. Retorna a lista
    de códigos de recuperação (só dessa vez) em sucesso, ou None se o
    código não bateu ou não havia ativação pendente."""
    secret = AUTH.get("totp_pending_secret", "")
    if not secret or not totp_mod.verify_totp(secret, code):
        return None
    codes = totp_mod.generate_recovery_codes(8)
    AUTH["totp_secret"] = secret
    AUTH["totp_enabled"] = True
    AUTH["totp_pending_secret"] = ""
    AUTH["totp_recovery_hashes"] = [generate_password_hash(c) for c in codes]
    _save()
    return codes


def totp_disable():
    AUTH["totp_enabled"] = False
    AUTH["totp_secret"] = ""
    AUTH["totp_pending_secret"] = ""
    AUTH["totp_recovery_hashes"] = []
    _save()


def totp_verify_login(code: str) -> bool:
    """Valida o código de 6 dígitos OU um código de recuperação (de uso
    único — é consumido/removido ao ser usado)."""
    code = (code or "").strip()
    secret = AUTH.get("totp_secret", "")
    if secret and AUTH.get("totp_enabled") and totp_mod.verify_totp(secret, code):
        return True
    for h in list(AUTH.get("totp_recovery_hashes", [])):
        try:
            if check_password_hash(h, code):
                AUTH["totp_recovery_hashes"].remove(h)
                _save()
                return True
        except Exception:
            continue
    return False


def totp_recovery_codes_remaining() -> int:
    return len(AUTH.get("totp_recovery_hashes", []))


# ------------------------------------------------------------------
# E-mail do proprietário (identificação e dica de recuperação)
# ------------------------------------------------------------------
def get_owner_email() -> str:
    return (AUTH.get("owner_email") or "").strip()


def set_owner_email(email: str) -> bool:
    email = (email or "").strip()[:254]
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        return False
    AUTH["owner_email"] = email
    return _save()


# ------------------------------------------------------------------
# Passkey / WebAuthn (credenciais do proprietário)
# Armazena apenas metadados seguros; a verificação criptográfica completa
# usa o desafio emitido pelo servidor + assinatura do navegador.
# ------------------------------------------------------------------
def get_webauthn_user_id_bytes() -> bytes:
    """Retorna um user handle aleatório estável, nunca derivado do e-mail."""
    raw = str(AUTH.get("webauthn_user_id") or "")
    if raw:
        try:
            return __import__("base64").urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4))
        except Exception:
            pass
    value = secrets.token_bytes(32)
    AUTH["webauthn_user_id"] = __import__("base64").urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    _save()
    return value


def list_webauthn_credentials():
    """Lista apenas metadados; nunca expõe a chave pública completa nem qualquer segredo."""
    out = []
    for c in AUTH.get("webauthn_credentials", []):
        if isinstance(c, dict) and c.get("id"):
            out.append({
                "id": c.get("id", "")[:32],
                "name": (c.get("name") or "Passkey")[:80],
                "created": c.get("created", ""),
                "verified": bool(c.get("verified")),
                "status": "VALIDADA" if c.get("verified") else "LEGADA/RECADASTRAR",
            })
    return out


def add_verified_webauthn_credential(cred_id: str, public_key_b64: str, user_id_b64: str, sign_count: int, name: str = "") -> bool:
    cred_id = (cred_id or "").strip()
    public_key_b64 = (public_key_b64 or "").strip()
    user_id_b64 = (user_id_b64 or "").strip()
    if not cred_id or not public_key_b64 or not user_id_b64 or len(cred_id) > 512 or len(public_key_b64) > 8192:
        return False
    creds = AUTH.setdefault("webauthn_credentials", [])
    for c in creds:
        if c.get("id") == cred_id:
            return False
    creds.append({
        "id": cred_id,
        "public_key": public_key_b64,
        "user_id": user_id_b64,
        "sign_count": max(0, int(sign_count or 0)),
        "name": (name or "Passkey")[:80],
        "created": datetime.now(timezone.utc).isoformat(),
        "verified": True,
    })
    return _save()


def update_webauthn_sign_count(cred_id: str, sign_count: int) -> bool:
    c = get_webauthn_credential(cred_id)
    if not c or not c.get("verified"):
        return False
    c["sign_count"] = max(0, int(sign_count or 0))
    return _save()


def remove_webauthn_credential(cred_id: str) -> bool:
    cred_id = (cred_id or "").strip()
    creds = AUTH.get("webauthn_credentials", [])
    new = [c for c in creds if c.get("id") != cred_id and not str(c.get("id", "")).startswith(cred_id[:16])]
    if len(new) == len(creds):
        return False
    AUTH["webauthn_credentials"] = new
    return _save()


def has_webauthn() -> bool:
    return any(isinstance(c, dict) and c.get("verified") for c in AUTH.get("webauthn_credentials", []))


def get_webauthn_credential(cred_id: str):
    value = (cred_id or "").strip()
    for c in AUTH.get("webauthn_credentials", []):
        if isinstance(c, dict) and c.get("verified") and c.get("id") == value:
            return c
    return None
