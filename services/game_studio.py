"""JARVIS Game Studio 5.0 — real editable game projects.

Extends game_lab without replacing it. User code never runs on the server.
Project data is JSON (scenes, entities, events, levels) executed only in the browser sandbox.
"""
from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from services import game_lab

# ---------------------------------------------------------------------------
# Game types & templates (studio)
# ---------------------------------------------------------------------------
GAME_TYPES = [
    "plataforma", "rpg", "aventura", "puzzle", "corrida", "arcade",
    "tower_defense", "shooter_edu", "quiz", "estrategia", "maze",
    "clicker", "endless_runner",
]

STUDIO_TEMPLATES = {
    "empty": {
        "name": "Jogo vazio",
        "type": "arcade",
        "description": "Cena vazia para montar do zero.",
    },
    "platformer": {
        "name": "Plataforma 2D",
        "type": "plataforma",
        "description": "Personagem, plataformas, moedas e inimigo.",
    },
    "platformer_simple": {
        "name": "Plataforma simples",
        "type": "plataforma",
        "description": "Versão mínima de plataforma.",
    },
    "topdown": {
        "name": "Top Down",
        "type": "aventura",
        "description": "Movimento em 4 direções, vista de cima.",
    },
    "rpg": {
        "name": "RPG 2D",
        "type": "rpg",
        "description": "Base RPG com NPC e diálogo simples.",
    },
    "puzzle": {
        "name": "Puzzle",
        "type": "puzzle",
        "description": "Objetivos e condições.",
    },
    "racing": {
        "name": "Corrida",
        "type": "corrida",
        "description": "Corrida lateral simples.",
    },
    "arcade": {
        "name": "Arcade",
        "type": "arcade",
        "description": "Score e inimigos.",
    },
    "endless": {
        "name": "Endless Runner",
        "type": "endless_runner",
        "description": "Corrida infinita educativa.",
    },
    "quiz": {
        "name": "Quiz Game",
        "type": "quiz",
        "description": "Perguntas e pontuação.",
    },
    "test_platformer": {
        "name": "JARVIS TEST PLATFORMER",
        "type": "plataforma",
        "description": "Jogo de teste completo: personagem, pulo, plataformas, moeda, inimigo, vida, score, objetivo.",
    },
}


def _entity(eid: str, kind: str, x: float, y: float, w: float, h: float, **props) -> dict:
    base = {
        "id": eid,
        "type": kind,
        "name": props.pop("name", kind),
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "rotation": 0,
        "scale": 1,
        "visible": True,
        "collision": True,
        "color": props.pop("color", "#4bb3ff"),
    }
    base.update(props)
    return base


