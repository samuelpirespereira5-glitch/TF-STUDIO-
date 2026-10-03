"""Vulnerability Doctor — acha vulnerabilidades em código/HTML/config que VOCÊ fornece
(ou em um site gerado pelo próprio app) e mostra COMO corrigir, com exemplo antes/depois.

É análise estática, local: não envia tráfego para nenhum alvo.
"""
import re
from pathlib import Path

from services.evidence import make_finding as F, risk_score, risk_label
from services.cyber import local

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SITES_DIR = BASE_DIR / "sites"

# ------------------------------------------------------------------ checagens específicas de HTML (sites gerados)
def scan_html(html: str, filename="index.html"):
    findings = []
    lines = (html or "")[:local.MAX_CHARS].splitlines()
    low = (html or "").lower()

    def add(rule, title, sev, ev, impact, fix, where):
        findings.append(F(rule, title, sev, evidence=ev, impact=impact, fix=fix, where=where))

    if "content-security-policy" not in low:
        add("html.no_csp", "Página sem Content-Security-Policy", "medium",
            "nenhuma <meta http-equiv=\"Content-Security-Policy\"> encontrada",
            "Sem CSP, um XSS consegue carregar scripts de qualquer origem.",
            "Adicione uma CSP restritiva (meta ou cabeçalho HTTP).", f"{filename}:csp")
    for n, line in enumerate(lines, 1):
        l = line.lower()
        if re.search(r"<a\b[^>]*target\s*=\s*[\"']_blank[\"'][^>]*>", l) and "noopener" not in l:
            add("html.blank_noopener", "Link com target=_blank sem rel=noopener", "low", f"{filename}:{n}: {line.strip()[:120]}",
                "A página aberta pode manipular a sua (window.opener).", "Adicione rel=\"noopener noreferrer\".", f"{filename}:{n}:blank")
        if re.search(r"<script\b[^>]*src\s*=\s*[\"']https?://", l) and "integrity=" not in l:
            add("html.no_sri", "Script externo sem Subresource Integrity (SRI)", "medium", f"{filename}:{n}: {line.strip()[:120]}",
                "Se o CDN for comprometido, o script malicioso roda no seu site.", "Adicione integrity=\"sha384-...\" e crossorigin=\"anonymous\".", f"{filename}:{n}:sri")
        if re.search(r"\son(click|error|load|mouseover)\s*=", l):
            add("html.inline_handler", "Handler de evento inline (onclick/onerror/…)", "low", f"{filename}:{n}: {line.strip()[:120]}",
                "Obriga a liberar 'unsafe-inline' na CSP e facilita XSS.", "Use addEventListener em um script separado.", f"{filename}:{n}:inline")
        if re.search(r"(src|href|action)\s*=\s*[\"']http://", l):
            add("html.mixed_content", "Recurso carregado via HTTP (conteúdo misto)", "medium", f"{filename}:{n}: {line.strip()[:120]}",
                "Pode ser interceptado/alterado em trânsito e é bloqueado pelos navegadores.", "Troque para https://.", f"{filename}:{n}:http")
        if re.search(r"<iframe\b", l) and "sandbox" not in l:
            add("html.iframe_no_sandbox", "iframe sem atributo sandbox", "low", f"{filename}:{n}: {line.strip()[:120]}",
                "Conteúdo embutido roda com privilégios amplos.", "Adicione sandbox (ex.: sandbox=\"allow-scripts\").", f"{filename}:{n}:iframe")
        if re.search(r"<input\b[^>]*type\s*=\s*[\"']password[\"']", l) and "autocomplete" not in l:
            add("html.pwd_autocomplete", "Campo de senha sem autocomplete definido", "info", f"{filename}:{n}: {line.strip()[:120]}",
                "Comportamento imprevisível em gerenciadores de senha.", "Use autocomplete=\"current-password\" ou \"new-password\".", f"{filename}:{n}:pwd")
        if re.search(r"<form\b[^>]*method\s*=\s*[\"']get[\"']", l) and "password" in low:
            add("html.form_get_pwd", "Formulário com senha usando GET", "high", f"{filename}:{n}: {line.strip()[:120]}",
                "Senha vai na URL (histórico, logs, referrer).", "Use method=\"post\".", f"{filename}:{n}:formget")
    return {"findings": findings, "raw": {"lines": len(lines), "file": filename}}


SQL_EXTRA = re.compile(r"""(?i)(f["'].*\b(select|insert|update|delete)\b.*\{[^}]+\}|["'].*\b(select|insert|update|delete)\b.*["']\s*(\+|%)\s*\w|\b(select|insert|update|delete)\b.*["']\s*\.format\()""")


def _extra_sql(text, filename):
    """Complementa local.scan_code: pega SQL montado por f-string/concatenação mesmo com aspas dentro."""
    out = []
    for n, line in enumerate((text or "").splitlines(), 1):
        st = line.strip()
        if st.startswith(("#", "//", "*")) or "?" in st and "execute(" in st and "{" not in st:
            continue
        if SQL_EXTRA.search(line) and re.search(r"(?i)select\b.+\bfrom\b|insert\s+into|update\b.+\bset\b|delete\s+from", line):
            out.append(F("code.sql_concat", "SQL montado por concatenação/formatação", "high",
                         evidence=f"{filename or 'texto'}:{n}: {st[:140]}",
                         impact="SQL Injection.", fix="Use consultas parametrizadas (placeholders).",
                         where=f"{filename}:{n}:code.sql_concat"))
    return out


