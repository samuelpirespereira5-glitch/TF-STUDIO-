"""JARVIS Game Studio 9 MAX — próximo nível (features do Claude).

Não reescreve o que já funciona. Estende:
- Jogos: multiplayer local, level editor, remix, PWA export
- Programação: debugger visual, playground colaborativo, snippets, versões Git-like
- Gamificação: loja cosmética, eventos sazonais, streak reforçado
- Certificados: PDF + QR de verificação pública
- Estudos: re-explicar com IA, biblioteca de PDFs, fórum
- Comunidade: perfil público, comentários/curtidas na galeria
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NL_DIR = DATA_DIR / "next_level9"
NL_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ===========================================================================
# 1. JOGOS — Multiplayer local, Level Editor, Remix, PWA
# ===========================================================================

LEVELS_FILE = NL_DIR / "levels.json"
REMIX_FILE = NL_DIR / "remixes.json"
GALLERY_FILE = NL_DIR / "gallery_meta.json"


def create_level(owner: str, name: str, width: int = 20, height: int = 12, tiles: list | None = None) -> dict:
    """Editor de níveis separado do sprite editor — mapa/fases em grid."""
    with _lock:
        data = _load_json(LEVELS_FILE, {"levels": {}})
        lid = "lvl_" + secrets.token_hex(6)
        grid = tiles if tiles else [[0 for _ in range(width)] for _ in range(height)]
        level = {
            "id": lid,
            "owner": owner,
            "name": (name or "Novo nível")[:80],
            "width": max(8, min(int(width), 64)),
            "height": max(6, min(int(height), 48)),
            "tiles": grid,
            "spawn": {"x": 1, "y": height - 2},
            "goal": {"x": width - 2, "y": 1},
            "entities": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        data["levels"][lid] = level
        _save_json(LEVELS_FILE, data)
        return level


def save_level(owner: str, lid: str, body: dict) -> dict:
    with _lock:
        data = _load_json(LEVELS_FILE, {"levels": {}})
        lvl = data["levels"].get(lid)
        if not lvl or lvl.get("owner") != owner:
            return {"ok": False, "error": "Nível não encontrado ou sem permissão"}
        for k in ("name", "width", "height", "tiles", "spawn", "goal", "entities"):
            if k in body:
                lvl[k] = body[k]
        lvl["updated_at"] = _now()
        _save_json(LEVELS_FILE, data)
        return {"ok": True, "level": lvl}


def list_levels(owner: str) -> list:
    with _lock:
        data = _load_json(LEVELS_FILE, {"levels": {}})
        return [v for v in data["levels"].values() if v.get("owner") == owner]


def get_level(lid: str) -> dict | None:
    with _lock:
        data = _load_json(LEVELS_FILE, {"levels": {}})
        return data["levels"].get(lid)


def remix_game(owner: str, source_project: dict, new_name: str | None = None) -> dict:
    """Sistema de remix: pega jogo de outro usuário e cria versão própria."""
    with _lock:
        data = _load_json(REMIX_FILE, {"remixes": []})
        rid = "rmx_" + secrets.token_hex(6)
        source_id = source_project.get("id") or source_project.get("project_id") or "unknown"
        original_owner = source_project.get("owner") or source_project.get("author") or "anon"
        remix = {
            "id": rid,
            "owner": owner,
            "source_id": str(source_id)[:80],
            "source_owner": str(original_owner)[:80],
            "name": (new_name or f"Remix de {source_project.get('name', 'jogo')}")[:80],
            "project_data": source_project.get("data") or source_project.get("project_data") or source_project,
            "created_at": _now(),
        }
        data["remixes"].append(remix)
        data["remixes"] = data["remixes"][-200:]
        _save_json(REMIX_FILE, data)
        return {"ok": True, "remix": remix}


def list_remixes(owner: str | None = None) -> list:
    with _lock:
        data = _load_json(REMIX_FILE, {"remixes": []})
        items = data.get("remixes") or []
        if owner:
            return [r for r in items if r.get("owner") == owner]
        return items[-50:]


def multiplayer_config(project_data: dict) -> dict:
    """Adiciona flag e controles padrão para multiplayer local (2 jogadores mesmo teclado)."""
    cfg = dict(project_data or {})
    cfg["multiplayer_local"] = True
    cfg["players"] = [
        {"id": 1, "keys": {"left": "a", "right": "d", "jump": "w", "action": "s"}, "color": "#4fc3f7"},
        {"id": 2, "keys": {"left": "ArrowLeft", "right": "ArrowRight", "jump": "ArrowUp", "action": "ArrowDown"}, "color": "#ff8a65"},
    ]
    cfg["multiplayer_note"] = "Jogador 1: WASD | Jogador 2: Setas"
    return cfg


def export_pwa_manifest(game_name: str, game_id: str, start_url: str) -> dict:
    """Gera manifest PWA para o jogo ficar instalável no celular."""
    safe = "".join(c for c in (game_name or "JARVIS Game") if c.isalnum() or c in " -_")[:40]
    return {
        "name": safe,
        "short_name": safe[:12],
        "description": f"Jogo criado no JARVIS Game Studio — {game_id}",
        "start_url": start_url,
        "display": "standalone",
        "background_color": "#0a0e17",
        "theme_color": "#00e5ff",
        "orientation": "any",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }


def export_pwa_html(game_name: str, game_js: str, manifest_url: str) -> str:
    """HTML mínimo instalável (PWA). APK real exigiria build nativo; PWA cobre o pedido de instalável no celular."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#00e5ff">
