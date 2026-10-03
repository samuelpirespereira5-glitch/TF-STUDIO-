"""JARVIS Game Studio 10 MAX — nível mais avançado (lista Claude).

Estende o Nível 9 sem reescrever o que já funciona.

Jogos: marketplace, modo torneio, sistema de replay, templates de física
Programação: code review por IA, desafios de performance, snippets+debugger, pair programming IA
Gamificação: clãs/times, conquistas secretas, loja temporária rotativa
Certificados: verificável por empresa, selo bronze/prata/ouro
Estudos: busca unificada, modo offline, resumo semanal
Comunidade: mentoria, feed de atividades, badges de contribuição
Qualidade: status page, log de erros centralizado, smoke tests
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
NL_DIR = DATA_DIR / "next_level10"
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
# 1. JOGOS — Marketplace, Torneio, Replay, Templates de física
# ===========================================================================

MARKET_FILE = NL_DIR / "marketplace.json"
TOURNAMENT_FILE = NL_DIR / "tournaments.json"
REPLAY_FILE = NL_DIR / "replays.json"
PHYSICS_TEMPLATES = {
    "platformer": {
        "id": "platformer",
        "name": "Plataforma com gravidade",
        "description": "Gravidade + colisão de plataformas + pulo",
        "physics": {
            "gravity": 0.45,
            "friction": 0.82,
            "jump_force": -9.5,
            "max_fall": 12,
            "collision": "aabb",
            "type": "side_view",
        },
        "default_entities": ["player", "platform", "spike", "coin", "flag"],
    },
    "topdown": {
        "id": "topdown",
        "name": "Top-down (visão de cima)",
        "description": "Movimento livre 4/8 direções, sem gravidade",
        "physics": {
            "gravity": 0,
            "friction": 0.9,
            "speed": 3.2,
            "collision": "aabb",
            "type": "top_down",
        },
        "default_entities": ["player", "wall", "npc", "item", "exit"],
    },
    "racing": {
        "id": "racing",
        "name": "Corrida (física veicular simples)",
        "description": "Aceleração, freio, drift leve",
        "physics": {
            "gravity": 0,
            "accel": 0.15,
            "brake": 0.25,
            "max_speed": 8,
            "turn_rate": 0.08,
            "friction": 0.98,
            "type": "racing",
        },
        "default_entities": ["car", "track", "checkpoint", "obstacle"],
    },
    "puzzle_blocks": {
        "id": "puzzle_blocks",
        "name": "Blocos / puzzle (estilo Sokoban)",
        "description": "Empurrar caixas em grade",
        "physics": {
            "gravity": 0,
            "grid": True,
            "pushable": True,
            "type": "grid_puzzle",
        },
        "default_entities": ["player", "box", "wall", "target"],
    },
}


def list_physics_templates() -> list:
    return list(PHYSICS_TEMPLATES.values())


def get_physics_template(tid: str) -> dict | None:
    return PHYSICS_TEMPLATES.get(tid)


def marketplace_list(limit: int = 50) -> list:
    with _lock:
        data = _load_json(MARKET_FILE, {"listings": []})
        items = sorted(data.get("listings", []), key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]


def marketplace_list_item(owner: str, game_id: str, title: str, price_xp: int, description: str = "") -> dict:
    """Usuário lista jogo para venda/troca usando XP/pontos."""
    with _lock:
        data = _load_json(MARKET_FILE, {"listings": [], "sales": []})
        lid = "mkt_" + secrets.token_hex(5)
        item = {
            "id": lid,
            "owner": owner,
            "game_id": game_id,
            "title": (title or "Jogo")[:80],
            "description": (description or "")[:400],
            "price_xp": max(0, int(price_xp)),
            "status": "active",
            "created_at": _now(),
        }
        data.setdefault("listings", []).append(item)
        data["listings"] = data["listings"][-200:]
        _save_json(MARKET_FILE, data)
        return {"ok": True, "listing": item}


def marketplace_buy(buyer: str, listing_id: str, buyer_xp: int) -> dict:
    """Compra com XP. Retorna novo saldo sugerido (o caller aplica)."""
    with _lock:
        data = _load_json(MARKET_FILE, {"listings": [], "sales": []})
        listings = data.get("listings", [])
        item = next((x for x in listings if x["id"] == listing_id and x.get("status") == "active"), None)
        if not item:
            return {"ok": False, "error": "Anúncio não encontrado ou já vendido"}
        if item["owner"] == buyer:
            return {"ok": False, "error": "Não pode comprar o próprio anúncio"}
        price = int(item.get("price_xp", 0))
        if buyer_xp < price:
            return {"ok": False, "error": f"XP insuficiente (precisa {price})"}
        item["status"] = "sold"
        item["buyer"] = buyer
        item["sold_at"] = _now()
        sale = {
            "listing_id": listing_id,
            "seller": item["owner"],
            "buyer": buyer,
            "game_id": item["game_id"],
            "price_xp": price,
            "at": _now(),
        }
        data.setdefault("sales", []).append(sale)
        data["sales"] = data["sales"][-300:]
        _save_json(MARKET_FILE, data)
        return {
            "ok": True,
            "sale": sale,
            "new_buyer_xp": buyer_xp - price,
            "seller_credit_xp": price,
            "game_id": item["game_id"],
        }


# --- Torneios ---

def create_tournament(owner: str, name: str, game_id: str, max_players: int = 8) -> dict:
    """Cria torneio com chaveamento automático (eliminação simples)."""
    with _lock:
        data = _load_json(TOURNAMENT_FILE, {"tournaments": {}})
        tid = "tn_" + secrets.token_hex(5)
        n = max(2, min(int(max_players), 32))
        # próximo potência de 2
        size = 1
        while size < n:
            size *= 2
        t = {
            "id": tid,
            "owner": owner,
            "name": (name or "Torneio")[:80],
            "game_id": game_id,
            "max_players": size,
            "players": [],
            "bracket": [],
            "status": "open",  # open | running | finished
            "created_at": _now(),
            "winner": None,
        }
        data["tournaments"][tid] = t
        _save_json(TOURNAMENT_FILE, data)
        return t


def join_tournament(tid: str, user_id: str, display_name: str = "") -> dict:
    with _lock:
        data = _load_json(TOURNAMENT_FILE, {"tournaments": {}})
        t = data["tournaments"].get(tid)
        if not t:
            return {"ok": False, "error": "Torneio não encontrado"}
        if t["status"] != "open":
            return {"ok": False, "error": "Inscrições fechadas"}
        if any(p["user_id"] == user_id for p in t["players"]):
            return {"ok": False, "error": "Já inscrito"}
        if len(t["players"]) >= t["max_players"]:
            return {"ok": False, "error": "Torneio cheio"}
        t["players"].append({
            "user_id": user_id,
            "name": (display_name or user_id)[:40],
            "joined_at": _now(),
        })
        # auto-start se lotou
        if len(t["players"]) >= t["max_players"]:
            t["status"] = "running"
            t["bracket"] = _build_bracket(t["players"])
        _save_json(TOURNAMENT_FILE, data)
        return {"ok": True, "tournament": t}


def _build_bracket(players: list) -> list:
    """Chaveamento eliminação simples. Bye se número ímpar de slots."""
    import random
    pl = list(players)
    random.shuffle(pl)
    size = 1
    while size < len(pl):
        size *= 2
    # preenche byes
    while len(pl) < size:
        pl.append({"user_id": None, "name": "BYE", "joined_at": None})
    rounds = []
    current = pl
    r = 1
    while len(current) >= 2:
        matches = []
        next_round = []
        for i in range(0, len(current), 2):
            a, b = current[i], current[i + 1]
            mid = f"m{r}_{i//2}"
            winner = None
            if a.get("user_id") is None:
                winner = b
            elif b.get("user_id") is None:
                winner = a
            match = {
                "id": mid,
                "round": r,
                "p1": a,
                "p2": b,
                "score1": None,
                "score2": None,
                "winner": winner["user_id"] if winner else None,
            }
            matches.append(match)
            next_round.append(winner if winner else {"user_id": f"pending_{mid}", "name": "A definir"})
        rounds.append(matches)
        current = next_round
        r += 1
    return rounds


def report_match_result(tid: str, match_id: str, score1: int, score2: int) -> dict:
    with _lock:
        data = _load_json(TOURNAMENT_FILE, {"tournaments": {}})
        t = data["tournaments"].get(tid)
        if not t or t["status"] != "running":
            return {"ok": False, "error": "Torneio inválido"}
        for rnd in t.get("bracket", []):
            for m in rnd:
                if m["id"] == match_id:
                    m["score1"] = int(score1)
                    m["score2"] = int(score2)
                    if score1 > score2:
                        m["winner"] = m["p1"].get("user_id")
                    elif score2 > score1:
                        m["winner"] = m["p2"].get("user_id")
                    else:
                        return {"ok": False, "error": "Empate não permitido em eliminação"}
                    # propaga vencedor se possível (simplificado: marca final)
                    _save_json(TOURNAMENT_FILE, data)
                    # checa se é a final
                    last = t["bracket"][-1][0] if t["bracket"] else None
                    if last and last.get("winner"):
                        t["status"] = "finished"
                        t["winner"] = last["winner"]
                        _save_json(TOURNAMENT_FILE, data)
                    return {"ok": True, "match": m, "tournament_status": t["status"]}
        return {"ok": False, "error": "Partida não encontrada"}


def list_tournaments(limit: int = 20) -> list:
    with _lock:
        data = _load_json(TOURNAMENT_FILE, {"tournaments": {}})
        items = sorted(data.get("tournaments", {}).values(), key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]


def get_tournament(tid: str) -> dict | None:
    with _lock:
        data = _load_json(TOURNAMENT_FILE, {"tournaments": {}})
        return data.get("tournaments", {}).get(tid)


# --- Replay ---

def save_replay(user_id: str, game_id: str, frames: list, meta: dict | None = None) -> dict:
    """Salva sequência de inputs/frames para reassistir."""
    with _lock:
        data = _load_json(REPLAY_FILE, {"replays": {}})
        rid = "rp_" + secrets.token_hex(6)
        # limita tamanho
        safe_frames = frames[:5000] if isinstance(frames, list) else []
        rec = {
            "id": rid,
            "user_id": user_id,
            "game_id": game_id,
            "frames": safe_frames,
            "meta": meta or {},
            "frame_count": len(safe_frames),
            "created_at": _now(),
        }
        data["replays"][rid] = rec
        # mantém só últimos 100
        if len(data["replays"]) > 100:
            oldest = sorted(data["replays"].values(), key=lambda x: x["created_at"])[: len(data["replays"]) - 100]
            for o in oldest:
                data["replays"].pop(o["id"], None)
        _save_json(REPLAY_FILE, data)
        return {"ok": True, "id": rid, "frame_count": len(safe_frames)}


def get_replay(rid: str) -> dict | None:
    with _lock:
        data = _load_json(REPLAY_FILE, {"replays": {}})
        return data.get("replays", {}).get(rid)


def list_replays(user_id: str | None = None, limit: int = 20) -> list:
    with _lock:
        data = _load_json(REPLAY_FILE, {"replays": {}})
        items = list(data.get("replays", {}).values())
        if user_id:
            items = [x for x in items if x.get("user_id") == user_id]
        items = sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)
        # sem frames na listagem
        return [{k: v for k, v in x.items() if k != "frames"} for x in items[:limit]]


# ===========================================================================
# 2. PROGRAMAÇÃO — Code review IA, performance, pair programming, snippets+dbg
# ===========================================================================

PERF_CHALLENGES = [
    {
        "id": "sum_slow",
        "title": "Soma lenta",
        "description": "Otimize a função que soma números de 1 a N (evite loop puro se possível).",
        "starter": "def sum_to_n(n):\n    total = 0\n    for i in range(1, n+1):\n        total += i\n    return total\n",
        "hint": "Fórmula fechada: n*(n+1)//2",
        "target": "O(1) ou O(log n)",
    },
    {
        "id": "find_dup",
        "title": "Encontrar duplicata",
        "description": "Dado array com n+1 elementos em 1..n, encontre o duplicado em tempo linear e espaço O(1) se possível.",
        "starter": "def find_duplicate(nums):\n    # implemente\n    seen = set()\n    for x in nums:\n        if x in seen:\n            return x\n        seen.add(x)\n    return -1\n",
        "hint": "Floyd cycle / tortoise-hare",
        "target": "O(n) tempo, O(1) espaço extra",
    },
    {
        "id": "str_build",
        "title": "Concatenação de strings",
        "description": "Evite concatenação em loop que gera muitas cópias intermediárias.",
        "starter": "def build_string(parts):\n    s = ''\n    for p in parts:\n        s = s + p\n    return s\n",
        "hint": "''.join(parts)",
        "target": "Uso de join ou buffer",
    },
]


def list_perf_challenges() -> list:
    return PERF_CHALLENGES


def get_perf_challenge(cid: str) -> dict | None:
    for c in PERF_CHALLENGES:
        if c["id"] == cid:
            return c
    return None


def code_review_ai_prompt(code: str, language: str = "python") -> dict:
    """Gera prompt estruturado para code review por IA (sugestões, não só certo/errado)."""
    code = (code or "")[:8000]
    prompt = f"""Você é um revisor de código experiente e didático.
