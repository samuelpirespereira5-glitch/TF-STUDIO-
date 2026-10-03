"""Desafios extras do Cyber Lab (secure coding + CTF educacional).

Tudo é texto local: nada é executado nem enviado à rede. Cada desafio é
validado por padrões sobre o texto que a pessoa envia.
"""

NEW_CATEGORIES = {
    "ssrf": "SSRF",
    "redirect": "Open Redirect",
    "xxe": "XXE",
    "deserial": "Desserialização insegura",
    "mass-assign": "Mass Assignment",
    "crypto": "Criptografia e hashing",
    "cookies": "Cookies seguros",
    "csp": "Content Security Policy",
    "redos": "ReDoS",
    "race": "Race condition",
    "ctf": "CTF clássico",
    "docker": "Containers",
    "supply": "Cadeia de suprimentos",
}

def build(_challenge):
    C = _challenge
    return [

C("ssrf-allowlist", "Busca de URL controlada", "ssrf", "avançado", 250,
 "Impeça que o servidor busque qualquer URL vinda do usuário: valide o host contra uma allowlist.",
 "O endpoint faz uma requisição para qualquer URL recebida, inclusive endereços internos.",
 """<!doctype html><h1>SSRF Lab</h1><pre>
@app.get("/preview")
def preview():
    return requests.get(request.args["url"]).text
# tarefa: aceitar somente hosts permitidos
</pre>""",
 required=(("allowlist de hosts", r"(allowed_hosts|allowlist)"), ("extrair o host da URL", r"(urlparse|hostname)")),
 forbidden=(("remover requisição direta com URL do usuário", r"requests\.get\(\s*request\.args"),),
 hints=("Nunca confie na URL inteira.", "Extraia o hostname com urlparse e compare com uma lista fixa."),
 explanation="SSRF faz o servidor acessar recursos internos (metadados de nuvem, painéis, bancos) em nome do atacante.",
 solution="Parseie a URL, compare o hostname com ALLOWED_HOSTS e bloqueie IPs privados/loopback."),

C("open-redirect", "Redirecionamento livre", "redirect", "intermediário", 150,
 "Redirecione apenas para caminhos internos do próprio site.",
 "O parâmetro next é usado direto no redirect após o login.",
 """<!doctype html><h1>Redirect Lab</h1><pre>
@app.post("/login")
def login():
    return redirect(request.args.get("next"))
# tarefa: aceitar só destinos internos
</pre>""",
 required=(("validar destino interno", r"(startswith\(\s*[\"']/[\"']|url_for|is_safe|urlparse|allowed)"),),
 forbidden=(("remover redirect direto", r"redirect\(\s*request\.args"),),
 hints=("Um destino seguro começa com uma única barra.", "Cuidado com //dominio.com, que também começa com barra."),
 explanation="Open redirect é usado em phishing: o link parece do seu site, mas leva para outro.",
 solution="Aceite só caminhos relativos (começando com '/' e não '//') ou use uma lista de destinos."),

C("xxe-parser", "Parser XML confiante demais", "xxe", "avançado", 250,
 "Desative a resolução de entidades externas no parser XML.",
 "O parser aceita entidades externas em documentos enviados pelo usuário.",
 """<!doctype html><h1>XXE Lab</h1><pre>
parser = etree.XMLParser(resolve_entities=True)
doc = etree.fromstring(request.data, parser)
# tarefa: fechar a superfície de XXE
</pre>""",
 required=(("entidades desativadas ou defusedxml", r"(resolve_entities\s*=\s*false|defusedxml)"),),
 forbidden=(("remover resolve_entities=True", r"resolve_entities\s*=\s*true"),),
 hints=("Procure a opção que resolve entidades.", "A biblioteca defusedxml já vem com padrões seguros."),
 explanation="XXE permite ler arquivos locais ou fazer requisições internas através de entidades XML.",
 solution="Use resolve_entities=False (e no_network=True) ou a biblioteca defusedxml."),

C("unsafe-deserialization", "Pickle do desconhecido", "deserial", "avançado", 250,
 "Troque a desserialização insegura por um formato de dados puro.",
 "O servidor usa pickle em dados recebidos da rede.",
 """<!doctype html><h1>Deserialization Lab</h1><pre>
@app.post("/import")
def import_data():
    obj = pickle.loads(request.data)
    return jsonify(obj)
# tarefa: usar um formato que não execute código
</pre>""",
 required=(("formato de dados puro", r"(json\.loads|yaml\.safe_load)"),),
 forbidden=(("remover pickle.loads", r"pickle\.loads"),),
 hints=("Pickle pode executar código ao carregar.", "JSON só carrega dados."),
 explanation="Desserializar objetos não confiáveis pode levar a execução remota de código.",
 solution="Use JSON (ou yaml.safe_load) e valide o esquema dos campos esperados."),

C("mass-assignment", "Campos demais", "mass-assign", "intermediário", 200,
 "Aceite apenas os campos permitidos ao criar o usuário.",
 "O corpo da requisição inteiro vira atributos do objeto, inclusive is_admin.",
 """<!doctype html><h1>Mass Assignment Lab</h1><pre>
@app.post("/users")
def create():
    user = User(**request.json)
    db.add(user)
# tarefa: aceitar somente name e email
</pre>""",
 required=(("lista de campos permitidos", r"(allowed_fields|allowlist|fields\s*=|pick\()"),),
 forbidden=(("remover **request.json", r"\*\*request\.(get_json|json|form)"),),
 hints=("Nunca desempacote a requisição direto no modelo.", "Monte um dicionário só com as chaves permitidas."),
 explanation="Sem allowlist, um cliente pode enviar campos como role ou is_admin e escalar privilégios.",
 solution="Filtre o payload com ALLOWED_FIELDS = {'name','email'} antes de criar o objeto."),

C("password-hashing", "Senha em MD5", "crypto", "iniciante", 100,
 "Guarde senhas com um algoritmo próprio para isso.",
 "As senhas são guardadas com MD5 sem sal.",
 """<!doctype html><h1>Password Lab</h1><pre>
digest = hashlib.md5(password.encode()).hexdigest()
db.save(user, digest)
# tarefa: usar hash de senha adequado
</pre>""",
 required=(("algoritmo de senha", r"(bcrypt|argon2|scrypt|pbkdf2)"),),
 forbidden=(("remover md5/sha1", r"hashlib\.(md5|sha1)\("),),
 hints=("Hash rápido é ruim para senhas.", "Use bcrypt, argon2 ou scrypt."),
 explanation="Hashes rápidos permitem testar bilhões de tentativas por segundo; algoritmos de senha são lentos de propósito e usam sal.",
 solution="Use bcrypt.hashpw / argon2 / hashlib.scrypt com sal aleatório."),

C("cookie-flags", "Cookie pelado", "cookies", "iniciante", 100,
 "Defina as flags de segurança do cookie de sessão.",
 "O cookie de sessão é criado sem nenhuma flag.",
 """<!doctype html><h1>Cookie Lab</h1><pre>
resp.set_cookie("session", token)
# tarefa: HttpOnly, Secure e SameSite
</pre>""",
 required=(("HttpOnly", r"httponly\s*=\s*true"), ("Secure", r"secure\s*=\s*true"), ("SameSite", r"samesite\s*=\s*[\"'](lax|strict)[\"']")),
 forbidden=(("remover set_cookie sem flags", r"set_cookie\(\s*[\"']session[\"']\s*,\s*token\s*\)"),),
 hints=("São três flags.", "SameSite aceita Lax ou Strict."),
 explanation="HttpOnly bloqueia leitura por JavaScript, Secure exige HTTPS e SameSite reduz CSRF.",
 solution="resp.set_cookie('session', token, httponly=True, secure=True, samesite='Lax')"),

C("csp-strict", "CSP permissiva", "csp", "intermediário", 200,
 "Escreva uma Content-Security-Policy que não libere scripts inline nem origens curinga.",
 "A política atual libera tudo, então quase não protege contra XSS.",
 """<!doctype html><h1>CSP Lab</h1><pre>
Content-Security-Policy: default-src * 'unsafe-inline'
# tarefa: restringir a origens próprias
</pre>""",
 required=(("default-src restrito", r"default-src\s+'self'"),),
 forbidden=(("remover 'unsafe-inline'", r"'unsafe-inline'"), ("remover curinga", r"default-src\s+\*")),
 hints=("Comece por default-src 'self'.", "Scripts inline podem usar nonce ou hash."),
 explanation="Uma CSP forte limita de onde scripts carregam e reduz muito o estrago de um XSS.",
 solution="Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'"),

C("redos-regex", "Regex que trava", "redos", "avançado", 250,
 "Elimine o quantificador aninhado e limite o tamanho da entrada.",
 "A expressão regular tem backtracking exponencial.",
 """<!doctype html><h1>ReDoS Lab</h1><pre>
import re
PATTERN = re.compile(r"^(a+)+$")
def valid(text):
    return bool(PATTERN.match(text))
# tarefa: corrigir o padrão e limitar a entrada
</pre>""",
 required=(("limite de tamanho", r"len\(.+\)\s*(<=|<)\s*\d+"),),
 forbidden=(("remover quantificador aninhado", r"\(\w\+\)\+"),),
 hints=("(a+)+ é o exemplo clássico.", "Use ^a+$ e recuse textos muito longos."),
 explanation="Regex com grupos repetidos dentro de repetições pode levar tempo exponencial e derrubar o serviço.",
 solution="Use ^a+$ e valide len(text) <= 100 antes de aplicar a expressão."),

C("race-condition", "Saldo duplo", "race", "avançado", 250,
 "Torne a verificação e o débito do saldo uma operação atômica.",
 "Duas requisições simultâneas passam pela checagem antes do débito.",
 """<!doctype html><h1>Race Lab</h1><pre>
def withdraw(user, amount):
    if user.balance >= amount:
        time.sleep(0.1)
        user.balance -= amount
# tarefa: evitar o saque duplo
</pre>""",
 required=(("lock/transação/atualização atômica", r"(with\s+\w*lock|select\s+.*for\s+update|atomic|transaction|update\s+.*where\s+.*balance\s*>=)"),),
 hints=("A checagem e a escrita precisam ser indivisíveis.", "Trava, transação ou UPDATE condicional resolvem."),
 explanation="Race conditions de check-then-act permitem gastar o mesmo saldo várias vezes.",
 solution="Use um lock, uma transação com SELECT ... FOR UPDATE ou UPDATE ... WHERE balance >= amount."),

C("dockerfile-nonroot", "Container como root", "docker", "iniciante", 100,
 "Fixe a versão da imagem e rode a aplicação com usuário sem privilégios.",
 "O Dockerfile usa a tag latest e roda como root.",
 """<!doctype html><h1>Docker Lab</h1><pre>
FROM python:latest
COPY . /app
CMD ["python", "/app/app.py"]
# tarefa: versão fixa e usuário não-root
</pre>""",
 required=(("usuário não-root", r"(?m)^\s*user\s+(?!root)\w+"),),
 forbidden=(("remover tag latest", r"(?m)^\s*from\s+\S+:latest"),),
 hints=("Use uma tag específica, como python:3.12-slim.", "Crie um usuário e use a instrução USER."),
 explanation="Root dentro do container aumenta o impacto de uma invasão; latest torna o build imprevisível.",
 solution="FROM python:3.12-slim + RUN useradd -m app + USER app"),

C("sri-script", "Script de CDN sem integridade", "supply", "iniciante", 100,
 "Adicione Subresource Integrity ao script externo.",
 "Se a CDN for comprometida, o site carrega código malicioso.",
 """<!doctype html><h1>SRI Lab</h1><pre>
<script src="https://cdn.example.com/lib.js"></script>
# tarefa: integrity + crossorigin
</pre>""",
 required=(("atributo integrity", r"integrity\s*=\s*[\"']sha(256|384|512)-"), ("atributo crossorigin", r"crossorigin")),
 hints=("O hash vem no formato sha384-...", "crossorigin=\"anonymous\" é necessário."),
 explanation="SRI faz o navegador recusar o arquivo se o conteúdo não bater com o hash esperado.",
 solution="<script src=... integrity=\"sha384-HASH\" crossorigin=\"anonymous\"></script>"),

C("ctf-rot13", "Mensagem embaralhada", "ctf", "iniciante", 100,
 "Decifre o texto e envie a flag no formato flag{...}.",
 "Um bilhete usa uma cifra de substituição bem conhecida.",
 """<!doctype html><h1>CTF Cifra</h1><pre>
synt{pnrfne_pvcure_yby}
Dica: cada letra foi deslocada 13 posições.
</pre>""",
 required=(("flag correta", r"flag\{caesar_cipher_lol\}"),),
 hints=("É a cifra de César com deslocamento 13 (ROT13).", "Em Python: codecs.decode(texto, 'rot13')."),
 explanation="ROT13 não é criptografia de verdade: aplicar duas vezes devolve o texto original.",
 solution="flag{caesar_cipher_lol}"),

C("ctf-base64", "Codificação não é cifra", "ctf", "iniciante", 100,
 "Decodifique o texto e envie a flag.",
 "Alguém escondeu a flag apenas codificando em Base64.",
 """<!doctype html><h1>CTF Base64</h1><pre>
ZmxhZ3tiYXNlNjRfbmFvX2VfY3JpcHRvZ3JhZmlhfQ==
</pre>""",
 required=(("flag correta", r"flag\{base64_nao_e_criptografia\}"),),
 hints=("O sinal de = no final é característico de Base64.", "Use base64 -d ou base64.b64decode."),
 explanation="Base64 é só uma forma de representar dados; não protege nada.",
 solution="flag{base64_nao_e_criptografia}"),

C("ctf-log-bruteforce", "Quem está tentando entrar?", "logs", "intermediário", 200,
 "Descubra o IP com mais falhas de login e informe-o na resposta.",
 "Um log de autenticação mostra tentativas repetidas de um mesmo endereço.",
 """<!doctype html><h1>Log Forensics</h1><pre>
10:01:02 FAIL user=admin ip=198.51.100.7
10:01:05 FAIL user=admin ip=203.0.113.50
10:01:06 FAIL user=root  ip=203.0.113.50
10:01:07 OK   user=ana   ip=192.0.2.15
10:01:08 FAIL user=test  ip=203.0.113.50
10:01:09 FAIL user=admin ip=203.0.113.50
10:01:10 FAIL user=guest ip=198.51.100.7
10:01:11 FAIL user=admin ip=203.0.113.50
</pre>""",
 required=(("IP correto", r"203\.0\.113\.50"),),
 forbidden=(("não citar IPs inocentes", r"198\.51\.100\.\d+|192\.0\.2\.\d+"),),
 hints=("Conte só as linhas FAIL por IP.", "grep FAIL log | grep -o 'ip=.*' | sort | uniq -c"),
 explanation="Muitas falhas seguidas de um mesmo IP e usuários diferentes indicam força bruta ou password spraying.",
 solution="203.0.113.50 (5 falhas). Resposta: bloquear/limitar o IP e ativar rate limit."),

C("ctf-xor-hex", "XOR de um byte", "reverse", "intermediário", 200,
 "Descubra a chave de um byte e envie a flag.",
 "A flag foi cifrada com XOR de uma única chave e escrita em hexadecimal.",
 """<!doctype html><h1>CTF XOR</h1><pre>
4c464b4d51524558754c4b49434657
Dica: o texto original começa com "flag{".
</pre>""",
 required=(("flag correta", r"flag\{xor_facil\}"),),
 hints=("XOR do primeiro byte com 'f' revela a chave.", "A chave é 0x2a."),
 explanation="XOR com chave curta é trivial de quebrar quando se conhece parte do texto.",
 solution="flag{xor_facil} (chave 0x2a)"),

C("ctf-http-basic", "Credenciais no ar", "pcap", "iniciante", 150,
 "Decodifique o cabeçalho, informe o usuário e a correção necessária.",
 "Uma captura mostra autenticação Basic sobre HTTP sem criptografia.",
 """<!doctype html><h1>Captura HTTP</h1><pre>
GET /admin HTTP/1.1
Host: intranet.lab
Authorization: Basic bWFyaWE6cGFzc3dvcmQxMjM=
</pre>""",
 required=(("usuário identificado", r"maria"), ("correção: usar HTTPS/TLS", r"(https|tls)")),
 hints=("Basic é Base64 de usuario:senha.", "A correção é proteger o canal."),
 explanation="Basic auth em HTTP expõe usuário e senha a qualquer um que veja o tráfego.",
 solution="Usuário: maria. Correção: exigir HTTPS/TLS e preferir tokens ou SSO."),

C("ssrf-dns-rebinding", "SSRF e DNS rebinding", "ssrf", "avançado", 300,
 "Valide o IP resolvido imediatamente antes da conexão e não confie apenas no hostname.",
 "O código resolve um host uma vez e depois conecta sem revalidar o destino.",
 """<!doctype html><h1>DNS Rebinding Lab</h1><pre>
host = urlparse(url).hostname
ip = socket.gethostbyname(host)
# ... algum tempo depois ...
requests.get(url)
# tarefa: resolver/validar o IP e bloquear redes privadas antes da conexão
</pre>""",
 required=(("resolver e validar IP", r"(getaddrinfo|gethostbyname|resolved_ip|ipaddress)"),
           ("bloquear redes não públicas", r"(is_private|is_loopback|is_link_local|is_reserved|private)")),
 forbidden=(("não conectar só pelo hostname", r"requests\.get\(url\)"),),
 hints=("DNS pode mudar entre a validação e a conexão.", "A decisão precisa usar o endereço resolvido no momento da conexão."),
 explanation="DNS rebinding tenta fazer um hostname público apontar para um IP interno depois da validação inicial.",
 solution="Resolva novamente de forma controlada, valide cada endereço retornado e conecte somente ao destino permitido."),

C("api-idempotency", "Operação idempotente", "api-insegura", "intermediário", 200,
 "Evite criar a mesma operação duas vezes quando o cliente repete uma requisição.",
 "O endpoint cria um recurso a cada POST, mesmo quando a mesma operação é reenviada.",
 """<!doctype html><h1>Idempotency Lab</h1><pre>
@app.post("/payments")
def pay():
    charge(request.json["amount"])
    return {"ok": True}
# tarefa: impedir que o reenvio da mesma requisição cobre duas vezes
</pre>""",
 required=(("chave de idempotência", r"(idempotency|idempotência|idempotency_key)"),
           ("resultado persistido/reutilizado", r"(store|cache|db|persist|existing|already)")),
 hints=("Reenvios podem ocorrer por timeout.", "A mesma chave deve retornar o mesmo resultado sem cobrar novamente."),
 explanation="Sem idempotência, retries podem duplicar pagamentos ou outras operações sensíveis.",
 solution="Aceite uma chave de idempotência, associe-a ao resultado e rejeite/reutilize reenvios."),

C("api-pagination", "Paginação segura", "api-insegura", "iniciante", 100,
 "Impeça que limit/offset causem respostas gigantes ou consultas abusivas.",
 "A API aceita qualquer tamanho solicitado pelo cliente.",
 """<!doctype html><h1>Pagination Lab</h1><pre>
limit = int(request.args.get("limit", 20))
rows = db.query(limit=limit)
return jsonify(rows)
# tarefa: limitar e normalizar limit/offset
</pre>""",
 required=(("limite máximo", r"(max|clamp|min\(|<=\s*\d+|MAX_LIMIT)"),
           ("entrada inválida tratada", r"(try:|except|ValueError|isdigit|int\()")),
 forbidden=(("não aceitar limite arbitrário", r"query\(limit=limit\)"),),
 hints=("Defina um máximo pequeno e previsível.", "Trate valores negativos, enormes e não numéricos."),
 explanation="Paginação sem limite pode consumir memória, banco e rede.",
 solution="Normalize limit/offset e aplique um teto no backend antes da consulta."),

C("csrf-double-submit", "CSRF em ação de estado", "csrf", "intermediário", 200,
 "Exija proteção CSRF no backend para uma operação que altera dados.",
 "O endpoint aceita POST sem verificar o token.",
 """<!doctype html><h1>CSRF Lab</h1><pre>
@app.post("/profile/email")
def change_email():
    user.email = request.form["email"]
    db.save(user)
# tarefa: proteger esta alteração de dados contra requisições forjadas entre sites
</pre>""",
 required=(("validação CSRF", r"(csrf|csrf_token|validate_csrf|X-CSRF)"),
           ("checagem de origem", r"(origin|referer|same-origin)")),
 forbidden=(("não confiar só no frontend", r"javascript.*csrf|button.*disabled"),),
 hints=("O navegador envia cookies automaticamente.", "A validação precisa acontecer antes da alteração persistir."),
 explanation="CSRF pode induzir um navegador autenticado a enviar uma ação que o usuário não pretendia.",
 solution="Valide token CSRF no servidor e use Origin/Referer como defesa complementar."),

C("audit-integrity", "Log de auditoria confiável", "logs", "intermediário", 200,
 "Registre ação sensível sem incluir segredos e preserve o contexto de correlação.",
 "O logger registra a senha/token completo e não possui request id.",
 """<!doctype html><h1>Audit Lab</h1><pre>
logger.info("PASSWORD_CHANGED password=%s token=%s", password, token)
# tarefa: remover segredos e registrar request_id, usuário, ação e resultado
</pre>""",
 required=(("request id", r"(request_id|correlation_id)"),
           ("ação e resultado", r"(action|event|result|success|ok)")),
 forbidden=(("não registrar senha/token", r"(password|token)\s*[%=,:]"),),
 hints=("Logs precisam ajudar a investigar sem virar fonte de segredos.", "Redija valores sensíveis antes de registrar."),
 explanation="Logs com credenciais podem causar um segundo vazamento e dificultar investigação segura.",
 solution="Registre contexto mínimo necessário e substitua segredos por marcadores/redação."),

C("upload-polyglot", "Upload por conteúdo real", "upload", "avançado", 300,
 "Não confie apenas na extensão ou MIME enviado pelo cliente.",
 "O endpoint aceita qualquer arquivo cujo nome termine em .jpg.",
 """<!doctype html><h1>Upload Lab</h1><pre>
name = request.files["file"].filename
if name.endswith(".jpg"):
    file.save("uploads/" + name)
# tarefa: nome aleatório, conteúdo real, diretório seguro e sem execução
</pre>""",
 required=(("nome seguro/aleatório", r"(secure_filename|uuid|secrets\.token|random)"),
           ("validar conteúdo", r"(magic|mimetype|content|signature|image)"),
           ("caminho seguro", r"(safe_join|resolve|commonpath|Path)")),
 forbidden=(("não usar nome diretamente", r"save\(\s*uploads/|save\(\s*.*filename"),),
 hints=("A extensão é controlável pelo cliente.", "O caminho final deve continuar dentro do diretório de uploads."),
 explanation="Uploads inseguros podem sobrescrever arquivos, atravessar diretórios ou armazenar conteúdo executável.",
 solution="Gere nome aleatório, valide o conteúdo real, limite tamanho e mantenha o diretório sem execução."),

C("secret-rotation", "Rotação de segredo", "secrets", "intermediário", 200,
 "Projete rotação sem registrar nem devolver o segredo antigo.",
 "O endpoint mostra a chave antiga e a nova na resposta.",
 """<!doctype html><h1>Secret Rotation Lab</h1><pre>
old = config.API_KEY
new = secrets.token_urlsafe(32)
print("old=", old, "new=", new)
return jsonify({"old": old, "new": new})
# tarefa: armazenar com segurança e nunca expor valores completos
</pre>""",
 required=(("rotação segura", r"(rotate|rotation|new_secret|token_urlsafe|secrets)"),
           ("redação/ausência do segredo na resposta", r"(redact|redacted|oculto|mask|last.?4|hint)")),
 forbidden=(("não devolver segredo completo", r"jsonify\([^\n]*(old|new)"),),
 hints=("Rotacionar não significa imprimir a credencial.", "Retorne apenas metadados seguros, como fingerprint ou últimos caracteres."),
 explanation="Expor uma credencial durante a rotação anula parte do benefício da rotação.",
 solution="Gere/armazenar o novo segredo com segurança, invalide o antigo e retorne somente um identificador seguro."),

C("supply-lockfile", "Cadeia de dependências", "supply", "intermediário", 200,
 "Adicione auditoria automatizada de vulnerabilidades sem atualizar produção automaticamente.",
 "O pipeline instala dependências sem qualquer verificação.",
 """<!doctype html><h1>Supply Chain Lab</h1><pre>
pip install -r requirements.txt
# tarefa: auditar dependências e falhar/alertar conforme política
</pre>""",
 required=(("auditoria de dependências", r"(pip-audit|safety|osv|dependency.?scan)"),
           ("pipeline automatizado", r"(ci|github|gitlab|workflow|pipeline|script)")),
 hints=("Auditoria e atualização são etapas diferentes.", "O objetivo do laboratório é detectar e alertar."),
 explanation="Uma dependência vulnerável pode introduzir risco mesmo quando o código da aplicação parece seguro.",
 solution="Execute pip-audit/OSV no CI, gere relatório e decida atualizações de forma controlada."),
    ]


