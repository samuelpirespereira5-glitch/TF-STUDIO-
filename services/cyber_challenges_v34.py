"""Parte 3 — desafios cyber adicionais (Fácil → Expert) + conquistas.

Laboratórios isolados (texto/HTML). Sem rede, sem payloads reais contra terceiros.
"""
from __future__ import annotations

NEW_CATEGORIES = {
    "tls-lab": "TLS / Certificados",
    "api-lab": "API Security Lab",
    "forense-lab": "Forense Lab",
    "supply-chain": "Supply Chain",
    "zero-trust": "Zero Trust / Segmentação",
}


def build(C):
    """C é a factory _challenge(cid, title, category, difficulty, xp, objective, description, html, ...)."""
    out = []

    out.append(C(
        "headers-expert-csp", "CSP à prova de XSS", "headers", "avançado", 350,
        "Complete a CSP do laboratório bloqueando scripts inline e hosts não confiáveis.",
        "A página ainda permite script inline e CDN arbitrária.",
        """<!doctype html><html><head>
<meta http-equiv="Content-Security-Policy" content="default-src *">
</head><body>
<h1>CSP Lab</h1>
<script>alert('inline')</script>
<p>Defina CSP com default-src 'self'; script-src 'self'; object-src 'none'.</p>
</body></html>""",
        required=(
            ("default-src self", r"default-src[^;]*'self'"),
            ("script-src self", r"script-src[^;]*'self'"),
            ("object-src none", r"object-src[^;]*'none'"),
        ),
        forbidden=(("default-src *", r"default-src\s+\*"),),
        hints=("CSP restritiva reduz XSS mesmo se houver falhas pontuais.", "Evite default-src *."),
        explanation="Content-Security-Policy é defesa em profundidade contra XSS e inclusão de recursos não confiáveis.",
        solution="default-src 'self'; script-src 'self'; object-src 'none' (e refine conforme o app).",
    ))

    out.append(C(
        "jwt-none-algo", "JWT com alg none", "api-insegura", "intermediário", 220,
        "Identifique e documente o risco de aceitar alg=none em JWT.",
        "O laboratório aceita tokens sem assinatura.",
        """<!doctype html><pre>
# Validador inseguro (lab)
def verify(token):
    header, payload, sig = token.split('.')
    # BUG: não verifica assinatura se alg == none
    if header_alg(header) == "none":
        return decode(payload)
    return verify_sig(token)

# Tarefa: reescreva verify para SEMPRE exigir algoritmo e assinatura válidos.
# Escreva: reject_none_alg = true
</pre>""",
        required=(("rejeitar alg none", r"reject_none_alg\s*=\s*true"),),
        hints=("RFC proíbe alg=none em contextos autenticados.",),
        explanation="Aceitar alg=none permite forjar tokens. Sempre valide algoritmo permitido e assinatura.",
        solution="reject_none_alg = true e lista fixa de algoritmos (ex.: RS256, ES256).",
    ))

    out.append(C(
        "log-bruteforce-expert", "Detectar força bruta", "logs", "avançado", 320,
        "A partir do log, marque a origem suspeita e a conta alvo.",
        "Vários 401 da mesma origem em pouco tempo.",
        """<!doctype html><pre>
2026-01-10T10:00:01Z src=203.0.113.50 user=alice status=401
2026-01-10T10:00:02Z src=203.0.113.50 user=alice status=401
2026-01-10T10:00:03Z src=203.0.113.50 user=alice status=401
2026-01-10T10:00:04Z src=203.0.113.50 user=alice status=401
2026-01-10T10:00:05Z src=198.51.100.9 user=bob status=200
# Preencha:
# suspect_ip=
# target_user=
# action=rate_limit_or_block
</pre>""",
        required=(
            ("IP suspeito", r"suspect_ip\s*=\s*203\.0\.113\.50"),
            ("usuário alvo", r"target_user\s*=\s*alice"),
            ("ação", r"action\s*=\s*rate_limit_or_block"),
        ),
        hints=("Procure muitos 401 seguidos da mesma origem.",),
        explanation="Padrão clássico de password spraying/brute force. Rate limit + alerta + MFA.",
        solution="suspect_ip=203.0.113.50 target_user=alice action=rate_limit_or_block",
    ))

    out.append(C(
        "ssrf-lab-metadata", "SSRF e metadata", "config", "avançado", 360,
        "Bloqueie no laboratório o acesso a 169.254.169.254 e link-local.",
        "A função fetch_url não valida o destino.",
        """<!doctype html><pre>
def fetch_url(url):
    # inseguro: qualquer URL
    return requests.get(url).text

# Tarefa: adicione as linhas de política:
# block_metadata = true
# block_private = true
# allowlist_only = true
</pre>""",
        required=(
            ("block metadata", r"block_metadata\s*=\s*true"),
            ("block private", r"block_private\s*=\s*true"),
            ("allowlist", r"allowlist_only\s*=\s*true"),
        ),
        hints=("Metadata AWS/GCP usa 169.254.169.254.", "SSRF Guard resolve e fixa IP."),
        explanation="SSRF pode expor metadata de nuvem e redes internas. Allowlist + bloqueio de faixas especiais.",
        solution="block_metadata=true; block_private=true; allowlist_only=true",
    ))

    out.append(C(
        "tls-weak-ciphers", "TLS fraco", "tls-lab", "intermediário", 200,
        "Remova protocolos legados da config de exemplo.",
        "ssl_protocols inclui TLSv1.",
        """<!doctype html><pre>
# nginx lab
ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
# Corrija para apenas TLSv1.2 e TLSv1.3
</pre>""",
        required=(("só 1.2 e 1.3", r"ssl_protocols\s+TLSv1\.2\s+TLSv1\.3"),),
        forbidden=(("sem TLSv1 nu", r"ssl_protocols\s+TLSv1\s"),),
        hints=("TLS 1.0/1.1 estão deprecados.",),
        explanation="Protocolos legados têm vulnerabilidades conhecidas. Use TLS 1.2+.",
        solution="ssl_protocols TLSv1.2 TLSv1.3;",
    ))

    out.append(C(
        "secrets-env-not-code", "Secret no código", "secrets", "fácil", 80,
        "Mova o secret para variável de ambiente no laboratório.",
        "API key hardcoded.",
        """<!doctype html><pre>
API_KEY = "sk_live_example_do_not_use"
# Substitua por:
# API_KEY = os.environ["API_KEY"]
</pre>""",
        required=(("environ", r"os\.environ\s*\[\s*[\"']API_KEY[\"']\s*\]"),),
        forbidden=(("hardcoded sk", r"sk_live_"),),
        hints=("Segredos não devem ir para o repositório.",),
        explanation="Hardcoded secrets vazam em git, logs e backups.",
        solution='API_KEY = os.environ["API_KEY"]',
    ))

    out.append(C(
        "idor-fix-order", "IDOR em pedido", "idor-bola", "intermediário", 210,
        "Garanta que o usuário só altere o próprio pedido.",
        "update_order usa order_id do cliente sem checar dono.",
        """<!doctype html><pre>
def update_order(user, order_id, data):
    order = db.get(order_id)  # sem checar dono
    order.update(data)
    return order

# Adicione a checagem:
# assert order.owner_id == user.id
</pre>""",
        required=(("checagem de dono", r"order\.owner_id\s*==\s*user\.id"),),
        hints=("BOLA/IDOR: sempre amarre o objeto ao sujeito autenticado.",),
        explanation="Sem verificação de propriedade, qualquer ID pode ser manipulado.",
        solution="assert order.owner_id == user.id (ou equivalente no ORM).",
    ))

    out.append(C(
        "forense-hash-chain", "Cadeia de custódia", "forense-lab", "avançado", 300,
        "Preencha hash e integridade da evidência no lab.",
        "Evidência precisa de SHA-256 e registro de custódia.",
        """<!doctype html><pre>
evidence_file = sample.bin
# sha256_evidence = (calcule mentalmente: use o placeholder abaixo)
# No lab, escreva:
# sha256_evidence = verified
# custody_log = append_only
# original_preserved = true
</pre>""",
        required=(
            ("hash verificado", r"sha256_evidence\s*=\s*verified"),
            ("custódia", r"custody_log\s*=\s*append_only"),
            ("original", r"original_preserved\s*=\s*true"),
        ),
        hints=("Nunca altere a evidência original; trabalhe em cópia.",),
        explanation="Forense exige integridade (hash) e cadeia de custódia auditável.",
        solution="sha256_evidence=verified; custody_log=append_only; original_preserved=true",
    ))

    out.append(C(
        "supply-lockfile", "Lockfile obrigatório", "supply-chain", "fácil", 90,
        "Exija lockfile no laboratório de build.",
        "CI instala sem lock.",
        """<!doctype html><pre>
# ci.yml
- run: npm install
# Corrija para:
# - run: npm ci
</pre>""",
        required=(("npm ci", r"npm\s+ci"),),
        forbidden=(("npm install solto", r"(?m)^\s*- run:\s*npm install\s*$"),),
        hints=("npm ci usa o lockfile e falha se estiver dessincronizado.",),
        explanation="Lockfiles tornam builds reproduzíveis e reduzem risco de supply chain.",
        solution="- run: npm ci",
    ))

    out.append(C(
        "expert-defense-in-depth", "Defesa em profundidade", "zero-trust", "expert", 500,
        "Liste 4 camadas de controle no playbook do lab.",
        "Um único controle não basta.",
        """<!doctype html><pre>
# Playbook Zero Trust Lab
# Preencha exatamente:
# layer1=identity_mfa
# layer2=network_segmentation
# layer3=least_privilege
# layer4=detect_respond
</pre>""",
        required=(
            ("layer1", r"layer1\s*=\s*identity_mfa"),
            ("layer2", r"layer2\s*=\s*network_segmentation"),
            ("layer3", r"layer3\s*=\s*least_privilege"),
            ("layer4", r"layer4\s*=\s*detect_respond"),
        ),
        hints=("Identidade, rede, privilégio e detecção formam um núcleo clássico.",),
        explanation="Zero Trust e defesa em profundidade combinam vários controles independentes.",
        solution="layer1=identity_mfa layer2=network_segmentation layer3=least_privilege layer4=detect_respond",
    ))

    out.append(C(
        "api-rate-limit", "Rate limit em API", "api-lab", "intermediário", 190,
        "Ative rate limit no pseudo-código da API.",
        "Login sem limite de tentativas.",
        """<!doctype html><pre>
@app.post("/login")
def login():
    return check_password(request.json)

# Adicione antes de check_password:
# rate_limit = "5/minute"
</pre>""",
        required=(("rate_limit", r"rate_limit\s*=\s*[\"']5/minute[\"']"),),
        hints=("Rate limit mitiga brute force e abuse.",),
        explanation="APIs públicas precisam de limitação de taxa por IP/usuário.",
        solution='rate_limit = "5/minute"',
    ))

    out.append(C(
        "malware-static-only", "Sandbox só estático", "malware", "fácil", 70,
        "Confirme política: sem execução e sem rede na sandbox do lab.",
        "Política de análise de amostra.",
        """<!doctype html><pre>
# Sandbox policy lab
# execution = ?
# network = ?
# Preencha:
# execution = blocked
# network = disabled
</pre>""",
        required=(
            ("execution blocked", r"execution\s*=\s*blocked"),
            ("network disabled", r"network\s*=\s*disabled"),
        ),
        hints=("No JARVIS Cyber Lab, malware sandbox é análise estática.",),
        explanation="Ambientes educacionais não devem executar malware real nem permitir exfiltração.",
        solution="execution=blocked; network=disabled",
    ))

    # ---- v34.1: mais laboratórios (hackers / blue team) ----
    out.append(C(
        "sqli-prepared", "SQL Injection → prepared statement", "web", "intermediário", 200,
        "Substitua concatenação de SQL por prepared statement no lab.",
        "Consulta vulnerável a injeção.",
        """<!doctype html><pre>
query = "SELECT * FROM users WHERE id = " + user_id
# Corrija para algo como:
# query = "SELECT * FROM users WHERE id = ?"
# params = (user_id,)
</pre>""",
        required=(
            ("placeholder", r"WHERE\s+id\s*=\s*\?"),
            ("params", r"params\s*="),
        ),
        forbidden=(("concat", r"SELECT\s+\*\s+FROM\s+users\s+WHERE\s+id\s*=\s*[\"'].*\+\s*user_id"),),
        hints=("Nunca concatene entrada do usuário em SQL.", "Use placeholders do driver."),
        explanation="Prepared statements separam código de dados e eliminam a maioria das SQLi clássicas.",
        solution='query = "SELECT * FROM users WHERE id = ?"; params = (user_id,)',
    ))

    out.append(C(
        "xss-escape-output", "XSS → escape de saída", "web", "fácil", 120,
        "Escape a saída do usuário no template do lab.",
        "Reflected XSS básico.",
        """<!doctype html><h1>Busca</h1>
<p>Resultados para: {{ query }}</p>
<!-- Use escape explícito no lab, ex.: {{ query | e }} ou html.escape -->
""",
        required=(("escape", r"(\{\{\s*query\s*\|\s*e\s*\}\}|html\.escape|escapeHtml)"),),
        hints=("Escape no momento de renderizar HTML.", "CSP ajuda, mas escape é a base."),
        explanation="XSS ocorre quando dados não confiáveis são interpretados como código no navegador.",
        solution="{{ query | e }} ou html.escape(query)",
    ))

    out.append(C(
        "idor-check-owner", "IDOR → checagem de dono", "api-lab", "intermediário", 210,
        "Garanta que o recurso só é acessível pelo dono autenticado.",
        "API devolve pedido de qualquer user_id.",
        """<!doctype html><pre>
@app.get("/orders/<order_id>")
def get_order(order_id):
    return db.orders.get(order_id)
# Adicione:
# if order.owner_id != current_user.id: abort(403)
</pre>""",
        required=(
            ("owner check", r"owner_id\s*!=\s*current_user\.id"),
            ("abort 403", r"abort\s*\(\s*403\s*\)"),
        ),
        hints=("Autenticação ≠ autorização.", "Sempre vincule o recurso ao sujeito da sessão."),
        explanation="IDOR (Insecure Direct Object Reference) é falha clássica de autorização.",
        solution="if order.owner_id != current_user.id: abort(403)",
    ))

    out.append(C(
        "ssrf-allowlist", "SSRF → allowlist de hosts", "api-lab", "avançado", 320,
        "Restrinja fetches do servidor a uma allowlist.",
        "Proxy interno aceita qualquer URL.",
        """<!doctype html><pre>
url = request.args["url"]
return requests.get(url).text
# Corrija:
# ALLOWED = {"api.interno.lab"}
# if urlparse(url).hostname not in ALLOWED: abort(400)
</pre>""",
        required=(
            ("allowlist", r"ALLOWED\s*="),
            ("hostname check", r"hostname\s+not\s+in\s+ALLOWED"),
        ),
        forbidden=(("open get", r"requests\.get\(\s*url\s*\)"),),
        hints=("SSRF pode alcançar metadata cloud (169.254.169.254).", "Valide esquema + host."),
        explanation="Server-Side Request Forgery permite que o atacante use o servidor como proxy.",
        solution="Allowlist de hostnames + só https + bloquear IPs privados.",
    ))

    out.append(C(
        "path-traversal-safe", "Path traversal → Path.resolve", "web", "intermediário", 200,
        "Impça sair do diretório base ao abrir arquivos.",
        "Download com filename controlado pelo usuário.",
        """<!doctype html><pre>
path = BASE / request.args["file"]
open(path).read()
# Corrija com resolve + checagem de prefixo:
# full = (BASE / name).resolve()
# if not str(full).startswith(str(BASE.resolve())): abort(400)
</pre>""",
        required=(
            ("resolve", r"\.resolve\s*\("),
            ("startswith", r"startswith\s*\("),
        ),
        hints=("Normalize o caminho antes de validar.", "Recuse .. e links simbólicos fora da base."),
        explanation="Path traversal permite ler arquivos sensíveis fora do diretório pretendido.",
        solution="(BASE / name).resolve() e garantir que o resultado permanece sob BASE.",
    ))

    out.append(C(
        "secrets-env-only", "Segredos só no ambiente", "config", "fácil", 90,
        "Remova segredos hardcoded e leia do ambiente.",
        "API key no código-fonte.",
        """<!doctype html><pre>
API_KEY = "sk-live-exemplo-123"
# Corrija:
# API_KEY = os.environ["API_KEY"]
</pre>""",
        required=(("environ", r"os\.environ\[|os\.getenv\("),),
        forbidden=(("hardcoded sk", r"API_KEY\s*=\s*[\"']sk-"),),
        hints=("Nunca commite chaves.", "Use variáveis de ambiente ou vault."),
        explanation="Segredos no código vazam em Git, logs e backups.",
        solution='API_KEY = os.environ["API_KEY"]',
    ))

    out.append(C(
        "cors-restrict", "CORS restrito", "headers", "intermediário", 160,
        "Restrinja Access-Control-Allow-Origin a um origin conhecido.",
        "CORS aberto (*).",
        """<!doctype html><pre>
Access-Control-Allow-Origin: *
# Corrija para o origin do app, ex.:
# Access-Control-Allow-Origin: https://app.lab.local
</pre>""",
        required=(("aca origin", r"Access-Control-Allow-Origin:\s*https?://"),),
        forbidden=(("star", r"Access-Control-Allow-Origin:\s*\*"),),
        hints=("* com credentials é inválido/perigoso.", "Espelhe só origins confiáveis."),
        explanation="CORS permissivo amplia a superfície de abuso de APIs autenticadas.",
        solution="Access-Control-Allow-Origin: https://app.lab.local",
    ))

    out.append(C(
        "clickjacking-frame", "Clickjacking → X-Frame-Options", "headers", "fácil", 80,
        "Bloqueie framing de terceiros.",
        "Página pode ser embutida em iframe malicioso.",
        """<!doctype html><pre>
# Adicione um dos headers:
# X-Frame-Options: DENY
# ou Content-Security-Policy: frame-ancestors 'none'
</pre>""",
        required=(("frame deny", r"(X-Frame-Options:\s*DENY|frame-ancestors[^;]*'none')"),),
        hints=("DENY/SAMEORIGIN ou CSP frame-ancestors.",),
        explanation="Clickjacking engana o usuário a clicar em UI oculta sob um iframe.",
        solution="X-Frame-Options: DENY",
    ))

    out.append(C(
        "password-hash-argon", "Hash de senha moderno", "auth", "intermediário", 180,
        "Troque MD5 por algoritmo adaptativo (bcrypt/argon2/scrypt/pbkdf2).",
        "Senhas com MD5.",
        """<!doctype html><pre>
hash = md5(password)
# Use, por exemplo:
# hash = generate_password_hash(password)  # werkzeug pbkdf2/scrypt
</pre>""",
        required=(("modern hash", r"(generate_password_hash|bcrypt|argon2|scrypt|pbkdf2)"),),
        forbidden=(("md5", r"md5\s*\(\s*password"),),
        hints=("MD5/SHA1 não são para senhas.", "Use custo adaptativo + salt."),
        explanation="Hashes rápidos permitem brute-force offline massivo.",
        solution="generate_password_hash / bcrypt / argon2",
    ))

    out.append(C(
        "log-injection-sanitize", "Log injection", "forense-lab", "intermediário", 150,
        "Sanitize quebras de linha em logs que incluem input do usuário.",
        "Atacante injeta linhas falsas no log.",
        """<!doctype html><pre>
log.write("user=" + username)
# Corrija:
# safe = username.replace("\\n", "").replace("\\r", "")
# log.write("user=" + safe)
</pre>""",
        required=(("strip newlines", r"replace\s*\(\s*[\"']\\\\[nr]"),),
        hints=("Remova \\n/\\r ou use logging estruturado (JSON).",),
        explanation="Log injection dificulta forense e pode enganar SIEM.",
        solution='username.replace("\\n","").replace("\\r","")',
    ))

    return out
