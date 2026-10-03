"""JARVIS Phase 9.0 — Education + Programming + Games + AI + UX expansion.
Incremental layer: reuses learning8, programming7, game_lab, ecosystem8.
No arbitrary server-side code execution. Local-first educational metadata.
"""
from __future__ import annotations
import json, re, uuid
from datetime import datetime, timezone
from services import platform_ultra, learning8, programming7, game_lab, ecosystem8

def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or "owner")[:120]
def clean(v, n=800): return str(v or "").strip()[:n]

# ── Learning modes (child / teen / adult) ──────────────────────────────────
MODES = {
    "crianca": {
        "id": "crianca", "title": "Criança", "icon": "🧒",
        "style": "histórias, personagens, missões e jogos",
        "tone": "simples, divertido, com analogias de jogos e heróis",
        "focus": ["lógica", "variáveis", "condições", "loops", "eventos", "game-loop"],
    },
    "adolescente": {
        "id": "adolescente", "title": "Adolescente", "icon": "🧑‍💻",
        "style": "web, Python, APIs, banco, Git, IA e projetos",
        "tone": "prático, com exemplos reais e mini-projetos",
        "focus": ["HTML", "CSS", "JavaScript", "Python", "APIs", "banco", "Git", "IA"],
    },
    "adulto": {
        "id": "adulto", "title": "Adulto / Profissional", "icon": "👔",
        "style": "arquitetura, testes, debugging, performance, segurança e deploy",
        "tone": "técnico, engenharia de software e boas práticas",
        "focus": ["arquitetura", "testes", "debugging", "performance", "segurança", "deploy", "APIs"],
    },
}

# Full learning track (Phase 9 §5)
FULL_TRACK = [
    {"id": "logica", "title": "Lógica", "order": 1},
    {"id": "algoritmos", "title": "Algoritmos", "order": 2},
    {"id": "html", "title": "HTML", "order": 3},
    {"id": "css", "title": "CSS", "order": 4},
    {"id": "javascript", "title": "JavaScript", "order": 5},
    {"id": "python", "title": "Python", "order": 6},
    {"id": "banco", "title": "Banco de Dados", "order": 7},
    {"id": "apis", "title": "APIs", "order": 8},
    {"id": "backend", "title": "Backend", "order": 9},
    {"id": "git", "title": "Git", "order": 10},
    {"id": "testes", "title": "Testes", "order": 11},
    {"id": "arquitetura", "title": "Arquitetura", "order": 12},
    {"id": "ia", "title": "IA", "order": 13},
    {"id": "gamedev", "title": "Game Development", "order": 14},
    {"id": "projeto-final", "title": "Projeto Final", "order": 15},
]

# Expanded lesson structure template (§3)
LESSON_SECTIONS = [
    "simple", "detailed", "example", "real_world", "code", "line_by_line",
    "exercise", "challenge", "common_errors", "tips", "experiment",
    "mini_project", "review",
]

EXPLAIN_STYLES = ["analogia", "exemplo_jogo", "exemplo_visual", "exemplo_tecnico", "exemplo_cotidiano"]

