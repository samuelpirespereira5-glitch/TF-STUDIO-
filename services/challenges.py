"""DESAFIOS PRÁTICOS — sites com problemas intencionais para o usuário
investigar, corrigir e ter a solução validada.

Filosofia igual à do debugger_service.py já existente: tudo aqui é
checagem ESTÁTICA de verdade sobre o HTML/CSS/JS real do arquivo — nada
de IA "achando" que o usuário acertou. Cada desafio tem:

  id, title, category, difficulty, summary, mission (o que investigar),
  html (o site quebrado de propósito), hints (dicas progressivas),
  validate(html) -> {"passed": bool, "checks": [...]}

Um desafio "iniciado" vira um site normal (reaproveita sites_service:
mesma pasta, mesmo index.html, mesmo Editor/Depurador/Preview que já
existem) — só ganha alguns campos extras no site.json:
  is_challenge, challenge_id, challenge_status, challenge_attempts,
  challenge_started_at, challenge_completed_at.

Isso evita duplicar qualquer funcionalidade: criar site, editar código,
pré-visualizar, depurar (aba "Depurar" já existente) continuam sendo os
MESMOS usados para desafios — só adicionamos a aba "Desafio" no editor
com a missão e o botão de validar.
"""
import re

CATEGORIES = {
    "js-erro": "HTML/CSS/JS com erro",
    "botao-quebrado": "Botão quebrado",
    "layout-quebrado": "Layout quebrado",
    "formulario-quebrado": "Formulário com erro",
    "links-quebrados": "Links quebrados",
    "responsividade": "Problema de responsividade",
    "pagina-lenta": "Página lenta",
    "bot-comando-quebrado": "Bot: comando quebrado",
    "bot-erro-logica": "Bot: erro de lógica",
    "bot-resposta-incorreta": "Bot: resposta incorreta",
    "bot-config-quebrada": "Bot: configuração quebrada",
    "bot-falha-api": "Bot: falha de API",
    "bot-sem-tratamento-erro": "Bot: tratamento de erro ausente",
}


# ------------------------------------------------------------------ helpers
def _has_id(html, element_id):
    return re.search(rf'id=["\']{re.escape(element_id)}["\']', html) is not None


def _tag_with_id(html, element_id):
    """Devolve a tag inteira (ex.: '<a ... id="x" ...>') que tem esse id,
    não importando a ordem dos atributos — pra ler o href/onclick real
    mesmo que o usuário tenha reordenado atributos ao corrigir."""
    m = re.search(rf'<[a-zA-Z]+[^>]*\bid=["\']{re.escape(element_id)}["\'][^>]*>', html)
    return m.group(0) if m else ""


def _attr(tag, name):
    m = re.search(rf'{name}=["\']([^"\']*)["\']', tag)
    return m.group(1) if m else None


def _css_rule(html, selector):
    """Extrai o conteúdo { ... } da primeira regra CSS com esse seletor."""
    m = re.search(re.escape(selector) + r"\s*{([^}]*)}", html)
    return m.group(1) if m else ""


def _no_js_syntax_issues(html):
    """Reaproveita a MESMA checagem de balanceamento de chaves/parênteses
    do debugger_service.py já existente — não reimplementa nada."""
    from services.debugger_service import analyze_site
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "index.html"
        p.write_text(html, encoding="utf-8")
        issues = analyze_site(Path(tmp))
    return not any(i["tipo"] == "javascript" for i in issues), issues


def _check(label, ok, detail=""):
    return {"label": label, "ok": bool(ok), "detail": detail}


def _result(checks):
    return {"passed": all(c["ok"] for c in checks), "checks": checks}


# ============================================================== 1) JS ERRO
HTML_JS_ERRO = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Contador de Cliques</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;display:flex;
  flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#111a2e;padding:32px 40px;border-radius:14px;text-align:center;
  box-shadow:0 0 24px rgba(0,229,255,.15)}
#contador{font-size:48px;font-weight:bold;color:#00e5ff;margin:14px 0}
button{background:#00e5ff;color:#04121f;border:none;padding:10px 22px;border-radius:8px;
  font-size:16px;cursor:pointer}
</style>
</head>
<body>
<div class="card">
  <h1>Contador de Cliques</h1>
  <div id="contador">0</div>
  <button id="btn-incrementar" onclick="incrementar()">+1</button>
</div>
<script>
let total = 0;
function incrementar() {
  total = total + 1;
  document.getElementById("contador").textContent = total;
  // BUG: falta fechar esta função (chave de fechamento ausente),
  // o que quebra TODO o script da página — nem o botão funciona.
</script>
</body>
</html>
"""


def _validate_js_erro(html):
    ok_js, issues = _no_js_syntax_issues(html)
    checks = [_check("O JavaScript da página não tem símbolos desbalanceados", ok_js,
                     "" if ok_js else "Ainda há chave/parêntese/colchete sem par no <script>.")]
    has_fn = re.search(r"function\s+incrementar\s*\([^)]*\)\s*{", html) is not None
    checks.append(_check("A função incrementar() ainda existe", has_fn))
    has_incr = re.search(r"total\s*(\+=\s*1|=\s*total\s*\+\s*1|\+\+)", html) is not None
    checks.append(_check("A lógica de incrementar o total continua presente", has_incr))
    btn = _tag_with_id(html, "btn-incrementar")
    calls_fn = bool(btn) and "incrementar()" in (btn or "") or "incrementar()" in html
    checks.append(_check("O botão ainda chama incrementar()", calls_fn))
    return _result(checks)


# ============================================================ 2) BOTÃO QUEBRADO
HTML_BOTAO_QUEBRADO = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Loja Rápida</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;margin:0;gap:14px}
.card{background:#111a2e;padding:30px 36px;border-radius:14px;text-align:center}
button{background:#00e5ff;color:#04121f;border:none;padding:12px 26px;border-radius:8px;
  font-size:16px;cursor:pointer}
#status{min-height:24px;color:#7CFFB2}
</style>
</head>
<body>
<div class="card">
  <h1>Tênis Runner X</h1>
  <p>R$ 299,90</p>
  <button id="botao-comprar">Comprar agora</button>
  <p id="status"></p>
</div>
<script>
// BUG: o botão de verdade tem id="botao-comprar", mas este script está
// procurando por "btn-comprar" — o clique nunca é capturado.
document.getElementById("btn-comprar").addEventListener("click", function () {
  document.getElementById("status").textContent = "✅ Adicionado ao carrinho!";
});
</script>
</body>
</html>
"""


def _get_element_ids(html):
    return set(re.findall(r'id=["\']([\w-]+)["\']', html))


def _get_element_by_id_targets(html):
    return re.findall(r'getElementById\(\s*["\']([\w-]+)["\']\s*\)', html)


def _validate_botao_quebrado(html):
    ids = _get_element_ids(html)
    targets = _get_element_by_id_targets(html)
    missing = [t for t in targets if t not in ids]
    checks = [_check("Todo getElementById() do script aponta para um id que existe no HTML",
                     len(missing) == 0, ("id(s) inexistente(s): " + ", ".join(missing)) if missing else "")]
    has_listener = bool(re.search(r"addEventListener\(\s*[\"']click[\"']", html))
    checks.append(_check("O botão ainda tem um listener de clique registrado", has_listener))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ============================================================ 3) LAYOUT QUEBRADO