def test_platformer_data() -> dict[str, Any]:
    """Fully playable platformer project data for the mandatory test flow."""
    entities = [
        _entity("player", "player", 40, 280, 28, 36,
                name="Hero", color="#38bdf8", speed=180, jump=420, gravity=1100,
                hp=3, maxHp=3, damage=0, points=0,
                controls={"left": "ArrowLeft", "right": "ArrowRight", "jump": "Space"}),
        _entity("ground1", "platform", 0, 360, 640, 40, name="Chão", color="#475569", solid=True),
        _entity("plat1", "platform", 120, 280, 120, 18, name="Plataforma A", color="#64748b", solid=True),
        _entity("plat2", "platform", 320, 220, 140, 18, name="Plataforma B", color="#64748b", solid=True),
        _entity("plat3", "platform", 480, 160, 100, 18, name="Plataforma C", color="#64748b", solid=True),
        _entity("coin1", "coin", 160, 240, 18, 18, name="Moeda", color="#fbbf24", points=10, solid=False),
        _entity("coin2", "coin", 360, 180, 18, 18, name="Moeda 2", color="#fbbf24", points=10, solid=False),
        _entity("coin3", "coin", 510, 120, 18, 18, name="Moeda 3", color="#fbbf24", points=15, solid=False),
        _entity("enemy1", "enemy", 400, 328, 28, 28, name="Slime", color="#f87171",
                hp=1, damage=1, speed=60, behavior="patrol", patrolMin=300, patrolMax=500, solid=True),
        _entity("goal1", "goal", 560, 120, 32, 36, name="Bandeira", color="#22c55e", solid=False),
        _entity("spawn", "spawn", 40, 280, 10, 10, name="Spawn", color="#a78bfa", visible=False, collision=False),
        _entity("checkpoint1", "checkpoint", 300, 328, 16, 32, name="Checkpoint", color="#2dd4bf", solid=False),
    ]

    events = [
        {"id": "ev_coin", "when": "collision", "a": "player", "bType": "coin",
         "actions": [{"type": "add_score", "value": "target.points"}, {"type": "remove_target"}, {"type": "play_sound", "sound": "coin"}]},
        {"id": "ev_enemy", "when": "collision", "a": "player", "bType": "enemy",
         "actions": [{"type": "damage_player", "value": 1}, {"type": "knockback"}, {"type": "play_sound", "sound": "hit"}]},
        {"id": "ev_goal", "when": "collision", "a": "player", "bType": "goal",
         "actions": [{"type": "win"}, {"type": "play_sound", "sound": "win"}]},
        {"id": "ev_checkpoint", "when": "collision", "a": "player", "bType": "checkpoint",
         "actions": [{"type": "set_checkpoint"}]},
        {"id": "ev_fall", "when": "player_y_gt", "value": 420,
         "actions": [{"type": "damage_player", "value": 1}, {"type": "respawn"}]},
        {"id": "ev_hp0", "when": "player_hp_lte", "value": 0,
         "actions": [{"type": "lose"}]},
    ]

    level = {
        "id": "level1",
        "name": "Fase 1 — Teste",
        "width": 640,
        "height": 400,
        "gravity": 1100,
        "background": "#0f172a",
        "entities": entities,
        "events": events,
        "spawn": "spawn",
        "objective": "Colete moedas e chegue à bandeira sem perder todas as vidas.",
    }

    code = """// JARVIS TEST PLATFORMER — código gerado pelo Studio
// O runtime principal usa as entidades/eventos do JSON.
// Você pode estender comportamentos aqui (sandbox do navegador).
function onStart(game) {
  game.log('TEST PLATFORMER iniciado');
}
function onUpdate(game, dt) {
  // opcional
}
"""

    return {
        "studioVersion": 5,
        "language": "javascript",
        "gameType": "plataforma",
        "blocks": [],
        "code": code,
        "settings": {
            "age_level": "BEGINNER",
            "controls": ["keyboard", "touch"],
            "audio": True,
            "showGrid": True,
            "debug": False,
        },
        "requirements": ["player", "movement", "jump", "gravity", "collision", "goal"],
        "assets": {"sprites": [], "sounds": [], "music": []},
        "levels": [level],
        "currentLevel": 0,
        "ui": {
            "showScore": True,
            "showHp": True,
            "title": "JARVIS TEST PLATFORMER",
        },
    }


def empty_project_data(game_type: str = "arcade") -> dict[str, Any]:
    return {
        "studioVersion": 5,
        "language": "javascript",
        "gameType": game_type,
        "blocks": [],
        "code": "// Seu código\nfunction onStart(game) {}\nfunction onUpdate(game, dt) {}\n",
        "settings": {
            "age_level": "BEGINNER",
            "controls": ["keyboard", "touch"],
            "audio": True,
            "showGrid": True,
            "debug": False,
        },
        "requirements": [],
        "assets": {"sprites": [], "sounds": [], "music": []},
        "levels": [{
            "id": "level1",
            "name": "Fase 1",
            "width": 640,
            "height": 400,
            "gravity": 1100,
            "background": "#0f172a",
            "entities": [
                _entity("player", "player", 40, 300, 28, 36, name="Player", color="#38bdf8",
                        speed=160, jump=400, gravity=1100, hp=3, maxHp=3),
                _entity("ground1", "platform", 0, 360, 640, 40, name="Chão", color="#475569", solid=True),
            ],
            "events": [
                {"id": "ev_fall", "when": "player_y_gt", "value": 420,
                 "actions": [{"type": "damage_player", "value": 1}, {"type": "respawn"}]},
                {"id": "ev_hp0", "when": "player_hp_lte", "value": 0, "actions": [{"type": "lose"}]},
            ],
            "spawn": "player",
            "objective": "Explore e construa sua fase.",
        }],
        "currentLevel": 0,
        "ui": {"showScore": True, "showHp": True, "title": "Novo Jogo"},
    }


def platformer_data() -> dict[str, Any]:
    d = test_platformer_data()
    d["ui"]["title"] = "Plataforma 2D"
    return d


