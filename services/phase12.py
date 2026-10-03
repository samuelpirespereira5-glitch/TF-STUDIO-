"""JARVIS Phase 12.0 — Educação expandida + Certificados próprios + Qualidade.

Partes 2 e 3: trilhas, labs, XP, certificados JARVIS, notas, health check.
Certificados são APENAS do JARVIS — nunca de terceiros (Curso em Vídeo, etc.).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths / storage (data/ isolado)
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CERT_DIR = DATA_DIR / "certificates"
NOTES_DIR = DATA_DIR / "study_notes"
CERT_DIR.mkdir(parents=True, exist_ok=True)
NOTES_DIR.mkdir(parents=True, exist_ok=True)

# Segredo local para assinatura de certificados (não é API key externa)
_CERT_SECRET = os.environ.get("JARVIS_CERT_SECRET") or "jarvis-local-cert-v1-not-for-production"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cert_code() -> str:
    year = datetime.now(timezone.utc).year
    return f"JARVIS-{year}-{secrets.token_hex(3).upper()}"


def _sign(payload: str) -> str:
    return hmac.new(_CERT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Trilhas
# ---------------------------------------------------------------------------
LEARNING_TRACKS: list[dict[str, Any]] = [
    {
        "id": "python",
        "titulo": "Trilha Python",
        "icon": "🐍",
        "descricao": "Do zero à aplicação: lógica, sintaxe, estruturas, POO, APIs e projetos.",
        "nivel": "iniciante → intermediário",
        "carga_horas": 40,
        "requisitos": [],
        "modulos": [
            {"id": "py-logic", "titulo": "Lógica", "aulas": ["Pensamento computacional", "Algoritmos", "Fluxogramas"], "exercicios": 3, "desafios": 1},
            {"id": "py-basico", "titulo": "Python básico", "aulas": ["Instalação", "IDLE", "print"], "exercicios": 4, "desafios": 1},
            {"id": "py-vars", "titulo": "Variáveis", "aulas": ["Tipos", "Atribuição"], "exercicios": 5, "desafios": 1},
            {"id": "py-cond", "titulo": "Condições", "aulas": ["if/elif/else", "Operadores"], "exercicios": 5, "desafios": 2},
            {"id": "py-loops", "titulo": "Loops", "aulas": ["for", "while", "range"], "exercicios": 6, "desafios": 2},
            {"id": "py-funcs", "titulo": "Funções", "aulas": ["def", "parâmetros", "return"], "exercicios": 5, "desafios": 2},
            {"id": "py-lists", "titulo": "Listas", "aulas": ["índices", "métodos"], "exercicios": 5, "desafios": 2},
            {"id": "py-dicts", "titulo": "Dicionários", "aulas": ["chave-valor", "métodos"], "exercicios": 4, "desafios": 1},
            {"id": "py-files", "titulo": "Arquivos", "aulas": ["open", "read/write"], "exercicios": 3, "desafios": 1},
            {"id": "py-oop", "titulo": "POO", "aulas": ["Classes", "objetos"], "exercicios": 4, "desafios": 2},
            {"id": "py-apis", "titulo": "APIs", "aulas": ["requests", "JSON"], "exercicios": 3, "desafios": 1},
            {"id": "py-db", "titulo": "Banco de dados", "aulas": ["SQLite", "CRUD"], "exercicios": 3, "desafios": 1},
            {"id": "py-proj", "titulo": "Projetos", "aulas": ["CLI", "mini web"], "exercicios": 0, "desafios": 3, "projetos": True},
        ],
    },
    {
        "id": "web",
        "titulo": "Trilha Web",
        "icon": "🌐",
        "descricao": "HTML, CSS, JavaScript, DOM, APIs e projetos front-end.",
        "nivel": "iniciante → intermediário",
        "carga_horas": 30,
        "requisitos": [],
        "modulos": [
            {"id": "web-html", "titulo": "HTML", "aulas": ["Estrutura", "Semântica", "Formulários"], "exercicios": 5, "desafios": 2},
            {"id": "web-css", "titulo": "CSS", "aulas": ["Seletores", "Flex/Grid", "Responsivo"], "exercicios": 6, "desafios": 2},
            {"id": "web-js", "titulo": "JavaScript", "aulas": ["Variáveis", "Funções", "Eventos"], "exercicios": 6, "desafios": 2},
            {"id": "web-dom", "titulo": "DOM", "aulas": ["Selecionar", "Manipular"], "exercicios": 5, "desafios": 2},
            {"id": "web-apis", "titulo": "APIs no browser", "aulas": ["fetch", "JSON"], "exercicios": 3, "desafios": 1},
            {"id": "web-proj", "titulo": "Projetos", "aulas": ["Landing", "To-do"], "exercicios": 0, "desafios": 3, "projetos": True},
        ],
    },
    {
        "id": "javascript",
        "titulo": "Trilha JavaScript",
        "icon": "⚡",
        "descricao": "JS moderno: sintaxe, DOM, assíncrono e módulos.",
        "nivel": "iniciante → intermediário",
        "carga_horas": 25,
        "requisitos": ["web"],
        "modulos": [
            {"id": "js-fund", "titulo": "Fundamentos", "aulas": ["Tipos", "Controle de fluxo"], "exercicios": 5, "desafios": 2},
            {"id": "js-fn", "titulo": "Funções e escopo", "aulas": ["Arrow", "closures"], "exercicios": 4, "desafios": 2},
            {"id": "js-arr", "titulo": "Arrays e objetos", "aulas": ["map/filter/reduce"], "exercicios": 5, "desafios": 2},
            {"id": "js-async", "titulo": "Assíncrono", "aulas": ["Promises", "async/await"], "exercicios": 4, "desafios": 2},
            {"id": "js-mod", "titulo": "Módulos e projetos", "aulas": ["ES modules"], "exercicios": 2, "desafios": 2, "projetos": True},
        ],
    },
    {
        "id": "algoritmos",
        "titulo": "Trilha Algoritmos",
        "icon": "⚙️",
        "descricao": "Busca, ordenação e estruturas de dados.",
        "nivel": "iniciante → intermediário",
        "carga_horas": 20,
        "requisitos": ["python"],
        "modulos": [
            {"id": "algo-intro", "titulo": "Introdução", "aulas": ["O que é algoritmo", "Big-O"], "exercicios": 3, "desafios": 1},
            {"id": "algo-search", "titulo": "Busca", "aulas": ["Linear", "Binária"], "exercicios": 4, "desafios": 2},
            {"id": "algo-sort", "titulo": "Ordenação", "aulas": ["Bubble", "Selection", "Insertion"], "exercicios": 5, "desafios": 2},
            {"id": "algo-struct", "titulo": "Estruturas", "aulas": ["Pilha", "Fila", "Árvore"], "exercicios": 5, "desafios": 2},
            {"id": "algo-rec", "titulo": "Recursão", "aulas": ["Caso base", "Fatorial"], "exercicios": 4, "desafios": 2},
        ],
    },
    {
        "id": "gamedev",
        "titulo": "Trilha Desenvolvimento de Jogos",
        "icon": "🎮",
        "descricao": "Game loop, colisão, estados e Game Lab.",
        "nivel": "iniciante → intermediário",
        "carga_horas": 25,
        "requisitos": ["javascript"],
        "modulos": [
            {"id": "gd-loop", "titulo": "Game loop", "aulas": ["update/draw", "estados"], "exercicios": 3, "desafios": 1},
            {"id": "gd-input", "titulo": "Entrada", "aulas": ["Teclado", "Touch"], "exercicios": 3, "desafios": 1},
            {"id": "gd-physics", "titulo": "Física simples", "aulas": ["Velocidade", "Colisão"], "exercicios": 4, "desafios": 2},
            {"id": "gd-levels", "titulo": "Níveis e score", "aulas": ["Progressão", "vidas"], "exercicios": 3, "desafios": 1},
            {"id": "gd-proj", "titulo": "Projetos no Game Lab", "aulas": ["Snake", "Pong"], "exercicios": 0, "desafios": 3, "projetos": True},
        ],
    },
    {
        "id": "ia",
        "titulo": "Trilha IA",
        "icon": "🤖",
        "descricao": "Conceitos de IA, prompts e uso ético.",
        "nivel": "iniciante",
        "carga_horas": 12,
        "requisitos": [],
        "modulos": [
            {"id": "ia-intro", "titulo": "O que é IA", "aulas": ["Tipos de IA", "Limitações"], "exercicios": 2, "desafios": 1},
            {"id": "ia-prompt", "titulo": "Prompts", "aulas": ["Clareza", "Contexto"], "exercicios": 4, "desafios": 2},
            {"id": "ia-ethics", "titulo": "Ética", "aulas": ["Privacidade", "Uso responsável"], "exercicios": 2, "desafios": 1},
            {"id": "ia-build", "titulo": "Integrar IA", "aulas": ["APIs de modelos", "JARVIS mentor"], "exercicios": 2, "desafios": 2, "projetos": True},
        ],
    },
]


def list_tracks() -> list[dict[str, Any]]:
    out = []
    for t in LEARNING_TRACKS:
        mods = t["modulos"]
        out.append({
            "id": t["id"],
            "titulo": t["titulo"],
            "icon": t.get("icon", ""),
            "descricao": t["descricao"],
            "nivel": t["nivel"],
            "carga_horas": t.get("carga_horas", 0),
            "requisitos": t.get("requisitos") or [],
            "modulos_count": len(mods),
            "aulas_count": sum(len(m.get("aulas") or []) for m in mods),
            "exercicios_count": sum(m.get("exercicios") or 0 for m in mods),
            "desafios_count": sum(m.get("desafios") or 0 for m in mods),
        })
    return out


def track_by_id(tid: str) -> dict[str, Any] | None:
    for t in LEARNING_TRACKS:
        if t["id"] == tid:
            return dict(t)
    return None


# ---------------------------------------------------------------------------
# Debug / Algo / API / DB (Parte 2)
# ---------------------------------------------------------------------------
DEBUG_EXERCISES: list[dict[str, Any]] = [
    {
        "id": "dbg-py-name",
        "titulo": "NameError: variável inexistente",
        "linguagem": "python",
        "dificuldade": "fácil",
        "objetivo": "Encontre e corrija o erro de nome.",
        "codigo_quebrado": "x = 10\ny = 5\nprint(x + z)",
        "erro_esperado": "NameError",
        "dicas": ["Qual nome não existe?", "Compare variáveis criadas com as usadas."],
        "solucao": "x = 10\ny = 5\nprint(x + y)",
        "explicacao": "A variável `z` nunca foi definida.",
        "testes": [{"expect_contains": "15"}],
        "xp": 15,
    },
    {
        "id": "dbg-py-indent",
        "titulo": "IndentationError",
        "linguagem": "python",
        "dificuldade": "fácil",
        "objetivo": "Corrija a indentação do if.",
        "codigo_quebrado": "idade = 18\nif idade >= 18:\nprint('maior')\nelse:\nprint('menor')",
        "erro_esperado": "IndentationError",
        "dicas": ["Bloco após `:` precisa indentação (4 espaços)."],
        "solucao": "idade = 18\nif idade >= 18:\n    print('maior')\nelse:\n    print('menor')",
        "explicacao": "Sem indentação o interpretador não sabe o bloco do if.",
        "testes": [{"expect_contains": "maior"}],
        "xp": 15,
    },
    {
        "id": "dbg-py-colon",
        "titulo": "Falta o dois-pontos",
        "linguagem": "python",
        "dificuldade": "fácil",
        "objetivo": "SyntaxError por falta de `:`",
        "codigo_quebrado": "for i in range(3)\n    print(i)",
        "erro_esperado": "SyntaxError",
        "dicas": ["for/if/while/def terminam com `:`."],
        "solucao": "for i in range(3):\n    print(i)",
        "explicacao": "O `:` abre o bloco indentado.",
        "testes": [{"expect_contains": "0"}],
        "xp": 10,
    },
    {
        "id": "dbg-js-eq",
        "titulo": "Atribuição no lugar de comparação",
        "linguagem": "javascript",
        "dificuldade": "médio",
        "objetivo": "O if sempre verdadeiro por causa de `=`.",
        "codigo_quebrado": "let score = 50;\nif (score = 100) {\n  console.log('perfeito');\n} else {\n  console.log('continue');\n}",
        "erro_esperado": "lógica",
        "dicas": ["`=` atribui; `===` compara."],
        "solucao": "let score = 50;\nif (score === 100) {\n  console.log('perfeito');\n} else {\n  console.log('continue');\n}",
        "explicacao": "Use `===` para comparar.",
        "testes": [{"expect_contains": "continue"}],
        "xp": 20,
    },
    {
        "id": "dbg-js-const",
        "titulo": "Reatribuir const",
        "linguagem": "javascript",
        "dificuldade": "fácil",
        "objetivo": "TypeError ao reatribuir const.",
        "codigo_quebrado": "const n = 1;\nn = 2;\nconsole.log(n);",
        "erro_esperado": "TypeError",
        "dicas": ["Use `let` se precisar reatribuir."],
        "solucao": "let n = 1;\nn = 2;\nconsole.log(n);",
        "explicacao": "`const` não permite reatribuição.",
        "testes": [{"expect_contains": "2"}],
        "xp": 15,
    },
    {
        "id": "dbg-html-tag",
        "titulo": "Tag não fechada",
        "linguagem": "html",
        "dificuldade": "fácil",
        "objetivo": "Feche a tag corretamente.",
        "codigo_quebrado": "<h1>Título\n<p>Texto</p>",
        "erro_esperado": "estrutura",
        "dicas": ["Toda tag de abertura deve ter fechamento."],
        "solucao": "<h1>Título</h1>\n<p>Texto</p>",
        "explicacao": "HTML mal fechado quebra layout e acessibilidade.",
        "testes": [],
        "xp": 10,
    },
]


def list_debug_exercises(lang: str | None = None) -> list[dict[str, Any]]:
    items = DEBUG_EXERCISES
    if lang:
        items = [x for x in items if x["linguagem"] == lang]
    return [{k: v for k, v in x.items() if k != "solucao"} for x in items]


def debug_by_id(eid: str, reveal: bool = False) -> dict[str, Any] | None:
    for x in DEBUG_EXERCISES:
        if x["id"] == eid:
            d = dict(x)
            if not reveal:
                d.pop("solucao", None)
            return d
    return None


def check_debug(eid: str, code: str) -> dict[str, Any]:
    ex = next((x for x in DEBUG_EXERCISES if x["id"] == eid), None)
    if not ex:
        return {"ok": False, "error": "Exercício não encontrado"}
    code_n = (code or "").strip().replace("\r\n", "\n")
    sol_n = (ex.get("solucao") or "").strip().replace("\r\n", "\n")
    if code_n == sol_n:
        return {"ok": True, "xp": ex.get("xp", 10), "message": "Correto! " + (ex.get("explicacao") or "")}
    broken = (ex.get("codigo_quebrado") or "").strip().replace("\r\n", "\n")
    if code_n != broken and len(code_n) >= max(8, len(sol_n) // 2):
        return {"ok": False, "partial": True, "message": "Ainda não está igual à solução. Revise as dicas.", "hint": (ex.get("dicas") or [""])[-1]}
    return {"ok": False, "message": "Continue investigando.", "hint": (ex.get("dicas") or [""])[0]}


ALGO_LAB: list[dict[str, Any]] = [
    {"id": "linear-search", "titulo": "Busca Linear", "categoria": "busca", "descricao": "Percorre a lista até achar o valor.", "complexidade": "O(n)", "visual": "array", "passos_demo": [3, 1, 4, 1, 5, 9, 2, 6], "alvo_demo": 9, "pseudocodigo": "para i de 0 até n-1:\n  se a[i] == alvo: retorne i\nretorne -1"},
    {"id": "binary-search", "titulo": "Busca Binária", "categoria": "busca", "descricao": "Lista ordenada: descarta metade a cada passo.", "complexidade": "O(log n)", "visual": "array", "passos_demo": [1, 2, 3, 4, 5, 6, 7, 8, 9], "alvo_demo": 6, "pseudocodigo": "esq=0; dir=n-1\nenquanto esq<=dir:\n  m=(esq+dir)//2\n  se a[m]==alvo: retorne m\n  se a[m]<alvo: esq=m+1 senão dir=m-1"},
    {"id": "bubble-sort", "titulo": "Bubble Sort", "categoria": "ordenacao", "descricao": "Troca pares adjacentes fora de ordem.", "complexidade": "O(n²)", "visual": "array", "passos_demo": [5, 1, 4, 2, 8], "pseudocodigo": "repita até não haver trocas:\n  para i de 0 até n-2:\n    se a[i] > a[i+1]: troque"},
    {"id": "selection-sort", "titulo": "Selection Sort", "categoria": "ordenacao", "descricao": "Coloca o menor restante na posição.", "complexidade": "O(n²)", "visual": "array", "passos_demo": [64, 25, 12, 22, 11], "pseudocodigo": "para i de 0 até n-2:\n  min=i\n  para j de i+1 até n-1:\n    se a[j]<a[min]: min=j\n  troque a[i] e a[min]"},
    {"id": "stack", "titulo": "Pilha (Stack)", "categoria": "estrutura", "descricao": "LIFO.", "complexidade": "push/pop O(1)", "visual": "stack", "passos_demo": ["push A", "push B", "pop", "push C"], "pseudocodigo": "push(x): empilha\npop(): remove do topo"},
    {"id": "queue", "titulo": "Fila (Queue)", "categoria": "estrutura", "descricao": "FIFO.", "complexidade": "O(1)", "visual": "queue", "passos_demo": ["enqueue A", "enqueue B", "dequeue"], "pseudocodigo": "enqueue(x): fim\ndequeue(): início"},
    {"id": "recursion-factorial", "titulo": "Recursão — Fatorial", "categoria": "recursao", "descricao": "Função que chama a si mesma.", "complexidade": "O(n)", "visual": "recursion", "passos_demo": [5], "pseudocodigo": "fat(n):\n  se n<=1: retorne 1\n  retorne n * fat(n-1)"},
]


def _algo_all() -> list[dict[str, Any]]:
    items = list(ALGO_LAB)
    try:
        from services import phase13
        seen = {x["id"] for x in items}
        for x in phase13.algo_extras():
            if x["id"] not in seen:
                items.append(x)
                seen.add(x["id"])
    except Exception:
        pass
    return items


def list_algorithms(cat: str | None = None) -> list[dict[str, Any]]:
    items = _algo_all()
    if cat:
        items = [x for x in items if x["categoria"] == cat]
    return items


def algorithm_by_id(aid: str) -> dict[str, Any] | None:
    for x in _algo_all():
        if x["id"] == aid:
            return dict(x)
    return None


API_SCENARIOS: list[dict[str, Any]] = [
    {"id": "get-users", "titulo": "GET lista", "metodo": "GET", "path": "/api/users", "descricao": "Lista JSON.", "request": {"method": "GET", "path": "/api/users"}, "response": {"status": 200, "body": [{"id": 1, "name": "Ana"}]}, "ensina": ["GET", "200", "JSON"]},
    {"id": "get-one", "titulo": "GET por id", "metodo": "GET", "path": "/api/users/1", "descricao": "200 ou 404.", "request": {"method": "GET", "path": "/api/users/1"}, "response": {"status": 200, "body": {"id": 1, "name": "Ana"}}, "ensina": ["path params", "404"]},
    {"id": "post-create", "titulo": "POST criar", "metodo": "POST", "path": "/api/users", "descricao": "201 Created.", "request": {"method": "POST", "path": "/api/users", "body": {"name": "Carla"}}, "response": {"status": 201, "body": {"id": 3, "name": "Carla"}}, "ensina": ["POST", "201"]},
    {"id": "put-update", "titulo": "PUT atualizar", "metodo": "PUT", "path": "/api/users/1", "descricao": "Substitui recurso.", "request": {"method": "PUT", "path": "/api/users/1", "body": {"name": "Ana S"}}, "response": {"status": 200, "body": {"id": 1, "name": "Ana S"}}, "ensina": ["PUT"]},
    {"id": "delete", "titulo": "DELETE", "metodo": "DELETE", "path": "/api/users/2", "descricao": "204.", "request": {"method": "DELETE", "path": "/api/users/2"}, "response": {"status": 204, "body": None}, "ensina": ["DELETE", "204"]},
]


def list_api_scenarios() -> list[dict[str, Any]]:
    return API_SCENARIOS


DB_SCHEMA = {
    "tables": {
        "alunos": {
            "columns": ["id", "nome", "idade", "curso"],
            "rows": [
                {"id": 1, "nome": "Ana", "idade": 20, "curso": "Python"},
                {"id": 2, "nome": "Bruno", "idade": 22, "curso": "Web"},
                {"id": 3, "nome": "Carla", "idade": 19, "curso": "Python"},
            ],
        },
        "notas": {
            "columns": ["id", "aluno_id", "disciplina", "nota"],
            "rows": [
                {"id": 1, "aluno_id": 1, "disciplina": "Lógica", "nota": 9.0},
                {"id": 2, "aluno_id": 2, "disciplina": "HTML", "nota": 7.0},
            ],
        },
    },
    "examples": [
        {"id": "sel-all", "sql": "SELECT * FROM alunos;", "titulo": "Listar todos"},
        {"id": "sel-where", "sql": "SELECT nome FROM alunos WHERE curso = 'Python';", "titulo": "WHERE"},
        {"id": "join", "sql": "SELECT a.nome, n.disciplina, n.nota FROM alunos a JOIN notas n ON a.id = n.aluno_id;", "titulo": "JOIN"},
        {"id": "insert", "sql": "INSERT INTO alunos (nome, idade, curso) VALUES ('Elena', 21, 'Web');", "titulo": "INSERT"},
    ],
}


def db_lab_schema() -> dict[str, Any]:
    return DB_SCHEMA


def db_lab_run_demo(sql: str) -> dict[str, Any]:
    s = (sql or "").strip().rstrip(";").lower()
    tables = DB_SCHEMA["tables"]
    if s.startswith("select") and "from alunos" in s and "join" not in s:
        rows = list(tables["alunos"]["rows"])
        if "python" in s:
            rows = [r for r in rows if r["curso"].lower() == "python"]
        if "nome from" in s:
            rows = [{"nome": r["nome"]} for r in rows]
        return {"ok": True, "rows": rows, "message": "Consulta simulada (demo isolada)."}
    if s.startswith("select") and "join" in s:
        alunos = {r["id"]: r for r in tables["alunos"]["rows"]}
        out = []
        for n in tables["notas"]["rows"]:
            a = alunos.get(n["aluno_id"])
            if a:
                out.append({"nome": a["nome"], "disciplina": n["disciplina"], "nota": n["nota"]})
        return {"ok": True, "rows": out, "message": "JOIN simulado."}
    if s.startswith(("insert", "update", "delete")):
        return {"ok": True, "rows": [], "message": "Comando de escrita em modo demo (não altera o servidor)."}
    return {"ok": False, "error": "Demo aceita SELECT em alunos/notas e exemplos de escrita. Use os botões."}


XP_LEVELS = [
    (0, "Iniciante"),
    (50, "Aprendiz"),
    (150, "Praticante"),
    (350, "Desenvolvedor Jr"),
    (700, "Desenvolvedor"),
    (1200, "Avançado"),
    (2000, "Mentor"),
]


def xp_info(xp: int) -> dict[str, Any]:
    xp = max(0, int(xp or 0))
    level_name = XP_LEVELS[0][1]
    level_idx = 0
    for i, (need, name) in enumerate(XP_LEVELS):
        if xp >= need:
            level_name = name
            level_idx = i
    next_need = XP_LEVELS[level_idx + 1][0] if level_idx + 1 < len(XP_LEVELS) else None
    base = XP_LEVELS[level_idx][0]
    return {
        "xp": xp,
        "level": level_idx + 1,
        "title": level_name,
        "next_xp": next_need,
        "progress_to_next": None if next_need is None else min(100, int(100 * (xp - base) / max(1, next_need - base))),
    }


EXTRA_CHALLENGES = [
    {"id": "daily-logic-1", "tipo": "diario", "titulo": "Some de 1 a N", "objetivo": "Some de 1 até 10 e imprima o total.", "linguagem": "python", "dificuldade": "fácil", "xp": 20, "dicas": ["range(1, 11)"], "testes": [{"expect_contains": "55"}]},
    {"id": "weekly-web-1", "tipo": "semanal", "titulo": "Card CSS com hover", "objetivo": "Card com sombra e hover.", "linguagem": "html", "dificuldade": "médio", "xp": 40, "dicas": ["box-shadow", ":hover"], "testes": []},
    {"id": "lang-js-map", "tipo": "linguagem", "titulo": "Dobrar com map", "objetivo": "map para dobrar [1,2,3].", "linguagem": "javascript", "dificuldade": "fácil", "xp": 25, "dicas": ["arr.map(n => n * 2)"], "testes": [{"expect_contains": "map"}]},
]


def list_extra_challenges(tipo: str | None = None) -> list[dict[str, Any]]:
    items = EXTRA_CHALLENGES
    if tipo:
        items = [x for x in items if x["tipo"] == tipo]
    return items


GAME_SOURCE = {
    "snake": {
        "html": '<canvas id="c" width="400" height="400"></canvas>',
        "css": "canvas{background:#0d1117;border:2px solid #22c55e}",
        "js": "const grid=20;let snake=[{x:10,y:10}],dir={x:1,y:0};\n// arrays, colisão, game loop, score",
        "ensina": "Arrays, objetos, colisão, game loop, pontuação.",
    },
    "pong": {
        "html": '<canvas id="c" width="480" height="320"></canvas>',
        "css": "canvas{background:#111}",
        "js": "let ball={x:240,y:160,vx:3,vy:2};\n// física, input, placar",
        "ensina": "Velocidade, colisão, input, placar.",
    },
    "memory": {
        "html": '<div id="board" class="grid"></div>',
        "css": ".grid{display:grid;grid-template-columns:repeat(4,80px);gap:8px}",
        "js": "const cards=[1,1,2,2,3,3,4,4].sort(()=>Math.random()-0.5);\n// estado, comparação, embaralhar",
        "ensina": "Estado, arrays, pares, embaralhamento.",
    },
}


def game_source(game_id: str) -> dict[str, Any]:
    s = GAME_SOURCE.get(game_id)
    if not s:
        return {"id": game_id, "html": "<!-- template -->", "css": "/* HUD */", "js": "// game loop", "ensina": "Game loop, estado, input, colisão."}
    return {"id": game_id, **s}


PROJECT_TEMPLATES = [
    {"id": "todo-html", "name": "To-do List", "lang": "html", "level": "iniciante", "desc": "Lista com localStorage"},
    {"id": "calc-js", "name": "Calculadora", "lang": "javascript", "level": "iniciante", "desc": "Calculadora no browser"},
    {"id": "snake-remix", "name": "Snake remix", "lang": "javascript", "level": "intermediário", "desc": "Base do Snake"},
    {"id": "cli-python", "name": "CLI Python", "lang": "python", "level": "iniciante", "desc": "Script interativo"},
]


def project_templates() -> list[dict[str, Any]]:
    return PROJECT_TEMPLATES


# ---------------------------------------------------------------------------
# Certificados JARVIS (próprios apenas)
# ---------------------------------------------------------------------------
def issue_certificate(
    user_name: str,
    track_id: str,
    modules_done: list[str] | None = None,
    project_name: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Emite certificado próprio do JARVIS. Nunca de terceiros."""
    track = track_by_id(track_id)
    if not track:
        return {"ok": False, "error": "Trilha JARVIS não encontrada. Certificados só para trilhas próprias."}
    name = (user_name or "Estudante").strip()[:80] or "Estudante"
    code = _cert_code()
    issued = _now_iso()
    modules = modules_done or [m["id"] for m in track.get("modulos") or []]
    payload = f"{code}|{name}|{track_id}|{issued}"
    signature = _sign(payload)
    cert = {
        "ok": True,
        "id": code,
        "codigo": code,
        "titulo": "Certificado de conclusão — JARVIS",
        "emissor": "JARVIS",
        "aviso": "Este é um certificado próprio do sistema JARVIS. Não é certificado do Curso em Vídeo, Gustavo Guanabara, YouTube nem de qualquer instituição externa.",
        "nome": name,
        "user_id": user_id or "",
        "trilha_id": track_id,
        "trilha": track["titulo"],
        "data": issued,
        "carga_horas": track.get("carga_horas", 0),
        "modulos_concluidos": modules,
        "modulos_count": len(modules),
        "projeto_final": project_name or "",
        "assinatura": signature,
        "validacao_url": f"/certificados/verificar/{code}",
        "status": "valido",
    }
    path = CERT_DIR / f"{code}.json"
    path.write_text(json.dumps(cert, ensure_ascii=False, indent=2), encoding="utf-8")
    return cert


