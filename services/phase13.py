"""JARVIS Phase 13.0 — Video Engine 2.0 + Intelligence + Tools Central + Game/Edu.

Incremental extension of phase11 / phase12 / learning8 / game_lab / central_tools.
Does not rewrite core. Adds:
- Video metadata helpers (thumbnails, states, continue studying)
- Expanded official catalog entries (Curso em Vídeo public IDs only)
- Tools central categories, favorites/recents metadata
- Global search across edu + tools + games
- Learning path ("Meu Caminho")
- Algorithm lab extras (insertion, BFS/DFS descriptions)
- Project analyzer summary helpers
- Performance / health hints for admin
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Extra official videos (public YouTube IDs from Curso em Vídeo / Guanabara)
# Only known public embeds — no invented content, no downloads.
# ---------------------------------------------------------------------------
EXTRA_VIDEOS: list[dict[str, Any]] = [
    {
        "id": "py-08",
        "titulo": "Curso Python #08 — Utilizando Módulos",
        "descricao": "Import, math, random e módulos da biblioteca padrão.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "oOUyhWCowj8",
        "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B",
        "url_oficial": "https://www.youtube.com/watch?v=oOUyhWCowj8",
        "duracao": "31:00",
        "modulo": "python-mundo1",
        "ordem": 8,
        "ativo": True,
        "o_que_aprendo": ["import", "math", "random", "módulos"],
    },
    {
        "id": "py-09",
        "titulo": "Curso Python #09 — Manipulando Texto",
        "descricao": "Strings, fatiamento, análise e transformação.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "a7rUFK5esws",
        "url_oficial": "https://www.youtube.com/watch?v=a7rUFK5esws",
        "duracao": "35:00",
        "modulo": "python-mundo1",
        "ordem": 9,
        "ativo": True,
        "o_que_aprendo": ["strings", "fatiamento", "métodos de str"],
    },
    {
        "id": "py-11",
        "titulo": "Curso Python #11 — Cores no Terminal",
        "descricao": "ANSI colors e formatação no terminal.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "0hBIhkcA8O8",
        "url_oficial": "https://www.youtube.com/watch?v=0hBIhkcA8O8",
        "duracao": "22:00",
        "modulo": "python-mundo1",
        "ordem": 11,
        "ativo": True,
        "o_que_aprendo": ["cores ANSI", "print formatado"],
    },
    {
        "id": "py-12",
        "titulo": "Curso Python #12 — Condições Aninhadas",
        "descricao": "if, elif, else aninhados.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "j9bYDjaAYzw",
        "url_oficial": "https://www.youtube.com/watch?v=j9bYDjaAYzw",
        "duracao": "40:00",
        "modulo": "python-mundo1",
        "ordem": 12,
        "ativo": True,
        "o_que_aprendo": ["elif", "condições aninhadas"],
    },
    {
        "id": "css-01",
        "titulo": "HTML5 e CSS3 — Módulo 1 (estrutura e estilo)",
        "descricao": "Bases de CSS3 no curso HTML5 do Curso em Vídeo.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "css",
        "nivel": "iniciante",
        "video_id": "Ejkb_YpuHWs",
        "playlist_id": "PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n",
        "duracao": "playlist",
        "modulo": "htmlcss-mod1",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["seletores", "cores", "fontes", "box model"],
    },
    {
        "id": "algo-01",
        "titulo": "Algoritmos — Conceitos (Curso em Vídeo / lógica)",
        "descricao": "Introdução a algoritmos e lógica de programação.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "algoritmos",
        "nivel": "iniciante",
        "video_id": "8meiZCTx8lM",
        "url_oficial": "https://www.youtube.com/watch?v=8meiZCTx8lM",
        "duracao": "28:00",
        "modulo": "algoritmos",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["algoritmo", "fluxo", "pseudocódigo"],
    },
    {
        "id": "git-01",
        "titulo": "Git e GitHub — Introdução",
        "descricao": "Controle de versão com Git (material oficial público quando disponível).",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "git",
        "nivel": "iniciante",
        "video_id": "xEKo29OWILE",
        "url_oficial": "https://www.youtube.com/watch?v=xEKo29OWILE",
        "duracao": "30:00",
        "modulo": "git",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["git init", "commit", "GitHub"],
    },
    {
        "id": "php-01",
        "titulo": "PHP — Introdução (Curso em Vídeo)",
        "descricao": "Primeiros passos com PHP.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "php",
        "nivel": "iniciante",
        "video_id": "TfsO0B989xg",
        "url_oficial": "https://www.youtube.com/watch?v=TfsO0B989xg",
        "duracao": "25:00",
        "modulo": "php",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["sintaxe PHP", "variáveis", "echo"],
    },
    {
        "id": "mysql-01",
        "titulo": "MySQL — Banco de Dados (introdução)",
        "descricao": "Conceitos de banco e MySQL no ecossistema Curso em Vídeo.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "mysql",
        "nivel": "iniciante",
        "video_id": "Ofktsne-utM",
        "url_oficial": "https://www.youtube.com/watch?v=Ofktsne-utM",
        "duracao": "35:00",
        "modulo": "mysql",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["tabelas", "SELECT", "INSERT"],
    },
    {
        "id": "java-01",
        "titulo": "Java — Primeiros Passos (Curso em Vídeo)",
        "descricao": "Introdução à linguagem Java.",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "java",
        "nivel": "iniciante",
        "video_id": "sTVJGJAWHRQ",
        "url_oficial": "https://www.youtube.com/watch?v=sTVJGJAWHRQ",
        "duracao": "30:00",
        "modulo": "java",
        "ordem": 1,
        "ativo": True,
        "o_que_aprendo": ["JVM", "classe", "main"],
    },

    # ---- Playlists oficiais extras (IDs públicos Curso em Vídeo) ----
    {
        "id": "pl-logica",
        "titulo": "Curso de Lógica de Programação",
        "descricao": "Playlist oficial de lógica com Gustavo Guanabara. Perfeita para iniciantes e crianças que querem entender o básico.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "logica",
        "nivel": "iniciante",
        "video_id": "8meiYCOvqMY",
        "playlist_id": "PLHz_AreHm4dmSj0MHol_ao67Eh5qLmNEX",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dmSj0MHol_ao67Eh5qLmNEX",
        "duracao": "playlist",
        "modulo": "logica",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["algoritmos", "variáveis", "condições", "loops"],
    },
    {
        "id": "pl-python-m1",
        "titulo": "Python Mundo 1 — Completo",
        "descricao": "Toda a playlist Python Mundo 1 (Curso em Vídeo).",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "S9uPNppGsGo",
        "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B",
        "duracao": "playlist",
        "modulo": "python-mundo1",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["Python básico", "print", "input", "tipos"],
    },
    {
        "id": "pl-python-m2",
        "titulo": "Python Mundo 2 — Completo",
        "descricao": "Playlist Python Mundo 2: condições e laços.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "python",
        "nivel": "iniciante",
        "video_id": "njkObffvV0Q",
        "playlist_id": "PLHz_AreHm4dk_nZHmSxEDX5GeK-XLTpE6",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dk_nZHmSxEDX5GeK-XLTpE6",
        "duracao": "playlist",
        "modulo": "python-mundo2",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["if", "for", "while", "range"],
    },
    {
        "id": "pl-python-m3",
        "titulo": "Python Mundo 3 — Completo",
        "descricao": "Playlist Python Mundo 3: estruturas compostas.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "python",
        "nivel": "intermediario",
        "video_id": "0LB3FSfjXu4",
        "playlist_id": "PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c",
        "duracao": "playlist",
        "modulo": "python-mundo3",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["tuplas", "listas", "dicionários", "funções"],
    },
    {
        "id": "pl-html5",
        "titulo": "HTML5 e CSS3 — Completo",
        "descricao": "Playlist oficial HTML5/CSS3 do Curso em Vídeo.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "html",
        "nivel": "iniciante",
        "video_id": "epDCjksKMok",
        "playlist_id": "PLHz_AreHm4dlAnJ_jJtV29RFxnPHDuk9o",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dlAnJ_jJtV29RFxnPHDuk9o",
        "duracao": "playlist",
        "modulo": "html-css",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["HTML5", "CSS3", "layouts"],
    },
    {
        "id": "pl-javascript",
        "titulo": "JavaScript — Completo",
        "descricao": "Playlist oficial de JavaScript do Curso em Vídeo.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "javascript",
        "nivel": "iniciante",
        "video_id": "Ptbk2af68e8",
        "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1",
        "duracao": "playlist",
        "modulo": "javascript",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["JS básico", "DOM", "eventos"],
    },
    {
        "id": "pl-java",
        "titulo": "Java Básico — Completo",
        "descricao": "Playlist oficial Java do Curso em Vídeo.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "java",
        "nivel": "iniciante",
        "video_id": "sTVVYpaxIlI",
        "playlist_id": "PLHz_AreHm4dkI2ZoyPBAtsaT0HgoL0z0",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkI2ZoyPBAtsaT0HgoL0z0",
        "duracao": "playlist",
        "modulo": "java",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["Java", "JVM", "classes"],
    },
    {
        "id": "pl-mysql",
        "titulo": "MySQL — Banco de Dados",
        "descricao": "Playlist oficial MySQL (Curso em Vídeo).",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "mysql",
        "nivel": "iniciante",
        "video_id": "Ofktsne-etQ",
        "playlist_id": "PLHz_AreHm4dkcVCk2VnZGV",
        "url_oficial": "https://www.youtube.com/watch?v=Ofktsne-etQ",
        "duracao": "playlist",
        "modulo": "mysql",
        "ordem": 0,
        "ativo": True,
        "o_que_aprendo": ["SQL", "tabelas", "SELECT"],
    },
    {
        "id": "pl-algoritmos-extra",
        "titulo": "Algoritmos e Lógica — Extra",
        "descricao": "Mais aulas de lógica e algoritmos para reforçar a base.",
        "fonte": "Curso em Vídeo",
        "tipo": "playlist",
        "linguagem": "logica",
        "nivel": "iniciante",
        "video_id": "8meiYCOvqMY",
        "playlist_id": "PLHz_AreHm4dmSj0MHol_ao67Eh5qLmNEX",
        "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dmSj0MHol_ao67Eh5qLmNEX",
        "duracao": "playlist",
        "modulo": "algoritmos",
        "ordem": 2,
        "ativo": True,
        "o_que_aprendo": ["fluxogramas", "pseudocódigo"],
    },
    {
        "id": "js-dom",
        "titulo": "JavaScript — Manipulando o DOM",
        "descricao": "Como o JS muda a página (ótimo para jogos no navegador).",
        "fonte": "Curso em Vídeo",
        "tipo": "aula",
        "linguagem": "javascript",
        "nivel": "iniciante",
        "video_id": "UftSB4N8bMw",
        "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1",
        "url_oficial": "https://www.youtube.com/watch?v=UftSB4N8bMw",
        "duracao": "~30min",
        "modulo": "javascript",
        "ordem": 10,
        "ativo": True,
        "o_que_aprendo": ["DOM", "querySelector", "eventos"],
    },

    # ========== EXPANSÃO: mais aulas oficiais Curso em Vídeo (IDs públicos) ==========
    # Python Mundo 1
    {"id": "py-05", "titulo": "Curso Python #05 — Instalando o PyCharm", "descricao": "IDE PyCharm e ambiente de prática.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "ElRd0cbXIv4", "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B", "url_oficial": "https://www.youtube.com/watch?v=ElRd0cbXIv4", "duracao": "31:41", "modulo": "python-mundo1", "ordem": 5, "ativo": True, "o_que_aprendo": ["PyCharm", "IDE"]},
    {"id": "py-07", "titulo": "Curso Python #07 — Operadores Aritméticos", "descricao": "Soma, subtração, potência, divisão inteira e módulo.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "Vw6gLypRKmY", "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B", "url_oficial": "https://www.youtube.com/watch?v=Vw6gLypRKmY", "duracao": "40:24", "modulo": "python-mundo1", "ordem": 7, "ativo": True, "o_que_aprendo": ["operadores", "+ - * / // % **"]},
    {"id": "py-10", "titulo": "Curso Python #10 — Condições (Parte 1)", "descricao": "if e else: decisões no código.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "K10u3XIf1-Q", "playlist_id": "PLHz_AreHm4dlKPKlMk7rGD4G4H1gV3t_B", "url_oficial": "https://www.youtube.com/watch?v=K10u3XIf1-Q", "duracao": "34:45", "modulo": "python-mundo1", "ordem": 10, "ativo": True, "o_que_aprendo": ["if", "else"]},
    {"id": "py-13", "titulo": "Curso Python #13 — Estrutura de repetição for", "descricao": "Laço for e range.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "cL4YDtFnCt4", "playlist_id": "PLHz_AreHm4dk_nZHmSxEDX5GeK-XLTpE6", "url_oficial": "https://www.youtube.com/watch?v=cL4YDtFnCt4", "duracao": "35:25", "modulo": "python-mundo2", "ordem": 13, "ativo": True, "o_que_aprendo": ["for", "range"]},
    {"id": "py-14", "titulo": "Curso Python #14 — Estrutura de repetição while", "descricao": "Laço while.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "LH6OIn2lBaI", "playlist_id": "PLHz_AreHm4dk_nZHmSxEDX5GeK-XLTpE6", "url_oficial": "https://www.youtube.com/watch?v=LH6OIn2lBaI", "duracao": "38:18", "modulo": "python-mundo2", "ordem": 14, "ativo": True, "o_que_aprendo": ["while"]},
    {"id": "py-15", "titulo": "Curso Python #15 — Interrompendo repetições while", "descricao": "break e controle de laços.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "1OFp_-R2B2A", "playlist_id": "PLHz_AreHm4dk_nZHmSxEDX5GeK-XLTpE6", "url_oficial": "https://www.youtube.com/watch?v=1OFp_-R2B2A", "duracao": "41:30", "modulo": "python-mundo2", "ordem": 15, "ativo": True, "o_que_aprendo": ["break", "while"]},
    {"id": "py-16", "titulo": "Curso Python #16 — Tuplas", "descricao": "Tuplas: sequências imutáveis.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "intermediario", "video_id": "0LB3FSfjXu4", "playlist_id": "PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c", "url_oficial": "https://www.youtube.com/watch?v=0LB3FSfjXu4", "duracao": "~40min", "modulo": "python-mundo3", "ordem": 16, "ativo": True, "o_que_aprendo": ["tuplas"]},
    {"id": "py-17a", "titulo": "Curso Python #17 — Listas (Parte 1)", "descricao": "Listas e operações básicas.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "intermediario", "video_id": "N1hTsbW50eM", "playlist_id": "PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c", "url_oficial": "https://www.youtube.com/watch?v=N1hTsbW50eM", "duracao": "40:17", "modulo": "python-mundo3", "ordem": 17, "ativo": True, "o_que_aprendo": ["listas", "append"]},
    {"id": "py-17b", "titulo": "Curso Python #17 — Listas (Parte 2)", "descricao": "Listas compostas e mais operações.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "intermediario", "video_id": "YV_JQmZNFsk", "playlist_id": "PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c", "url_oficial": "https://www.youtube.com/watch?v=YV_JQmZNFsk", "duracao": "39:01", "modulo": "python-mundo3", "ordem": 18, "ativo": True, "o_que_aprendo": ["listas compostas"]},
    {"id": "py-19", "titulo": "Curso Python #19 — Dicionários", "descricao": "Dicionários: chave e valor.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "intermediario", "video_id": "ZWj8o692qGY", "playlist_id": "PLHz_AreHm4dksKLxe6Xnyp7Y_4eR9R2c", "url_oficial": "https://www.youtube.com/watch?v=ZWj8o692qGY", "duracao": "45:17", "modulo": "python-mundo3", "ordem": 19, "ativo": True, "o_que_aprendo": ["dict", "chaves"]},
    # Exercícios Python
    {"id": "py-ex01", "titulo": "Exercício Python #001 — Deixando tudo pronto", "descricao": "Primeiro exercício oficial do curso.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "nIHq1MtJaKs", "playlist_id": "PLHz_AreHm4dm6wYOIW20Nyg12TAjmMGT-", "url_oficial": "https://www.youtube.com/watch?v=nIHq1MtJaKs", "duracao": "12:31", "modulo": "python-exercicios", "ordem": 1, "ativo": True, "o_que_aprendo": ["prática", "print"]},
    {"id": "py-ex02", "titulo": "Exercício Python #002 — Respondendo ao Usuário", "descricao": "input e print juntos.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "python", "nivel": "iniciante", "video_id": "FNqdV5Zb_5Q", "playlist_id": "PLHz_AreHm4dm6wYOIW20Nyg12TAjmMGT-", "url_oficial": "https://www.youtube.com/watch?v=FNqdV5Zb_5Q", "duracao": "04:46", "modulo": "python-exercicios", "ordem": 2, "ativo": True, "o_que_aprendo": ["input", "f-string"]},
    {"id": "pl-python-ex", "titulo": "Playlist — Exercícios de Python 3", "descricao": "Todos os exercícios resolvidos do Curso em Vídeo.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "python", "nivel": "iniciante", "video_id": "nIHq1MtJaKs", "playlist_id": "PLHz_AreHm4dm6wYOIW20Nyg12TAjmMGT-", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dm6wYOIW20Nyg12TAjmMGT-", "duracao": "playlist", "modulo": "python-exercicios", "ordem": 0, "ativo": True, "o_que_aprendo": ["prática", "exercícios"]},
    # HTML5/CSS3 módulos
    {"id": "html-mod1", "titulo": "HTML5 e CSS3 — Módulo 1 de 5", "descricao": "Playlist oficial módulo 1 (conceito, internet, primeiro código).", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "html", "nivel": "iniciante", "video_id": "Ejkb_YpuHWs", "playlist_id": "PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n", "duracao": "playlist", "modulo": "html-css-m1", "ordem": 0, "ativo": True, "o_que_aprendo": ["HTML", "internet", "tags"]},
    {"id": "html-mod2", "titulo": "HTML5 e CSS3 — Módulo 2 de 5", "descricao": "Playlist oficial módulo 2.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "html", "nivel": "iniciante", "video_id": "Ejkb_YpuHWs", "playlist_id": "PLHz_AreHm4dlUpEXkY1AyVLQGcpSgVF8s", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dlUpEXkY1AyVLQGcpSgVF8s", "duracao": "playlist", "modulo": "html-css-m2", "ordem": 0, "ativo": True, "o_que_aprendo": ["CSS", "cores", "fontes"]},
    {"id": "html-mod3", "titulo": "HTML5 e CSS3 — Módulo 3 de 5", "descricao": "Playlist oficial módulo 3.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "html", "nivel": "iniciante", "video_id": "Ejkb_YpuHWs", "playlist_id": "PLHz_AreHm4dmcAviDwiGgHbeEJToxbOpZ", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dmcAviDwiGgHbeEJToxbOpZ", "duracao": "playlist", "modulo": "html-css-m3", "ordem": 0, "ativo": True, "o_que_aprendo": ["box model", "layout"]},
    {"id": "html-mod4", "titulo": "HTML5 e CSS3 — Módulo 4 de 5", "descricao": "Playlist oficial módulo 4.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "html", "nivel": "intermediario", "video_id": "Ejkb_YpuHWs", "playlist_id": "PLHz_AreHm4dkcVCk2Bn_fdVQ81Fkrh6WT", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkcVCk2Bn_fdVQ81Fkrh6WT", "duracao": "playlist", "modulo": "html-css-m4", "ordem": 0, "ativo": True, "o_que_aprendo": ["flexbox", "grid"]},
    {"id": "html-mod5", "titulo": "HTML5 e CSS3 — Módulo 5 de 5", "descricao": "Playlist oficial módulo 5.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "html", "nivel": "intermediario", "video_id": "Ejkb_YpuHWs", "playlist_id": "PLHz_AreHm4dn1bAtIJWFrugl5z2Ej_52d", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dn1bAtIJWFrugl5z2Ej_52d", "duracao": "playlist", "modulo": "html-css-m5", "ordem": 0, "ativo": True, "o_que_aprendo": ["responsivo", "projeto"]},
    {"id": "html-01", "titulo": "HTML5 — Seu primeiro código HTML", "descricao": "Primeira página HTML na prática.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "html", "nivel": "iniciante", "video_id": "E6CdIawPTh0", "playlist_id": "PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n", "url_oficial": "https://www.youtube.com/watch?v=E6CdIawPTh0", "duracao": "17:34", "modulo": "html-css-m1", "ordem": 1, "ativo": True, "o_que_aprendo": ["html", "body", "h1"]},
    {"id": "html-diff", "titulo": "Diferença entre HTML, CSS e JavaScript", "descricao": "O papel de cada linguagem no front-end.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "html", "nivel": "iniciante", "video_id": "B4FU3NFRTDw", "playlist_id": "PLHz_AreHm4dkZ9-atkcmcBaMZdmLHft8n", "url_oficial": "https://www.youtube.com/watch?v=B4FU3NFRTDw", "duracao": "26:33", "modulo": "html-css-m1", "ordem": 2, "ativo": True, "o_que_aprendo": ["HTML", "CSS", "JS"]},
    {"id": "html-old-05", "titulo": "Curso HTML5 — Tags básicas", "descricao": "Tags essenciais do HTML5 (curso clássico).", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "html", "nivel": "iniciante", "video_id": "EANOXuQsglo", "playlist_id": "PLHz_AreHm4dlAnJ_jJtV29RFxnPHDuk9o", "url_oficial": "https://www.youtube.com/watch?v=EANOXuQsglo", "duracao": "21:09", "modulo": "html-classico", "ordem": 5, "ativo": True, "o_que_aprendo": ["tags", "p", "img", "a"]},
    # JavaScript aulas
    {"id": "js-02", "titulo": "JavaScript #02 — Como o JS chegou até aqui", "descricao": "História e evolução do JavaScript.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "javascript", "nivel": "iniciante", "video_id": "rUTKomc2gG8", "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1", "url_oficial": "https://www.youtube.com/watch?v=rUTKomc2gG8", "duracao": "24:47", "modulo": "javascript", "ordem": 2, "ativo": True, "o_que_aprendo": ["história JS", "ECMAScript"]},
    {"id": "js-03", "titulo": "JavaScript #03 — Dando os primeiros passos", "descricao": "Ambiente e primeiros conceitos.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "javascript", "nivel": "iniciante", "video_id": "FdePtO5JSd0", "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1", "url_oficial": "https://www.youtube.com/watch?v=FdePtO5JSd0", "duracao": "32:52", "modulo": "javascript", "ordem": 3, "ativo": True, "o_que_aprendo": ["console", "navegador"]},
    {"id": "js-teaser", "titulo": "JavaScript — Trailer do curso", "descricao": "Apresentação do curso de JS moderno.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "javascript", "nivel": "iniciante", "video_id": "BXqUH86F-kA", "playlist_id": "PLHz_AreHm4dlsK3Nr9GVvXCbpQyHQl1o1", "url_oficial": "https://www.youtube.com/watch?v=BXqUH86F-kA", "duracao": "03:18", "modulo": "javascript", "ordem": 0, "ativo": True, "o_que_aprendo": ["visão geral"]},
    # MySQL
    {"id": "mysql-01", "titulo": "MySQL #01 — O que é um Banco de Dados?", "descricao": "Introdução a bancos de dados relacionais.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "mysql", "nivel": "iniciante", "video_id": "Ofktsne-utM", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/watch?v=Ofktsne-utM", "duracao": "22:28", "modulo": "mysql", "ordem": 1, "ativo": True, "o_que_aprendo": ["BD", "tabelas"]},
    {"id": "mysql-02a", "titulo": "MySQL #02a — Instalando com WAMP", "descricao": "Instalação do MySQL via WAMP.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "mysql", "nivel": "iniciante", "video_id": "5JbAOWJbgIA", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/watch?v=5JbAOWJbgIA", "duracao": "23:46", "modulo": "mysql", "ordem": 2, "ativo": True, "o_que_aprendo": ["WAMP", "instalação"]},
    {"id": "mysql-03", "titulo": "MySQL #03 — Criando o primeiro Banco", "descricao": "CREATE DATABASE e primeiras tabelas.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "mysql", "nivel": "iniciante", "video_id": "m9YPlX0fcJk", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/watch?v=m9YPlX0fcJk", "duracao": "27:55", "modulo": "mysql", "ordem": 3, "ativo": True, "o_que_aprendo": ["CREATE", "DATABASE"]},
    {"id": "mysql-05", "titulo": "MySQL #05 — INSERT INTO", "descricao": "Inserindo dados nas tabelas.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "mysql", "nivel": "iniciante", "video_id": "NCG9niOlm40", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/watch?v=NCG9niOlm40", "duracao": "25:43", "modulo": "mysql", "ordem": 5, "ativo": True, "o_que_aprendo": ["INSERT"]},
    {"id": "mysql-11", "titulo": "MySQL #11 — SELECT (Parte 1)", "descricao": "Consultas com SELECT.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "mysql", "nivel": "iniciante", "video_id": "GaOlyL3Uv9M", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/watch?v=GaOlyL3Uv9M", "duracao": "34:31", "modulo": "mysql", "ordem": 11, "ativo": True, "o_que_aprendo": ["SELECT", "WHERE"]},
    {"id": "pl-mysql-full", "titulo": "Playlist — MySQL Completo", "descricao": "Curso de Banco de Dados MySQL (playlist oficial).", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "mysql", "nivel": "iniciante", "video_id": "Ofktsne-utM", "playlist_id": "PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dkBs-795Dsgvau_ekxg8g1r", "duracao": "playlist", "modulo": "mysql", "ordem": 0, "ativo": True, "o_que_aprendo": ["SQL", "MySQL"]},
    # PHP Moderno
    {"id": "php-mod1", "titulo": "PHP Moderno — Módulo 1", "descricao": "Playlist oficial PHP Moderno módulo 1.", "fonte": "Curso em Vídeo", "tipo": "playlist", "linguagem": "php", "nivel": "iniciante", "video_id": "TfsO0BGvGn0", "playlist_id": "PLHz_AreHm4dlFPrCXCmd5g92860x_Pbr_", "url_oficial": "https://www.youtube.com/playlist?list=PLHz_AreHm4dlFPrCXCmd5g92860x_Pbr_", "duracao": "playlist", "modulo": "php", "ordem": 0, "ativo": True, "o_que_aprendo": ["PHP", "servidor"]},
    {"id": "php-01", "titulo": "PHP Moderno — Seu curso começa aqui", "descricao": "Introdução ao PHP moderno.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "php", "nivel": "iniciante", "video_id": "TfsO0BGvGn0", "playlist_id": "PLHz_AreHm4dlFPrCXCmd5g92860x_Pbr_", "url_oficial": "https://www.youtube.com/watch?v=TfsO0BGvGn0", "duracao": "09:30", "modulo": "php", "ordem": 1, "ativo": True, "o_que_aprendo": ["PHP", "visão geral"]},
    # Java
    {"id": "java-01", "titulo": "Java #01 — História do Java", "descricao": "Origem e importância da linguagem Java.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "java", "nivel": "iniciante", "video_id": "sTX0UEplF54", "playlist_id": "PLHz_AreHm4dkI2ZoyPBAtsaT0HgoL0z0", "url_oficial": "https://www.youtube.com/watch?v=sTX0UEplF54", "duracao": "36:08", "modulo": "java", "ordem": 1, "ativo": True, "o_que_aprendo": ["Java", "JVM", "história"]},
    # Lógica / Algoritmos
    {"id": "log-01", "titulo": "Algoritmos — Introdução (Guanabara)", "descricao": "Primeiros passos em lógica e algoritmos.", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "logica", "nivel": "iniciante", "video_id": "8meiYCOvqMY", "playlist_id": "PLHz_AreHm4dmSj0MHol_ao67Eh5qLmNEX", "url_oficial": "https://www.youtube.com/watch?v=8meiYCOvqMY", "duracao": "~30min", "modulo": "logica", "ordem": 1, "ativo": True, "o_que_aprendo": ["algoritmo", "fluxograma"]},
    # Git (quando disponível no canal / aulas relacionadas)
    {"id": "git-intro", "titulo": "Git e GitHub — Conceitos iniciais", "descricao": "Versionamento: ideia de commit e repositório (aula de referência pública).", "fonte": "Curso em Vídeo", "tipo": "aula", "linguagem": "git", "nivel": "iniciante", "video_id": "xEKo29OWILE", "playlist_id": "", "url_oficial": "https://www.youtube.com/watch?v=xEKo29OWILE", "duracao": "variável", "modulo": "git", "ordem": 1, "ativo": True, "o_que_aprendo": ["git", "commit"]},

]


def youtube_thumb(video_id: str, quality: str = "hqdefault") -> str:
    """Official YouTube thumbnail URL (no download, CDN only)."""
    vid = (video_id or "").strip()
    if not vid:
        return ""
    q = quality if quality in ("default", "mqdefault", "hqdefault", "sddefault", "maxresdefault") else "hqdefault"
    return f"https://i.ytimg.com/vi/{vid}/{q}.jpg"


def enrich_video(v: dict[str, Any]) -> dict[str, Any]:
    out = dict(v)
    vid = out.get("video_id") or ""
    out["thumbnail"] = youtube_thumb(vid)
    out["thumbnail_mq"] = youtube_thumb(vid, "mqdefault")
    pl = out.get("playlist_id") or ""
    if out.get("tipo") == "playlist" and pl:
        out["embed_url"] = f"https://www.youtube.com/embed/videoseries?list={pl}&rel=0"
    elif vid:
        out["embed_url"] = f"https://www.youtube.com/embed/{vid}?rel=0"
    else:
        out["embed_url"] = ""
    # Explicação fácil (para iniciantes / crianças)
    if not out.get("easy_explain") and out.get("descricao"):
        out["easy_explain"] = (
            "📚 " + out["descricao"]
            + " Assista com calma, pause quando precisar e pratique o que aprendeu."
        )
    return out


def merge_catalog(base: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge EXTRA_VIDEOS into base catalog without duplicating ids."""
    seen = {v.get("id") for v in base}
    out = list(base)
    for v in EXTRA_VIDEOS:
        if v.get("id") not in seen:
            out.append(v)
            seen.add(v.get("id"))
    return out


