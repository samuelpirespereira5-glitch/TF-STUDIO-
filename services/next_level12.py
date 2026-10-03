"""JARVIS Game Studio 12 — Polimento + Novas Áreas (lista Claude screenshots).

Nível de Polimento + features que ainda não tinham aparecido:
  Acessibilidade, Controle/Admin, Sustentabilidade, Integrações externas,
  Dados & Insights, Conteúdo extra, Ferramentas do dia a dia, Engajamento extra,
  "Uau" de verdade, Identidade visual, Inteligência real.

Não reescreve módulos existentes — só estende (padrão dos Níveis 9–11).
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
NL_DIR = DATA_DIR / "next_level12"
NL_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


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


def next_level12_overview(user_id: str) -> dict:
    return {
        "ok": True,
        "nivel": 12,
        "titulo": "Polimento + Novas Áreas",
        "areas": [
            "Acessibilidade",
            "Controle/Admin",
            "Sustentabilidade",
            "Integrações externas",
            "Dados & Insights",
            "Conteúdo extra",
            "Ferramentas do dia a dia",
            "Engajamento extra",
            "Uau de verdade",
            "Identidade visual",
            "Inteligência real",
            "Polimento (navegação unificada)",
        ],
        "user_id": user_id,
        "ts": _now(),
    }


# ===========================================================================
# 1. ACESSIBILIDADE
# ===========================================================================

A11Y_FILE = NL_DIR / "a11y_prefs.json"
KEYBOARD_SHORTCUTS = {
    "g h": "Ir para Home / Hub",
    "g s": "Ir para Estúdio de Jogos",
    "g e": "Ir para Educação / Trilhas",
    "g c": "Ir para Certificados",
    "g a": "Abrir Assistente Jarvis",
    "/": "Focar busca global",
    "?": "Mostrar todos os atalhos",
    "Esc": "Fechar modal / painel",
    "Alt + +": "Aumentar fonte",
    "Alt + -": "Diminuir fonte",
    "Alt + C": "Alternar alto contraste",
    "Alt + R": "Ler página em voz alta (TTS)",
}


def get_a11y_prefs(user_id: str) -> dict:
    data = _load_json(A11Y_FILE, {})
    prefs = data.get(user_id) or {
        "tts_enabled": False,
        "tts_rate": 1.0,
        "tts_lang": "pt-BR",
        "high_contrast": False,
        "font_scale": 1.0,
        "reduce_motion": False,
        "keyboard_nav": True,
    }
    return {"ok": True, "prefs": prefs, "shortcuts": KEYBOARD_SHORTCUTS}


def set_a11y_prefs(user_id: str, updates: dict) -> dict:
    with _lock:
        data = _load_json(A11Y_FILE, {})
        prefs = data.get(user_id) or {}
        allowed = {
            "tts_enabled", "tts_rate", "tts_lang", "high_contrast",
            "font_scale", "reduce_motion", "keyboard_nav",
        }
        for k, v in (updates or {}).items():
            if k in allowed:
                prefs[k] = v
        data[user_id] = prefs
        _save_json(A11Y_FILE, data)
    return {"ok": True, "prefs": prefs}


def tts_preview(text: str, lang: str = "pt-BR") -> dict:
    """Stub: retorna metadados do que seria falado (TTS real no front via Web Speech API)."""
    t = (text or "").strip()
    if not t:
        return {"ok": False, "error": "Texto vazio"}
    words = len(t.split())
    est_sec = max(1, round(words / 2.5))
    return {
        "ok": True,
        "text": t[:500],
        "lang": lang,
        "words": words,
        "estimated_seconds": est_sec,
        "hint": "No browser use speechSynthesis.speak() com este texto.",
    }


# ===========================================================================
# 2. CONTROLE / ADMIN
# ===========================================================================

CLASSES_FILE = NL_DIR / "classes.json"
MODERATION_FILE = NL_DIR / "moderation_queue.json"
PARENT_LINKS_FILE = NL_DIR / "parent_links.json"


def create_classroom(teacher_id: str, name: str, description: str = "") -> dict:
    name = (name or "").strip()
    if len(name) < 3:
        return {"ok": False, "error": "Nome da turma muito curto"}
    cid = f"class_{uuid.uuid4().hex[:10]}"
    with _lock:
        data = _load_json(CLASSES_FILE, {"classes": []})
        entry = {
            "id": cid,
            "name": name,
            "description": (description or "").strip(),
            "teacher_id": teacher_id,
            "students": [],
            "assignments": [],
            "created_at": _now(),
        }
        data["classes"].append(entry)
        _save_json(CLASSES_FILE, data)
    return {"ok": True, "classroom": entry}


def list_classrooms(user_id: str) -> list:
    data = _load_json(CLASSES_FILE, {"classes": []})
    return [
        c for c in data["classes"]
        if c.get("teacher_id") == user_id or user_id in c.get("students", [])
    ]


def add_student_to_class(class_id: str, student_id: str, teacher_id: str) -> dict:
    with _lock:
        data = _load_json(CLASSES_FILE, {"classes": []})
        for c in data["classes"]:
            if c["id"] == class_id and c["teacher_id"] == teacher_id:
                if student_id not in c["students"]:
                    c["students"].append(student_id)
                _save_json(CLASSES_FILE, data)
                return {"ok": True, "classroom": c}
    return {"ok": False, "error": "Turma não encontrada ou sem permissão"}


def assign_exercise(class_id: str, teacher_id: str, title: str, exercise_id: str = "") -> dict:
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "Título obrigatório"}
    with _lock:
        data = _load_json(CLASSES_FILE, {"classes": []})
        for c in data["classes"]:
            if c["id"] == class_id and c["teacher_id"] == teacher_id:
                aid = f"asg_{uuid.uuid4().hex[:8]}"
                assignment = {
                    "id": aid,
                    "title": title,
                    "exercise_id": exercise_id or aid,
                    "assigned_at": _now(),
                    "completed_by": [],
                }
                c["assignments"].append(assignment)
                _save_json(CLASSES_FILE, data)
                return {"ok": True, "assignment": assignment}
    return {"ok": False, "error": "Turma não encontrada ou sem permissão"}


def class_report(class_id: str, teacher_id: str) -> dict:
    data = _load_json(CLASSES_FILE, {"classes": []})
    for c in data["classes"]:
        if c["id"] == class_id and c["teacher_id"] == teacher_id:
            total_students = len(c.get("students", []))
            assignments = c.get("assignments", [])
            completion = []
            for a in assignments:
                done = len(a.get("completed_by", []))
                completion.append({
                    "assignment": a["title"],
                    "done": done,
                    "total": total_students,
                    "pct": round(100 * done / total_students, 1) if total_students else 0,
                })
            return {
                "ok": True,
                "class_name": c["name"],
                "students": total_students,
                "assignments": len(assignments),
                "completion": completion,
            }
    return {"ok": False, "error": "Turma não encontrada"}


def link_parent_account(parent_id: str, child_id: str) -> dict:
    with _lock:
        data = _load_json(PARENT_LINKS_FILE, {"links": []})
        for L in data["links"]:
            if L["parent"] == parent_id and L["child"] == child_id:
                return {"ok": True, "link": L, "already": True}
        entry = {
            "id": f"pl_{uuid.uuid4().hex[:8]}",
            "parent": parent_id,
            "child": child_id,
            "created_at": _now(),
        }
        data["links"].append(entry)
        _save_json(PARENT_LINKS_FILE, data)
    return {"ok": True, "link": entry}


def parent_dashboard(parent_id: str) -> dict:
    data = _load_json(PARENT_LINKS_FILE, {"links": []})
    children = [L["child"] for L in data["links"] if L["parent"] == parent_id]
    # Stub progress summary
    progress = [
        {
            "child_id": ch,
            "xp": abs(hash(ch)) % 5000,
            "streak": abs(hash(ch + "s")) % 30,
            "last_activity": _today(),
            "modules_done": abs(hash(ch + "m")) % 20,
        }
        for ch in children
    ]
    return {"ok": True, "children": children, "progress": progress}


def report_content(reporter_id: str, content_type: str, content_id: str, reason: str) -> dict:
    with _lock:
        data = _load_json(MODERATION_FILE, {"queue": []})
        entry = {
            "id": f"mod_{uuid.uuid4().hex[:10]}",
            "reporter": reporter_id,
            "content_type": content_type or "unknown",
            "content_id": content_id or "",
            "reason": (reason or "").strip()[:500],
            "status": "pending",
            "created_at": _now(),
        }
        data["queue"].append(entry)
        _save_json(MODERATION_FILE, data)
    return {"ok": True, "ticket": entry}


def moderation_queue(status: str = "pending") -> dict:
    data = _load_json(MODERATION_FILE, {"queue": []})
    items = [q for q in data["queue"] if not status or q.get("status") == status]
    return {"ok": True, "count": len(items), "items": items[-50:]}


def moderate_item(item_id: str, action: str, reviewer_id: str) -> dict:
    action = (action or "").lower()
    if action not in ("approve", "remove", "warn"):
        return {"ok": False, "error": "Ação deve ser approve|remove|warn"}
    with _lock:
        data = _load_json(MODERATION_FILE, {"queue": []})
        for q in data["queue"]:
            if q["id"] == item_id:
                q["status"] = action
                q["reviewed_by"] = reviewer_id
                q["reviewed_at"] = _now()
                _save_json(MODERATION_FILE, data)
                return {"ok": True, "item": q}
    return {"ok": False, "error": "Item não encontrado"}


# ===========================================================================
# 3. SUSTENTABILIDADE (planos + parcerias)
# ===========================================================================

PLANS_FILE = NL_DIR / "user_plans.json"
PARTNERSHIPS_FILE = NL_DIR / "partnerships.json"

PLANS = {
    "free": {
        "name": "Gratuito",
        "games_limit": 5,
        "storage_mb": 50,
        "ai_credits_day": 10,
        "features": ["trilhas básicas", "editor simples", "certificados padrão"],
    },
    "premium": {
        "name": "Premium",
        "games_limit": 100,
        "storage_mb": 2000,
        "ai_credits_day": 200,
        "features": [
            "trilhas avançadas",
            "editor IA ilimitado",
            "certificados com competências",
            "relatório PDF mensal",
            "prioridade suporte",
            "sala de aula (até 30 alunos)",
        ],
        "price_brl": 29.90,
    },
}


def get_user_plan(user_id: str) -> dict:
    data = _load_json(PLANS_FILE, {})
    plan_id = data.get(user_id, {}).get("plan", "free")
    return {
        "ok": True,
        "plan_id": plan_id,
        "plan": PLANS.get(plan_id, PLANS["free"]),
        "since": data.get(user_id, {}).get("since"),
    }


def set_user_plan(user_id: str, plan_id: str) -> dict:
    if plan_id not in PLANS:
        return {"ok": False, "error": "Plano inválido (free|premium)"}
    with _lock:
        data = _load_json(PLANS_FILE, {})
        data[user_id] = {"plan": plan_id, "since": _now()}
        _save_json(PLANS_FILE, data)
    return {"ok": True, "plan_id": plan_id, "plan": PLANS[plan_id]}


def list_plans() -> dict:
    return {"ok": True, "plans": PLANS}


def request_partnership(org_name: str, contact_email: str, type_: str = "school") -> dict:
    org = (org_name or "").strip()
    email = (contact_email or "").strip()
    if len(org) < 2 or "@" not in email:
        return {"ok": False, "error": "Nome e e-mail válidos obrigatórios"}
    with _lock:
        data = _load_json(PARTNERSHIPS_FILE, {"requests": []})
        entry = {
            "id": f"ptn_{uuid.uuid4().hex[:10]}",
            "org_name": org,
            "contact_email": email,
            "type": type_ or "school",
            "status": "pending",
            "created_at": _now(),
        }
        data["requests"].append(entry)
        _save_json(PARTNERSHIPS_FILE, data)
    return {"ok": True, "request": entry}


def list_partnerships() -> dict:
    data = _load_json(PARTNERSHIPS_FILE, {"requests": []})
    return {"ok": True, "requests": data["requests"][-30:]}


# ===========================================================================
# 4. INTEGRAÇÕES EXTERNAS
# ===========================================================================

API_KEYS_FILE = NL_DIR / "api_keys.json"
EXPORTS_FILE = NL_DIR / "exports.json"
SOCIAL_LINKS_FILE = NL_DIR / "social_links.json"


def create_api_key(user_id: str, label: str = "default") -> dict:
    key = f"jgk_{secrets.token_urlsafe(24)}"
    with _lock:
        data = _load_json(API_KEYS_FILE, {"keys": []})
        entry = {
            "id": f"key_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "label": (label or "default")[:40],
            "key_prefix": key[:12] + "...",
            "key_hash": hashlib.sha256(key.encode()).hexdigest(),
            "created_at": _now(),
            "last_used": None,
        }
        data["keys"].append(entry)
        _save_json(API_KEYS_FILE, data)
    return {
        "ok": True,
        "api_key": key,  # só mostrado uma vez
        "meta": {k: v for k, v in entry.items() if k != "key_hash"},
        "docs": {
            "base": "/api/public/v1",
            "auth": "Header: Authorization: Bearer <api_key>",
            "endpoints": [
                "GET /progress — progresso do usuário",
                "GET /certificates — certificados emitidos",
                "POST /games — criar jogo via API",
            ],
        },
    }


def list_api_keys(user_id: str) -> dict:
    data = _load_json(API_KEYS_FILE, {"keys": []})
    keys = [
        {k: v for k, v in e.items() if k != "key_hash"}
        for e in data["keys"] if e.get("user_id") == user_id
    ]
    return {"ok": True, "keys": keys}


def export_progress_json(user_id: str) -> dict:
    payload = {
        "schema": "jarvis-game-studio-progress/v1",
        "user_id": user_id,
        "exported_at": _now(),
        "progress": {
            "xp": abs(hash(user_id)) % 8000,
            "level": 1 + (abs(hash(user_id)) % 20),
            "modules_completed": abs(hash(user_id + "m")) % 40,
            "games_created": abs(hash(user_id + "g")) % 15,
            "certificates": abs(hash(user_id + "c")) % 5,
            "streak_days": abs(hash(user_id + "s")) % 45,
        },
        "open": True,
        "license": "user-owned / open-export",
    }
    with _lock:
        data = _load_json(EXPORTS_FILE, {"exports": []})
        data["exports"].append({"user_id": user_id, "at": _now(), "type": "progress"})
        _save_json(EXPORTS_FILE, data)
    return {"ok": True, "export": payload}


def link_social_login(user_id: str, provider: str, external_id: str = "") -> dict:
    provider = (provider or "").lower()
    if provider not in ("google", "github"):
        return {"ok": False, "error": "Provider deve ser google|github"}
    with _lock:
        data = _load_json(SOCIAL_LINKS_FILE, {"links": []})
        for L in data["links"]:
            if L["user_id"] == user_id and L["provider"] == provider:
                return {"ok": True, "link": L, "already": True}
        entry = {
            "id": f"soc_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "provider": provider,
            "external_id": external_id or f"{provider}_{uuid.uuid4().hex[:6]}",
            "linked_at": _now(),
        }
        data["links"].append(entry)
        _save_json(SOCIAL_LINKS_FILE, data)
    return {
        "ok": True,
        "link": entry,
        "note": "OAuth real (Google/GitHub) exige client_id/secret no deploy; este endpoint registra o vínculo.",
    }


def list_social_links(user_id: str) -> dict:
    data = _load_json(SOCIAL_LINKS_FILE, {"links": []})
    links = [L for L in data["links"] if L.get("user_id") == user_id]
    return {"ok": True, "links": links}


# ===========================================================================
# 5. DADOS E INSIGHTS
# ===========================================================================

ACTIVITY_FILE = NL_DIR / "user_activity.json"


def _ensure_activity(user_id: str) -> list:
    data = _load_json(ACTIVITY_FILE, {})
    hist = data.get(user_id)
    if hist:
        return hist
    # gera histórico sintético dos últimos 30 dias
    hist = []
    base = datetime.now(timezone.utc)
    for i in range(30):
        d = (base - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        hist.append({
            "date": d,
            "hours_studied": round((abs(hash(user_id + d)) % 40) / 10, 1),
            "games_created": abs(hash(user_id + d + "g")) % 3,
            "xp_gained": abs(hash(user_id + d + "x")) % 200,
            "exercises_done": abs(hash(user_id + d + "e")) % 8,
        })
    data[user_id] = hist
    _save_json(ACTIVITY_FILE, data)
    return hist


def monthly_report(user_id: str) -> dict:
    hist = _ensure_activity(user_id)
    # últimos ~30 dias
    hours = sum(h["hours_studied"] for h in hist)
    games = sum(h["games_created"] for h in hist)
    xp = sum(h["xp_gained"] for h in hist)
    exercises = sum(h["exercises_done"] for h in hist)
    return {
        "ok": True,
        "title": "Seu mês em números",
        "period": f"{hist[0]['date']} → {hist[-1]['date']}" if hist else _today(),
        "stats": {
            "hours_studied": round(hours, 1),
            "games_created": games,
            "xp_gained": xp,
            "exercises_done": exercises,
        },
        "pdf_ready": True,
        "hint": "No front, gere PDF com jsPDF ou no backend com reportlab a partir destes dados.",
        "series": hist,
    }


def evolution_chart(user_id: str) -> dict:
    hist = _ensure_activity(user_id)
    cumulative_xp = []
    total = 0
    for h in hist:
        total += h["xp_gained"]
        cumulative_xp.append({"date": h["date"], "xp": total, "hours": h["hours_studied"]})
    return {
        "ok": True,
        "series": cumulative_xp,
        "chart_type": "line",
        "labels": ["XP acumulado", "Horas por dia"],
    }


# ===========================================================================
# 6. CONTEÚDO EXTRA
# ===========================================================================

PDF_QUIZ_FILE = NL_DIR / "pdf_quizzes.json"
INTEREST_TRACKS_FILE = NL_DIR / "interest_tracks.json"
NEWS_CACHE_FILE = NL_DIR / "tech_news.json"

INTEREST_CATALOG = {
    "jogos_terror": {
        "title": "Quero criar jogos de terror",
        "modules": ["Atmosfera e som", "AI de inimigos", "Iluminação dramática", "Narrativa de medo"],
    },
    "site_loja": {
        "title": "Quero fazer site de loja",
        "modules": ["HTML/CSS loja", "Carrinho JS", "Pagamentos stub", "Deploy estático"],
    },
    "python_jogos": {
        "title": "Quero aprender Python fazendo um jogo",
        "modules": ["Python básico", "Pygame intro", "Sprites e colisão", "Publicar no estúdio"],
    },
    "cyber_web": {
        "title": "Quero segurança web ofensiva",
        "modules": ["OWASP Top 10", "XSS/SQLi lab", "Burp básico", "Relatório de pentest"],
    },
}


def generate_quiz_from_text(user_id: str, source_text: str, n_questions: int = 5) -> dict:
    """Gera perguntas de múltipla escolha a partir de texto (simula PDF enviado)."""
    text = (source_text or "").strip()
    if len(text) < 40:
        return {"ok": False, "error": "Texto muito curto (mín. ~40 chars, simule o conteúdo do PDF)"}
    n = max(1, min(int(n_questions or 5), 15))
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 20]
    if not sentences:
        sentences = [text[:120]]
    questions = []
    for i in range(n):
        base = sentences[i % len(sentences)]
        qid = f"q_{uuid.uuid4().hex[:6]}"
        questions.append({
            "id": qid,
            "question": f"Com base no material: qual afirmação está correta sobre «{base[:60]}...»?",
            "options": [
                f"Afirmação correta derivada do trecho {i+1}",
                f"Distrator A sobre o tema {i+1}",
                f"Distrator B genérico",
                f"Distrator C irrelevante",
            ],
            "correct_index": 0,
        })
    quiz_id = f"quiz_{uuid.uuid4().hex[:10]}"
    entry = {
        "id": quiz_id,
        "user_id": user_id,
        "n_questions": n,
        "questions": questions,
        "created_at": _now(),
    }
    with _lock:
        data = _load_json(PDF_QUIZ_FILE, {"quizzes": []})
        data["quizzes"].append(entry)
        _save_json(PDF_QUIZ_FILE, data)
    return {"ok": True, "quiz": entry}


def list_interest_tracks() -> dict:
    return {"ok": True, "tracks": INTEREST_CATALOG}


def start_interest_track(user_id: str, track_key: str) -> dict:
    if track_key not in INTEREST_CATALOG:
        return {"ok": False, "error": f"Track inválida. Use: {list(INTEREST_CATALOG.keys())}"}
    with _lock:
        data = _load_json(INTEREST_TRACKS_FILE, {"enrollments": []})
        for e in data["enrollments"]:
            if e["user_id"] == user_id and e["track"] == track_key:
                return {"ok": True, "enrollment": e, "already": True}
        entry = {
            "id": f"tr_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "track": track_key,
            "title": INTEREST_CATALOG[track_key]["title"],
            "modules": INTEREST_CATALOG[track_key]["modules"],
            "progress": 0,
            "started_at": _now(),
        }
        data["enrollments"].append(entry)
        _save_json(INTEREST_TRACKS_FILE, data)
    return {"ok": True, "enrollment": entry}


def tech_news_digest() -> dict:
    """Notícias de tecnologia resumidas (stub estático + cache)."""
    cached = _load_json(NEWS_CACHE_FILE, {})
    if cached.get("date") == _today() and cached.get("items"):
        return {"ok": True, "date": _today(), "items": cached["items"], "cached": True}
    items = [
        {
            "title": "IA generativa acelera criação de jogos indie",
            "summary": "Ferramentas de texto→jogo e assets automáticos reduzem o tempo de protótipo de semanas para horas.",
            "tag": "IA / Games",
        },
        {
            "title": "PWA e notificações push ganham espaço em edtech",
            "summary": "Plataformas de aprendizado usam instalável + lembretes para manter streak e engajamento mobile.",
            "tag": "EdTech",
        },
        {
            "title": "Acessibilidade WCAG 2.2 vira requisito em produtos públicos",
            "summary": "Contraste, teclado completo e TTS deixam de ser opcionais em apps educacionais.",
            "tag": "A11y",
        },
        {
            "title": "OpenAPI e exportação de dados viram diferencial de confiança",
            "summary": "Usuários pedem API documentada e export JSON aberto para portabilidade de progresso e certificados.",
            "tag": "Open Data",
        },
    ]
    _save_json(NEWS_CACHE_FILE, {"date": _today(), "items": items})
    return {"ok": True, "date": _today(), "items": items, "cached": False}


# ===========================================================================
# 7. FERRAMENTAS DO DIA A DIA
# ===========================================================================

PALETTES_FILE = NL_DIR / "palettes.json"
CONVERSIONS_FILE = NL_DIR / "conversions.json"
RESUME_TEMPLATES = {
    "dev_junior": {
        "name": "Dev Júnior — limpo",
        "sections": ["Resumo", "Habilidades", "Projetos do estúdio", "Certificados", "Contato"],
    },
    "game_creator": {
        "name": "Criador de Jogos",
        "sections": ["Bio", "Jogos publicados", "Engine / stack", "Premiações", "Links"],
    },
    "cyber_analyst": {
        "name": "Analista de Segurança",
        "sections": ["Resumo", "Labs concluídos", "Ferramentas", "Certificados", "Write-ups"],
    },
}


def generate_palette(seed: str = "", n_colors: int = 5) -> dict:
    n = max(3, min(int(n_colors or 5), 8))
    base = abs(hash(seed or secrets.token_hex(4)))
    colors = []
    for i in range(n):
        h = (base + i * 47) % 360
        s = 55 + (i * 7) % 30
        l = 40 + (i * 9) % 35
        # HSL → hex aproximado simples
        colors.append({
            "hsl": f"hsl({h}, {s}%, {l}%)",
            "hex": f"#{(base + i * 9973) % 0xFFFFFF:06x}",
            "role": ["primary", "secondary", "accent", "bg", "text", "muted", "success", "warn"][i % 8],
        })
    icons = ["🎮", "🚀", "✦", "⬡", "◆", "◎", "▲", "●"]
    entry = {
        "id": f"pal_{uuid.uuid4().hex[:8]}",
        "seed": seed or "random",
        "colors": colors,
        "suggested_icons": icons[:n],
        "created_at": _now(),
    }
    with _lock:
        data = _load_json(PALETTES_FILE, {"items": []})
        data["items"].append(entry)
        _save_json(PALETTES_FILE, data)
    return {"ok": True, "palette": entry}


def convert_media_stub(filename: str, target_format: str) -> dict:
    """Stub de conversor de imagem/áudio — registra a intenção."""
    fn = (filename or "").strip()
    fmt = (target_format or "").lower().strip().lstrip(".")
    if not fn or not fmt:
        return {"ok": False, "error": "filename e target_format obrigatórios"}
    allowed = {"png", "jpg", "jpeg", "webp", "gif", "mp3", "ogg", "wav", "webm"}
    if fmt not in allowed:
        return {"ok": False, "error": f"Formato alvo deve ser um de: {sorted(allowed)}"}
    entry = {
        "id": f"conv_{uuid.uuid4().hex[:8]}",
        "source": fn,
        "target_format": fmt,
        "status": "queued",
        "note": "Em produção: usar ffmpeg/Pillow no worker. Aqui só registra o job.",
        "created_at": _now(),
    }
    with _lock:
        data = _load_json(CONVERSIONS_FILE, {"jobs": []})
        data["jobs"].append(entry)
        _save_json(CONVERSIONS_FILE, data)
    return {"ok": True, "job": entry}


def list_resume_templates() -> dict:
    return {"ok": True, "templates": RESUME_TEMPLATES}


def generate_resume_draft(user_id: str, template_key: str, display_name: str = "") -> dict:
    if template_key not in RESUME_TEMPLATES:
        return {"ok": False, "error": f"Template inválido. Use: {list(RESUME_TEMPLATES.keys())}"}
    tpl = RESUME_TEMPLATES[template_key]
    name = (display_name or user_id or "Usuário").strip()
    draft = {
        "template": template_key,
        "name": name,
        "generated_at": _now(),
        "sections": {
            s: f"[Preencher: {s} — dados do perfil {name}]"
            for s in tpl["sections"]
        },
        "hint": "Exporte como Markdown/PDF no front; dados reais vêm do progresso do usuário.",
    }
    return {"ok": True, "draft": draft}


# ===========================================================================
# 8. ENGAJAMENTO EXTRA
# ===========================================================================

REWARDS_FILE = NL_DIR / "surprise_rewards.json"
INVITES_FILE = NL_DIR / "invites.json"

SURPRISE_POOL = [
    {"type": "xp", "amount": 50, "label": "+50 XP surpresa"},
    {"type": "xp", "amount": 100, "label": "+100 XP raro"},
    {"type": "badge", "id": "lucky_day", "label": "Badge: Dia de Sorte"},
    {"type": "badge", "id": "night_owl", "label": "Badge: Coruja Noturna"},
    {"type": "cosmetic", "id": "frame_neon", "label": "Moldura neon no avatar"},
    {"type": "boost", "id": "2x_xp_1h", "label": "Boost 2x XP por 1 hora"},
]


def roll_surprise_reward(user_id: str, task_id: str = "") -> dict:
    idx = abs(hash(user_id + (task_id or _now()) + secrets.token_hex(2))) % len(SURPRISE_POOL)
    reward = dict(SURPRISE_POOL[idx])
    entry = {
        "id": f"rw_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "task_id": task_id or "any",
        "reward": reward,
        "at": _now(),
    }
    with _lock:
        data = _load_json(REWARDS_FILE, {"rolls": []})
        data["rolls"].append(entry)
        _save_json(REWARDS_FILE, data)
    return {"ok": True, "reward": reward, "entry": entry}


def create_invite(user_id: str) -> dict:
    code = secrets.token_urlsafe(6)[:8].upper()
    with _lock:
        data = _load_json(INVITES_FILE, {"invites": []})
        entry = {
            "code": code,
            "inviter": user_id,
            "uses": 0,
            "max_uses": 10,
            "xp_bonus_each": 75,
            "created_at": _now(),
        }
        data["invites"].append(entry)
        _save_json(INVITES_FILE, data)
    return {"ok": True, "invite": entry, "share_url": f"/join?ref={code}"}


def redeem_invite(code: str, new_user_id: str) -> dict:
    code = (code or "").strip().upper()
    with _lock:
        data = _load_json(INVITES_FILE, {"invites": []})
        for inv in data["invites"]:
            if inv["code"] == code and inv["uses"] < inv["max_uses"]:
                if inv["inviter"] == new_user_id:
                    return {"ok": False, "error": "Não pode usar o próprio convite"}
                inv["uses"] += 1
                inv.setdefault("redeemed_by", []).append({"user": new_user_id, "at": _now()})
                _save_json(INVITES_FILE, data)
                return {
                    "ok": True,
                    "xp_bonus": inv["xp_bonus_each"],
                    "for_inviter": inv["inviter"],
                    "for_invitee": new_user_id,
                    "message": f"Ambos ganham +{inv['xp_bonus_each']} XP!",
                }
    return {"ok": False, "error": "Convite inválido ou esgotado"}


# ===========================================================================
# 9. "UAU" DE VERDADE
# ===========================================================================

JARVIS_SESSIONS_FILE = NL_DIR / "jarvis_sessions.json"
ONBOARDING_FILE = NL_DIR / "onboarding.json"
ONECLICK_FILE = NL_DIR / "oneclick_games.json"


def jarvis_plan_route(user_id: str, intent: str) -> dict:
    """Assistente único: interpreta intenção e monta roteiro trilha + projeto + certificado."""
    intent = (intent or "").strip()
    if len(intent) < 5:
        return {"ok": False, "error": "Descreva o que quer aprender/fazer (mín. 5 chars)"}
    lower = intent.lower()
    track = "python_jogos"
    if any(w in lower for w in ("terror", "horror", "medo")):
        track = "jogos_terror"
    elif any(w in lower for w in ("loja", "e-commerce", "site de venda")):
        track = "site_loja"
    elif any(w in lower for w in ("segurança", "cyber", "hacker", "pentest")):
        track = "cyber_web"

    modules = INTEREST_CATALOG.get(track, INTEREST_CATALOG["python_jogos"])["modules"]
    plan = {
        "intent": intent,
        "track": track,
        "title": INTEREST_CATALOG.get(track, {}).get("title", track),
        "steps": [
            {"step": 1, "type": "trilha", "item": modules[0] if modules else "Intro"},
            {"step": 2, "type": "trilha", "item": modules[1] if len(modules) > 1 else "Prática"},
            {"step": 3, "type": "projeto", "item": f"Projeto guiado: {intent[:60]}"},
            {"step": 4, "type": "certificado", "item": f"Certificado de competência — {track}"},
        ],
        "estimated_hours": 8 + len(modules) * 2,
        "created_at": _now(),
    }
    with _lock:
        data = _load_json(JARVIS_SESSIONS_FILE, {"sessions": []})
        data["sessions"].append({"user_id": user_id, "plan": plan})
        _save_json(JARVIS_SESSIONS_FILE, data)
    return {"ok": True, "plan": plan, "assistant": "Jarvis"}


def cinematic_onboarding_state(user_id: str) -> dict:
    data = _load_json(ONBOARDING_FILE, {})
    done = data.get(user_id, {}).get("completed", False)
    return {
        "ok": True,
        "completed": done,
        "scenes": [
            {"id": 1, "title": "Bem-vindo ao estúdio", "duration_s": 4, "visual": "holograma Jarvis"},
            {"id": 2, "title": "Crie seu primeiro jogo em 1 clique", "duration_s": 5, "visual": "demo live"},
            {"id": 3, "title": "Trilhas + certificados", "duration_s": 4, "visual": "mapa de progresso"},
            {"id": 4, "title": "Você está no comando", "duration_s": 3, "visual": "painel central"},
        ],
        "hint": "Front: animar com CSS/Canvas; não é tutorial de texto.",
    }


def complete_onboarding(user_id: str) -> dict:
    with _lock:
        data = _load_json(ONBOARDING_FILE, {})
        data[user_id] = {"completed": True, "at": _now()}
        _save_json(ONBOARDING_FILE, data)
    return {"ok": True, "completed": True}


def one_click_game(user_id: str, idea: str) -> dict:
    """Modo um clique: ideia → jogo publicado (simulado em <2 min)."""
    idea = (idea or "").strip()
    if len(idea) < 4:
        return {"ok": False, "error": "Descreva a ideia do jogo"}
    gid = f"oc_{uuid.uuid4().hex[:10]}"
    steps_live = [
        "Analisando ideia…",
        "Gerando sprites e mapa…",
        "Montando regras e física…",
        "Publicando no estúdio…",
        "Pronto!",
    ]
    game = {
        "id": gid,
        "title": idea[:80],
        "user_id": user_id,
        "status": "published",
        "play_url": f"/play/{gid}",
        "steps_shown": steps_live,
        "elapsed_simulated_sec": 47,
        "created_at": _now(),
    }
    with _lock:
        data = _load_json(ONECLICK_FILE, {"games": []})
        data["games"].append(game)
        _save_json(ONECLICK_FILE, data)
    return {"ok": True, "game": game}


# ===========================================================================
# 10. IDENTIDADE VISUAL
# ===========================================================================

THEME_FILE = NL_DIR / "visual_theme.json"

DEFAULT_THEME = {
    "name": "jarvis-hologram",
    "style": "sci-fi/holograma",
    "primary": "#00e5ff",
    "secondary": "#7c4dff",
    "bg": "#050a12",
    "accent": "#00ffa3",
    "font": "Orbitron, Rajdhani, system-ui",
    "mascot": "Jarvis",
    "sounds_enabled": True,
    "consistent_all_pages": True,
}


def get_visual_theme(user_id: str = "") -> dict:
    data = _load_json(THEME_FILE, {})
    user_override = data.get(user_id) if user_id else None
    theme = {**DEFAULT_THEME, **(user_override or {})}
    return {"ok": True, "theme": theme}


def set_visual_theme(user_id: str, updates: dict) -> dict:
    with _lock:
        data = _load_json(THEME_FILE, {})
        cur = data.get(user_id) or {}
        for k in ("primary", "secondary", "bg", "accent", "sounds_enabled", "mascot"):
            if k in (updates or {}):
                cur[k] = updates[k]
        data[user_id] = cur
        _save_json(THEME_FILE, data)
    return get_visual_theme(user_id)


def jarvis_mascot_tip(context: str = "") -> dict:
    tips = [
        "Dica: complete a missão diária para manter o streak 🔥",
        "Você está perto de um novo certificado — mais um módulo!",
        "Experimente o modo um clique para publicar um protótipo rápido.",
        "Alto contraste e TTS estão em Acessibilidade se precisar.",
        "Convide um amigo e os dois ganham XP bônus.",
    ]
    idx = abs(hash(context or _now())) % len(tips)
    return {
        "ok": True,
        "mascot": "Jarvis",
        "mood": "helpful",
        "tip": tips[idx],
        "context": context or "global",
    }


# ===========================================================================
# 11. INTELIGÊNCIA REAL
# ===========================================================================

PATTERN_FILE = NL_DIR / "user_patterns.json"
FRUSTRATION_FILE = NL_DIR / "frustration.json"


def record_activity_pattern(user_id: str, hour: int | None = None, action: str = "") -> dict:
    h = hour if hour is not None else datetime.now(timezone.utc).hour
    with _lock:
        data = _load_json(PATTERN_FILE, {})
        u = data.get(user_id) or {"hours": {}, "actions": {}, "fail_counts": {}}
        u["hours"][str(h)] = u["hours"].get(str(h), 0) + 1
        if action:
            u["actions"][action] = u["actions"].get(action, 0) + 1
        data[user_id] = u
        _save_json(PATTERN_FILE, data)
    return {"ok": True, "recorded": True}


def suggest_next_step(user_id: str) -> dict:
    data = _load_json(PATTERN_FILE, {})
    u = data.get(user_id) or {"hours": {}, "actions": {}}
    hours = u.get("hours") or {}
    peak = max(hours.items(), key=lambda x: x[1])[0] if hours else None
    now_h = datetime.now(timezone.utc).hour
    suggestions = []
    if peak is not None and abs(int(peak) - now_h) <= 2:
        suggestions.append(f"Você costuma estudar por volta das {peak}h — ótimo momento para uma missão rápida.")
    else:
        suggestions.append("Que tal uma sessão curta de 15 min na trilha atual?")
    top_action = max(u.get("actions", {}).items(), key=lambda x: x[1])[0] if u.get("actions") else None
    if top_action:
        suggestions.append(f"Você interage muito com «{top_action}» — tem conteúdo novo relacionado.")
    suggestions.append("Modo um clique: transforme uma ideia em jogo publicado agora.")
    return {
        "ok": True,
        "peak_hour_utc": peak,
        "suggestions": suggestions,
        "message": suggestions[0] if suggestions else "Continue explorando o hub!",
    }


def report_exercise_fail(user_id: str, exercise_id: str) -> dict:
    with _lock:
        data = _load_json(FRUSTRATION_FILE, {})
        key = f"{user_id}::{exercise_id}"
        count = data.get(key, 0) + 1
        data[key] = count
        _save_json(FRUSTRATION_FILE, data)
    help_offered = count >= 3
    return {
        "ok": True,
        "exercise_id": exercise_id,
        "fail_count": count,
        "frustration_detected": help_offered,
        "help": {
            "message": "Vi que esse exercício está difícil. Quer uma dica, ver a solução passo a passo, ou tentar uma versão mais fácil?",
            "options": ["dica", "solucao_guiada", "versao_facil", "pular_por_agora"],
        } if help_offered else None,
    }


def reset_exercise_fails(user_id: str, exercise_id: str) -> dict:
    with _lock:
        data = _load_json(FRUSTRATION_FILE, {})
        key = f"{user_id}::{exercise_id}"
        data.pop(key, None)
        _save_json(FRUSTRATION_FILE, data)
    return {"ok": True, "reset": True}


# ===========================================================================
# 12. POLIMENTO — navegação unificada / checklist
# ===========================================================================

POLISH_FILE = NL_DIR / "polish_checklist.json"

DEFAULT_CHECKLIST = [
    {"id": "nav_unified", "label": "Unificar navegação num painel central (evitar menu lateral gigante)", "done": False},
    {"id": "dedupe_features", "label": "Revisar funções duplicadas/espalhadas em módulos diferentes", "done": False},
    {"id": "flow_zero", "label": "Testar fluxo do zero como usuário novo (onboarding → primeira trilha → jogo)", "done": False},
    {"id": "perf_app", "label": "Revisar performance (app.py / módulos carregando juntos)", "done": False},
    {"id": "a11y_pass", "label": "Passar checklist de acessibilidade (teclado, contraste, TTS)", "done": False},
    {"id": "visual_consistent", "label": "Tema holograma/sci-fi consistente em todas as páginas", "done": False},
    {"id": "api_docs", "label": "Documentar API pública mínima", "done": False},
]


def get_polish_checklist() -> dict:
    data = _load_json(POLISH_FILE, {})
    items = data.get("items") or list(DEFAULT_CHECKLIST)
    done = sum(1 for i in items if i.get("done"))
    return {
        "ok": True,
        "items": items,
        "progress": f"{done}/{len(items)}",
        "recommendation": "Conclua o Nível de Polimento antes de empilhar mais features (Nível 13+).",
    }


def toggle_polish_item(item_id: str, done: bool | None = None) -> dict:
    with _lock:
        data = _load_json(POLISH_FILE, {})
        items = data.get("items") or list(DEFAULT_CHECKLIST)
        for it in items:
            if it["id"] == item_id:
                it["done"] = (not it.get("done")) if done is None else bool(done)
                break
        data["items"] = items
        _save_json(POLISH_FILE, data)
    return get_polish_checklist()
