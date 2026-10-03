"""
JARVIS Community Space — contas, personagem, comunidades e clãs.
Camada complementar: não substitui next_level9/10/11/12.
"""
from __future__ import annotations
import json, re, secrets, threading, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPACE_DIR = DATA_DIR / "community_space"
SPACE_DIR.mkdir(parents=True, exist_ok=True)
_LOCK = threading.RLock()
PROFILES_FILE = SPACE_DIR / "profiles.json"
SPACES_FILE = SPACE_DIR / "spaces.json"
POSTS_FILE = SPACE_DIR / "posts.json"
INVITES_FILE = SPACE_DIR / "invites.json"
ALLOWED_SPACE_KINDS = {"community", "clan"}
ALLOWED_VISIBILITY = {"public", "private"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _clean(value: Any, max_len: int = 120) -> str:
    return str(value or "").strip()[:max_len]


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _clean(value, 80).lower().encode("ascii", "ignore").decode())
    return s.strip("-")[:50] or "espaco"


def _uid(user_id: str) -> str:
    return _clean(user_id, 120) or "owner"


def _profile_default(user_id: str) -> dict:
    return {
        "user_id": _uid(user_id), "username": "", "display_name": "", "bio": "",
        "avatar": "🤖", "interests": [],
        "character": {"name": "", "class": "Explorer", "title": "Recruta JARVIS", "accent": "cyan", "frame": "standard", "origin": "JARVIS Academy", "specialty": "Programação", "companion": "", "ability": "", "motto": "", "name_color": "cyan"},
        "onboarding_complete": False, "created_at": _now(), "updated_at": _now(),
    }


def get_profile(user_id: str) -> dict:
    uid = _uid(user_id)
    with _LOCK:
        data = _load(PROFILES_FILE, {"profiles": {}})
        p = data.setdefault("profiles", {}).get(uid)
        if not isinstance(p, dict):
            p = _profile_default(uid)
            data["profiles"][uid] = p
            _save(PROFILES_FILE, data)
        return dict(p)


def onboarding_state(user_id: str) -> dict:
    p = get_profile(user_id)
    return {"complete": bool(p.get("onboarding_complete")), "profile": p, "needs_character": not bool((p.get("character") or {}).get("name"))}


def complete_onboarding(user_id: str, display_name: str, username: str, bio: str = "", avatar: str = "🤖", interests: list | None = None, character: dict | None = None) -> dict:
    uid = _uid(user_id)
    display_name = _clean(display_name, 60)
    username = re.sub(r"[^a-zA-Z0-9_.-]", "", _clean(username, 24)).lower()
    if not display_name:
        raise ValueError("Nome de exibição obrigatório.")
    if len(username) < 3:
        raise ValueError("O nome de usuário precisa ter pelo menos 3 caracteres.")
    interests = [_clean(x, 30) for x in (interests or []) if _clean(x, 30)][:8]
    char = dict(character or {})
    char_name = _clean(char.get("name"), 40)
    if not char_name:
        raise ValueError("Crie seu personagem antes de continuar.")
    char["name"] = char_name
    char["class"] = _clean(char.get("class"), 30) or "Explorer"
    char["title"] = _clean(char.get("title"), 40) or "Recruta JARVIS"
    char["accent"] = _clean(char.get("accent"), 20) or "cyan"
    char["frame"] = _clean(char.get("frame"), 20) or "standard"
    char["origin"] = _clean(char.get("origin"), 30) or "JARVIS Academy"
    char["specialty"] = _clean(char.get("specialty"), 30) or "Programação"
    char["companion"] = _clean(char.get("companion"), 30)
    char["ability"] = _clean(char.get("ability"), 40)
    char["motto"] = _clean(char.get("motto"), 80)
    char["name_color"] = _clean(char.get("name_color"), 20) or "cyan"
    with _LOCK:
        data = _load(PROFILES_FILE, {"profiles": {}})
        profiles = data.setdefault("profiles", {})
        for other_uid, other in profiles.items():
            if other_uid != uid and isinstance(other, dict) and other.get("username") == username:
                raise ValueError("Esse nome de usuário já está em uso.")
        p = profiles.setdefault(uid, _profile_default(uid))
        p.update({"user_id": uid, "username": username, "display_name": display_name, "bio": _clean(bio, 300),
                  "avatar": _clean(avatar, 8) or "🤖", "interests": interests, "character": char,
                  "onboarding_complete": True, "updated_at": _now()})
        _save(PROFILES_FILE, data)
        return dict(p)


def update_profile(user_id: str, **updates) -> dict:
    p = get_profile(user_id)
    for k in {"display_name", "bio", "avatar", "interests"}:
        if k in updates:
            p[k] = [_clean(x, 30) for x in (updates[k] or [])][:8] if k == "interests" else _clean(updates[k], 300 if k == "bio" else 60)
    p["updated_at"] = _now()
    with _LOCK:
        data = _load(PROFILES_FILE, {"profiles": {}})
        data.setdefault("profiles", {})[_uid(user_id)] = p
        _save(PROFILES_FILE, data)
    return p


