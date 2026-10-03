"""Desafios Cyber Lab isolados e verificáveis.

Os laboratórios são arquivos de texto/HTML: não executam payloads, não fazem
requisições externas e não usam sistemas de terceiros como alvo.
"""
import re

CATEGORIES = {
    "xss": "XSS em laboratório",
    "sqli": "SQL Injection em laboratório",
    "idor-bola": "IDOR/BOLA",
    "auth-fraca": "Autenticação",
    "sessao": "Sessões",
    "csrf": "CSRF",
    "cors": "CORS",
    "api-insegura": "APIs",
    "upload": "Upload inseguro",
    "traversal": "Path Traversal",
    "cmdi": "Command Injection",
    "secrets": "Secrets expostos",
    "headers": "Headers de segurança",
    "config": "Configuração insegura",
    "logica": "Lógica de negócio",
    "logs": "Análise de logs",
    "incidente": "Blue Team / Incidente",
    "malware": "Análise de malware fictício",
    "pcap": "Análise de PCAP",
    "reverse": "Engenharia reversa",
}

def _check(label, ok, detail=""):
    return {"label": label, "ok": bool(ok), "detail": detail}

def _validate(html, required=(), forbidden=()):
    checks = []
    low = html.lower()
    for label, pattern in required:
        checks.append(_check(label, bool(re.search(pattern, low, re.I)),
                             "Padrão esperado encontrado." if re.search(pattern, low, re.I)
                             else "Ainda não encontrei a correção esperada."))
    for label, pattern in forbidden:
        checks.append(_check(label, not re.search(pattern, low, re.I),
                             "Padrão inseguro ainda está presente." if re.search(pattern, low, re.I)
                             else "Padrão inseguro não encontrado."))
    return {"passed": all(c["ok"] for c in checks), "checks": checks}

def _challenge(cid, title, category, difficulty, xp, objective, description, html,
               required=(), forbidden=(), hints=(), explanation="", solution=""):
    return {
        "id": cid, "title": title, "category": category, "difficulty": difficulty,
        "xp": xp, "summary": description, "mission": objective, "objective": objective,
        "environment": "laboratório isolado — somente texto/código local; nenhuma ação de rede",
        "hints": list(hints), "html": html,
        "validate": lambda value, r=required, f=forbidden: _validate(value, r, f),
        "explanation": explanation, "expected_solution": solution,
        "status_model": "resolvido/não resolvido",
    }