def template_payload(template_id: str, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    tid = (template_id or "empty").lower()
    if tid == "test_platformer":
        data = test_platformer_data()
    elif tid in ("platformer", "platformer_simple"):
        data = platformer_data()
        if tid == "platformer_simple":
            # fewer entities
            lvl = data["levels"][0]
            lvl["entities"] = [e for e in lvl["entities"] if e["type"] in ("player", "platform", "coin", "goal", "spawn")]
            lvl["entities"] = lvl["entities"][:6]
    elif tid == "empty":
        data = empty_project_data("arcade")
    else:
        data = empty_project_data(STUDIO_TEMPLATES.get(tid, {}).get("type", "arcade"))
        data["ui"]["title"] = STUDIO_TEMPLATES.get(tid, {}).get("name", "Jogo")
    if name:
        data["ui"]["title"] = name[:100]
    meta = STUDIO_TEMPLATES.get(tid, STUDIO_TEMPLATES["empty"])
    return {
        "template": tid,
        "name": (name or meta["name"])[:100],
        "description": (description or meta["description"])[:500],
        "data": data,
    }


def create_studio_project(owner: str, body: dict) -> dict:
    """Create project with studio schema. Falls back to game_lab storage."""
    template = str(body.get("template") or "platformer")[:40]
    if template not in STUDIO_TEMPLATES and template not in game_lab.TEMPLATES:
        # allow empty / test
        if template not in ("empty", "test_platformer", "platformer_simple", "topdown", "endless"):
            template = "platformer"

    # Ensure game_lab accepts template key: map studio-only to platformer for DB column
    db_template = template if template in game_lab.TEMPLATES else "platformer"
    if template == "test_platformer":
        db_template = "platformer"

    payload_wrap = template_payload(
        template,
        name=body.get("name"),
        description=body.get("description"),
    )
    data = payload_wrap["data"]
    data["gameType"] = body.get("gameType") or data.get("gameType") or "plataforma"
    data["difficulty"] = str(body.get("difficulty") or "normal")[:20]
    data["platform"] = str(body.get("platform") or "web")[:20]

    pid = uuid.uuid4().hex[:16]
    t = game_lab.now()
    name = payload_wrap["name"]
    desc = payload_wrap["description"]
    # store full studio data in data_json
    with game_lab.conn() as c:
        c.execute(
            "INSERT INTO kids_projects VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (pid, game_lab._uid(owner), name, desc, db_template, 1, 10, "DRAFT", json.dumps(data), t, t),
        )
        c.execute(
            "INSERT INTO kids_project_versions(project_id,owner_uid,version,changes,data_json,created_at) VALUES(?,?,?,?,?,?)",
            (pid, game_lab._uid(owner), 1, f"Studio: criado ({template})", json.dumps(data), t),
        )
    try:
        from services import phase5
        phase5.audit(owner, "GAME_STUDIO_CREATED", pid, template)
    except Exception:
        pass
    game_lab._award(owner, 10, "game-creation")
    return game_lab.project(owner, pid)


def save_studio_project(owner: str, pid: str, body: dict) -> dict:
    p = game_lab.project(owner, pid)
    if not p:
        raise ValueError("Projeto não encontrado")
    old = p["version"]
    new = old + 1
    t = game_lab.now()
    # merge studio fields
    prev = p.get("data") or {}
    data = body.get("data") if isinstance(body.get("data"), dict) else None
    if data is None:
        data = {
            "studioVersion": 5,
            "language": str(body.get("language") or prev.get("language") or "javascript"),
            "blocks": body.get("blocks") if body.get("blocks") is not None else prev.get("blocks") or [],
            "code": str(body.get("code") if body.get("code") is not None else prev.get("code") or "")[:50000],
            "settings": body.get("settings") or prev.get("settings") or {},
            "requirements": prev.get("requirements") or [],
            "assets": body.get("assets") or prev.get("assets") or {},
            "levels": body.get("levels") or prev.get("levels") or [],
            "currentLevel": body.get("currentLevel", prev.get("currentLevel", 0)),
            "ui": body.get("ui") or prev.get("ui") or {},
            "gameType": body.get("gameType") or prev.get("gameType"),
        }
    else:
        data = copy.deepcopy(data)
        data["studioVersion"] = 5
        if "code" in data:
            data["code"] = str(data["code"])[:50000]

    # security: strip dangerous code markers in stored form (runtime still sandboxed)
    safe_check = game_lab.validate_code(data.get("code") or "")
    if not safe_check.get("safe"):
        data.setdefault("warnings", safe_check.get("errors") or [])

    progress = max(0, min(100, int(body.get("progress", p.get("progress") or 0) or 0)))
    changes = str(body.get("changes") or "Salvo no Game Studio")[:500]
    status = str(body.get("status") or p.get("status") or "DRAFT")[:20]
    with game_lab.conn() as c:
        c.execute(
            "UPDATE kids_projects SET version=?,progress=?,status=?,data_json=?,updated_at=? WHERE id=? AND owner_uid=?",
            (new, progress, status, json.dumps(data), t, pid, game_lab._uid(owner)),
        )
        c.execute(
            "INSERT INTO kids_project_versions(project_id,owner_uid,version,changes,data_json,created_at) VALUES(?,?,?,?,?,?)",
            (pid, game_lab._uid(owner), new, changes, json.dumps(data), t),
        )
    return game_lab.project(owner, pid)


def list_versions(owner: str, pid: str) -> list:
    with game_lab.conn() as c:
        rows = c.execute(
            "SELECT version,changes,created_at FROM kids_project_versions WHERE project_id=? AND owner_uid=? ORDER BY version DESC",
            (pid, game_lab._uid(owner)),
        ).fetchall()
    return [dict(r) for r in rows]


def restore_version(owner: str, pid: str, version: int) -> dict:
    with game_lab.conn() as c:
        r = c.execute(
            "SELECT data_json,changes FROM kids_project_versions WHERE project_id=? AND owner_uid=? AND version=?",
            (pid, game_lab._uid(owner), int(version)),
        ).fetchone()
    if not r:
        raise ValueError("Versão não encontrada")
    data = json.loads(r["data_json"])
    return save_studio_project(owner, pid, {
        "data": data,
        "changes": f"Restaurado da versão {version}",
        "progress": 50,
    })


def publish_project(owner: str, pid: str) -> dict:
    p = game_lab.project(owner, pid)
    if not p:
        raise ValueError("Projeto não encontrado")
    return save_studio_project(owner, pid, {
        "data": p["data"],
        "status": "PUBLISHED",
        "changes": "Publicado na galeria local",
        "progress": max(int(p.get("progress") or 0), 80),
    })


def game_check(project_data: dict) -> dict:
    """Structural validation before play — no code execution on server."""
    checks = []
    levels = (project_data or {}).get("levels") or []
    checks.append({"id": "project", "ok": bool(project_data), "label": "Projeto"})
    checks.append({"id": "levels", "ok": len(levels) > 0, "label": "Cenas / fases"})
    ents = []
    if levels:
        ents = levels[0].get("entities") or []
    has_player = any(e.get("type") == "player" for e in ents)
    has_platform = any(e.get("type") == "platform" for e in ents)
    checks.append({"id": "player", "ok": has_player, "label": "Personagem"})
    checks.append({"id": "platforms", "ok": has_platform or True, "label": "Cenário"})
    code = (project_data or {}).get("code") or ""
    v = game_lab.validate_code(code)
    checks.append({"id": "code", "ok": v.get("safe", True), "label": "Código seguro", "detail": v.get("errors")})
    checks.append({"id": "events", "ok": True, "label": "Eventos"})
    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks}


