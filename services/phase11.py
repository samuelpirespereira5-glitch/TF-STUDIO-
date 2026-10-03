"""JARVIS Phase 11.0 — Educação de Programação completa.

Extensão de phase10 / learning8 / programming7 / game_lab.
Não reescreve o core. Adiciona:
- Banco de vídeos oficiais (Curso em Vídeo / Guanabara) via YouTube embed
- Trilha "Nunca programei"
- Editor/playground client-side seguro
- Desafios com validação
- Progresso / conquistas
- Menu Educação expandido
- Integração com Mentor / Professor JARVIS
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone, date
from typing import Any

# ---------------------------------------------------------------------------
# Vídeos públicos oficiais (Curso em Vídeo / Gustavo Guanabara)
# Apenas IDs/playlists públicos — embed via YouTube, sem download.
# ---------------------------------------------------------------------------
VIDEO_CATALOG: list[dict[str, Any]] = [
    # Python — aulas principais (IDs públicos conhecidos)
    {
        "id": "py-01",
        "titulo": "Curso Python #01 — Seja um Programador",
        "descricao": "Introdução: o que é programação e por que Python.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "S9uPNppGsGo",
        "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B",
        "url_oficial": "https://www.youtube.com/watch?v=S9uPNppGsGo",
        "duracao": "29:07",
        "modulo": "python-mundo1",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["O que é programação", "Por que Python", "Primeiros passos"],
    },
    {
        "id": "py-02",
        "titulo": "Curso Python #02 — Para que serve o Python?",
        "descricao": "Aplicações reais da linguagem Python.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "Mp0vhMDI7fA",
        "playlist_id": "",
        "url_oficial": "https://www.youtube.com/watch?v=Mp0vhMDI7fA",
        "duracao": "21:53",
        "modulo": "python-mundo1",
        "ordem": 2,
        "ativo": True,
        "o_que_aprendo": ["Casos de uso", "Áreas de aplicação"],
    },
    {
        "id": "py-03",
        "titulo": "Curso Python #03 — Instalando o Python 3 e o IDLE",
        "descricao": "Instalação do ambiente.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "VuKvR1J2LQE",
        "url_oficial": "https://www.youtube.com/watch?v=VuKvR1J2LQE",
        "duracao": "17:49",
        "modulo": "python-mundo1",
        "ordem": 3,
        "ativo": True,
        "o_que_aprendo": ["Instalação", "IDLE"],
    },
    {
        "id": "py-04",
        "titulo": "Curso Python #04 — Primeiros comandos em Python 3",
        "descricao": "print, input e primeiros comandos.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "31llNGKWDdo",
        "url_oficial": "https://www.youtube.com/watch?v=31llNGKWDdo",
        "duracao": "27:33",
        "modulo": "python-mundo1",
        "ordem": 4,
        "ativo": True,
        "o_que_aprendo": ["print", "input", "comandos básicos"],
    },
    {
        "id": "py-06",
        "titulo": "Curso Python #06 — Tipos Primitivos e Saída de Dados",
        "descricao": "int, float, bool, str e formatação.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "hdDHg1p3YVc",
        "url_oficial": "https://www.youtube.com/watch?v=hdDHg1p3YVc",
        "duracao": "29:41",
        "modulo": "python-mundo1",
        "ordem": 6,
        "ativo": True,
        "o_que_aprendo": ["Tipos primitivos", "Saída de dados"],
    },
    {
        "id": "py-07",
        "titulo": "Curso Python #07 — Operadores Aritméticos",
        "descricao": "Soma, subtração, multiplicação, divisão e mais.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "Vw6gLypRKmY",
        "url_oficial": "https://www.youtube.com/watch?v=Vw6gLypRKmY",
        "duracao": "40:24",
        "modulo": "python-mundo1",
        "ordem": 7,
        "ativo": True,
        "o_que_aprendo": ["Operadores aritméticos"],
    },
    {
        "id": "py-10",
        "titulo": "Curso Python #10 — Condições (Parte 1)",
        "descricao": "if, else e tomada de decisão.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "K10u3XIf1-Q",
        "url_oficial": "https://www.youtube.com/watch?v=K10u3XIf1-Q",
        "duracao": "34:45",
        "modulo": "python-mundo1",
        "ordem": 10,
        "ativo": True,
        "o_que_aprendo": ["if", "else", "condições"],
    },
    # HTML5
    {
        "id": "html-00",
        "titulo": "Curso HTML5 — 00 — Site Completo (Trailer)",
        "descricao": "Apresentação do curso HTML5 + CSS3 + JS.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "html",
        "nivel": "iniciante",
        "video_id": "epDCjksKMok",
        "playlist_id": "PLHz_AreHm4dlAnJ_jJtV29RFxnPHDuk9o",
        "url_oficial": "https://www.youtube.com/watch?v=epDCjksKMok",
        "duracao": "05:16",
        "modulo": "html5",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["Visão geral do curso"],
    },
    {
        "id": "html-05",
        "titulo": "Curso HTML5 — 05 — Tags Básicas em HTML5",
        "descricao": "Tags fundamentais de HTML5.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "html",
        "nivel": "iniciante",
        "video_id": "EANOXuQsglo",
        "url_oficial": "https://www.youtube.com/watch?v=EANOXuQsglo",
        "duracao": "21:09",
        "modulo": "html5",
        "ordem": 5,
        "ativo": True,
        "o_que_aprendo": ["Tags básicas", "Estrutura de página"],
    },
    # HTML5/CSS3 atualizado
    {
        "id": "htmlcss-mod1",
        "titulo": "HTML5 e CSS3 — Módulo 1 (atualizado)",
        "descricao": "Início do curso atualizado de HTML5 + CSS3.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "html",
        "nivel": "iniciante",
        "video_id": "Ejkb_YpuHWs",
        "playlist_id": "PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n",
        "duracao": "módulo",
        "modulo": "htmlcss-mod1",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["Fundamentos HTML5", "CSS3 básico"],
    },
    # JavaScript
    {
        "id": "js-01",
        "titulo": "JavaScript — O que o JS é capaz de fazer?",
        "descricao": "Introdução ao JavaScript moderno.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "javascript",
        "nivel": "iniciante",
        "video_id": "Ptbk2af68e8",
        "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1",
        "url_oficial": "https://www.youtube.com/watch?v=Ptbk2af68e8",
        "duracao": "28:50",
        "modulo": "javascript",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["O que é JavaScript", "Possibilidades da linguagem"],
    },
    {
        "id": "js-04",
        "titulo": "JavaScript — Criando seu primeiro script",
        "descricao": "Primeiro código JavaScript no navegador.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "javascript",
        "nivel": "iniciante",
        "video_id": "OmmJBfcMJA8",
        "url_oficial": "https://www.youtube.com/watch?v=OmmJBfcMJA8",
        "duracao": "24:15",
        "modulo": "javascript",
        "ordem": 4,
        "ativo": True,
        "o_que_aprendo": ["Primeiro script", "Console", "alert"],
    },
]

# ---------------------------------------------------------------------------
# Trilha "Nunca programei" — extremamente simples
# ---------------------------------------------------------------------------
BEGINNER_TRACK = [
    {
        "id": "zero-01",
        "title": "O que é programação?",
        "explanation": "Programação é dar instruções claras para o computador fazer alguma coisa. Como uma receita de bolo: passo a passo.",
        "easy_explain": "Imagina que o computador é um robô bem obediente, mas um pouco bobinho: ele só faz exatamente o que você manda. Programar é escrever a lista de ordens para ele.",
        "analogy": "É igual ensinar alguém a fazer um sanduíche: 1) pegue o pão 2) passe a manteiga 3) coloque o queijo. Se faltar um passo, o sanduíche fica errado!",
        "steps_kid": ["Pense no que você quer que o computador faça", "Quebre em passos pequenos", "Escreva cada passo em código", "Teste e corrija"],
        "example": "Receita: 1) pegue o ovo 2) quebre 3) misture. Programa: 1) leia o nome 2) diga olá.",
        "code": '# Em Python isso vira:\nprint("Olá, mundo!")',
        "language": "python",
        "exercise": "Explique com suas palavras o que é um programa.",
        "challenge": "Pense em 3 coisas do dia a dia que poderiam ser automatizadas com um programa.",
        "hint": "Pense em tarefas repetitivas: calcular, organizar, responder.",
        "next": "zero-02",
    },
    {
        "id": "zero-02",
        "title": "O que é código?",
        "explanation": "Código é o texto que você escreve em uma linguagem que o computador entende (Python, JavaScript, etc.).",
        "easy_explain": "Código é tipo uma carta mágica que o computador sabe ler. Você escreve palavras especiais e ele obedece.",
        "analogy": "Se português é a língua que você fala com amigos, Python é a língua que você fala com o computador.",
        "steps_kid": ["Abra o editor", "Escreva o comando", "Aperte executar", "Veja o resultado na tela"],
        "example": 'print("Oi")  →  o computador mostra Oi na tela.',
        "code": 'print("Meu primeiro código")',
        "language": "python",
        "exercise": "Escreva um print com o seu nome.",
        "challenge": "Faça o programa imprimir duas linhas diferentes.",
        "hint": "Use print duas vezes, uma em cada linha.",
        "next": "zero-03",
    },
    {
        "id": "zero-03",
        "title": "Variáveis",
        "explanation": "Variável é como uma caixinha com um nome. Você guarda uma informação dentro e pode usar depois.",
        "easy_explain": "Uma variável é uma caixinha com etiqueta. Na etiqueta está o nome (ex: idade) e dentro você coloca o valor (ex: 10).",
        "analogy": "É como a gaveta da sua mesa: você escreve 'lápis' na frente e guarda os lápis lá. Quando precisar, abre a gaveta 'lápis'.",
        "steps_kid": ["Escolha um nome fácil", "Use o sinal = para guardar", "Depois use o nome para pegar o valor"],
        "example": 'nome = "João"\nprint(nome)  →  mostra João',
        "code": 'nome = "Maria"\nprint("Olá,", nome)',
        "language": "python",
        "exercise": "Crie uma variável idade e imprima.",
        "challenge": "Crie nome e cidade e imprima uma frase completa.",
        "hint": "idade = 20  e  print(idade)",
        "next": "zero-04",
        "visual": {"box": "nome", "value": '"João"'},
    },
    {
        "id": "zero-04",
        "title": "Texto e números",
        "explanation": "Texto fica entre aspas. Números não. 5 + 3 = 8. \"5\" + \"3\" junta textos: \"53\".",
        "easy_explain": "Números são para contar e calcular. Textos (strings) são palavras e frases e sempre vão entre aspas.",
        "analogy": "5 é cinco dedos. \"5\" é o desenho do número cinco no papel — você não soma desenhos, junta eles.",
        "steps_kid": ["Número: sem aspas", "Texto: com aspas", "Somar números usa +", "Juntar textos também usa +, mas vira uma frase"],
        "example": 'print(5 + 3)   # 8\nprint("5" + "3")  # 53',
        "code": 'a = 10\nb = 5\nprint(a + b)\nprint("resultado:", a + b)',
        "language": "python",
        "exercise": "Some dois números e imprima o resultado.",
        "challenge": "Calcule a média de 3 notas.",
        "hint": "(n1 + n2 + n3) / 3",
        "next": "zero-05",
    },
    {
        "id": "zero-05",
        "title": "Entrada e saída",
        "explanation": "Saída = mostrar algo (print). Entrada = receber do usuário (input).",
        "easy_explain": "print mostra na tela. input pergunta e espera você digitar. Assim o programa conversa com você!",
        "analogy": "print é o computador falando. input é você respondendo.",
        "steps_kid": ["print(\"oi\") mostra oi", "nome = input(\"Nome? \") guarda a resposta", "Use a variável depois"],
        "example": 'nome = input("Seu nome: ")\nprint("Oi,", nome)',
        "code": 'nome = input("Qual seu nome? ")\nprint("Bem-vindo,", nome)',
        "language": "python",
        "exercise": "Peça a idade e imprima daqui a 10 anos.",
        "challenge": "Peça dois números e mostre a soma.",
        "hint": "idade = int(input(...))",
        "next": "zero-06",
    },
    {
        "id": "zero-06",
        "title": "Condições",
        "explanation": "if decide: SE algo for verdade, faça isto; SENÃO, faça aquilo.",
        "easy_explain": "if é o 'se'. Se a condição for verdade, faz uma coisa; senão (else), faz outra.",
        "analogy": "Se estiver chovendo, leve guarda-chuva. Senão, vá de óculos de sol.",
        "steps_kid": ["Escreva if condição:", "Indentação no que acontece se for verdade", "else: para o caminho contrário"],
        "example": 'idade = 18\nif idade >= 18:\n    print("maior")\nelse:\n    print("menor")',
        "code": 'idade = int(input("Idade: "))\nif idade >= 18:\n    print("Você é maior de idade")\nelse:\n    print("Você é menor de idade")',
        "language": "python",
        "exercise": "Peça uma nota e diga se passou (>= 7).",
        "challenge": "Classifique temperatura: frio / agradável / quente.",
        "hint": "Use if / elif / else",
        "next": "zero-07",
    },
    {
        "id": "zero-07",
        "title": "Repetições",
        "easy_explain": "Loops são para não ficar escrevendo a mesma coisa mil vezes. O computador repete sozinho.",
        "analogy": "É como contar de 1 até 100: em vez de falar cada número, você diz 'conte de 1 a 100'.",
        "steps_kid": ["for i in range(n): repete n vezes", "while condição: repete enquanto for verdade", "Cuidado para não criar loop infinito"],
        "explanation": "Loops repetem instruções. for conta. while continua enquanto a condição for verdadeira.",
        "example": "for i in range(5):\n    print(i)",
        "code": 'for i in range(1, 6):\n    print("Contagem:", i)',
        "language": "python",
        "exercise": "Imprima os números de 1 a 10.",
        "challenge": "Some todos os números de 1 a 100.",
        "hint": "total = 0; for i in range(1,101): total += i",
        "next": "zero-08",
    },
    {
        "id": "zero-08",
        "title": "Funções",
        "easy_explain": "Função é um atalho: você ensina um truque uma vez e chama pelo nome sempre que precisar.",
        "analogy": "É como ter um botão 'fazer sanduíche': você programou os passos uma vez e depois só aperta o botão.",
        "steps_kid": ["def nome():", "Coloque os passos dentro", "Chame nome() quando quiser usar"],
        "explanation": "Função é um bloco com nome que você pode reutilizar. def nome():",
        "example": 'def cumprimentar(nome):\n    print("Olá,", nome)\ncumprimentar("Ana")',
        "code": 'def somar(a, b):\n    return a + b\nprint(somar(3, 5))',
        "language": "python",
        "exercise": "Crie uma função que multiplica dois números.",
        "challenge": "Função que recebe nome e idade e imprime uma apresentação.",
        "hint": "def nome(params): return ...",
        "next": "zero-09",
    },
    {
        "id": "zero-09",
        "title": "Listas",
        "easy_explain": "Lista é uma fileira de caixinhas numeradas começando do zero. Guarda vários valores juntos.",
        "analogy": "É como uma prateleira de brinquedos: posição 0, 1, 2... Você pega pelo número da prateleira.",
        "steps_kid": ["Crie com colchetes []", "Acesse com lista[0]", "Adicione com .append()"],
        "explanation": "Lista guarda vários valores em ordem. nomes = [\"Ana\", \"Bruno\"]",
        "example": 'frutas = ["maçã", "banana"]\nprint(frutas[0])\nfrutas.append("uva")',
        "code": 'notas = [7, 8, 9]\nprint("Média:", sum(notas) / len(notas))',
        "language": "python",
        "exercise": "Crie uma lista de 3 cores e imprima a segunda.",
        "challenge": "Peça 5 números, guarde em lista e mostre o maior.",
        "hint": "max(lista) ou percorra comparando",
        "next": "zero-10",
    },
    {
        "id": "zero-10",
        "title": "Primeiro projeto",
        "easy_explain": "Agora você junta tudo: perguntar, calcular, decidir e mostrar o resultado. Parabéns, isso já é um programinha de verdade!",
        "analogy": "É montar um Lego completo: cada peça (variável, if, print) encaixa e vira um brinquedo que funciona.",
        "steps_kid": ["Peça os dados", "Calcule", "Decida com if", "Mostre o resultado"],
        "explanation": "Junte o que aprendeu: variáveis, input, if, print. Um mini programa completo.",
        "example": "Calculadora simples de 2 números.",
        "code": '''print("=== Calculadora ===")
a = float(input("Número 1: "))
b = float(input("Número 2: "))
op = input("Operação (+ - * /): ")
if op == "+":
    print(a + b)
elif op == "-":
    print(a - b)
elif op == "*":
    print(a * b)
elif op == "/":
    print(a / b if b != 0 else "Divisão por zero!")
else:
    print("Operação inválida")''',
        "language": "python",
        "exercise": "Modifique a calculadora para aceitar também potência (**).",
        "challenge": "Crie um quiz de 3 perguntas com pontuação.",
        "hint": "Use variáveis de pontuação e if para cada resposta.",
        "next": None,
    },
]

# ---------------------------------------------------------------------------
# Desafios com validação simples (client-side friendly)
# ---------------------------------------------------------------------------
CHALLENGES: list[dict[str, Any]] = [
    {
        "id": "ch-var-01",
        "titulo": "Criar variável",
        "descricao": "Crie uma variável chamada mensagem com o valor 'Olá JARVIS' e imprima.",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "variáveis",
        "starter_code": "# Seu código aqui\n",
        "tests": [{"expect_contains": "Olá JARVIS"}],
        "hints": ["Use mensagem = \"Olá JARVIS\"", "Depois print(mensagem)"],
        "solution": 'mensagem = "Olá JARVIS"\nprint(mensagem)',
        "explanation": "Variável guarda o texto; print mostra na tela.",
    },
    {
        "id": "ch-sum-01",
        "titulo": "Somar números",
        "descricao": "Some 15 e 27 e imprima o resultado.",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "aritmética",
        "starter_code": "# Some 15 + 27\n",
        "tests": [{"expect_contains": "42"}],
        "hints": ["print(15 + 27)"],
        "solution": "print(15 + 27)",
        "explanation": "Operador + soma números.",
    },
    {
        "id": "ch-if-01",
        "titulo": "Condição simples",
        "descricao": "Se a variável idade for >= 18, imprima 'maior', senão 'menor'. Use idade = 20.",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "condições",
        "starter_code": "idade = 20\n# complete\n",
        "tests": [{"expect_contains": "maior"}],
        "hints": ["if idade >= 18:", "print('maior')"],
        "solution": 'idade = 20\nif idade >= 18:\n    print("maior")\nelse:\n    print("menor")',
        "explanation": "if decide o caminho do programa.",
    },
    {
        "id": "ch-loop-01",
        "titulo": "Contador",
        "descricao": "Imprima os números de 1 a 5, um por linha.",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "loops",
        "starter_code": "# for i in range(...)\n",
        "tests": [{"expect_contains": "1"}, {"expect_contains": "5"}],
        "hints": ["for i in range(1, 6):", "print(i)"],
        "solution": "for i in range(1, 6):\n    print(i)",
        "explanation": "range(1, 6) gera 1,2,3,4,5.",
    },
    {
        "id": "ch-fun-01",
        "titulo": "Primeira função",
        "descricao": "Crie uma função dobro(n) que retorna n*2. Teste com print(dobro(7)).",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "funções",
        "starter_code": "def dobro(n):\n    # return ...\n\nprint(dobro(7))\n",
        "tests": [{"expect_contains": "14"}],
        "hints": ["return n * 2"],
        "solution": "def dobro(n):\n    return n * 2\n\nprint(dobro(7))",
        "explanation": "Funções encapsulam lógica reutilizável.",
    },
    {
        "id": "ch-bug-01",
        "titulo": "Caçador de bugs",
        "descricao": "O código abaixo tem um erro. Corrija para imprimir a soma.",
        "linguagem": "python",
        "nivel": "iniciante",
        "categoria": "debug",
        "starter_code": "a = 10\nb = 5\nprint(a + c)\n",
        "tests": [{"expect_contains": "15"}],
        "hints": ["A variável c não existe", "Troque c por b"],
        "solution": "a = 10\nb = 5\nprint(a + b)",
        "explanation": "NameError: variável inexistente. Use nomes que existem.",
    },
]

# ---------------------------------------------------------------------------
# Conquistas
# ---------------------------------------------------------------------------
ACHIEVEMENTS = [
    {"id": "first_code", "title": "Primeiro código", "desc": "Executou seu primeiro código"},
    {"id": "first_run", "title": "Primeiro programa executado", "desc": "Rodou um programa com sucesso"},
    {"id": "first_bug", "title": "Primeiro bug corrigido", "desc": "Corrigiu um erro de código"},
    {"id": "first_project", "title": "Primeiro projeto", "desc": "Criou e salvou um projeto"},
    {"id": "first_game", "title": "Primeiro jogo", "desc": "Criou ou modificou um jogo no Game Lab"},
    {"id": "challenges_10", "title": "10 desafios", "desc": "Completou 10 desafios"},
    {"id": "challenges_50", "title": "50 desafios", "desc": "Completou 50 desafios"},
    {"id": "first_loop", "title": "Primeiro loop", "desc": "Usou for ou while com sucesso"},
    {"id": "first_function", "title": "Primeira função", "desc": "Definiu e chamou uma função"},
    {"id": "first_site", "title": "Primeiro site", "desc": "Criou uma página HTML"},
    {"id": "zero_track", "title": "Do zero ao código", "desc": "Completou a trilha Nunca Programei"},
    {"id": "video_5", "title": "Aprendiz visual", "desc": "Assistiu 5 vídeos"},
]

# ---------------------------------------------------------------------------
# Menu Educação (estrutura)
# ---------------------------------------------------------------------------
EDU_MENU = [
    {"id": "inicio", "label": "Início", "icon": "🏠"},
    {"id": "aprender", "label": "Aprender programação", "icon": "📘"},
    {"id": "cursos", "label": "Cursos", "icon": "🎓"},
    {"id": "videos", "label": "Vídeos", "icon": "▶️"},
    {"id": "aulas", "label": "Aulas", "icon": "📝"},
    {"id": "exercicios", "label": "Exercícios", "icon": "✏️"},
    {"id": "desafios", "label": "Desafios", "icon": "🎯"},
    {"id": "laboratorio", "label": "Laboratório", "icon": "🧪"},
    {"id": "criar-projeto", "label": "Criar projeto", "icon": "🛠️"},
    {"id": "game-lab", "label": "Game Lab", "icon": "🎮"},
    {"id": "progresso", "label": "Meu progresso", "icon": "📊"},
    {"id": "conquistas", "label": "Conquistas", "icon": "🏆"},
    {"id": "meus-projetos", "label": "Meus projetos", "icon": "📁"},
    {"id": "biblioteca", "label": "Biblioteca", "icon": "📚"},
]

# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------
def menu() -> list:
    return EDU_MENU


def _catalog() -> list:
    """Phase 13: merge extra official videos + enrich thumbnails without rewriting catalog."""
    try:
        from services import phase13
        items = phase13.merge_catalog(VIDEO_CATALOG)
        return [phase13.enrich_video(v) for v in items]
    except Exception:
        return list(VIDEO_CATALOG)


def videos(linguagem: str | None = None, ativo_only: bool = True) -> list:
    items = _catalog()
    if ativo_only:
        items = [v for v in items if v.get("ativo")]
    if linguagem:
        lg = linguagem.lower()
        items = [v for v in items if (v.get("linguagem") or "").lower() == lg]
    return sorted(items, key=lambda x: (x.get("modulo") or "", x.get("ordem") or 0))


def video_by_id(vid: str) -> dict | None:
    for v in _catalog():
        if v["id"] == vid:
            return dict(v)
    return None


def beginner_track() -> list:
    return BEGINNER_TRACK


def beginner_lesson(lid: str) -> dict | None:
    for L in BEGINNER_TRACK:
        if L["id"] == lid:
            return dict(L)
    return None


def challenges(categoria: str | None = None, nivel: str | None = None) -> list:
    items = CHALLENGES
    if categoria:
        items = [c for c in items if c.get("categoria") == categoria]
    if nivel:
        items = [c for c in items if c.get("nivel") == nivel]
    return items


def challenge_by_id(cid: str) -> dict | None:
    for c in CHALLENGES:
        if c["id"] == cid:
            return dict(c)
    return None


def achievements() -> list:
    return ACHIEVEMENTS


def daily_challenge() -> dict:
    """Desafio do dia baseado na data (estável por dia)."""
    day = date.today().toordinal()
    idx = day % len(CHALLENGES)
    ch = dict(CHALLENGES[idx])
    ch["daily"] = True
    ch["date"] = date.today().isoformat()
    return ch


def overview_phase11() -> dict:
    return {
        "version": "11.0",
        "menu": EDU_MENU,
        "videos_count": len([v for v in VIDEO_CATALOG if v.get("ativo")]),
        "beginner_lessons": len(BEGINNER_TRACK),
        "challenges_count": len(CHALLENGES),
        "achievements_count": len(ACHIEVEMENTS),
        "daily": daily_challenge(),
        "continue_hint": "Continue de onde parou na trilha ou assista um vídeo.",
        "sections": {
            "continue": "Continue aprendendo",
            "daily": "Desafio do dia",
            "track": "Minha trilha",
            "projects": "Projetos recentes",
            "videos": "Vídeos",
            "game_lab": "Game Lab",
        },
    }


def search_edu(q: str) -> dict:
    q = (q or "").strip().lower()
    if not q:
        return {"query": q, "results": []}
    results = []
    for v in videos():
        blob = f"{v.get('titulo','')} {v.get('descricao','')} {v.get('linguagem','')}".lower()
        if q in blob:
            results.append({"type": "video", "id": v["id"], "title": v["titulo"]})
    for L in BEGINNER_TRACK:
        blob = f"{L.get('title','')} {L.get('explanation','')}".lower()
        if q in blob:
            results.append({"type": "lesson", "id": L["id"], "title": L["title"]})
    for c in CHALLENGES:
        blob = f"{c.get('titulo','')} {c.get('descricao','')} {c.get('categoria','')}".lower()
        if q in blob:
            results.append({"type": "challenge", "id": c["id"], "title": c["titulo"]})
    return {"query": q, "results": results[:30]}


def professor_buttons() -> list:
    return [
        {"id": "simple", "label": "Explicar simples"},
        {"id": "example", "label": "Mostrar exemplo"},
        {"id": "steps", "label": "Explicar passo a passo"},
        {"id": "code", "label": "Mostrar código"},
        {"id": "run", "label": "Executar"},
        {"id": "hint", "label": "Me dê uma dica"},
        {"id": "where_wrong", "label": "Onde estou errando?"},
        {"id": "another_way", "label": "Explique de outro jeito"},
    ]


def project_templates() -> list:
    return [
        {"id": "calc", "name": "Calculadora", "lang": "html+js", "level": "iniciante"},
        {"id": "quiz", "name": "Quiz", "lang": "html+js", "level": "iniciante"},
        {"id": "todo", "name": "Lista de tarefas", "lang": "html+js", "level": "iniciante"},
        {"id": "site", "name": "Site simples", "lang": "html+css", "level": "iniciante"},
        {"id": "portfolio", "name": "Portfólio", "lang": "html+css", "level": "intermediário"},
        {"id": "game", "name": "Jogo", "lang": "js", "level": "intermediário"},
        {"id": "dashboard", "name": "Dashboard", "lang": "html+css+js", "level": "intermediário"},
        {"id": "bot", "name": "Bot educativo", "lang": "python", "level": "intermediário"},
        {"id": "interactive", "name": "Página interativa", "lang": "html+js", "level": "iniciante"},
        {"id": "api-demo", "name": "API de demonstração", "lang": "python", "level": "avançado"},
    ]
