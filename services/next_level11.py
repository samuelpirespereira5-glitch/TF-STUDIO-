"""JARVIS Game Studio 11 — Nível Ambicioso (lista Claude screenshots).

Estende o Nível 10 sem reescrever o que já funciona.

Jogos: Editor de IA (texto → jogo), co-op online WebSocket, sistema de mods, ranking global cross-jogos
Programação: Projeto do mês (hackathon), linter/formatter ao vivo, entrevista técnica simulada, viz. algoritmos animada
Gamificação: Temporadas (season pass), missões diárias/semanais variadas, apostas de XP entre clãs
Certificados: Competências específicas listadas, integração LinkedIn
Estudos: Tutor IA plano personalizado, simulados cronometrados, modo "ensine para aprender"
Comunidade: Eventos ao vivo, sistema de reputação, portfólio público exportável
Infra: Backup export/import conta, dark mode/temas, analytics admin, i18n PT/EN
Mobile: PWA + notificações push (stubs)
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NL_DIR = DATA_DIR / "next_level11"
NL_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _week_id() -> str:
    d = datetime.now(timezone.utc)
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"


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
# 1. JOGOS — Editor IA, Co-op WebSocket, Mods, Ranking global
# ===========================================================================

AI_GAMES_FILE = NL_DIR / "ai_games.json"
MODS_FILE = NL_DIR / "mods.json"
GLOBAL_RANK_FILE = NL_DIR / "global_rank.json"
COOP_ROOMS_FILE = NL_DIR / "coop_rooms.json"


def generate_game_from_text(user_id: str, description: str) -> dict:
    """Simula geração de jogo completo a partir de descrição em texto."""
    desc = (description or "").strip()
    if len(desc) < 8:
        return {"ok": False, "error": "Descrição muito curta (mín. 8 chars)"}
    game_id = f"ai_{uuid.uuid4().hex[:10]}"
    # Heurística simples para tipo de jogo
    lower = desc.lower()
    if any(w in lower for w in ("plataforma", "platformer", "pulo", "salto", "gelo")):
        genre = "platformer"
        physics = {"gravity": 0.45, "jump": -9.5, "friction": 0.82}
        phases = 3 if "3" in lower or "três" in lower else 2
    elif any(w in lower for w in ("corrida", "racing", "carro", "pista")):
        genre = "racing"
        physics = {"accel": 0.3, "max_speed": 12, "drag": 0.98}
        phases = 1
    elif any(w in lower for w in ("puzzle", "bloco", "tetris", "match")):
        genre = "puzzle"
        physics = {"grid": [10, 20], "gravity_step": 1}
        phases = 5
    else:
        genre = "topdown"
        physics = {"speed": 4, "collision": "aabb"}
        phases = 2

    game = {
        "id": game_id,
        "user_id": user_id,
        "title": f"Jogo gerado: {desc[:40]}",
        "description": desc,
        "genre": genre,
        "physics": physics,
        "phases": [
            {
                "id": i + 1,
                "name": f"Fase {i + 1}",
                "theme": "gelo" if "gelo" in lower else "padrão",
                "enemies": 3 + i * 2,
                "goal": "chegar ao portal",
            }
            for i in range(phases)
        ],
        "assets_hint": ["player_sprite", "tileset", "bg_music"],
        "code_stub": f"# Auto-generated {genre}\n# physics={physics}\n# TODO: implement main loop",
        "created_at": _now(),
    }
    with _lock:
        games = _load_json(AI_GAMES_FILE, [])
        games.append(game)
        _save_json(AI_GAMES_FILE, games[-80:])
    return {"ok": True, "game": game}


def list_ai_games(user_id: str | None = None) -> list:
    games = _load_json(AI_GAMES_FILE, [])
    if user_id:
        return [g for g in games if g.get("user_id") == user_id]
    return games[-30:]


def create_coop_room(user_id: str, game_id: str, max_players: int = 4) -> dict:
    """Cria sala co-op online (WebSocket ready — stub de sala)."""
    room_id = f"coop_{uuid.uuid4().hex[:8]}"
    room = {
        "id": room_id,
        "game_id": game_id or "demo",
        "host": user_id,
        "players": [{"id": user_id, "joined_at": _now()}],
        "max_players": max(2, min(int(max_players), 8)),
        "status": "waiting",
        "ws_url_hint": f"/ws/coop/{room_id}",
        "created_at": _now(),
    }
    with _lock:
        rooms = _load_json(COOP_ROOMS_FILE, [])
        rooms.append(room)
        _save_json(COOP_ROOMS_FILE, rooms[-50:])
    return {"ok": True, "room": room}


def join_coop_room(room_id: str, user_id: str) -> dict:
    with _lock:
        rooms = _load_json(COOP_ROOMS_FILE, [])
        for r in rooms:
            if r["id"] == room_id:
                if any(p["id"] == user_id for p in r["players"]):
                    return {"ok": True, "room": r, "msg": "já na sala"}
                if len(r["players"]) >= r["max_players"]:
                    return {"ok": False, "error": "sala cheia"}
                r["players"].append({"id": user_id, "joined_at": _now()})
                if len(r["players"]) >= 2:
                    r["status"] = "ready"
                _save_json(COOP_ROOMS_FILE, rooms)
                return {"ok": True, "room": r}
    return {"ok": False, "error": "sala não encontrada"}


def list_coop_rooms() -> list:
    return _load_json(COOP_ROOMS_FILE, [])[-20:]


def publish_mod(user_id: str, game_id: str, title: str, description: str, content: dict | None = None) -> dict:
    mod_id = f"mod_{uuid.uuid4().hex[:8]}"
    mod = {
        "id": mod_id,
        "game_id": game_id or "any",
        "author": user_id,
        "title": title or "Mod sem título",
        "description": description or "",
        "content": content or {"type": "addon", "files": ["mod.json"]},
        "downloads": 0,
        "created_at": _now(),
    }
    with _lock:
        mods = _load_json(MODS_FILE, [])
        mods.append(mod)
        _save_json(MODS_FILE, mods[-100:])
    return {"ok": True, "mod": mod}


def list_mods(game_id: str | None = None) -> list:
    mods = _load_json(MODS_FILE, [])
    if game_id:
        return [m for m in mods if m.get("game_id") in (game_id, "any")]
    return mods[-40:]


def record_global_score(user_id: str, game_id: str, score: int, meta: dict | None = None) -> dict:
    """Ranking global cross-jogos: pontuação agregada do estúdio."""
    with _lock:
        rank = _load_json(GLOBAL_RANK_FILE, {"players": {}, "entries": []})
        players = rank.setdefault("players", {})
        p = players.setdefault(user_id, {"total_xp": 0, "games": {}, "name": user_id})
        p["total_xp"] = p.get("total_xp", 0) + max(0, int(score))
        p["games"][game_id] = p["games"].get(game_id, 0) + max(0, int(score))
        rank["entries"].append({
            "user_id": user_id,
            "game_id": game_id,
            "score": int(score),
            "meta": meta or {},
            "at": _now(),
        })
        rank["entries"] = rank["entries"][-200:]
        _save_json(GLOBAL_RANK_FILE, rank)
    return {"ok": True, "total_xp": p["total_xp"]}


def global_ranking(limit: int = 20) -> list:
    rank = _load_json(GLOBAL_RANK_FILE, {"players": {}})
    players = rank.get("players", {})
    sorted_p = sorted(players.items(), key=lambda x: x[1].get("total_xp", 0), reverse=True)
    return [
        {"user_id": uid, "total_xp": data.get("total_xp", 0), "games_played": len(data.get("games", {}))}
        for uid, data in sorted_p[:limit]
    ]


# ===========================================================================
# 2. PROGRAMAÇÃO — Projeto do mês, Linter, Entrevista, Viz algoritmos
# ===========================================================================

PROJECTS_FILE = NL_DIR / "month_projects.json"
INTERVIEWS_FILE = NL_DIR / "interviews.json"


def create_month_project(admin_id: str, title: str, description: str, days: int = 14) -> dict:
    """Projeto do mês — desafio grande em equipe (hackathon interno)."""
    pid = f"proj_{uuid.uuid4().hex[:8]}"
    deadline = (datetime.now(timezone.utc) + timedelta(days=max(3, min(days, 30)))).isoformat()
    proj = {
        "id": pid,
        "title": title or "Projeto do Mês",
        "description": description or "",
        "created_by": admin_id,
        "deadline": deadline,
        "teams": [],
        "status": "open",
        "created_at": _now(),
    }
    with _lock:
        projs = _load_json(PROJECTS_FILE, [])
        projs.append(proj)
        _save_json(PROJECTS_FILE, projs[-20:])
    return {"ok": True, "project": proj}


def join_month_project(project_id: str, user_id: str, team_name: str = "") -> dict:
    with _lock:
        projs = _load_json(PROJECTS_FILE, [])
        for p in projs:
            if p["id"] == project_id:
                team = next((t for t in p["teams"] if t.get("name") == (team_name or user_id)), None)
                if not team:
                    team = {"name": team_name or f"Time de {user_id}", "members": [], "submitted": False}
                    p["teams"].append(team)
                if user_id not in team["members"]:
                    team["members"].append(user_id)
                _save_json(PROJECTS_FILE, projs)
                return {"ok": True, "project": p, "team": team}
    return {"ok": False, "error": "projeto não encontrado"}


def list_month_projects() -> list:
    return _load_json(PROJECTS_FILE, [])


def lint_code(code: str, language: str = "python") -> dict:
    """Linter/formatter automático — boas práticas em tempo real (heurístico)."""
    code = code or ""
    issues = []
    suggestions = []
    lines = code.splitlines()
    if language.lower() in ("python", "py"):
        for i, line in enumerate(lines, 1):
            if line.rstrip() != line and line.strip():
                issues.append({"line": i, "sev": "info", "msg": "Espaço em branco no final da linha"})
            if "print(" in line and "debug" not in line.lower():
                suggestions.append({"line": i, "msg": "Considere logging em vez de print em produção"})
            if len(line) > 100:
                issues.append({"line": i, "sev": "warn", "msg": "Linha > 100 chars (PEP8 recomenda ≤79/99)"})
            if "except:" in line:
                issues.append({"line": i, "sev": "error", "msg": "except nu — capture Exception específica"})
        if "def " in code and '"""' not in code and "'''" not in code:
            suggestions.append({"line": 0, "msg": "Adicione docstrings nas funções públicas"})
        if "import *" in code:
            issues.append({"line": 0, "sev": "warn", "msg": "Evite import * — importe nomes explícitos"})
    else:
        suggestions.append({"line": 0, "msg": f"Linter básico para {language}; regras completas em breve"})
    score = max(0, 100 - len(issues) * 8 - len(suggestions) * 3)
    return {
        "ok": True,
        "language": language,
        "score": score,
        "issues": issues,
        "suggestions": suggestions,
        "formatted_hint": "Use black / prettier no CI para formatação automática",
    }