<link rel="manifest" href="{manifest_url}">
<title>{game_name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0e17;color:#e0f7fa;font-family:system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;min-height:100vh}}
header{{padding:12px;text-align:center}}
canvas{{max-width:100%;border:1px solid #1a3a4a;border-radius:8px;background:#000}}
.hint{{font-size:12px;opacity:.7;margin:8px}}
</style>
</head>
<body>
<header><h1>{game_name}</h1><p class="hint">JARVIS Game Studio · PWA</p></header>
<canvas id="game" width="800" height="450"></canvas>
<script>
if('serviceWorker' in navigator){{navigator.serviceWorker.register('/static/sw-game.js').catch(()=>{{}});}}
{game_js or "// Cole o runtime do jogo aqui"}
</script>
</body>
</html>"""


# ===========================================================================
# 2. PROGRAMAÇÃO — Debugger visual, playground colaborativo, snippets, Git
# ===========================================================================

SNIPPETS_FILE = NL_DIR / "snippets.json"
COLLAB_FILE = NL_DIR / "collab_rooms.json"
DEBUG_SESSIONS = {}  # in-memory step sessions
VERSIONS_DIR = NL_DIR / "code_versions"
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SNIPPETS = [
    {"id": "py_hello", "lang": "python", "title": "Hello World", "code": 'print("Olá, JARVIS!")\n', "tags": ["iniciante"]},
    {"id": "py_for", "lang": "python", "title": "Loop for", "code": "for i in range(5):\n    print(i)\n", "tags": ["loops"]},
    {"id": "py_func", "lang": "python", "title": "Função", "code": "def soma(a, b):\n    return a + b\n\nprint(soma(2, 3))\n", "tags": ["funções"]},
    {"id": "py_list", "lang": "python", "title": "Lista e map", "code": "nums = [1, 2, 3, 4]\nprint([x * 2 for x in nums])\n", "tags": ["listas"]},
    {"id": "js_dom", "lang": "javascript", "title": "DOM query", "code": "const el = document.querySelector('#app');\nel.textContent = 'Pronto!';\n", "tags": ["web"]},
    {"id": "js_fetch", "lang": "javascript", "title": "Fetch async", "code": "async function load() {\n  const r = await fetch('/api/health');\n  console.log(await r.json());\n}\nload();\n", "tags": ["async"]},
    {"id": "html_card", "lang": "html", "title": "Card CSS", "code": '<div class="card">\\n  <h2>Título</h2>\\n  <p>Conteúdo</p>\\n</div>\\n', "tags": ["ui"]},
    {"id": "py_dict", "lang": "python", "title": "Dicionário", "code": 'd = {"nome": "JARVIS", "nivel": 9}\\nprint(d["nome"], d.get("nivel"))\\n', "tags": ["estruturas"]},
]


def list_snippets(lang: str | None = None) -> list:
    with _lock:
        data = _load_json(SNIPPETS_FILE, {"snippets": DEFAULT_SNIPPETS})
        items = data.get("snippets") or DEFAULT_SNIPPETS
        if lang:
            return [s for s in items if s.get("lang") == lang]
        return items


def add_snippet(owner: str, title: str, lang: str, code: str, tags: list | None = None) -> dict:
    with _lock:
        data = _load_json(SNIPPETS_FILE, {"snippets": list(DEFAULT_SNIPPETS)})
        sid = "snp_" + secrets.token_hex(4)
        snip = {
            "id": sid,
            "owner": owner,
            "title": (title or "Snippet")[:80],
            "lang": (lang or "python")[:20],
            "code": (code or "")[:8000],
            "tags": tags or [],
            "created_at": _now(),
        }
        data.setdefault("snippets", []).append(snip)
        _save_json(SNIPPETS_FILE, data)
        return snip


def create_collab_room(owner: str, lang: str = "python", initial_code: str = "") -> dict:
    """Playground colaborativo: dois usuários editando o mesmo código (polling)."""
    with _lock:
        data = _load_json(COLLAB_FILE, {"rooms": {}})
        rid = "room_" + secrets.token_hex(4)
        room = {
            "id": rid,
            "owner": owner,
            "lang": lang,
            "code": initial_code or "# Colabore aqui\n",
            "cursor": {},
            "members": [owner],
            "updated_at": _now(),
            "version": 1,
        }
        data["rooms"][rid] = room
        _save_json(COLLAB_FILE, data)
        return room


def join_collab_room(rid: str, user: str) -> dict:
    with _lock:
        data = _load_json(COLLAB_FILE, {"rooms": {}})
        room = data["rooms"].get(rid)
        if not room:
            return {"ok": False, "error": "Sala não encontrada"}
        if user not in room["members"]:
            room["members"].append(user)
        room["updated_at"] = _now()
        _save_json(COLLAB_FILE, data)
        return {"ok": True, "room": room}


def update_collab_code(rid: str, user: str, code: str) -> dict:
    with _lock:
        data = _load_json(COLLAB_FILE, {"rooms": {}})
        room = data["rooms"].get(rid)
        if not room:
            return {"ok": False, "error": "Sala não encontrada"}
        room["code"] = code[:50000]
        room["version"] = int(room.get("version") or 0) + 1
        room["updated_at"] = _now()
        room["last_editor"] = user
        _save_json(COLLAB_FILE, data)
        return {"ok": True, "version": room["version"], "updated_at": room["updated_at"]}


def get_collab_room(rid: str) -> dict | None:
    with _lock:
        data = _load_json(COLLAB_FILE, {"rooms": {}})
        return data["rooms"].get(rid)


def save_code_version(owner: str, project_id: str, code: str, message: str = "salvar versão") -> dict:
    """Integração Git simplificada: salvar versão / voltar versão anterior."""
    path = VERSIONS_DIR / f"{owner}_{project_id}.json"
    with _lock:
        data = _load_json(path, {"versions": []})
        ver = {
            "n": len(data["versions"]) + 1,
            "message": (message or "salvar versão")[:120],
            "code": code[:100000],
            "at": _now(),
        }
        data["versions"].append(ver)
        data["versions"] = data["versions"][-50:]  # keep last 50
        _save_json(path, data)
        return {"ok": True, "version": ver["n"], "total": len(data["versions"])}


def list_code_versions(owner: str, project_id: str) -> list:
    path = VERSIONS_DIR / f"{owner}_{project_id}.json"
    with _lock:
        data = _load_json(path, {"versions": []})
        return [{"n": v["n"], "message": v["message"], "at": v["at"]} for v in data.get("versions") or []]


def restore_code_version(owner: str, project_id: str, n: int) -> dict:
    path = VERSIONS_DIR / f"{owner}_{project_id}.json"
    with _lock:
        data = _load_json(path, {"versions": []})
        for v in data.get("versions") or []:
            if v.get("n") == n:
                return {"ok": True, "code": v["code"], "message": v["message"], "n": n}
        return {"ok": False, "error": "Versão não encontrada"}


def visual_debugger_start(code: str, lang: str = "python") -> dict:
    """Debugger visual passo a passo — simula execução linha a linha mostrando variáveis.

    Para Python: usa trace simples (sem exec real de código perigoso — apenas análise estática + simulação de assigns).
    """
    lines = (code or "").splitlines() or ["# vazio"]
    sid = "dbg_" + secrets.token_hex(6)
    # Simple line-by-line state for demo (safe, no real exec)
    steps = []
    vars_state: dict[str, Any] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        step = {"line": i + 1, "code": line, "vars": dict(vars_state), "action": "noop"}
        # Detect simple assignments for educational simulation
        if "=" in stripped and not stripped.startswith("#") and not stripped.startswith("def ") and not stripped.startswith("class "):
            parts = stripped.split("=", 1)
            left = parts[0].strip()
            right = parts[1].strip() if len(parts) > 1 else ""
            if left.isidentifier():
                # try literal evaluation of simple values only
                val = right
                try:
                    if right in ("True", "False", "None"):
                        val = {"True": True, "False": False, "None": None}[right]
                    elif right.isdigit() or (right.startswith("-") and right[1:].isdigit()):
                        val = int(right)
                    elif right.replace(".", "", 1).isdigit():
                        val = float(right)
                    elif (right.startswith('"') and right.endswith('"')) or (right.startswith("'") and right.endswith("'")):
                        val = right[1:-1]
                except Exception:
                    pass
                vars_state[left] = val
                step["action"] = "assign"
                step["assigned"] = left
                step["vars"] = dict(vars_state)
        elif stripped.startswith("print("):
            step["action"] = "print"
            step["output_hint"] = stripped
        steps.append(step)
    DEBUG_SESSIONS[sid] = {
        "id": sid,
        "lang": lang,
        "lines": lines,
        "steps": steps,
        "cursor": 0,
        "created_at": _now(),
    }
    return {
        "ok": True,
        "session_id": sid,
        "total_lines": len(lines),
        "first": steps[0] if steps else None,
    }


def visual_debugger_step(session_id: str) -> dict:
    sess = DEBUG_SESSIONS.get(session_id)
    if not sess:
        return {"ok": False, "error": "Sessão expirada ou inválida"}
    idx = sess["cursor"]
    if idx >= len(sess["steps"]):
        return {"ok": True, "done": True, "message": "Fim da execução simulada"}
    step = sess["steps"][idx]
    sess["cursor"] = idx + 1
    return {
        "ok": True,
        "done": False,
        "step": step,
        "progress": f"{idx + 1}/{len(sess['steps'])}",
        "next_available": sess["cursor"] < len(sess["steps"]),
    }


def visual_debugger_reset(session_id: str) -> dict:
    sess = DEBUG_SESSIONS.get(session_id)
    if not sess:
        return {"ok": False, "error": "Sessão não encontrada"}
    sess["cursor"] = 0
    return {"ok": True, "message": "Reiniciado"}


# ===========================================================================
# 3. GAMIFICAÇÃO — Loja, eventos sazonais, streak
# ===========================================================================

SHOP_FILE = NL_DIR / "shop.json"
EVENTS_FILE = NL_DIR / "seasonal_events.json"
STREAK_FILE = NL_DIR / "streaks.json"

SHOP_ITEMS = [
    {"id": "avatar_robot", "name": "Avatar Robô", "type": "avatar", "cost": 50, "icon": "🤖", "desc": "Avatar clássico JARVIS"},
    {"id": "avatar_ninja", "name": "Avatar Ninja", "type": "avatar", "cost": 120, "icon": "🥷", "desc": "Estilo stealth"},
    {"id": "avatar_wizard", "name": "Avatar Mago", "type": "avatar", "cost": 150, "icon": "🧙", "desc": "Magia do código"},
    {"id": "frame_gold", "name": "Moldura Ouro", "type": "frame", "cost": 200, "icon": "🖼️", "desc": "Moldura dourada no perfil"},
    {"id": "frame_neon", "name": "Moldura Neon", "type": "frame", "cost": 180, "icon": "✨", "desc": "Moldura neon ciano"},
    {"id": "frame_cyber", "name": "Moldura Cyber", "type": "frame", "cost": 250, "icon": "🔮", "desc": "Moldura holográfica"},
    {"id": "badge_streak7", "name": "Badge 7 dias", "type": "badge", "cost": 80, "icon": "🔥", "desc": "Exibe streak de 7 dias"},
    {"id": "title_hacker", "name": "Título Hacker", "type": "title", "cost": 300, "icon": "💻", "desc": "Título especial no perfil"},
]


def shop_catalog() -> list:
    return list(SHOP_ITEMS)


def get_user_inventory(user_id: str) -> dict:
    with _lock:
        data = _load_json(SHOP_FILE, {"users": {}})
        u = data["users"].setdefault(user_id, {"owned": [], "equipped": {}, "points": 0})
        return u


def buy_item(user_id: str, item_id: str, current_xp: int = 0) -> dict:
    """Troca pontos/XP por item cosmético. Usa XP do gamification como moeda."""
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        return {"ok": False, "error": "Item não encontrado"}
    with _lock:
        data = _load_json(SHOP_FILE, {"users": {}})
        u = data["users"].setdefault(user_id, {"owned": [], "equipped": {}, "points": 0})
        if item_id in u["owned"]:
            return {"ok": False, "error": "Você já possui este item"}
        # Prefer dedicated points; fallback to XP check from caller
        points = int(u.get("points") or 0)
        if points < item["cost"] and current_xp < item["cost"]:
            return {"ok": False, "error": f"Pontos insuficientes (precisa {item['cost']})"}
        if points >= item["cost"]:
            u["points"] = points - item["cost"]
        u["owned"].append(item_id)
        _save_json(SHOP_FILE, data)
        return {"ok": True, "item": item, "owned": u["owned"], "points_left": u.get("points", 0)}


def equip_item(user_id: str, item_id: str) -> dict:
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        return {"ok": False, "error": "Item inválido"}
    with _lock:
        data = _load_json(SHOP_FILE, {"users": {}})
        u = data["users"].setdefault(user_id, {"owned": [], "equipped": {}, "points": 0})
        if item_id not in u["owned"]:
            return {"ok": False, "error": "Compre o item primeiro"}
        u["equipped"][item["type"]] = item_id
        _save_json(SHOP_FILE, data)
        return {"ok": True, "equipped": u["equipped"]}


def add_shop_points(user_id: str, amount: int) -> dict:
    with _lock:
        data = _load_json(SHOP_FILE, {"users": {}})
        u = data["users"].setdefault(user_id, {"owned": [], "equipped": {}, "points": 0})
        u["points"] = int(u.get("points") or 0) + max(0, amount)
        _save_json(SHOP_FILE, data)
        return {"points": u["points"]}


def current_seasonal_event() -> dict:
    """Evento sazonal / desafio da semana."""
    with _lock:
        data = _load_json(EVENTS_FILE, {"events": []})
        events = data.get("events") or []
        today = _today()
        active = [e for e in events if e.get("start", "") <= today <= e.get("end", "")]
        if active:
            return active[0]
        # auto-generate weekly challenge
        week = datetime.now(timezone.utc).isocalendar()
        eid = f"week_{week[0]}_{week[1]}"
        event = {
            "id": eid,
            "title": f"Desafio da Semana {week[1]}",
            "description": "Complete 5 exercícios ou 3 jogos nesta semana e ganhe recompensa especial.",
            "goal": {"type": "complete_any", "count": 5},
            "reward": {"xp": 100, "item": "frame_neon", "points": 50},
            "start": today,
            "end": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),
            "icon": "🏆",
        }
        data.setdefault("events", []).append(event)
        data["events"] = data["events"][-20:]
        _save_json(EVENTS_FILE, data)
        return event


def record_streak(user_id: str) -> dict:
    """Sistema de streak (dias seguidos estudando, tipo Duolingo)."""
    with _lock:
        data = _load_json(STREAK_FILE, {"users": {}})
        u = data["users"].setdefault(user_id, {"current": 0, "best": 0, "last_day": None, "history": []})
        today = _today()
        last = u.get("last_day")
        if last == today:
            return {"ok": True, "current": u["current"], "best": u["best"], "already_today": True}
        if last:
            try:
                last_d = datetime.strptime(last, "%Y-%m-%d").date()
                today_d = datetime.strptime(today, "%Y-%m-%d").date()
                delta = (today_d - last_d).days
            except Exception:
                delta = 99
            if delta == 1:
                u["current"] = int(u.get("current") or 0) + 1
            elif delta > 1:
                u["current"] = 1
            else:
                u["current"] = max(1, int(u.get("current") or 0))
        else:
            u["current"] = 1
        u["best"] = max(int(u.get("best") or 0), u["current"])
        u["last_day"] = today
        hist = u.setdefault("history", [])
        if today not in hist:
            hist.append(today)
        u["history"] = hist[-90:]
        _save_json(STREAK_FILE, data)
        return {"ok": True, "current": u["current"], "best": u["best"], "already_today": False}


def get_streak(user_id: str) -> dict:
    with _lock:
        data = _load_json(STREAK_FILE, {"users": {}})
        u = data["users"].get(user_id) or {"current": 0, "best": 0, "last_day": None}
        return {"current": u.get("current", 0), "best": u.get("best", 0), "last_day": u.get("last_day")}


# ===========================================================================
# 4. CERTIFICADOS — PDF + QR
# ===========================================================================

CERT_PDF_DIR = DATA_DIR / "certificates" / "pdf"
CERT_PDF_DIR.mkdir(parents=True, exist_ok=True)


def issue_certificate_pdf(nome: str, trilha: str, codigo: str, horas: int = 0, verify_base_url: str = "") -> dict:
    """Gera certificado HTML imprimível + QR (data URL) e tenta PDF se reportlab disponível."""
    verify_url = f"{verify_base_url.rstrip('/')}/certificados/verificar/{codigo}" if verify_base_url else f"/certificados/verificar/{codigo}"
    # QR via free API-less: SVG/data using simple qrcode if available, else placeholder URL
    qr_data_url = ""
    try:
        import qrcode
        import io
        img = qrcode.make(verify_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # fallback: link only
        qr_data_url = ""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Certificado JARVIS — {codigo}</title>
<style>
@page {{ size: A4 landscape; margin: 0; }}
body {{ margin:0; font-family: Georgia, serif; background:#0b1220; color:#e8f4ff; }}
.cert {{ width: 297mm; height: 210mm; box-sizing:border-box; padding:24mm 20mm;
  background: linear-gradient(135deg,#0b1220 0%,#132238 50%,#0b1220 100%);
  border: 8px solid #00e5ff; position:relative; }}
.inner {{ border: 2px solid rgba(0,229,255,.4); height:100%; padding:18px 28px; box-sizing:border-box; }}
h1 {{ text-align:center; letter-spacing:.2em; font-size:28px; color:#00e5ff; margin:8px 0 4px; }}
.sub {{ text-align:center; opacity:.8; font-size:13px; }}
.name {{ text-align:center; font-size:36px; margin:28px 0 8px; color:#fff; border-bottom:1px solid rgba(0,229,255,.3); padding-bottom:8px; }}
.track {{ text-align:center; font-size:18px; margin:12px 0; }}
.meta {{ display:flex; justify-content:space-between; align-items:flex-end; margin-top:40px; font-size:12px; }}
.qr {{ text-align:center; }}
.qr img {{ width:90px; height:90px; background:#fff; padding:4px; }}
.code {{ font-family: monospace; color:#80deea; }}
.footer {{ text-align:center; font-size:11px; opacity:.6; margin-top:16px; }}
</style>
</head>
<body>
<div class="cert"><div class="inner">
  <h1>CERTIFICADO</h1>
  <p class="sub">JARVIS Learning Platform · Certificado próprio do sistema</p>
  <p class="sub">Conferimos a</p>
  <div class="name">{nome}</div>
  <p class="track">a conclusão da trilha <strong>{trilha}</strong>{f' ({horas}h)' if horas else ''}</p>
  <div class="meta">
    <div>
      <div>Código: <span class="code">{codigo}</span></div>
      <div>Emitido em: {datetime.now(timezone.utc).strftime('%d/%m/%Y')}</div>
      <div>Verificação pública: {verify_url}</div>
    </div>
    <div class="qr">
      {"<img src='" + qr_data_url + "' alt='QR'>" if qr_data_url else "<div class='code'>QR: " + verify_url + "</div>"}
      <div>Escaneie para verificar</div>
    </div>
  </div>
  <p class="footer">Este certificado é emitido pelo JARVIS e não representa diploma de instituição externa.</p>
</div></div>
</body>
</html>"""

    html_path = CERT_PDF_DIR / f"{codigo}.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path = None
    try:
        # optional: weasyprint or reportlab — keep graceful
        from weasyprint import HTML as WHTML
        pdf_file = CERT_PDF_DIR / f"{codigo}.pdf"
        WHTML(string=html).write_pdf(str(pdf_file))
        pdf_path = str(pdf_file)
    except Exception:
        pdf_path = None

    return {
        "ok": True,
        "codigo": codigo,
        "html_path": str(html_path),
        "pdf_path": pdf_path,
        "verify_url": verify_url,
        "qr": bool(qr_data_url),
        "download_html": f"/api/nl9/cert/download/{codigo}",
    }


# ===========================================================================
# 5. ESTUDOS — re-explicar, biblioteca PDF, fórum
# ===========================================================================

FORUM_FILE = NL_DIR / "forum.json"
PDF_LIB_FILE = NL_DIR / "pdf_library.json"
STUDY_MISTAKES = NL_DIR / "study_mistakes.json"


def record_exercise_mistake(user_id: str, exercise_id: str, topic: str = "") -> dict:
    """Conta erros repetidos; quando >= 3, sinaliza modo 'explicar de novo'."""
    with _lock:
        data = _load_json(STUDY_MISTAKES, {"users": {}})
        u = data["users"].setdefault(user_id, {})
        key = str(exercise_id)[:80]
        entry = u.setdefault(key, {"count": 0, "topic": topic, "last": None})
        entry["count"] = int(entry.get("count") or 0) + 1
        entry["last"] = _now()
        if topic:
            entry["topic"] = topic
        _save_json(STUDY_MISTAKES, data)
        need_explain = entry["count"] >= 3
        return {"ok": True, "count": entry["count"], "need_reexplain": need_explain, "topic": entry.get("topic")}


def reexplain_prompt(topic: str, exercise_id: str, user_answer: str = "") -> str:
    """Gera prompt para a IA explicar de novo de forma diferente."""
    return (
        f"O aluno errou o exercício '{exercise_id}' sobre '{topic or 'programação'}' várias vezes. "
        f"Resposta do aluno: {user_answer or '(vazia)'}. "
        "Explique o conceito DE NOVO, com analogia do dia a dia, exemplo mínimo de código, "
        "e 1 pergunta de verificação no final. Seja paciente e claro. Responda em português."
    )


def list_pdf_library(subject: str | None = None) -> list:
    with _lock:
        data = _load_json(PDF_LIB_FILE, {"items": [
            {"id": "py_basico", "title": "Python Básico — Apostila JARVIS", "subject": "python", "pages": 24, "path": None},
            {"id": "js_dom", "title": "JavaScript e DOM", "subject": "javascript", "pages": 18, "path": None},
            {"id": "html_css", "title": "HTML & CSS Fundamentos", "subject": "web", "pages": 20, "path": None},
            {"id": "cyber_intro", "title": "Introdução a Cyber (lab autorizado)", "subject": "cyber", "pages": 30, "path": None},
            {"id": "logica", "title": "Lógica de Programação", "subject": "logica", "pages": 16, "path": None},
        ]})
        items = data.get("items") or []
        if subject:
            return [i for i in items if i.get("subject") == subject]
        return items


def add_pdf_entry(title: str, subject: str, path: str | None = None, pages: int = 0) -> dict:
    with _lock:
        data = _load_json(PDF_LIB_FILE, {"items": []})
        item = {
            "id": "pdf_" + secrets.token_hex(4),
            "title": title[:120],
            "subject": subject[:40],
            "pages": pages,
            "path": path,
            "added_at": _now(),
        }
        data.setdefault("items", []).append(item)
        _save_json(PDF_LIB_FILE, data)
        return item


def forum_post(user_id: str, title: str, body: str, tags: list | None = None) -> dict:
    with _lock:
        data = _load_json(FORUM_FILE, {"posts": []})
        post = {
            "id": "post_" + secrets.token_hex(5),
            "user_id": user_id,
            "title": (title or "Dúvida")[:120],
            "body": (body or "")[:4000],
            "tags": tags or [],
            "replies": [],
            "created_at": _now(),
            "likes": 0,
        }
        data["posts"].insert(0, post)
        data["posts"] = data["posts"][:200]
        _save_json(FORUM_FILE, data)
        return post


def forum_reply(post_id: str, user_id: str, body: str) -> dict:
    with _lock:
        data = _load_json(FORUM_FILE, {"posts": []})
        for p in data.get("posts") or []:
            if p.get("id") == post_id:
                reply = {"user_id": user_id, "body": body[:2000], "at": _now()}
                p.setdefault("replies", []).append(reply)
                _save_json(FORUM_FILE, data)
                return {"ok": True, "reply": reply}
        return {"ok": False, "error": "Post não encontrado"}


def forum_list(limit: int = 30) -> list:
    with _lock:
        data = _load_json(FORUM_FILE, {"posts": []})
        return (data.get("posts") or [])[:limit]


# ===========================================================================
# 6. COMUNIDADE — perfil público, comentários/curtidas
# ===========================================================================

PROFILES_FILE = NL_DIR / "public_profiles.json"
COMMENTS_FILE = NL_DIR / "gallery_comments.json"


def update_public_profile(user_id: str, display_name: str = "", bio: str = "", games: list | None = None, certs: list | None = None) -> dict:
    with _lock:
        data = _load_json(PROFILES_FILE, {"profiles": {}})
        p = data["profiles"].setdefault(user_id, {})
        if display_name:
            p["display_name"] = display_name[:60]
        if bio is not None:
            p["bio"] = bio[:300]
        if games is not None:
            p["games"] = games[:50]
        if certs is not None:
            p["certificates"] = certs[:30]
        p["updated_at"] = _now()
        # merge cosmetics from shop
        inv = get_user_inventory(user_id)
        p["equipped"] = inv.get("equipped") or {}
        _save_json(PROFILES_FILE, data)
        return p


def get_public_profile(user_id: str) -> dict:
    with _lock:
        data = _load_json(PROFILES_FILE, {"profiles": {}})
        p = data["profiles"].get(user_id) or {}
    streak = get_streak(user_id)
    inv = get_user_inventory(user_id)
    return {
        "user_id": user_id,
        "display_name": p.get("display_name") or user_id,
        "bio": p.get("bio") or "",
        "games": p.get("games") or [],
        "certificates": p.get("certificates") or [],
        "equipped": inv.get("equipped") or p.get("equipped") or {},
        "streak": streak,
        "updated_at": p.get("updated_at"),
    }


def like_game(game_id: str, user_id: str) -> dict:
    with _lock:
        data = _load_json(COMMENTS_FILE, {"likes": {}, "comments": {}})
        likes = data.setdefault("likes", {}).setdefault(str(game_id), [])
        if user_id in likes:
            likes.remove(user_id)
            liked = False
        else:
            likes.append(user_id)
            liked = True
        _save_json(COMMENTS_FILE, data)
        return {"ok": True, "liked": liked, "count": len(likes)}


def comment_game(game_id: str, user_id: str, text: str) -> dict:
    with _lock:
        data = _load_json(COMMENTS_FILE, {"likes": {}, "comments": {}})
        comments = data.setdefault("comments", {}).setdefault(str(game_id), [])
        c = {
            "id": "cmt_" + secrets.token_hex(4),
            "user_id": user_id,
            "text": (text or "")[:500],
            "at": _now(),
        }
        comments.append(c)
        data["comments"][str(game_id)] = comments[-100:]
        _save_json(COMMENTS_FILE, data)
        return {"ok": True, "comment": c}


def get_game_social(game_id: str) -> dict:
    with _lock:
        data = _load_json(COMMENTS_FILE, {"likes": {}, "comments": {}})
        likes = data.get("likes", {}).get(str(game_id), [])
        comments = data.get("comments", {}).get(str(game_id), [])
        return {"likes": len(likes), "liked_by": likes[:20], "comments": comments[-30:]}


# ===========================================================================
# Overview for UI hub
# ===========================================================================

def next_level_overview(user_id: str) -> dict:
    return {
        "shop": shop_catalog(),
        "inventory": get_user_inventory(user_id),
        "event": current_seasonal_event(),
        "streak": get_streak(user_id),
        "snippets_count": len(list_snippets()),
        "forum_count": len(forum_list(5)),
        "pdf_count": len(list_pdf_library()),
        "features": [
            "multiplayer_local", "level_editor", "remix", "pwa_export",
            "visual_debugger", "collab_playground", "code_versions", "snippets",
            "cosmetic_shop", "seasonal_events", "streak",
            "cert_pdf_qr", "reexplain", "pdf_library", "forum",
            "public_profile", "gallery_likes_comments",
        ],
    }