# ── Labs catalog (§6) ───────────────────────────────────────────────────────
LABS = {
    "algorithm": {
        "id": "algorithm", "title": "Algorithm Lab", "icon": "🧮",
        "desc": "Visualize busca linear, binária, ordenações, recursão, árvores, grafos e pathfinding.",
        "controls": ["INICIAR", "PAUSAR", "AVANÇAR", "REINICIAR"],
        "items": ["linear_search", "binary_search", "bubble_sort", "insertion_sort",
                  "selection_sort", "merge_sort", "quick_sort", "recursion", "bfs", "dfs", "dijkstra"],
    },
    "datastructure": {
        "id": "datastructure", "title": "Data Structure Lab", "icon": "📦",
        "desc": "Array, stack, queue, linked list, tree, graph e hash table interativos.",
        "items": ["array", "stack", "queue", "linked_list", "tree", "graph", "hash_table"],
    },
    "debug": {
        "id": "debug", "title": "Debug Lab", "icon": "🐛",
        "desc": "Código quebrado: executar → observar → localizar → entender → corrigir.",
        "flow": ["executar", "observar_erro", "localizar", "entender", "corrigir", "reexecutar"],
    },
    "api": {
        "id": "api", "title": "API Lab", "icon": "🔌",
        "desc": "Endpoint, método, parâmetros, headers, body, JSON, resposta e validação.",
    },
    "database": {
        "id": "database", "title": "Database Lab", "icon": "🗄️",
        "desc": "Database → table → column → type → relationship.",
    },
    "git": {
        "id": "git", "title": "Git Lab", "icon": "🌿",
        "desc": "commit, branch, merge, status, diff e histórico visual.",
    },
    "http": {
        "id": "http", "title": "HTTP Lab", "icon": "🌐",
        "desc": "Client → request → server → response visualizado.",
    },
    "json": {
        "id": "json", "title": "JSON Lab", "icon": "{ }",
        "desc": "Parse, validação, estrutura e transformação de JSON.",
    },
    "regex": {
        "id": "regex", "title": "Regex Lab", "icon": ".*",
        "desc": "Padrões, grupos, flags e testes interativos.",
    },
    "html": {"id": "html", "title": "HTML Lab", "icon": "📄", "desc": "Estrutura, tags, semântica e acessibilidade."},
    "css": {"id": "css", "title": "CSS Lab", "icon": "🎨", "desc": "Layout, flex, grid, responsividade e animações."},
    "javascript": {"id": "javascript", "title": "JavaScript Lab", "icon": "⚡", "desc": "DOM, eventos, async e módulos."},
    "python": {"id": "python", "title": "Python Lab", "icon": "🐍", "desc": "Sintaxe, tipos, estruturas e projetos (estudo local)."},
    "testing": {"id": "testing", "title": "Testing Lab", "icon": "✅", "desc": "Unitários, integração, regressão e casos de teste."},
    "architecture": {"id": "architecture", "title": "Architecture Lab", "icon": "🏗️", "desc": "Frontend → API → Backend → Database."},
    "performance": {"id": "performance", "title": "Performance Lab", "icon": "🚀", "desc": "Lazy load, debounce, cache e otimização."},
    "accessibility": {"id": "accessibility", "title": "Accessibility Lab", "icon": "♿", "desc": "ARIA, contraste, teclado e leitores de tela."},
    "ai": {"id": "ai", "title": "AI Lab", "icon": "🤖", "desc": "Modelos, tokens, prompts, embeddings, agentes e avaliação."},
}