def start_tech_interview(user_id: str, level: str = "junior") -> dict:
    """Modo entrevista técnica simulada com feedback."""
    bank = {
        "junior": [
            {"id": "j1", "q": "O que é uma variável e como declarar em Python?", "type": "open"},
            {"id": "j2", "q": "Diferença entre lista e tupla?", "type": "open"},
            {"id": "j3", "q": "O que faz o método .append()?", "type": "open"},
            {"id": "j4", "q": "Explique o que é um loop for.", "type": "open"},
        ],
        "pleno": [
            {"id": "p1", "q": "Explique GIL em Python e impacto em threads.", "type": "open"},
            {"id": "p2", "q": "Como funciona um hash map internamente?", "type": "open"},
            {"id": "p3", "q": "Diferença entre process e thread.", "type": "open"},
            {"id": "p4", "q": "O que é complexidadade O(n log n)? Dê exemplo.", "type": "open"},
        ],
        "senior": [
            {"id": "s1", "q": "Desenhe a arquitetura de um rate-limiter distribuído.", "type": "system"},
            {"id": "s2", "q": "Como você faria code review de um PR de 2k linhas?", "type": "open"},
            {"id": "s3", "q": "Trade-offs entre monólito e microserviços.", "type": "open"},
        ],
    }
    questions = bank.get(level, bank["junior"])
    session_id = f"int_{uuid.uuid4().hex[:8]}"
    session = {
        "id": session_id,
        "user_id": user_id,
        "level": level,
        "questions": questions,
        "answers": [],
        "started_at": _now(),
        "status": "in_progress",
    }
    with _lock:
        data = _load_json(INTERVIEWS_FILE, [])
        data.append(session)
        _save_json(INTERVIEWS_FILE, data[-40:])
    return {"ok": True, "session": session}