HTML_LAYOUT_QUEBRADO = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Portfólio</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;margin:0;padding:40px}
h1{text-align:center}
.cards{
  /* BUG: erro de digitação em "display" — o navegador ignora a regra
  inteira e as cards ficam empilhadas verticalmente em vez de em linha. */
  dispaly: flex;
  gap:18px;
  justify-content:center;
  flex-wrap:wrap;
}
.card{background:#111a2e;border-radius:12px;padding:20px;width:200px;text-align:center}
</style>
</head>
<body>
<h1>Meus Projetos</h1>
<div class="cards">
  <div class="card">Projeto A</div>
  <div class="card">Projeto B</div>
  <div class="card">Projeto C</div>
</div>
</body>
</html>
"""


def _validate_layout_quebrado(html):
    has_typo = "dispaly" in html.lower()
    checks = [_check("O typo 'dispaly' foi corrigido", not has_typo)]
    rule = _css_rule(html, ".cards")
    has_flex_or_grid = bool(re.search(r"display\s*:\s*(flex|grid)", rule, re.IGNORECASE))
    checks.append(_check(".cards usa display: flex (ou grid) de verdade", has_flex_or_grid,
                         "" if has_flex_or_grid else "A regra .cards não define display:flex/grid."))
    return _result(checks)


# ========================================================== 4) FORMULÁRIO QUEBRADO
HTML_FORMULARIO_QUEBRADO = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Fale Conosco</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;
  display:flex;flex-direction:column;align-items:center;padding:40px;margin:0}
form{background:#111a2e;padding:26px 32px;border-radius:14px;display:flex;
  flex-direction:column;gap:12px;width:280px}
input,textarea{padding:8px;border-radius:6px;border:1px solid #274;background:#0b1220;color:#e6f1ff}
button{background:#00e5ff;color:#04121f;border:none;padding:10px;border-radius:8px;cursor:pointer}
#form-sucesso{color:#7CFFB2;display:none}
</style>
</head>
<body>
<h1>Fale Conosco</h1>
<form id="contato">
  <!-- BUG: nenhum campo tem o atributo "name" — o script que lê
  event.target.nome / .email / .mensagem sempre encontra "undefined". -->
  <input id="nome" placeholder="Seu nome" required>
  <input id="email" type="email" placeholder="Seu e-mail" required>
  <textarea id="mensagem" placeholder="Sua mensagem" required></textarea>
  <button type="submit">Enviar</button>
  <p id="form-sucesso">✅ Mensagem enviada!</p>
</form>
<script>
document.getElementById("contato").addEventListener("submit", function (event) {
  event.preventDefault();
  const nome = event.target.nome && event.target.nome.value;
  const email = event.target.email && event.target.email.value;
  const mensagem = event.target.mensagem && event.target.mensagem.value;
  if (nome && email && mensagem) {
    document.getElementById("form-sucesso").style.display = "block";
  }
});
</script>
</body>
</html>
"""


def _validate_formulario_quebrado(html):
    form_m = re.search(r"<form[^>]*id=[\"']contato[\"'][^>]*>([\s\S]*?)</form>", html)
    form_block = form_m.group(0) if form_m else ""
    checks = []
    for expected in ("nome", "email", "mensagem"):
        ok = bool(re.search(rf'name=["\']{expected}["\']', form_block))
        checks.append(_check(f'O campo "{expected}" tem name="{expected}"', ok))
    checks.append(_check("O elemento de sucesso (#form-sucesso) ainda existe", _has_id(html, "form-sucesso")))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ============================================================= 5) LINKS QUEBRADOS
