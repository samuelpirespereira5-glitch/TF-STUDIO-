"""Desafios extras v33 (secure coding, blue team, CTF e resposta a incidentes).

Tudo é texto local: nada é executado nem enviado à rede. Cada desafio é
validado por padrões sobre o texto que a pessoa envia, e cada um tem uma
solução de referência em TEST_SOLUTIONS (usada pelos testes para garantir
que o desafio falha quebrado e passa corrigido).
"""
import base64
import urllib.parse

NEW_CATEGORIES = {
    "jwt": "JWT",
    "nosql": "NoSQL Injection",
    "ssti": "Template Injection (SSTI)",
    "clickjacking": "Clickjacking",
    "log-inject": "Log injection",
    "rate-limit": "Rate limit e força bruta",
    "password-storage": "Armazenamento de senhas",
    "cloud": "Cloud e IaC",
    "phishing": "Phishing e engenharia social",
    "privacy": "Privacidade e LGPD",
    "forense": "Forense básica",
    "input-val": "Validação de entrada",
}

_F_B64 = "TT{base64_nao_e_criptografia}"
_F_HEX = "TT{hex_e_so_formato}"
_F_CESAR = "TT{cesar_nao_protege}"
_F_JWT = "TT{jwt_nao_e_segredo}"
_F_URL = "TT{url_encode_nao_protege}"
_F_SRC = "TT{codigo_fonte_fala}"


def _cesar(s, k=3):
    out = []
    for ch in s:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + k) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + k) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)


def _b64url(obj):
    return base64.urlsafe_b64encode(obj.encode()).decode().rstrip("=")


_JWT = f'{_b64url(chr(123) + chr(34) + "alg" + chr(34) + ":" + chr(34) + "HS256" + chr(34) + chr(125))}.' \
       f'{_b64url("{" + chr(34) + "sub" + chr(34) + ":" + chr(34) + "ana" + chr(34) + "," + chr(34) + "nota" + chr(34) + ":" + chr(34) + _F_JWT + chr(34) + "}")}.assinatura-de-exemplo'

TEST_SOLUTIONS = {
    "jwt-alg-none": 'claims = jwt.decode(token, SECRET, algorithms=["HS256"])',
    "jwt-expiry": 'payload = {"sub": user.id, "exp": datetime.utcnow() + timedelta(minutes=15)}',
    "jwt-secret-hardcoded": 'import os\nkey = os.environ["JWT_KEY"]\ntoken = jwt.encode(p, key)',
    "nosql-operator": 'u, p = request.json["user"], request.json["pass"]\nif not isinstance(u, str) or not isinstance(p, str): abort(400)\ndb.users.find_one({"user": u, "pass": p})',
    "ssti-render-string": 'return render_template("ola.html", name=name)',
    "clickjacking-frame": "X-Frame-Options: DENY\nContent-Security-Policy: frame-ancestors 'none'",
    "log-injection": 'safe = username.replace("\\n", " ").replace("\\r", " ")\nlogger.info("login %s", safe)',
    "rate-limit-login": "if tentativas[ip] >= 5:\n    return 429\nif not check_password(user, pw):\n    tentativas[ip] += 1",
    "password-hash-md5": "from werkzeug.security import generate_password_hash\nh = generate_password_hash(pw)",
    "password-salt": "import bcrypt\nh = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())",
    "iac-open-sg": 'cidr_blocks = ["10.0.0.0/16"]',
    "iac-public-bucket": 'acl = "private"\nblock_public_acls = true',
    "docker-root-user": 'FROM python:3.12\nCOPY . /app\nUSER app\nCMD ["python", "app.py"]',
    "docker-latest-tag": "FROM python:3.12.4-slim\nCOPY . /app",
    "docker-secrets-env": "RUN --mount=type=secret,id=api_key ./build.sh",
    "phishing-email-triage": "classificacao: phishing\nacao: reportar ao suporte e excluir sem clicar",
    "phishing-domain-lookalike": "suspeitos: paypa1.com, pay-pal.secure-login.net",
    "log-bruteforce-ip": "ip: 203.0.113.7\nacao: bloquear o IP e ativar MFA",
    "log-sqli-access": "tipo: SQL injection\ncorrecao: usar consultas parametrizadas (prepared statements)",
    "forense-hash-compare": "integro: nao\nmotivo: os hashes SHA-256 diferem, o arquivo foi alterado",
    "ctf-base64-layers": _F_B64,
    "ctf-hex-flag": _F_HEX,
    "ctf-caesar": _F_CESAR,
    "ctf-jwt-peek": _F_JWT,
    "ctf-url-decode": _F_URL,
    "ctf-flag-in-source": f"flag: {_F_SRC}",
    "cors-wildcard-credentials": 'ALLOWED_ORIGINS = {"https://app.exemplo.com"}\nif origin in ALLOWED_ORIGINS: resp.headers["Access-Control-Allow-Origin"] = origin',
    "idor-file-download": "path = (BASE / name).resolve()\nif not path.is_relative_to(BASE): abort(404)\nreturn send_file(path)",
    "yaml-unsafe-load": "cfg = yaml.safe_load(data)",
    "eval-input": "import ast\nresult = ast.literal_eval(request.args['expr'])",
    "privacy-log-pii": 'logger.info("cpf=%s", mask(user.cpf))',
    "privacy-retention": "purge_older_than(days=90)  # política de retenção",
    "session-fixation": 'session.clear()\nsession["user"] = user.id',
    "secrets-leak-response": "passo 1: revogar e rotacionar a chave agora\npasso 2: limpar o histórico do Git com filter-repo\npasso 3: auditar os logs de uso da chave",
    "incidente-ransomware": "passo 1: isolar as máquinas da rede\npasso 2: preservar evidências e backups offline\npasso 3: comunicar a liderança e o jurídico (LGPD)",
    "incidente-account-takeover": "passo 1: revogar sessões e trocar a senha\npasso 2: ativar MFA na conta\npasso 3: revisar logs e atividade suspeita",
}