def verify_certificate(code: str) -> dict[str, Any]:
    code = (code or "").strip().upper()
    if not code.startswith("JARVIS-"):
        return {"valido": False, "status": "invalido", "mensagem": "Código inválido. Formato esperado: JARVIS-ANO-XXXXXX"}
    path = CERT_DIR / f"{code}.json"
    if not path.exists():
        return {"valido": False, "status": "invalido", "mensagem": "Certificado não encontrado.", "codigo": code}
    try:
        cert = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"valido": False, "status": "erro", "mensagem": "Arquivo de certificado corrompido."}
    payload = f"{cert.get('codigo')}|{cert.get('nome')}|{cert.get('trilha_id')}|{cert.get('data')}"
    expected = _sign(payload)
    if not hmac.compare_digest(str(cert.get("assinatura") or ""), expected):
        return {"valido": False, "status": "assinatura_invalida", "mensagem": "Assinatura não confere. Certificado pode ter sido alterado.", "codigo": code}
    return {
        "valido": True,
        "status": "valido",
        "codigo": cert.get("codigo"),
        "nome": cert.get("nome"),
        "trilha": cert.get("trilha"),
        "trilha_id": cert.get("trilha_id"),
        "data": cert.get("data"),
        "carga_horas": cert.get("carga_horas"),
        "modulos_count": cert.get("modulos_count"),
        "projeto_final": cert.get("projeto_final"),
        "titulo": cert.get("titulo"),
        "emissor": "JARVIS",
        "aviso": cert.get("aviso"),
        "validacao_url": cert.get("validacao_url"),
    }


