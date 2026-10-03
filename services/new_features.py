"""JARVIS New Features Hub v2 — expansão máxima.

Templates, ranking, assets, flashcards (SM-2), study tools, profile, sprite editor data,
quiz scoring, streaks, guided projects, site scaffolds, sound bank, mindmap nodes.
"""
from __future__ import annotations

import json
import re
import time
import uuid
import hashlib
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GAMES_DIR = DATA / "games"
RANK_DIR = DATA / "rankings"
ASSETS_DIR = DATA / "assets"
FLASH_DIR = DATA / "flashcards"
STUDY_DIR = DATA / "study"
SPRITES_DIR = DATA / "sprites"
PROGRESS_FILE = DATA / "user_progress.json"

for d in (RANK_DIR, ASSETS_DIR, FLASH_DIR, STUDY_DIR, SPRITES_DIR, GAMES_DIR / "public"):
    d.mkdir(parents=True, exist_ok=True)

# ===========================================================================
# 1. Game templates (expanded)
# ===========================================================================
GAME_TEMPLATES = [
    {"id": "tpl_platform_forest", "name": "Plataforma na Floresta", "type": "platform", "scenario": "forest", "hero": "hero", "item": "coin", "monster": "slime", "difficulty": "easy",
     "description": "Pule plataformas, colete moedas e chegue à bandeira.", "tags": ["plataforma", "fácil", "criança"]},
    {"id": "tpl_race_city", "name": "Corrida Urbana", "type": "race", "scenario": "city", "hero": "robot", "item": "star", "monster": "none", "difficulty": "normal",
     "description": "Corra pela cidade coletando estrelas.", "tags": ["corrida", "velocidade"]},
    {"id": "tpl_quiz_space", "name": "Coleta Espacial", "type": "collect", "scenario": "space", "hero": "alien", "item": "gem", "monster": "robot_enemy", "difficulty": "normal",
     "description": "Colete gemas no espaço e fuja dos robôs.", "tags": ["coleta", "espaço"]},
    {"id": "tpl_puzzle_castle", "name": "Labirinto do Castelo", "type": "maze", "scenario": "castle", "hero": "wizard", "item": "key", "monster": "ghost", "difficulty": "hard",
     "description": "Encontre a saída do labirinto com o mago.", "tags": ["puzzle", "labirinto"]},
    {"id": "tpl_tower_volcano", "name": "Defesa no Vulcão", "type": "shooter", "scenario": "volcano", "hero": "knight", "item": "heart", "monster": "dragon", "difficulty": "hard",
     "description": "Defenda a torre atirando nos dragões.", "tags": ["tiro", "tower"]},
    {"id": "tpl_escape_ocean", "name": "Fuga no Oceano", "type": "escape", "scenario": "ocean", "hero": "cat", "item": "candy", "monster": "bat", "difficulty": "easy",
     "description": "Fuja dos morcegos até o portal.", "tags": ["fuga", "fácil"]},
    {"id": "tpl_platform_snow", "name": "Aventura na Neve", "type": "platform", "scenario": "snow", "hero": "ninja", "item": "star", "monster": "slime", "difficulty": "normal",
     "description": "Ninja na neve: pule e colete estrelas.", "tags": ["plataforma", "neve"]},
    {"id": "tpl_maze_desert", "name": "Labirinto do Deserto", "type": "maze", "scenario": "desert", "hero": "dog", "item": "gem", "monster": "none", "difficulty": "easy",
     "description": "Encontre a saída no deserto sem monstros.", "tags": ["labirinto", "fácil"]},
    {"id": "tpl_shooter_space", "name": "Tiro Espacial", "type": "shooter", "scenario": "space", "hero": "robot", "item": "coin", "monster": "robot_enemy", "difficulty": "normal",
     "description": "Atire nos inimigos no espaço.", "tags": ["tiro", "espaço"]},
    {"id": "tpl_collect_forest", "name": "Caça ao Tesouro", "type": "collect", "scenario": "forest", "hero": "knight", "item": "key", "monster": "ghost", "difficulty": "hard",
     "description": "Colete todas as chaves na floresta.", "tags": ["coleta", "tesouro"]},
]


def list_game_templates(tag: str | None = None) -> list[dict[str, Any]]:
    if tag:
        t = tag.lower()
        return [x for x in GAME_TEMPLATES if t in (x.get("tags") or []) or t in x.get("type", "") or t in x.get("name", "").lower()]
    return GAME_TEMPLATES


def get_template(tpl_id: str) -> dict[str, Any] | None:
    for t in GAME_TEMPLATES:
        if t["id"] == tpl_id:
            return t
    return None


