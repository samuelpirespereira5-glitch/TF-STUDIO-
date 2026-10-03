"""Community Social 2.0: canais, chat, eventos ao vivo e rankings.
Persistência simples em JSON para manter compatibilidade com o projeto Flask atual.
Não cria um segundo sistema de autenticação.
"""
from __future__ import annotations
import json, re, secrets, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "data" / "community_social"
DATA.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
CHANNELS = DATA / "channels.json"
MESSAGES = DATA / "messages.json"
EVENTS = DATA / "events.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, data: Any):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def clean(v: Any, n: int = 500) -> str:
    return str(v or "").strip()[:n]


def safe_name(v: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "", clean(v, 40))[:40]


def _channel_defaults(space_id: str) -> list[dict]:
    return [
        {"id": f"{space_id}:general", "space_id": space_id, "name": "geral", "label": "💬 geral", "kind": "text", "position": 1},
        {"id": f"{space_id}:announcements", "space_id": space_id, "name": "avisos", "label": "📢 avisos", "kind": "text", "position": 2},
        {"id": f"{space_id}:workshops", "space_id": space_id, "name": "workshops", "label": "🎓 workshops", "kind": "text", "position": 3},
        {"id": f"{space_id}:lounge", "space_id": space_id, "name": "lounge", "label": "🔊 lounge", "kind": "voice", "position": 4},
    ]


def require_member(space_id: str, user_id: str) -> bool:
    try:
        from services import community_space
        data = load(community_space.SPACES_FILE, {"spaces": {}})
        space = data.get("spaces", {}).get(space_id)
        return bool(space and user_id in (space.get("members") or {}))
    except Exception:
        return False


def channels(space_id: str) -> list[dict]:
    with LOCK:
        data = load(CHANNELS, {"channels": []})
        rows = [x for x in data.get("channels", []) if x.get("space_id") == space_id]
        if not rows:
            rows = _channel_defaults(space_id)
            data.setdefault("channels", []).extend(rows)
            save(CHANNELS, data)
        return sorted(rows, key=lambda x: x.get("position", 99))


def add_channel(space_id: str, user_id: str, name: str, kind: str = "text") -> dict:
    name = re.sub(r"[^a-zA-Z0-9\-_]", "-", clean(name, 32).lower()).strip("-") or "canal"
    kind = kind if kind in {"text", "voice", "stage"} else "text"
    with LOCK:
        rows = load(CHANNELS, {"channels": []})
        existing = [x for x in rows["channels"] if x.get("space_id") == space_id]
        if any(x.get("name") == name for x in existing):
            return next(x for x in existing if x.get("name") == name)
        item = {"id": f"{space_id}:{name}:{secrets.token_hex(3)}", "space_id": space_id, "name": name,
                "label": ("🔊 " if kind == "voice" else "# ") + name, "kind": kind, "position": len(existing) + 1,
                "created_by": user_id, "created_at": now()}
        rows["channels"].append(item); save(CHANNELS, rows)
        return item


def _author(user_id: str) -> dict:
    try:
        from services import community_space
        p = community_space.get_profile(user_id)
    except Exception:
        p = {}
    return {"user_id": user_id, "display_name": p.get("display_name") or user_id, "username": p.get("username") or "", "avatar": p.get("avatar") or "🤖"}


def messages(space_id: str, channel_id: str, limit: int = 80, before: str = "") -> list[dict]:
    rows = load(MESSAGES, {"messages": []}).get("messages", [])
    rows = [x for x in rows if x.get("space_id") == space_id and x.get("channel_id") == channel_id]
    return rows[-max(1, min(limit, 150)):]


def send_message(user_id: str, space_id: str, channel_id: str, content: str, kind: str = "text") -> dict:
    content = clean(content, 2000)
    if not content:
        raise ValueError("Mensagem vazia.")
    if kind not in {"text", "announcement", "system"}:
        kind = "text"
    with LOCK:
        data = load(MESSAGES, {"messages": []})
        msg = {"id": "msg_" + uuid.uuid4().hex[:12], "space_id": space_id, "channel_id": channel_id,
               "author": _author(user_id), "content": content, "kind": kind, "created_at": now()}
        data.setdefault("messages", []).append(msg)
        data["messages"] = data["messages"][-5000:]
        save(MESSAGES, data)
        return msg