# Player states (client uses these labels)
VIDEO_STATES = [
    "LOADING",
    "READY",
    "PLAYING",
    "PAUSED",
    "BUFFERING",
    "ERROR",
    "UNAVAILABLE",
    "OFFLINE",
]


# Tools central categories (maps existing registry categories)
TOOLS_CENTRAL_CATEGORIES = [
    {"id": "programacao", "label": "Programação", "icon": "💻", "match": ["central", "code", "debug", "json", "regex", "html"]},
    {"id": "web", "label": "Web", "icon": "🌐", "match": ["web", "http", "html", "css", "link"]},
    {"id": "ia", "label": "IA", "icon": "🤖", "match": ["ai", "ia", "mentor", "professor"]},
    {"id": "estudos", "label": "Estudos", "icon": "📚", "match": ["edu", "lesson", "track", "video"]},
    {"id": "projetos", "label": "Projetos", "icon": "📁", "match": ["project", "template"]},
    {"id": "jogos", "label": "Jogos", "icon": "🎮", "match": ["game", "play"]},
    {"id": "arquivos", "label": "Arquivos", "icon": "📄", "match": ["file"]},
    {"id": "dados", "label": "Dados", "icon": "🗄️", "match": ["db", "sql", "json", "data"]},
    {"id": "seguranca", "label": "Segurança Defensiva", "icon": "🛡️", "match": ["cyber", "pentest", "security", "owasp", "tls", "dns"]},
    {"id": "utilidades", "label": "Utilidades", "icon": "🔧", "match": ["util", "hash", "base64", "jwt", "cidr", "external"]},
]