def list_certificates(user_id: str | None = None) -> list[dict[str, Any]]:
    out = []
    for p in sorted(CERT_DIR.glob("JARVIS-*.json"), reverse=True):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            if user_id and c.get("user_id") and c.get("user_id") != user_id:
                continue
            out.append({
                "codigo": c.get("codigo"),
                "nome": c.get("nome"),
                "trilha": c.get("trilha"),
                "data": c.get("data"),
                "status": "valido",
            })
        except Exception:
            continue
    return out[:50]


# ---------------------------------------------------------------------------
# Notas de estudo
# ---------------------------------------------------------------------------
def _notes_path(uid: str) -> Path:
    safe = "".join(c for c in (uid or "anon") if c.isalnum() or c in "-_")[:64] or "anon"
    return NOTES_DIR / f"{safe}.json"


def get_notes(uid: str) -> list[dict[str, Any]]:
    p = _notes_path(uid)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_note(uid: str, note: dict[str, Any]) -> dict[str, Any]:
    notes = get_notes(uid)
    item = {
        "id": note.get("id") or secrets.token_hex(4),
        "tipo": note.get("tipo") or "nota",  # nota | pergunta | favorito | trecho | link | codigo
        "titulo": (note.get("titulo") or "")[:120],
        "conteudo": (note.get("conteudo") or "")[:5000],
        "curso": (note.get("curso") or "")[:80],
        "playlist": (note.get("playlist") or "")[:80],
        "aula": (note.get("aula") or "")[:120],
        "created_at": note.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
    }
    # update or append
    found = False
    for i, n in enumerate(notes):
        if n.get("id") == item["id"]:
            notes[i] = item
            found = True
            break
    if not found:
        notes.insert(0, item)
    notes = notes[:200]
    _notes_path(uid).write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def delete_note(uid: str, note_id: str) -> bool:
    notes = get_notes(uid)
    new = [n for n in notes if n.get("id") != note_id]
    if len(new) == len(notes):
        return False
    _notes_path(uid).write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Health / quality check