def create_event(user_id: str, space_id: str, title: str, kind: str, starts_at: str, description: str = "", media_url: str = "") -> dict:
    kind = kind if kind in {"chat", "video", "workshop"} else "chat"
    title = clean(title, 100) or "Evento da comunidade"
    media_url = clean(media_url, 500)
    embed = embed_url(media_url) if media_url else ""
    with LOCK:
        data = load(EVENTS, {"events": []})
        event = {"id": "event_" + uuid.uuid4().hex[:10], "space_id": space_id, "host": user_id, "host_profile": _author(user_id),
                 "title": title, "kind": kind, "starts_at": clean(starts_at, 50), "description": clean(description, 800),
                 "media_url": media_url, "embed_url": embed, "attendees": [user_id], "status": "scheduled", "created_at": now()}
        data.setdefault("events", []).append(event); data["events"] = data["events"][-300:]; save(EVENTS, data)
        return event


def list_events(space_id: str = "") -> list[dict]:
    rows = load(EVENTS, {"events": []}).get("events", [])
    if space_id: rows = [x for x in rows if x.get("space_id") == space_id]
    return list(reversed(rows[-100:]))


def join_event(user_id: str, event_id: str) -> dict:
    with LOCK:
        data = load(EVENTS, {"events": []})
        for e in data.get("events", []):
            if e.get("id") == event_id:
                if user_id not in e.setdefault("attendees", []): e["attendees"].append(user_id)
                e["status"] = "live"
                save(EVENTS, data); return e
    raise ValueError("Evento não encontrado.")


def embed_url(url: str) -> str:
    """Só permite hosts de vídeo conhecidos; evita iframe arbitrário."""
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        if host in {"youtube.com", "www.youtube.com", "youtu.be", "www.youtube-nocookie.com"}:
            vid = ""
            if host.endswith("youtu.be"): vid = p.path.strip("/").split("/")[0]
            elif p.path == "/watch":
                from urllib.parse import parse_qs
                vid = parse_qs(p.query).get("v", [""])[0]
            elif "/embed/" in p.path: vid = p.path.split("/embed/", 1)[1].split("/", 1)[0]
            elif "/live/" in p.path: vid = p.path.split("/live/", 1)[1].split("/", 1)[0]
            return f"https://www.youtube-nocookie.com/embed/{vid}" if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid) else ""
        if host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
            m = re.search(r"(\d{5,15})", p.path)
            return f"https://player.vimeo.com/video/{m.group(1)}" if m else ""
    except Exception:
        pass
    return ""


def rankings(limit: int = 30) -> dict:
    """Agrega métricas já existentes sem alterar XP/permissões."""
    users: dict[str, dict] = {}
    try:
        from services import new_features
        for r in new_features.get_global_rankings(100):
            u = users.setdefault(r.get("user_id", ""), {"user_id": r.get("user_id", ""), "xp": 0, "games": 0, "posts": 0, "reputation": 0})
            u["xp"] += int(r.get("xp", 0)); u["level"] = int(r.get("level", 1)); u["completed"] = int(r.get("completed_count", 0))
    except Exception:
        pass
    try:
        from services import gamification
        for r in gamification.leaderboard(100):
            u = users.setdefault(r["user_id"], {"user_id": r["user_id"], "xp": 0, "games": 0, "posts": 0, "reputation": 0})
            u["xp"] = max(u.get("xp", 0), int(r.get("xp", 0))); u["level"] = max(u.get("level", 1), int(r.get("level", 1)))
            u["completed"] = max(u.get("completed", 0), int(r.get("completed_count", 0)))
    except Exception: pass
    try:
        from services import next_level11
        for r in next_level11.global_ranking(100):
            u = users.setdefault(r["user_id"], {"user_id": r["user_id"], "xp": 0, "games": 0, "posts": 0, "reputation": 0})
            u["game_score"] = int(r.get("total_xp", 0)); u["games"] = int(r.get("games_played", 0)); u["xp"] += int(r.get("total_xp", 0))
    except Exception: pass
    try:
        from services import community_space
        pdata = load(community_space.PROFILES_FILE, {"profiles": {}}).get("profiles", {})
        for uid, p in pdata.items():
            u = users.setdefault(uid, {"user_id": uid, "xp": 0, "games": 0, "posts": 0, "reputation": 0})
            u["display_name"] = p.get("display_name") or p.get("username") or uid; u["avatar"] = p.get("avatar") or "🤖"
    except Exception: pass
    msgs = load(MESSAGES, {"messages": []}).get("messages", [])
    for m in msgs:
        uid = m.get("author", {}).get("user_id")
        if uid:
            u = users.setdefault(uid, {"user_id": uid, "xp": 0, "games": 0, "posts": 0, "reputation": 0})
            u["posts"] = u.get("posts", 0) + 1
    for u in users.values():
        u.setdefault("display_name", u["user_id"]); u.setdefault("avatar", "🤖")
        u["community_score"] = u.get("xp", 0) + u.get("posts", 0) * 5 + u.get("reputation", 0)
    rows = sorted(users.values(), key=lambda x: (-x["community_score"], -x.get("xp", 0), -x.get("posts", 0), x["display_name"].lower()))[:limit]
    for i, r in enumerate(rows, 1): r["rank"] = i
    return {"global": rows, "season": rows[:], "community": sorted(rows, key=lambda x: (-x.get("posts",0), -x.get("community_score",0)))[:limit], "games": sorted(rows, key=lambda x: (-x.get("game_score",0), -x.get("xp",0)))[:limit]}