def answer_interview(session_id: str, question_id: str, answer: str) -> dict:
    with _lock:
        data = _load_json(INTERVIEWS_FILE, [])
        for s in data:
            if s["id"] == session_id:
                feedback = _gen_interview_feedback(question_id, answer)
                s["answers"].append({
                    "question_id": question_id,
                    "answer": answer,
                    "feedback": feedback,
                    "at": _now(),
                })
                if len(s["answers"]) >= len(s["questions"]):
                    s["status"] = "completed"
                    s["score"] = sum(a["feedback"].get("score", 50) for a in s["answers"]) // max(1, len(s["answers"]))
                _save_json(INTERVIEWS_FILE, data)
                return {"ok": True, "feedback": feedback, "session": s}
    return {"ok": False, "error": "sessão não encontrada"}


def _gen_interview_feedback(qid: str, answer: str) -> dict:
    ans = (answer or "").strip().lower()
    length = len(ans)
    score = 40
    notes = []
    if length < 20:
        notes.append("Resposta muito curta — expanda com exemplos.")
        score = 30
    elif length > 80:
        score = 70
        notes.append("Boa extensão. Verifique se cobriu o conceito central.")
    else:
        score = 55
        notes.append("Resposta ok; adicione um exemplo concreto para subir a nota.")
    keywords = {
        "j1": ["variável", "atribu", "=", "nome"],
        "j2": ["imutável", "mutável", "tuple", "lista", "list"],
        "p1": ["gil", "global interpreter", "thread", "cpu"],
        "p2": ["hash", "bucket", "colisão", "chave"],
    }
    for k, words in keywords.items():
        if qid.startswith(k[0]) or qid == k:
            if any(w in ans for w in words):
                score = min(95, score + 25)
                notes.append("Mencionou conceitos-chave — ótimo.")
            break
    return {"score": score, "notes": notes, "suggestion": "Pratique explicar em voz alta em 2 minutos."}