CHALLENGES = [
_challenge("xss", "Eco inseguro", "xss", "iniciante", 100,
 "Faça a saída do usuário ser tratada como texto, sem interpretar HTML.",
 "O laboratório usa innerHTML com uma entrada que deveria ser apenas texto.",
 """<!doctype html><h1>Lab XSS</h1><pre id="out">resultado</pre><script>
 const userInput = "texto do laboratório";
 document.getElementById("out").innerHTML = userInput;
 </script>""",
 required=(("usar textContent", r"\.textcontent\s*="),),
 forbidden=(("remover innerHTML na saída", r"\.innerhtml\s*=\s*userinput"),),
 hints=("Procure a API que interpreta HTML.", "Para texto simples, use textContent."),
 explanation="innerHTML interpreta a string como marcação. Em um app real, conteúdo controlado pelo usuário pode virar XSS.",
 solution="Troque a atribuição para textContent (ou sanitize o HTML com uma biblioteca apropriada)."),

_challenge("sqli", "Consulta parametrizada", "sqli", "iniciante", 100,
 "Remova a concatenação de entrada na consulta e use parâmetros.",
 "O código monta uma consulta SQL juntando uma variável diretamente.",
 """<!doctype html><h1>SQLi Lab</h1><pre>
cursor.execute("SELECT id,name FROM users WHERE name = '" + user + "'")
# tarefa: tornar a consulta parametrizada
</pre>""",
 required=(("usar placeholder", r"(execute\s*\([^)]*[%?]|execute\s*\([^)]*:\w+|placeholder)"),),
 forbidden=(("remover concatenação SQL", r"select\s+id,name\s+from\s+users[^\\n]*\+\s*user"),),
 hints=("Não coloque a entrada dentro da string SQL.", "Passe os valores como parâmetros separados."),
 explanation="Concatenar entrada na consulta mistura dados com código SQL e cria uma superfície clássica de SQL Injection.",
 solution="Use placeholder suportado pelo driver e passe user como argumento separado."),

_challenge("idor-bola", "Objeto do usuário correto", "idor-bola", "intermediário", 200,
 "Faça a autorização depender do usuário autenticado, não apenas do ID recebido.",
 "O endpoint confia no user_id enviado pelo cliente.",
 """<!doctype html><h1>BOLA Lab</h1><pre>
def get_invoice(request):
    invoice = db.get_invoice(request.args["invoice_id"])
    return invoice
# Deve haver uma checagem de propriedade/tenant antes de devolver o objeto.
</pre>""",
 required=(("verificar proprietário", r"(current_user\.id|owner_id|tenant_id).{0,120}(invoice|object)|authorize|permission"),),
 forbidden=(("não confiar só no ID", r"db\.get_invoice\(request\.args\[\s*[\"']invoice_id"),),
 hints=("Autenticação diz quem é o usuário; autorização diz o que ele pode acessar.",),
 explanation="BOLA/IDOR ocorre quando um identificador controlado pelo cliente permite acessar um objeto sem checar autorização.",
 solution="Busque o objeto dentro do escopo do usuário/tenant ou valide explicitamente a propriedade antes de retornar."),

_challenge("auth-fraca", "Login sem senha fixa", "auth-fraca", "iniciante", 100,
 "Remova a senha fixa e use verificação por hash.",
 "O laboratório compara a senha recebida diretamente com uma string.",
 """<!doctype html><h1>Auth Lab</h1><pre>
def login(password):
    if password == "123456":
        return "ok"
    return "denied"
</pre>""",
 required=(("usar verificação de hash", r"(check_password_hash|bcrypt|argon2|verify_password)"),),
 forbidden=(("remover senha literal", r"password\s*==\s*[\"']123456[\"']"),),
 hints=("Não armazene nem compare senhas em texto puro.",),
 explanation="Uma senha fixa no código pode ser descoberta e reutilizada. Sistemas reais devem armazenar hashes fortes com salt.",
 solution="Use uma biblioteca de hashing de senha e compare o hash armazenado com a senha recebida."),

_challenge("sessao", "Cookie de sessão protegido", "sessao", "intermediário", 200,
 "Adicione flags de segurança ao cookie de sessão.",
 "A configuração inicial não define Secure, HttpOnly e SameSite.",
 """<!doctype html><h1>Session Lab</h1><pre>
app.config["SESSION_COOKIE_HTTPONLY"] = False
app.config["SESSION_COOKIE_SECURE"] = False
# Tarefa: endurecer a sessão sem quebrar o login local.
</pre>""",
 required=(("HttpOnly habilitado", r"SESSION_COOKIE_HTTPONLY.{0,30}true"),("SameSite configurado", r"SESSION_COOKIE_SAMESITE"),),
 forbidden=(("Secure não desativado", r"SESSION_COOKIE_SECURE.{0,30}false"),),
 hints=("HttpOnly reduz acesso do JavaScript ao cookie.", "SameSite ajuda contra CSRF; Secure exige HTTPS."),
 explanation="Cookies de sessão precisam de flags apropriadas para reduzir roubo e envio indevido.",
 solution="Use HttpOnly=True, SameSite=Lax/Strict e Secure=True em produção HTTPS."),

_challenge("csrf", "Proteção CSRF", "csrf", "intermediário", 200,
 "Exija um token anti-CSRF antes de aceitar uma alteração de estado.",
 "O formulário altera dados sem nenhuma verificação anti-CSRF.",
 """<!doctype html><h1>CSRF Lab</h1><form method="post" action="/profile">
<input name="display_name"><button>Salvar</button>
</form><pre># tarefa: adicionar token e validação no backend</pre>""",
 required=(("token CSRF presente", r"(csrf_token|csrf-token|csrf)"),("validação no backend", r"(validate_csrf|csrfprotect|validate.*csrf)"),),
 hints=("Um campo escondido sozinho não protege: o servidor precisa validar o token.",),
 explanation="CSRF explora ações autenticadas enviadas por uma origem não confiável. A defesa precisa ser validada no servidor.",
 solution="Use um token anti-CSRF por sessão/formulário e valide-o no endpoint mutável."),

_challenge("cors", "CORS restrito", "cors", "iniciante", 100,
 "Troque CORS universal por uma lista de origens confiáveis.",
 "A API aceita qualquer origem.",
 """<!doctype html><h1>CORS Lab</h1><pre>
response.headers["Access-Control-Allow-Origin"] = "*"
# Tarefa: permitir somente https://app.exemplo.test
</pre>""",
 required=(("origem confiável", r"app\.exemplo\.test"),),
 forbidden=(("remover wildcard", r"allow-origin[^\\n]*\*"),),
 hints=("CORS deve refletir uma política de origens, não ser um atalho para '*'." ,),
 explanation="CORS aberto pode permitir que sites não confiáveis leiam respostas de APIs que o navegador autoriza.",
 solution="Configure uma allowlist e valide Origin no backend."),

_challenge("api-insegura", "API com autorização", "api-insegura", "intermediário", 200,
 "Faça o endpoint exigir autenticação e autorização antes de alterar dados.",
 "O endpoint executa uma operação apenas porque recebeu JSON válido.",
 """<!doctype html><h1>API Lab</h1><pre>
@app.post("/api/admin/reset")
def reset():
    data = request.json
    return {"ok": True}
# Tarefa: exigir usuário autenticado e papel administrativo.
</pre>""",
 required=(("autenticação", r"(login_required|authenticated|current_user)"),("autorização", r"(admin|role|permission|authorize)"),),
 hints=("Validação de JSON não substitui autenticação.",),
 explanation="APIs precisam verificar identidade e permissão no servidor em cada operação sensível.",
 solution="Proteja a rota com autenticação e uma checagem de capacidade/papel no backend."),

_challenge("upload", "Upload seguro", "upload", "intermediário", 200,
 "Valide nome, extensão e conteúdo do arquivo antes de salvar.",
 "A implementação confia somente na extensão enviada pelo cliente.",
 """<!doctype html><h1>Upload Lab</h1><pre>
filename = request.files["file"].filename
if filename.endswith(".png"):
    request.files["file"].save("/uploads/" + filename)
# Tarefa: validar conteúdo e usar nome seguro.
</pre>""",
 required=(("nome seguro", r"secure_filename"),("validação do conteúdo", r"(verify|Image\.open|magic|mime)"),),
 forbidden=(("remover concatenação direta do caminho", r"save\([^\\n]*\+\s*filename"),),
 hints=("Extensão é controlada pelo cliente.", "Use secure_filename e valide o conteúdo real."),
 explanation="Upload inseguro pode permitir arquivos inesperados ou manipulação de caminhos.",
 solution="Use secure_filename, allowlist de tipos e validação do conteúdo; grave fora de diretórios executáveis."),

_challenge("traversal", "Caminho confinado", "traversal", "intermediário", 200,
 "Impeça que o nome do arquivo escape do diretório permitido.",
 "O caminho é montado diretamente com entrada do usuário.",
 """<!doctype html><h1>Traversal Lab</h1><pre>
path = os.path.join(BASE_DIR, request.args["file"])
return send_file(path)
# Tarefa: confinar o caminho ao diretório permitido.
</pre>""",
 required=(("resolver caminho com segurança", r"(resolve\(|safe_join|commonpath)"),),
 forbidden=(("não juntar entrada diretamente", r"os\.path\.join\(base_dir,\s*request\.args"),),
 hints=("Normalize/resolva o caminho e confirme que ele permanece dentro do diretório base.",),
 explanation="Path traversal ocorre quando entrada externa consegue apontar para arquivos fora do diretório pretendido.",
 solution="Resolva o caminho, compare o diretório final com a base e rejeite qualquer escape."),

_challenge("cmdi", "Subprocesso sem shell", "cmdi", "avançado", 300,
 "Execute argumentos de forma estruturada e sem shell interpretando entrada.",
 "O comando usa shell=True com entrada externa.",
 """<!doctype html><h1>Command Lab</h1><pre>
subprocess.run("ping -c 1 " + host, shell=True)
# Tarefa: remover interpretação de shell e validar o argumento.
</pre>""",
 required=(("shell desativado", r"shell\s*=\s*false"),),
 forbidden=(("não usar shell=True", r"shell\s*=\s*true"),),
 hints=("Prefira uma lista de argumentos.", "shell=False é o padrão seguro para subprocess."),
 explanation="shell=True combinado com entrada controlável pode permitir command injection.",
 solution="Use subprocess.run([...], shell=False) e uma validação/allowlist adequada do argumento."),

_challenge("secrets", "Segredo fora do código", "secrets", "iniciante", 100,
 "Remova credenciais hardcoded e leia segredos do ambiente/cofre.",
 "O arquivo contém uma credencial literal.",
 """<!doctype html><h1>Secrets Lab</h1><pre>
API_KEY = "demo-secret-12345678"
DATABASE_URL = "postgres://admin:senha@db.local/app"
# Tarefa: substituir por configuração segura.
</pre>""",
 required=(("usar ambiente/cofre", r"(os\.environ|getenv|secret manager|vault)"),),
 forbidden=(("remover segredo literal", r"(demo-secret-12345678|postgres://admin:senha@)"),),
 hints=("O repositório não deve ser o cofre.",),
 explanation="Segredos no código podem vazar por repositório, logs, backups e cópias.",
 solution="Use variáveis de ambiente ou um secret manager e rotacione credenciais que já tenham vazado."),

_challenge("headers", "Headers HTTP defensivos", "headers", "iniciante", 100,
 "Adicione headers que reduzam classes comuns de ataque no navegador.",
 "A resposta não define headers de segurança.",
 """<!doctype html><h1>Headers Lab</h1><pre>
@app.after_request
def headers(resp):
    return resp
# Tarefa: adicionar pelo menos nosniff, frame-ancestors/X-Frame-Options e CSP.
</pre>""",
 required=(("nosniff", r"x-content-type-options"),("proteção de frame", r"(x-frame-options|frame-ancestors)"),("CSP", r"content-security-policy"),),
 hints=("Use uma política compatível com os recursos reais do site.",),
 explanation="Headers de segurança ajudam o navegador a restringir comportamentos perigosos.",
 solution="Defina políticas apropriadas no backend, testando recursos legítimos da aplicação."),

_challenge("config", "Debug fora de produção", "config", "iniciante", 100,
 "Impeça que o modo debug seja ativado em produção.",
 "O servidor inicia com debug=True.",
 """<!doctype html><h1>Config Lab</h1><pre>
app.run(debug=True)
# Tarefa: usar configuração segura para produção.
</pre>""",
 required=(("debug desligado", r"debug\s*=\s*false|debug\s*=\s*os\.getenv"),),
 forbidden=(("não iniciar com debug=True", r"app\.run\([^\\n]*debug\s*=\s*true"),),
 hints=("Debug pode expor stack traces e informações internas.",),
 explanation="Modo debug é útil localmente, mas não deve ser exposto em produção.",
 solution="Controle debug por configuração de ambiente e mantenha-o desativado em produção."),

_challenge("logica", "Preço controlado pelo servidor", "logica", "avançado", 300,
 "Não confie no preço enviado pelo navegador.",
 "O total da compra usa diretamente um valor fornecido pelo cliente.",
 """<!doctype html><h1>Business Logic Lab</h1><pre>
@app.post("/checkout")
def checkout():
    item = request.json["item_id"]
    price = request.json["price"]
    charge(price)
# Tarefa: buscar o preço oficial no servidor e calcular o total.
</pre>""",
 required=(("preço oficial do servidor", r"(db\.|catalog|product|server_price|official_price)"),),
 forbidden=(("não cobrar preço recebido", r"charge\s*\(\s*price\s*\)"),),
 hints=("O cliente pode alterar qualquer campo enviado.",),
 explanation="Falhas de lógica de negócio não dependem de uma falha técnica: confiar em valores críticos do cliente pode permitir fraude.",
 solution="Busque preço/estoque no backend e calcule o valor final exclusivamente no servidor."),

_challenge("logs", "Detectar força bruta", "logs", "iniciante", 100,
 "Analise os eventos e identifique a origem com muitas falhas de login.",
 "Use o conjunto de logs fornecido para encontrar o indicador de ataque.",
 """<!doctype html><h1>Blue Team — Logs</h1><pre>
10.0.0.5 login failed
10.0.0.5 login failed
10.0.0.5 login failed
10.0.0.5 login failed
10.0.0.5 login failed
10.0.0.9 login success
Tarefa: registre no final: resposta_suspeito=...; resposta_tipo=...
</pre>""",
 required=(("identificar IP", r"resposta_suspeito\s*=\s*10\.0\.0\.5"),("classificar brute force", r"resposta_tipo\s*=\s*(brute[\s-]*force|força\s*bruta)"),),
 hints=("Conte falhas repetidas por origem.",),
 explanation="Muitas falhas de autenticação concentradas na mesma origem podem indicar tentativa de adivinhação de credenciais.",
 solution="Registrar o IOC e correlacionar com janela de tempo, conta atingida e controles de rate limit."),

_challenge("incidente", "Linha do tempo do incidente", "incidente", "intermediário", 200,
 "Construa uma timeline a partir dos eventos e destaque o primeiro indicador suspeito.",
 "É um exercício de investigação sem executar malware ou acessar rede.",
 """<!doctype html><h1>Incident Response Lab</h1><pre>
09:01 backup concluído
09:04 login failed user=admin src=10.0.0.5
09:05 login failed user=admin src=10.0.0.5
09:07 login success user=admin src=10.0.0.5
09:08 arquivo config alterado
Tarefa: registre: resposta_timeline=...; resposta_indicador=...
</pre>""",
 required=(("timeline correta", r"resposta_timeline\s*=\s*09:04.{0,80}09:05.{0,80}09:07.{0,80}09:08"),("indicador", r"resposta_indicador\s*=\s*(login|autenticação).{0,80}(repet|falh|suspeit)"),),
 hints=("Comece pelo primeiro evento anômalo e preserve a ordem temporal.",),
 explanation="Uma timeline ajuda a separar atividade normal, acesso inicial e mudanças posteriores.",
 solution="Documente timestamps, usuário, origem, ação e evidência sem alterar os artefatos originais."),

_challenge("malware", "Malware fictício — triagem", "malware", "intermediário", 200,
 "Identifique indicadores no artefato fictício sem executá-lo.",
 "O laboratório contém strings simuladas que devem ser classificadas.",
 """<!doctype html><h1>Malware Analysis Lab</h1><pre>
FILE: sample_fake.bin
STRINGS:
"C:\\Users\\Public\\update.exe"
"powershell -enc [SIMULADO]"
"connect-back.invalid"
Tarefa: registre: resposta_ioc=...; resposta_tecnica=...; resposta_dominio=...
</pre>""",
 required=(("IOC do arquivo", r"resposta_ioc\s*=\s*update\.exe"),("script", r"resposta_tecnica\s*=\s*(powershell|script)"),("domínio fictício", r"resposta_dominio\s*=\s*connect-back\.invalid"),),
 hints=("Não execute o arquivo; análise estática é suficiente.",),
 explanation="Triagem inicial pode extrair strings e indicadores sem executar o artefato.",
 solution="Registrar os IOCs e investigar contexto em ambiente isolado/sandbox apropriado."),

_challenge("pcap", "PCAP simulado", "pcap", "intermediário", 200,
 "Interpretar um pequeno recorte de tráfego simulado.",
 "O exercício usa linhas de pacote, não captura tráfego real.",
 """<!doctype html><h1>PCAP Lab</h1><pre>
10.0.0.7:51514 -> 10.0.0.20:80 GET /login
10.0.0.7:51515 -> 10.0.0.20:22 SYN
10.0.0.7:51516 -> 10.0.0.20:22 SYN
Tarefa: registre: resposta_origem=...; resposta_servico=...; resposta_web=...
</pre>""",
 required=(("origem", r"resposta_origem\s*=\s*10\.0\.0\.7"),("porta sondada", r"resposta_servico\s*=\s*22"),("web", r"resposta_web\s*=\s*80"),),
 hints=("Leia origem, destino e porta antes de interpretar intenção.",),
 explanation="A leitura básica de PCAP envolve identificar fluxos, portas e sequência de eventos.",
 solution="Documente o fluxo observado e só conclua sobre intenção quando houver evidência suficiente."),

_challenge("reverse", "Reverse Engineering — pseudocódigo", "reverse", "avançado", 300,
 "Reconheça a lógica de uma função sem executar o binário.",
 "O binário é representado por pseudocódigo seguro.",
 """<!doctype html><h1>Reverse Lab</h1><pre>
FUNC check(input):
  hash = SHA256(input)
  IF hash == "ABC123_SIMULADO":
     RETURN "OK"
  RETURN "NO"
Tarefa: registre: resposta_objetivo=...; resposta_comparacao=...
</pre>""",
 required=(("objetivo identificado", r"resposta_objetivo\s*=\s*verificar\s*hash"),("constante identificada", r"resposta_comparacao\s*=\s*ABC123_SIMULADO"),),
 hints=("Procure a transformação da entrada e a condição de retorno.",),
 explanation="Engenharia reversa começa por reconhecer fluxo, chamadas e constantes antes de tentar entender detalhes.",
 solution="Documente função, entrada, transformação, comparação e caminhos de retorno; não execute código desconhecido."),


_challenge("rate-limit", "API contra força bruta", "config", "intermediário", 200,
 "Adicione limitação de tentativas ao endpoint de autenticação.",
 "O endpoint aceita tentativas ilimitadas no laboratório.",
 """<!doctype html><h1>Rate Limit Lab</h1><pre>
@app.post("/login")
def login():
    # tarefa: limitar tentativas por IP/conta e responder de forma segura
    return authenticate(request.json)
</pre>""",
 required=(("limitação implementada", r"(rate.?limit|limiter|429|too.?many)"),
           ("janela/limite definido", r"(per.?minute|per.?second|max.?attempt|limit\s*=)")),
 forbidden=(("não confiar só no frontend", r"javascript[^\n]*disable|button[^\n]*disabled"),),
 hints=("Rate limiting precisa ser aplicado no servidor.", "Considere IP e/ou identidade da conta e uma janela de tempo."),
 explanation="Sem limitação no servidor, um endpoint de autenticação pode receber muitas tentativas automatizadas.",
 solution="Aplique rate limiting no backend, registre eventos e retorne 429 quando o limite for excedido."),

_challenge("tls-min", "TLS moderno", "config", "intermediário", 200,
 "Impeça o uso de protocolos TLS obsoletos.",
 "A configuração simulada ainda permite TLS 1.0/1.1.",
 """<!doctype html><h1>TLS Lab</h1><pre>
ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
# tarefa: permitir apenas protocolos modernos
</pre>""",
 required=(("TLS moderno habilitado", r"TLSv1\.2|TLSv1\.3"),),
 forbidden=(("TLS antigo removido", r"TLSv1(?:\s|;|$)|TLSv1\.1"),),
 hints=("TLS 1.0 e 1.1 são legados.", "Mantenha somente versões modernas suportadas pelo seu ambiente."),
 explanation="Protocolos legados aumentam a superfície criptográfica e podem impedir políticas modernas de segurança.",
 solution="Configure o servidor para aceitar somente TLS moderno, conforme a política e compatibilidade necessárias."),

_challenge("permissions", "Permissões mínimas", "config", "iniciante", 100,
 "Remova permissões excessivamente abertas de um arquivo de configuração.",
 "O arquivo está marcado como legível/escrevível por qualquer usuário.",
 """<!doctype html><h1>Permissions Lab</h1><pre>
chmod 777 /etc/tfstudio/app.conf
# tarefa: aplicar menor privilégio
</pre>""",
 required=(("permissão restrita", r"chmod\s+(600|640|644)"),),
 forbidden=(("remover 777", r"chmod\s+777"),),
 hints=("Comece pelo princípio do menor privilégio.", "Arquivos com segredos não precisam ser graváveis por todos."),
 explanation="Permissões amplas podem permitir leitura ou alteração indevida de configurações sensíveis.",
 solution="Use a permissão mínima necessária para o processo e os administradores legítimos."),

_challenge("error-leak", "Erros sem vazamento", "api-insegura", "intermediário", 200,
 "Evite devolver traceback e detalhes internos ao cliente.",
 "O endpoint devolve a exceção completa na resposta HTTP.",
 """<!doctype html><h1>Error Handling Lab</h1><pre>
try:
    result = service.run()
except Exception as exc:
    return {"error": repr(exc), "traceback": traceback.format_exc()}, 500
# tarefa: registrar detalhes no servidor e devolver mensagem genérica
</pre>""",
 required=(("mensagem segura ao cliente", r"(mensagem genérica|internal server error|erro interno|generic)"),
           ("log interno", r"(logger|log\.exception|logging)")),
 forbidden=(("não devolver traceback", r"traceback\.format_exc\(\)|[\"']traceback[\"']\s*:"),),
 hints=("O usuário precisa de uma mensagem útil, não do stack trace.", "Registre detalhes no servidor com controle de acesso."),
 explanation="Tracebacks podem revelar caminhos, bibliotecas, consultas e detalhes internos úteis para um atacante.",
 solution="Registre a exceção no servidor e retorne uma mensagem genérica com um identificador de correlação."),

_challenge("jwt-verify", "JWT com assinatura verificada", "api-insegura", "avançado", 300,
 "Garanta que o servidor valide a assinatura do JWT antes de confiar nas claims.",
 "O código apenas decodifica o token e usa o payload.",
 """<!doctype html><h1>JWT Lab</h1><pre>
payload = jwt.decode(token, options={"verify_signature": False})
if payload.get("role") == "admin":
    return admin_area()
# tarefa: validar assinatura antes de usar role
</pre>""",
 required=(("assinatura verificada", r"(verify_signature\s*=\s*true|verify=True|algorithms\s*=|decode_and_verify|verify_token)"),),
 forbidden=(("não confiar em decode sem verificação", r"verify_signature\s*[=:]\s*false|verify_signature[\"']?\s*\]"),),
 hints=("Decodificar não é o mesmo que verificar.", "A biblioteca deve validar assinatura e algoritmo esperado antes das claims."),
 explanation="Um JWT pode ser lido sem ser autenticado. Confiar em claims sem verificar a assinatura permite manipulação do conteúdo.",
 solution="Valide assinatura, algoritmo permitido, expiração e demais claims necessárias antes de autorizar."),

_challenge("admin-route", "Rota administrativa protegida", "auth-fraca", "intermediário", 200,
 "Proteja uma rota administrativa com autenticação e autorização no backend.",
 "A rota retorna dados administrativos sem checar o usuário.",
 """<!doctype html><h1>Admin Route Lab</h1><pre>
@app.get("/admin/reports")
def reports():
    return get_private_reports()
# tarefa: exigir autenticação e papel/capacidade adequada
</pre>""",
 required=(("autenticação presente", r"(login_required|authenticated|current_user|require_auth)"),
           ("autorização presente", r"(admin|role|permission|require_cap|authorize)")),
 hints=("Autenticação identifica; autorização decide se pode.", "A proteção precisa estar no backend."),
 explanation="Uma rota administrativa sem checagem permite que qualquer sessão ou requisição direta tente acessar dados privilegiados.",
 solution="Use os decoradores/middleware de autenticação e capacidade já existentes no projeto."),

_challenge("input-allowlist", "Validação de entrada", "config", "iniciante", 100,
 "Valide uma entrada antes de usá-la em uma operação sensível.",
 "O código aceita qualquer valor recebido pelo cliente.",
 """<!doctype html><h1>Input Validation Lab</h1><pre>
filename = request.args.get("filename", "")
open("/safe/files/" + filename, "rb")
# tarefa: validar formato e confinar o caminho
</pre>""",
 required=(("validação/allowlist", r"(allowlist|allowed|regex|re\.fullmatch|secure_filename|Path\().{0,160}(filename|input)"),),
 forbidden=(("remover concatenação de caminho não validada", r"open\([^\n]*safe/files/[^\n]*\+\s*filename"),),
 hints=("Validação deve acontecer no servidor.", "Além do formato, confine o caminho ao diretório permitido."),
 explanation="Entradas externas precisam ser tratadas como não confiáveis, principalmente quando influenciam arquivos ou operações sensíveis.",
 solution="Valide o formato esperado e use APIs de caminho seguro que impeçam sair do diretório permitido."),

_challenge("dependency-pinning", "Dependência previsível", "config", "intermediário", 200,
 "Torne uma dependência do laboratório determinística e auditável.",
 "O arquivo aceita qualquer versão de uma biblioteca crítica.",
 """<!doctype html><h1>Dependency Lab</h1><pre>
requests
flask>=2
# tarefa: usar versões/faixas conscientemente definidas e manter auditoria de dependências
</pre>""",
 required=(("dependência com versão", r"(?m)^\s*(requests|flask)\s*[=<>~!]{1,2}\s*\d"),),
 forbidden=(("evitar dependência totalmente solta", r"(?m)^\s*requests\s*$"),),
 hints=("Pinning ou faixas conscientes ajudam a reproduzir builds.", "Dependências ainda precisam de atualização e auditoria de vulnerabilidades."),
 explanation="Dependências sem versão podem mudar o comportamento do ambiente de forma inesperada e dificultar auditoria/reprodução.",
 solution="Defina versões/faixas conscientemente e use ferramentas de auditoria/lockfile apropriadas ao ecossistema."),

]

from services import cyber_challenges_extra as _extra
CATEGORIES.update(_extra.NEW_CATEGORIES)
CHALLENGES.extend(_extra.build(_challenge))
if hasattr(_extra, "build_more"):
    CHALLENGES.extend(_extra.build_more(_challenge))

from services import cyber_challenges_v33 as _v33  # v33: desafios extras
CATEGORIES.update(_v33.NEW_CATEGORIES)
CHALLENGES.extend(_v33.build(_challenge))

from services import cyber_challenges_v34 as _v34  # v34: expert + conquistas
CATEGORIES.update(_v34.NEW_CATEGORIES)
CHALLENGES.extend(_v34.build(_challenge))

CATALOG = {c["id"]: c for c in CHALLENGES}
