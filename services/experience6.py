"""JARVIS Experience/Auth/Performance/Game Lab 6.0 support.

This module augments existing systems. It does not replace authentication,
RBAC, Game Lab or diagnostics. Runtime metrics are intentionally bounded and
kept in memory; no secrets or raw request bodies are stored.
"""
from __future__ import annotations

import hashlib
import time
from collections import deque
from functools import wraps

from flask import jsonify, request, session

PERF = deque(maxlen=300)
SLOW_MS = 800
CRITICAL_MS = 2500
STEP_UP_TTL = 300

RISK = {
    "normal": {"label": "SESSION ACTIVE", "reauth": False},
    "important": {"label": "STEP-UP REQUIRED", "reauth": True},
    "critical": {"label": "STEP-UP REQUIRED", "reauth": True},
}

CHALLENGES = {
    "bug-hunter": {
        "context": "Um programa deveria somar pontos, mas o resultado não muda.",
        "learn": "variáveis, atribuição e depuração",
        "concept": "Uma variável guarda estado e uma atribuição altera esse estado.",
        "mission": "Encontre a linha que impede o score de ser atualizado.",
        "hints": ["Observe onde score recebe um valor.", "Compare =, == e +=.", "Teste uma pequena alteração e observe o resultado."],
        "extra": "Faça a correção funcionar para qualquer valor inicial de score.",
    },
    "code-runner": {
        "context": "O jogo precisa atualizar a pontuação quando o jogador coleta um item.",
        "learn": "eventos, condições e estado",
        "concept": "Eventos disparam lógica e condições decidem quando uma ação ocorre.",
        "mission": "Complete a lógica que soma 10 pontos ao coletar o item.",
        "hints": ["Comece pela condição de colisão.", "Depois procure a variável score.", "Use += para acrescentar ao valor existente."],
        "extra": "Adicione um contador de itens coletados.",
    },
    "password-defense": {
        "context": "Um formulário educacional aceita senhas muito fracas.",
        "learn": "validação e defesa de autenticação",
        "concept": "Validação reduz entradas inadequadas, mas senhas nunca devem ser armazenadas em texto puro.",
        "mission": "Defina regras de tamanho e bloqueie padrões obviamente fracos no sandbox.",
        "hints": ["Comece pelo tamanho mínimo.", "Procure padrões repetidos.", "Separe validação de armazenamento seguro."],
        "extra": "Explique por que hashing deve ocorrer no backend.",
    },
}

MODES = [
    ("GENERAL", "Assistente geral e navegação"),
    ("CODER", "Explicação e revisão de código"),
    ("TEACHER", "Ensino guiado por perguntas e dicas"),
    ("GAME DEV", "Mecânicas, jogos e Game Lab"),
    ("PROJECT", "Contexto e organização de projetos"),
    ("DEBUG", "Diagnóstico e reprodução de erros"),
    ("SECURITY", "Segurança defensiva e laboratório isolado"),
    ("CREATOR", "Criação de sites e experiências"),
]


def start_timer():
    return time.perf_counter()


def record_request(path: str, method: str, status: int, started: float):
    ms = round((time.perf_counter() - started) * 1000, 2)
    item = {"path": str(path)[:180], "method": method, "status": int(status), "ms": ms, "ts": time.time()}
    PERF.append(item)
    return item


def performance(limit=100):
    rows = list(PERF)[-max(1, min(int(limit or 100), 300)):]
    rows.reverse()
    slow = [r for r in rows if r["ms"] >= SLOW_MS]
    critical = [r for r in rows if r["ms"] >= CRITICAL_MS]
    avg = round(sum(r["ms"] for r in rows) / len(rows), 2) if rows else 0
    return {
        "samples": len(rows), "average_ms": avg, "slow": len(slow), "critical": len(critical),
        "status": "CRITICAL" if critical else "WARNING" if slow else "OK",
        "slow_ms": SLOW_MS, "critical_ms": CRITICAL_MS, "recent": rows,
    }


def session_trust():
    now = time.time()
    until = float(session.get("tf_step_up_until", 0) or 0)
    return {
        "authenticated": bool(session.get("tf_authed")),
        "state": "SESSION VERIFIED" if until > now else "SESSION ACTIVE",
        "step_up_until": int(until) if until > now else 0,
        "step_up_active": until > now,
    }


def grant_step_up(action: str, ttl: int = STEP_UP_TTL):
    session["tf_step_up_until"] = time.time() + max(30, min(int(ttl), 900))
    session["tf_step_up_action"] = hashlib.sha256(str(action).encode()).hexdigest()[:20]
    session.modified = True
    return session_trust()


def step_up_valid(action: str):
    until = float(session.get("tf_step_up_until", 0) or 0)
    expected = hashlib.sha256(str(action).encode()).hexdigest()[:20]
    return until > time.time() and session.get("tf_step_up_action") == expected


def clear_step_up():
    session.pop("tf_step_up_until", None)
    session.pop("tf_step_up_action", None)
    session.modified = True


def require_step_up(action: str):
    """Decorator for genuinely critical endpoints only.

    Normal authenticated navigation never passes through this decorator.
    """
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if step_up_valid(action):
                return fn(*args, **kwargs)
            return jsonify({
                "error": "Confirmação adicional necessária para esta ação.",
                "requires_step_up": True,
                "action": action,
            }), 428
        return wrapped
    return deco


def challenge_detail(cid):
    data = CHALLENGES.get(str(cid), {})
    if not data:
        return {"id": cid, "available": False}
    return {"id": cid, "available": True, **data}
