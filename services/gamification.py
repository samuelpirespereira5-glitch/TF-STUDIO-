"""XP, níveis, conquistas e ranking local — Parte 3.

Persiste em data/gamification.json. Não envia dados para fora.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "gamification.json"
_lock = threading.Lock()

XP_PER_LEVEL = 300

ACHIEVEMENTS = {
    "first_game": {"id":"first_game","name":"Primeiro Jogo","description":"Conclua sua primeira partida no Arcade.","icon":"🎮","condition":lambda st: st.get("games_played",0)>=1},
    "ten_games": {"id":"ten_games","name":"Arcade Runner","description":"Jogue 10 partidas no Arcade.","icon":"🕹️","condition":lambda st: st.get("games_played",0)>=10},
    "first_blood": {
        "id": "first_blood",
        "name": "First Blood",
        "description": "Conclua seu primeiro desafio.",
        "icon": "🩸",
        "condition": lambda st: st.get("completed_count", 0) >= 1,
    },
    "ten_solved": {
        "id": "ten_solved",
        "name": "Caçador de Bugs",
        "description": "Conclua 10 desafios.",
        "icon": "🎯",
        "condition": lambda st: st.get("completed_count", 0) >= 10,
    },
    "twenty_five": {
        "id": "twenty_five",
        "name": "Analista",
        "description": "Conclua 25 desafios.",
        "icon": "🔎",
        "condition": lambda st: st.get("completed_count", 0) >= 25,
    },
    "level_5": {
        "id": "level_5",
        "name": "Nível 5",
        "description": "Alcance o nível 5.",
        "icon": "⭐",
        "condition": lambda st: st.get("level", 1) >= 5,
    },
    "level_10": {
        "id": "level_10",
        "name": "Nível 10",
        "description": "Alcance o nível 10.",
        "icon": "🏆",
        "condition": lambda st: st.get("level", 1) >= 10,
    },
    "expert_one": {
        "id": "expert_one",
        "name": "Expert",
        "description": "Conclua um desafio Expert.",
        "icon": "💀",
        "condition": lambda st: st.get("expert_solved", 0) >= 1,
    },
    "blue_team": {
        "id": "blue_team",
        "name": "Blue Team",
        "description": "Conclua 5 desafios de logs/incidente/headers.",
        "icon": "🛡️",
        "condition": lambda st: st.get("blue_solved", 0) >= 5,
    },
    "crypto_curious": {
        "id": "crypto_curious",
        "name": "Crypto Curious",
        "description": "Use ferramentas de hash/JWT pelo menos 3 vezes (registrado).",
        "icon": "🔐",
        "condition": lambda st: st.get("crypto_tools_used", 0) >= 3,
    },
    "tool_master": {
        "id": "tool_master",
        "name": "Tool Master",
        "description": "Use 10 ferramentas diferentes do Cyber Lab.",
        "icon": "🧰",
        "condition": lambda st: len(st.get("tools_used", [])) >= 10,
    },
    "perfect_week": {
        "id": "perfect_week",
        "name": "Semana Perfeita",
        "description": "Conclua 7 desafios (qualquer período).",
        "icon": "📅",
        "condition": lambda st: st.get("completed_count", 0) >= 7,
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return {"users": {}, "updated_at": _now()}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"users": {}, "updated_at": _now()}
        data.setdefault("users", {})
        return data
    except Exception:
        return {"users": {}, "updated_at": _now()}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


def _user_state(data: dict, user_id: str) -> dict:
    u = data["users"].setdefault(user_id, {
        "xp": 0,
        "completed": [],
        "achievements": [],
        "tools_used": [],
        "expert_solved": 0,
        "blue_solved": 0,
        "crypto_tools_used": 0,
        "history": [],
    })
    return u


def level_from_xp(xp: int) -> tuple[int, int, int]:
    """Retorna (level, xp_into_level, xp_per_level)."""
    xp = max(0, int(xp))
    level = 1 + xp // XP_PER_LEVEL
    into = xp % XP_PER_LEVEL
    return level, into, XP_PER_LEVEL


def sync_from_challenge_sites(user_id: str, completed_ids: list[str], catalog: dict) -> dict:
    """Sincroniza XP a partir dos desafios concluídos (sites_service)."""
    with _lock:
        data = _load()
        st = _user_state(data, user_id)
        blue_cats = {"logs", "incidente", "headers", "blue_team", "config"}
        new_xp = 0
        expert = 0
        blue = 0
        completed = []
        for cid in completed_ids:
            c = catalog.get(cid) or {}
            xp = int(c.get("xp") or 0)
            new_xp += xp
            completed.append(cid)
            diff = str(c.get("difficulty") or "").lower()
            if diff in ("expert", "avançado", "avancado"):
                if diff == "expert":
                    expert += 1
            if c.get("category") in blue_cats:
                blue += 1
        st["xp"] = new_xp
        st["completed"] = completed
        st["completed_count"] = len(completed)
        st["expert_solved"] = expert
        st["blue_solved"] = blue
        level, into, per = level_from_xp(new_xp)
        st["level"] = level
        st["xp_into_level"] = into
        st["xp_per_level"] = per
        _unlock_achievements(st)
        _save(data)
        return public_user(user_id, st)


def record_tool_use(user_id: str, tool_id: str) -> None:
    with _lock:
        data = _load()
        st = _user_state(data, user_id)
        tools = st.setdefault("tools_used", [])
        if tool_id not in tools:
            tools.append(tool_id)
        if tool_id in ("hash_analyzer", "hash_generator", "jwt_analyzer", "jwt_decoder", "ssl_tls_analyzer"):
            st["crypto_tools_used"] = int(st.get("crypto_tools_used") or 0) + 1
        level, into, per = level_from_xp(int(st.get("xp") or 0))
        st["level"] = level
        _unlock_achievements(st)
        _save(data)


def record_challenge_complete(user_id: str, challenge_id: str, xp: int, difficulty: str = "", category: str = "") -> dict:
    with _lock:
        data = _load()
        st = _user_state(data, user_id)
        if challenge_id not in st.get("completed", []):
            st.setdefault("completed", []).append(challenge_id)
            st["xp"] = int(st.get("xp") or 0) + int(xp or 0)
            st["history"].append({"id": challenge_id, "xp": xp, "at": _now()})
            st["history"] = st["history"][-100:]
            if str(difficulty).lower() == "expert":
                st["expert_solved"] = int(st.get("expert_solved") or 0) + 1
            if category in ("logs", "incidente", "headers", "config"):
                st["blue_solved"] = int(st.get("blue_solved") or 0) + 1
        st["completed_count"] = len(st.get("completed") or [])
        level, into, per = level_from_xp(int(st["xp"]))
        st["level"] = level
        st["xp_into_level"] = into
        st["xp_per_level"] = per
        unlocked = _unlock_achievements(st)
        _save(data)
        out = public_user(user_id, st)
        out["newly_unlocked"] = unlocked
        return out


def record_game_result(user_id: str, game_id: str, xp: int = 5) -> dict:
    """Registra atividade do Arcade no sistema de gamificação existente.
    Não cria uma segunda progressão de XP.
    """
    with _lock:
        data = _load()
        st = _user_state(data, user_id)
        st["xp"] = int(st.get("xp") or 0) + max(0, min(int(xp or 0), 50))
        hist = st.setdefault("history", [])
        hist.append({"id": "arcade:" + str(game_id)[:80], "xp": max(0, min(int(xp or 0), 50)), "at": _now()})
        st["history"] = hist[-100:]
        st["games_played"] = int(st.get("games_played") or 0) + 1
        games = st.setdefault("games", [])
        if game_id not in games: games.append(str(game_id)[:80])
        level, into, per = level_from_xp(int(st["xp"]))
        st["level"], st["xp_into_level"], st["xp_per_level"] = level, into, per
        _unlock_achievements(st)
        _save(data)
        return public_user(user_id, st)


def _unlock_achievements(st: dict) -> list[str]:
    have = set(st.get("achievements") or [])
    newly = []
    snapshot = {
        "completed_count": st.get("completed_count") or len(st.get("completed") or []),
        "level": st.get("level") or 1,
        "expert_solved": st.get("expert_solved") or 0,
        "blue_solved": st.get("blue_solved") or 0,
        "crypto_tools_used": st.get("crypto_tools_used") or 0,
        "tools_used": st.get("tools_used") or [],
        "games_played": st.get("games_played") or 0,
    }
    for aid, meta in ACHIEVEMENTS.items():
        if aid in have:
            continue
        try:
            if meta["condition"](snapshot):
                have.add(aid)
                newly.append(aid)
        except Exception:
            continue
    st["achievements"] = sorted(have)
    return newly


def public_user(user_id: str, st: dict | None = None) -> dict:
    if st is None:
        with _lock:
            data = _load()
            st = _user_state(data, user_id)
    level, into, per = level_from_xp(int(st.get("xp") or 0))
    ach = []
    have = set(st.get("achievements") or [])
    for aid, meta in ACHIEVEMENTS.items():
        ach.append({
            "id": aid,
            "name": meta["name"],
            "description": meta["description"],
            "icon": meta["icon"],
            "unlocked": aid in have,
        })
    return {
        "user_id": user_id,
        "xp": int(st.get("xp") or 0),
        "level": level,
        "xp_into_level": into,
        "xp_per_level": per,
        "completed_count": st.get("completed_count") or len(st.get("completed") or []),
        "completed": list(st.get("completed") or []),
        "achievements": ach,
        "tools_used_count": len(st.get("tools_used") or []),
    }


def leaderboard(limit: int = 20) -> list[dict]:
    with _lock:
        data = _load()
        rows = []
        for uid, st in (data.get("users") or {}).items():
            level, into, per = level_from_xp(int(st.get("xp") or 0))
            rows.append({
                "user_id": uid,
                "xp": int(st.get("xp") or 0),
                "level": level,
                "completed_count": st.get("completed_count") or len(st.get("completed") or []),
                "achievements": len(st.get("achievements") or []),
            })
        rows.sort(key=lambda r: (-r["xp"], -r["completed_count"], r["user_id"]))
        for i, r in enumerate(rows[:limit], 1):
            r["rank"] = i
        return rows[:limit]


def achievements_catalog() -> list[dict]:
    return [
        {"id": a["id"], "name": a["name"], "description": a["description"], "icon": a["icon"]}
        for a in ACHIEVEMENTS.values()
    ]