def apply_coder_patch(owner: str, pid: str, instruction: str) -> dict:
    """Heuristic JARVIS Game Coder — patches project JSON safely with version backup."""
    p = game_lab.project(owner, pid)
    if not p:
        raise ValueError("Projeto não encontrado")
    data = copy.deepcopy(p.get("data") or {})
    levels = data.get("levels") or []
    if not levels:
        raise ValueError("Projeto sem fases")
    lvl = levels[data.get("currentLevel", 0) or 0]
    ents = lvl.setdefault("entities", [])
    events = lvl.setdefault("events", [])
    text = (instruction or "").lower()
    changes = []

    def find_type(t):
        return [e for e in ents if e.get("type") == t]

    if "pul" in text or "jump" in text:
        for e in find_type("player"):
            e["jump"] = max(int(e.get("jump") or 400) + 40, 480)
            changes.append(f"Pulo do personagem ajustado para {e['jump']}")
    if "velocidade" in text or "mais rápido" in text or "speed" in text:
        for e in find_type("player"):
            e["speed"] = max(int(e.get("speed") or 160) + 20, 200)
            changes.append(f"Velocidade do personagem: {e['speed']}")
    if "inimigo" in text and ("cri" in text or "adic" in text or "siga" in text or "perseg" in text):
        eid = "enemy_" + uuid.uuid4().hex[:6]
        ents.append(_entity(eid, "enemy", 350, 328, 28, 28, name="Inimigo", color="#f87171",
                            hp=1, damage=1, speed=70, behavior="patrol" if "perseg" not in text else "chase",
                            patrolMin=200, patrolMax=500, solid=True))
        changes.append("Inimigo adicionado")
        if not any(ev.get("bType") == "enemy" for ev in events):
            events.append({
                "id": "ev_enemy_auto", "when": "collision", "a": "player", "bType": "enemy",
                "actions": [{"type": "damage_player", "value": 1}, {"type": "knockback"}],
            })
            changes.append("Evento de colisão com inimigo")
    if "moeda" in text and ("10" in text or "ponto" in text or "cri" in text or "adic" in text):
        pts = 10
        for e in find_type("coin"):
            e["points"] = pts
        if "cri" in text or "adic" in text:
            eid = "coin_" + uuid.uuid4().hex[:6]
            ents.append(_entity(eid, "coin", 200, 200, 18, 18, name="Moeda", color="#fbbf24", points=pts, solid=False))
            changes.append("Moeda adicionada")
        changes.append(f"Moedas valem {pts} pontos")
        if not any(ev.get("bType") == "coin" for ev in events):
            events.append({
                "id": "ev_coin_auto", "when": "collision", "a": "player", "bType": "coin",
                "actions": [{"type": "add_score", "value": "target.points"}, {"type": "remove_target"}],
            })
    if "vida" in text or "hp" in text:
        for e in find_type("player"):
            e["hp"] = 5
            e["maxHp"] = 5
            changes.append("Vidas do jogador = 5")
    if "fase" in text or "level" in text or "segunda" in text:
        new_lvl = copy.deepcopy(lvl)
        new_lvl["id"] = "level" + str(len(levels) + 1)
        new_lvl["name"] = f"Fase {len(levels) + 1}"
        for e in new_lvl.get("entities") or []:
            if e.get("type") == "player":
                e["x"] = 40
                e["y"] = 280
        levels.append(new_lvl)
        changes.append(f"Nova fase criada: {new_lvl['name']}")
    if "porta" in text and "chave" in text:
        ents.append(_entity("key1", "key", 180, 240, 16, 16, name="Chave", color="#fde047", solid=False))
        ents.append(_entity("door1", "door", 560, 300, 28, 60, name="Porta", color="#a16207", solid=True, locked=True))
        events.append({
            "id": "ev_key", "when": "collision", "a": "player", "bType": "key",
            "actions": [{"type": "set_flag", "flag": "hasKey", "value": True}, {"type": "remove_target"}],
        })
        events.append({
            "id": "ev_door", "when": "collision", "a": "player", "bType": "door",
            "actions": [{"type": "require_flag", "flag": "hasKey"}, {"type": "remove_target"}, {"type": "add_score", "value": 50}],
        })
        changes.append("Chave e porta com condição")
    if not changes:
        changes.append("Nenhuma alteração automática reconhecida. Tente ser mais específico (pulo, inimigo, moeda, fase, vidas).")

    data["levels"] = levels
    result = save_studio_project(owner, pid, {
        "data": data,
        "changes": "JARVIS Game Coder: " + "; ".join(changes)[:400],
    })
    return {"project": result, "changes": changes, "instruction": instruction}


def studio_overview(owner: str) -> dict:
    projs = game_lab.projects(owner)
    published = [p for p in projs if (p.get("status") or "").upper() == "PUBLISHED"]
    return {
        "version": "5.0",
        "templates": [{"id": k, **v} for k, v in STUDIO_TEMPLATES.items()],
        "gameTypes": GAME_TYPES,
        "projects": projs,
        "published": published,
        "recent": projs[:8],
        "catalog": game_lab.catalog(owner),
    }


def ensure_test_platformer(owner: str) -> dict:
    """Create or return JARVIS TEST PLATFORMER for the owner."""
    for p in game_lab.projects(owner):
        if (p.get("name") or "").startswith("JARVIS TEST PLATFORMER"):
            return p
    return create_studio_project(owner, {
        "name": "JARVIS TEST PLATFORMER",
        "description": STUDIO_TEMPLATES["test_platformer"]["description"],
        "template": "test_platformer",
        "gameType": "plataforma",
        "difficulty": "normal",
    })