# ---------------------------------------------------------------------------
# Voice Live / WebRTC signaling — somente sinalização, o áudio é P2P.
# O servidor nunca recebe nem armazena o áudio do usuário.
VOICE = DATA / "voice_rooms.json"
VOICE_TTL = 35

def _voice_load():
    return load(VOICE, {"rooms": {}})

def _voice_save(data):
    save(VOICE, data)

def _voice_cleanup(data, room_id: str):
    room = data.setdefault("rooms", {}).setdefault(room_id, {"peers": {}, "signals": []})
    cutoff = datetime.now(timezone.utc).timestamp() - VOICE_TTL
    for pid, p in list(room.get("peers", {}).items()):
        try: old = datetime.fromisoformat(p.get("last_seen", "")).timestamp() < cutoff
        except Exception: old = True
        if old: room["peers"].pop(pid, None)
    room["signals"] = [x for x in room.get("signals", []) if x.get("created", 0) >= cutoff]
    if not room["peers"]:
        data.get("rooms", {}).pop(room_id, None)

def voice_join(user_id: str, space_id: str, channel_id: str) -> dict:
    room_id = f"{space_id}:{channel_id}"
    with LOCK:
        data = _voice_load(); _voice_cleanup(data, room_id)
        room = data.setdefault("rooms", {}).setdefault(room_id, {"peers": {}, "signals": []})
        peer_id = secrets.token_urlsafe(12)
        peers = [{"peer_id": pid, "user_id": p.get("user_id", "")} for pid, p in room["peers"].items()]
        room["peers"][peer_id] = {"user_id": user_id, "last_seen": now()}
        _voice_save(data)
        return {"peer_id": peer_id, "room_id": room_id, "peers": peers}

def voice_poll(user_id: str, room_id: str, peer_id: str) -> dict:
    with LOCK:
        data = _voice_load(); _voice_cleanup(data, room_id)
        room = data.get("rooms", {}).get(room_id)
        if not room or peer_id not in room.get("peers", {}): return {"signals": [], "peers": []}
        room["peers"][peer_id]["last_seen"] = now()
        signals = [x for x in room.get("signals", []) if x.get("to") == peer_id]
        room["signals"] = [x for x in room.get("signals", []) if x.get("to") != peer_id]
        peers = [{"peer_id": pid, "user_id": p.get("user_id", "")} for pid, p in room.get("peers", {}).items() if pid != peer_id]
        _voice_save(data)
        return {"signals": signals, "peers": peers}

def voice_signal(user_id: str, room_id: str, peer_id: str, target: str, payload: dict) -> dict:
    if not isinstance(payload, dict): raise ValueError("Sinal inválido.")
    allowed = {"offer", "answer", "ice", "bye"}
    typ = clean(payload.get("type"), 12)
    if typ not in allowed: raise ValueError("Tipo de sinal inválido.")
    with LOCK:
        data = _voice_load(); _voice_cleanup(data, room_id)
        room = data.get("rooms", {}) .get(room_id)
        if not room or peer_id not in room.get("peers", {}): raise ValueError("Sala de voz expirada.")
        if target not in room.get("peers", {}): raise ValueError("Participante não encontrado.")
        packet = {"id": secrets.token_hex(8), "from": peer_id, "to": target, "type": typ, "payload": payload.get("data"), "created": datetime.now(timezone.utc).timestamp()}
        room.setdefault("signals", []).append(packet)
        room["signals"] = room["signals"][-500:]
        room["peers"][peer_id]["last_seen"] = now()
        _voice_save(data)
        return {"ok": True}

def voice_leave(user_id: str, room_id: str, peer_id: str) -> dict:
    with LOCK:
        data = _voice_load(); room = data.get("rooms", {}).get(room_id)
        if room:
            room.get("peers", {}).pop(peer_id, None)
            room["signals"] = [x for x in room.get("signals", []) if x.get("from") != peer_id and x.get("to") != peer_id]
            _voice_cleanup(data, room_id); _voice_save(data)
        return {"ok": True}
