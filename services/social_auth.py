"""Social/OIDC authentication for JARVIS.

The master password remains the owner/admin credential. Social providers are
only an optional sign-in method for regular user accounts; provider secrets
never reach the browser and provider access tokens are not persisted.
"""
from __future__ import annotations

import os
import secrets
import time
import json
from pathlib import Path
from urllib.parse import urlencode

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOCIAL_FILE = DATA_DIR / "social_accounts.json"


def _load():
    try:
        if SOCIAL_FILE.exists():
            data = json.loads(SOCIAL_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("accounts", {})
                return data
    except Exception:
        pass
    return {"accounts": {}}


def _save(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SOCIAL_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SOCIAL_FILE)


def configured(provider: str) -> bool:
    p = provider.lower()
    if p == "google":
        return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    if p == "github":
        return bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))
    return False


def redirect_uri(provider: str, request_url_root: str) -> str:
    env_name = f"{provider.upper()}_REDIRECT_URI"
    return os.getenv(env_name, "").strip() or f"{request_url_root.rstrip('/')}/auth/{provider}/callback"


def start(provider: str, request_url_root: str, next_url: str = "") -> dict:
    p = provider.lower()
    if not configured(p):
        return {"ok": False, "error": f"Login com {p.title()} ainda não está configurado no servidor."}
    state = secrets.token_urlsafe(32)
    base = {
        "provider": p,
        "state": state,
        "next": next_url if next_url.startswith("/") and not next_url.startswith("//") else "/",
        "created": time.time(),
    }
    if p == "google":
        params = {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "redirect_uri": redirect_uri(p, request_url_root),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    elif p == "github":
        params = {
            "client_id": os.environ["GITHUB_CLIENT_ID"],
            "redirect_uri": redirect_uri(p, request_url_root),
            "scope": "read:user user:email",
            "state": state,
            "allow_signup": "true",
        }
        url = "https://github.com/login/oauth/authorize?" + urlencode(params)
    else:
        return {"ok": False, "error": "Provedor não suportado."}
    return {"ok": True, "state_data": base, "url": url}


def _http():
    return httpx.Client(timeout=12.0, follow_redirects=False, headers={"User-Agent": "JARVIS/15 social-auth"})


def exchange_google(code: str, request_url_root: str) -> dict:
    ruri = redirect_uri("google", request_url_root)
    with _http() as client:
        token = client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": ruri,
            "grant_type": "authorization_code",
        })
        token.raise_for_status()
        body = token.json()
        id_token = body.get("id_token")
        if not id_token:
            raise ValueError("Google não retornou um ID token.")
        info = client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token})
        info.raise_for_status()
        user = info.json()
    if user.get("aud") != os.environ.get("GOOGLE_CLIENT_ID"):
        raise ValueError("Audience do Google não confere com este aplicativo.")
    if user.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Emissor Google inválido.")
    if str(user.get("email_verified", "")).lower() not in ("true", "1"):
        raise ValueError("A conta Google precisa ter e-mail verificado.")
    return {
        "provider": "google",
        "external_id": str(user.get("sub") or ""),
        "email": str(user.get("email") or ""),
        "name": str(user.get("name") or user.get("email") or "Google User")[:120],
        "avatar": str(user.get("picture") or "")[:500],
    }


def exchange_github(code: str, request_url_root: str) -> dict:
    with _http() as client:
        token = client.post("https://github.com/login/oauth/access_token", data={
            "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
            "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
            "code": code,
            "redirect_uri": redirect_uri("github", request_url_root),
        }, headers={"Accept": "application/json"})
        token.raise_for_status()
        body = token.json()
        access_token = body.get("access_token")
        if not access_token:
            raise ValueError("GitHub não retornou um access token.")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        me = client.get("https://api.github.com/user", headers=headers)
        me.raise_for_status()
        profile = me.json()
        emails = client.get("https://api.github.com/user/emails", headers=headers)
        emails.raise_for_status()
        email_rows = emails.json() if isinstance(emails.json(), list) else []
    verified = [e for e in email_rows if e.get("verified")]
    primary = next((e for e in verified if e.get("primary")), None) or (verified[0] if verified else None)
    email = (primary or {}).get("email") or profile.get("email") or ""
    if not email:
        raise ValueError("Não foi possível obter um e-mail verificado do GitHub.")
    return {
        "provider": "github",
        "external_id": str(profile.get("id") or ""),
        "email": str(email),
        "name": str(profile.get("name") or profile.get("login") or email)[:120],
        "avatar": str(profile.get("avatar_url") or "")[:500],
    }


def upsert_account(identity: dict) -> dict:
    provider = identity["provider"]
    external_id = identity["external_id"]
    key = f"{provider}:{external_id}"
    data = _load()
    accounts = data.setdefault("accounts", {})
    now = time.time()
    existing = accounts.get(key) or {}
    uid = existing.get("uid") or key
    entry = {
        "uid": uid,
        "provider": provider,
        "external_id": external_id,
        "email": identity.get("email", "")[:240],
        "display_name": identity.get("name", "User")[:120],
        "avatar": identity.get("avatar", "")[:500],
        "created_ts": existing.get("created_ts", now),
        "last_login_ts": now,
    }
    accounts[key] = entry
    _save(data)
    return entry