# ------------------------------------------------------------------ correções (antes/depois) por regra
FIXES = {
    "code.sql_concat": {
        "how": "Nunca monte SQL juntando texto. Use placeholders e deixe o driver escapar os valores.",
        "before": 'db.execute(f"SELECT * FROM users WHERE name = \'{name}\'")',
        "after": 'db.execute("SELECT * FROM users WHERE name = ?", (name,))'},
    "code.eval": {
        "how": "Troque eval por um parser seguro do formato que você realmente precisa.",
        "before": "data = eval(user_input)",
        "after": "import json\ndata = json.loads(user_input)   # ou ast.literal_eval para literais Python"},
    "code.exec": {
        "how": "Evite executar texto como código. Mapeie ações permitidas explicitamente.",
        "before": "exec(user_code)",
        "after": "ACTIONS = {'start': start, 'stop': stop}\nACTIONS[action]()   # só o que você permitiu"},
    "code.shell_true": {
        "how": "Passe os argumentos como lista e desligue o shell.",
        "before": 'subprocess.run(f"ping {host}", shell=True)',
        "after": 'subprocess.run(["ping", "-c", "1", host], shell=False, check=True)'},
    "code.os_system": {
        "how": "Use subprocess com lista de argumentos.",
        "before": 'os.system("ls " + path)',
        "after": 'subprocess.run(["ls", path], check=True)'},
    "code.pickle": {
        "how": "Use um formato de dados, não de objetos: JSON.",
        "before": "obj = pickle.loads(request.data)",
        "after": "obj = json.loads(request.data)"},
    "code.yaml_load": {
        "how": "Use o carregador seguro.",
        "before": "cfg = yaml.load(text)",
        "after": "cfg = yaml.safe_load(text)"},
    "code.innerhtml": {
        "how": "Use textContent para texto; se precisar de HTML, sanitize com DOMPurify.",
        "before": "el.innerHTML = userInput;",
        "after": "el.textContent = userInput;\n// ou: el.innerHTML = DOMPurify.sanitize(userInput);"},
    "code.md5_sha1": {
        "how": "Para senhas use hash lento com salt; para integridade use SHA-256.",
        "before": "hashlib.md5(pwd.encode()).hexdigest()",
        "after": "from werkzeug.security import generate_password_hash, check_password_hash\nhash = generate_password_hash(pwd)"},
    "code.verify_false": {
        "how": "Remova verify=False. Se o certificado for interno, aponte para a CA correta.",
        "before": "requests.get(url, verify=False)",
        "after": "requests.get(url, timeout=10)   # ou verify='/caminho/ca.pem'"},
    "code.debug_true": {
        "how": "Leia o modo debug de variável de ambiente e deixe desligado em produção.",
        "before": "app.run(debug=True)",
        "after": "app.run(debug=os.environ.get('FLASK_DEBUG') == '1')"},
    "code.weak_random": {
        "how": "Para tokens/senhas use o módulo secrets.",
        "before": "token = str(random.randint(0, 999999))",
        "after": "import secrets\ntoken = secrets.token_urlsafe(32)"},
    "code.jwt_none": {
        "how": "Fixe o algoritmo e sempre verifique a assinatura.",
        "before": 'jwt.decode(token, options={"verify_signature": False})',
        "after": 'jwt.decode(token, SECRET, algorithms=["HS256"])'},
    "code.cors_any": {
        "how": "Liste só as origens que precisam acessar a API.",
        "before": "CORS(app)",
        "after": 'CORS(app, origins=["https://meusite.com"])'},
    "code.secret_default": {
        "how": "Leia a chave de variável de ambiente e falhe se não existir.",
        "before": 'app.secret_key = "minha-chave"',
        "after": 'app.secret_key = os.environ["SECRET_KEY"]'},
    "auth.plain_password": {
        "how": "Guarde só o hash e compare com a função apropriada.",
        "before": 'if password == "admin123":',
        "after": "if check_password_hash(user.password_hash, password):"},
    "html.no_csp": {
        "how": "Adicione uma CSP no <head> (ou, melhor, como cabeçalho HTTP no servidor).",
        "before": "<head>\n  <title>Meu site</title>\n</head>",
        "after": "<head>\n  <meta http-equiv=\"Content-Security-Policy\"\n        content=\"default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'\">\n  <title>Meu site</title>\n</head>"},
    "html.blank_noopener": {
        "how": "Acrescente rel=\"noopener noreferrer\".",
        "before": '<a href="https://x.com" target="_blank">',
        "after": '<a href="https://x.com" target="_blank" rel="noopener noreferrer">'},
    "html.no_sri": {
        "how": "Adicione integrity e crossorigin (gere o hash em srihash.org ou com openssl).",
        "before": '<script src="https://cdn.exemplo.com/lib.js"></script>',
        "after": '<script src="https://cdn.exemplo.com/lib.js"\n        integrity="sha384-HASH_AQUI" crossorigin="anonymous"></script>'},
    "html.inline_handler": {
        "how": "Mova o comportamento para um script com addEventListener.",
        "before": '<button onclick="comprar()">Comprar</button>',
        "after": '<button id="btn-comprar">Comprar</button>\n<script>document.getElementById("btn-comprar").addEventListener("click", comprar);</script>'},
    "html.mixed_content": {
        "how": "Use HTTPS em todos os recursos.",
        "before": '<img src="http://site.com/foto.jpg">',
        "after": '<img src="https://site.com/foto.jpg">'},
    "html.iframe_no_sandbox": {
        "how": "Restrinja o iframe com sandbox e libere só o necessário.",
        "before": '<iframe src="https://mapa.com/x"></iframe>',
        "after": '<iframe src="https://mapa.com/x" sandbox="allow-scripts allow-same-origin"></iframe>'},
    "html.form_get_pwd": {
        "how": "Formulários com senha sempre usam POST.",
        "before": '<form method="get">',
        "after": '<form method="post">'},
    "headers.content-security-policy": {
        "how": "No nginx, adicione o cabeçalho.",
        "before": "# (sem cabeçalho)",
        "after": "add_header Content-Security-Policy \"default-src 'self'\" always;"},
    "headers.strict-transport-security": {
        "how": "Force HTTPS por 1 ano.",
        "before": "# (sem cabeçalho)",
        "after": 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'},
    "headers.x-frame-options": {
        "how": "Impeça que seu site seja embutido em iframes de terceiros.",
        "before": "# (sem cabeçalho)",
        "after": 'add_header X-Frame-Options "DENY" always;'},
    "headers.x-content-type-options": {
        "how": "Desative o MIME sniffing.",
        "before": "# (sem cabeçalho)",
        "after": 'add_header X-Content-Type-Options "nosniff" always;'},
}


def _fix_for(rule: str):
    if rule in FIXES:
        return FIXES[rule]
    if rule.startswith("secret."):
        return {"how": "Revogue a credencial exposta agora, tire do código e leia de variável de ambiente.",
                "before": 'API_KEY = "sk-abc123..."',
                "after": 'API_KEY = os.environ["API_KEY"]'}
    if rule.startswith("deps."):
        return {"how": "Fixe a versão exata e atualize dependências com falha conhecida.",
                "before": "flask",
                "after": "Flask==3.0.3"}
    return None


def _enrich(findings):
    out = []
    for f in findings:
        f = dict(f)
        f["remediation"] = _fix_for(f["rule"])
        out.append(f)
    return out


# ------------------------------------------------------------------ orquestração
def _guess_kind(text, filename):
    name = (filename or "").lower()
    if name.endswith((".html", ".htm")) or re.search(r"(?is)<\s*(html|head|body|script|div)\b", text or ""):
        return "html"
    if name.endswith((".py", ".js", ".ts", ".php", ".jsx", ".tsx")):
        return "code"
    if name.endswith((".env", ".conf", ".ini")) or name in ("nginx.conf", "sshd_config"):
        return "config"
    if name.endswith(("requirements.txt", "package.json")):
        return "deps"
    return "code"


def diagnose(text: str, filename: str = ""):
    """Roda todas as análises locais aplicáveis e devolve achados + como corrigir + score."""
    text = text or ""
    kind = _guess_kind(text, filename)
    findings = []
    findings += local.scan_secrets(text, filename)["findings"]
    if kind == "html":
        findings += scan_html(text, filename or "index.html")["findings"]
        findings += local.scan_code(text, filename or "index.html")["findings"]  # JS embutido
    elif kind == "config":
        findings += local.audit_config(text)["findings"]
    elif kind == "deps":
        findings += local.scan_dependencies(text, filename)["findings"]
    else:
        findings += local.scan_code(text, filename)["findings"]
    if kind in ("code", "html"):
        findings += _extra_sql(text, filename)
    # dedup por id estável
    seen, uniq = set(), []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            uniq.append(f)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    uniq.sort(key=lambda f: order[f["severity"]])
    enriched = _enrich(uniq)
    score = risk_score(enriched)
    return {"kind": kind, "findings": enriched, "score": score, "risk": risk_label(score),
            "summary": f"{len(enriched)} vulnerabilidade(s) · risco {risk_label(score)} ({score}/100)"}


def diagnose_site(slug: str):
    """Analisa o index.html de um site gerado pelo próprio app."""
    folder = (SITES_DIR / (slug or "")).resolve()
    if SITES_DIR.resolve() not in folder.parents or not folder.is_dir():
        raise ValueError("Site não encontrado.")
    index = folder / "index.html"
    if not index.exists():
        raise ValueError("Este site não tem index.html.")
    res = diagnose(index.read_text(encoding="utf-8", errors="ignore"), "index.html")
    res["site"] = folder.name
    return res