# ===========================================================================
# 2. Asset store
# ===========================================================================
ASSET_CATALOG = [
    {"id": "char_hero", "name": "Herói", "category": "personagens", "emoji": "🦸", "color": "#3b82f6", "tags": ["herói"]},
    {"id": "char_ninja", "name": "Ninja", "category": "personagens", "emoji": "🥷", "color": "#1e293b", "tags": ["ninja"]},
    {"id": "char_robot", "name": "Robô", "category": "personagens", "emoji": "🤖", "color": "#94a3b8", "tags": ["robô"]},
    {"id": "char_wizard", "name": "Mago", "category": "personagens", "emoji": "🧙", "color": "#8b5cf6", "tags": ["mago"]},
    {"id": "char_knight", "name": "Cavaleiro", "category": "personagens", "emoji": "⚔️", "color": "#f59e0b", "tags": ["cavaleiro"]},
    {"id": "char_alien", "name": "Alienígena", "category": "personagens", "emoji": "👽", "color": "#22c55e", "tags": ["alien"]},
    {"id": "char_cat", "name": "Gato", "category": "personagens", "emoji": "🐱", "color": "#f97316", "tags": ["gato"]},
    {"id": "char_dog", "name": "Cachorro", "category": "personagens", "emoji": "🐶", "color": "#a16207", "tags": ["cão"]},
    {"id": "scene_forest", "name": "Floresta", "category": "cenários", "emoji": "🌲", "color": "#0d2818", "tags": ["floresta"]},
    {"id": "scene_space", "name": "Espaço", "category": "cenários", "emoji": "🚀", "color": "#0a0a1a", "tags": ["espaço"]},
    {"id": "scene_castle", "name": "Castelo", "category": "cenários", "emoji": "🏰", "color": "#1a1220", "tags": ["castelo"]},
    {"id": "scene_ocean", "name": "Oceano", "category": "cenários", "emoji": "🌊", "color": "#0a1e2e", "tags": ["oceano"]},
    {"id": "scene_city", "name": "Cidade", "category": "cenários", "emoji": "🏙️", "color": "#121820", "tags": ["cidade"]},
    {"id": "scene_desert", "name": "Deserto", "category": "cenários", "emoji": "🏜️", "color": "#2a2210", "tags": ["deserto"]},
    {"id": "scene_snow", "name": "Neve", "category": "cenários", "emoji": "❄️", "color": "#1a2430", "tags": ["neve"]},
    {"id": "scene_volcano", "name": "Vulcão", "category": "cenários", "emoji": "🌋", "color": "#2a1010", "tags": ["vulcão"]},
    {"id": "item_coin", "name": "Moeda", "category": "itens", "emoji": "🪙", "color": "#eab308", "tags": ["moeda"]},
    {"id": "item_gem", "name": "Gema", "category": "itens", "emoji": "💎", "color": "#06b6d4", "tags": ["gema"]},
    {"id": "item_star", "name": "Estrela", "category": "itens", "emoji": "⭐", "color": "#fbbf24", "tags": ["estrela"]},
    {"id": "item_key", "name": "Chave", "category": "itens", "emoji": "🔑", "color": "#f59e0b", "tags": ["chave"]},
    {"id": "item_heart", "name": "Coração", "category": "itens", "emoji": "❤️", "color": "#ef4444", "tags": ["vida"]},
    {"id": "sfx_jump", "name": "Pulo", "category": "sons", "emoji": "🔊", "color": "#6366f1", "tags": ["pulo"]},
    {"id": "sfx_coin", "name": "Coleta", "category": "sons", "emoji": "🔔", "color": "#eab308", "tags": ["coleta"]},
    {"id": "sfx_win", "name": "Vitória", "category": "sons", "emoji": "🏆", "color": "#22c55e", "tags": ["vitória"]},
    {"id": "sfx_hit", "name": "Colisão", "category": "sons", "emoji": "💥", "color": "#ef4444", "tags": ["dano"]},
]


def list_assets(category: str | None = None) -> list[dict[str, Any]]:
    if category:
        return [a for a in ASSET_CATALOG if a["category"] == category]
    return ASSET_CATALOG


# ===========================================================================
# 3. Ranking
# ===========================================================================
def _rank_path(game_id: str) -> Path:
    safe = re.sub(r"[^\w\-]", "_", str(game_id))[:80]
    return RANK_DIR / f"{safe}.json"