HTML_LINKS_QUEBRADOS = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Site Institucional</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;margin:0}
nav{display:flex;gap:20px;padding:18px 30px;background:#111a2e}
nav a{color:#00e5ff;text-decoration:none}
section{padding:60px 30px;min-height:200px;border-bottom:1px solid #223}
footer{padding:24px 30px;color:#9fb}
</style>
</head>
<body>
<nav>
  <!-- BUG 1: href="#" não leva a lugar nenhum -->
  <a id="nav-sobre" href="#">Sobre</a>
  <!-- BUG 2: aponta para #secao-servicos, mas o id real da seção é "servicos" -->
  <a id="nav-servicos" href="#secao-servicos">Serviços</a>
  <!-- BUG 3: falta o esquema (https://) — vira link relativo quebrado -->
  <a id="nav-site-oficial" href="siteoficial.com.br">Site oficial</a>
</nav>
<section id="sobre"><h2>Sobre nós</h2><p>Texto institucional...</p></section>
<section id="servicos"><h2>Nossos serviços</h2><p>Lista de serviços...</p></section>
<footer>© 2026 Empresa</footer>
</body>
</html>
"""


def _validate_links_quebrados(html):
    checks = []
    sobre = _tag_with_id(html, "nav-sobre")
    href_sobre = _attr(sobre, "href") or ""
    ok_sobre = href_sobre not in ("", "#")
    checks.append(_check('O link "Sobre" tem um destino real (não "#"/vazio)', ok_sobre, f"href atual: {href_sobre!r}"))

    servicos = _tag_with_id(html, "nav-servicos")
    href_servicos = _attr(servicos, "href") or ""
    target_id = href_servicos[1:] if href_servicos.startswith("#") else None
    ok_servicos = bool(target_id) and _has_id(html, target_id)
    checks.append(_check('O link "Serviços" aponta para um id que existe na página',
                         ok_servicos, f"href atual: {href_servicos!r}"))

    oficial = _tag_with_id(html, "nav-site-oficial")
    href_oficial = _attr(oficial, "href") or ""
    ok_oficial = href_oficial.startswith(("http://", "https://"))
    checks.append(_check('O link "Site oficial" é uma URL completa (http/https)',
                         ok_oficial, f"href atual: {href_oficial!r}"))
    return _result(checks)


# ========================================================= 6) RESPONSIVIDADE
HTML_RESPONSIVIDADE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<!-- BUG: falta a meta viewport — em celular, o navegador renderiza a
página como se fosse desktop e depois espreme tudo, quebrando o layout. -->
<title>Cardápio Digital</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;margin:0}
.container{
  /* BUG: largura fixa grande, sem max-width relativo nem media query —
  em telas pequenas isso força rolagem horizontal e corta o conteúdo. */
  width:1200px;
  margin:0 auto;
  padding:30px;
}
.item{background:#111a2e;padding:16px;border-radius:10px;margin-bottom:12px}
</style>
</head>
<body>
<div class="container">
  <h1>Cardápio</h1>
  <div class="item">Pizza Margherita — R$ 42,90</div>
  <div class="item">Lasanha à Bolonhesa — R$ 38,50</div>
  <div class="item">Suco Natural — R$ 9,90</div>
</div>
</body>
</html>
"""


def _validate_responsividade(html):
    viewport_m = re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    has_viewport = bool(viewport_m) and "width=device-width" in (viewport_m.group(1) or "")
    checks = [_check("Existe <meta name=\"viewport\"> com width=device-width", has_viewport)]
    rule = _css_rule(html, ".container")
    has_flex_width = bool(re.search(r"max-width", rule)) or bool(re.search(r"@media[^{]*{[^}]*\.container", html, re.DOTALL))
    checks.append(_check(".container tem max-width (ou uma @media cuidando dela) em vez de largura fixa rígida",
                         has_flex_width))
    return _result(checks)


# =============================================================== 7) PÁGINA LENTA
HTML_PAGINA_LENTA = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Blog Rápido</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;margin:0}
</style>
</head>
<body>
<h1>Bem-vindo ao Blog</h1>
<p>Se a página demorou pra aparecer, o motivo está no &lt;script&gt; abaixo.</p>
<script>
// BUG: este laço síncrono roda ANTES da página terminar de renderizar
// e trava a aba inteira por alguns segundos — um erro de performance
// real (trabalho pesado no thread principal, sem setTimeout/async).
let soma = 0;
for (let i = 0; i < 900000000; i++) {
  soma += i;
}
console.log(soma);
</script>
</body>
</html>
"""


def _validate_pagina_lenta(html):
    checks = []
    big_loop = re.search(r"for\s*\([^;]*;[^;]*<\s*([0-9][0-9_]{5,})", html)
    is_heavy = False
    if big_loop:
        try:
            bound = int(big_loop.group(1).replace("_", ""))
            is_heavy = bound >= 5_000_000
        except ValueError:
            is_heavy = True
    still_blocking = False
    if is_heavy:
        start = big_loop.start()
        window = html[max(0, start - 250):start]
        wrapped = bool(re.search(r"setTimeout\s*\(|requestIdleCallback\s*\(|addEventListener\s*\(", window))
        still_blocking = not wrapped
    checks.append(_check("Não há mais um laço pesado travando o carregamento da página",
                         not still_blocking,
                         "" if not still_blocking else "Ainda existe um for com muitas iterações rodando de forma síncrona."))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ================================================================
# DESAFIOS DE BOT — mesmo padrão dos desafios de site acima (html +
# validate() estático via regex, reaproveitando _check/_result/
# _no_js_syntax_issues), só que a "página quebrada" é um mini
# chatbot embutido em vez de um site comum. Cobre os 6 tipos de
# defeito pedidos: comando quebrado, erro de lógica, resposta
# incorreta, configuração quebrada, falha de API (assíncrona) e
# tratamento de erro ausente.
# ================================================================
BOT_CSS = """
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e6f1ff;margin:0;
  display:flex;flex-direction:column;align-items:center;padding:30px;gap:14px}
.bot-card{background:#111a2e;border-radius:14px;padding:20px;width:340px;
  box-shadow:0 0 24px rgba(0,229,255,.12)}
.bot-log{height:220px;overflow-y:auto;background:#0b1220;border-radius:8px;padding:10px;
  margin-bottom:10px;display:flex;flex-direction:column;gap:6px;font-size:14px}
.bot-log .msg{padding:6px 10px;border-radius:8px;max-width:85%}
.bot-log .user{align-self:flex-end;background:#1c3a52}
.bot-log .bot{align-self:flex-start;background:#173323;color:#bdf5cf}
.bot-row{display:flex;gap:8px}
.bot-row input{flex:1;padding:8px;border-radius:6px;border:1px solid #274;background:#0b1220;color:#e6f1ff}
.bot-row button{background:#00e5ff;color:#04121f;border:none;padding:8px 16px;border-radius:8px;cursor:pointer}
.bot-hint{color:#9fb;font-size:12.5px}
"""


def _bot_page(title, body_script, extra_html=""):
    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>{BOT_CSS}</style>
</head>
<body>
<div class="bot-card">
  <h1 style="font-size:18px;margin-top:0">{title}</h1>
  {extra_html}
  <div class="bot-log" id="bot-log"></div>
  <div class="bot-row">
    <input id="bot-input" placeholder="Digite um comando...">
    <button id="bot-enviar">Enviar</button>
  </div>
</div>
<script>
function mostrarMensagem(texto, autor) {{
  const log = document.getElementById("bot-log");
  const div = document.createElement("div");
  div.className = "msg " + (autor === "user" ? "user" : "bot");
  div.textContent = texto;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}}

{body_script}

document.getElementById("bot-enviar").addEventListener("click", function () {{
  const input = document.getElementById("bot-input");
  const texto = input.value.trim();
  if (!texto) return;
  mostrarMensagem(texto, "user");
  input.value = "";
  responder(texto);
}});
document.getElementById("bot-input").addEventListener("keydown", function (e) {{
  if (e.key === "Enter") document.getElementById("bot-enviar").click();
}});
</script>
</body>
</html>
"""


# ---------------------------------------------------- 8) BOT: COMANDO QUEBRADO
HTML_BOT_COMANDO_QUEBRADO = _bot_page(
    "TF Mini Bot — Central de Ajuda",
    """
function responder(mensagem) {
  const partes = mensagem.trim().split(" ");
  const comando = partes[0];
  // BUG: o usuário digita "/ajuda" (com barra, como todos os outros
  // comandos deste bot), mas esta comparação espera "ajuda" sem barra
  // — o comando nunca é reconhecido e cai sempre no "não entendi".
  if (comando === "ajuda") {
    mostrarMensagem("Comandos disponíveis: /ajuda, /hora, /eco <texto>", "bot");
  } else if (comando === "/hora") {
    mostrarMensagem("Agora são " + new Date().toLocaleTimeString(), "bot");
  } else if (comando === "/eco") {
    mostrarMensagem(partes.slice(1).join(" ") || "(nada pra ecoar)", "bot");
  } else {
    mostrarMensagem("Não entendi esse comando. Digite /ajuda.", "bot");
  }
}
""",
    '<p class="bot-hint">Comandos: /ajuda · /hora · /eco &lt;texto&gt;</p>',
)


def _validate_bot_comando_quebrado(html):
    checks = []
    has_slash_check = bool(re.search(r'comando\s*===\s*["\']\/ajuda["\']', html))
    checks.append(_check('A checagem do comando de ajuda compara com "/ajuda" (com barra, igual aos outros comandos)',
                         has_slash_check))
    still_has_others = "/hora" in html and "/eco" in html
    checks.append(_check("Os comandos /hora e /eco continuam funcionando", still_has_others))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ------------------------------------------------------- 9) BOT: ERRO DE LÓGICA
HTML_BOT_ERRO_LOGICA = _bot_page(
    "TF Mini Bot — Par ou Ímpar",
    """
function responder(mensagem) {
  const partes = mensagem.trim().split(" ");
  if (partes[0] === "/par") {
    const numero = Number(partes[1]);
    if (Number.isNaN(numero)) {
      mostrarMensagem("Use assim: /par 4", "bot");
      return;
    }
    // BUG: a condição e os textos estão invertidos — um número
    // divisível por 2 está sendo anunciado como "ímpar", e vice-versa.
    const resposta = (numero % 2 === 0) ? "ímpar" : "par";
    mostrarMensagem(numero + " é " + resposta + ".", "bot");
  } else {
    mostrarMensagem("Digite /par <numero> para eu dizer se é par ou ímpar.", "bot");
  }
}
""",
    '<p class="bot-hint">Comando: /par &lt;numero&gt;</p>',
)


def _validate_bot_erro_logica(html):
    checks = []
    m = re.search(r'\(numero\s*%\s*2\s*===\s*0\)\s*\?\s*"([^"]+)"\s*:\s*"([^"]+)"', html)
    par_branch = m.group(1).strip().lower() if m else ""
    impar_branch = m.group(2).strip().lower() if m else ""
    ok = bool(m) and "par" == par_branch and "ímpar" in impar_branch
    checks.append(_check('Quando o número é divisível por 2, a resposta é "par" (e "ímpar" no outro caso)', ok,
                         "" if ok else "O ternário ainda associa os textos errados a cada condição."))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# --------------------------------------------------- 10) BOT: RESPOSTA INCORRETA
HTML_BOT_RESPOSTA_INCORRETA = _bot_page(
    "TF Mini Bot — Recepção",
    """
// BUG: as respostas de "oi" e "clima" estão trocadas entre si — quem
// cumprimenta o bot recebe uma previsão do tempo, e quem pergunta do
// clima recebe uma saudação.
const RESPOSTAS = {
  "oi": "A previsão para hoje é de sol, 26°C.",
  "tchau": "Até logo! 👋",
  "clima": "Olá! Em que posso ajudar?"
};

function responder(mensagem) {
  const chave = mensagem.trim().toLowerCase();
  const resposta = RESPOSTAS[chave];
  mostrarMensagem(resposta || "Não tenho uma resposta pronta pra isso ainda.", "bot");
}
""",
    '<p class="bot-hint">Tente: oi · clima · tchau</p>',
)


def _validate_bot_resposta_incorreta(html):
    checks = []
    oi_m = re.search(r'"oi"\s*:\s*"([^"]*)"', html)
    clima_m = re.search(r'"clima"\s*:\s*"([^"]*)"', html)
    oi_txt = (oi_m.group(1) if oi_m else "").lower()
    clima_txt = (clima_m.group(1) if clima_m else "").lower()
    oi_is_greeting = bool(re.search(r"ol[aá]|ajudar|oi\b", oi_txt))
    clima_is_weather = bool(re.search(r"sol|chuva|previs|°c|grau|clima", clima_txt))
    checks.append(_check('"oi" tem uma resposta de saudação (não fala sobre o tempo)', oi_is_greeting,
                         f"resposta atual de 'oi': {oi_txt!r}"))
    checks.append(_check('"clima" tem uma resposta sobre o tempo (não uma saudação)', clima_is_weather,
                         f"resposta atual de 'clima': {clima_txt!r}"))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ------------------------------------------------- 11) BOT: CONFIGURAÇÃO QUEBRADA
HTML_BOT_CONFIG_QUEBRADA = _bot_page(
    "TF Mini Bot — Boas-vindas",
    """
const CONFIG = {
  nomeBot: "Íris",
  comandoAjuda: "/ajuda",
  maxHistorico: 50
};

function responder(mensagem) {
  if (mensagem.trim() === "/oi") {
    // BUG: lê CONFIG.nome, mas a chave de verdade no objeto é
    // "nomeBot" — o resultado sai como "Olá, eu sou o undefined".
    mostrarMensagem("Olá, eu sou o " + CONFIG.nome + "! Digite " + CONFIG.comandoAjuda + " para ver os comandos.", "bot");
  } else if (mensagem.trim() === CONFIG.comandoAjuda) {
    mostrarMensagem("Comandos: /oi, " + CONFIG.comandoAjuda, "bot");
  } else {
    mostrarMensagem("Não entendi. Digite " + CONFIG.comandoAjuda + ".", "bot");
  }
}
""",
    '<p class="bot-hint">Comandos: /oi · /ajuda</p>',
)


def _validate_bot_config_quebrada(html):
    checks = []
    m = re.search(r'"Olá, eu sou o "\s*\+\s*CONFIG\.(\w+)', html)
    used_key = m.group(1) if m else ""
    checks.append(_check("A mensagem de boas-vindas lê CONFIG.nomeBot (não uma chave que não existe no objeto)",
                         used_key == "nomeBot",
                         f"chave usada atualmente: CONFIG.{used_key or '?'}"))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# -------------------------------------------------------- 12) BOT: FALHA DE API
HTML_BOT_FALHA_API = _bot_page(
    "TF Mini Bot — Clima (API simulada)",
    """
// API simulada (assíncrona de propósito, como uma chamada de rede real).
function buscarClimaNaAPI(cidade) {
  return new Promise(function (resolve) {
    setTimeout(function () {
      resolve(Math.round(15 + Math.random() * 15) + "°C em " + cidade);
    }, 400);
  });
}

function responder(mensagem) {
  const partes = mensagem.trim().split(" ");
  if (partes[0] === "/clima") {
    const cidade = partes.slice(1).join(" ") || "sua cidade";
    // BUG: buscarClimaNaAPI() devolve uma Promise, não o texto do clima
    // — falta "await" (ou ".then(...)") antes de usar o resultado, então
    // o bot mostra "[object Promise]" em vez do clima de verdade.
    const resultado = buscarClimaNaAPI(cidade);
    mostrarMensagem(resultado, "bot");
  } else {
    mostrarMensagem("Digite /clima <cidade>.", "bot");
  }
}
""",
    '<p class="bot-hint">Comando: /clima &lt;cidade&gt;</p>',
)


def _validate_bot_falha_api(html):
    checks = []
    handles_promise = bool(re.search(r"await\s+buscarClimaNaAPI\s*\(", html)) or \
        bool(re.search(r"buscarClimaNaAPI\s*\([^)]*\)\s*\.then\s*\(", html))
    checks.append(_check("O resultado de buscarClimaNaAPI() é aguardado (await ou .then) antes de ser exibido",
                         handles_promise,
                         "" if handles_promise else "O código ainda passa a Promise direto pra mostrarMensagem()."))
    still_direct = bool(re.search(r"mostrarMensagem\s*\(\s*resultado\s*,", html)) and not handles_promise
    checks.append(_check("mostrarMensagem() não recebe mais a Promise sem resolver", not still_direct))
    if handles_promise:
        uses_async = bool(re.search(r"async\s+function\s+responder", html)) or "await" not in html
        checks.append(_check("Se usou 'await', a função responder() foi marcada como 'async function responder'",
                             (("await" not in html) or uses_async)))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ------------------------------------------------ 13) BOT: TRATAMENTO DE ERRO AUSENTE
HTML_BOT_SEM_TRATAMENTO_ERRO = _bot_page(
    "TF Mini Bot — Calculadora",
    """
function responder(mensagem) {
  const partes = mensagem.trim().split(" ");
  if (partes[0] === "/dividir") {
    // BUG: nenhum tratamento para divisor zero nem para entrada que não
    // é número — o bot responde "Infinity" ou "NaN" em vez de avisar o
    // usuário do problema, e um valor não-numérico pode quebrar o resto
    // da conversa silenciosamente.
    const a = Number(partes[1]);
    const b = Number(partes[2]);
    const resultado = a / b;
    mostrarMensagem(a + " ÷ " + b + " = " + resultado, "bot");
  } else {
    mostrarMensagem("Digite /dividir <numero1> <numero2>.", "bot");
  }
}
""",
    '<p class="bot-hint">Comando: /dividir &lt;numero1&gt; &lt;numero2&gt; — tente /dividir 10 0</p>',
)


def _validate_bot_sem_tratamento_erro(html):
    checks = []
    has_zero_guard = bool(re.search(r"b\s*(===|==|<=)\s*0", html)) or bool(re.search(r"!\s*b\b", html))
    checks.append(_check("Existe uma checagem explícita para divisão por zero antes de dividir", has_zero_guard))
    has_nan_guard = bool(re.search(r"isNaN\s*\(", html)) or bool(re.search(r"Number\.isNaN\s*\(", html))
    checks.append(_check("Existe uma checagem para entrada que não é um número (isNaN)", has_nan_guard))
    ok_js, _ = _no_js_syntax_issues(html)
    checks.append(_check("O JavaScript continua sem erro de sintaxe", ok_js))
    return _result(checks)


# ------------------------------------------------------------------ CATÁLOGO
CATALOG = {
    "js-erro": {
        "id": "js-erro", "category": "js-erro", "title": "O contador que não conta",
        "difficulty": "iniciante",
        "summary": "Um botão de contador que não incrementa nada quando clicado.",
        "mission": "Abra a aba Depurar e veja o que ela aponta no JavaScript. Depois abra o "
                   "Código, encontre o bloco <script> e conserte o problema — o botão +1 "
                   "precisa voltar a somar no contador.",
        "hints": [
            "A aba 'Depurar' já existente no Editor detecta símbolos desbalanceados em JS — use-a primeiro.",
            "Toda função em JavaScript precisa de uma chave de abertura { e uma de fechamento }.",
            "Conte as chaves do bloco <script> uma a uma, de cima para baixo.",
        ],
        "html": HTML_JS_ERRO, "validate": _validate_js_erro,
    },
    "botao-quebrado": {
        "id": "botao-quebrado", "category": "botao-quebrado", "title": "O botão que não faz nada",
        "difficulty": "iniciante",
        "summary": "O botão 'Comprar agora' não reage a nenhum clique.",
        "mission": "Clique no botão na Pré-visualização — nada acontece. Investigue o "
                   "JavaScript: ele está procurando um elemento pelo id certo?",
        "hints": [
            "document.getElementById('X') só funciona se existir um elemento com id=\"X\" no HTML.",
            "Compare o id usado no script com o id real do botão no HTML.",
            "Você pode corrigir tanto o HTML quanto o JavaScript — o importante é os dois baterem.",
        ],
        "html": HTML_BOTAO_QUEBRADO, "validate": _validate_botao_quebrado,
    },
    "layout-quebrado": {
        "id": "layout-quebrado", "category": "layout-quebrado", "title": "O layout que virou bagunça",
        "difficulty": "iniciante",
        "summary": "As cards de projeto deveriam ficar lado a lado, mas empilham na vertical.",
        "mission": "Olhe o CSS da classe .cards na Pré-visualização e no Código. Alguma "
                   "propriedade está escrita errada?",
        "hints": [
            "CSS não avisa quando o nome de uma propriedade está com erro de digitação — ele "
            "simplesmente ignora a linha inteira.",
            "'display' é o nome certo da propriedade que controla flex/grid.",
        ],
        "html": HTML_LAYOUT_QUEBRADO, "validate": _validate_layout_quebrado,
    },
    "formulario-quebrado": {
        "id": "formulario-quebrado", "category": "formulario-quebrado",
        "title": "Formulário que não confirma o envio", "difficulty": "intermediário",
        "summary": "Preencher e enviar o formulário nunca mostra a mensagem de sucesso.",
        "mission": "O script lê event.target.nome, .email e .mensagem. Veja no HTML se os "
                   "campos realmente têm esses atributos.",
        "hints": [
            "event.target.nome só existe se o campo tiver name=\"nome\" no HTML — id não é a "
            "mesma coisa que name.",
            "Repita o mesmo raciocínio para email e mensagem.",
        ],
        "html": HTML_FORMULARIO_QUEBRADO, "validate": _validate_formulario_quebrado,
    },
    "links-quebrados": {
        "id": "links-quebrados", "category": "links-quebrados", "title": "Links que não levam a lugar nenhum",
        "difficulty": "iniciante",
        "summary": "Três links do menu estão quebrados de formas diferentes.",
        "mission": "Teste cada link do menu na Pré-visualização. Um não tem destino, outro "
                   "aponta para uma âncora que não existe, e um terceiro está sem o "
                   "https:// na frente.",
        "hints": [
            "Links internos (href=\"#algumId\") só funcionam se existir um elemento com esse id na página.",
            "Um link para um site externo precisa começar com http:// ou https://.",
        ],
        "html": HTML_LINKS_QUEBRADOS, "validate": _validate_links_quebrados,
    },
    "responsividade": {
        "id": "responsividade", "category": "responsividade", "title": "Quebra no celular",
        "difficulty": "intermediário",
        "summary": "A página fica cortada e com rolagem horizontal em telas pequenas.",
        "mission": "Reduza a largura da janela de Pré-visualização (ou olhe no celular) e "
                   "veja o problema. Falta algo essencial no <head> e o CSS do .container "
                   "está rígido demais.",
        "hints": [
            "Toda página responsiva precisa de uma tag <meta name=\"viewport\"> no <head>.",
            "Uma largura fixa em pixels (width: 1200px) não se adapta a telas menores — "
            "considere max-width ou uma @media query.",
        ],
        "html": HTML_RESPONSIVIDADE, "validate": _validate_responsividade,
    },
    "pagina-lenta": {
        "id": "pagina-lenta", "category": "pagina-lenta", "title": "Página que demora pra carregar",
        "difficulty": "avançado",
        "summary": "A página trava por alguns segundos antes de responder a qualquer clique.",
        "mission": "Abra a Pré-visualização e sinta a demora. O problema está em um "
                   "<script> fazendo um trabalho pesado de forma síncrona logo no carregamento.",
        "hints": [
            "Um laço 'for' com centenas de milhões de iterações rodando direto trava a aba inteira.",
            "Trabalho pesado deveria rodar depois (setTimeout) ou ser bem menor — ou simplesmente removido se não servir pra nada.",
        ],
        "html": HTML_PAGINA_LENTA, "validate": _validate_pagina_lenta,
    },
    "bot-comando-quebrado": {
        "id": "bot-comando-quebrado", "category": "bot-comando-quebrado",
        "title": "O bot que ignora o comando /ajuda", "difficulty": "iniciante",
        "summary": "O comando /ajuda nunca funciona, mas /hora e /eco sim.",
        "mission": "Digite /ajuda na Pré-visualização e veja que o bot diz \"não entendi\". "
                   "Compare como cada comando é comparado no código — todos usam o mesmo padrão?",
        "hints": [
            "Todo comando deste bot é digitado com uma barra na frente, tipo /hora.",
            "Veja com que texto exato o código compara a variável 'comando' no bloco do /ajuda.",
            "if (comando === \"ajuda\") não é a mesma coisa que if (comando === \"/ajuda\").",
        ],
        "html": HTML_BOT_COMANDO_QUEBRADO, "validate": _validate_bot_comando_quebrado,
    },
    "bot-erro-logica": {
        "id": "bot-erro-logica", "category": "bot-erro-logica",
        "title": "O bot que confunde par com ímpar", "difficulty": "iniciante",
        "summary": "O comando /par diz que números pares são ímpares (e vice-versa).",
        "mission": "Teste /par 4 e /par 7 na Pré-visualização. As respostas estão trocadas — "
                   "ache o ternário que decide o texto e corrija a lógica.",
        "hints": [
            "numero % 2 === 0 é verdadeiro quando o número é PAR.",
            "Um ternário (condição) ? A : B devolve A se a condição for verdadeira, e B se for falsa.",
            "Os dois textos \"par\" e \"ímpar\" estão no lugar errado um do outro.",
        ],
        "html": HTML_BOT_ERRO_LOGICA, "validate": _validate_bot_erro_logica,
    },
    "bot-resposta-incorreta": {
        "id": "bot-resposta-incorreta", "category": "bot-resposta-incorreta",
        "title": "O bot que troca as respostas", "difficulty": "iniciante",
        "summary": "Cumprimentar o bot ('oi') dá previsão do tempo, e perguntar do clima dá uma saudação.",
        "mission": "Digite 'oi' e depois 'clima' na Pré-visualização. As respostas fazem sentido "
                   "com a pergunta? Veja o objeto RESPOSTAS no código.",
        "hints": [
            "RESPOSTAS é um objeto: cada chave (\"oi\", \"clima\"...) tem um texto de resposta associado.",
            "O texto associado a \"oi\" deveria ser uma saudação, não uma previsão do tempo.",
        ],
        "html": HTML_BOT_RESPOSTA_INCORRETA, "validate": _validate_bot_resposta_incorreta,
    },
    "bot-config-quebrada": {
        "id": "bot-config-quebrada", "category": "bot-config-quebrada",
        "title": "O bot que esqueceu o próprio nome", "difficulty": "intermediário",
        "summary": "Digitar /oi faz o bot se apresentar como \"undefined\".",
        "mission": "Veja o objeto CONFIG no topo do script e depois veja qual propriedade a "
                   "mensagem de boas-vindas está tentando ler. Os nomes batem?",
        "hints": [
            "CONFIG.nomeBot e CONFIG.nome não são a mesma propriedade.",
            "Ler uma propriedade que não existe em um objeto JavaScript devolve 'undefined', não erro.",
        ],
        "html": HTML_BOT_CONFIG_QUEBRADA, "validate": _validate_bot_config_quebrada,
    },
    "bot-falha-api": {
        "id": "bot-falha-api", "category": "bot-falha-api",
        "title": "O bot que mostra '[object Promise]'", "difficulty": "avançado",
        "summary": "O comando /clima mostra '[object Promise]' em vez do clima de verdade.",
        "mission": "buscarClimaNaAPI() simula uma chamada de rede (é assíncrona, devolve uma "
                   "Promise). O código em responder() está tratando esse resultado corretamente?",
        "hints": [
            "Uma função que devolve 'new Promise(...)' não devolve o valor final na hora — "
            "esse valor só existe depois, dentro de .then(valor => ...) ou com 'await'.",
            "Se usar 'await', lembre-se de marcar a função responder como 'async function responder(...)'.",
        ],
        "html": HTML_BOT_FALHA_API, "validate": _validate_bot_falha_api,
    },
    "bot-sem-tratamento-erro": {
        "id": "bot-sem-tratamento-erro", "category": "bot-sem-tratamento-erro",
        "title": "A calculadora que não sabe dizer 'não posso fazer isso'", "difficulty": "intermediário",
        "summary": "/dividir 10 0 responde 'Infinity', e um texto no lugar de número quebra a resposta.",
        "mission": "Teste /dividir 10 0 e /dividir dez cinco na Pré-visualização. Adicione as "
                   "checagens que faltam para o bot responder algo útil nesses dois casos.",
        "hints": [
            "Dividir por zero em JavaScript não dá erro — dá Infinity. Você precisa checar isso 'na mão'.",
            "Number(\"dez\") não é um número válido — isNaN(...) ajuda a detectar isso antes de calcular.",
        ],
        "html": HTML_BOT_SEM_TRATAMENTO_ERRO, "validate": _validate_bot_sem_tratamento_erro,
    },
}


def list_catalog():
    return [{k: v for k, v in c.items() if k not in ("html", "validate")} for c in CATALOG.values()]


def get(challenge_id):
    return CATALOG.get(challenge_id)


def validate(challenge_id, html):
    c = CATALOG.get(challenge_id)
    if not c:
        raise ValueError("Desafio não encontrado.")
    return c["validate"](html)


# ================================================================
# ENRIQUECIMENTO DOS DESAFIOS — objetivo / explicação do erro /
# solução esperada / XP.
#
# Feito como um passo separado (em vez de reescrever os 13 dicionários
# acima) de propósito: os dicionários originais continuam exatamente
# como estavam (difficulty, summary, mission, hints, html, validate),
# então nada que já dependia deles quebra. Isto só ACRESCENTA campos
# novos em cada entrada do CATALOG já existente.
# ================================================================
XP_BY_DIFFICULTY = {"iniciante": 100, "intermediário": 200, "avançado": 300}

DETAILS = {
    "js-erro": {
        "objective": "Fazer o botão \"+1\" voltar a incrementar o contador na tela.",
        "explanation": "Em JavaScript, toda função precisa ter uma chave de abertura { e uma "
                       "de fechamento } em par. A função incrementar() ficou sem a chave final "
                       "— isso não gera um erro visível na página, mas quebra o parser do "
                       "restante do <script>, então NENHUM código depois dela é executado, "
                       "incluindo o listener do clique.",
        "expected_solution": "Adicionar a chave de fechamento } que falta, logo após a linha que "
                             "atualiza o textContent do #contador, antes de </script>.",
    },
    "botao-quebrado": {
        "objective": "Fazer o botão \"Comprar agora\" mostrar a mensagem de confirmação ao ser clicado.",
        "explanation": "document.getElementById(\"btn-comprar\") procura um elemento com esse id "
                       "exato. O botão real no HTML tem id=\"botao-comprar\" — como os textos são "
                       "diferentes, getElementById devolve null, e chamar .addEventListener em "
                       "null lança um erro silencioso que impede o resto do script de rodar.",
        "expected_solution": "Trocar \"btn-comprar\" por \"botao-comprar\" no getElementById (ou "
                             "renomear o id do botão no HTML para \"btn-comprar\") — os dois lados "
                             "precisam usar o mesmo texto.",
    },
    "layout-quebrado": {
        "objective": "Fazer as três cards de projeto ficarem lado a lado em vez de empilhadas.",
        "explanation": "CSS ignora silenciosamente qualquer propriedade que não reconhece — não "
                       "lança erro nem avisa no console. \"dispaly\" (com erro de digitação) não "
                       "existe como propriedade CSS, então a regra inteira é descartada e o "
                       ".cards volta ao comportamento padrão (block), empilhando os itens.",
        "expected_solution": "Corrigir o nome da propriedade para \"display\" (mantendo o valor \"flex\").",
    },
    "formulario-quebrado": {
        "objective": "Fazer a mensagem de sucesso aparecer depois de preencher e enviar o formulário.",
        "explanation": "event.target.nome só existe se o campo do formulário tiver o atributo "
                       "name=\"nome\" — id e name são atributos diferentes e servem a propósitos "
                       "diferentes. Sem o name, event.target.nome/.email/.mensagem sempre valem "
                       "undefined, então o \"if\" nunca é verdadeiro.",
        "expected_solution": "Adicionar name=\"nome\", name=\"email\" e name=\"mensagem\" nos três "
                             "campos do formulário (mantendo os ids como estão).",
    },
    "links-quebrados": {
        "objective": "Fazer os três links do menu levarem a algum lugar de verdade.",
        "explanation": "Cada link falha por um motivo diferente: href=\"#\" não aponta a lugar "
                       "nenhum; href=\"#secao-servicos\" busca um id que não existe na página "
                       "(o id real é \"servicos\"); e \"siteoficial.com.br\" sem http(s):// é "
                       "interpretado como um caminho relativo do próprio site, não como um site externo.",
        "expected_solution": "Dar um destino real ao link \"Sobre\" (ex.: \"#sobre\"), corrigir o "
                             "href do link \"Serviços\" para \"#servicos\", e prefixar o link do "
                             "site oficial com \"https://\".",
    },
    "responsividade": {
        "objective": "Fazer a página se adaptar corretamente a uma tela de celular.",
        "explanation": "Sem <meta name=\"viewport\">, navegadores móveis renderizam a página numa "
                       "largura virtual grande (geralmente 980px) e depois encolhem tudo — texto "
                       "fica minúsculo. Além disso, width:1200px fixo no .container nunca encolhe, "
                       "forçando rolagem horizontal em qualquer tela menor que isso.",
        "expected_solution": "Adicionar <meta name=\"viewport\" content=\"width=device-width, "
                             "initial-scale=1\"> no <head>, e trocar width:1200px por max-width:1200px "
                             "(ou uma @media query) no .container.",
    },
    "pagina-lenta": {
        "objective": "Fazer a página carregar/responder sem travar por vários segundos.",
        "explanation": "JavaScript roda em uma única thread principal, a mesma que desenha a tela "
                       "e reage a cliques. Um laço síncrono com centenas de milhões de iterações "
                       "ocupa essa thread inteira até terminar — a aba fica \"congelada\" até o "
                       "laço acabar, mesmo que o resultado (a soma) não seja usado em lugar nenhum.",
        "expected_solution": "Remover o laço pesado (ele não afeta nada visível), ou, se o cálculo "
                             "fosse necessário de verdade, adiar/dividir o trabalho (setTimeout, "
                             "requestIdleCallback, um Web Worker) em vez de rodar tudo de uma vez.",
    },
    "bot-comando-quebrado": {
        "objective": "Fazer o comando /ajuda responder normalmente, igual aos outros comandos.",
        "explanation": "O bot sempre lê o comando inteiro digitado, incluindo a barra (\"/hora\", "
                       "\"/eco\"). Só a comparação do /ajuda foi escrita sem a barra (\"ajuda\"), "
                       "então `comando === \"ajuda\"` nunca é verdadeiro para o que o usuário "
                       "realmente digita (\"/ajuda\") — o fluxo sempre cai no \"não entendi\".",
        "expected_solution": "Trocar a comparação para comando === \"/ajuda\", com a barra, igual "
                             "aos outros comandos do mesmo bot.",
    },
    "bot-erro-logica": {
        "objective": "Fazer o comando /par classificar corretamente números pares e ímpares.",
        "explanation": "numero % 2 === 0 é verdadeiro exatamente quando o número é par (resto 0 "
                       "na divisão por 2). O ternário está associando o texto \"ímpar\" a essa "
                       "condição verdadeira e \"par\" à falsa — os dois resultados estão trocados "
                       "entre si.",
        "expected_solution": "Inverter os dois textos do ternário: (numero % 2 === 0) ? \"par\" : \"ímpar\".",
    },
    "bot-resposta-incorreta": {
        "objective": "Fazer \"oi\" responder com uma saudação e \"clima\" com uma previsão do tempo.",
        "explanation": "RESPOSTAS é um mapa de palavra-chave → texto de resposta. O valor "
                       "associado à chave \"oi\" é sobre o tempo, e o valor da chave \"clima\" é "
                       "uma saudação — os dois textos foram atribuídos à chave errada.",
        "expected_solution": "Trocar os dois valores de lugar: \"oi\" recebe o texto de saudação "
                             "e \"clima\" recebe o texto sobre o tempo.",
    },
    "bot-config-quebrada": {
        "objective": "Fazer o bot se apresentar com o próprio nome, em vez de \"undefined\".",
        "explanation": "Ler uma propriedade que não existe em um objeto JavaScript não gera erro "
                       "— simplesmente devolve undefined. O objeto CONFIG define a chave "
                       "\"nomeBot\", mas a mensagem de boas-vindas lê \"CONFIG.nome\" (sem \"Bot\"), "
                       "uma chave que nunca existiu.",
        "expected_solution": "Trocar CONFIG.nome por CONFIG.nomeBot na linha que monta a mensagem "
                             "de boas-vindas.",
    },
    "bot-falha-api": {
        "objective": "Fazer /clima mostrar o texto do clima, não \"[object Promise]\".",
        "explanation": "buscarClimaNaAPI() devolve uma Promise (representa um valor que vai "
                       "existir no futuro, típico de chamadas assíncronas/de rede). Usar esse "
                       "valor diretamente, sem esperar ele resolver, mostra o objeto Promise em "
                       "si — daí o texto literal \"[object Promise]\" na tela.",
        "expected_solution": "Usar 'await buscarClimaNaAPI(cidade)' (marcando responder como "
                             "'async function responder(...)') ou 'buscarClimaNaAPI(cidade).then(resultado => "
                             "mostrarMensagem(resultado, \"bot\"))'.",
    },
    "bot-sem-tratamento-erro": {
        "objective": "Fazer /dividir responder de forma útil quando o divisor é zero ou a entrada não é um número.",
        "explanation": "JavaScript não lança erro ao dividir por zero — o resultado é o valor "
                       "especial Infinity (ou -Infinity/NaN), que é tecnicamente um número válido "
                       "mas inútil pra mostrar ao usuário. Da mesma forma, Number(\"dez\") não "
                       "lança erro: vira NaN silenciosamente. Sem checagens explícitas, o bot "
                       "propaga esses valores sem avisar que algo deu errado.",
        "expected_solution": "Antes de dividir, checar isNaN(a) || isNaN(b) e responder pedindo "
                             "números válidos; checar b === 0 separadamente e responder que não é "
                             "possível dividir por zero — só then dividir se passar nas duas checagens.",
    },
}


for _cid, _c in CATALOG.items():
    _d = DETAILS.get(_cid, {})
    _c["objective"] = _d.get("objective", _c["mission"])
    _c["explanation"] = _d.get("explanation", "")
    _c["expected_solution"] = _d.get("expected_solution", "")
    _c["xp"] = XP_BY_DIFFICULTY.get(_c["difficulty"], 100)


# ---------------------------------------------------------------
# Extensão Cyber Lab: mantém o catálogo original intacto e adiciona
# laboratórios isolados/CTF como uma segunda fonte de desafios.
from services import cyber_challenges as _cyber_challenges

for _cid, _challenge in _cyber_challenges.CATALOG.items():
    CATALOG.setdefault(_cid, _challenge)
for _cid, _label in _cyber_challenges.CATEGORIES.items():
    CATEGORIES.setdefault(_cid, _label)


# Phase 3: novos laboratórios defensivos. Duplicatas são ignoradas para
# preservar IDs já existentes e evitar dois validadores para o mesmo desafio.
try:
    from services import phase3_challenges as _phase3_challenges
    for _challenge in _phase3_challenges.CHALLENGES:
        CATALOG.setdefault(_challenge["id"], _challenge)
    for _challenge in _phase3_challenges.CHALLENGES:
        CATEGORIES.setdefault(_challenge["category"], _challenge["category"])
except Exception:
    pass



def total_possible_xp():
    return sum(c["xp"] for c in CATALOG.values())


def xp_for(challenge_id):
    c = CATALOG.get(challenge_id)
    return c["xp"] if c else 0