# ---------------------------------------------------------------------------
def health_check() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str = ""):
        checks.append({"name": name, "status": status, "detail": detail})

    # Data dirs
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        add("data_dir", "ONLINE", str(DATA_DIR))
    except Exception as e:
        add("data_dir", "ERROR", str(e))

    try:
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        add("certificates_dir", "ONLINE", str(CERT_DIR))
    except Exception as e:
        add("certificates_dir", "ERROR", str(e))

    # Tracks
    add("tracks", "ONLINE" if LEARNING_TRACKS else "ERROR", f"{len(LEARNING_TRACKS)} trilhas")

    # Phase11
    try:
        from services import phase11
        ov = phase11.overview_phase11() if hasattr(phase11, "overview_phase11") else {}
        add("phase11", "ONLINE", str(ov)[:120])
    except Exception as e:
        add("phase11", "WARNING", str(e))

    # AI key presence (não expõe o valor)
    try:
        from services import config as cfg
        has_key = bool(getattr(cfg, "get_api_key", lambda: None)())
        add("ai_api_key", "ONLINE" if has_key else "WARNING", "configurada" if has_key else "não configurada — chat pode falhar")
    except Exception:
        add("ai_api_key", "WARNING", "não foi possível verificar")

    # Auth module
    try:
        from services import auth
        add("auth_module", "ONLINE", "carregado")
    except Exception as e:
        add("auth_module", "ERROR", str(e))

    # Game lab
    try:
        from services import game_lab
        add("game_lab", "ONLINE", "carregado")
    except Exception as e:
        add("game_lab", "WARNING", str(e))

    # Static files critical
    root = Path(__file__).resolve().parent.parent
    for rel in ["static/js/jarvis.js", "static/js/phase11.js", "templates/education.html", "templates/jarvis.html"]:
        p = root / rel
        add(f"file:{rel}", "ONLINE" if p.exists() else "ERROR", "ok" if p.exists() else "ausente")

    online = sum(1 for c in checks if c["status"] == "ONLINE")
    warn = sum(1 for c in checks if c["status"] == "WARNING")
    err = sum(1 for c in checks if c["status"] == "ERROR")
    overall = "ONLINE" if err == 0 and warn == 0 else ("WARNING" if err == 0 else "ERROR")
    return {
        "overall": overall,
        "online": online,
        "warning": warn,
        "error": err,
        "checks": checks,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Busca + overview
# ---------------------------------------------------------------------------
def search_all(q: str) -> dict[str, Any]:
    qn = (q or "").strip().lower()
    if not qn:
        return {"query": q, "results": []}
    results: list[dict[str, Any]] = []
    for t in LEARNING_TRACKS:
        if qn in (t["titulo"] + " " + t["descricao"]).lower():
            results.append({"type": "trilha", "id": t["id"], "title": t["titulo"]})
        for m in t["modulos"]:
            if qn in m["titulo"].lower() or any(qn in a.lower() for a in m.get("aulas") or []):
                results.append({"type": "modulo", "id": m["id"], "title": m["titulo"], "track": t["id"]})
    for d in DEBUG_EXERCISES:
        if qn in d["titulo"].lower():
            results.append({"type": "debug", "id": d["id"], "title": d["titulo"]})
    for a in ALGO_LAB:
        if qn in a["titulo"].lower():
            results.append({"type": "algoritmo", "id": a["id"], "title": a["titulo"]})
    try:
        from services import phase11
        p11 = phase11.search_edu(q)
        for r in (p11.get("results") or p11.get("items") or []):
            if isinstance(r, dict):
                results.append(r)
    except Exception:
        pass
    return {"query": q, "results": results[:40]}


def overview_phase12() -> dict[str, Any]:
    return {
        "tracks": len(LEARNING_TRACKS),
        "debug_exercises": len(DEBUG_EXERCISES),
        "algorithms": len(ALGO_LAB),
        "api_scenarios": len(API_SCENARIOS),
        "extra_challenges": len(EXTRA_CHALLENGES),
        "project_templates": len(PROJECT_TEMPLATES),
        "certificates_issued": len(list(CERT_DIR.glob("JARVIS-*.json"))),
        "xp_levels": len(XP_LEVELS),
    }


def professor_prompts() -> list[dict[str, str]]:
    return [
        {"id": "beginner", "label": "Explique como se eu fosse iniciante", "prompt": "Explique como se eu fosse iniciante: "},
        {"id": "example", "label": "Explique com exemplo", "prompt": "Explique com um exemplo prático: "},
        {"id": "exercise", "label": "Me dê um exercício", "prompt": "Me dê um exercício sobre: "},
        {"id": "code", "label": "Explique esse código", "prompt": "Explique este código linha a linha:\n"},
        {"id": "error", "label": "Encontre meu erro", "prompt": "Encontre o erro neste código:\n"},
        {"id": "summary", "label": "Faça um resumo", "prompt": "Faça um resumo claro de: "},
        {"id": "quiz", "label": "Teste meu conhecimento", "prompt": "Faça 3 perguntas para testar meu conhecimento sobre: "},
    ]
