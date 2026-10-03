"""JARVIS Game Creator — gerador de jogos estilo criador de sites (melhorado).

Tipos: plataforma, coleta, labirinto, fuga, corrida, shooter-simples.
Descrição em frase → regras preenchem opções → prévia jogável no canvas.
Código do usuário nunca executado no servidor.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "games"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GAME_TYPES = [
    {"id": "platform", "label": "Plataforma", "desc": "Pule, colete e chegue na bandeira."},
    {"id": "collect", "label": "Coleta", "desc": "Pegue todos os itens."},
    {"id": "maze", "label": "Labirinto", "desc": "Encontre a saída."},
    {"id": "escape", "label": "Fuga", "desc": "Fuja dos monstros até o portal."},
    {"id": "race", "label": "Corrida", "desc": "Chegue ao fim da pista."},
    {"id": "shooter", "label": "Tiro simples", "desc": "Desvie e atire nos inimigos (espaço = tiro)."},
]

SCENARIOS = [
    {"id": "forest", "label": "Floresta", "emoji": "🌲", "bg": "#0d2818"},
    {"id": "space", "label": "Espaço", "emoji": "🚀", "bg": "#0a0a1a"},
    {"id": "castle", "label": "Castelo", "emoji": "🏰", "bg": "#1a1220"},
    {"id": "ocean", "label": "Oceano", "emoji": "🌊", "bg": "#0a1e2e"},
    {"id": "city", "label": "Cidade", "emoji": "🏙️", "bg": "#121820"},
    {"id": "desert", "label": "Deserto", "emoji": "🏜️", "bg": "#2a2210"},
    {"id": "snow", "label": "Neve", "emoji": "❄️", "bg": "#1a2430"},
    {"id": "volcano", "label": "Vulcão", "emoji": "🌋", "bg": "#2a1010"},
]

HEROES = [
    {"id": "hero", "label": "Herói", "emoji": "🦸"},
    {"id": "robot", "label": "Robô", "emoji": "🤖"},
    {"id": "cat", "label": "Gato", "emoji": "🐱"},
    {"id": "knight", "label": "Cavaleiro", "emoji": "⚔️"},
    {"id": "wizard", "label": "Mago", "emoji": "🧙"},
    {"id": "alien", "label": "Alienígena", "emoji": "👽"},
    {"id": "ninja", "label": "Ninja", "emoji": "🥷"},
    {"id": "dog", "label": "Cachorro", "emoji": "🐶"},
]

ITEMS = [
    {"id": "coin", "label": "Moedas", "emoji": "🪙"},
    {"id": "star", "label": "Estrelas", "emoji": "⭐"},
    {"id": "gem", "label": "Gemas", "emoji": "💎"},
    {"id": "key", "label": "Chaves", "emoji": "🔑"},
    {"id": "heart", "label": "Corações", "emoji": "❤️"},
    {"id": "candy", "label": "Doces", "emoji": "🍬"},
]

MONSTERS = [
    {"id": "slime", "label": "Slime", "emoji": "🟢"},
    {"id": "ghost", "label": "Fantasma", "emoji": "👻"},
    {"id": "robot_enemy", "label": "Robô inimigo", "emoji": "👾"},
    {"id": "bat", "label": "Morcego", "emoji": "🦇"},
    {"id": "dragon", "label": "Dragão", "emoji": "🐉"},
    {"id": "none", "label": "Sem monstros", "emoji": "☮️"},
]

DIFFICULTIES = [
    {"id": "easy", "label": "Fácil (criança)", "lives": 5, "speed": 0.75, "enemies": 1},
    {"id": "normal", "label": "Normal", "lives": 3, "speed": 1.0, "enemies": 2},
    {"id": "hard", "label": "Difícil", "lives": 2, "speed": 1.35, "enemies": 3},
]

THEMES_KID = [
    "para criança", "kids", "infantil", "fácil", "facil", "iniciante", "divertido",
]


def options_catalog() -> dict[str, Any]:
    return {
        "types": GAME_TYPES,
        "scenarios": SCENARIOS,
        "heroes": HEROES,
        "items": ITEMS,
        "monsters": MONSTERS,
        "difficulties": DIFFICULTIES,
        "tips": [
            "Descreva: tipo + cenário + herói + o que coletar.",
            "Ex: 'plataforma no espaço com ninja que pega gemas, fácil'",
            "Ex: 'labirinto no castelo com mago, sem monstros'",
            "Depois ajuste os menus e clique em Prévia.",
        ],
    }


def _guess_from_text(text: str) -> dict[str, str]:
    t = (text or "").lower()
    gtype = "platform"
    if any(w in t for w in ("labirinto", "maze", "saída", "saida")):
        gtype = "maze"
    elif any(w in t for w in ("fuga", "fugir", "escape", "correr dos")):
        gtype = "escape"
    elif any(w in t for w in ("coleta", "pegar tudo", "coletar", "pegar todos")):
        gtype = "collect"
    elif any(w in t for w in ("corrida", "race", "pista", "velocidade")):
        gtype = "race"
    elif any(w in t for w in ("tiro", "shooter", "atirar", "nave")):
        gtype = "shooter"

    scenario = "forest"
    mapping = {
        "espaço": "space", "espaco": "space", "space": "space", "galáxia": "space",
        "castelo": "castle", "castle": "castle",
        "oceano": "ocean", "mar": "ocean", "água": "ocean",
        "cidade": "city", "city": "city",
        "deserto": "desert",
        "neve": "snow", "gelo": "snow", "inverno": "snow",
        "vulcão": "volcano", "vulcao": "volcano", "lava": "volcano",
        "floresta": "forest",
    }
    for k, v in mapping.items():
        if k in t:
            scenario = v
            break

    hero = "hero"
    for h in HEROES:
        if h["label"].lower() in t or h["id"] in t:
            hero = h["id"]
            break
    for word, hid in (("gato", "cat"), ("cachorro", "dog"), ("cão", "dog"), ("robo", "robot"),
                      ("robô", "robot"), ("mago", "wizard"), ("ninja", "ninja"),
                      ("cavaleiro", "knight"), ("alien", "alien")):
        if word in t:
            hero = hid
            break

    item = "coin"
    for word, iid in (("estrela", "star"), ("gema", "gem"), ("chave", "key"),
                      ("coração", "heart"), ("coracao", "heart"), ("doce", "candy")):
        if word in t:
            item = iid
            break

    monster = "slime"
    if any(w in t for w in ("sem monstro", "sem inimigo", "pacífico", "pacifico", "sem inimigos")):
        monster = "none"
    else:
        for word, mid in (("fantasma", "ghost"), ("morcego", "bat"), ("dragão", "dragon"),
                          ("dragao", "dragon"), ("alien", "robot_enemy"), ("slime", "slime")):
            if word in t:
                monster = mid
                break

    diff = "normal"
    if any(w in t for w in THEMES_KID):
        diff = "easy"
    if any(w in t for w in ("difícil", "dificil", "hard", "hardcore")):
        diff = "hard"

    title = text.strip()[:48] if text and text.strip() else "Meu jogo"
    title = re.sub(r"\s+", " ", title).strip() or "Meu jogo"
    # short title: first meaningful chunk
    if len(title) > 36:
        title = title[:33] + "…"

    return {
        "title": title,
        "type": gtype,
        "scenario": scenario,
        "hero": hero,
        "item": item,
        "monster": monster,
        "difficulty": diff,
        "description": text.strip()[:400],
        "levels": 1 if diff == "easy" else (2 if diff == "normal" else 3),
    }


def fill_from_description(description: str) -> dict[str, Any]:
    guessed = _guess_from_text(description)
    return {"ok": True, "fields": guessed, "catalog": options_catalog()}


def _entity(eid: str, kind: str, **kw: Any) -> dict[str, Any]:
    e = {"id": eid, "kind": kind}
    e.update(kw)
    return e


def _build_level(gtype: str, level: int, width: int, height: int,
                 her: dict, it: dict, mon: dict, diff: dict) -> list[dict]:
    entities: list[dict] = []
    n_enemies = min(diff["enemies"] + level - 1, 5)
    if mon["id"] == "none":
        n_enemies = 0

    player = _entity("player", "player", emoji=her["emoji"], x=50, y=height - 100,
                     w=36, h=36, vx=0, vy=0)
    entities.append(player)

    if gtype == "platform":
        entities.append(_entity("ground", "platform", x=0, y=height - 36, w=width, h=36))
        platforms = [
            (120 + level * 20, 360 - level * 10, 130, 16),
            (320, 290 - level * 15, 140, 16),
            (520 + level * 10, 220, 130, 16),
            (200, 150, 100, 16),
        ]
        if level >= 2:
            platforms.append((400, 120, 120, 16))
        if level >= 3:
            platforms.append((650, 300, 100, 16))
        for i, (x, y, w, h) in enumerate(platforms):
            entities.append(_entity(f"p{i}", "platform", x=x, y=y, w=w, h=h))
        n_items = 4 + level * 2
        for i in range(n_items):
            entities.append(_entity(
                f"item{i}", "item", emoji=it["emoji"],
                x=100 + (i * 90) % (width - 80),
                y=80 + (i % 4) * 50,
                w=24, h=24, points=10,
            ))
        # extra life
        if level == 1:
            entities.append(_entity("life1", "powerup", emoji="❤️", x=350, y=250, w=22, h=22, effect="life"))
        for i in range(n_enemies):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"],
                x=250 + i * 140, y=height - 90, w=30, h=30,
                patrol=[180 + i * 100, 350 + i * 100],
            ))
        entities.append(_entity("goal", "goal", emoji="🏁", x=width - 70, y=170, w=40, h=40))
        player["y"] = height - 100

    elif gtype == "collect":
        entities.append(_entity("ground", "platform", x=0, y=height - 36, w=width, h=36))
        n_items = 6 + level * 3
        for i in range(n_items):
            entities.append(_entity(
                f"item{i}", "item", emoji=it["emoji"],
                x=60 + (i % 5) * 150, y=60 + (i // 5) * 100,
                w=28, h=28, points=15,
            ))
        for i in range(n_enemies):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"],
                x=150 + i * 180, y=180, w=30, h=30,
                patrol=[80 + i * 50, width - 100],
            ))
        player["y"] = height - 100

    elif gtype == "maze":
        walls = [
            (0, 0, width, 18), (0, height - 18, width, 18),
            (0, 0, 18, height), (width - 18, 0, 18, height),
            (100, 60, 18, 220 + level * 20),
            (220, 100, 180 + level * 30, 18),
            (380, 180, 18, 200),
            (500, 60, 18, 260),
            (180, 300, 160, 18),
            (600, 200, 120, 18),
        ]
        if level >= 2:
            walls.append((300, 60, 18, 100))
        if level >= 3:
            walls.append((450, 320, 100, 18))
        for i, (x, y, w, h) in enumerate(walls):
            entities.append(_entity(f"wall{i}", "wall", x=x, y=y, w=w, h=h))
        player["x"], player["y"] = 40, 40
        entities.append(_entity("goal", "goal", emoji="🚪", x=width - 70, y=height - 70, w=36, h=36))
        for i in range(n_enemies):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"],
                x=280 + i * 80, y=200 + i * 40, w=26, h=26,
                patrol=[200, 500],
            ))
        # optional keys
        if level >= 2:
            entities.append(_entity("key1", "item", emoji="🔑", x=250, y=140, w=22, h=22, points=20))

    elif gtype == "escape":
        entities.append(_entity("ground", "platform", x=0, y=height - 36, w=width, h=36))
        entities.append(_entity("goal", "goal", emoji="🌀", x=width - 80, y=height - 100, w=48, h=48))
        for i in range(max(2, n_enemies + 1)):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"],
                x=180 + i * 120, y=80 + i * 50, w=32, h=32, chase=True,
            ))
        player["y"] = height - 100

    elif gtype == "race":
        entities.append(_entity("ground", "platform", x=0, y=height - 36, w=width * 2, h=36))
        for i in range(5 + level):
            entities.append(_entity(
                f"item{i}", "item", emoji=it["emoji"],
                x=150 + i * 160, y=height - 120 - (i % 3) * 40, w=24, h=24, points=10,
            ))
        for i in range(n_enemies):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"],
                x=300 + i * 200, y=height - 90, w=30, h=30,
                patrol=[250 + i * 180, 450 + i * 180],
            ))
        entities.append(_entity("goal", "goal", emoji="🏁", x=width * 2 - 100, y=height - 100, w=50, h=50))
        player["y"] = height - 100

    else:  # shooter
        player["x"], player["y"] = 80, height // 2
        for i in range(6 + level * 2):
            entities.append(_entity(
                f"enemy{i}", "enemy", emoji=mon["emoji"] if mon["id"] != "none" else "👾",
                x=width - 80 - (i % 3) * 60,
                y=40 + (i * 55) % (height - 80),
                w=28, h=28, vx=-40 - level * 10,
            ))
        entities.append(_entity("goal", "goal", emoji="⭐", x=width - 40, y=20, w=1, h=1))  # win by score

    return entities


def build_game_spec(payload: dict[str, Any]) -> dict[str, Any]:
    gtype = payload.get("type") or "platform"
    scenario = payload.get("scenario") or "forest"
    hero = payload.get("hero") or "hero"
    item = payload.get("item") or "coin"
    monster = payload.get("monster") or "slime"
    difficulty = payload.get("difficulty") or "normal"
    title = (payload.get("title") or "Meu jogo").strip()[:80]
    description = (payload.get("description") or "").strip()[:400]
    n_levels = int(payload.get("levels") or 1)
    n_levels = max(1, min(5, n_levels))

    diff = next((d for d in DIFFICULTIES if d["id"] == difficulty), DIFFICULTIES[1])
    scen = next((s for s in SCENARIOS if s["id"] == scenario), SCENARIOS[0])
    her = next((h for h in HEROES if h["id"] == hero), HEROES[0])
    it = next((i for i in ITEMS if i["id"] == item), ITEMS[0])
    mon = next((m for m in MONSTERS if m["id"] == monster), MONSTERS[0])

    width, height = 800, 480
    if gtype == "race":
        width = 1200

    levels = []
    for lv in range(1, n_levels + 1):
        levels.append({
            "index": lv,
            "entities": _build_level(gtype, lv, width, height, her, it, mon, diff),
        })

    win_mode = {
        "platform": "reach_goal",
        "collect": "collect_all",
        "maze": "reach_goal",
        "escape": "reach_goal",
        "race": "reach_goal",
        "shooter": "survive_or_clear",
    }.get(gtype, "reach_goal")

    # Studio 2.0: regras e editor visual simples. O cliente nunca envia código executável.
    studio_in = payload.get("studio") if isinstance(payload.get("studio"), dict) else {}
    studio = {
        "theme": str(studio_in.get("theme") or "cyber")[:24],
        "camera": str(studio_in.get("camera") or "follow")[:24],
        "time_limit": max(0, min(int(studio_in.get("time_limit") or 0), 3600)),
        "score_goal": max(0, min(int(studio_in.get("score_goal") or 0), 1000000)),
        "checkpoints": bool(studio_in.get("checkpoints", True)),
        "powerups": [str(x)[:24] for x in (studio_in.get("powerups") or []) if str(x).strip()][:8],
        "boss": str(studio_in.get("boss") or "none")[:24],
        "music": str(studio_in.get("music") or "none")[:24],
        "story": str(studio_in.get("story") or "").strip()[:1200],
        "difficulty_scaling": bool(studio_in.get("difficulty_scaling", False)),
        "save_progress": bool(studio_in.get("save_progress", True)),
    }
    editor_cells = []
    for cell in (payload.get("editor_cells") or [])[:500]:
        if not isinstance(cell, dict):
            continue
        try:
            col, row = int(cell.get("col", 0)), int(cell.get("row", 0))
            kind = str(cell.get("kind") or "platform")
            if 0 <= col < 32 and 0 <= row < 16 and kind in {"platform","item","enemy","powerup","goal"}:
                editor_cells.append({"col": col, "row": row, "kind": kind})
        except Exception:
            continue
    if editor_cells:
        # 25px cells; player/spawn stays from the generated template.
        for lv in levels:
            extra = []
            for i, c in enumerate(editor_cells):
                x, y = c["col"] * 25, c["row"] * 25
                if c["kind"] == "platform": extra.append(_entity(f"edit_p{i}", "platform", x=x, y=y, w=25, h=25))
                elif c["kind"] == "item": extra.append(_entity(f"edit_i{i}", "item", emoji=it["emoji"], x=x+3, y=y+3, w=20, h=20, points=20))
                elif c["kind"] == "enemy": extra.append(_entity(f"edit_e{i}", "enemy", emoji=mon["emoji"], x=x, y=y, w=24, h=24, patrol=[max(0,x-25), min(width-30,x+25)]))
                elif c["kind"] == "powerup": extra.append(_entity(f"edit_pw{i}", "powerup", emoji="⚡", x=x+3, y=y+3, w=20, h=20, effect="life"))
                elif c["kind"] == "goal": extra.append(_entity(f"edit_g{i}", "goal", emoji="🏁", x=x, y=y, w=28, h=28))
            lv["entities"].extend(extra)

    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "type": gtype,
        "scenario": scenario,
        "scenario_emoji": scen["emoji"],
        "bg": scen.get("bg", "#0b1628"),
        "hero": hero,
        "hero_emoji": her["emoji"],
        "item": item,
        "item_emoji": it["emoji"],
        "monster": monster,
        "monster_emoji": mon["emoji"],
        "difficulty": difficulty,
        "lives": diff["lives"],
        "speed": diff["speed"],
        "width": width,
        "height": height,
        "win_mode": win_mode,
        "levels": levels,
        "entities": levels[0]["entities"],  # compat runtime atual
        "controls": {
            "move": "Setas ou WASD",
            "jump": "Espaço / ↑",
            "shoot": "Espaço (modo tiro)",
        },
        "studio": studio,
        "editor_cells": editor_cells,
        "created_at": int(time.time()),
    }


def save_game(user_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    folder = DATA_DIR / uid
    folder.mkdir(parents=True, exist_ok=True)
    gid = spec.get("id") or str(uuid.uuid4())
    spec["id"] = gid
    path = folder / f"{gid}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "id": gid, "title": spec.get("title")}


def list_games(user_id: str) -> list[dict[str, Any]]:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    folder = DATA_DIR / uid
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id"),
                "title": data.get("title"),
                "type": data.get("type"),
                "scenario_emoji": data.get("scenario_emoji"),
                "hero_emoji": data.get("hero_emoji"),
                "difficulty": data.get("difficulty"),
                "created_at": data.get("created_at"),
            })
        except Exception:
            continue
    return out


def load_game(user_id: str, game_id: str) -> dict[str, Any] | None:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    path = DATA_DIR / uid / f"{game_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_game(user_id: str, game_id: str) -> bool:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    path = DATA_DIR / uid / f"{game_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