def update_character(user_id: str, **updates) -> dict:
    p = get_profile(user_id)
    char = p.setdefault("character", {})
    for k in ("name", "class", "title", "accent", "frame", "origin", "specialty", "companion", "ability", "motto", "name_color"):
        if k in updates:
            char[k] = _clean(updates[k], 80 if k in {"motto", "ability"} else 40)
    if not char.get("name"):
        raise ValueError("O personagem precisa ter um nome.")
    p["updated_at"] = _now()
    with _LOCK:
        data = _load(PROFILES_FILE, {"profiles": {}})
        data.setdefault("profiles", {})[_uid(user_id)] = p
        _save(PROFILES_FILE, data)
    return p


def _space_public(space: dict) -> dict:
    members = space.get("members") or {}
    return {"id": space["id"], "kind": space["kind"], "name": space["name"], "slug": space["slug"],
            "description": space.get("description", ""), "visibility": space.get("visibility", "public"),
            "owner": space["owner"], "tags": space.get("tags", []), "icon": space.get("icon", "🌐"),
            "created_at": space.get("created_at"), "members_count": len(members), "channels": space.get("channels", []),
            "rules": space.get("rules", "")}


def create_space(user_id: str, kind: str, name: str, description: str = "", visibility: str = "public", tags: list | None = None, icon: str = "🌐", rules: str = "") -> dict:
    uid = _uid(user_id); kind = kind if kind in ALLOWED_SPACE_KINDS else "community"; name = _clean(name, 70)
    if len(name) < 3: raise ValueError("O nome precisa ter pelo menos 3 caracteres.")
    visibility = visibility if visibility in ALLOWED_VISIBILITY else "public"
    tags = [_clean(x, 24) for x in (tags or []) if _clean(x, 24)][:8]
    prefix = "clan" if kind == "clan" else "com"
    space = {"id": f"{prefix}_{uuid.uuid4().hex[:10]}", "kind": kind, "name": name, "slug": f"{_slug(name)}-{secrets.token_hex(3)}",
             "description": _clean(description, 500), "visibility": visibility, "owner": uid, "tags": tags,
             "icon": _clean(icon, 8) or ("⚔️" if kind == "clan" else "🌐"), "rules": _clean(rules, 1000), "created_at": _now(),
             "members": {uid: {"role": "owner", "joined_at": _now()}},
             "channels": [{"id":"general","name":"geral","description":"Conversa principal"},
                          {"id":"announcements","name":"avisos","description":"Novidades e comunicados"},
                          {"id":"projects","name":"projetos","description":"Projetos, jogos e estudos"}]}
    with _LOCK:
        data = _load(SPACES_FILE, {"spaces": {}}); data.setdefault("spaces", {})[space["id"]] = space; _save(SPACES_FILE, data)
    return _space_public(space)


def list_spaces(user_id: str = "", kind: str = "", include_private_owned: bool = True) -> list:
    uid = _uid(user_id) if user_id else ""; kind = kind if kind in ALLOWED_SPACE_KINDS else ""
    with _LOCK:
        data = _load(SPACES_FILE, {"spaces": {}}); rows = []
        for s in data.get("spaces", {}).values():
            if kind and s.get("kind") != kind: continue
            is_member = uid in (s.get("members") or {})
            if s.get("visibility") == "private" and not (is_member or (include_private_owned and s.get("owner") == uid)): continue
            row = _space_public(s); row["is_member"] = is_member
            row["role"] = (s.get("members") or {}).get(uid, {}).get("role", "") if uid else ""
            rows.append(row)
        rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return rows[:100]


def get_space(space_id: str) -> dict | None:
    with _LOCK:
        s = _load(SPACES_FILE, {"spaces": {}}).get("spaces", {}).get(_clean(space_id, 80))
        return _space_public(s) if isinstance(s, dict) else None


def join_space(user_id: str, space_id: str, invite_code: str = "") -> dict:
    uid = _uid(user_id)
    with _LOCK:
        data = _load(SPACES_FILE, {"spaces": {}}); spaces = data.get("spaces", {}); s = spaces.get(_clean(space_id, 80))
        if not s: return {"ok": False, "error": "Espaço não encontrado."}
        if uid in s.setdefault("members", {}): return {"ok": True, "space": _space_public(s), "message": "Você já é membro."}
        if s.get("visibility") == "private":
            if not invite_code: return {"ok": False, "error": "Esse espaço é privado e exige convite."}
            invites = _load(INVITES_FILE, {"invites": {}}).get("invites", {}); inv = invites.get(invite_code)
            if not inv or inv.get("space_id") != s["id"]: return {"ok": False, "error": "Convite inválido."}
            if inv.get("expires_at", "") and inv["expires_at"] < _now(): return {"ok": False, "error": "Convite expirado."}
            if int(inv.get("uses", 0)) >= int(inv.get("max_uses", 20)): return {"ok": False, "error": "Limite do convite atingido."}
            inv["uses"] = int(inv.get("uses", 0)) + 1; _save(INVITES_FILE, {"invites": invites})
        s["members"][uid] = {"role": "member", "joined_at": _now()}; _save(SPACES_FILE, data)
        return {"ok": True, "space": _space_public(s)}