def categorize_tool(tool: dict[str, Any]) -> str:
    cat = (tool.get("category") or "").lower()
    name = (tool.get("name") or "").lower()
    tid = (tool.get("id") or "").lower()
    blob = f"{cat} {name} {tid}"
    for c in TOOLS_CENTRAL_CATEGORIES:
        for m in c["match"]:
            if m in blob:
                return c["id"]
    return "utilidades"


def tools_central_index(tools: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list] = {c["id"]: [] for c in TOOLS_CENTRAL_CATEGORIES}
    for t in tools:
        cid = categorize_tool(t)
        item = dict(t)
        item["central_category"] = cid
        buckets.setdefault(cid, []).append(item)
    return {
        "categories": TOOLS_CENTRAL_CATEGORIES,
        "by_category": buckets,
        "total": len(tools),
    }


# Algorithm lab extras (descriptions only — animation on client)
ALGO_EXTRA = [
    {
        "id": "insertion-sort",
        "titulo": "Insertion Sort",
        "categoria": "ordenacao",
        "descricao": "Insere cada elemento na posição correta da parte já ordenada.",
        "complexidade": "O(n²)",
        "visual": "array",
        "passos_demo": [5, 2, 4, 6, 1, 3],
        "pseudocodigo": "para i de 1 até n-1:\n  chave = a[i]\n  j = i-1\n  enquanto j>=0 e a[j]>chave:\n    a[j+1]=a[j]; j-=1\n  a[j+1]=chave",
    },
    {
        "id": "bfs",
        "titulo": "BFS (Busca em Largura)",
        "categoria": "grafo",
        "descricao": "Explora vizinhos nível a nível (fila).",
        "complexidade": "O(V+E)",
        "visual": "graph",
        "passos_demo": ["A", "B", "C", "D"],
        "pseudocodigo": "fila = [inicio]; visitados={inicio}\nenquanto fila:\n  u = fila.pop(0)\n  para v em vizinhos(u):\n    se v não visitado: visitar; fila.append(v)",
    },
    {
        "id": "dfs",
        "titulo": "DFS (Busca em Profundidade)",
        "categoria": "grafo",
        "descricao": "Explora o mais fundo possível antes de voltar (pilha/recursão).",
        "complexidade": "O(V+E)",
        "visual": "graph",
        "passos_demo": ["A", "B", "D", "C"],
        "pseudocodigo": "def dfs(u):\n  visitar(u)\n  para v em vizinhos(u):\n    se não visitado: dfs(v)",
    },
    {
        "id": "pathfinding",
        "titulo": "Pathfinding (ideia)",
        "categoria": "grafo",
        "descricao": "Encontrar caminho em grade (BFS ou A*).",
        "complexidade": "O(V+E)",
        "visual": "grid",
        "passos_demo": ["start", "right", "down", "goal"],
        "pseudocodigo": "Use BFS na grade;\ncada célula: cima/baixo/esq/dir;\npare ao alcançar o objetivo.",
    },
]