# Algorithm visualizer steps (educational, no real heavy computation server-side)
ALGO_DEMOS = {
    "linear_search": {
        "title": "Busca Linear",
        "desc": "Percorre a lista do início ao fim até achar o valor.",
        "input": [4, 2, 9, 1, 7, 5],
        "target": 7,
        "steps": [
            {"i": 0, "msg": "Comparar 4 com 7 → não"},
            {"i": 1, "msg": "Comparar 2 com 7 → não"},
            {"i": 2, "msg": "Comparar 9 com 7 → não"},
            {"i": 3, "msg": "Comparar 1 com 7 → não"},
            {"i": 4, "msg": "Comparar 7 com 7 → encontrado!"},
        ],
        "complexity": "O(n)",
    },
    "binary_search": {
        "title": "Busca Binária",
        "desc": "Lista ordenada: descarta metade a cada passo.",
        "input": [1, 2, 4, 5, 7, 9],
        "target": 7,
        "steps": [
            {"lo": 0, "hi": 5, "mid": 2, "msg": "Meio=4; 7>4 → direita"},
            {"lo": 3, "hi": 5, "mid": 4, "msg": "Meio=7 → encontrado!"},
        ],
        "complexity": "O(log n)",
    },
    "bubble_sort": {
        "title": "Bubble Sort",
        "desc": "Troca pares adjacentes até ordenar.",
        "input": [5, 3, 8, 1, 2],
        "steps": [
            {"arr": [3, 5, 8, 1, 2], "msg": "5↔3"},
            {"arr": [3, 5, 1, 8, 2], "msg": "8↔1"},
            {"arr": [3, 5, 1, 2, 8], "msg": "8↔2"},
            {"arr": [3, 1, 5, 2, 8], "msg": "5↔1"},
            {"arr": [3, 1, 2, 5, 8], "msg": "5↔2"},
            {"arr": [1, 3, 2, 5, 8], "msg": "3↔1"},
            {"arr": [1, 2, 3, 5, 8], "msg": "3↔2 — ordenado"},
        ],
        "complexity": "O(n²)",
    },
    "insertion_sort": {
        "title": "Insertion Sort",
        "desc": "Insere cada elemento na posição correta da parte já ordenada.",
        "input": [5, 3, 8, 1, 2],
        "steps": [
            {"arr": [3, 5, 8, 1, 2], "msg": "3 entra antes de 5"},
            {"arr": [3, 5, 8, 1, 2], "msg": "8 já está no lugar"},
            {"arr": [1, 3, 5, 8, 2], "msg": "1 vai para o início"},
            {"arr": [1, 2, 3, 5, 8], "msg": "2 entra entre 1 e 3"},
        ],
        "complexity": "O(n²)",
    },
    "selection_sort": {
        "title": "Selection Sort",
        "desc": "Seleciona o menor e coloca na posição atual.",
        "input": [5, 3, 8, 1, 2],
        "steps": [
            {"arr": [1, 3, 8, 5, 2], "msg": "Menor=1 → posição 0"},
            {"arr": [1, 2, 8, 5, 3], "msg": "Menor=2 → posição 1"},
            {"arr": [1, 2, 3, 5, 8], "msg": "Menor=3 → posição 2"},
            {"arr": [1, 2, 3, 5, 8], "msg": "Já ordenado"},
        ],
        "complexity": "O(n²)",
    },
    "recursion": {
        "title": "Recursão (fatorial)",
        "desc": "Função que chama a si mesma com caso base.",
        "input": 4,
        "steps": [
            {"msg": "fat(4) = 4 * fat(3)"},
            {"msg": "fat(3) = 3 * fat(2)"},
            {"msg": "fat(2) = 2 * fat(1)"},
            {"msg": "fat(1) = 1 (base)"},
            {"msg": "Resultado: 24"},
        ],
        "complexity": "O(n)",
    },
    "bfs": {
        "title": "BFS (largura)",
        "desc": "Explora nível a nível usando fila.",
        "input": {"nodes": ["A", "B", "C", "D", "E"], "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]]},
        "steps": [
            {"queue": ["A"], "visited": [], "msg": "Inicia em A"},
            {"queue": ["B", "C"], "visited": ["A"], "msg": "Visita A, enfileira B,C"},
            {"queue": ["C", "D"], "visited": ["A", "B"], "msg": "Visita B, enfileira D"},
            {"queue": ["D", "E"], "visited": ["A", "B", "C"], "msg": "Visita C, enfileira E"},
            {"queue": ["E"], "visited": ["A", "B", "C", "D"], "msg": "Visita D"},
            {"queue": [], "visited": ["A", "B", "C", "D", "E"], "msg": "Visita E — fim"},
        ],
        "complexity": "O(V+E)",
    },
    "dfs": {
        "title": "DFS (profundidade)",
        "desc": "Explora o mais fundo possível com pilha/recursão.",
        "input": {"nodes": ["A", "B", "C", "D"], "edges": [["A", "B"], ["B", "C"], ["A", "D"]]},
        "steps": [
            {"stack": ["A"], "visited": [], "msg": "Inicia em A"},
            {"stack": ["A", "B"], "visited": ["A"], "msg": "Desce para B"},
            {"stack": ["A", "B", "C"], "visited": ["A", "B"], "msg": "Desce para C"},
            {"stack": ["A", "B"], "visited": ["A", "B", "C"], "msg": "Volta de C"},
            {"stack": ["A"], "visited": ["A", "B", "C"], "msg": "Volta de B"},
            {"stack": ["A", "D"], "visited": ["A", "B", "C"], "msg": "Desce para D"},
            {"stack": [], "visited": ["A", "B", "C", "D"], "msg": "Fim"},
        ],
        "complexity": "O(V+E)",
    },
}

# Data structure demos
DS_DEMOS = {
    "array": {"title": "Array", "ops": ["push", "pop", "get", "set"], "example": [10, 20, 30]},
    "stack": {"title": "Stack (LIFO)", "ops": ["push", "pop", "peek"], "example": []},
    "queue": {"title": "Queue (FIFO)", "ops": ["enqueue", "dequeue", "front"], "example": []},
    "linked_list": {"title": "Linked List", "ops": ["append", "prepend", "remove"], "example": ["A", "B", "C"]},
    "tree": {"title": "Binary Tree", "ops": ["insert", "traverse"], "example": {"root": 5, "left": 3, "right": 8}},
    "graph": {"title": "Graph", "ops": ["add_node", "add_edge"], "example": {"nodes": ["A", "B"], "edges": [["A", "B"]]}},
    "hash_table": {"title": "Hash Table", "ops": ["set", "get", "delete"], "example": {"nome": "Jarvis", "nivel": 9}},
}

# Debug Lab challenges (§9)
DEBUG_CHALLENGES = [
    {
        "id": "off-by-one",
        "title": "Erro off-by-one",
        "language": "javascript",
        "broken": "for (let i = 0; i <= arr.length; i++) {\n  console.log(arr[i]);\n}",
        "error": "undefined no último acesso",
        "hint1": "Olhe o limite do for.",
        "hint2": "Arrays vão de 0 até length-1.",
        "fixed": "for (let i = 0; i < arr.length; i++) {\n  console.log(arr[i]);\n}",
        "explain": "i <= length acessa um índice inexistente.",
    },
    {
        "id": "mutable-default",
        "title": "Mutação inesperada",
        "language": "javascript",
        "broken": "function add(item, list = []) {\n  list.push(item);\n  return list;\n}",
        "error": "lista compartilha estado entre chamadas",
        "hint1": "Parâmetro default é avaliado uma vez.",
        "hint2": "Crie a lista dentro da função se não for passada.",
        "fixed": "function add(item, list) {\n  if (!list) list = [];\n  list.push(item);\n  return list;\n}",
        "explain": "Default mutável em JS/Python causa estado compartilhado.",
    },
    {
        "id": "async-race",
        "title": "Promessa não aguardada",
        "language": "javascript",
        "broken": "async function load() {\n  const data = fetch('/api');\n  return data.json();\n}",
        "error": "data.json is not a function",
        "hint1": "fetch retorna uma Promise.",
        "hint2": "Use await antes de fetch.",
        "fixed": "async function load() {\n  const data = await fetch('/api');\n  return data.json();\n}",
        "explain": "Sem await, data é Promise, não Response.",
    },
    {
        "id": "sql-concat",
        "title": "Concatenação insegura (conceitual)",
        "language": "python",
        "broken": 'query = "SELECT * FROM users WHERE id = " + user_id',
        "error": "risco de SQL injection (conceitual)",
        "hint1": "Nunca monte SQL com concatenação de entrada do usuário.",
        "hint2": "Use placeholders parametrizados.",
        "fixed": 'query = "SELECT * FROM users WHERE id = ?"\n# cursor.execute(query, (user_id,))',
        "explain": "Placeholders separam código SQL de dados.",
    },
]

# New educational games (§15)
EDU_GAMES = {
    "robot_code": {
        "id": "robot_code", "title": "Robot Code", "icon": "🤖",
        "desc": "Programe um robô com comandos: FRENTE, ESQUERDA, DIREITA, PEGAR.",
        "concepts": ["sequência", "comandos", "loops"],
        "commands": ["FRENTE", "ESQUERDA", "DIREITA", "PEGAR", "REPETIR"],
    },
    "code_maze": {
        "id": "code_maze", "title": "Code Maze", "icon": "🗺️",
        "desc": "Programe o personagem para encontrar o caminho no labirinto.",
        "concepts": ["algoritmos", "condições", "pathfinding"],
    },
    "bug_hunter": {
        "id": "bug_hunter", "title": "Bug Hunter", "icon": "🐞",
        "desc": "Encontre e corrija bugs em trechos de código.",
        "concepts": ["debug", "leitura de código"],
    },
    "algorithm_race": {
        "id": "algorithm_race", "title": "Algorithm Race", "icon": "🏁",
        "desc": "Compare algoritmos lado a lado e veja quem chega primeiro.",
        "concepts": ["complexidade", "ordenação", "busca"],
    },
    "space_programmer": {
        "id": "space_programmer", "title": "Space Programmer", "icon": "🚀",
        "desc": "Programe uma nave: combustível, trajetória e missão.",
        "concepts": ["variáveis", "física simples", "estados"],
    },
    "logic_factory": {
        "id": "logic_factory", "title": "Logic Factory", "icon": "🏭",
        "desc": "Resolva sequências lógicas e complete a linha de produção.",
        "concepts": ["lógica", "padrões", "funções"],
    },
    "database_quest": {
        "id": "database_quest", "title": "Database Quest", "icon": "🗄️",
        "desc": "Missões de SELECT, JOIN e modelagem.",
        "concepts": ["SQL", "relacionamentos"],
    },
    "api_adventure": {
        "id": "api_adventure", "title": "API Adventure", "icon": "🔌",
        "desc": "Aprenda request e response em uma aventura.",
        "concepts": ["HTTP", "JSON", "status codes"],
    },
}

# Challenge types (§33)
CHALLENGE_TYPES = [
    {"id": "find_bug", "title": "Encontrar bug"},
    {"id": "complete_code", "title": "Completar código"},
    {"id": "predict", "title": "Prever resultado"},
    {"id": "organize", "title": "Organizar código"},
    {"id": "build_algo", "title": "Montar algoritmo"},
    {"id": "build_api", "title": "Construir API"},
    {"id": "model_db", "title": "Modelar banco"},
    {"id": "create_ui", "title": "Criar interface"},
    {"id": "optimize", "title": "Otimizar código"},
    {"id": "create_game", "title": "Criar jogo"},
    {"id": "fix_arch", "title": "Corrigir arquitetura"},
]

# Dashboard priorities (§36)
DASHBOARD_PRIORITY = [
    {"id": "continue", "title": "Continuar aprendendo", "icon": "📖"},
    {"id": "project", "title": "Projeto atual", "icon": "🚀"},
    {"id": "challenge", "title": "Desafio", "icon": "🎯"},
    {"id": "tools", "title": "Ferramentas", "icon": "🛠️"},
    {"id": "games", "title": "Jogos", "icon": "🎮"},
    {"id": "progress", "title": "Progresso", "icon": "📊"},
    {"id": "jarvis", "title": "JARVIS", "icon": "🤖"},
]

# Contextual roles (§40)
CONTEXT_ROLES = {
    "aula": {"role": "professor", "actions": ["EXPLICAR", "EXERCÍCIO", "DESAFIO", "REVISAR"]},
    "editor": {"role": "programador", "actions": ["ANALISAR", "CORRIGIR", "TESTAR", "MELHORAR", "DOCUMENTAR"]},
    "game_lab": {"role": "game developer", "actions": ["CRIAR", "DEBUGAR", "TESTAR", "MELHORAR"]},
    "debug": {"role": "debugger", "actions": ["LOCALIZAR", "EXPLICAR", "CORRIGIR", "TESTAR"]},
    "projeto": {"role": "mentor", "actions": ["PLANEJAR", "REVISAR", "ORIENTAR", "VALIDAR"]},
    "ai_lab": {"role": "professor de IA", "actions": ["EXPLICAR", "COMPARAR PROMPTS", "AVALIAR", "CRIAR AGENTE"]},
}

def conn():
    c = platform_ultra.conn()
    c.execute("""CREATE TABLE IF NOT EXISTS phase9_progress(
        owner_uid TEXT PRIMARY KEY,
        mode TEXT NOT NULL DEFAULT 'adolescente',
        track_json TEXT NOT NULL DEFAULT '[]',
        labs_json TEXT NOT NULL DEFAULT '{}',
        games_json TEXT NOT NULL DEFAULT '{}',
        daily_json TEXT NOT NULL DEFAULT '{}',
        weekly_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS phase9_snapshots(
        id TEXT PRIMARY KEY, owner_uid TEXT NOT NULL, label TEXT NOT NULL,
        kind TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS phase9_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL,
        event TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL
    )""")
    return c

def _progress(owner):
    with conn() as c:
        r = c.execute("SELECT * FROM phase9_progress WHERE owner_uid=?", (uid(owner),)).fetchone()
    if not r:
        with conn() as c:
            c.execute("INSERT OR IGNORE INTO phase9_progress(owner_uid,updated_at) VALUES(?,?)", (uid(owner), now()))
        return {"mode": "adolescente", "track": [], "labs": {}, "games": {}, "daily": {}, "weekly": {}}
    return {
        "mode": r["mode"],
        "track": json.loads(r["track_json"] or "[]"),
        "labs": json.loads(r["labs_json"] or "{}"),
        "games": json.loads(r["games_json"] or "{}"),
        "daily": json.loads(r["daily_json"] or "{}"),
        "weekly": json.loads(r["weekly_json"] or "{}"),
    }

def set_mode(owner, mode):
    mode = clean(mode, 20)
    if mode not in MODES:
        raise ValueError("Modo inválido. Use: crianca, adolescente ou adulto.")
    p = _progress(owner)
    with conn() as c:
        c.execute(
            "UPDATE phase9_progress SET mode=?, updated_at=? WHERE owner_uid=?",
            (mode, now(), uid(owner)),
        )
        c.execute(
            "INSERT INTO phase9_events(owner_uid,event,detail,created_at) VALUES(?,?,?,?)",
            (uid(owner), "mode_change", mode, now()),
        )
    p["mode"] = mode
    return p

def overview(owner):
    p = _progress(owner)
    try:
        learn = learning8.overview(owner)
    except Exception:
        learn = {}
    try:
        games = game_lab.overview(owner)
    except Exception:
        games = {}
    return {
        "version": "9.0",
        "mode": MODES.get(p["mode"], MODES["adolescente"]),
        "modes": list(MODES.values()),
        "track": FULL_TRACK,
        "labs": list(LABS.values()),
        "edu_games": list(EDU_GAMES.values()),
        "challenge_types": CHALLENGE_TYPES,
        "dashboard": DASHBOARD_PRIORITY,
        "context_roles": CONTEXT_ROLES,
        "progress": p,
        "learning": learn,
        "game_lab": games,
        "explain_styles": EXPLAIN_STYLES,
        "lesson_sections": LESSON_SECTIONS,
    }

def lab_detail(lab_id):
    lab = LABS.get(lab_id)
    if not lab:
        raise KeyError("Laboratório não encontrado")
    extra = {}
    if lab_id == "algorithm":
        extra["demos"] = ALGO_DEMOS
    elif lab_id == "datastructure":
        extra["demos"] = DS_DEMOS
    elif lab_id == "debug":
        extra["challenges"] = DEBUG_CHALLENGES
    return {**lab, **extra}

def algo_demo(algo_id):
    d = ALGO_DEMOS.get(algo_id)
    if not d:
        raise KeyError("Algoritmo não encontrado")
    return d

def ds_demo(ds_id):
    d = DS_DEMOS.get(ds_id)
    if not d:
        raise KeyError("Estrutura não encontrada")
    return d

def debug_challenge(cid):
    for c in DEBUG_CHALLENGES:
        if c["id"] == cid:
            # progressive: never return fixed until requested explicitly
            out = {k: v for k, v in c.items() if k != "fixed"}
            return out
    raise KeyError("Desafio não encontrado")

def debug_hint(cid, level=1):
    for c in DEBUG_CHALLENGES:
        if c["id"] == cid:
            if level <= 1:
                return {"hint": c["hint1"], "level": 1}
            if level == 2:
                return {"hint": c["hint2"], "level": 2}
            return {"hint": c["explain"], "level": 3, "partial": True}
    raise KeyError("Desafio não encontrado")

def debug_reveal(cid):
    for c in DEBUG_CHALLENGES:
        if c["id"] == cid:
            return {"fixed": c["fixed"], "explain": c["explain"]}
    raise KeyError("Desafio não encontrado")

def edu_game(gid):
    g = EDU_GAMES.get(gid)
    if not g:
        raise KeyError("Jogo não encontrado")
    return g

def explain_other_way(topic, style="analogia"):
    """§3 EXPLICAR DE OUTRO JEITO"""
    style = style if style in EXPLAIN_STYLES else "analogia"
    topic = clean(topic, 200)
    templates = {
        "analogia": f"Pense em «{topic}» como uma receita de bolo: ingredientes (dados), passos (algoritmo) e o bolo pronto (resultado).",
        "exemplo_jogo": f"No jogo, «{topic}» é como a regra que decide se o herói ganha ponto ou perde vida.",
        "exemplo_visual": f"Imagine caixas na prateleira: «{topic}» organiza, busca ou transforma o que está dentro delas.",
        "exemplo_tecnico": f"Tecnicamente, «{topic}» opera sobre entradas, aplica regras e produz saídas observáveis.",
        "exemplo_cotidiano": f"No dia a dia, «{topic}» parece escolher o caminho mais curto no mapa ou organizar a fila do caixa.",
    }
    return {"topic": topic, "style": style, "explanation": templates[style], "styles": EXPLAIN_STYLES}

def project_builder(owner, idea):
    """§12 Project Builder — ensina o processo, não só entrega código."""
    idea = clean(idea, 500)
    if not idea:
        raise ValueError("Descreva a ideia do projeto.")
    plan = {
        "objetivo": f"Transformar a ideia «{idea}» em um projeto funcional e testável.",
        "arquitetura": [
            "Interface (UI / páginas)",
            "Regras de negócio (lógica)",
            "Dados (persistência local ou API)",
            "Testes e validação",
        ],
        "tecnologias": ["HTML/CSS/JS ou Python (estudo)", "JSON para dados", "Git para versão"],
        "tarefas": [
            {"id": 1, "title": "Definir escopo mínimo (MVP)", "status": "todo"},
            {"id": 2, "title": "Desenhar fluxo de telas/dados", "status": "todo"},
            {"id": 3, "title": "Implementar núcleo (1 feature principal)", "status": "todo"},
            {"id": 4, "title": "Adicionar validação e feedback ao usuário", "status": "todo"},
            {"id": 5, "title": "Escrever casos de teste manuais", "status": "todo"},
            {"id": 6, "title": "Revisar, documentar e publicar versão 0.1", "status": "todo"},
        ],
        "etapas": ["IDEIA", "ARQUITETURA", "CÓDIGO", "TESTE", "CORREÇÃO", "VERSÃO FINAL"],
        "testes": [
            "Caminho feliz da feature principal",
            "Entrada inválida / vazia",
            "Estado vazio e estado com dados",
        ],
        "ensino": "JARVIS guia o processo: você decide, implementa e valida. Código completo só após entender cada etapa.",
    }
    try:
        ecosystem8.create_idea(owner, idea[:80], "project", idea)
    except Exception:
        pass
    return plan

def mentor_step(owner, stage, context=""):
    """§28 Mentor Mode: PERGUNTA → PISTA → TENTATIVA → FEEDBACK → NOVA PISTA → SOLUÇÃO"""
    stages = ["pergunta", "pista", "tentativa", "feedback", "nova_pista", "solucao"]
    stage = clean(stage, 20).lower() or "pergunta"
    if stage not in stages:
        stage = "pergunta"
    ctx = clean(context, 400)
    scripts = {
        "pergunta": f"O que você já tentou sobre «{ctx or 'este problema'}»? Descreva em uma frase.",
        "pista": "Observe a entrada e a saída esperada. Qual parte do código trata esse caminho?",
        "tentativa": "Faça uma mudança pequena e teste. Não reescreva tudo de uma vez.",
        "feedback": "Se ainda falhou: o erro está na condição, no índice ou no valor inicial?",
        "nova_pista": "Compare com um exemplo que funciona. Qual linha difere?",
        "solucao": "Revise o caso base / condição de parada / limite do loop. Depois documente o que aprendeu.",
    }
    idx = stages.index(stage)
    return {
        "stage": stage,
        "message": scripts[stage],
        "next": stages[idx + 1] if idx + 1 < len(stages) else None,
        "stages": stages,
    }

def code_review(code, language="javascript"):
    """§10 Code Review + Refactor — analysis only, no execution."""
    code = clean(code, 8000)
    language = clean(language, 20) or "javascript"
    issues = []
    if not code.strip():
        return {"issues": [{"severity": "high", "msg": "Código vazio."}], "score": 0}
    if "eval(" in code or "exec(" in code:
        issues.append({"severity": "high", "msg": "Evite eval/exec — risco de segurança."})
    if re.search(r"password\s*=\s*['\"][^'\"]+['\"]", code, re.I):
        issues.append({"severity": "high", "msg": "Possível segredo hardcoded."})
    if code.count("\n") > 80 and "function" not in code and "def " not in code:
        issues.append({"severity": "medium", "msg": "Arquivo longo sem funções — considere modularizar."})
    if re.search(r"\bvar\b", code) and language == "javascript":
        issues.append({"severity": "low", "msg": "Prefira let/const em vez de var."})
    if "==" in code and language == "javascript" and "===" not in code:
        issues.append({"severity": "low", "msg": "Considere === para comparação estrita."})
    if not issues:
        issues.append({"severity": "info", "msg": "Nenhum problema óbvio detectado estaticamente."})
    score = max(0, 100 - sum({"high": 30, "medium": 15, "low": 5, "info": 0}[i["severity"]] for i in issues))
    return {
        "language": language,
        "issues": issues,
        "score": score,
        "refactor_hint": "ANTES → identifique duplicação e nomes ruins → PROPOSTA → extraia funções → DEPOIS → teste.",
    }

def architecture_view():
    return {
        "layers": [
            {"id": "frontend", "title": "FRONTEND", "resp": "UI, eventos, validação de formulário, estado visual"},
            {"id": "api", "title": "API", "resp": "Contrato HTTP, autenticação, serialização JSON"},
            {"id": "backend", "title": "BACKEND", "resp": "Regras de negócio, orquestração, segurança"},
            {"id": "database", "title": "DATABASE", "resp": "Persistência, integridade, consultas"},
        ],
        "flow": "Usuário → Frontend → API → Backend → Database → resposta no caminho inverso",
    }

def network_dns_view():
    return {
        "network": ["COMPUTADOR", "ROTEADOR", "SERVIDOR"],
        "dns": ["DOMÍNIO", "DNS", "IP", "SERVIDOR"],
        "explain": {
            "network": "O pacote sai do seu PC, passa pelo roteador da rede e chega ao servidor de destino.",
            "dns": "O nome (ex: exemplo.com) é traduzido pelo DNS em um endereço IP numérico.",
        },
    }

def daily_challenge(owner):
    keys = list(learning8.LESSONS.keys()) if hasattr(learning8, "LESSONS") else ["variables"]
    day = datetime.now(timezone.utc).timetuple().tm_yday
    key = keys[day % len(keys)]
    lesson = learning8.LESSONS.get(key, {})
    return {
        "type": "daily",
        "lesson_key": key,
        "title": lesson.get("title", key),
        "requirements": ["Completar o exercício", "Tentar o desafio"],
        "concepts": [lesson.get("concept", key)],
        "tasks": [lesson.get("exercise", ""), lesson.get("challenge", "")],
        "hints": lesson.get("common", [])[:2],
        "goal": lesson.get("project", "Aplicar o conceito em um mini exemplo"),
    }

def weekly_project(owner):
    return {
        "type": "weekly",
        "title": "Projeto da semana: Mini API + interface",
        "requirements": [
            "Definir 2 endpoints (GET lista, POST criar)",
            "Validar entrada",
            "Mostrar lista na UI",
            "Escrever 3 casos de teste manuais",
        ],
        "concepts": ["HTTP", "JSON", "estado", "validação"],
        "tasks": [
            "Desenhar o contrato da API",
            "Implementar a lista em memória (estudo)",
            "Conectar a UI",
            "Documentar e versionar",
        ],
        "hints": ["Comece pelo caminho feliz", "Trate campo vazio"],
        "goal": "Uma feature completa do zero ao teste",
    }

def record_lab(owner, lab_id, action="visit"):
    p = _progress(owner)
    labs = p.get("labs") or {}
    labs[lab_id] = {"last": now(), "action": clean(action, 40), "count": labs.get(lab_id, {}).get("count", 0) + 1}
    with conn() as c:
        c.execute(
            "UPDATE phase9_progress SET labs_json=?, updated_at=? WHERE owner_uid=?",
            (json.dumps(labs, ensure_ascii=False), now(), uid(owner)),
        )
    return labs.get(lab_id)

def snapshot(owner, label, kind, data):
    sid = str(uuid.uuid4())
    with conn() as c:
        c.execute(
            "INSERT INTO phase9_snapshots VALUES(?,?,?,?,?,?)",
            (sid, uid(owner), clean(label, 80), clean(kind, 40), json.dumps(data or {}, ensure_ascii=False), now()),
        )
    return {"id": sid, "label": label, "kind": kind}

def snapshots(owner, kind=None):
    with conn() as c:
        if kind:
            rows = c.execute(
                "SELECT id,label,kind,created_at FROM phase9_snapshots WHERE owner_uid=? AND kind=? ORDER BY created_at DESC LIMIT 50",
                (uid(owner), clean(kind, 40)),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id,label,kind,created_at FROM phase9_snapshots WHERE owner_uid=? ORDER BY created_at DESC LIMIT 50",
                (uid(owner),),
            ).fetchall()
    return [{"id": r["id"], "label": r["label"], "kind": r["kind"], "created_at": r["created_at"]} for r in rows]

def smart_search(owner, q):
    q = clean(q, 100).lower()
    if not q:
        return []
    results = []
    for lid, lab in LABS.items():
        if q in lab["title"].lower() or q in lab["desc"].lower():
            results.append({"type": "lab", "id": lid, "title": lab["title"], "desc": lab["desc"]})
    for gid, g in EDU_GAMES.items():
        if q in g["title"].lower() or q in g["desc"].lower():
            results.append({"type": "game", "id": gid, "title": g["title"], "desc": g["desc"]})
    for t in FULL_TRACK:
        if q in t["title"].lower() or q in t["id"]:
            results.append({"type": "track", "id": t["id"], "title": t["title"]})
    try:
        for r in learning8.search(owner, q)[:10]:
            results.append({"type": "lesson", **r})
    except Exception:
        pass
    return results[:30]

def quality_center():
    """§41 Quality Center — static self-check metadata for developers."""
    return {
        "areas": [
            {"id": "bugs", "title": "BUGS", "status": "monitor", "note": "Verifique console e /api diagnostics"},
            {"id": "performance", "title": "PERFORMANCE", "status": "monitor", "note": "Lazy load labs e jogos"},
            {"id": "apis", "title": "APIs", "status": "ok", "note": "Rotas phase9 registradas sob /api/cyber/phase9"},
            {"id": "erros", "title": "ERROS", "status": "monitor", "note": "Mensagens claras ao usuário; detalhes no developer panel"},
            {"id": "jogos", "title": "JOGOS", "status": "expand", "note": "8 jogos educacionais novos + game lab existente"},
            {"id": "aulas", "title": "AULAS", "status": "expand", "note": "Modos criança/adolescente/adulto + trilha completa"},
            {"id": "sistema", "title": "SISTEMA", "status": "ok", "note": "Camada phase9 sem execução remota de código"},
        ]
    }
