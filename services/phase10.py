"""JARVIS Phase 10.0 — Education Hub, Smart Auth helpers, Labs & Tools catalog.

Design rules:
- Does not replace learning8 / programming7 / game_lab / phase9.
- Reuses their content when available.
- Public catalog endpoints expose only read-only educational metadata.
- Progress / save / history still require an authenticated uid.
- No arbitrary code execution on the server for playgrounds (client-side only).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone, date
from typing import Any

# ---------------------------------------------------------------------------
# Role levels (documentation + helpers). Enforcement stays in permissions/auth.
# ---------------------------------------------------------------------------
ROLE_LEVELS = {
    "public": 0,       # no session
    "guest": 1,        # optional future light session
    "user": 2,
    "developer": 3,
    "administrator": 4,  # maps to owner/admin
}

# Paths / endpoint names that are safe to expose without login (read-only).
# Used by app.py PUBLIC expansion. Never include write/save/admin routes.
PUBLIC_EDUCATION_ENDPOINTS = {
    "cyber.education_page",
    "cyber.phase10_overview",
    "cyber.phase10_tracks",
    "cyber.phase10_lesson_public",
    "cyber.phase10_skill_tree",
    "cyber.phase10_learning_map",
    "cyber.phase10_labs_catalog",
    "cyber.phase10_tools_catalog",
    "cyber.phase10_daily_public",
    "cyber.phase10_search_public",
    "cyber.programming7_page",
    "cyber.learning8_page",
    "cyber.phase9_page",
    "cyber.game_lab_page",
}

PUBLIC_PATH_PREFIXES = (
    "/educacao",
    "/education",
    "/api/cyber/phase10/public",
    "/api/cyber/phase10/overview",
    "/api/cyber/phase10/tracks",
    "/api/cyber/phase10/skill-tree",
    "/api/cyber/phase10/learning-map",
    "/api/cyber/phase10/labs",
    "/api/cyber/phase10/tools",
    "/api/cyber/phase10/daily-public",
    "/api/cyber/phase10/search-public",
    "/api/cyber/phase10/lesson/",
)

# ---------------------------------------------------------------------------
# Tracks progression (requested path)
# ---------------------------------------------------------------------------
PROGRESSION = [
    {"id": "logic", "title": "Lógica", "icon": "🧠"},
    {"id": "algorithms", "title": "Algoritmos", "icon": "⚙️"},
    {"id": "html", "title": "HTML", "icon": "📄"},
    {"id": "css", "title": "CSS", "icon": "🎨"},
    {"id": "javascript", "title": "JavaScript", "icon": "⚡"},
    {"id": "python", "title": "Python", "icon": "🐍"},
    {"id": "database", "title": "Banco de Dados", "icon": "🗄️"},
    {"id": "apis", "title": "APIs", "icon": "🔌"},
    {"id": "backend", "title": "Backend", "icon": "🖥️"},
    {"id": "git", "title": "Git", "icon": "🌿"},
    {"id": "tests", "title": "Testes", "icon": "🧪"},
    {"id": "architecture", "title": "Arquitetura", "icon": "🏗️"},
    {"id": "ai", "title": "IA", "icon": "🤖"},
    {"id": "gamedev", "title": "Desenvolvimento de Jogos", "icon": "🎮"},
    {"id": "final", "title": "Projeto Final", "icon": "🏆"},
]

# ---------------------------------------------------------------------------
# Enhanced lesson template fields (14-point structure)
# ---------------------------------------------------------------------------
LESSON_FIELDS = [
    "what", "purpose", "why", "how", "simple_example", "real_example",
    "code", "line_by_line", "common_errors", "how_to_test", "exercise",
    "challenge", "mini_project", "next",
]

# Core enhanced lessons (public, no secrets). Keep self-contained.
ENHANCED_LESSONS: dict[str, dict[str, Any]] = {
    "variables": {
        "id": "variables",
        "track": "logic",
        "title": "Variáveis",
        "level": "iniciante",
        "prereq": [],
        "what": "Uma variável é um nome que guarda um valor na memória do programa.",
        "purpose": "Permitir guardar, ler e alterar dados enquanto o programa roda.",
        "why": "Sem estado (valores guardados), programas não conseguem lembrar pontuação, vidas, texto digitado etc.",
        "how": "Você declara um nome, atribui um valor e depois usa esse nome no código.",
        "simple_example": "Imagine uma caixa com etiqueta `idade`. Você coloca o número 12 dentro e depois pode ler o que está na caixa.",
        "real_example": "Num jogo, `score` começa em 0 e aumenta a cada ponto; `lives` diminui quando o personagem é atingido.",
        "code": "let score = 0;\nscore += 10;\nconsole.log(score); // 10",
        "line_by_line": [
            "let score = 0; → cria a variável score com valor inicial 0",
            "score += 10; → soma 10 ao valor atual",
            "console.log(score); → mostra o valor no console",
        ],
        "common_errors": [
            "Usar a variável antes de criá-la",
            "Confundir = (atribuir) com == (comparar)",
            "Escrever o nome errado (Score vs score)",
        ],
        "how_to_test": "Abra o console do navegador, cole o código e veja se imprime 10.",
        "exercise": "Crie lives = 3 e diminua 1 vida.",
        "challenge": "Faça score e lives e imprima 'vitória' quando score >= 100.",
        "mini_project": "Mini placar: botões +1 ponto e -1 vida.",
        "next": "conditions",
        "analogies": {
            "cotidiano": "Variável é como um potinho com etiqueta na geladeira: o conteúdo muda, o nome fica.",
            "jogo": "No placar do jogo, cada número (pontos, vidas, tempo) é uma variável.",
            "visual": "Caixa → etiqueta (nome) → valor dentro.",
            "tecnica": "Símbolo na tabela de símbolos ligado a um endereço de memória.",
        },
    },
    "conditions": {
        "id": "conditions",
        "track": "logic",
        "title": "Condições (if/else)",
        "level": "iniciante",
        "prereq": ["variables"],
        "what": "Estruturas que executam código só quando uma condição é verdadeira.",
        "purpose": "Fazer o programa decidir: se isso, faça aquilo; senão, faça outra coisa.",
        "why": "Quase toda lógica real depende de decisões (vitória, erro, login, colisão).",
        "how": "Avalia uma expressão booleana (verdadeiro/falso) e escolhe o ramo.",
        "simple_example": "Se estiver chovendo, leve guarda-chuva; senão, não leve.",
        "real_example": "Se score >= 100, chamar win(); senão, continuar jogando.",
        "code": "if (score >= 100) {\n  console.log('vitória');\n} else {\n  console.log('continue');\n}",
        "line_by_line": [
            "if (score >= 100) → testa se score é maior ou igual a 100",
            "console.log('vitória') → executa só se a condição for verdadeira",
            "else → caminho alternativo quando a condição é falsa",
        ],
        "common_errors": [
            "Escrever if score >= 100 sem parênteses (em JS)",
            "Usar = em vez de == ou ===",
            "Esquecer chaves e agrupar linhas erradas",
        ],
        "how_to_test": "Mude score para 50 e 150 e observe as mensagens diferentes.",
        "exercise": "Se lives <= 0, mostre 'game over'.",
        "challenge": "Combine score e lives: vitória só com score >= 100 e lives > 0.",
        "mini_project": "Porta de acesso: se senha correta, 'aberto'; senão 'negado'.",
        "next": "loops",
        "analogies": {
            "cotidiano": "Semáforo: se verde, passa; se vermelho, para.",
            "jogo": "Se colidiu com inimigo, perde vida; senão, continua.",
            "visual": "Fluxograma com losango de decisão.",
            "tecnica": "Branch condicional no fluxo de controle.",
        },
    },
    "loops": {
        "id": "loops",
        "track": "logic",
        "title": "Loops (repetição)",
        "level": "iniciante",
        "prereq": ["conditions"],
        "what": "Estruturas que repetem um bloco de código enquanto uma condição vale.",
        "purpose": "Evitar copiar e colar a mesma lógica dezenas de vezes.",
        "why": "Listas, animações, contadores e buscas precisam de repetição controlada.",
        "how": "for / while / forEach avaliam condição, executam corpo, atualizam estado.",
        "simple_example": "Contar de 1 a 5 em voz alta — o mesmo ato, valores diferentes.",
        "real_example": "Desenhar 10 inimigos ou somar todos os itens de um carrinho.",
        "code": "for (let i = 1; i <= 5; i++) {\n  console.log(i);\n}",
        "line_by_line": [
            "let i = 1 → contador inicial",
            "i <= 5 → condição de continuação",
            "i++ → avança o contador a cada volta",
            "console.log(i) → corpo repetido",
        ],
        "common_errors": [
            "Loop infinito (condição que nunca fica falsa)",
            "Começar do índice errado (0 vs 1)",
            "Modificar a lista enquanto itera sem cuidado",
        ],
        "how_to_test": "Altere o limite para 3 e confira quantas linhas aparecem.",
        "exercise": "Some os números de 1 a 10 com um for.",
        "challenge": "Imprima só os pares de 1 a 20.",
        "mini_project": "Gerador de tabuada do 1 ao 10.",
        "next": "functions",
        "analogies": {
            "cotidiano": "Lavar 10 pratos: mesma ação, item diferente.",
            "jogo": "Atualizar posição de cada inimigo a cada frame.",
            "visual": "Seta que volta ao início do bloco até a condição falhar.",
            "tecnica": "Iteração com invariante de loop.",
        },
    },
    "functions": {
        "id": "functions",
        "track": "logic",
        "title": "Funções",
        "level": "iniciante",
        "prereq": ["loops"],
        "what": "Blocos nomeados de código que recebem entradas e podem devolver um resultado.",
        "purpose": "Organizar, reutilizar e testar pedaços de lógica.",
        "why": "Código grande sem funções vira cópia, bug e confusão.",
        "how": "Declare com nome e parâmetros; chame passando argumentos.",
        "simple_example": "Receita: ingredientes (parâmetros) → prato (retorno).",
        "real_example": "function damage(hp, amount) { return hp - amount; }",
        "code": "function add(a, b) {\n  return a + b;\n}\nconsole.log(add(2, 3)); // 5",
        "line_by_line": [
            "function add(a, b) → declara função com dois parâmetros",
            "return a + b → devolve a soma",
            "add(2, 3) → chama com argumentos 2 e 3",
        ],
        "common_errors": [
            "Esquecer return e receber undefined",
            "Confundir parâmetro com argumento",
            "Nomear funções de forma genérica demais (doStuff)",
        ],
        "how_to_test": "Chame add com vários pares e confira o retorno.",
        "exercise": "Crie multiply(a, b).",
        "challenge": "Crie clamp(value, min, max) que limita o valor.",
        "mini_project": "Biblioteca mini: add, sub, mul, div com proteção de divisão por zero.",
        "next": "html_basics",
        "analogies": {
            "cotidiano": "Botão de elevador: você aperta (chama), ele sobe (executa).",
            "jogo": "Função jump() usada pelo player e por NPCs.",
            "visual": "Caixa preta com entrada → saída.",
            "tecnica": "Abstração procedural com escopo próprio.",
        },
    },
    "html_basics": {
        "id": "html_basics",
        "track": "html",
        "title": "HTML — estrutura de páginas",
        "level": "iniciante",
        "prereq": ["functions"],
        "what": "HTML descreve a estrutura e o significado do conteúdo de uma página.",
        "purpose": "Organizar títulos, parágrafos, links, imagens e seções.",
        "why": "O navegador precisa de marcação semântica para renderizar e acessar o conteúdo.",
        "how": "Tags aninhadas formam uma árvore de elementos (DOM).",
        "simple_example": "Um documento com capa (h1), texto (p) e um link (a).",
        "real_example": "Página de aula com título, explicação e botão 'Próxima'.",
        "code": "<!DOCTYPE html>\n<html>\n<head><title>Aula</title></head>\n<body>\n  <h1>Olá</h1>\n  <p>Bem-vindo ao JARVIS.</p>\n</body>\n</html>",
        "line_by_line": [
            "<!DOCTYPE html> → declara HTML5",
            "<head> → metadados (título, CSS)",
            "<body> → conteúdo visível",
            "<h1> / <p> → título e parágrafo",
        ],
        "common_errors": [
            "Esquecer de fechar tags",
            "Colocar block dentro de inline indevidamente",
            "Usar div para tudo sem semântica",
        ],
        "how_to_test": "Salve como .html e abra no navegador.",
        "exercise": "Crie uma página com h1, 2 parágrafos e um link.",
        "challenge": "Monte uma lista de 3 conceitos aprendidos com <ul>.",
        "mini_project": "Card de perfil: nome, bio, link para GitHub.",
        "next": "css_basics",
        "analogies": {
            "cotidiano": "Esqueleto de uma casa: paredes e cômodos antes da pintura.",
            "jogo": "HUD e menus definidos por estrutura de elementos.",
            "visual": "Árvore: html → body → seções → texto.",
            "tecnica": "Marcação semântica consumida pelo parser do browser.",
        },
    },
    "css_basics": {
        "id": "css_basics",
        "track": "css",
        "title": "CSS — aparência e layout",
        "level": "iniciante",
        "prereq": ["html_basics"],
        "what": "CSS define como os elementos HTML aparecem: cores, espaçamento, layout.",
        "purpose": "Separar conteúdo (HTML) de apresentação (CSS).",
        "why": "Facilita temas, responsividade e manutenção visual.",
        "how": "Seletores apontam elementos; propriedades definem estilo.",
        "simple_example": "h1 { color: #00e5ff; } deixa o título ciano.",
        "real_example": "Card de aula com fundo escuro, borda e padding confortável.",
        "code": "h1 {\n  color: #00e5ff;\n  font-size: 1.6rem;\n}\n.card {\n  padding: 16px;\n  border-radius: 12px;\n}",
        "line_by_line": [
            "h1 { ... } → seletor de todos os h1",
            "color → cor do texto",
            ".card → seletor de classe",
            "padding / border-radius → espaço interno e cantos",
        ],
        "common_errors": [
            "Especificidade demais (só !important)",
            "Esquecer unidades (px, rem)",
            "Quebrar layout mobile sem media queries",
        ],
        "how_to_test": "Aplique o CSS num HTML simples e recarregue.",
        "exercise": "Estilize um botão com hover.",
        "challenge": "Crie um layout de 2 colunas com flexbox.",
        "mini_project": "Tema claro/escuro só com classes CSS.",
        "next": "javascript_basics",
        "analogies": {
            "cotidiano": "Roupa e pintura da casa — a estrutura continua a mesma.",
            "jogo": "Skin e HUD skinning sem mudar a lógica.",
            "visual": "Camada de estilo sobre a árvore HTML.",
            "tecnica": "Cascade + specificity resolvem conflitos de regras.",
        },
    },
    "javascript_basics": {
        "id": "javascript_basics",
        "track": "javascript",
        "title": "JavaScript — interatividade",
        "level": "iniciante",
        "prereq": ["css_basics"],
        "what": "Linguagem que roda no navegador (e no servidor) para lógica e interação.",
        "purpose": "Reagir a cliques, validar formulários, atualizar a página sem recarregar.",
        "why": "HTML/CSS sozinhos não tomam decisões dinâmicas.",
        "how": "Escuta eventos, altera o DOM, chama APIs.",
        "simple_example": "Botão que soma 1 ao placar ao ser clicado.",
        "real_example": "Chat que envia mensagem e mostra resposta do JARVIS.",
        "code": "const btn = document.querySelector('#plus');\nlet score = 0;\nbtn.addEventListener('click', () => {\n  score += 1;\n  document.querySelector('#score').textContent = score;\n});",
        "line_by_line": [
            "querySelector → encontra o elemento",
            "addEventListener → registra reação ao clique",
            "score += 1 → atualiza estado",
            "textContent → reflete no HTML",
        ],
        "common_errors": [
            "Script no <head> sem DOMContentLoaded",
            "Typos no id/classe do seletor",
            "Mutar DOM em loop pesado sem necessidade",
        ],
        "how_to_test": "Abra a página, clique no botão e veja o número mudar.",
        "exercise": "Botão que diminui o score (mínimo 0).",
        "challenge": "Atalho de teclado Espaço também soma ponto.",
        "mini_project": "Contador com + / − / reset.",
        "next": "python_basics",
        "analogies": {
            "cotidiano": "O cérebro que reage quando você aperta um interruptor.",
            "jogo": "Input + game loop atualizando sprites.",
            "visual": "Evento → handler → mudança na tela.",
            "tecnica": "Event-driven programming sobre o DOM.",
        },
    },
    "python_basics": {
        "id": "python_basics",
        "track": "python",
        "title": "Python — primeiros passos",
        "level": "iniciante",
        "prereq": ["javascript_basics"],
        "what": "Linguagem legível, usada em web, dados, automação e IA.",
        "purpose": "Escrever lógica clara com pouca cerimônia sintática.",
        "why": "Ótima para aprender algoritmos e para backends/scripts.",
        "how": "Indentação define blocos; tipos dinâmicos; funções def.",
        "simple_example": "print('olá') mostra texto no terminal.",
        "real_example": "Script que lê JSON e calcula média de notas.",
        "code": "def greet(name):\n    return f'Olá, {name}!'\n\nprint(greet('JARVIS'))",
        "line_by_line": [
            "def greet(name): → define função",
            "return f'...' → f-string com interpolação",
            "print(...) → saída padrão",
        ],
        "common_errors": [
            "Misturar tabs e espaços",
            "Esquecer dois-pontos após def/if/for",
            "Comparar com = em vez de ==",
        ],
        "how_to_test": "Rode no interpretador Python ou no playground.",
        "exercise": "Função que retorna o dobro de um número.",
        "challenge": "Função que conta vogais em uma string.",
        "mini_project": "CLI de lista de tarefas em memória.",
        "next": "sql_basics",
        "analogies": {
            "cotidiano": "Receita escrita em linguagem quase humana.",
            "jogo": "Scripts de comportamento de NPCs.",
            "visual": "Linhas indentadas = blocos aninhados.",
            "tecnica": "Interpretada, tipagem dinâmica, batteries included.",
        },
    },
    "sql_basics": {
        "id": "sql_basics",
        "track": "database",
        "title": "SQL — consultar dados",
        "level": "intermediario",
        "prereq": ["python_basics"],
        "what": "Linguagem para definir e consultar bancos relacionais.",
        "purpose": "Filtrar, juntar e agregar dados de forma declarativa.",
        "why": "Aplicações reais precisam persistir e consultar informação.",
        "how": "SELECT ... FROM ... WHERE ...; tabelas e relações.",
        "simple_example": "SELECT name FROM students WHERE score >= 7;",
        "real_example": "Listar usuários ativos ordenados por última visita.",
        "code": "SELECT id, title\nFROM lessons\nWHERE track = 'logic'\nORDER BY title;",
        "line_by_line": [
            "SELECT id, title → colunas desejadas",
            "FROM lessons → tabela",
            "WHERE track = 'logic' → filtro",
            "ORDER BY title → ordenação",
        ],
        "common_errors": [
            "SELECT * em produção sem necessidade",
            "Esquecer WHERE e atualizar/apagar tudo",
            "Injeção SQL (nunca concatenar input cru)",
        ],
        "how_to_test": "Use o SQL Playground com dados de demonstração.",
        "exercise": "Selecione aulas do track python.",
        "challenge": "Conte quantas aulas existem por track (GROUP BY).",
        "mini_project": "Modelo simples: users, lessons, progress.",
        "next": "api_basics",
        "analogies": {
            "cotidiano": "Perguntar ao bibliotecário: livros de ficção após 2020.",
            "jogo": "Inventário persistido: quantos itens do tipo X.",
            "visual": "Tabela de planilha com filtros.",
            "tecnica": "Álgebra relacional expressa em SQL.",
        },
    },
    "api_basics": {
        "id": "api_basics",
        "track": "apis",
        "title": "APIs HTTP",
        "level": "intermediario",
        "prereq": ["sql_basics"],
        "what": "Interfaces que permitem sistemas conversarem via HTTP (JSON etc.).",
        "purpose": "Expor e consumir dados/ações de forma padronizada.",
        "why": "Frontend, mobile e serviços precisam de contratos claros.",
        "how": "Métodos GET/POST/PUT/PATCH/DELETE + status codes + body/headers.",
        "simple_example": "GET /api/lessons → lista aulas em JSON.",
        "real_example": "POST /api/progress com {lessonId, correct} salva progresso.",
        "code": "fetch('/api/cyber/phase10/public/overview')\n  .then(r => r.json())\n  .then(data => console.log(data));",
        "line_by_line": [
            "fetch(url) → faz a requisição",
            "r.json() → parse do corpo JSON",
            "then(data => ...) → usa o resultado",
        ],
        "common_errors": [
            "Ignorar status HTTP (tratar 401/500)",
            "Esquecer Content-Type em POST JSON",
            "Expor secrets no frontend",
        ],
        "how_to_test": "Abra o Network do DevTools e inspecione a chamada.",
        "exercise": "Chame o overview público e mostre o título no DOM.",
        "challenge": "Trate erro de rede com mensagem amigável.",
        "mini_project": "Cliente mínimo de API de aulas.",
        "next": "git_basics",
        "analogies": {
            "cotidiano": "Cardápio do restaurante: você pede (request), recebe o prato (response).",
            "jogo": "Servidor de matchmaking respondendo salas disponíveis.",
            "visual": "Cliente → request → API → response.",
            "tecnica": "REST sobre HTTP com recursos e verbos.",
        },
    },
}

# ---------------------------------------------------------------------------
# Skill tree (hierarchical)
# ---------------------------------------------------------------------------
SKILL_TREE = {
    "id": "root",
    "title": "Programação",
    "children": [
        {
            "id": "logic",
            "title": "Lógica",
            "children": [
                {"id": "variables", "title": "Variáveis", "lesson": "variables"},
                {"id": "conditions", "title": "Condições", "lesson": "conditions"},
                {"id": "loops", "title": "Loops", "lesson": "loops"},
                {"id": "functions", "title": "Funções", "lesson": "functions"},
                {"id": "algorithms", "title": "Algoritmos", "lesson": None},
            ],
        },
        {
            "id": "web",
            "title": "Web",
            "children": [
                {"id": "html", "title": "HTML", "lesson": "html_basics"},
                {"id": "css", "title": "CSS", "lesson": "css_basics"},
                {"id": "javascript", "title": "JavaScript", "lesson": "javascript_basics"},
            ],
        },
        {
            "id": "python",
            "title": "Python",
            "children": [
                {"id": "python_basics", "title": "Sintaxe", "lesson": "python_basics"},
            ],
        },
        {
            "id": "data",
            "title": "Dados & APIs",
            "children": [
                {"id": "sql", "title": "SQL", "lesson": "sql_basics"},
                {"id": "apis", "title": "APIs", "lesson": "api_basics"},
            ],
        },
        {
            "id": "advanced",
            "title": "Avançado",
            "children": [
                {"id": "backend", "title": "Backend"},
                {"id": "git", "title": "Git"},
                {"id": "tests", "title": "Testes"},
                {"id": "architecture", "title": "Arquitetura"},
                {"id": "ai", "title": "IA"},
                {"id": "gamedev", "title": "Games"},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Labs catalog (metadata; UI tools are client-side or existing services)
# ---------------------------------------------------------------------------
LABS = [
    {"id": "algorithm", "title": "Algorithm Lab", "icon": "⚙️", "desc": "Visualize busca e ordenação passo a passo."},
    {"id": "datastruct", "title": "Data Structure Lab", "icon": "🧩", "desc": "Array, Stack, Queue, Linked List, Tree, Graph, Hash."},
    {"id": "debug", "title": "Debug Lab", "icon": "🐛", "desc": "Código quebrado → erro → localizar → corrigir."},
    {"id": "api", "title": "API Lab", "icon": "🔌", "desc": "Client → Request → API → Backend → DB → Response."},
    {"id": "database", "title": "Database Lab", "icon": "🗄️", "desc": "Tabelas, tipos, relações e SQL demo isolado."},
    {"id": "git", "title": "Git Lab", "icon": "🌿", "desc": "commit, branch, merge — fluxos visuais."},
    {"id": "http", "title": "HTTP Lab", "icon": "🌐", "desc": "Métodos, headers, status codes."},
    {"id": "json", "title": "JSON Lab", "icon": "{ }", "desc": "Formatar, validar e explorar JSON."},
    {"id": "regex", "title": "Regex Lab", "icon": ".*", "desc": "Testar expressões regulares com destaques."},
    {"id": "html", "title": "HTML Lab", "icon": "📄", "desc": "Preview ao vivo de marcação."},
    {"id": "css", "title": "CSS Lab", "icon": "🎨", "desc": "Playground de estilos."},
    {"id": "javascript", "title": "JavaScript Lab", "icon": "⚡", "desc": "Editor + console seguro no browser."},
    {"id": "python", "title": "Python Lab", "icon": "🐍", "desc": "Exemplos e exercícios (sem exec remota arbitrária)."},
    {"id": "sql", "title": "SQL Lab", "icon": "📊", "desc": "Consultas em banco de demonstração isolado."},
    {"id": "testing", "title": "Testing Lab", "icon": "🧪", "desc": "Unitário, integração, regressão."},
    {"id": "architecture", "title": "Architecture Lab", "icon": "🏗️", "desc": "Frontend → API → Backend → Database."},
    {"id": "performance", "title": "Performance Lab", "icon": "🚀", "desc": "Carregamento, lazy load, cleanup."},
    {"id": "a11y", "title": "Accessibility Lab", "icon": "♿", "desc": "Contraste, teclado, semântica."},
    {"id": "ai", "title": "AI Lab", "icon": "🤖", "desc": "Prompts, tokens, agentes, ferramentas."},
    {"id": "physics", "title": "Physics Lab", "icon": "⚛️", "desc": "Gravidade, velocidade, colisão."},
    {"id": "animation", "title": "Animation Lab", "icon": "🎞️", "desc": "IDLE, WALK, JUMP, frames e timeline."},
    {"id": "network", "title": "Network Lab", "icon": "📡", "desc": "DNS, IP, roteador, servidor."},
]

TOOLS = [
    {"id": "code-explainer", "title": "Code Explainer", "icon": "📖"},
    {"id": "code-formatter", "title": "Code Formatter", "icon": "✨"},
    {"id": "code-diff", "title": "Code Diff", "icon": "↔️"},
    {"id": "json-formatter", "title": "JSON Formatter", "icon": "{ }"},
    {"id": "json-validator", "title": "JSON Validator", "icon": "✅"},
    {"id": "regex-tester", "title": "Regex Tester", "icon": ".*"},
    {"id": "markdown-preview", "title": "Markdown Preview", "icon": "📝"},
    {"id": "html-preview", "title": "HTML Preview", "icon": "📄"},
    {"id": "css-playground", "title": "CSS Playground", "icon": "🎨"},
    {"id": "js-playground", "title": "JavaScript Playground", "icon": "⚡"},
    {"id": "python-playground", "title": "Python Playground", "icon": "🐍"},
    {"id": "sql-playground", "title": "SQL Playground", "icon": "📊"},
    {"id": "http-tester", "title": "HTTP Tester", "icon": "🌐"},
    {"id": "timestamp", "title": "Timestamp Tool", "icon": "⏱️"},
    {"id": "ascii", "title": "ASCII Lab", "icon": "🔤"},
    {"id": "base64", "title": "Base64 Lab", "icon": "🔢"},
    {"id": "hash", "title": "Hash Demonstrator", "icon": "#️⃣"},
    {"id": "color", "title": "Color Converter", "icon": "🌈"},
    {"id": "unit", "title": "Unit Converter", "icon": "📐"},
]

# Educational games (concepts) — after fixing existing ones
EDU_GAMES = [
    {"id": "robot-code", "title": "Robot Code", "concept": "sequência de comandos"},
    {"id": "code-maze", "title": "Code Maze", "concept": "condições e caminhos"},
    {"id": "bug-hunter", "title": "Bug Hunter", "concept": "debug e leitura de erro"},
    {"id": "algorithm-race", "title": "Algorithm Race", "concept": "complexidade e passos"},
    {"id": "space-programmer", "title": "Space Programmer", "concept": "funções e parâmetros"},
    {"id": "logic-factory", "title": "Logic Factory", "concept": "booleanos e portas lógicas"},
    {"id": "database-quest", "title": "Database Quest", "concept": "consultas SQL"},
    {"id": "api-adventure", "title": "API Adventure", "concept": "HTTP e JSON"},
]

DAILY_POOL = [
    {"id": "d1", "title": "Some com loop", "prompt": "Some os números de 1 a 20 usando um loop.", "track": "logic"},
    {"id": "d2", "title": "Filtro de lista", "prompt": "Dada uma lista de scores, retorne só os >= 70.", "track": "javascript"},
    {"id": "d3", "title": "HTML semântico", "prompt": "Monte um article com header, p e footer.", "track": "html"},
    {"id": "d4", "title": "CSS card", "prompt": "Estilize um card com sombra e hover.", "track": "css"},
    {"id": "d5", "title": "SQL básico", "prompt": "SELECT name FROM users WHERE active = 1;", "track": "database"},
    {"id": "d6", "title": "API mental", "prompt": "Qual status code para recurso criado com sucesso? (201)", "track": "apis"},
    {"id": "d7", "title": "Encontre o bug", "prompt": "Por que `if (score = 100)` é problemático?", "track": "debug"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_uid(uid: str | None) -> str:
    return str(uid or "anon")[:120]


def overview(uid: str | None = None) -> dict:
    """Public-safe overview of the Education hub."""
    return {
        "version": "10.0",
        "title": "JARVIS Educação",
        "subtitle": "Trilhas, aulas, labs, ferramentas e mentor",
        "progression": PROGRESSION,
        "lesson_count": len(ENHANCED_LESSONS),
        "lab_count": len(LABS),
        "tool_count": len(TOOLS),
        "game_count": len(EDU_GAMES),
        "sections": [
            {"id": "cursos", "title": "Cursos", "icon": "📚"},
            {"id": "trilhas", "title": "Trilhas", "icon": "🛤️"},
            {"id": "aulas", "title": "Aulas", "icon": "🎓"},
            {"id": "exercicios", "title": "Exercícios", "icon": "✏️"},
            {"id": "desafios", "title": "Desafios", "icon": "🎯"},
            {"id": "projetos", "title": "Projetos", "icon": "🧱"},
            {"id": "laboratorios", "title": "Laboratórios", "icon": "🔬"},
            {"id": "progresso", "title": "Progresso", "icon": "📈"},
            {"id": "mapa", "title": "Mapa de conhecimento", "icon": "🗺️"},
            {"id": "skilltree", "title": "Skill Tree", "icon": "🌳"},
            {"id": "mentor", "title": "Mentor JARVIS", "icon": "🤖"},
            {"id": "ferramentas", "title": "Ferramentas", "icon": "🛠️"},
        ],
        "auth_note": "Aulas e demos públicas não exigem login. Salvar progresso exige autenticação.",
        "generated_at": now_iso(),
        "viewer": _safe_uid(uid),
    }


def tracks() -> list:
    return PROGRESSION


def skill_tree() -> dict:
    return SKILL_TREE


def learning_map() -> dict:
    """Edges between lessons / concepts for the knowledge map."""
    nodes = []
    edges = []
    for lid, lesson in ENHANCED_LESSONS.items():
        nodes.append({
            "id": lid,
            "title": lesson["title"],
            "track": lesson.get("track"),
            "level": lesson.get("level"),
        })
        for pre in lesson.get("prereq") or []:
            edges.append({"from": pre, "to": lid})
        nxt = lesson.get("next")
        if nxt and nxt in ENHANCED_LESSONS:
            edges.append({"from": lid, "to": nxt, "kind": "next"})
    return {"nodes": nodes, "edges": edges, "labs": [x["id"] for x in LABS]}


def labs_catalog() -> list:
    return LABS


def tools_catalog() -> list:
    return TOOLS


def edu_games() -> list:
    return EDU_GAMES


def lesson_public(key: str) -> dict | None:
    lesson = ENHANCED_LESSONS.get(key)
    if not lesson:
        return None
    return dict(lesson)


def explain_another_way(key: str, style: str = "cotidiano") -> dict:
    lesson = ENHANCED_LESSONS.get(key)
    if not lesson:
        return {"error": "Aula não encontrada"}
    style = (style or "cotidiano").lower()
    analogies = lesson.get("analogies") or {}
    text = analogies.get(style) or analogies.get("cotidiano") or lesson.get("what")
    return {
        "lesson_id": key,
        "style": style,
        "explanation": text,
        "available_styles": list(analogies.keys()) or ["cotidiano", "jogo", "visual", "tecnica"],
        "title": lesson.get("title"),
    }


def mentor_step(question: str, attempt: str = "", stage: str = "pergunta") -> dict:
    """Progressive mentor: pergunta → pista → tentativa → feedback → nova pista → solução."""
    q = (question or "").strip()[:500]
    attempt = (attempt or "").strip()[:2000]
    stage = (stage or "pergunta").lower()
    stages = ["pergunta", "pista", "tentativa", "feedback", "nova_pista", "solucao"]
    if stage not in stages:
        stage = "pergunta"

    # Heuristic, offline-friendly mentor (no model required).
    hint1 = "Releia o enunciado e identifique entradas, saídas e restrições."
    hint2 = "Escreva em português o passo a passo antes de codificar."
    feedback = "Boa tentativa. Verifique casos de borda (vazio, zero, negativo)."
    solution = (
        "1) Entenda o problema\n"
        "2) Escolha estruturas simples\n"
        "3) Implemente o caminho feliz\n"
        "4) Teste casos de borda\n"
        "5) Refatore nomes e funções"
    )
    if "bug" in q.lower() or "erro" in q.lower():
        hint1 = "Leia a mensagem de erro completa: tipo, linha e stack."
        hint2 = "Reproduza o erro com o menor exemplo possível."
        solution = "Isolar → reproduzir → hipótese → corrigir → testar de novo."
    if "loop" in q.lower():
        hint1 = "Defina variável de controle, condição de parada e atualização."
        hint2 = "Evite loops infinitos: a condição precisa mudar."

    idx = stages.index(stage)
    next_stage = stages[min(idx + 1, len(stages) - 1)]
    payload = {
        "stage": stage,
        "next_stage": next_stage,
        "question": q,
        "attempt": attempt,
        "flow": stages,
    }
    if stage in ("pergunta", "pista"):
        payload["hint"] = hint1
    elif stage in ("tentativa", "feedback"):
        payload["feedback"] = feedback
        payload["hint"] = hint2
    elif stage == "nova_pista":
        payload["hint"] = hint2
    else:
        payload["solution"] = solution
        payload["hint"] = "Compare sua solução com a proposta e anote diferenças."
    return payload


def daily_public() -> dict:
    """Deterministic daily challenge from date (no user state)."""
    day_index = date.today().toordinal() % len(DAILY_POOL)
    item = dict(DAILY_POOL[day_index])
    item["date"] = date.today().isoformat()
    item["kind"] = "daily"
    return item


def weekly_public() -> dict:
    # ISO week based
    iso = date.today().isocalendar()
    week_index = (iso.year * 53 + iso.week) % len(DAILY_POOL)
    base = DAILY_POOL[week_index]
    return {
        "kind": "weekly",
        "title": f"Projeto semanal: {base['title']}",
        "prompt": f"Expanda em um mini-projeto: {base['prompt']} Documente e teste.",
        "track": base["track"],
        "week": f"{iso.year}-W{iso.week:02d}",
    }


def smart_search_public(q: str) -> list:
    q = (q or "").strip().lower()
    if not q:
        return []
    results = []
    for lid, lesson in ENHANCED_LESSONS.items():
        blob = " ".join([
            lid, lesson.get("title", ""), lesson.get("what", ""),
            lesson.get("track", ""), " ".join(lesson.get("common_errors") or []),
        ]).lower()
        if q in blob:
            results.append({"type": "lesson", "id": lid, "title": lesson["title"], "track": lesson.get("track")})
    for lab in LABS:
        if q in (lab["title"] + lab["desc"]).lower() or q in lab["id"]:
            results.append({"type": "lab", "id": lab["id"], "title": lab["title"]})
    for tool in TOOLS:
        if q in tool["title"].lower() or q in tool["id"]:
            results.append({"type": "tool", "id": tool["id"], "title": tool["title"]})
    return results[:40]


def algorithm_steps(algo: str, data: list | None = None) -> dict:
    """Server-side step generator for educational visualization (no user code exec)."""
    algo = (algo or "bubble").lower()
    arr = list(data if isinstance(data, list) and data else [5, 2, 8, 1, 9, 3])
    arr = [int(x) for x in arr[:24]]
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
        n = len(a)
        for i in range(n):
            m = i
            for j in range(i + 1, n):
                steps.append({"type": "compare", "i": m, "j": j, "array": a[:]})
                if a[j] < a[m]:
                    m = j
            if m != i:
                a[i], a[m] = a[m], a[i]
                steps.append({"type": "swap", "i": i, "j": m, "array": a[:]})
        steps.append({"type": "done", "array": a[:]})
    elif algo in ("insertion", "insertion_sort"):
        for i in range(1, len(a)):
            key = a[i]
            j = i - 1
            while j >= 0 and a[j] > key:
                steps.append({"type": "compare", "i": j, "j": j + 1, "array": a[:]})
                a[j + 1] = a[j]
                j -= 1
                steps.append({"type": "shift", "array": a[:]})
            a[j + 1] = key
            steps.append({"type": "insert", "array": a[:]})
        steps.append({"type": "done", "array": a[:]})
    elif algo in ("linear", "linear_search"):
        target = a[len(a) // 2] if a else 0
        for i, v in enumerate(a):
            steps.append({"type": "probe", "i": i, "value": v, "target": target, "array": a[:]})
            if v == target:
                steps.append({"type": "found", "i": i, "array": a[:]})
                break
        else:
            steps.append({"type": "not_found", "array": a[:]})
    elif algo in ("binary", "binary_search"):
        a = sorted(a)
        target = a[len(a) // 2] if a else 0
        lo, hi = 0, len(a) - 1
        steps.append({"type": "sorted", "array": a[:], "target": target})
        while lo <= hi:
            mid = (lo + hi) // 2
            steps.append({"type": "probe", "i": mid, "lo": lo, "hi": hi, "array": a[:]})
            if a[mid] == target:
                steps.append({"type": "found", "i": mid, "array": a[:]})
                break
            if a[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        else:
            steps.append({"type": "not_found", "array": a[:]})
    else:
        return {"error": "Algoritmo não suportado", "supported": [
            "bubble", "selection", "insertion", "linear", "binary"
        ]}
    return {"algo": algo, "input": arr, "steps": steps, "final": a}


def hash_demo(text: str, algo: str = "sha256") -> dict:
    raw = (text or "").encode("utf-8")
    algo = (algo or "sha256").lower()
    out = {}
    if algo in ("md5", "all"):
        out["md5"] = hashlib.md5(raw).hexdigest()
    if algo in ("sha1", "all"):
        out["sha1"] = hashlib.sha1(raw).hexdigest()
    if algo in ("sha256", "all"):
        out["sha256"] = hashlib.sha256(raw).hexdigest()
    if not out:
        out["sha256"] = hashlib.sha256(raw).hexdigest()
    return {"input_length": len(raw), "hashes": out, "note": "Apenas demonstração educacional."}


def base64_lab(text: str = "", mode: str = "encode", b64: str = "") -> dict:
    import base64
    mode = (mode or "encode").lower()
    try:
        if mode == "decode":
            decoded = base64.b64decode((b64 or text or "").encode("ascii"), validate=False)
            return {"mode": "decode", "result": decoded.decode("utf-8", errors="replace")}
        encoded = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
        return {"mode": "encode", "result": encoded}
    except Exception as e:
        return {"error": "Falha no Base64", "detail": str(e)[:200]}


def quality_rules() -> dict:
    return {
        "rules": [
            "Não criar botão falso",
            "Não criar card falso",
            "Não simular funcionalidade inexistente",
            "Não exigir autenticação desnecessariamente",
            "Não duplicar funcionalidades",
            "Não carregar tudo de uma vez",
            "Não quebrar funções existentes",
            "Toda feature: funcional, responsiva, segura, explicada, testada, otimizada",
        ]
    }