def build_more(C):
    """Novos desafios locais; continuam determinísticos e sem execução/rede."""
    return [
C("csp-nonce", "Nonce em script inline", "csp", "intermediário", 180,
  "Troque a confiança em script inline por nonce/hash e mantenha a CSP restritiva.",
  "A página usa script-src 'self' 'unsafe-inline' sem nonce.",
  """<pre>Content-Security-Policy: script-src 'self' 'unsafe-inline'\n&lt;script&gt;boot()&lt;/script&gt;</pre>""",
  required=(("nonce presente", r"nonce[-_]?|script-src[^\n]*nonce"),("unsafe-inline removido", r"script-src[^\n]*unsafe-inline")),
  forbidden=(("não liberar inline", r"unsafe-inline"),),
  hints=("Nonce precisa ser imprevisível e ligado à resposta.",),
  explanation="Nonce permite scripts inline específicos sem liberar qualquer script inline.",
  solution="Gere nonce aleatório por resposta, use no script e em script-src 'nonce-...'."),
C("clickjacking", "Proteção contra clickjacking", "csp", "iniciante", 100,
  "Impeça que o painel seja incorporado por sites externos.",
  "A resposta não define frame-ancestors nem X-Frame-Options.",
  """<pre>HTTP/1.1 200 OK\nContent-Type: text/html\n# tarefa: impedir enquadramento externo</pre>""",
  required=(("frame-ancestors", r"frame-ancestors"),),
  forbidden=(("não permitir all", r"frame-ancestors\s+\*"),),
  hints=("CSP moderna pode substituir X-Frame-Options.",),
  explanation="Clickjacking sobrepõe a interface real em um frame controlado por outro site.",
  solution="Use frame-ancestors 'none' ou uma allowlist adequada."),
C("host-header", "Host header confiável", "config", "intermediário", 180,
  "Evite construir links absolutos a partir de um Host não validado.",
  "O aplicativo usa request.host diretamente para links de recuperação.",
  """<pre>reset = f"https://{request.host}/reset/{token}"\n# tarefa: usar configuração de host confiável</pre>""",
  required=(("host allowlist/configuração", r"ALLOWED_HOSTS|allowed_hosts|trusted_hosts"),),
  forbidden=(("não confiar diretamente no host", r"request\.host\s*\}"),),
  hints=("Host é entrada controlada pelo cliente em muitos deployments.",),
  explanation="Host header poisoning pode gerar links de recuperação ou callbacks apontando para domínio controlado pelo atacante.",
  solution="Use origem configurada e validada no servidor; rejeite Hosts desconhecidos."),
C("openapi-auth", "Contrato de API protegido", "api-insegura", "intermediário", 180,
  "Documente autenticação e autorização no contrato da API.",
  "O OpenAPI não descreve nenhum security scheme.",
  """<pre>openapi: 3.0.0\npaths:\n  /admin/users:\n    get: {}\n# tarefa: documentar o requisito de segurança</pre>""",
  required=(("security scheme", r"securitySchemes"),("security aplicado", r"security:")),
  hints=("Documentação não substitui a checagem no backend.",),
  explanation="Contratos incompletos tornam mais fácil esquecer controles em endpoints sensíveis.",
  solution="Defina securitySchemes e aplique security aos endpoints que exigem autenticação."),
C("ssrf-redirect-chain", "Redirect não confiável", "ssrf", "avançado", 280,
  "Valide cada destino de redirect durante uma requisição server-side.",
  "O cliente HTTP segue redirects automaticamente sem revalidar o destino.",
  """<pre>http.get(url, follow_redirects=True)\n# tarefa: revalidar cada destino</pre>""",
  required=(("redirects controlados", r"follow_redirects\s*=\s*false|redirect.*validate|revalidate"),),
  forbidden=(("não seguir redirects cegamente", r"follow_redirects\s*=\s*true"),),
  hints=("Um URL público pode redirecionar para rede privada.",),
  explanation="SSRF pode escapar de uma validação inicial através de redirects para destinos internos.",
  solution="Desative redirects automáticos ou valide cada Location antes de conectar ao próximo destino."),
C("dns-rebinding", "DNS rebinding", "ssrf", "avançado", 280,
  "Mantenha a decisão de SSRF ligada ao IP realmente conectado.",
  "O hostname é validado uma vez e resolvido novamente pelo cliente HTTP.",
  """<pre>ip = resolve(host)\nassert public(ip)\nrequests.get("https://" + host)\n# tarefa: impedir mudança entre validação e conexão</pre>""",
  required=(("conexão ao IP validado", r"pinned|resolved_ip|connect.*ip|Pinned"),("bloqueio de IP privado", r"is_private|is_loopback|is_link_local|is_reserved")),
  forbidden=(("não reconectar pelo hostname", r"requests\.get\(.*host"),),
  hints=("A segunda resolução pode retornar outro IP.",),
  explanation="DNS rebinding explora a diferença entre o endereço validado e o endereço usado na conexão.",
  solution="Resolva, valide e fixe o endereço aprovado para a conexão, tratando redirects do mesmo modo."),
C("jwt-algorithm", "JWT: algoritmo inesperado", "crypto", "avançado", 260,
  "Não aceite algoritmo criptográfico arbitrário vindo do token.",
  "O servidor escolhe a verificação a partir do campo alg do JWT.",
  """<pre>header = decode_header(token)\nverify(token, algorithm=header["alg"])\n# tarefa: allowlist de algoritmos</pre>""",
  required=(("allowlist de algoritmo", r"allowed.*alg|algorithms\s*=|allowlist"),),
  forbidden=(("não confiar no alg do token", r'algorithm\s*=\s*header\[\"alg\"\]'),),
  hints=("O token não deve escolher a política criptográfica do servidor.",),
  explanation="Política criptográfica precisa ser definida pelo servidor, não pelo atacante.",
  solution="Defina uma allowlist de algoritmos e rejeite qualquer algoritmo fora dela."),
C("webhook-signature", "Webhook autenticado", "api-insegura", "intermediário", 200,
  "Verifique autenticidade e integridade de webhooks recebidos.",
  "O endpoint aceita o JSON sem validar assinatura.",
  """<pre>@app.post("/webhook")\ndef hook():\n    data = request.get_json()\n    process(data)\n# tarefa: verificar assinatura</pre>""",
  required=(("assinatura HMAC", r"hmac|hmac\.new|compare_digest|signature"),),
  hints=("Use o corpo bruto da requisição e comparação em tempo constante.",),
  explanation="Sem autenticação do webhook, terceiros podem forjar eventos.",
  solution="Valide assinatura HMAC com segredo fora do código e compare de forma resistente a timing."),
C("file-magic", "Tipo real do arquivo", "upload", "intermediário", 180,
  "Valide o tipo real do arquivo, não apenas o Content-Type enviado.",
  "O upload confia em request.content_type.",
  """<pre>if file.content_type == "image/png":\n    save(file)\n# tarefa: verificar assinatura/conteúdo</pre>""",
  required=(("validação de conteúdo", r"magic|signature|Image\.open|filetype|content"),),
  forbidden=(("não confiar só no MIME", r"content_type\s*=="),),
  hints=("O cliente controla o MIME declarado.",),
  explanation="MIME declarado pode não corresponder aos bytes reais.",
  solution="Valide assinatura/magic bytes e, quando aplicável, reencode imagens/documentos em formato seguro."),
C("zip-slip", "ZIP sem path traversal", "upload", "avançado", 280,
  "Extraia arquivos ZIP sem permitir que nomes escapem do diretório destino.",
  "O extrator usa o nome do membro diretamente.",
  """<pre>for member in zip.namelist():\n    zip.extract(member, DEST)\n# tarefa: confinar cada caminho</pre>""",
  required=(("confinar caminho", r"resolve|commonpath|safe_join|is_relative_to"),),
  forbidden=(("não extrair membro sem validação", r"extract\(member\s*,\s*DEST"),),
  hints=("Membros podem conter ../ ou caminhos absolutos.",),
  explanation="Zip Slip pode sobrescrever arquivos fora do diretório de extração.",
  solution="Resolva cada destino e confirme que permanece dentro do diretório permitido antes de gravar."),
C("logging-encoding", "Log injection", "logs", "intermediário", 160,
  "Normalize entradas antes de colocá-las em logs estruturados.",
  "Um nome de usuário controlado pelo cliente contém quebra de linha.",
  """<pre>logger.info("login user=%s", username)\n# tarefa: log estruturado/normalizado</pre>""",
  required=(("normalização/estrutura", r"json|structured|sanitize|replace|escape"),),
  hints=("Quebras de linha podem forjar eventos visuais no log.",),
  explanation="Entradas não normalizadas podem falsificar linhas de log e atrapalhar investigação.",
  solution="Use logging estruturado e normalize caracteres de controle em campos destinados a texto."),
C("backup-encryption", "Backup sem segredo exposto", "config", "intermediário", 180,
  "Proteja backups que possam conter dados sensíveis.",
  "O backup é salvo em diretório público e sem controle de integridade.",
  """<pre>backup = "/var/www/html/backup.zip"\n# tarefa: local privado + integridade + retenção</pre>""",
  required=(("fora do web root", r"private|outside|backup_dir|/var/backups|not.*public"),("integridade/retenção", r"sha256|checksum|retention|version")),
  hints=("Backup é dado persistente sensível.",),
  explanation="Backup exposto pode vazar dados e também virar um ponto de alteração não detectada.",
  solution="Armazene fora do diretório público, aplique retenção, integridade e criptografia quando o modelo de ameaça exigir."),
C("rate-limit-reset", "Rate limit resistente a reset", "api-insegura", "intermediário", 200,
  "Evite que o cliente contorne o limite apenas trocando um cabeçalho controlável.",
  "O limite usa X-Forwarded-For sem proxy confiável.",
  """<pre>ip = request.headers.get("X-Forwarded-For")\nlimiter.hit(ip)\n# tarefa: usar cadeia de proxy confiável</pre>""",
  required=(("proxy confiável", r"trusted_proxy|proxy_hops|remote_addr"),),
  hints=("Headers de proxy só são confiáveis quando a infraestrutura que os injeta é conhecida.",),
  explanation="Se qualquer cliente puder escolher o IP usado pelo rate limit, pode rotacioná-lo e escapar do limite.",
  solution="Confie em headers de forwarding somente atrás de proxies conhecidos e normalize a origem no backend."),
C("sql-least-privilege", "Banco com menor privilégio", "sqli", "intermediário", 180,
  "Reduza o impacto de uma eventual injeção com privilégios mínimos no banco.",
  "O usuário da aplicação é administrador do banco.",
  """<pre>DB_USER = "root"\n# tarefa: conta dedicada com privilégios mínimos</pre>""",
  required=(("usuário dedicado", r"app_user|least.?privilege|read_only|grant"),),
  forbidden=(("não usar root/admin", r"DB_USER\s*=\s*[\"\'](root|admin)"),),
  hints=("Defesa em profundidade importa mesmo após parametrização.",),
  explanation="Privilégios excessivos aumentam o impacto de falhas no aplicativo.",
  solution="Use uma conta dedicada com somente SELECT/INSERT/UPDATE necessários e permissões específicas por ambiente."),
C("dependency-transitive", "Dependência transitiva", "supply", "intermediário", 180,
  "Audite também dependências transitivas, não apenas as declaradas diretamente.",
  "O pipeline verifica somente requirements.txt linha a linha.",
  """<pre>pip install -r requirements.txt\n# tarefa: auditar árvore completa de dependências</pre>""",
  required=(("árvore transitiva", r"pip-audit|osv|transitive|dependency tree|pipdeptree"),),
  hints=("Uma dependência indireta também pode introduzir CVE.",),
  explanation="Vulnerabilidades frequentemente entram por dependências transitivas.",
  solution="Use um scanner que resolva a árvore de dependências e gere relatório reproduzível."),

C("cors-allowlist", "CORS sem wildcard", "api-insegura", "intermediário", 170,
  "Restrinja origens CORS a domínios confiáveis.", "A API responde Access-Control-Allow-Origin: *.",
  """<pre>Access-Control-Allow-Origin: *\n# tarefa: permitir apenas a origem configurada</pre>""",
  required=(("origem allowlist", r"allowlist|allowed_origins|trusted_origins|configured_origin"),),
  forbidden=(("remover wildcard CORS", r"Allow-Origin:\s*\*"),), hints=("CORS não substitui autorização.",),
  explanation="CORS permissivo pode ampliar a superfície de aplicações que conseguem ler respostas do navegador.",
  solution="Use uma allowlist de origens e nunca trate CORS como mecanismo de autorização."),
C("api-error-leak", "Erro de API sem stack trace", "api-insegura", "iniciante", 120,
  "Retorne erros úteis ao cliente sem revelar detalhes internos.", "A API devolve exception e stack trace diretamente.",
  """<pre>except Exception as exc:\n    return jsonify(error=str(exc), trace=traceback.format_exc()), 500\n# tarefa: resposta genérica + request id</pre>""",
  required=(("erro genérico", r"internal server error|erro interno|generic|request.?id|error_id"),),
  forbidden=(("não devolver stack trace", r"traceback\.format_exc|str\(exc\)"),), hints=("Logs internos podem manter o detalhe.",),
  explanation="Stack traces podem revelar caminhos, bibliotecas, consultas e segredos de configuração.",
  solution="Registre o detalhe no backend e devolva uma mensagem genérica com Request ID."),
C("session-rotation", "Rotação de sessão após login", "cookies", "intermediário", 180,
  "Evite session fixation regenerando o contexto após autenticação.", "A sessão anterior permanece ativa após o login.",
  """<pre>if password_ok:\n    session[\"user\"] = user.id\n# tarefa: invalidar contexto anterior</pre>""",
  required=(("limpar/rotacionar sessão", r"session\.clear|rotate|regenerate|new session"),), hints=("Não carregue privilégios da sessão pré-login.",),
  explanation="Session fixation pode permitir que um identificador conhecido seja reutilizado após autenticação.",
  solution="Invalide o contexto anterior, gere uma nova sessão e só então atribua o usuário autenticado."),
C("csrf-origin", "CSRF com Origin", "csrf", "intermediário", 170,
  "Use Origin/Referer como camada adicional nas operações de estado.", "A aplicação aceita POSTs sem conferir a origem do navegador.",
  """<pre>@app.post(\"/settings\")\ndef settings():\n    update()\n# tarefa: validar CSRF + origem</pre>""",
  required=(("validação de origem", r"Origin|Referer|same.?origin|trusted_origin"),("CSRF", r"csrf|csrf_token|validate_csrf")), hints=("Origin é complementar, não substituto de token CSRF.",),
  explanation="A combinação de token CSRF e validação de origem reduz ataques cross-site em endpoints de alteração.",
  solution="Valide token CSRF no backend e confira Origin/Referer contra a origem esperada."),
C("secret-env", "Secret fora do código", "supply", "iniciante", 120,
  "Remova credenciais fixas do código-fonte.", "Uma API key aparece como literal no arquivo.",
  """<pre>API_KEY = \"sk-exemplo-secreto\"\n# tarefa: carregar de ambiente/secret manager</pre>""",
  required=(("variável de ambiente", r"os\.getenv|environ|secret manager|vault"),),
  forbidden=(("remover literal secreto", r"API_KEY\s*=\s*[\"']sk-"),), hints=("Segredos devem ser injetados no ambiente de execução.",),
  explanation="Secrets no código podem parar em Git, logs, artefatos de build ou forks.",
  solution="Use secret manager/variáveis de ambiente e rotacione qualquer credencial que tenha sido exposta."),
C("dependency-pin", "Dependência reproduzível", "supply", "intermediário", 150,
  "Torne a instalação reproduzível e auditável.", "O projeto instala dependências sem versão ou integridade definida.",
  """<pre>pip install pacote\n# tarefa: fixar as versões e auditar o que foi instalado</pre>""",
  required=(("versão pinada", r"==|lock|requirements|poetry\.lock|uv\.lock"),), hints=("Auditoria exige saber exatamente o que foi instalado.",),
  explanation="Dependências flutuantes dificultam reproduzir builds e investigar mudanças de risco.",
  solution="Pine versões ou use lockfile, e combine com auditoria de vulnerabilidades."),
C("ssrf-ip-literal", "SSRF por IP literal", "ssrf", "avançado", 260,
  "Não permita contornar a política usando IPv4/IPv6 literais.", "A allowlist valida somente nomes de host.",
  """<pre>if urlparse(url).hostname in ALLOWED_HOSTS:\n    fetch(url)\n# tarefa: resolver e validar IP antes da conexão</pre>""",
  required=(("validação de IP", r"ipaddress|is_private|is_loopback|is_link_local|resolved"),), hints=("Hostname não é o mesmo que destino de rede.",),
  explanation="IP literal e IPv6 podem contornar validações que só olham para nomes.",
  solution="Resolva o destino e valide todos os IPs contra loopback, privado, reservado, link-local e metadata."),
C("redirect-ssrf", "Redirect seguro", "redirect", "avançado", 260,
  "Valide cada destino de redirect, não apenas o primeiro URL.", "O cliente fornece uma URL permitida que redireciona para rede interna.",
  """<pre>response = client.get(url, follow_redirects=True)\n# tarefa: validar cada destino</pre>""",
  required=(("validar redirects", r"redirect|history|follow_redirects|next_url"),("SSRF guard", r"ssrf|is_private|allowlist")), hints=("O segundo destino também é um alvo.",),
  explanation="Um redirect externo pode transformar uma URL inicialmente permitida em acesso a um destino bloqueado.",
  solution="Inspecione cada Location e reaplique a política SSRF antes de seguir o redirect."),
C("upload-exec", "Upload sem execução", "upload", "intermediário", 170,
  "Grave uploads em local que não execute scripts.", "Arquivos enviados são salvos diretamente dentro do web root executável.",
  """<pre>path = WEB_ROOT / file.filename\nfile.save(path)\n# tarefa: armazenamento isolado e não executável</pre>""",
  required=(("diretório isolado", r"upload_dir|outside|private|no.?exec|non.?executable"),), hints=("Validação de extensão sozinha não é suficiente.",),
  explanation="Upload executável pode transformar uma falha de arquivo em execução de código.",
  solution="Use nomes aleatórios, validação de conteúdo e diretório fora do web root sem execução."),
C("backup-restore", "Restauração testada", "config", "intermediário", 170,
  "Não trate a existência do backup como prova de recuperabilidade.", "O sistema cria cópias mas nunca testa restauração.",
  """<pre>make_backup()\n# tarefa: verificar integridade e testar restore</pre>""",
  required=(("restore", r"restore|restauração|extract|recover"),("integridade", r"sha256|checksum|manifest")), hints=("Backup sem teste pode falhar quando mais precisar dele.",),
  explanation="Testes de restauração detectam arquivos incompletos, permissões incorretas e formatos inválidos.",
  solution="Valide manifesto, restaure em ambiente isolado e registre o resultado sem expor dados sensíveis."),
C("rbac-backend", "RBAC no backend", "authz", "intermediário", 190,
  "Não dependa apenas de esconder botões para proteger ações administrativas.", "A interface esconde o botão, mas a rota aceita qualquer usuário autenticado.",
  """<pre># frontend esconde /admin\n@app.post(\"/admin/delete\")\ndef delete():\n    remove_item()\n# tarefa: autorização real no backend</pre>""",
  required=(("checagem de papel/capacidade", r"role|permission|cap|authorize|require"),), hints=("O atacante pode chamar a rota diretamente.",),
  explanation="Autorização precisa existir no servidor, independentemente da interface.",
  solution="Aplique uma checagem de papel/capacidade antes da operação sensível."),
    ]