def build(_challenge):
    C = _challenge
    return [

C("jwt-alg-none", "JWT sem verificação", "jwt", "avançado", 250,
  "Faça o servidor aceitar só tokens com assinatura verificada e algoritmo fixo.",
  "O token é decodificado sem conferir a assinatura: qualquer um forja um JWT.",
  """<!doctype html><h1>JWT Lab</h1><pre>
claims = jwt.decode(token, options={"verify_signature": False})
# tarefa: aceitar somente tokens realmente assinados
</pre>""",
  required=(("lista fixa de algoritmos", r"algorithms\s*=\s*\["),),
  forbidden=(("não desligar a verificação", r"verify_signature[\"']?\s*:\s*false"),),
  hints=("Nunca deixe o token escolher o algoritmo.", "Passe a chave e a lista de algoritmos permitidos."),
  explanation="Sem verificar a assinatura (ou aceitando alg=none), o atacante edita o payload e vira admin.",
  solution="jwt.decode(token, SECRET, algorithms=[\"HS256\"])"),

C("jwt-expiry", "JWT que nunca expira", "jwt", "intermediário", 180,
  "Dê validade curta ao token para limitar o estrago se ele vazar.",
  "O payload não tem data de expiração: o token vale para sempre.",
  """<pre>
payload = {"sub": user.id}
token = jwt.encode(payload, KEY, algorithm="HS256")
# tarefa: limitar por quanto tempo este token serve
</pre>""",
  required=(("campo de validade", r"[\"']exp[\"']\s*:"), ("tempo curto", r"timedelta|utcnow|time\.time|minutes|seconds")),
  hints=("A claim padrão chama-se exp.", "Minutos, não meses."),
  explanation="Tokens eternos tornam qualquer vazamento permanente.",
  solution="Inclua \"exp\": agora + timedelta(minutes=15) e valide no servidor."),

C("jwt-secret-hardcoded", "Segredo do JWT no código", "jwt", "iniciante", 120,
  "Tire o segredo do código-fonte.",
  "A chave de assinatura está escrita direto no arquivo (e vai para o Git).",
  """<pre>
SECRET = "123456"
token = jwt.encode(payload, SECRET, algorithm="HS256")
# tarefa: ler a chave de fora do código
</pre>""",
  required=(("ler de ambiente/cofre", r"os\.environ|os\.getenv|getenv|secret_manager|vault"),),
  forbidden=(("sem segredo literal", r"secret\s*=\s*[\"'][^\"']+[\"']"),),
  hints=("Variáveis de ambiente ou um cofre de segredos.",),
  explanation="Segredos no código vazam com o repositório e são difíceis de rotacionar.",
  solution="key = os.environ[\"JWT_KEY\"]"),

C("nosql-operator", "Injeção de operador NoSQL", "nosql", "avançado", 240,
  "Impeça que o usuário mande um objeto no lugar de um texto.",
  "Se alguém enviar {\"$ne\": null} como senha, a consulta passa sem a senha correta.",
  """<pre>
@app.post("/login")
def login():
    return db.users.find_one({"user": request.json["user"], "pass": request.json["pass"]})
# tarefa: garantir que os campos sejam apenas texto simples
</pre>""",
  required=(("checar o tipo", r"isinstance\(|type\(|str\(|schema|validate"),),
  hints=("O JSON pode trazer objetos, não só texto.",),
  explanation="Operadores como $ne/$gt em campos de login burlam a checagem de senha.",
  solution="Valide com isinstance(valor, str) antes de consultar (ou use um schema)."),

C("ssti-render-string", "Template montado com entrada", "ssti", "avançado", 260,
  "Nunca concatene entrada do usuário dentro do texto do template.",
  "O texto do template inclui o nome recebido: {{ ... }} digitado pelo usuário é executado.",
  """<pre>
@app.get("/ola")
def ola():
    name = request.args.get("name", "")
    return render_template_string("Olá " + name)
# tarefa: usar um template fixo e passar o valor como variável
</pre>""",
  required=(("template fixo", r"render_template\(|escape\(|\|\s*e\b"),),
  forbidden=(("sem concatenar no template", r"render_template_string\(\s*[\"'][^\"']*[\"']\s*\+"),),
  hints=("O template deve ser constante.", "O valor entra como variável."),
  explanation="SSTI pode levar a execução de código no servidor.",
  solution="render_template(\"ola.html\", name=name)"),

C("clickjacking-frame", "Página que pode ser emoldurada", "clickjacking", "iniciante", 120,
  "Impeça que outro site exiba sua página dentro de um iframe.",
  "A resposta não tem nenhuma proteção contra clickjacking.",
  """<pre>
HTTP/1.1 200 OK
Content-Type: text/html
# tarefa: impedir que outro site exiba esta página dentro de um iframe
</pre>""",
  required=(("proteção de moldura", r"x-frame-options|frame-ancestors"),),
  hints=("Há um cabeçalho clássico e uma diretiva moderna de CSP.",),
  explanation="Atacantes sobrepõem um iframe invisível para induzir cliques.",
  solution="X-Frame-Options: DENY e/ou CSP frame-ancestors 'none'."),

C("log-injection", "Log forjado por quebra de linha", "log-inject", "intermediário", 170,
  "Impeça que o usuário crie linhas falsas no log.",
  "O nome de usuário vai direto para o log: dá para inserir uma linha 'login ok' falsa.",
  """<pre>
logger.info("login " + username)
# tarefa: impedir que quebras de linha do usuário forjem linhas de log
</pre>""",
  required=(("neutralizar quebras", r"replace\(|sanitize|repr\(|!r|%r|escape|strip\("),),
  forbidden=(("sem concatenar entrada", r"info\(\s*[\"'][^\"']*[\"']\s*\+\s*username"),),
  hints=("Remova \\n e \\r, ou registre com repr().",),
  explanation="Log injection esconde ataques e confunde investigações.",
  solution="Neutralize \\n/\\r e use logger.info(\"login %s\", valor_seguro)."),

C("rate-limit-login", "Login sem freio", "rate-limit", "intermediário", 180,
  "Adicione um freio para quem testa muitas senhas seguidas.",
  "Qualquer pessoa pode tentar milhares de senhas por minuto.",
  """<pre>
@app.post("/login")
def login():
    if check_password(user, pw):
        return ok()
    return erro()
# tarefa: frear quem testa muitas senhas seguidas
</pre>""",
  required=(("contador/limite", r"rate|limit|throttle|lockout|attempts|tentativas|429"),),
  hints=("Conte falhas por IP e/ou por conta.", "Retorne 429 ou bloqueie por um tempo."),
  explanation="Sem limite, força bruta e credential stuffing ficam baratos.",
  solution="Conte falhas, bloqueie após N tentativas e retorne 429."),

C("password-hash-md5", "Senha guardada com MD5", "password-storage", "iniciante", 130,
  "Troque o hash rápido por um algoritmo próprio para senhas.",
  "MD5 é rápido demais: um vazamento vira senhas em claro em minutos.",
  """<pre>
import hashlib
stored = hashlib.md5(pw.encode()).hexdigest()
# tarefa: guardar a senha de um jeito que resista a um vazamento do banco
</pre>""",
  required=(("hash de senha adequado", r"bcrypt|argon2|scrypt|pbkdf2|generate_password_hash"),),
  forbidden=(("sem MD5/SHA-1", r"md5|sha1"),),
  hints=("Procure algoritmos lentos e com sal embutido.",),
  explanation="Hashes rápidos permitem bilhões de tentativas por segundo.",
  solution="Use bcrypt, scrypt, argon2 ou generate_password_hash."),

C("password-salt", "Hash sem sal", "password-storage", "intermediário", 160,
  "Use sal único e um KDF, não um SHA simples.",
  "O mesmo hash SHA-256 sem sal entrega quem tem a mesma senha e facilita tabelas prontas.",
  """<pre>
digest = hashlib.sha256(pw.encode()).hexdigest()
# tarefa: tornar cada hash único e caro de calcular
</pre>""",
  required=(("KDF com sal", r"bcrypt|argon2|scrypt|pbkdf2|salt|gensalt|urandom"),),
  forbidden=(("sem SHA puro em senha", r"sha256\(\s*pw"),),
  hints=("Sal é aleatório e diferente por usuário.",),
  explanation="Sem sal, senhas iguais geram hashes iguais e rainbow tables funcionam.",
  solution="bcrypt.hashpw(pw, bcrypt.gensalt()) ou scrypt/argon2 com sal."),

C("iac-open-sg", "Porta SSH aberta para o mundo", "cloud", "intermediário", 200,
  "Restrinja a origem do acesso administrativo.",
  "O grupo de segurança libera a porta 22 para qualquer IP da internet.",
  """<pre>
resource "aws_security_group_rule" "ssh" {
  from_port   = 22
  to_port     = 22
  cidr_blocks = ["0.0.0.0/0"]
}
# tarefa: limitar quem pode chegar nesta porta
</pre>""",
  required=(("rede restrita", r"cidr_blocks\s*=\s*\[\s*[\"'](10\.|172\.|192\.168\.|\d+\.\d+\.\d+\.\d+/(2[4-9]|3[0-2]))"),),
  forbidden=(("sem 0.0.0.0/0", r"0\.0\.0\.0/0"),),
  hints=("Use a rede da empresa, uma VPN ou um bastion.",),
  explanation="Portas administrativas expostas recebem ataques automáticos o tempo todo.",
  solution="cidr_blocks = [\"10.0.0.0/16\"] (ou o IP fixo da VPN)."),

C("iac-public-bucket", "Bucket público", "cloud", "intermediário", 190,
  "Deixe o armazenamento privado por padrão.",
  "O bucket está com ACL pública: qualquer pessoa lê os arquivos.",
  """<pre>
resource "aws_s3_bucket_acl" "dados" {
  acl = "public-read"
}
# tarefa: tornar o acesso restrito
</pre>""",
  required=(("acesso privado", r"acl\s*=\s*[\"']private[\"']|block_public_acls\s*=\s*true"),),
  forbidden=(("sem public-read", r"public-read"),),
  hints=("Existe um bloco de 'bloquear acesso público'.",),
  explanation="Buckets públicos são uma das maiores fontes de vazamento em nuvem.",
  solution="acl = \"private\" e block_public_acls = true."),

C("docker-root-user", "Container rodando como root", "docker", "iniciante", 140,
  "Rode a aplicação com um usuário sem privilégios.",
  "O processo roda como administrador dentro do container.",
  """<pre>
FROM python:3.12
COPY . /app
CMD ["python", "app.py"]
# tarefa: não rodar o processo como administrador do container
</pre>""",
  required=(("usuário comum", r"(?m)^\s*user\s+(?!root\b)\w+"),),
  hints=("Crie um usuário e use a instrução USER.",),
  explanation="Se o app for invadido, root no container facilita escapar para o host.",
  solution="Adicione USER app (criado antes) antes do CMD."),

C("docker-latest-tag", "Imagem com tag latest", "docker", "iniciante", 110,
  "Fixe a versão da imagem base.",
  "A tag 'latest' muda sem aviso e quebra builds ou traz vulnerabilidades novas.",
  """<pre>
FROM python:latest
COPY . /app
# tarefa: deixar o build reproduzível
</pre>""",
  required=(("versão fixa", r"from\s+[\w./-]+:\d"),),
  forbidden=(("sem latest", r":latest"),),
  hints=("Use número de versão (e, melhor ainda, digest).",),
  explanation="Builds reproduzíveis facilitam auditoria e reversão.",
  solution="FROM python:3.12.4-slim"),

C("docker-secrets-env", "Segredo dentro da imagem", "docker", "intermediário", 170,
  "Não grave segredos em ENV na imagem.",
  "A chave fica no histórico da imagem e vaza para quem puxar a imagem.",
  """<pre>
FROM python:3.12-slim
ENV API_KEY=abc123
COPY . /app
# tarefa: entregar o segredo sem gravá-lo na imagem
</pre>""",
  required=(("segredo em tempo de build/execução", r"--mount=type=secret|docker secret|secrets:|run/secrets"),),
  forbidden=(("sem ENV com segredo", r"(?m)^\s*env\s+\w*(key|token|password|secret)\w*\s*=\s*\S+"),),
  hints=("BuildKit tem montagem de segredos; em runtime, o orquestrador injeta.",),
  explanation="Camadas de imagem guardam tudo que foi escrito nelas.",
  solution="Remova o ENV e use --mount=type=secret ou docker secret."),

C("phishing-email-triage", "Este e-mail é seguro?", "phishing", "iniciante", 120,
  "Classifique o e-mail e diga o que fazer.",
  "Leia a mensagem e preencha as duas linhas de resposta.",
  """<pre>
De: suporte@banc0-seguro.example
Assunto: URGENTE - sua conta será suspensa em 2 horas

Prezado cliente, detectamos acesso estranho. Confirme seus dados
agora em http://banc0-seguro.example/validar ou perderá o acesso.

classificacao:
acao:
</pre>""",
  required=(("classificação", r"(?m)^classifica[cç][aã]o:\s*.*(phishing|golpe|fraude)"),
            ("ação segura", r"(?m)^a[cç][aã]o:\s*.*(reportar|denunciar|excluir|apagar|n[aã]o clic)")),
  hints=("Urgência, erro no domínio e link suspeito são sinais clássicos.",),
  explanation="Phishing explora pressa e medo. O certo é não clicar e avisar o time de segurança.",
  solution="classificacao: phishing / acao: reportar e excluir sem clicar."),

C("phishing-domain-lookalike", "Qual domínio é falso?", "phishing", "intermediário", 150,
  "Aponte os domínios que imitam o PayPal.",
  "Três endereços chegaram por e-mail. Só um é o verdadeiro.",
  """<pre>
1) paypal.com
2) paypa1.com
3) pay-pal.secure-login.net

suspeitos:
</pre>""",
  required=(("domínio com número no lugar de letra", r"(?m)^suspeitos:.*paypa1"),
            ("domínio com subdomínio enganoso", r"(?m)^suspeitos:.*secure-login")),
  hints=("Olhe o que vem imediatamente antes do último ponto.", "Troque letras por números é um truque comum."),
  explanation="Domínios parecidos (typosquatting) enganam leitura rápida.",
  solution="suspeitos: paypa1.com, pay-pal.secure-login.net"),

C("log-bruteforce-ip", "Quem está atacando o login?", "logs", "iniciante", 130,
  "Identifique o IP suspeito e defina a resposta.",
  "O log mostra muitas falhas de login em sequência.",
  """<pre>
10:01 FAIL user=admin src=203.0.113.7
10:01 FAIL user=admin src=203.0.113.7
10:01 FAIL user=root  src=203.0.113.7
10:02 FAIL user=ana   src=203.0.113.7
10:05 OK   user=ana   src=198.51.100.20

ip:
acao:
</pre>""",
  required=(("IP correto", r"(?m)^ip:\s*203\.0\.113\.7"),
            ("ação defensiva", r"(?m)^a[cç][aã]o:\s*.*(bloque|fail2ban|rate|mfa|limit)")),
  hints=("Conte as falhas por origem.",),
  explanation="Várias falhas em poucos segundos vindas do mesmo IP indicam força bruta.",
  solution="ip: 203.0.113.7 / acao: bloquear o IP e ativar MFA."),

C("log-sqli-access", "Ataque escondido no access log", "logs", "intermediário", 180,
  "Reconheça o tipo de ataque e diga como corrigir.",
  "Uma das linhas do log de acesso tem uma requisição estranha.",
  """<pre>
GET /produtos?id=7 200
GET /produtos?id=7'%20OR%201=1-- 500
GET /carrinho 200

tipo:
correcao:
</pre>""",
  required=(("tipo do ataque", r"(?m)^tipo:\s*.*(sql|inje)"),
            ("correção", r"(?m)^corre[cç][aã]o:\s*.*(parametr|prepared|orm|bind)")),
  hints=("Olhe o que vem depois do id.",),
  explanation="Aspas e 'OR 1=1' são a assinatura clássica de SQL injection.",
  solution="tipo: SQL injection / correcao: consultas parametrizadas."),

C("forense-hash-compare", "O arquivo foi adulterado?", "forense", "iniciante", 120,
  "Compare os hashes e conclua sobre a integridade.",
  "Você tem o hash de quando o arquivo foi recebido e o de agora.",
  """<pre>
recebido: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
agora:    60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c4b3b59

integro:
motivo:
</pre>""",
  required=(("conclusão correta", r"(?m)^integro:\s*(n[aã]o|false|no)\b"),
            ("justificativa", r"(?m)^motivo:\s*.*(hash|diferen|alter)")),
  hints=("Hashes iguais = mesmo conteúdo. Diferentes = algo mudou.",),
  explanation="Qualquer alteração de 1 bit muda o hash por completo.",
  solution="integro: nao / motivo: os hashes diferem."),

C("ctf-base64-layers", "CTF: Base64 não é segredo", "ctf", "iniciante", 100,
  "Decodifique e envie a flag na forma TT{...}.",
  "Uma mensagem foi 'escondida' com Base64.",
  f"<pre>\n{base64.b64encode(_F_B64.encode()).decode()}\n\nenvie a flag decodificada abaixo:\n</pre>",
  required=(("flag correta", r"tt\{base64_nao_e_criptografia\}"),),
  hints=("Base64 é só um formato, qualquer um decodifica.",),
  explanation="Codificar não é criptografar.",
  solution=_F_B64),

C("ctf-hex-flag", "CTF: Hex", "ctf", "iniciante", 100,
  "Converta de hexadecimal para texto e envie a flag.",
  "A flag está escrita em bytes hexadecimais.",
  f"<pre>\n{_F_HEX.encode().hex()}\n\nenvie a flag decodificada abaixo:\n</pre>",
  required=(("flag correta", r"tt\{hex_e_so_formato\}"),),
  hints=("Cada par de dígitos é um byte ASCII.",),
  explanation="Hex é apenas outra forma de escrever bytes.",
  solution=_F_HEX),

C("ctf-caesar", "CTF: Cifra de César", "ctf", "iniciante", 120,
  "Desfaça o deslocamento de 3 letras.",
  "Uma cifra antiga de mais de 2 mil anos.",
  f"<pre>\n{_cesar(_F_CESAR)}\n\ndeslocamento usado: 3\nenvie a flag decodificada abaixo:\n</pre>",
  required=(("flag correta", r"tt\{cesar_nao_protege\}"),),
  hints=("Volte 3 letras no alfabeto.",),
  explanation="Só 25 chaves possíveis: quebra-se por força bruta em segundos.",
  solution=_F_CESAR),

C("ctf-jwt-peek", "CTF: Espie o JWT", "ctf", "intermediário", 160,
  "Leia o payload do token e envie a flag.",
  "O payload do JWT é apenas Base64URL — não é sigiloso.",
  f"<pre>\n{_JWT}\n\nenvie a flag encontrada abaixo:\n</pre>",
  required=(("flag correta", r"tt\{jwt_nao_e_segredo\}"),),
  hints=("Um JWT tem três partes separadas por ponto; decodifique a do meio.",),
  explanation="Assinatura garante integridade, não confidencialidade.",
  solution=_F_JWT),

C("ctf-url-decode", "CTF: URL encode", "ctf", "iniciante", 100,
  "Decodifique a URL e envie a flag.",
  "A flag foi percent-encoded.",
  f"<pre>\n{urllib.parse.quote(_F_URL, safe='')}\n\nenvie a flag decodificada abaixo:\n</pre>",
  required=(("flag correta", r"tt\{url_encode_nao_protege\}"),),
  hints=("%7B = { e %7D = }",),
  explanation="Percent-encoding existe para transportar caracteres, não para esconder.",
  solution=_F_URL),

C("ctf-flag-in-source", "CTF: Olhe o código-fonte", "ctf", "iniciante", 100,
  "Encontre a flag escondida e escreva 'flag: ...' no fim.",
  "Nem tudo que está na página aparece na tela.",
  f"""<!doctype html><h1>Página comum</h1>
<!-- {_F_SRC} -->
<p>Nada de interessante aqui.</p>
<pre>
flag:
</pre>""",
  required=(("flag correta", r"(?m)^flag:\s*tt\{codigo_fonte_fala\}"),),
  hints=("Comentários HTML não aparecem no navegador.",),
  explanation="Nunca deixe segredos em comentários de código entregue ao cliente.",
  solution=f"flag: {_F_SRC}"),

C("cors-wildcard-credentials", "CORS aberto demais", "cors", "intermediário", 190,
  "Permita só origens conhecidas.",
  "A API aceita qualquer site e ainda envia cookies.",
  """<pre>
resp.headers["Access-Control-Allow-Origin"] = "*"
resp.headers["Access-Control-Allow-Credentials"] = "true"
# tarefa: aceitar apenas os sites que você conhece
</pre>""",
  required=(("lista de origens permitidas", r"allowed_origins|allowlist|origin\s+in\b"),),
  forbidden=(("sem curinga", r"allow-origin[\"']?\]?\s*[:,=]\s*[\"']?\*"),),
  hints=("Compare a origem recebida com uma lista fixa e devolva a própria origem.",),
  explanation="Curinga + credenciais deixa qualquer site ler respostas autenticadas.",
  solution="Valide Origin contra ALLOWED_ORIGINS e devolva só a origem aprovada."),

C("idor-file-download", "Download que vaza arquivos", "idor-bola", "intermediário", 190,
  "Garanta que o arquivo pedido está dentro da pasta permitida.",
  "O nome do arquivo vem da URL sem nenhuma checagem.",
  """<pre>
@app.get("/baixar")
def baixar():
    return send_file(f"/data/{request.args['arquivo']}")
# tarefa: só servir arquivos da pasta permitida
</pre>""",
  required=(("caminho resolvido/seguro", r"secure_filename|realpath|resolve\(\)|is_relative_to|commonpath"),),
  forbidden=(("sem caminho direto do usuário", r"send_file\(\s*f?[\"']/data/"),),
  hints=("Resolva o caminho final e compare com a pasta base.",),
  explanation="../ na entrada deixa ler qualquer arquivo do servidor.",
  solution="Resolva o caminho, confira is_relative_to(BASE) e só então envie."),

C("yaml-unsafe-load", "YAML que executa código", "deserial", "intermediário", 170,
  "Use o carregador seguro do YAML.",
  "yaml.load com dados não confiáveis pode instanciar objetos arbitrários.",
  """<pre>
import yaml
cfg = yaml.load(request.data)
# tarefa: ler o YAML sem permitir objetos arbitrários
</pre>""",
  required=(("carregador seguro", r"safe_load"),),
  forbidden=(("sem yaml.load", r"yaml\.load\("),),
  hints=("O nome do método seguro tem 'safe'.",),
  explanation="Tags especiais do YAML permitem execução de código em loaders inseguros.",
  solution="yaml.safe_load(data)"),

C("eval-input", "eval em entrada do usuário", "input-val", "intermediário", 180,
  "Troque o eval por uma interpretação segura.",
  "O endpoint executa como código o que o usuário digitar.",
  """<pre>
@app.get("/calc")
def calc():
    return str(eval(request.args["expr"]))
# tarefa: aceitar só valores literais
</pre>""",
  required=(("alternativa segura", r"ast\.literal_eval|int\(|float\(|decimal|parser"),),
  forbidden=(("sem eval", r"\beval\("),),
  hints=("literal_eval só aceita literais.",),
  explanation="eval com entrada do usuário é execução remota de código.",
  solution="ast.literal_eval(...) ou converta com int()/float() e valide."),

C("privacy-log-pii", "Dados pessoais no log", "privacy", "intermediário", 160,
  "Não registre CPF e cartão completos.",
  "Os logs guardam dados pessoais em claro, e logs costumam ser copiados por todo lado.",
  """<pre>
logger.info(f"cpf={user.cpf} cartao={card}")
# tarefa: registrar sem expor os dados completos
</pre>""",
  required=(("mascarar/omitir", r"mask|redact|\[-4:\]|\[:4\]|\*{3}|hash|anonim"),),
  forbidden=(("sem dados completos", r"\{user\.cpf\}|\{card\}"),),
  hints=("Guarde só o fim do número, ou nada.",),
  explanation="A LGPD exige minimizar dados pessoais; logs viram vazamentos.",
  solution="Mascare (ex.: últimos 4 dígitos) ou não registre."),

C("privacy-retention", "Dados guardados para sempre", "privacy", "avançado", 210,
  "Defina por quanto tempo os dados ficam e apague depois.",
  "Nada é apagado nunca — o banco só cresce e o risco também.",
  """<pre>
def salvar_cliente(d):
    db.insert(d)
# tarefa: definir um prazo e uma rotina para remover dados antigos
</pre>""",
  required=(("política de prazo", r"retention|reten[cç][aã]o|purge|expire|ttl|delete|apagar|older_than"),),
  hints=("Pense em uma tarefa agendada que remove o que passou do prazo.",),
  explanation="Guardar menos e por menos tempo reduz o impacto de qualquer vazamento.",
  solution="Defina o prazo (ex.: 90 dias) e rode uma rotina de expurgo."),

C("session-fixation", "Sessão que não muda no login", "sessao", "intermediário", 190,
  "Gere uma sessão nova depois de autenticar.",
  "O ID da sessão antes e depois do login é o mesmo: pode ter sido plantado por um atacante.",
  """<pre>
def login():
    if check_password(user, pw):
        session["user"] = user.id
# tarefa: renovar a sessão no momento do login
</pre>""",
  required=(("renovar sessão", r"session\.clear\(|regenerate|rotate|new_session|session\.new|cycle_key"),),
  hints=("Limpe a sessão antiga antes de gravar o usuário.",),
  explanation="Fixação de sessão permite assumir a conta de quem logar depois.",
  solution="session.clear() (ou regenerar o ID) antes de session[\"user\"] = ..."),

C("secrets-leak-response", "Chave vazou no GitHub", "incidente", "intermediário", 200,
  "Escreva os 3 primeiros passos da resposta.",
  "Uma chave de API foi commitada em um repositório público.",
  """<pre>
Situação: chave de produção apareceu no histórico do Git.

passo 1:
passo 2:
passo 3:
</pre>""",
  required=(("passo 1: revogar", r"(?m)^passo\s*1:.*(revog|rotacion|invalid|troc)"),
            ("passo 2: limpar histórico", r"(?m)^passo\s*2:.*(hist|filter-repo|bfg|limp|remov)"),
            ("passo 3: auditar", r"(?m)^passo\s*3:.*(audit|log|uso|monitor|investig)")),
  hints=("Primeiro invalide a chave, só depois limpe.",),
  explanation="Apagar o commit não basta: a chave precisa ser considerada comprometida.",
  solution="1) revogar/rotacionar, 2) limpar histórico, 3) auditar o uso."),

C("incidente-ransomware", "Máquinas criptografadas", "incidente", "avançado", 260,
  "Escreva os primeiros passos de contenção.",
  "Vários computadores mostram arquivos bloqueados e um pedido de resgate.",
  """<pre>
Situação: arquivos com extensão estranha e bilhete de resgate na tela.

passo 1:
passo 2:
passo 3:
</pre>""",
  required=(("passo 1: isolar", r"(?m)^passo\s*1:.*(isol|desconect)"),
            ("passo 2: preservar", r"(?m)^passo\s*2:.*(backup|preserv|evid|imagem)"),
            ("passo 3: comunicar", r"(?m)^passo\s*3:.*(comunic|notific|lgpd|respons|lider|jur)")),
  hints=("Conter antes de investigar.", "Não pague sem avaliar; preserve evidências."),
  explanation="Isolar evita a propagação; evidências e comunicação correta vêm em seguida.",
  solution="1) isolar, 2) preservar evidências/backups, 3) comunicar."),

C("incidente-account-takeover", "Conta invadida", "incidente", "intermediário", 200,
  "Escreva os passos para recuperar uma conta comprometida.",
  "Um usuário relata e-mails que ele não enviou.",
  """<pre>
Situação: login de outro país e mensagens enviadas pela conta.

passo 1:
passo 2:
passo 3:
</pre>""",
  required=(("passo 1: cortar acesso", r"(?m)^passo\s*1:.*(revog|sess|senha|troc|desconect)"),
            ("passo 2: MFA", r"(?m)^passo\s*2:.*(mfa|2fa|dois fatores|autentica)"),
            ("passo 3: revisar", r"(?m)^passo\s*3:.*(log|revis|audit|regra|atividade)")),
  hints=("Derrube quem está dentro e feche a porta.",),
  explanation="Revogar sessões + MFA + revisão de regras/atividade cobre o essencial.",
  solution="1) revogar sessões e trocar senha, 2) MFA, 3) revisar atividade."),

    ]