Analise o código {language} abaixo e responda em português, em markdown:

1. **Resumo** (1-2 frases)
2. **Pontos fortes**
3. **Problemas / cheiros de código** (bugs potenciais, legibilidade, segurança)
4. **Sugestões de melhoria** (concretas, com trechos de código quando útil)
5. **Possíveis otimizações** (complexidade, memória)
6. **Nota geral** de 1 a 10 e o porquê

NÃO reescreva o código inteiro a menos que seja muito curto. Foque em feedback acionável.

```{language}
{code}
```
"""
    return {
        "ok": True,
        "prompt": prompt,
        "system": "Você é um senior engineer que faz code review construtivo e educativo.",
        "language": language,
        "code_length": len(code),
    }


def pair_programming_prompt(code: str, goal: str, language: str = "python") -> dict:
    """Modo pair programming: IA sugere o próximo passo SEM dar a resposta pronta."""
    code = (code or "")[:6000]
    goal = (goal or "continuar a implementação")[:300]
    prompt = f"""Você é um pair programmer paciente (estilo mentor Socrático).
O aluno está programando em {language}. Objetivo: {goal}

Código atual:
```{language}
{code}
```

Regras:
- NÃO entregue a solução completa.
- Sugira APENAS o próximo passo pequeno e claro (1-3 frases).
- Faça no máximo 1 pergunta de reflexão se ajudar.
- Se o código estiver errado, aponte a região do problema sem corrigir tudo.
- Responda em português, tom encorajador.
"""
    return {
        "ok": True,
        "prompt": prompt,
        "system": "Pair programming mentor. Nunca entregue a resposta pronta; guie passo a passo.",
        "goal": goal,
    }


def snippet_open_in_debugger(snippet_id: str, code: str | None = None) -> dict:
    """Integra snippet com debugger visual: prepara sessão pronta para abrir."""
    # O debugger real vive em debugger_service / nl9; aqui só empacota o payload.
    session = {
        "id": "dbg_" + secrets.token_hex(4),
        "snippet_id": snippet_id,
        "code": code or "",
        "language": "python",
        "breakpoints": [0],
        "ready": True,
        "hint": "Abra /api/nl9/debugger/start com este code ou use o painel do Nível 9.",
        "created_at": _now(),
    }
    return {"ok": True, "debugger_session": session}


# ===========================================================================
# 3. GAMIFICAÇÃO — Clãs, conquistas secretas, loja rotativa
# ===========================================================================

CLANS_FILE = NL_DIR / "clans.json"
SECRETS_FILE = NL_DIR / "secret_achievements.json"
ROTATING_SHOP_FILE = NL_DIR / "rotating_shop.json"

SECRET_ACHIEVEMENTS = [
    {
        "id": "night_owl",
        "name": "Coruja Noturna",
        "description": "Completou uma trilha entre 00h e 05h",
        "icon": "🦉",
        "hidden": True,
        "condition": "activity_hour_0_5",
    },
    {
        "id": "first_blood",
        "name": "First Blood",
        "description": "Primeiro a completar um desafio novo na semana",
        "icon": "⚔️",
        "hidden": True,
        "condition": "first_challenge_week",
    },
    {
        "id": "helper_100",
        "name": "Mentor Sombra",
        "description": "100 respostas úteis no fórum (sem mostrar progresso)",
        "icon": "🎭",
        "hidden": True,
        "condition": "forum_helps_100",
    },
    {
        "id": "perfect_week",
        "name": "Semana Perfeita",
        "description": "7 dias de streak com pelo menos 1 desafio/dia",
        "icon": "💎",
        "hidden": True,
        "condition": "streak_7_challenges",
    },
    {
        "id": "code_golf",
        "name": "Code Golf",
        "description": "Resolveu desafio de performance com solução < 5 linhas",
        "icon": "⛳",
        "hidden": True,
        "condition": "perf_under_5_lines",
    },
]


def create_clan(owner: str, name: str, tag: str = "") -> dict:
    with _lock:
        data = _load_json(CLANS_FILE, {"clans": {}})
        cid = "clan_" + secrets.token_hex(4)
        clan = {
            "id": cid,
            "name": (name or "Clã")[:40],
            "tag": (tag or name[:4].upper())[:6],
            "owner": owner,
            "members": [owner],
            "xp_total": 0,
            "created_at": _now(),
        }
        data["clans"][cid] = clan
        _save_json(CLANS_FILE, data)
        return clan


def join_clan(cid: str, user_id: str) -> dict:
    with _lock:
        data = _load_json(CLANS_FILE, {"clans": {}})
        clan = data["clans"].get(cid)
        if not clan:
            return {"ok": False, "error": "Clã não encontrado"}
        if user_id in clan["members"]:
            return {"ok": False, "error": "Já é membro"}
        if len(clan["members"]) >= 50:
            return {"ok": False, "error": "Clã cheio"}
        clan["members"].append(user_id)
        _save_json(CLANS_FILE, data)
        return {"ok": True, "clan": clan}


def add_clan_xp(cid: str, amount: int) -> dict:
    with _lock:
        data = _load_json(CLANS_FILE, {"clans": {}})
        clan = data["clans"].get(cid)
        if not clan:
            return {"ok": False, "error": "Clã não encontrado"}
        clan["xp_total"] = int(clan.get("xp_total", 0)) + max(0, int(amount))
        _save_json(CLANS_FILE, data)
        return {"ok": True, "xp_total": clan["xp_total"]}


def list_clans(limit: int = 30) -> list:
    with _lock:
        data = _load_json(CLANS_FILE, {"clans": {}})
        items = sorted(data.get("clans", {}).values(), key=lambda x: x.get("xp_total", 0), reverse=True)
        return items[:limit]


def clan_ranking() -> list:
    return list_clans(50)


def list_secret_achievements(unlocked_ids: list | None = None) -> list:
    unlocked = set(unlocked_ids or [])
    out = []
    for a in SECRET_ACHIEVEMENTS:
        if a["id"] in unlocked:
            out.append({**a, "unlocked": True, "hidden": False})
        else:
            out.append({
                "id": a["id"],
                "name": "???",
                "description": "Conquista secreta — descubra jogando",
                "icon": "❓",
                "hidden": True,
                "unlocked": False,
            })
    return out


def unlock_secret(user_id: str, achievement_id: str) -> dict:
    with _lock:
        data = _load_json(SECRETS_FILE, {"users": {}})
        u = data.setdefault("users", {}).setdefault(user_id, {"unlocked": []})
        if achievement_id not in u["unlocked"]:
            # valida se existe
            if not any(a["id"] == achievement_id for a in SECRET_ACHIEVEMENTS):
                return {"ok": False, "error": "Conquista inválida"}
            u["unlocked"].append(achievement_id)
            u["last_unlock"] = _now()
            _save_json(SECRETS_FILE, data)
            real = next(a for a in SECRET_ACHIEVEMENTS if a["id"] == achievement_id)
            return {"ok": True, "achievement": real, "newly": True}
        return {"ok": True, "newly": False}


def get_user_secrets(user_id: str) -> list:
    with _lock:
        data = _load_json(SECRETS_FILE, {"users": {}})
        unlocked = data.get("users", {}).get(user_id, {}).get("unlocked", [])
        return list_secret_achievements(unlocked)


# Loja rotativa — 3 itens especiais por semana
ROTATING_CATALOG = [
    {"id": "skin_neon", "name": "Skin Neon Cyber", "price_xp": 120, "type": "skin"},
    {"id": "title_architect", "name": "Título: Arquiteto", "price_xp": 200, "type": "title"},
    {"id": "frame_gold", "name": "Moldura Dourada", "price_xp": 150, "type": "frame"},
    {"id": "pet_drone", "name": "Pet Drone", "price_xp": 180, "type": "pet"},
    {"id": "emote_matrix", "name": "Emote Matrix", "price_xp": 80, "type": "emote"},
    {"id": "theme_synthwave", "name": "Tema Synthwave", "price_xp": 100, "type": "theme"},
    {"id": "badge_pioneer", "name": "Badge Pioneiro", "price_xp": 250, "type": "badge"},
    {"id": "trail_fire", "name": "Rastro de Fogo", "price_xp": 90, "type": "trail"},
]


def current_rotating_shop() -> dict:
    """3 itens da semana (determinístico pelo week_id)."""
    wid = _week_id()
    seed = int(hashlib.md5(wid.encode()).hexdigest()[:8], 16)
    idxs = [(seed + i * 7) % len(ROTATING_CATALOG) for i in range(3)]
    # garante únicos
    seen = set()
    items = []
    i = 0
    while len(items) < 3 and i < 20:
        idx = (seed + i * 7) % len(ROTATING_CATALOG)
        if idx not in seen:
            seen.add(idx)
            it = dict(ROTATING_CATALOG[idx])
            it["week"] = wid
            items.append(it)
        i += 1
    return {"week": wid, "items": items, "expires_hint": "Troca toda segunda-feira (UTC)"}


def buy_rotating_item(user_id: str, item_id: str, user_xp: int) -> dict:
    shop = current_rotating_shop()
    item = next((x for x in shop["items"] if x["id"] == item_id), None)
    if not item:
        return {"ok": False, "error": "Item não está na loja desta semana"}
    price = int(item["price_xp"])
    if user_xp < price:
        return {"ok": False, "error": f"XP insuficiente (precisa {price})"}
    with _lock:
        data = _load_json(ROTATING_SHOP_FILE, {"purchases": {}})
        key = f"{user_id}:{shop['week']}:{item_id}"
        if key in data.get("purchases", {}):
            return {"ok": False, "error": "Já comprou este item nesta semana"}
        data.setdefault("purchases", {})[key] = {"at": _now(), "item": item}
        _save_json(ROTATING_SHOP_FILE, data)
    return {"ok": True, "item": item, "new_xp": user_xp - price}


# ===========================================================================
# 4. CERTIFICADOS — verificável por empresa + selos bronze/prata/ouro
# ===========================================================================

CERT_FILE = NL_DIR / "certs_v2.json"


def issue_verifiable_cert(
    user_id: str,
    user_name: str,
    track: str,
    score: float,
    hours: float = 0,
) -> dict:
    """Certificado com link público verificável por RH + selo por desempenho."""
    score = float(score)
    if score >= 90:
        seal = "ouro"
    elif score >= 75:
        seal = "prata"
    elif score >= 60:
        seal = "bronze"
    else:
        seal = "participacao"

    with _lock:
        data = _load_json(CERT_FILE, {"certs": {}})
        token = secrets.token_urlsafe(16)
        cid = "cert_" + secrets.token_hex(6)
        cert = {
            "id": cid,
            "token": token,
            "user_id": user_id,
            "user_name": (user_name or user_id)[:80],
            "track": (track or "Trilha")[:120],
            "score": round(score, 1),
            "seal": seal,
            "hours": round(float(hours), 1),
            "issued_at": _now(),
            "verify_path": f"/api/nl10/cert/verify/{token}",
        }
        data["certs"][cid] = cert
        # índice por token
        data.setdefault("by_token", {})[token] = cid
        _save_json(CERT_FILE, data)
        return cert


def verify_cert(token: str) -> dict:
    with _lock:
        data = _load_json(CERT_FILE, {"certs": {}, "by_token": {}})
        cid = data.get("by_token", {}).get(token)
        if not cid:
            return {"ok": False, "valid": False, "error": "Certificado não encontrado"}
        cert = data.get("certs", {}).get(cid)
        if not cert:
            return {"ok": False, "valid": False, "error": "Certificado inválido"}
        return {
            "ok": True,
            "valid": True,
            "user_name": cert["user_name"],
            "track": cert["track"],
            "score": cert["score"],
            "seal": cert["seal"],
            "hours": cert.get("hours"),
            "issued_at": cert["issued_at"],
            "message": f"Certificado válido — selo {cert['seal'].upper()}",
        }


def list_user_certs(user_id: str) -> list:
    with _lock:
        data = _load_json(CERT_FILE, {"certs": {}})
        return [c for c in data.get("certs", {}).values() if c.get("user_id") == user_id]


# ===========================================================================
# 5. ESTUDOS — busca unificada, offline pack, resumo semanal
# ===========================================================================

STUDY_INDEX_FILE = NL_DIR / "study_index.json"
OFFLINE_FILE = NL_DIR / "offline_packs.json"
WEEKLY_FILE = NL_DIR / "weekly_summaries.json"


def unified_search(query: str, limit: int = 20) -> dict:
    """Busca simples em índice local (PDFs, vídeos, exercícios, fórum)."""
    q = (query or "").strip().lower()
    if not q:
        return {"ok": True, "results": []}
    with _lock:
        index = _load_json(STUDY_INDEX_FILE, {"items": []})
        # seed mínimo se vazio
        if not index.get("items"):
            index["items"] = [
                {"id": "pdf1", "type": "pdf", "title": "Introdução a Algoritmos", "tags": ["algoritmos", "pdf"], "body": "complexidade big o ordenação"},
                {"id": "vid1", "type": "video", "title": "Loops em Python", "tags": ["python", "video"], "body": "for while range"},
                {"id": "ex1", "type": "exercise", "title": "Desafio soma", "tags": ["exercício"], "body": "implemente soma de lista"},
                {"id": "forum1", "type": "forum", "title": "Dúvida sobre listas", "tags": ["fórum"], "body": "como remover duplicatas"},
            ]
            _save_json(STUDY_INDEX_FILE, index)
        results = []
        for it in index["items"]:
            hay = " ".join([
                str(it.get("title", "")),
                str(it.get("body", "")),
                " ".join(it.get("tags", [])),
            ]).lower()
            if q in hay:
                results.append({
                    "id": it["id"],
                    "type": it.get("type"),
                    "title": it.get("title"),
                    "tags": it.get("tags", []),
                })
            if len(results) >= limit:
                break
        return {"ok": True, "query": query, "results": results}


def create_offline_pack(user_id: str, track_id: str, items: list) -> dict:
    """Gera pacote para baixar e estudar sem internet."""
    with _lock:
        data = _load_json(OFFLINE_FILE, {"packs": {}})
        pid = "off_" + secrets.token_hex(5)
        pack = {
            "id": pid,
            "user_id": user_id,
            "track_id": track_id,
            "items": items[:50] if isinstance(items, list) else [],
            "created_at": _now(),
            "size_hint": f"{len(items) if isinstance(items, list) else 0} itens",
        }
        data["packs"][pid] = pack
        _save_json(OFFLINE_FILE, data)
        return {"ok": True, "pack": pack}


def weekly_summary(user_id: str, learned: list | None = None) -> dict:
    """Resumo semanal do que o usuário aprendeu (para e-mail/notificação)."""
    wid = _week_id()
    with _lock:
        data = _load_json(WEEKLY_FILE, {"summaries": {}})
        key = f"{user_id}:{wid}"
        entry = data.get("summaries", {}).get(key) or {
            "user_id": user_id,
            "week": wid,
            "topics": [],
            "challenges_done": 0,
            "minutes": 0,
            "highlights": [],
        }
        if learned:
            for t in learned[:20]:
                if t and t not in entry["topics"]:
                    entry["topics"].append(str(t)[:80])
            entry["challenges_done"] = entry.get("challenges_done", 0) + len(learned)
        entry["updated_at"] = _now()
        # gera texto
        topics = ", ".join(entry["topics"][-8:]) or "nenhum tópico registrado ainda"
        text = (
            f"📅 Resumo da semana {wid}\n"
            f"Você avançou em: {topics}.\n"
            f"Desafios/atividades: {entry.get('challenges_done', 0)}.\n"
            f"Continue o streak! — JARVIS"
        )
        entry["text"] = text
        data.setdefault("summaries", {})[key] = entry
        _save_json(WEEKLY_FILE, data)
        return {"ok": True, "summary": entry}


# ===========================================================================
# 6. COMUNIDADE — mentoria, feed, badges de contribuição
# ===========================================================================

MENTOR_FILE = NL_DIR / "mentorship.json"
FEED_FILE = NL_DIR / "activity_feed.json"
BADGES_FILE = NL_DIR / "contribution_badges.json"

CONTRIB_BADGES = [
    {"id": "helper_10", "name": "Ajudante", "min_helps": 10, "icon": "🤝"},
    {"id": "helper_50", "name": "Mentor Ativo", "min_helps": 50, "icon": "🌟"},
    {"id": "helper_100", "name": "Lenda do Fórum", "min_helps": 100, "icon": "🏆"},
]


def request_mentor(beginner_id: str, topic: str) -> dict:
    with _lock:
        data = _load_json(MENTOR_FILE, {"requests": [], "pairs": []})
        req = {
            "id": "mr_" + secrets.token_hex(4),
            "beginner_id": beginner_id,
            "topic": (topic or "geral")[:80],
            "status": "open",
            "created_at": _now(),
        }
        data.setdefault("requests", []).append(req)
        data["requests"] = data["requests"][-100:]
        _save_json(MENTOR_FILE, data)
        return {"ok": True, "request": req}


def accept_mentor(request_id: str, mentor_id: str) -> dict:
    with _lock:
        data = _load_json(MENTOR_FILE, {"requests": [], "pairs": []})
        req = next((r for r in data.get("requests", []) if r["id"] == request_id and r["status"] == "open"), None)
        if not req:
            return {"ok": False, "error": "Pedido não encontrado"}
        req["status"] = "matched"
        req["mentor_id"] = mentor_id
        pair = {
            "id": "pair_" + secrets.token_hex(4),
            "mentor_id": mentor_id,
            "beginner_id": req["beginner_id"],
            "topic": req["topic"],
            "created_at": _now(),
            "channel_hint": "Use o fórum ou chat dedicado da plataforma",
        }
        data.setdefault("pairs", []).append(pair)
        _save_json(MENTOR_FILE, data)
        return {"ok": True, "pair": pair}


def list_mentor_requests(limit: int = 20) -> list:
    with _lock:
        data = _load_json(MENTOR_FILE, {"requests": []})
        open_reqs = [r for r in data.get("requests", []) if r.get("status") == "open"]
        return open_reqs[-limit:]


def post_activity(user_id: str, text: str, kind: str = "general") -> dict:
    with _lock:
        data = _load_json(FEED_FILE, {"items": []})
        item = {
            "id": "act_" + secrets.token_hex(4),
            "user_id": user_id,
            "kind": kind,
            "text": (text or "")[:200],
            "at": _now(),
        }
        data.setdefault("items", []).append(item)
        data["items"] = data["items"][-200:]
        _save_json(FEED_FILE, data)
        return {"ok": True, "item": item}


def activity_feed(limit: int = 30) -> list:
    with _lock:
        data = _load_json(FEED_FILE, {"items": []})
        items = data.get("items", [])
        return list(reversed(items[-limit:]))


def record_help(user_id: str) -> dict:
    """Incrementa contador de contribuições e concede badges."""
    with _lock:
        data = _load_json(BADGES_FILE, {"users": {}})
        u = data.setdefault("users", {}).setdefault(user_id, {"helps": 0, "badges": []})
        u["helps"] = int(u.get("helps", 0)) + 1
        new_badges = []
        for b in CONTRIB_BADGES:
            if u["helps"] >= b["min_helps"] and b["id"] not in u.get("badges", []):
                u.setdefault("badges", []).append(b["id"])
                new_badges.append(b)
        _save_json(BADGES_FILE, data)
        return {"ok": True, "helps": u["helps"], "badges": u["badges"], "new_badges": new_badges}


def get_contribution(user_id: str) -> dict:
    with _lock:
        data = _load_json(BADGES_FILE, {"users": {}})
        u = data.get("users", {}).get(user_id, {"helps": 0, "badges": []})
        badge_details = [b for b in CONTRIB_BADGES if b["id"] in u.get("badges", [])]
        return {"helps": u.get("helps", 0), "badges": badge_details}


# ===========================================================================
# 7. QUALIDADE / INFRA — status, error log, smoke tests
# ===========================================================================

ERROR_LOG_FILE = NL_DIR / "error_log.json"
STATUS_CHECKS = [
    {"id": "api", "name": "API core", "ok": True},
    {"id": "auth", "name": "Auth", "ok": True},
    {"id": "data", "name": "Data dir", "ok": True},
    {"id": "ai", "name": "AI engine", "ok": True},
]


def log_error(source: str, message: str, detail: str = "") -> dict:
    with _lock:
        data = _load_json(ERROR_LOG_FILE, {"errors": []})
        entry = {
            "id": "err_" + secrets.token_hex(4),
            "source": (source or "app")[:60],
            "message": (message or "")[:300],
            "detail": (detail or "")[:1000],
            "at": _now(),
        }
        data.setdefault("errors", []).append(entry)
        data["errors"] = data["errors"][-200:]
        _save_json(ERROR_LOG_FILE, data)
        return entry


def recent_errors(limit: int = 30) -> list:
    with _lock:
        data = _load_json(ERROR_LOG_FILE, {"errors": []})
        return list(reversed(data.get("errors", [])[-limit:]))


def status_page() -> dict:
    """Página de status simples (/status style)."""
    checks = []
    overall = True
    # data dir
    data_ok = DATA_DIR.exists() and DATA_DIR.is_dir()
    checks.append({"id": "data", "name": "Data directory", "ok": data_ok})
    overall = overall and data_ok
    # nl10 dir
    nl_ok = NL_DIR.exists()
    checks.append({"id": "nl10", "name": "Next Level 10 storage", "ok": nl_ok})
    overall = overall and nl_ok
    # write test
    try:
        test_p = NL_DIR / ".healthwrite"
        test_p.write_text("ok", encoding="utf-8")
        write_ok = test_p.read_text(encoding="utf-8") == "ok"
        test_p.unlink(missing_ok=True)
    except Exception:
        write_ok = False
    checks.append({"id": "write", "name": "Disk write", "ok": write_ok})
    overall = overall and write_ok
    checks.append({"id": "api", "name": "API process", "ok": True})
    return {
        "status": "operational" if overall else "degraded",
        "checks": checks,
        "checked_at": _now(),
    }


def run_smoke_tests() -> dict:
    """Testes automáticos leves antes de deploy (CI simples)."""
    results = []
    # 1 physics templates
    results.append({"name": "physics_templates", "ok": len(PHYSICS_TEMPLATES) >= 3})
    # 2 create/list marketplace structure
    try:
        marketplace_list(1)
        results.append({"name": "marketplace_io", "ok": True})
    except Exception as e:
        results.append({"name": "marketplace_io", "ok": False, "error": str(e)})
    # 3 secrets list
    results.append({"name": "secret_achievements", "ok": len(SECRET_ACHIEVEMENTS) >= 3})
    # 4 rotating shop
    shop = current_rotating_shop()
    results.append({"name": "rotating_shop", "ok": len(shop.get("items", [])) == 3})
    # 5 cert verify missing
    v = verify_cert("invalid_token_xyz")
    results.append({"name": "cert_verify_negative", "ok": v.get("valid") is False})
    # 6 status
    st = status_page()
    results.append({"name": "status_page", "ok": st.get("status") in ("operational", "degraded")})
    passed = sum(1 for r in results if r.get("ok"))
    return {
        "ok": passed == len(results),
        "passed": passed,
        "total": len(results),
        "results": results,
        "at": _now(),
    }


# ===========================================================================
# Overview
# ===========================================================================

def next_level10_overview(user_id: str) -> dict:
    return {
        "physics_templates": len(PHYSICS_TEMPLATES),
        "marketplace_count": len(marketplace_list(5)),
        "tournaments_open": sum(1 for t in list_tournaments(50) if t.get("status") == "open"),
        "rotating_shop": current_rotating_shop(),
        "secrets": get_user_secrets(user_id),
        "clans_top": list_clans(5),
        "contribution": get_contribution(user_id),
        "status": status_page().get("status"),
        "features": [
            "marketplace", "tournament", "replay", "physics_templates",
            "code_review_ai", "perf_challenges", "pair_programming", "snippet_debugger",
            "clans", "secret_achievements", "rotating_shop",
            "verifiable_cert", "performance_seals",
            "unified_search", "offline_pack", "weekly_summary",
            "mentorship", "activity_feed", "contribution_badges",
            "status_page", "error_log", "smoke_tests",
        ],
    }