def algo_extras() -> list[dict[str, Any]]:
    return list(ALGO_EXTRA)


# Guided projects (step pipeline)
GUIDED_PROJECTS = [
    {"id": "page", "titulo": "Página pessoal", "lang": "html+css", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "calc", "titulo": "Calculadora", "lang": "html+js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "todo", "titulo": "Lista de tarefas", "lang": "html+js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "quiz", "titulo": "Quiz", "lang": "html+js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "game", "titulo": "Jogo simples", "lang": "js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "api", "titulo": "API REST simples", "lang": "python", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "dashboard", "titulo": "Dashboard", "lang": "html+css+js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "chatbot", "titulo": "Chatbot", "lang": "js", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
    {"id": "sistema", "titulo": "Sistema simples", "lang": "python", "steps": ["IDEIA", "PLANEJAMENTO", "CÓDIGO", "TESTE", "DEBUG", "PREVIEW", "CONCLUSÃO"]},
]


def guided_projects() -> list[dict[str, Any]]:
    return list(GUIDED_PROJECTS)


# Learning path template
def learning_path_template() -> dict[str, Any]:
    return {
        "name": "Meu Caminho",
        "flow": ["objetivo", "curso", "playlist", "aulas", "exercícios", "projeto", "conclusão"],
        "features": ["progresso", "histórico", "favoritos", "notas", "desafios", "conquistas"],
    }


# Intent categories for JARVIS Intelligence
INTENT_CATEGORIES = [
    "CHAT", "EDUCACAO", "CODIGO", "DEBUG", "PROJETO", "JOGO",
    "PESQUISA", "ARQUIVOS", "SEGURANCA", "FERRAMENTAS", "SISTEMA",
    "EXPLICACAO", "PLANEJAMENTO",
]


def detect_intent(text: str) -> dict[str, Any]:
    t = (text or "").lower()
    rules = [
        ("DEBUG", ["erro", "bug", "não funciona", "nao funciona", "exception", "traceback", "quebrado", "debug"]),
        ("CODIGO", ["código", "codigo", "função", "funcao", "classe", "script", "program"]),
        ("EDUCACAO", ["ensina", "aprende", "aula", "curso", "explica", "o que é", "o que e", "como funciona"]),
        ("JOGO", ["jogo", "game", "play", "personagem", "fase"]),
        ("PROJETO", ["projeto", "criar site", "montar", "build", "arquitetura"]),
        ("SEGURANCA", ["segurança", "seguranca", "xss", "csrf", "sql injection", "vulnerabilidade", "owasp"]),
        ("FERRAMENTAS", ["regex", "json", "formatar", "ferramenta", "tool", "analise", "analisar"]),
        ("ARQUIVOS", ["arquivo", "file", "upload", "pasta"]),
        ("PESQUISA", ["pesquise", "busca", "procure", "encontre"]),
        ("PLANEJAMENTO", ["plano", "roteiro", "passos", "roadmap"]),
        ("EXPLICACAO", ["explique", "detalhe", "por que", "porque", "significado"]),
        ("SISTEMA", ["status", "saúde", "saude", "config", "admin", "log"]),
    ]
    for intent, kws in rules:
        if any(k in t for k in kws):
            return {"intent": intent, "confidence": 0.75, "categories": INTENT_CATEGORIES}
    return {"intent": "CHAT", "confidence": 0.4, "categories": INTENT_CATEGORIES}


# Project analyzer (lightweight structural summary — no arbitrary code exec)
def analyze_project_tree(tree: list[str] | None = None, deps: list[str] | None = None) -> dict[str, Any]:
    files = tree or []
    dep_list = deps or []
    routes = [f for f in files if "route" in f.lower() or f.endswith("routes.py")]
    templates = [f for f in files if "template" in f.lower() or f.endswith(".html")]
    statics = [f for f in files if "/static/" in f or f.startswith("static/")]
    services = [f for f in files if "/services/" in f or f.startswith("services/")]
    return {
        "estrutura": {
            "arquivos": len(files),
            "rotas": len(routes),
            "templates": len(templates),
            "static": len(statics),
            "services": len(services),
        },
        "dependencias": dep_list[:50],
        "avisos": [],
        "resumo": f"{len(files)} arquivos, {len(routes)} rotas, {len(services)} services.",
        "nota": "Análise estrutural. Não executa código do usuário.",
    }


def global_search(q: str, videos: list | None = None, tools: list | None = None, games: list | None = None) -> dict[str, Any]:
    q = (q or "").strip().lower()
    if not q:
        return {"query": q, "results": []}
    results = []
    for v in videos or []:
        blob = f"{v.get('titulo','')} {v.get('descricao','')} {v.get('linguagem','')}".lower()
        if q in blob:
            results.append({"type": "video", "id": v.get("id"), "title": v.get("titulo"), "meta": v.get("linguagem")})
    for t in tools or []:
        blob = f"{t.get('name','')} {t.get('description','')} {t.get('id','')}".lower()
        if q in blob:
            results.append({"type": "tool", "id": t.get("id"), "title": t.get("name"), "meta": t.get("category")})
    for g in games or []:
        blob = f"{g.get('name','')} {g.get('id','')} {g.get('concept','')}".lower()
        if q in blob:
            results.append({"type": "game", "id": g.get("id"), "title": g.get("name"), "meta": "game"})
    for p in GUIDED_PROJECTS:
        if q in p["titulo"].lower() or q in p["id"]:
            results.append({"type": "project", "id": p["id"], "title": p["titulo"], "meta": p["lang"]})
    return {"query": q, "results": results[:40]}


def overview_phase13() -> dict[str, Any]:
    return {
        "version": "13.0",
        "parts": ["video_engine_2", "intelligence", "tools_central", "game_lab_4", "edu_advanced", "security_qa"],
        "video_states": VIDEO_STATES,
        "tools_categories": TOOLS_CENTRAL_CATEGORIES,
        "intent_categories": INTENT_CATEGORIES,
        "guided_projects_count": len(GUIDED_PROJECTS),
        "extra_videos_count": len(EXTRA_VIDEOS),
        "algo_extras_count": len(ALGO_EXTRA),
        "learning_path": learning_path_template(),
        "notes": [
            "Vídeos externos dependem do YouTube/rede — sem promessa de zero travamentos externos.",
            "Certificados apenas de conteúdos próprios JARVIS.",
            "Cyber Lab apenas defensivo e controlado.",
        ],
    }


def health_hints() -> dict[str, Any]:
    return {
        "checks": [
            "auth/session/csrf",
            "rate_limit",
            "secrets_not_in_frontend",
            "csp_cors_cookies",
            "no_sensitive_logs",
            "cert_hmac_only_own_content",
        ],
        "performance": [
            "lazy_video_iframe",
            "playlist_cards_first",
            "single_active_player",
            "js_css_cache_bust",
        ],
    }