def submit_score(game_id: str, user_id: str, username: str, score: int, meta: dict | None = None) -> dict[str, Any]:
    path = _rank_path(game_id)
    data = {"game_id": game_id, "entries": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    entry = {
        "id": str(uuid.uuid4())[:8],
        "user_id": user_id or "guest",
        "username": (username or "Anônimo")[:40],
        "score": int(score),
        "at": int(time.time()),
        "meta": meta or {},
    }
    data["entries"].append(entry)
    data["entries"] = sorted(data["entries"], key=lambda e: e["score"], reverse=True)[:100]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    rank = next((i + 1 for i, e in enumerate(data["entries"]) if e["id"] == entry["id"]), None)
    add_xp(user_id, min(50, max(5, int(score) // 10)), "game_played")
    return {"ok": True, "rank": rank, "top": data["entries"][:10]}


def get_ranking(game_id: str, limit: int = 20) -> list[dict[str, Any]]:
    path = _rank_path(game_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("entries", [])[:limit]
    except Exception:
        return []


def get_global_rankings(limit: int = 30) -> list[dict[str, Any]]:
    all_entries = []
    for f in RANK_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for e in data.get("entries", [])[:5]:
                e = dict(e)
                e["game_id"] = data.get("game_id", f.stem)
                all_entries.append(e)
        except Exception:
            continue
    return sorted(all_entries, key=lambda e: e.get("score", 0), reverse=True)[:limit]


# ===========================================================================
# 4. Public share
# ===========================================================================
def make_public_share(user_id: str, game_id: str) -> dict[str, Any]:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    path = GAMES_DIR / uid / f"{game_id}.json"
    if not path.exists():
        return {"ok": False, "error": "Jogo não encontrado. Salve o jogo primeiro no Criador."}
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "Arquivo inválido"}
    token = hashlib.sha256(f"{user_id}:{game_id}:{time.time()}".encode()).hexdigest()[:16]
    pub = GAMES_DIR / "public" / f"{token}.json"
    spec["public_token"] = token
    spec["shared_at"] = int(time.time())
    pub.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "token": token, "url": f"/jogar/publico/{token}"}


def load_public_game(token: str) -> dict[str, Any] | None:
    safe = re.sub(r"[^a-f0-9]", "", token)[:16]
    path = GAMES_DIR / "public" / f"{safe}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ===========================================================================
# 5. Flashcards SM-2
# ===========================================================================
def _flash_path(user_id: str) -> Path:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    return FLASH_DIR / f"{uid}.json"


def list_decks(user_id: str) -> list[dict[str, Any]]:
    path = _flash_path(user_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        return [{
            "id": d["id"], "name": d["name"], "count": len(d.get("cards", [])),
            "due": sum(1 for c in d.get("cards", []) if c.get("next_review", 0) <= now),
        } for d in data.get("decks", [])]
    except Exception:
        return []


def create_deck(user_id: str, name: str) -> dict[str, Any]:
    path = _flash_path(user_id)
    data = {"decks": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    deck = {"id": str(uuid.uuid4())[:10], "name": (name or "Meu deck")[:80], "cards": [], "created_at": int(time.time())}
    data["decks"].append(deck)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "deck": {"id": deck["id"], "name": deck["name"], "count": 0}}


def add_card(user_id: str, deck_id: str, front: str, back: str) -> dict[str, Any]:
    path = _flash_path(user_id)
    if not path.exists():
        return {"ok": False, "error": "Nenhum deck"}
    data = json.loads(path.read_text(encoding="utf-8"))
    for d in data["decks"]:
        if d["id"] == deck_id:
            card = {
                "id": str(uuid.uuid4())[:8], "front": front[:500], "back": back[:1000],
                "ease": 2.5, "interval": 0, "reps": 0, "next_review": int(time.time()),
            }
            d["cards"].append(card)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "card": card}
    return {"ok": False, "error": "Deck não encontrado"}


def get_due_cards(user_id: str, deck_id: str, limit: int = 20) -> list[dict[str, Any]]:
    path = _flash_path(user_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    now = time.time()
    for d in data["decks"]:
        if d["id"] == deck_id:
            due = [c for c in d["cards"] if c.get("next_review", 0) <= now]
            return due[:limit]
    return []


def get_all_cards(user_id: str, deck_id: str) -> list[dict[str, Any]]:
    path = _flash_path(user_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    for d in data["decks"]:
        if d["id"] == deck_id:
            return d.get("cards", [])
    return []


def review_card(user_id: str, deck_id: str, card_id: str, quality: int) -> dict[str, Any]:
    path = _flash_path(user_id)
    if not path.exists():
        return {"ok": False, "error": "Nenhum deck"}
    data = json.loads(path.read_text(encoding="utf-8"))
    q = max(0, min(5, int(quality)))
    for d in data["decks"]:
        if d["id"] == deck_id:
            for c in d["cards"]:
                if c["id"] == card_id:
                    if q < 3:
                        c["reps"] = 0
                        c["interval"] = 0
                    else:
                        c["reps"] = c.get("reps", 0) + 1
                        if c["reps"] == 1:
                            c["interval"] = 1
                        elif c["reps"] == 2:
                            c["interval"] = 6
                        else:
                            c["interval"] = int(c.get("interval", 1) * c.get("ease", 2.5))
                    c["ease"] = max(1.3, c.get("ease", 2.5) + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
                    c["next_review"] = int(time.time()) + max(0, c["interval"]) * 86400
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    return {"ok": True, "card": c}
    return {"ok": False, "error": "Card não encontrado"}


def import_cards_bulk(user_id: str, deck_id: str, pairs: list) -> dict[str, Any]:
    added = 0
    for p in (pairs or [])[:100]:
        r = add_card(user_id, deck_id, p.get("front", ""), p.get("back", ""))
        if r.get("ok"):
            added += 1
    return {"ok": True, "added": added}


# ===========================================================================
# 6. Quiz
# ===========================================================================
QUIZ_BANKS = {
    "python": [
        ("O que é uma lista em Python?", ["Sequência mutável", "Tipo imutável", "Função embutida", "Módulo"], 0),
        ("Qual palavra-chave define uma função?", ["def", "func", "function", "fn"], 0),
        ("Como comentar uma linha?", ["# comentário", "// comentário", "/* */", "-- comentário"], 0),
        ("O que range(3) gera?", ["0,1,2", "1,2,3", "0,1,2,3", "3,2,1"], 0),
        ("Qual método adiciona item ao final da lista?", ["append", "add", "push", "insert"], 0),
        ("O que é um dicionário?", ["Pares chave-valor", "Lista ordenada", "Conjunto", "Tupla"], 0),
        ("Como tratar exceção?", ["try/except", "catch/throw", "if/error", "handle"], 0),
        ("f-strings usam qual sintaxe?", ['f"texto {var}"', '"texto %s"', "format()", "template()"], 0),
    ],
    "javascript": [
        ("Como declarar variável (moderna)?", ["let/const", "var only", "dim", "int"], 0),
        ("=== compara:", ["Valor e tipo", "Só valor", "Só tipo", "Referência"], 0),
        ("Array.push faz o quê?", ["Adiciona no final", "Remove do final", "Adiciona no início", "Ordena"], 0),
        ("async/await é usado para:", ["Código assíncrono", "Loops", "CSS", "HTML"], 0),
        ("document.querySelector seleciona:", ["Primeiro elemento que casa", "Todos", "Só IDs", "Só classes"], 0),
        ("JSON.parse faz:", ["String → objeto", "Objeto → string", "Valida HTML", "Compila JS"], 0),
        ("typeof null retorna:", ["object", "null", "undefined", "number"], 0),
        ("Promise representa:", ["Valor futuro", "Variável global", "Evento DOM", "CSS rule"], 0),
    ],
    "html": [
        ("Tag de parágrafo?", ["<p>", "<para>", "<text>", "<div>"], 0),
        ("Atributo de link (URL)?", ["href", "src", "link", "url"], 0),
        ("Tag de imagem?", ["<img>", "<image>", "<pic>", "<photo>"], 0),
        ("HTML5 semântico para navegação?", ["<nav>", "<menu>", "<header>", "<aside>"], 0),
        ("Input de e-mail?", ['type="email"', 'type="mail"', 'type="text-email"', "type=e-mail"], 0),
    ],
    "css": [
        ("Centralizar com Flexbox (eixo principal)?", ["justify-content: center", "align-items: center", "text-align: center", "margin: auto"], 0),
        ("Unidade relativa à viewport width?", ["vw", "vh", "em", "px"], 0),
        ("Selecionar classe .btn?", [".btn", "#btn", "btn", "*btn"], 0),
        ("display: none faz:", ["Remove do layout", "Só esconde visual", "Opacidade 0", "Inverte cores"], 0),
        ("Box model inclui:", ["content, padding, border, margin", "só content", "só margin", "só border"], 0),
    ],
    "geral": [
        ("Git: salvar alterações no repositório local?", ["git commit", "git push", "git pull", "git clone"], 0),
        ("HTTP status de sucesso?", ["200", "404", "500", "301"], 0),
        ("O que é API?", ["Interface de programação", "Banco de dados", "Sistema operacional", "Navegador"], 0),
        ("SQL: buscar dados?", ["SELECT", "GET", "FETCH", "FIND"], 0),
        ("Complexidade de busca linear?", ["O(n)", "O(1)", "O(log n)", "O(n²)"], 0),
    ],
}


def generate_quiz(topic: str, n_questions: int = 5) -> dict[str, Any]:
    topic_raw = (topic or "geral").strip()
    topic_key = topic_raw.lower()
    bank = None
    for k, v in QUIZ_BANKS.items():
        if k in topic_key or topic_key in k:
            bank = v
            break
    if not bank:
        for k, v in QUIZ_BANKS.items():
            if any(w in topic_key for w in k.split()) or k[:3] in topic_key:
                bank = v
                break
    if not bank:
        bank = list(QUIZ_BANKS["geral"]) + [
            (f"O que é importante ao estudar {topic_raw}?", ["Praticar com consistência", "Só memorizar", "Evitar exercícios", "Ignorar erros"], 0),
            (f"Melhor forma de aprender {topic_raw}?", ["Projetos práticos", "Só vídeos passivos", "Copiar sem entender", "Pular fundamentos"], 0),
        ]
    n = max(1, min(int(n_questions), len(bank), 10))
    chosen = random.sample(bank, n) if len(bank) >= n else bank[:n]
    questions = []
    for q, opts, ans in chosen:
        indexed = list(enumerate(opts))
        random.shuffle(indexed)
        new_opts = [o for _, o in indexed]
        new_ans = next(i for i, (orig_i, _) in enumerate(indexed) if orig_i == ans)
        questions.append({
            "id": str(uuid.uuid4())[:6],
            "question": q,
            "options": new_opts,
            "answer": new_ans,
        })
    return {
        "quiz_id": str(uuid.uuid4())[:10],
        "topic": topic_raw,
        "questions": questions,
        "created_at": int(time.time()),
        "note": "Respostas embaralhadas. Use /api/nf/quiz/score para pontuar.",
    }


def score_quiz(answers: list, questions: list) -> dict[str, Any]:
    correct = 0
    details = []
    qmap = {q["id"]: q for q in questions}
    for a in answers:
        q = qmap.get(a.get("id"))
        if not q:
            continue
        ok = int(a.get("chosen", -1)) == int(q.get("answer", -999))
        if ok:
            correct += 1
        details.append({"id": q["id"], "correct": ok, "expected": q.get("answer")})
    total = len(questions) or 1
    pct = round(100 * correct / total)
    if pct >= 90:
        grade = "Excelente 🏆"
    elif pct >= 70:
        grade = "Bom 👍"
    elif pct >= 50:
        grade = "Regular 📚"
    else:
        grade = "Continue praticando 💪"
    return {"ok": True, "correct": correct, "total": total, "percent": pct, "details": details, "grade": grade}


# ===========================================================================
# 7. Summary / mind map
# ===========================================================================
def generate_summary(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if len(text) < 20:
        return {"ok": False, "error": "Cole um texto maior (mín. 20 caracteres)"}
    sentences = re.split(r"[.!?\n]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15][:12]
    words = re.findall(r"\b[a-záàâãéêíóôõúçA-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{4,}\b", text)
    stop = {"para", "como", "mais", "sobre", "quando", "onde", "porque", "isso", "esta", "este",
            "aqui", "também", "muito", "pode", "ser", "uma", "com", "dos", "das", "que", "não",
            "são", "pelo", "pela", "entre", "depois", "antes", "ainda", "assim", "esse", "essa",
            "this", "that", "with", "from", "have", "been", "were", "their", "which", "would"}
    freq: dict[str, int] = {}
    for w in words:
        wl = w.lower()
        if wl not in stop:
            freq[wl] = freq.get(wl, 0) + 1
    keywords = sorted(freq.items(), key=lambda x: -x[1])[:10]
    root = {"id": "root", "label": "Resumo", "children": []}
    for i, sent in enumerate(sentences[:7]):
        label = sent[:90] + ("…" if len(sent) > 90 else "")
        root["children"].append({"id": f"n{i}", "label": label, "children": []})
    if root["children"] and keywords:
        for i, (kw, cnt) in enumerate(keywords[:5]):
            root["children"][i % len(root["children"])]["children"].append({
                "id": f"k{i}", "label": f"{kw} ({cnt})", "children": []
            })
    return {
        "ok": True,
        "summary_points": sentences[:7],
        "keywords": [k for k, _ in keywords],
        "mindmap": root,
        "char_count": len(text),
        "word_count": len(words),
    }


# ===========================================================================
# 8. Study calendar
# ===========================================================================
def _study_path(user_id: str) -> Path:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    return STUDY_DIR / f"{uid}_calendar.json"


def list_study_events(user_id: str) -> list[dict[str, Any]]:
    path = _study_path(user_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("events", [])
    except Exception:
        return []


def add_study_event(user_id: str, title: str, date: str, time_str: str = "09:00", note: str = "") -> dict[str, Any]:
    path = _study_path(user_id)
    data = {"events": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    ev = {
        "id": str(uuid.uuid4())[:8], "title": title[:100], "date": date,
        "time": time_str, "note": note[:300], "done": False, "created_at": int(time.time()),
    }
    data["events"].append(ev)
    data["events"] = sorted(data["events"], key=lambda e: (e["date"], e["time"]))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "event": ev}


def toggle_study_event(user_id: str, event_id: str) -> dict[str, Any]:
    path = _study_path(user_id)
    if not path.exists():
        return {"ok": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["events"]:
        if e["id"] == event_id:
            e["done"] = not e.get("done", False)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "event": e}
    return {"ok": False, "error": "Evento não encontrado"}


def delete_study_event(user_id: str, event_id: str) -> dict[str, Any]:
    path = _study_path(user_id)
    if not path.exists():
        return {"ok": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data["events"])
    data["events"] = [e for e in data["events"] if e["id"] != event_id]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "removed": before - len(data["events"])}


# ===========================================================================
# 9. Profile / XP / streaks
# ===========================================================================
def _progress_load() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _progress_save(data: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_progress() -> dict:
    return {
        "xp": 0, "level": 1,
        "games_created": 0, "games_played": 0, "exercises_done": 0,
        "videos_watched": 0, "flashcards_reviewed": 0, "sites_created": 0,
        "quizzes_done": 0, "sprites_saved": 0,
        "favorites": [], "achievements": [],
        "streak_days": 0, "last_active_day": None, "last_active": None,
        "daily_xp": 0, "daily_xp_day": None,
    }


def get_progress(user_id: str) -> dict[str, Any]:
    uid = str(user_id or "guest")
    all_p = _progress_load()
    p = all_p.get(uid) or _default_progress()
    for k, v in _default_progress().items():
        if k not in p:
            p[k] = v
    p["level"] = max(1, 1 + p.get("xp", 0) // 300)
    p["xp_to_next"] = 300 - (p.get("xp", 0) % 300)
    p["xp_in_level"] = p.get("xp", 0) % 300
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if p.get("last_active_day") and p.get("last_active_day") != today:
        try:
            last = datetime.strptime(p["last_active_day"], "%Y-%m-%d").date()
            if (datetime.now(timezone.utc).date() - last).days > 1:
                p["streak_days"] = 0
        except Exception:
            pass
    return p


def add_xp(user_id: str, amount: int, reason: str = "") -> dict[str, Any]:
    uid = str(user_id or "guest")
    all_p = _progress_load()
    p = all_p.get(uid) or _default_progress()
    for k, v in _default_progress().items():
        if k not in p:
            p[k] = v
    amount = max(0, int(amount))
    p["xp"] = p.get("xp", 0) + amount
    p["level"] = max(1, 1 + p["xp"] // 300)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if p.get("last_active_day") != today:
        if p.get("last_active_day"):
            try:
                last = datetime.strptime(p["last_active_day"], "%Y-%m-%d").date()
                if (datetime.now(timezone.utc).date() - last).days == 1:
                    p["streak_days"] = p.get("streak_days", 0) + 1
                else:
                    p["streak_days"] = 1
            except Exception:
                p["streak_days"] = 1
        else:
            p["streak_days"] = 1
        p["last_active_day"] = today
        p["daily_xp"] = 0
        p["daily_xp_day"] = today
    p["daily_xp"] = p.get("daily_xp", 0) + amount
    p["last_active"] = int(time.time())
    reason_map = {
        "game_created": "games_created", "game_played": "games_played",
        "exercise": "exercises_done", "flashcard": "flashcards_reviewed",
        "site": "sites_created", "quiz": "quizzes_done", "sprite": "sprites_saved",
    }
    if reason in reason_map:
        key = reason_map[reason]
        p[key] = p.get(key, 0) + 1
    ach = set(p.get("achievements") or [])
    checks = [
        ("first_game", p.get("games_created", 0) >= 1),
        ("gamer_10", p.get("games_played", 0) >= 10),
        ("flash_master", p.get("flashcards_reviewed", 0) >= 50),
        ("quiz_whiz", p.get("quizzes_done", 0) >= 5),
        ("streak_7", p.get("streak_days", 0) >= 7),
        ("level_5", p.get("level", 1) >= 5),
        ("level_10", p.get("level", 1) >= 10),
        ("artist", p.get("sprites_saved", 0) >= 3),
    ]
    for aid, ok in checks:
        if ok:
            ach.add(aid)
    p["achievements"] = list(ach)
    all_p[uid] = p
    _progress_save(all_p)
    return get_progress(uid)


ACHIEVEMENT_META = {
    "first_game": {"name": "Primeiro Jogo", "icon": "🎮", "desc": "Criou o primeiro jogo"},
    "gamer_10": {"name": "Jogador", "icon": "🕹️", "desc": "10 partidas jogadas"},
    "flash_master": {"name": "Memória de Aço", "icon": "🃏", "desc": "50 flashcards revisados"},
    "quiz_whiz": {"name": "Quiz Master", "icon": "❓", "desc": "5 quizzes completos"},
    "streak_7": {"name": "Sequência 7 dias", "icon": "🔥", "desc": "7 dias seguidos ativos"},
    "level_5": {"name": "Nível 5", "icon": "⭐", "desc": "Alcançou nível 5"},
    "level_10": {"name": "Nível 10", "icon": "🏆", "desc": "Alcançou nível 10"},
    "artist": {"name": "Artista", "icon": "🎨", "desc": "3 sprites salvos"},
}


def list_achievements(user_id: str) -> list[dict[str, Any]]:
    p = get_progress(user_id)
    unlocked = set(p.get("achievements") or [])
    return [{**meta, "id": aid, "unlocked": aid in unlocked} for aid, meta in ACHIEVEMENT_META.items()]


def toggle_favorite(user_id: str, item_type: str, item_id: str, title: str = "") -> dict[str, Any]:
    uid = str(user_id or "guest")
    all_p = _progress_load()
    p = all_p.get(uid) or _default_progress()
    favs = p.get("favorites", [])
    key = f"{item_type}:{item_id}"
    existing = next((f for f in favs if f.get("key") == key), None)
    if existing:
        favs = [f for f in favs if f.get("key") != key]
        action = "removed"
    else:
        favs.append({"key": key, "type": item_type, "id": item_id, "title": title[:80], "at": int(time.time())})
        action = "added"
    p["favorites"] = favs[:100]
    all_p[uid] = p
    _progress_save(all_p)
    return {"ok": True, "action": action, "favorites": p["favorites"]}


# ===========================================================================
# 10. Guided projects
# ===========================================================================
GUIDED_PROJECTS = [
    {"id": "calc", "title": "Crie uma calculadora", "level": "iniciante", "lang": "javascript",
     "checkpoints": ["Estrutura HTML com display e botões 0-9", "CSS em grid para o teclado", "Funções + − × ÷", "Divisão por zero e botão C"],
     "starter": "let display = '0';\nfunction press(n) {\n  display = display === '0' ? String(n) : display + n;\n  return display;\n}\nfunction clear() { display = '0'; return display; }\nfunction calc(a, op, b) {\n  a = Number(a); b = Number(b);\n  if (op === '+') return a + b;\n  if (op === '-') return a - b;\n  if (op === '*') return a * b;\n  if (op === '/') return b === 0 ? 'Erro' : a / b;\n}",
     "hint": "Use Number() para converter strings em números."},
    {"id": "todo", "title": "Crie um to-do list", "level": "iniciante", "lang": "javascript",
     "checkpoints": ["Array de tarefas {text, done}", "Função add(text)", "Função toggle(index)", "localStorage"],
     "starter": "const KEY = 'todos';\nlet tasks = JSON.parse(localStorage.getItem(KEY) || '[]');\nfunction save() { localStorage.setItem(KEY, JSON.stringify(tasks)); }\nfunction add(text) { tasks.push({ text, done: false }); save(); }\nfunction toggle(i) { tasks[i].done = !tasks[i].done; save(); }",
     "hint": "localStorage só guarda strings — use JSON.stringify/parse."},
    {"id": "quiz_app", "title": "Quiz interativo", "level": "intermediário", "lang": "javascript",
     "checkpoints": ["Array de perguntas", "Renderizar pergunta atual", "Pontuar respostas", "Tela de resultado %"],
     "starter": "const questions = [\n  { q: '2+2?', opts: ['3','4','5'], a: 1 },\n  { q: 'Capital do Brasil?', opts: ['SP','RJ','Brasília'], a: 2 },\n];\nlet score = 0, idx = 0;\nfunction answer(choice) {\n  if (choice === questions[idx].a) score++;\n  idx++;\n  return idx >= questions.length ? { done: true, score } : { done: false, next: questions[idx] };\n}",
     "hint": "Guarde o índice da pergunta atual."},
    {"id": "api_fetch", "title": "Consuma uma API pública", "level": "intermediário", "lang": "javascript",
     "checkpoints": ["fetch() JSONPlaceholder", "Loading e erro", "Renderizar posts", "Filtro de busca"],
     "starter": "async function loadPosts() {\n  const r = await fetch('https://jsonplaceholder.typicode.com/posts?_limit=8');\n  if (!r.ok) throw new Error('Falha na API');\n  return r.json();\n}\nfunction filterPosts(posts, term) {\n  const t = term.toLowerCase();\n  return posts.filter(p => p.title.toLowerCase().includes(t));\n}",
     "hint": "Use try/catch em torno do await fetch."},
    {"id": "counter", "title": "Contador com histórico", "level": "iniciante", "lang": "javascript",
     "checkpoints": ["count = 0", "Botões +1 e -1", "Não negativo", "Últimas 5 alterações"],
     "starter": "let count = 0;\nconst history = [];\nfunction inc() { count++; history.push('+1'); if (history.length > 5) history.shift(); return count; }\nfunction dec() { if (count > 0) { count--; history.push('-1'); if (history.length > 5) history.shift(); } return count; }",
     "hint": "history.shift() remove o item mais antigo."},
    {"id": "palindrome", "title": "Detector de palíndromo", "level": "iniciante", "lang": "python",
     "checkpoints": ["Função recebe string", "Ignorar espaços/maiúsculas", "Comparar com invertida", "True/False"],
     "starter": "def is_palindrome(s):\n    cleaned = ''.join(c.lower() for c in s if c.isalnum())\n    return cleaned == cleaned[::-1]\n\nprint(is_palindrome('Ame a ema'))  # True",
     "hint": "s[::-1] inverte a string em Python."},
    {"id": "responsive_card", "title": "Card responsivo", "level": "iniciante", "lang": "html",
     "checkpoints": ["HTML título/texto/botão", "border-radius e sombra", "Media query <600px", "Hover no botão"],
     "starter": '<article class="card">\n  <h2>Meu Card</h2>\n  <p>Conteúdo aqui.</p>\n  <button>Ação</button>\n</article>\n<style>\n.card { max-width: 320px; padding: 1.25rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,.15); }\n@media (max-width: 600px) { .card { max-width: 100%; } }\nbutton:hover { opacity: .85; }\n</style>',
     "hint": "box-shadow deixa o card com profundidade."},
]


def list_guided_projects() -> list[dict[str, Any]]:
    return [{"id": p["id"], "title": p["title"], "level": p["level"], "lang": p["lang"], "checkpoints": len(p["checkpoints"])} for p in GUIDED_PROJECTS]


def get_guided_project(pid: str) -> dict[str, Any] | None:
    for p in GUIDED_PROJECTS:
        if p["id"] == pid:
            return p
    return None


DAILY_CHALLENGES = [
    {"week": 1, "title": "Função maior número", "desc": "Crie uma função que receba dois números e retorne o maior.", "lang": "python"},
    {"week": 2, "title": "Card responsivo", "desc": "Faça um card HTML/CSS que se adapte a telas pequenas.", "lang": "html"},
    {"week": 3, "title": "Contador +/−", "desc": "Implemente um contador com botões + e − em JavaScript.", "lang": "javascript"},
    {"week": 4, "title": "Busca linear", "desc": "Implemente busca linear e conte as comparações.", "lang": "python"},
    {"week": 5, "title": "To-do com filtro", "desc": "To-do list com filtro todas/pendentes/concluídas.", "lang": "javascript"},
    {"week": 6, "title": "Validador de e-mail", "desc": "Função que valida formato de e-mail com regex.", "lang": "javascript"},
    {"week": 7, "title": "Palíndromo", "desc": "Verifique se uma string é um palíndromo.", "lang": "python"},
    {"week": 8, "title": "FizzBuzz", "desc": "Para 1..30: múltiplos de 3=Fizz, 5=Buzz, ambos=FizzBuzz.", "lang": "python"},
    {"week": 9, "title": "Accordion CSS", "desc": "Seção expansível só com HTML+CSS.", "lang": "html"},
    {"week": 10, "title": "Debounce", "desc": "Implemente debounce de 300ms para um campo de busca.", "lang": "javascript"},
]


def get_daily_challenge() -> dict[str, Any]:
    week = datetime.now(timezone.utc).isocalendar()[1] % len(DAILY_CHALLENGES)
    ch = dict(DAILY_CHALLENGES[week])
    ch["week_number"] = datetime.now(timezone.utc).isocalendar()[1]
    return ch


# ===========================================================================
# 11. Site templates + scaffolds
# ===========================================================================
SITE_TEMPLATES = [
    {"id": "portfolio", "name": "Portfólio", "desc": "Página pessoal com projetos e contato", "sections": ["hero", "about", "projects", "contact"]},
    {"id": "loja", "name": "Loja", "desc": "Vitrine de produtos com carrinho simples", "sections": ["hero", "products", "cart", "footer"]},
    {"id": "blog", "name": "Blog", "desc": "Lista de posts com sidebar", "sections": ["header", "posts", "sidebar", "footer"]},
    {"id": "landing", "name": "Landing Page", "desc": "Página de conversão com CTA", "sections": ["hero", "features", "testimonials", "cta"]},
    {"id": "docs", "name": "Documentação", "desc": "Docs com menu lateral", "sections": ["sidebar", "content", "toc"]},
    {"id": "evento", "name": "Evento", "desc": "Página de evento com inscrição", "sections": ["hero", "agenda", "speakers", "register"]},
]

SITE_SCAFFOLDS = {
    "portfolio": """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meu Portfólio</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--accent:#3b82f6;--text:#e2e8f0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
header{padding:4rem 1.5rem;text-align:center;background:linear-gradient(135deg,#1e3a5f,#0f172a)}
header h1{font-size:2.2rem;margin-bottom:.5rem}
.muted{opacity:.7}
section{max-width:900px;margin:0 auto;padding:2.5rem 1.5rem}
h2{margin-bottom:1rem;color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}
.card{background:var(--card);padding:1.25rem;border-radius:12px}
a.btn{display:inline-block;margin-top:1rem;padding:.6rem 1.2rem;background:var(--accent);color:#fff;border-radius:8px;text-decoration:none}
footer{text-align:center;padding:2rem;opacity:.5;font-size:.85rem}
</style></head><body>
<header><h1>Seu Nome</h1><p class="muted">Desenvolvedor · Designer · Criador</p>
<a class="btn" href="#contato">Fale comigo</a></header>
<section id="sobre"><h2>Sobre</h2><p>Breve biografia. Substitua este texto.</p></section>
<section id="projetos"><h2>Projetos</h2><div class="grid">
<div class="card"><h3>Projeto 1</h3><p class="muted">Descrição.</p></div>
<div class="card"><h3>Projeto 2</h3><p class="muted">Descrição.</p></div>
<div class="card"><h3>Projeto 3</h3><p class="muted">Descrição.</p></div>
</div></section>
<section id="contato"><h2>Contato</h2><p>email@exemplo.com</p></section>
<footer>© 2026 — Feito com JARVIS</footer></body></html>""",
    "landing": """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Landing</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#0b1220;color:#e8eef7}
.hero{min-height:80vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2rem;background:radial-gradient(ellipse at top,#1e3a5f 0%,#0b1220 70%)}
h1{font-size:clamp(2rem,5vw,3rem);margin-bottom:.75rem}
.cta{margin-top:1.5rem;padding:.85rem 1.75rem;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border:none;color:#fff;font-size:1.05rem;border-radius:999px;cursor:pointer}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.25rem;max-width:960px;margin:3rem auto;padding:0 1.5rem}
.feat{background:#141c2e;padding:1.5rem;border-radius:12px;border:1px solid #1e293b}
</style></head><body>
<div class="hero"><h1>Seu produto incrível</h1>
<p style="opacity:.75;max-width:480px">Uma frase que vende o valor em menos de 10 segundos.</p>
<button class="cta">Começar agora</button></div>
<div class="features">
<div class="feat"><h3>Rápido</h3><p style="opacity:.7">Benefício 1.</p></div>
<div class="feat"><h3>Simples</h3><p style="opacity:.7">Benefício 2.</p></div>
<div class="feat"><h3>Confiável</h3><p style="opacity:.7">Benefício 3.</p></div>
</div></body></html>""",
    "blog": """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meu Blog</title>
<style>
body{margin:0;font-family:Georgia,serif;background:#faf9f7;color:#1a1a1a}
header{padding:2rem 1.5rem;border-bottom:1px solid #e5e5e5;text-align:center}
main{max-width:680px;margin:0 auto;padding:2rem 1.5rem}
article{margin-bottom:2.5rem;padding-bottom:2rem;border-bottom:1px solid #eee}
.meta{font-size:.85rem;color:#888;margin-bottom:.75rem}
a{color:#2563eb}
</style></head><body>
<header><h1>Meu Blog</h1><p style="color:#666">Pensamentos e tutoriais</p></header>
<main>
<article><h2><a href="#">Título do post 1</a></h2><div class="meta">2 out 2026 · 5 min</div><p>Resumo do post…</p></article>
<article><h2><a href="#">Título do post 2</a></h2><div class="meta">28 set 2026 · 3 min</div><p>Outro resumo.</p></article>
</main></body></html>""",
}


def list_site_templates() -> list[dict[str, Any]]:
    return SITE_TEMPLATES


def get_site_scaffold(tpl_id: str) -> dict[str, Any]:
    html = SITE_SCAFFOLDS.get(tpl_id)
    if not html:
        meta = next((t for t in SITE_TEMPLATES if t["id"] == tpl_id), None)
        if not meta:
            return {"ok": False, "error": "Template não encontrado"}
        sections = "".join(f'<section id="{s}"><h2>{s.title()}</h2><p>Conteúdo de {s}…</p></section>' for s in meta["sections"])
        html = f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>{meta["name"]}</title><style>body{{font-family:system-ui;margin:2rem;background:#0f172a;color:#e2e8f0}}section{{margin:2rem 0}}</style></head><body><h1>{meta["name"]}</h1>{sections}</body></html>'
    return {"ok": True, "id": tpl_id, "html": html}


# ===========================================================================
# 12. Sounds
# ===========================================================================
SOUND_BANK = [
    {"id": "jump", "name": "Pulo", "file": "sfx_jump", "desc": "Efeito de pulo", "freq": 400, "type": "square", "dur": 0.12},
    {"id": "coin", "name": "Coleta", "file": "sfx_coin", "desc": "Coletar item", "freq": 880, "type": "sine", "dur": 0.15},
    {"id": "hit", "name": "Colisão", "file": "sfx_hit", "desc": "Colisão / dano", "freq": 150, "type": "sawtooth", "dur": 0.2},
    {"id": "win", "name": "Vitória", "file": "sfx_win", "desc": "Fim de fase", "freq": 523, "type": "sine", "dur": 0.4},
    {"id": "lose", "name": "Derrota", "file": "sfx_lose", "desc": "Game over", "freq": 120, "type": "triangle", "dur": 0.5},
    {"id": "click", "name": "Clique", "file": "sfx_click", "desc": "UI click", "freq": 600, "type": "square", "dur": 0.05},
]


def list_sounds() -> list[dict[str, Any]]:
    return SOUND_BANK


# ===========================================================================
# 13. Sprite editor
# ===========================================================================
def _sprite_path(user_id: str) -> Path:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    return SPRITES_DIR / f"{uid}.json"


def list_sprites(user_id: str) -> list[dict[str, Any]]:
    path = _sprite_path(user_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [{"id": s["id"], "name": s["name"], "size": s.get("size", 16), "updated_at": s.get("updated_at")} for s in data.get("sprites", [])]
    except Exception:
        return []


def save_sprite(user_id: str, name: str, size: int, pixels: list) -> dict[str, Any]:
    path = _sprite_path(user_id)
    data = {"sprites": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    size = max(8, min(64, int(size or 16)))
    expected = size * size
    if not isinstance(pixels, list) or len(pixels) != expected:
        return {"ok": False, "error": f"pixels deve ter {expected} itens"}
    sid = str(uuid.uuid4())[:10]
    sprite = {"id": sid, "name": (name or "Sprite")[:60], "size": size, "pixels": pixels, "updated_at": int(time.time())}
    data["sprites"].append(sprite)
    data["sprites"] = data["sprites"][-50:]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    add_xp(user_id, 15, "sprite")
    return {"ok": True, "id": sid, "name": sprite["name"]}


def load_sprite(user_id: str, sprite_id: str) -> dict[str, Any] | None:
    path = _sprite_path(user_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for s in data.get("sprites", []):
        if s["id"] == sprite_id:
            return s
    return None


def delete_sprite(user_id: str, sprite_id: str) -> dict[str, Any]:
    path = _sprite_path(user_id)
    if not path.exists():
        return {"ok": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data["sprites"])
    data["sprites"] = [s for s in data["sprites"] if s["id"] != sprite_id]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "removed": before - len(data["sprites"])}


# ===========================================================================
# 14. Playground snippets
# ===========================================================================
def save_playground(user_id: str, title: str, code: str, lang: str = "javascript") -> dict[str, Any]:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    folder = STUDY_DIR / "playground" / uid
    folder.mkdir(parents=True, exist_ok=True)
    pid = str(uuid.uuid4())[:10]
    doc = {"id": pid, "title": (title or "Sem título")[:80], "code": (code or "")[:50000], "lang": lang, "updated_at": int(time.time())}
    (folder / f"{pid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    add_xp(user_id, 10, "exercise")
    return {"ok": True, "id": pid}


def list_playground(user_id: str) -> list[dict[str, Any]]:
    uid = re.sub(r"[^\w\-]", "_", str(user_id or "guest"))[:64]
    folder = STUDY_DIR / "playground" / uid
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "title": d["title"], "lang": d.get("lang"), "updated_at": d.get("updated_at")})
        except Exception:
            continue
    return out