def algorithm_viz_steps(algo: str, data: list | None = None) -> dict:
    """Visualização de algoritmos animada passo a passo (dados para frontend)."""
    arr = list(data) if data else [5, 2, 8, 1, 9, 3]
    algo = (algo or "bubble").lower()
    steps = []
    a = arr[:]
    if algo in ("bubble", "bubble_sort"):
        n = len(a)
        for i in range(n):
            for j in range(0, n - i - 1):
                steps.append({"type": "compare", "i": j, "j": j + 1, "array": a[:]})
                if a[j] > a[j + 1]:
                    a[j], a[j + 1] = a[j + 1], a[j]
                    steps.append({"type": "swap", "i": j, "j": j + 1, "array": a[:]})
        steps.append({"type": "done", "array": a[:]})
    elif algo in ("selection", "selection_sort"):
        for i in range(len(a)):
            min_idx = i
            for j in range(i + 1, len(a)):
                steps.append({"type": "compare", "i": min_idx, "j": j, "array": a[:]})
                if a[j] < a[min_idx]:
                    min_idx = j
            a[i], a[min_idx] = a[min_idx], a[i]
            steps.append({"type": "swap", "i": i, "j": min_idx, "array": a[:]})
        steps.append({"type": "done", "array": a[:]})
    elif algo in ("binary", "binary_search"):
        target = a[len(a) // 2] if a else 0
        a_sorted = sorted(a)
        lo, hi = 0, len(a_sorted) - 1
        steps.append({"type": "info", "msg": f"Buscando {target} em {a_sorted}", "array": a_sorted[:]})
        while lo <= hi:
            mid = (lo + hi) // 2
            steps.append({"type": "probe", "lo": lo, "hi": hi, "mid": mid, "array": a_sorted[:]})
            if a_sorted[mid] == target:
                steps.append({"type": "found", "index": mid, "array": a_sorted[:]})
                break
            elif a_sorted[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        else:
            steps.append({"type": "not_found", "array": a_sorted[:]})
    else:
        steps.append({"type": "info", "msg": f"Algoritmo '{algo}' não implementado ainda. Use bubble, selection ou binary."})
    return {"ok": True, "algo": algo, "initial": arr, "steps": steps, "step_count": len(steps)}


# ===========================================================================
# 3. GAMIFICAÇÃO — Temporadas, Missões, Apostas XP clãs
# ===========================================================================

SEASONS_FILE = NL_DIR / "seasons.json"
MISSIONS_FILE = NL_DIR / "missions.json"
BETS_FILE = NL_DIR / "clan_bets.json"


def get_or_create_season() -> dict:
    """Temporadas (season pass): ranking reseta a cada X meses."""
    with _lock:
        data = _load_json(SEASONS_FILE, {"current": None, "history": []})
        cur = data.get("current")
        now = datetime.now(timezone.utc)
        if cur:
            end = datetime.fromisoformat(cur["ends_at"].replace("Z", "+00:00"))
            if now < end:
                return cur
            data["history"].append(cur)
        # Nova temporada de 3 meses
        start = now
        end = start + timedelta(days=90)
        season = {
            "id": f"S{start.year}Q{(start.month - 1) // 3 + 1}",
            "name": f"Temporada {start.strftime('%Y-%m')}",
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "rewards": [
                {"rank": 1, "item": "Skin Lendária + 5000 XP", "exclusive": True},
                {"rank": "2-5", "item": "Badge Ouro + 2000 XP", "exclusive": True},
                {"rank": "6-20", "item": "Badge Prata + 500 XP", "exclusive": False},
            ],
            "rankings": {},
        }
        data["current"] = season
        _save_json(SEASONS_FILE, data)
        return season


def season_add_xp(user_id: str, xp: int) -> dict:
    season = get_or_create_season()
    with _lock:
        data = _load_json(SEASONS_FILE, {})
        cur = data.get("current") or season
        ranks = cur.setdefault("rankings", {})
        ranks[user_id] = ranks.get(user_id, 0) + max(0, int(xp))
        data["current"] = cur
        _save_json(SEASONS_FILE, data)
    return {"ok": True, "season_id": cur["id"], "user_xp": ranks[user_id]}


def season_ranking(limit: int = 15) -> dict:
    season = get_or_create_season()
    ranks = season.get("rankings", {})
    sorted_r = sorted(ranks.items(), key=lambda x: x[1], reverse=True)
    return {
        "season": {"id": season["id"], "name": season["name"], "ends_at": season["ends_at"]},
        "top": [{"user_id": u, "xp": x} for u, x in sorted_r[:limit]],
        "rewards": season.get("rewards", []),
    }


def get_daily_missions(user_id: str) -> dict:
    """Missões diárias/semanais variadas (não só streak)."""
    day = _today()
    week = _week_id()
    seed = int(hashlib.md5(f"{day}:{user_id}".encode()).hexdigest()[:8], 16)
    daily_pool = [
        {"id": "d1", "title": "Complete 1 desafio de código", "xp": 30, "type": "code"},
        {"id": "d2", "title": "Jogue 2 partidas em qualquer jogo", "xp": 25, "type": "play"},
        {"id": "d3", "title": "Poste 1 mensagem no fórum", "xp": 20, "type": "community"},
        {"id": "d4", "title": "Revise 1 certificado ou trilha", "xp": 35, "type": "study"},
        {"id": "d5", "title": "Ajude 1 pessoa na mentoria", "xp": 40, "type": "mentor"},
        {"id": "d6", "title": "Gere 1 jogo com o Editor IA", "xp": 50, "type": "create"},
    ]
    weekly_pool = [
        {"id": "w1", "title": "Complete 5 missões diárias", "xp": 150, "type": "meta"},
        {"id": "w2", "title": "Participe de 1 torneio ou co-op", "xp": 100, "type": "compete"},
        {"id": "w3", "title": "Publique 1 mod ou projeto", "xp": 120, "type": "create"},
        {"id": "w4", "title": "Alcance 500 XP na temporada", "xp": 80, "type": "season"},
    ]
    daily = [daily_pool[(seed + i) % len(daily_pool)] for i in range(3)]
    weekly = [weekly_pool[(seed // 7 + i) % len(weekly_pool)] for i in range(2)]
    with _lock:
        progress = _load_json(MISSIONS_FILE, {})
        up = progress.setdefault(user_id, {})
        up.setdefault("daily", {}).setdefault(day, {m["id"]: False for m in daily})
        up.setdefault("weekly", {}).setdefault(week, {m["id"]: False for m in weekly})
        _save_json(MISSIONS_FILE, progress)
    return {
        "daily": [{"mission": m, "done": progress[user_id]["daily"][day].get(m["id"], False)} for m in daily],
        "weekly": [{"mission": m, "done": progress[user_id]["weekly"][week].get(m["id"], False)} for m in weekly],
        "day": day,
        "week": week,
    }


def complete_mission(user_id: str, mission_id: str, scope: str = "daily") -> dict:
    day = _today()
    week = _week_id()
    with _lock:
        progress = _load_json(MISSIONS_FILE, {})
        up = progress.setdefault(user_id, {})
        key = day if scope == "daily" else week
        bucket = up.setdefault(scope, {}).setdefault(key, {})
        if bucket.get(mission_id):
            return {"ok": True, "already": True}
        bucket[mission_id] = True
        _save_json(MISSIONS_FILE, progress)
    # XP aproximado
    xp = 30 if scope == "daily" else 100
    season_add_xp(user_id, xp)
    return {"ok": True, "xp_gained": xp}


def place_clan_bet(clan_id: str, tournament_id: str, amount_xp: int, user_id: str) -> dict:
    """Sistema de apostas de XP entre clãs em torneios."""
    if amount_xp < 10:
        return {"ok": False, "error": "aposta mínima 10 XP"}
    bet = {
        "id": f"bet_{uuid.uuid4().hex[:8]}",
        "clan_id": clan_id,
        "tournament_id": tournament_id,
        "amount": int(amount_xp),
        "by": user_id,
        "status": "open",
        "created_at": _now(),
    }
    with _lock:
        bets = _load_json(BETS_FILE, [])
        bets.append(bet)
        _save_json(BETS_FILE, bets[-100:])
    return {"ok": True, "bet": bet}


def list_clan_bets(tournament_id: str | None = None) -> list:
    bets = _load_json(BETS_FILE, [])
    if tournament_id:
        return [b for b in bets if b.get("tournament_id") == tournament_id]
    return bets[-30:]


def resolve_clan_bet(bet_id: str, winner_clan: str) -> dict:
    with _lock:
        bets = _load_json(BETS_FILE, [])
        for b in bets:
            if b["id"] == bet_id:
                b["status"] = "resolved"
                b["winner_clan"] = winner_clan
                b["resolved_at"] = _now()
                _save_json(BETS_FILE, bets)
                return {"ok": True, "bet": b}
    return {"ok": False, "error": "aposta não encontrada"}


# ===========================================================================
# 4. CERTIFICADOS — Competências específicas + LinkedIn
# ===========================================================================

CERTS_FILE = NL_DIR / "certs_skills.json"


def issue_skills_cert(
    user_id: str,
    user_name: str,
    track: str,
    skills: list[str],
    score: float = 80.0,
) -> dict:
    """Certificado com competências específicas listadas."""
    token = secrets.token_urlsafe(16)
    cert = {
        "token": token,
        "user_id": user_id,
        "user_name": user_name or user_id,
        "track": track or "Trilha",
        "skills": skills or ["Fundamentos"],
        "score": float(score),
        "issued_at": _now(),
        "verify_url": f"/api/nl11/cert/verify/{token}",
        "linkedin_share": {
            "url": f"https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME&name={track}&organizationName=JARVIS%20Game%20Studio&issueYear={datetime.now().year}&certUrl={{BASE}}/api/nl11/cert/verify/{token}",
            "button_label": "Adicionar certificado no LinkedIn",
        },
    }
    with _lock:
        certs = _load_json(CERTS_FILE, [])
        certs.append(cert)
        _save_json(CERTS_FILE, certs[-100:])
    return cert


def verify_skills_cert(token: str) -> dict:
    certs = _load_json(CERTS_FILE, [])
    for c in certs:
        if c.get("token") == token:
            return {"ok": True, "valid": True, "cert": c}
    return {"ok": True, "valid": False, "error": "certificado não encontrado"}


def list_user_skills_certs(user_id: str) -> list:
    return [c for c in _load_json(CERTS_FILE, []) if c.get("user_id") == user_id]


# ===========================================================================
# 5. ESTUDOS — Tutor IA, Simulados, Ensine para aprender
# ===========================================================================

PLANS_FILE = NL_DIR / "study_plans.json"
SIMULADOS_FILE = NL_DIR / "simulados.json"
TEACH_FILE = NL_DIR / "teach_recordings.json"


def generate_study_plan(user_id: str, known_topics: list[str], goal: str = "") -> dict:
    """Tutor por IA: plano de estudos personalizado baseado no que o usuário já sabe."""
    known = set(t.lower().strip() for t in (known_topics or []))
    catalog = [
        {"id": "py-basics", "title": "Python Básico", "prereq": [], "hours": 8},
        {"id": "py-oop", "title": "Orientação a Objetos", "prereq": ["py-basics"], "hours": 6},
        {"id": "py-algo", "title": "Algoritmos e Estruturas", "prereq": ["py-basics"], "hours": 10},
        {"id": "web-html", "title": "HTML/CSS", "prereq": [], "hours": 5},
        {"id": "web-js", "title": "JavaScript", "prereq": ["web-html"], "hours": 8},
        {"id": "web-flask", "title": "Flask / Backend", "prereq": ["py-basics", "web-js"], "hours": 12},
        {"id": "game-loop", "title": "Game Loop & Física", "prereq": ["py-basics"], "hours": 7},
        {"id": "game-ai", "title": "IA em Jogos", "prereq": ["game-loop", "py-algo"], "hours": 9},
        {"id": "security", "title": "Segurança Web", "prereq": ["web-flask"], "hours": 8},
    ]
    # Já sabe se o id ou título contém alguma palavra conhecida
    def is_known(item):
        title_l = item["title"].lower()
        return item["id"] in known or any(k in title_l or k in item["id"] for k in known)

    known_ids = {c["id"] for c in catalog if is_known(c)}
    # Também aceita nomes parciais do usuário
    for t in known:
        for c in catalog:
            if t in c["id"] or t in c["title"].lower():
                known_ids.add(c["id"])

    plan_items = []
    for c in catalog:
        if c["id"] in known_ids:
            continue
        prereqs_ok = all(p in known_ids or p in [x["id"] for x in plan_items] for p in c["prereq"])
        if prereqs_ok or not c["prereq"]:
            plan_items.append(c)
            if len(plan_items) >= 6:
                break

    plan = {
        "id": f"plan_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "goal": goal or "Avançar nas trilhas",
        "known": list(known_ids),
        "items": plan_items,
        "total_hours": sum(i["hours"] for i in plan_items),
        "created_at": _now(),
    }
    with _lock:
        plans = _load_json(PLANS_FILE, [])
        plans.append(plan)
        _save_json(PLANS_FILE, plans[-50:])
    return {"ok": True, "plan": plan}


def create_simulado(user_id: str, topic: str, minutes: int = 30, n_questions: int = 10) -> dict:
    """Simulados cronometrados tipo prova com correção automática."""
    bank = {
        "python": [
            {"q": "Qual o resultado de 2 ** 3?", "options": ["6", "8", "9", "5"], "a": 1},
            {"q": "Qual estrutura é imutável?", "options": ["list", "dict", "tuple", "set"], "a": 2},
            {"q": "O que é list comprehension?", "options": ["Loop", "Expressão que gera lista", "Função", "Classe"], "a": 1},
            {"q": "Como abrir arquivo para leitura?", "options": ["open(f,'w')", "open(f,'r')", "read(f)", "file(f)"], "a": 1},
            {"q": "O que faz range(3)?", "options": ["[1,2,3]", "[0,1,2]", "[0,1,2,3]", "erro"], "a": 1},
        ],
        "algoritmos": [
            {"q": "Complexidade do binary search?", "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"], "a": 1},
            {"q": "Bubble sort no pior caso?", "options": ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], "a": 2},
            {"q": "Estrutura FIFO?", "options": ["Stack", "Queue", "Tree", "Graph"], "a": 1},
        ],
        "geral": [
            {"q": "O que é HTTP 404?", "options": ["OK", "Redirect", "Not Found", "Error server"], "a": 2},
            {"q": "Git comando para novo branch?", "options": ["git new", "git branch", "git checkout -b", "git create"], "a": 2},
        ],
    }
    topic_l = (topic or "geral").lower()
    qs = bank.get(topic_l, bank["geral"])
    if topic_l == "python":
        qs = bank["python"]
    selected = (qs * ((n_questions // len(qs)) + 1))[:n_questions]
    sim_id = f"sim_{uuid.uuid4().hex[:8]}"
    sim = {
        "id": sim_id,
        "user_id": user_id,
        "topic": topic,
        "minutes": max(5, min(minutes, 120)),
        "questions": [{"id": i, "q": q["q"], "options": q["options"]} for i, q in enumerate(selected)],
        "answers_key": [q["a"] for q in selected],  # server-side only
        "started_at": _now(),
        "status": "open",
    }
    with _lock:
        sims = _load_json(SIMULADOS_FILE, [])
        # não salvar answers_key no arquivo público idealmente, mas ok para demo
        sims.append(sim)
        _save_json(SIMULADOS_FILE, sims[-40:])
    public = {k: v for k, v in sim.items() if k != "answers_key"}
    return {"ok": True, "simulado": public}


def grade_simulado(sim_id: str, answers: list[int]) -> dict:
    with _lock:
        sims = _load_json(SIMULADOS_FILE, [])
        for s in sims:
            if s["id"] == sim_id:
                key = s.get("answers_key", [])
                correct = sum(1 for i, a in enumerate(answers) if i < len(key) and a == key[i])
                total = len(key)
                score = round(100 * correct / total, 1) if total else 0
                s["status"] = "graded"
                s["score"] = score
                s["correct"] = correct
                s["total"] = total
                s["graded_at"] = _now()
                _save_json(SIMULADOS_FILE, sims)
                return {"ok": True, "score": score, "correct": correct, "total": total, "passed": score >= 60}
    return {"ok": False, "error": "simulado não encontrado"}


def submit_teach_recording(user_id: str, topic: str, media_url: str = "", transcript: str = "") -> dict:
    """Modo ensine para aprender: grava explicação para comunidade avaliar."""
    rec = {
        "id": f"teach_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "topic": topic or "Tópico",
        "media_url": media_url or "",
        "transcript": transcript or "",
        "votes": [],
        "avg_score": None,
        "created_at": _now(),
    }
    with _lock:
        recs = _load_json(TEACH_FILE, [])
        recs.append(rec)
        _save_json(TEACH_FILE, recs[-60:])
    return {"ok": True, "recording": rec}


def rate_teach(rec_id: str, voter: str, score: int, comment: str = "") -> dict:
    score = max(1, min(5, int(score)))
    with _lock:
        recs = _load_json(TEACH_FILE, [])
        for r in recs:
            if r["id"] == rec_id:
                r["votes"] = [v for v in r.get("votes", []) if v.get("voter") != voter]
                r["votes"].append({"voter": voter, "score": score, "comment": comment, "at": _now()})
                r["avg_score"] = round(sum(v["score"] for v in r["votes"]) / len(r["votes"]), 2)
                _save_json(TEACH_FILE, recs)
                return {"ok": True, "recording": r}
    return {"ok": False, "error": "gravação não encontrada"}


def list_teach_recordings() -> list:
    return _load_json(TEACH_FILE, [])[-30:]


# ===========================================================================
# 6. COMUNIDADE — Eventos ao vivo, Reputação, Portfólio público
# ===========================================================================

EVENTS_FILE = NL_DIR / "live_events.json"
REPUTATION_FILE = NL_DIR / "reputation.json"
PORTFOLIOS_FILE = NL_DIR / "portfolios.json"


def create_live_event(user_id: str, title: str, starts_at: str, kind: str = "chat") -> dict:
    """Eventos ao vivo (sala de chat/vídeo em horário marcado)."""
    ev = {
        "id": f"ev_{uuid.uuid4().hex[:8]}",
        "host": user_id,
        "title": title or "Evento ao vivo",
        "kind": kind if kind in ("chat", "video", "workshop") else "chat",
        "starts_at": starts_at or _now(),
        "room_url": f"/live/{uuid.uuid4().hex[:6]}",
        "attendees": [user_id],
        "status": "scheduled",
        "created_at": _now(),
    }
    with _lock:
        events = _load_json(EVENTS_FILE, [])
        events.append(ev)
        _save_json(EVENTS_FILE, events[-40:])
    return {"ok": True, "event": ev}


def join_live_event(event_id: str, user_id: str) -> dict:
    with _lock:
        events = _load_json(EVENTS_FILE, [])
        for e in events:
            if e["id"] == event_id:
                if user_id not in e["attendees"]:
                    e["attendees"].append(user_id)
                _save_json(EVENTS_FILE, events)
                return {"ok": True, "event": e}
    return {"ok": False, "error": "evento não encontrado"}


def list_live_events() -> list:
    return _load_json(EVENTS_FILE, [])


def get_reputation(user_id: str) -> dict:
    """Sistema de reputação visível (nível de confiança)."""
    data = _load_json(REPUTATION_FILE, {})
    rep = data.get(user_id, {"points": 0, "level": "Novo", "badges": []})
    pts = rep.get("points", 0)
    if pts >= 500:
        level = "Lenda"
    elif pts >= 200:
        level = "Confiável"
    elif pts >= 50:
        level = "Ativo"
    else:
        level = "Novo"
    rep["level"] = level
    return {"user_id": user_id, **rep}


def add_reputation(user_id: str, points: int, reason: str = "") -> dict:
    with _lock:
        data = _load_json(REPUTATION_FILE, {})
        rep = data.setdefault(user_id, {"points": 0, "history": []})
        rep["points"] = rep.get("points", 0) + int(points)
        rep.setdefault("history", []).append({"points": points, "reason": reason, "at": _now()})
        rep["history"] = rep["history"][-50:]
        data[user_id] = rep
        _save_json(REPUTATION_FILE, data)
    return get_reputation(user_id)


def export_public_portfolio(user_id: str, display_name: str = "") -> dict:
    """Exportar portfólio público (link único)."""
    slug = hashlib.md5(user_id.encode()).hexdigest()[:12]
    # Agrega dados de vários sistemas (stubs + arquivos existentes se houver)
    portfolio = {
        "slug": slug,
        "user_id": user_id,
        "display_name": display_name or user_id,
        "public_url": f"/portfolio/{slug}",
        "sections": {
            "certificates": list_user_skills_certs(user_id),
            "ai_games": list_ai_games(user_id),
            "mods": [m for m in list_mods() if m.get("author") == user_id],
            "teach": [t for t in list_teach_recordings() if t.get("user_id") == user_id],
            "reputation": get_reputation(user_id),
            "global_rank_hint": next((r for r in global_ranking(50) if r["user_id"] == user_id), None),
        },
        "updated_at": _now(),
    }
    with _lock:
        ports = _load_json(PORTFOLIOS_FILE, {})
        ports[slug] = portfolio
        _save_json(PORTFOLIOS_FILE, ports)
    return {"ok": True, "portfolio": portfolio}


def get_portfolio_by_slug(slug: str) -> dict | None:
    ports = _load_json(PORTFOLIOS_FILE, {})
    return ports.get(slug)


# ===========================================================================
# 7. INFRA / QUALIDADE — Backup, Temas, Analytics, i18n
# ===========================================================================

BACKUPS_FILE = NL_DIR / "backups.json"
THEMES_FILE = NL_DIR / "user_themes.json"
ANALYTICS_FILE = NL_DIR / "analytics.json"
I18N = {
    "pt": {
        "welcome": "Bem-vindo ao JARVIS Game Studio",
        "missions": "Missões",
        "season": "Temporada",
        "portfolio": "Portfólio",
        "dark_mode": "Modo escuro",
    },
    "en": {
        "welcome": "Welcome to JARVIS Game Studio",
        "missions": "Missions",
        "season": "Season",
        "portfolio": "Portfolio",
        "dark_mode": "Dark mode",
    },
}


def export_user_backup(user_id: str) -> dict:
    """Backup automático / export de conta."""
    payload = {
        "user_id": user_id,
        "exported_at": _now(),
        "version": 11,
        "data": {
            "ai_games": list_ai_games(user_id),
            "certs": list_user_skills_certs(user_id),
            "reputation": get_reputation(user_id),
            "missions": _load_json(MISSIONS_FILE, {}).get(user_id, {}),
            "theme": _load_json(THEMES_FILE, {}).get(user_id),
        },
    }
    token = secrets.token_urlsafe(12)
    with _lock:
        backups = _load_json(BACKUPS_FILE, {})
        backups[token] = payload
        # keep last 30
        if len(backups) > 30:
            for k in list(backups.keys())[:-30]:
                del backups[k]
        _save_json(BACKUPS_FILE, backups)
    return {"ok": True, "token": token, "backup": payload}


def import_user_backup(user_id: str, token: str) -> dict:
    backups = _load_json(BACKUPS_FILE, {})
    payload = backups.get(token)
    if not payload:
        return {"ok": False, "error": "backup não encontrado"}
    # Em produção copiaria dados; aqui só confirma
    return {"ok": True, "imported_from": payload.get("user_id"), "exported_at": payload.get("exported_at"), "msg": "Dados restaurados (demo)"}


def set_user_theme(user_id: str, theme: str = "dark", custom: dict | None = None) -> dict:
    """Modo dark / temas personalizáveis."""
    allowed = {"dark", "light", "neon", "cyber", "custom"}
    theme = theme if theme in allowed else "dark"
    entry = {"theme": theme, "custom": custom or {}, "updated_at": _now()}
    with _lock:
        themes = _load_json(THEMES_FILE, {})
        themes[user_id] = entry
        _save_json(THEMES_FILE, themes)
    return {"ok": True, "theme": entry}


def get_user_theme(user_id: str) -> dict:
    return _load_json(THEMES_FILE, {}).get(user_id, {"theme": "dark", "custom": {}})


def track_analytics(event: str, user_id: str = "", meta: dict | None = None) -> dict:
    with _lock:
        data = _load_json(ANALYTICS_FILE, {"events": [], "counts": {}})
        data["events"].append({"event": event, "user_id": user_id, "meta": meta or {}, "at": _now()})
        data["events"] = data["events"][-500:]
        data["counts"][event] = data["counts"].get(event, 0) + 1
        _save_json(ANALYTICS_FILE, data)
    return {"ok": True}


def admin_analytics() -> dict:
    """Painel de analytics pro admin."""
    data = _load_json(ANALYTICS_FILE, {"events": [], "counts": {}})
    users = set()
    for e in data.get("events", []):
        if e.get("user_id"):
            users.add(e["user_id"])
    return {
        "unique_users_tracked": len(users),
        "event_counts": data.get("counts", {}),
        "recent": data.get("events", [])[-20:],
        "top_features": sorted(data.get("counts", {}).items(), key=lambda x: x[1], reverse=True)[:10],
    }


def t(key: str, lang: str = "pt") -> str:
    """Internacionalização PT/EN."""
    lang = lang if lang in I18N else "pt"
    return I18N[lang].get(key, key)


def i18n_dict(lang: str = "pt") -> dict:
    return I18N.get(lang, I18N["pt"])


# ===========================================================================
# 8. MOBILE / PWA — stubs de push
# ===========================================================================

PUSH_SUBS_FILE = NL_DIR / "push_subs.json"


def register_push_subscription(user_id: str, endpoint: str, keys: dict | None = None) -> dict:
    """PWA com notificações push (lembrete de streak, nova missão)."""
    sub = {
        "user_id": user_id,
        "endpoint": endpoint or f"https://push.example/{user_id}",
        "keys": keys or {},
        "registered_at": _now(),
    }
    with _lock:
        subs = _load_json(PUSH_SUBS_FILE, [])
        subs = [s for s in subs if s.get("user_id") != user_id]
        subs.append(sub)
        _save_json(PUSH_SUBS_FILE, subs[-100:])
    return {"ok": True, "subscription": sub}


def list_push_targets(event: str = "mission") -> list:
    return _load_json(PUSH_SUBS_FILE, [])


# ===========================================================================
# OVERVIEW
# ===========================================================================

def next_level11_overview(user_id: str) -> dict:
    return {
        "level": 11,
        "title": "Nível Ambicioso — Claude Batch 2",
        "user": user_id,
        "season": season_ranking(5),
        "missions": get_daily_missions(user_id),
        "reputation": get_reputation(user_id),
        "global_rank": global_ranking(5),
        "features": [
            "Editor IA (texto → jogo)",
            "Co-op online (WebSocket rooms)",
            "Sistema de mods",
            "Ranking global cross-jogos",
            "Projeto do mês (hackathon)",
            "Linter em tempo real",
            "Entrevista técnica simulada",
            "Viz. algoritmos animada",
            "Temporadas / season pass",
            "Missões diárias/semanais",
            "Apostas XP entre clãs",
            "Certificados com skills + LinkedIn",
            "Tutor IA plano personalizado",
            "Simulados cronometrados",
            "Ensine para aprender",
            "Eventos ao vivo",
            "Reputação na comunidade",
            "Portfólio público",
            "Backup export/import",
            "Temas / dark mode",
            "Analytics admin",
            "i18n PT/EN",
            "PWA push notifications",
        ],
    }