def leave_space(user_id: str, space_id: str) -> dict:
    uid = _uid(user_id)
    with _LOCK:
        data = _load(SPACES_FILE, {"spaces": {}}); s = data.get("spaces", {}).get(_clean(space_id, 80))
        if not s: return {"ok": False, "error": "Espaço não encontrado."}
        if s.get("owner") == uid: return {"ok": False, "error": "O dono deve transferir ou excluir o espaço antes de sair."}
        s.setdefault("members", {}).pop(uid, None); _save(SPACES_FILE, data); return {"ok": True}


def create_invite(user_id: str, space_id: str, max_uses: int = 20, hours: int = 72) -> dict:
    uid = _uid(user_id)
    with _LOCK:
        data = _load(SPACES_FILE, {"spaces": {}}); s = data.get("spaces", {}).get(_clean(space_id, 80))
        if not s: raise ValueError("Espaço não encontrado.")
        member = s.get("members", {}).get(uid)
        if not member or member.get("role") not in {"owner", "admin", "moderator"}: raise ValueError("Você não tem permissão para criar convites.")
        code = secrets.token_urlsafe(8); expires = datetime.now(timezone.utc) + timedelta(hours=max(1, min(int(hours or 72), 720)))
        invites = _load(INVITES_FILE, {"invites": {}}); invites.setdefault("invites", {})[code] = {
            "space_id": s["id"], "created_by": uid, "created_at": _now(), "expires_at": expires.isoformat(), "uses": 0,
            "max_uses": max(1, min(int(max_uses or 20), 500))}
        _save(INVITES_FILE, invites); return {"ok": True, "code": code, "expires_at": expires.isoformat(), "space_id": s["id"]}


def create_post(user_id: str, space_id: str, title: str, body: str, kind: str = "discussion", channel: str = "general") -> dict:
    uid = _uid(user_id); title = _clean(title, 120); body = _clean(body, 4000)
    if not body: raise ValueError("Escreva o conteúdo da publicação.")
    with _LOCK:
        spaces = _load(SPACES_FILE, {"spaces": {}}).get("spaces", {}); s = spaces.get(_clean(space_id, 80))
        if not s or uid not in s.get("members", {}): raise ValueError("Você precisa ser membro para publicar.")
        post = {"id": "post_" + uuid.uuid4().hex[:10], "space_id": s["id"], "author": uid, "title": title or "Publicação",
                "body": body, "kind": _clean(kind, 30) or "discussion", "channel": _clean(channel, 40) or "general", "created_at": _now(), "likes": [], "comments": []}
        data = _load(POSTS_FILE, {"posts": []}); data.setdefault("posts", []).insert(0, post); data["posts"] = data["posts"][:1000]; _save(POSTS_FILE, data)
        return dict(post)


def feed(user_id: str, space_id: str = "", limit: int = 40) -> list:
    uid = _uid(user_id)
    with _LOCK:
        posts = _load(POSTS_FILE, {"posts": []}).get("posts", []); spaces = _load(SPACES_FILE, {"spaces": {}}).get("spaces", {})
        allowed = {sid for sid, s in spaces.items() if uid in s.get("members", {})}; out = []
        for p in posts:
            if space_id and p.get("space_id") != space_id: continue
            if not space_id and p.get("space_id") not in allowed: continue
            q = dict(p); q["likes_count"] = len(q.get("likes", [])); q["liked_by_me"] = uid in q.get("likes", []); q.pop("likes", None)
            out.append(q)
            if len(out) >= max(1, min(int(limit or 40), 100)): break
        return out


def react_post(user_id: str, post_id: str) -> dict:
    uid = _uid(user_id)
    with _LOCK:
        data = _load(POSTS_FILE, {"posts": []})
        for p in data.get("posts", []):
            if p.get("id") == _clean(post_id, 80):
                likes = p.setdefault("likes", [])
                if uid in likes: likes.remove(uid); liked = False
                else: likes.append(uid); liked = True
                _save(POSTS_FILE, data); return {"ok": True, "liked": liked, "likes": len(likes)}
    return {"ok": False, "error": "Publicação não encontrada."}


def search_spaces(user_id: str, query: str = "", kind: str = "") -> list:
    q = _clean(query, 80).lower(); rows = list_spaces(user_id, kind)
    if not q: return rows
    return [x for x in rows if q in (x["name"] + " " + x.get("description", "") + " " + " ".join(x.get("tags", []))).lower()]


def my_spaces(user_id: str) -> list:
    return [x for x in list_spaces(user_id) if x.get("is_member")]


def overview(user_id: str) -> dict:
    uid = _uid(user_id); p = get_profile(uid); spaces = my_spaces(uid); posts = feed(uid, limit=100)
    return {"profile": p, "onboarding": onboarding_state(uid), "communities": [x for x in spaces if x["kind"] == "community"],
            "clans": [x for x in spaces if x["kind"] == "clan"], "feed": posts[:12],
            "stats": {"spaces": len(spaces), "communities": sum(1 for x in spaces if x["kind"] == "community"),
                      "clans": sum(1 for x in spaces if x["kind"] == "clan"), "posts": len(posts)}}
