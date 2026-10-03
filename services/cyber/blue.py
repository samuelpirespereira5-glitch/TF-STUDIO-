"""Módulo Blue Team: Threat Intel, hardening, FIM, phishing, IR, relatórios.
Tudo aqui é análise/consulta/defesa — nada dispara tráfego contra terceiros.
"""
import hashlib
import json
import math
import re
import time
from datetime import datetime

from services.evidence import make_finding as F

# ---------------------------------------------------------------- MITRE ATT&CK (subset curado)
MITRE_TACTICS = [
    {"id": "TA0043", "name": "Reconnaissance", "pt": "Reconhecimento",
     "techniques": [
         {"id": "T1595", "name": "Active Scanning", "detect": "Alertar em varredura de portas/paths em sequência rápida vinda do mesmo IP (ver Analisador de Logs).",
          "mitigate": "Rate limiting, WAF, fail2ban."},
         {"id": "T1589", "name": "Gather Victim Identity Information", "detect": "Monitorar OSINT sobre a própria organização.",
          "mitigate": "Minimizar exposição de e-mails/nomes em código-fonte e metadados."},
     ]},
    {"id": "TA0001", "name": "Initial Access", "pt": "Acesso Inicial",
     "techniques": [
         {"id": "T1190", "name": "Exploit Public-Facing Application", "detect": "Padrões de SQLi/XSS/traversal nos logs de acesso.",
          "mitigate": "Validação de entrada, WAF, patch de dependências (ver Scanner de Dependências)."},
         {"id": "T1566", "name": "Phishing", "detect": "SPF/DKIM/DMARC ausentes ou 'fail' em cabeçalhos recebidos.",
          "mitigate": "Publicar SPF/DKIM/DMARC estritos; treinar usuários."},
     ]},
    {"id": "TA0004", "name": "Privilege Escalation", "pt": "Escalada de Privilégios",
     "techniques": [
         {"id": "T1068", "name": "Exploitation for Privilege Escalation", "detect": "Dependências desatualizadas com CVEs conhecidas.",
          "mitigate": "Patch management e princípio do menor privilégio."},
         {"id": "T1548", "name": "Abuse Elevation Control Mechanism", "detect": "Configs com debug=True ou SECRET_KEY fraca em produção.",
          "mitigate": "Hardening de configuração (ver Análise de Configs)."},
     ]},
    {"id": "TA0005", "name": "Defense Evasion", "pt": "Evasão de Defesa",
     "techniques": [
         {"id": "T1070", "name": "Indicator Removal", "detect": "Gaps/lacunas suspeitas no timeline de logs; hashes de log alterados.",
          "mitigate": "Logging centralizado e imutável (syslog remoto), FIM nos próprios logs."},
     ]},
    {"id": "TA0006", "name": "Credential Access", "pt": "Acesso a Credenciais",
     "techniques": [
         {"id": "T1110", "name": "Brute Force", "detect": "Múltiplas falhas de autenticação do mesmo IP/usuário em curto período.",
          "mitigate": "Bloqueio progressivo, MFA, CAPTCHA."},
         {"id": "T1552", "name": "Unsecured Credentials", "detect": "Segredos expostos em código/repo (ver Scanner de Segredos).",
          "mitigate": "Cofre de segredos, rotação de chaves, git-secrets em CI."},
     ]},
    {"id": "TA0010", "name": "Exfiltration", "pt": "Exfiltração",
     "techniques": [
         {"id": "T1041", "name": "Exfiltration Over C2 Channel", "detect": "Volume incomum de dados de saída; user-agents/paths anômalos.",
          "mitigate": "DLP, egress filtering, alertas de volume."},
         {"id": "T1567", "name": "Exfiltration Over Web Service", "detect": "Requisições POST grandes para domínios externos incomuns nos logs.",
          "mitigate": "CSP restritiva, allowlist de domínios de saída."},
     ]},
    {"id": "TA0040", "name": "Impact", "pt": "Impacto",
     "techniques": [
         {"id": "T1499", "name": "Endpoint Denial of Service", "detect": "Picos de requisições/erro 5xx em curto intervalo.",
          "mitigate": "Rate limiting, autoscaling, CDN com proteção anti-DDoS."},
     ]},
]


def mitre_lookup(query=""):
    q = (query or "").strip().lower()
    if not q:
        return MITRE_TACTICS
    out = []
    for tac in MITRE_TACTICS:
        techs = [t for t in tac["techniques"]
                 if q in t["id"].lower() or q in t["name"].lower() or q in tac["pt"].lower() or q in tac["name"].lower()]
        if techs or q in tac["pt"].lower() or q in tac["name"].lower():
            out.append({**tac, "techniques": techs or tac["techniques"]})
    return out


# ---------------------------------------------------------------- IoC feed (educacional/estático)
# Hashes/IPs de exemplo conhecidos publicamente como maliciosos em relatórios públicos (didático).
IOC_SAMPLE = {
    "hashes_md5": [
        "d41d8cd98f00b204e9800998ecf8427e",  # arquivo vazio (referência/baseline, não malicioso)
    ],
    "note": "Feed de exemplo local. Para produção, integre feeds reais (AlienVault OTX, abuse.ch) via API própria.",
    "reputational_ip_ranges_info": [
        "Consulte AbuseIPDB / GreyNoise / Shodan manualmente para reputação real de um IP.",
    ],
}


def check_hash_against_feed(hash_value: str):
    h = (hash_value or "").strip().lower()
    found = h in [x.lower() for x in IOC_SAMPLE["hashes_md5"]]
    return {"hash": h, "found_in_local_feed": found,
            "note": "Feed local é apenas demonstrativo. Recomenda-se consultar VirusTotal/abuse.ch para veredito real."}


# ---------------------------------------------------------------- WAF / firewall rule generator
def generate_waf_rules(target_engine: str, patterns: list):
    """Gera regras DEFENSIVAS de bloqueio (nginx/modsecurity/iptables) a partir de
    padrões de ataque já observados (ex.: nos próprios logs). Não gera exploits."""
    engine = (target_engine or "nginx").lower()
    patterns = patterns or ["sqli", "xss", "traversal", "scanner"]
    rules_map = {
        "sqli": r"(?i)(union(\s|%20)+select|or\s+1=1|sleep\(\d|information_schema)",
        "xss": r"(?i)(<script|%3Cscript|onerror=|javascript:)",
        "traversal": r"(\.\./|%2e%2e%2f|/etc/passwd)",
        "scanner": r"(?i)(wp-login|xmlrpc\.php|/\.env|/\.git/|phpmyadmin)",
    }
    chosen = {k: v for k, v in rules_map.items() if k in patterns}
    out = ""
    if engine == "nginx":
        out += "# Bloqueio por padrão de ataque conhecido (nginx)\n"
        for name, pat in chosen.items():
            out += f'if ($request_uri ~* "{pat}") {{ return 403; }}\n'
        out += "\n# Rate limiting básico\nlimit_req_zone $binary_remote_addr zone=defensive:10m rate=10r/s;\nlimit_req zone=defensive burst=20 nodelay;\n"
    elif engine == "modsecurity":
        out += "# Regras ModSecurity (SecRule) — ajuste IDs conforme seu conjunto\n"
        rid = 900001
        for name, pat in chosen.items():
            out += (f'SecRule REQUEST_URI "@rx {pat}" '
                    f'"id:{rid},phase:1,deny,status:403,log,msg:\'Bloqueado padrão {name}\'"\n')
            rid += 1
    elif engine == "iptables":
        out += "# Regras iptables básicas (rate limit + bloqueio de IP repetido ofensor)\n"
        out += ("iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --set\n"
                "iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --update --seconds 1 --hitcount 20 -j DROP\n"
                "# Para bloquear um IP específico identificado como ofensor nos logs:\n"
                "# iptables -A INPUT -s <IP_OFENSOR> -j DROP\n")
    else:
        return {"error": f"engine desconhecido: {engine}"}
    return {"engine": engine, "patterns": list(chosen.keys()), "rules": out.strip()}


# ---------------------------------------------------------------- Hardening de headers HTTP
REQUIRED_HEADERS = {
    "content-security-policy": ("high", "CSP ausente", "Sem CSP o navegador não restringe origens de scripts/estilos (mitiga XSS).",
                                 "Adicione Content-Security-Policy restritiva (ex.: default-src 'self')."),
    "strict-transport-security": ("medium", "HSTS ausente", "Sem HSTS, downgrade para HTTP é possível.",
                                   "Adicione Strict-Transport-Security: max-age=31536000; includeSubDomains."),
    "x-frame-options": ("medium", "X-Frame-Options ausente", "Vulnerável a clickjacking.",
                         "Adicione X-Frame-Options: DENY (ou CSP frame-ancestors)."),
    "x-content-type-options": ("low", "X-Content-Type-Options ausente", "MIME sniffing pode causar XSS.",
                                "Adicione X-Content-Type-Options: nosniff."),
    "referrer-policy": ("low", "Referrer-Policy ausente", "Vaza URL completa em referrers cross-site.",
                         "Adicione Referrer-Policy: strict-origin-when-cross-origin."),
    "permissions-policy": ("low", "Permissions-Policy ausente", "APIs sensíveis (câmera/geo) sem restrição.",
                            "Adicione Permissions-Policy restringindo o que não é usado."),
}


def audit_http_headers(headers_text: str):
    """Recebe cabeçalhos HTTP brutos (colados pelo usuário, ex.: saída de curl -I no próprio site)
    e aponta o que falta. Não faz requisição de rede."""
    low = "\n".join(l.strip().lower() for l in (headers_text or "").splitlines())
    findings = []
    for header, (sev, title, impact, fix) in REQUIRED_HEADERS.items():
        if header not in low:
            findings.append(F(f"headers.{header}", title, sev, evidence=f"cabeçalho '{header}' não encontrado",
                              impact=impact, fix=fix, where=f"header:{header}"))
    if "set-cookie" in low and "secure" not in low:
        findings.append(F("headers.cookie_insecure", "Cookie sem flag Secure", "medium",
                          evidence="Set-Cookie sem 'Secure'", impact="Cookie pode trafegar em HTTP puro.",
                          fix="Adicione Secure; HttpOnly; SameSite=Strict/Lax aos cookies."))
    if "set-cookie" in low and "httponly" not in low:
        findings.append(F("headers.cookie_httponly", "Cookie sem flag HttpOnly", "medium",
                          evidence="Set-Cookie sem 'HttpOnly'", impact="Cookie acessível via JS (roubo em XSS).",
                          fix="Adicione HttpOnly ao cookie."))
    return {"findings": findings, "raw": {"checked": list(REQUIRED_HEADERS.keys())}}


# ---------------------------------------------------------------- File Integrity Monitoring (FIM)
def fim_hash_files(file_map: dict):
    """file_map: {caminho_relativo: conteudo_texto_ou_base64}. Retorna hash SHA-256 de cada."""
    out = {}
    for path, content in (file_map or {}).items():
        data = content.encode("utf-8", errors="ignore") if isinstance(content, str) else content
        out[path] = hashlib.sha256(data).hexdigest()
    return {"hashes": out, "generated_at": datetime.utcnow().isoformat() + "Z", "count": len(out)}


def fim_compare(baseline: dict, current: dict):
    baseline = baseline or {}
    current = current or {}
    findings = []
    added = [p for p in current if p not in baseline]
    removed = [p for p in baseline if p not in current]
    modified = [p for p in current if p in baseline and baseline[p] != current[p]]
    for p in modified:
        findings.append(F("fim.modified", f"Arquivo modificado: {p}", "high",
                          evidence=f"hash mudou de {baseline[p][:12]}… para {current[p][:12]}…",
                          impact="Alteração não rastreada em arquivo crítico.",
                          fix="Verifique se a mudança foi autorizada; se não, restaure do backup/git e investigue.",
                          where=f"fim:{p}"))
    for p in removed:
        findings.append(F("fim.removed", f"Arquivo removido: {p}", "medium",
                          evidence="presente no baseline, ausente agora", impact="Pode indicar remoção maliciosa ou deploy incompleto.",
                          fix="Confirme se a remoção foi intencional.", where=f"fim:{p}"))
    for p in added:
        findings.append(F("fim.added", f"Arquivo novo: {p}", "info",
                          evidence="não estava no baseline", impact="Pode ser legítimo (novo deploy) ou plantado.",
                          fix="Confirme a origem do arquivo.", where=f"fim:{p}"))
    return {"findings": findings, "raw": {"added": added, "removed": removed, "modified": modified}}


# ---------------------------------------------------------------- Analisador de cabeçalhos de e-mail
def analyze_email_headers(raw_headers: str):
    text = raw_headers or ""
    findings = []
    spf = re.search(r"(?i)Received-SPF:\s*(\w+)", text) or re.search(r"(?i)spf=(\w+)", text)
    dkim = re.search(r"(?i)dkim=(\w+)", text)
    dmarc = re.search(r"(?i)dmarc=(\w+)", text)
    auth_results = re.search(r"(?i)Authentication-Results:.*", text)

    def status(m):
        return m.group(1).lower() if m else None

    spf_s, dkim_s, dmarc_s = status(spf), status(dkim), status(dmarc)
    if spf_s is None:
        findings.append(F("email.spf_missing", "SPF não encontrado nos cabeçalhos", "medium",
                          evidence="sem Received-SPF/spf=", impact="Não é possível confirmar autorização do servidor de envio.",
                          fix="Publique um registro SPF (TXT) restritivo no domínio remetente.", where="email:spf"))
    elif spf_s not in ("pass",):
        findings.append(F("email.spf_fail", f"SPF = {spf_s}", "high" if spf_s == "fail" else "medium",
                          evidence=f"spf={spf_s}", impact="Remetente pode estar forjado (spoofing).",
                          fix="Investigue o domínio de origem; trate com suspeita.", where="email:spf"))
    if dkim_s is None:
        findings.append(F("email.dkim_missing", "DKIM não encontrado", "medium", evidence="sem dkim=",
                          impact="Assinatura de integridade ausente.", fix="Configure DKIM no domínio remetente.", where="email:dkim"))
    elif dkim_s != "pass":
        findings.append(F("email.dkim_fail", f"DKIM = {dkim_s}", "high", evidence=f"dkim={dkim_s}",
                          impact="Conteúdo pode ter sido alterado em trânsito, ou assinatura inválida.",
                          fix="Trate com suspeita; verifique remetente real.", where="email:dkim"))
    if dmarc_s is None:
        findings.append(F("email.dmarc_missing", "DMARC não encontrado", "low", evidence="sem dmarc=",
                          impact="Sem política de alinhamento declarada.", fix="Publique DMARC (mesmo que p=none no início).", where="email:dmarc"))
    elif dmarc_s not in ("pass",):
        findings.append(F("email.dmarc_fail", f"DMARC = {dmarc_s}", "high", evidence=f"dmarc={dmarc_s}",
                          impact="Forte indício de phishing/spoofing.", fix="Não confie neste e-mail; reporte como phishing.", where="email:dmarc"))
    mismatched_from = re.findall(r"(?i)^From:.*?<([^>]+)>", text, re.M)
    reply_to = re.findall(r"(?i)^Reply-To:.*?<([^>]+)>", text, re.M)
    if mismatched_from and reply_to and mismatched_from[0].split("@")[-1].lower() != reply_to[0].split("@")[-1].lower():
        findings.append(F("email.reply_to_mismatch", "Reply-To em domínio diferente do From", "high",
                          evidence=f"From@{mismatched_from[0].split('@')[-1]} vs Reply-To@{reply_to[0].split('@')[-1]}",
                          impact="Técnica comum em phishing/BEC: resposta vai para domínio do atacante.",
                          fix="Trate como suspeito; confirme por outro canal antes de responder.", where="email:reply_to"))
    return {"findings": findings, "raw": {"spf": spf_s, "dkim": dkim_s, "dmarc": dmarc_s,
            "auth_results_line": auth_results.group(0) if auth_results else None}}


# ---------------------------------------------------------------- IR Playbooks
IR_PLAYBOOKS = {
    "web_compromise": {
        "title": "Comprometimento de aplicação web",
        "steps": [
            {"phase": "Identificação", "text": "Confirme o indício (log suspeito, alerta FIM, comportamento anômalo). Registre hora e evidência."},
            {"phase": "Contenção", "text": "Isole o serviço (tire do balanceador ou pare temporariamente), preserve logs antes de qualquer limpeza, revogue credenciais/tokens expostos."},
            {"phase": "Erradicação", "text": "Identifique a causa raiz (via Scanner de Código/Config), remova webshells/arquivos plantados (compare com FIM), atualize dependências vulneráveis."},
            {"phase": "Recuperação", "text": "Restaure de backup limpo se necessário, reative o serviço monitorando de perto, rode novo scan completo antes de declarar resolvido."},
            {"phase": "Lições aprendidas", "text": "Gere o Relatório de Auditoria, documente timeline, atualize regras de WAF/detecção para o padrão observado."},
        ],
    },
    "credential_leak": {
        "title": "Vazamento de credencial/segredo",
        "steps": [
            {"phase": "Identificação", "text": "Confirme o segredo exposto (Scanner de Segredos) e onde (repo, log, build público)."},
            {"phase": "Contenção", "text": "Revogue/rotacione a credencial IMEDIATAMENTE, mesmo antes de entender o alcance."},
            {"phase": "Erradicação", "text": "Remova do histórico (git filter-repo/BFG), audite acessos feitos com a credencial no período exposto."},
            {"phase": "Recuperação", "text": "Emita nova credencial via cofre de segredos, atualize configuração dos serviços."},
            {"phase": "Lições aprendidas", "text": "Adicione hook de pre-commit / CI que rode o Scanner de Segredos automaticamente."},
        ],
    },
    "bruteforce_detected": {
        "title": "Força bruta / varredura detectada nos logs",
        "steps": [
            {"phase": "Identificação", "text": "Use o Analisador de Logs para confirmar IP(s) e volume de tentativas."},
            {"phase": "Contenção", "text": "Bloqueie o(s) IP(s) via regra de firewall/WAF gerada aqui; ative rate limiting se ainda não houver."},
            {"phase": "Erradicação", "text": "Confirme que nenhuma tentativa teve sucesso (cheque logs de autenticação bem-sucedida no mesmo período)."},
            {"phase": "Recuperação", "text": "Se alguma conta foi comprometida, force reset de senha e revise sessões ativas."},
            {"phase": "Lições aprendidas", "text": "Considere MFA e fail2ban permanente."},
        ],
    },
    "phishing_reported": {
        "title": "E-mail de phishing reportado",
        "steps": [
            {"phase": "Identificação", "text": "Rode o Analisador de Cabeçalhos de E-mail (SPF/DKIM/DMARC, Reply-To)."},
            {"phase": "Contenção", "text": "Oriente o usuário a não clicar/responder; bloqueie remetente/domínio no filtro de e-mail."},
            {"phase": "Erradicação", "text": "Verifique se outros usuários receberam o mesmo e-mail; remova das caixas de entrada se possível."},
            {"phase": "Recuperação", "text": "Se houve clique, force reset de senha e verifique atividade da conta."},
            {"phase": "Lições aprendidas", "text": "Reforce DMARC (p=reject) e treinamento de conscientização."},
        ],
    },
}


def get_ir_playbook(key: str):
    return IR_PLAYBOOKS.get(key)


def list_ir_playbooks():
    return [{"key": k, "title": v["title"]} for k, v in IR_PLAYBOOKS.items()]


# ---------------------------------------------------------------- Gerador de testes de segurança
def generate_security_tests(language: str, endpoints: list):
    language = (language or "python").lower()
    endpoints = endpoints or [{"path": "/api/example", "method": "GET"}]
    if language.startswith("py"):
        code = "import pytest\nimport requests\n\nBASE_URL = \"http://localhost:5000\"  # ajuste para o seu ambiente de teste\n\n"
        for ep in endpoints:
            path = ep.get("path", "/")
            method = ep.get("method", "GET").upper()
            fn = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "root"
            code += f'''
def test_{fn}_rejects_sqli_payload():
    """{method} {path} não deve refletir/erroar com payload de SQLi (teste de robustez, contra o próprio ambiente local)."""
    r = requests.{method.lower()}(BASE_URL + "{path}", params={{"q": "' OR '1'='1"}})
    assert r.status_code in (200, 400, 422), f"status inesperado: {{r.status_code}}"
    assert "sql" not in r.text.lower() and "syntax error" not in r.text.lower()


def test_{fn}_rejects_xss_payload():
    r = requests.{method.lower()}(BASE_URL + "{path}", params={{"q": "<script>alert(1)</script>"}})
    assert "<script>" not in r.text, "payload refletido sem sanitização (possível XSS)"


def test_{fn}_handles_missing_params_gracefully():
    r = requests.{method.lower()}(BASE_URL + "{path}")
    assert r.status_code != 500, "erro 500 com parâmetros ausentes indica falta de validação"
'''
        return {"language": "python", "code": code.strip(), "filename": "test_security_endpoints.py"}
    else:
        code = "const request = require('supertest');\nconst BASE_URL = 'http://localhost:3000';\n\n"
        for ep in endpoints:
            path = ep.get("path", "/")
            method = ep.get("method", "GET").lower()
            fn = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_") or "root"
            code += f'''
describe('{method.upper()} {path}', () => {{
  test('rejeita payload de SQLi sem erro 500', async () => {{
    const res = await request(BASE_URL).{method}('{path}').query({{ q: "' OR '1'='1" }});
    expect(res.status).not.toBe(500);
    expect(res.text.toLowerCase()).not.toContain('sql');
  }});

  test('não reflete payload de XSS sem sanitizar', async () => {{
    const res = await request(BASE_URL).{method}('{path}').query({{ q: '<script>alert(1)</script>' }});
    expect(res.text).not.toContain('<script>');
  }});

  test('lida com parâmetros ausentes sem 500', async () => {{
    const res = await request(BASE_URL).{method}('{path}');
    expect(res.status).not.toBe(500);
  }});
}});
'''
        return {"language": "javascript", "code": code.strip(), "filename": "security.test.js"}


# ---------------------------------------------------------------- CTF educacional (código vulnerável para o usuário corrigir)
CTF_CHALLENGES = [
    {"id": "ctf1", "title": "SQL Injection básica", "difficulty": "iniciante",
     "vulnerable_code": '''@app.route("/login", methods=["POST"])
def login():
    user = request.form["user"]
    pwd = request.form["pwd"]
    query = f"SELECT * FROM users WHERE user='{user}' AND pwd='{pwd}'"
    result = db.execute(query)
    return "ok" if result else "fail"''',
     "hint": "O que acontece se 'user' for  admin' --  ?",
     "fixed_code": '''@app.route("/login", methods=["POST"])
def login():
    user = request.form["user"]
    pwd = request.form["pwd"]
    result = db.execute("SELECT * FROM users WHERE user=? AND pwd=?", (user, pwd))
    return "ok" if result else "fail"'''},
    {"id": "ctf2", "title": "XSS refletido", "difficulty": "iniciante",
     "vulnerable_code": '''@app.route("/search")
def search():
    q = request.args.get("q", "")
    return f"<h1>Resultados para: {q}</h1>"''',
     "hint": "O parâmetro 'q' vai direto pro HTML sem escape.",
     "fixed_code": '''from markupsafe import escape

@app.route("/search")
def search():
    q = request.args.get("q", "")
    return f"<h1>Resultados para: {escape(q)}</h1>"'''},
    {"id": "ctf3", "title": "Deserialização insegura", "difficulty": "intermediário",
     "vulnerable_code": '''import pickle

@app.route("/load", methods=["POST"])
def load():
    data = pickle.loads(request.data)
    return str(data)''',
     "hint": "pickle.loads executa código arbitrário se o atacante controlar os bytes.",
     "fixed_code": '''import json

@app.route("/load", methods=["POST"])
def load():
    data = json.loads(request.data)
    return str(data)'''},
    {"id": "ctf4", "title": "Path traversal em download", "difficulty": "intermediário",
     "vulnerable_code": '''@app.route("/download")
def download():
    filename = request.args.get("file")
    return send_file(f"uploads/{filename}")''',
     "hint": "E se filename for ../../etc/passwd ?",
     "fixed_code": '''import os

@app.route("/download")
def download():
    filename = request.args.get("file", "")
    safe_name = os.path.basename(filename)  # remove qualquer path traversal
    full_path = os.path.join("uploads", safe_name)
    if not os.path.abspath(full_path).startswith(os.path.abspath("uploads")):
        abort(400)
    return send_file(full_path)'''},
    {"id": "ctf5", "title": "SSRF em fetch de URL", "difficulty": "avançado",
     "vulnerable_code": '''@app.route("/fetch")
def fetch():
    url = request.args.get("url")
    r = requests.get(url)
    return r.text''',
     "hint": "O atacante pode apontar 'url' para http://169.254.169.254/ (metadata da nuvem) ou serviços internos.",
     "fixed_code": '''ALLOWED_HOSTS = {"api.meusite.com"}

@app.route("/fetch")
def fetch():
    url = request.args.get("url", "")
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS or parsed.scheme != "https":
        abort(400, "host não permitido")
    r = requests.get(url, timeout=5)
    return r.text'''},
]


def list_ctf_challenges():
    return [{"id": c["id"], "title": c["title"], "difficulty": c["difficulty"]} for c in CTF_CHALLENGES]


def get_ctf_challenge(cid, reveal_fix=False):
    for c in CTF_CHALLENGES:
        if c["id"] == cid:
            out = {"id": c["id"], "title": c["title"], "difficulty": c["difficulty"],
                   "vulnerable_code": c["vulnerable_code"], "hint": c["hint"]}
            if reveal_fix:
                out["fixed_code"] = c["fixed_code"]
            return out
    return None


def check_ctf_answer(cid, user_code):
    """Verificação heurística simples: procura se o padrão perigoso ainda está presente."""
    c = next((x for x in CTF_CHALLENGES if x["id"] == cid), None)
    if not c:
        return {"error": "desafio não encontrado"}
    from services.cyber import local as local_mod
    scan = local_mod.scan_code(user_code or "", filename=f"{cid}.py")
    solved = len(scan["findings"]) == 0
    return {"solved": solved, "remaining_findings": scan["findings"],
            "message": "Parabéns, nenhum padrão perigoso detectado!" if solved else
                       "Ainda há padrão(ões) de risco no seu código — veja os achados."}


# ---------------------------------------------------------------- Analisador de Força de Senha (educacional)
COMMON_PASSWORDS = {
    "123456", "password", "123456789", "12345678", "qwerty", "abc123", "senha", "senha123",
    "admin", "admin123", "123123", "letmein", "welcome", "iloveyou", "111111", "12345",
    "brasil", "vasco", "flamengo", "corinthians", "password1", "1q2w3e4r",
}


def analyze_password_strength(pwd: str):
    pwd = pwd or ""
    findings = []
    score = 0
    length = len(pwd)
    if length == 0:
        return {"score": 0, "label": "vazia", "findings": [F("pwd.empty", "Senha vazia", "critical", evidence="—",
                impact="Sem senha não há autenticação.", fix="Defina uma senha.")]}
    if length < 8:
        findings.append(F("pwd.short", "Senha curta (menos de 8 caracteres)", "high",
                          evidence=f"{length} caractere(s)", impact="Suscetível a força bruta rápida.",
                          fix="Use pelo menos 12 caracteres, idealmente uma frase-senha."))
    else:
        score += min(length, 20)
    classes = sum([bool(re.search(r"[a-z]", pwd)), bool(re.search(r"[A-Z]", pwd)),
                   bool(re.search(r"\d", pwd)), bool(re.search(r"[^a-zA-Z0-9]", pwd))])
    score += classes * 10
    if classes < 3:
        findings.append(F("pwd.low_variety", "Pouca variedade de caracteres", "medium",
                          evidence=f"{classes}/4 classes (minúsculas/maiúsculas/números/símbolos)",
                          impact="Reduz o espaço de busca de um ataque de força bruta.",
                          fix="Combine maiúsculas, minúsculas, números e símbolos."))
    if pwd.lower() in COMMON_PASSWORDS:
        findings.append(F("pwd.common", "Senha está em lista de senhas comuns", "critical",
                          evidence="presente em wordlist pública conhecida",
                          impact="É a primeira tentativa de qualquer ataque de dicionário.",
                          fix="Troque imediatamente por uma senha única e forte."))
        score = min(score, 10)
    if re.search(r"(.)\1{2,}", pwd):
        findings.append(F("pwd.repeat", "Caracteres repetidos em sequência", "low", evidence="ex.: 'aaa', '111'",
                          impact="Padrão previsível.", fix="Evite repetições."))
    if re.search(r"(?i)(123|abc|qwe|senha|password)", pwd):
        findings.append(F("pwd.pattern", "Contém padrão de teclado/palavra previsível", "medium",
                          evidence="padrão sequencial ou palavra comum embutida",
                          impact="Reduz drasticamente o espaço de busca.", fix="Evite sequências e palavras de dicionário."))
    ent = _entropy(pwd) * length  # entropia aproximada total em bits
    score = max(0, min(100, score))
    label = "muito fraca" if score < 25 else "fraca" if score < 50 else "razoável" if score < 75 else "forte"
    return {"score": score, "label": label, "approx_entropy_bits": round(ent, 1), "findings": findings}


def _entropy(s):
    if not s:
        return 0
    from collections import Counter
    c = Counter(s)
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in c.values())

# ---------------------------------------------------------------- Scanner de padrões de malware em texto (forense/YARA-lite)
MALWARE_STRING_RULES = [
    ("webshell_php", "critical", r"(?i)(eval\s*\(\s*\$_(?:GET|POST|REQUEST)|base64_decode\s*\(\s*\$_|assert\s*\(\s*\$_)",
     "Padrão de webshell PHP", "Código executa entrada do usuário diretamente (backdoor comum em sites comprometidos)."),
    ("obfuscated_js", "high", r"(?i)(eval\s*\(\s*(atob|unescape|String\.fromCharCode)\s*\()",
     "JavaScript ofuscado com eval", "Técnica comum para esconder payload malicioso em página comprometida."),
    ("powershell_encoded", "high", r"(?i)powershell.{0,20}-enc(odedcommand)?\s+[A-Za-z0-9+/=]{20,}",
     "Comando PowerShell codificado em Base64", "Técnica comum de evasão em malware/scripts maliciosos."),
    ("cmd_download_exec", "critical", r"(?i)(certutil.{0,20}-urlcache|iwr\s|invoke-webrequest|wget\s+http.{0,10}\|\s*sh|curl\s+http.{0,10}\|\s*(sh|bash))",
     "Padrão de download+execução remota", "Técnica comum de dropper/stage 2 de malware."),
    ("suspicious_useragent", "medium", r"(?i)(sqlmap|nikto|nmap scripting engine|masscan|zgrab)",
     "User-Agent de ferramenta de varredura/exploração", "Indica reconhecimento ou ataque automatizado em andamento (verifique se foi autorizado por você)."),
    ("crypto_miner", "high", r"(?i)(stratum\+tcp://|xmrig|cryptonight)",
     "Indício de cryptominer", "Pode indicar comprometimento usando recursos para minerar criptomoeda."),
]


def scan_malware_patterns(text: str, filename=""):
    findings = []
    for n, line in enumerate((text or "").splitlines(), 1):
        for rule, sev, pat, title, impact in MALWARE_STRING_RULES:
            if re.search(pat, line):
                findings.append(F(f"malware.{rule}", title, sev,
                                  evidence=f"{filename or 'texto'}:{n}: {line.strip()[:140]}",
                                  impact=impact,
                                  fix="Isole o arquivo/host, preserve evidência e siga o playbook de IR 'web_compromise'.",
                                  where=f"{filename}:{n}:{rule}"))
    return {"findings": findings, "raw": {"lines": len((text or "").splitlines())}}


# ---------------------------------------------------------------- Nota (grade) de segurança para headers
def headers_letter_grade(findings: list):
    sev_weight = {"critical": 30, "high": 20, "medium": 10, "low": 4, "info": 0}
    penalty = sum(sev_weight.get(f.get("severity", "info"), 0) for f in findings)
    score = max(0, 100 - penalty)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 55 else "D" if score >= 35 else "F"
    return {"score": score, "grade": grade}

def compute_security_score(all_findings: list):
    weights = {"critical": 25, "high": 12, "medium": 5, "low": 2, "info": 0}
    penalty = sum(weights.get((f.get("severity") or "info").lower(), 0) for f in all_findings)
    score = max(0, 100 - penalty)
    risk = "crítico" if score < 40 else "alto" if score < 60 else "médio" if score < 80 else "baixo"
    return {"score": score, "risk": risk, "total_findings": len(all_findings)}


def generate_audit_report(all_findings: list, fmt="markdown", target="aplicação"):
    sec = compute_security_score(all_findings)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if fmt == "json":
        return json.dumps({"target": target, "generated_at": ts, "security_score": sec,
                           "findings": all_findings}, ensure_ascii=False, indent=2)
    if fmt == "html":
        esc = lambda v: str(v or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
        by_sev = {}
        for f in all_findings:
            by_sev.setdefault((f.get("severity") or "info").lower(), []).append(f)
        order = ["critical", "high", "medium", "low", "info"]
        blocks = []
        for sev in order:
            items = by_sev.get(sev, [])
            if not items:
                continue
            cards = "".join(
                f"<article class='finding'><h3>{esc(f.get('title'))}</h3>"
                f"<p><b>Severidade:</b> {esc(sev)} · <b>Local:</b> {esc(f.get('where'))}</p>"
                f"<p><b>Evidência:</b> {esc(f.get('evidence'))}</p>"
                f"<p><b>Impacto:</b> {esc(f.get('impact'))}</p>"
                f"<p><b>Correção:</b> {esc(f.get('fix'))}</p></article>"
                for f in items
            )
            blocks.append(f"<section><h2>{esc(sev.upper())} ({len(items)})</h2>{cards}</section>")
        return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Relatório de Segurança — {esc(target)}</title><style>
body{{font-family:Inter,Arial,sans-serif;background:#07101d;color:#eef4ff;max-width:1000px;margin:auto;padding:32px;line-height:1.55}}
h1{{color:#00e5ff}}section{{margin:24px 0}}.finding{{background:#101c30;border:1px solid #263b58;border-radius:12px;padding:16px;margin:10px 0}}
small,.muted{{color:#9aacc7}}.score{{font-size:28px;font-weight:800}}
</style></head><body><h1>Relatório de Auditoria de Segurança</h1><p><b>Alvo:</b> {esc(target)}</p>
<p><b>Gerado em:</b> {esc(ts)}</p><p class='score'>Security Score: {sec['score']}/100</p><p>{sec['total_findings']} achado(s) · risco {esc(sec['risk'])}</p>
{''.join(blocks) if blocks else '<p>Nenhum achado registrado.</p>'}</body></html>"""
    # markdown
    by_sev = {}
    for f in all_findings:
        by_sev.setdefault((f.get("severity") or "info").lower(), []).append(f)
    order = ["critical", "high", "medium", "low", "info"]
    lines = [f"# Relatório de Auditoria de Segurança — {target}", "",
             f"**Gerado em:** {ts}  ", f"**Security Score:** {sec['score']}/100 (risco {sec['risk']})  ",
             f"**Total de achados:** {sec['total_findings']}", ""]
    for sev in order:
        items = by_sev.get(sev, [])
        if not items:
            continue
        lines.append(f"## {sev.upper()} ({len(items)})")
        for f in items:
            lines.append(f"- **{f.get('title','(sem título)')}** — {f.get('evidence','')}")
            if f.get("impact"):
                lines.append(f"  - Impacto: {f['impact']}")
            if f.get("fix"):
                lines.append(f"  - Correção: {f['fix']}")
        lines.append("")
    lines.append("## Recomendações gerais")
    lines.append("- Priorize achados CRITICAL e HIGH primeiro.")
    lines.append("- Reexecute a auditoria após aplicar correções para validar o novo score.")
    return "\n".join(lines)

# ------------------------------------------------------------------
# V29 defensive analyzers (texto local; sem tráfego e sem execução)
def analyze_csp_policy(policy: str):
    text = (policy or "").strip()
    low = text.lower()
    findings = []
    if not text:
        findings.append(F("csp.empty", "CSP ausente", "high", evidence="nenhuma política fornecida",
                          impact="O navegador não recebe uma política de conteúdo deste input.",
                          fix="Defina uma CSP explícita e restritiva para a aplicação.", where="csp"))
        return {"findings": findings, "raw": {"directives": []}}
    directives = {}
    for part in text.split(";"):
        bits = part.strip().split()
        if bits:
            directives[bits[0].lower()] = bits[1:]
    if "default-src" not in directives:
        findings.append(F("csp.default_src", "default-src ausente", "medium", evidence="diretiva não encontrada",
                          impact="Recursos sem diretiva específica ficam menos previsíveis.",
                          fix="Defina default-src 'self' como base e sobrescreva apenas o necessário.", where="csp:default-src"))
    if "'unsafe-inline'" in low:
        findings.append(F("csp.unsafe_inline", "CSP permite unsafe-inline", "medium", evidence="'unsafe-inline' encontrado",
                          impact="Scripts/estilos inline podem ampliar o impacto de XSS.",
                          fix="Prefira arquivos externos, nonce ou hashes.", where="csp:unsafe-inline"))
    if "'unsafe-eval'" in low:
        findings.append(F("csp.unsafe_eval", "CSP permite unsafe-eval", "medium", evidence="'unsafe-eval' encontrado",
                          impact="APIs que avaliam strings ampliam a superfície de execução.",
                          fix="Remova se nenhuma biblioteca legítima exigir avaliação dinâmica.", where="csp:unsafe-eval"))
    if "*" in directives.get("script-src", []) or "*" in directives.get("default-src", []):
        findings.append(F("csp.wildcard", "CSP usa wildcard", "medium", evidence="* em script-src/default-src",
                          impact="Origens arbitrárias podem fornecer conteúdo ativo.",
                          fix="Use allowlist explícita de origens necessárias.", where="csp:wildcard"))
    if "object-src" not in directives or "'none'" not in directives.get("object-src", []):
        findings.append(F("csp.object_src", "object-src não está bloqueado", "low", evidence="object-src não contém 'none'",
                          impact="Conteúdo legado baseado em plugins recebe mais liberdade.",
                          fix="Use object-src 'none' quando plugins não forem necessários.", where="csp:object-src"))
    return {"findings": findings, "raw": {"directives": directives}}


def analyze_cookie_headers(headers_text: str):
    text = headers_text or ""
    cookies = re.findall(r"(?im)^set-cookie:\s*(.+)$", text)
    findings = []
    for idx, cookie in enumerate(cookies, 1):
        low = cookie.lower()
        name = cookie.split("=", 1)[0].strip() or f"cookie-{idx}"
        if "secure" not in low:
            findings.append(F("cookie.secure", f"Cookie {name} sem Secure", "medium", evidence=cookie[:180],
                              impact="Pode ser enviado por HTTP se o navegador permitir.",
                              fix="Adicione Secure em produção HTTPS.", where=f"cookie:{name}"))
        if "httponly" not in low:
            findings.append(F("cookie.httponly", f"Cookie {name} sem HttpOnly", "medium", evidence=cookie[:180],
                              impact="JavaScript pode acessar o cookie, aumentando o impacto de XSS.",
                              fix="Adicione HttpOnly quando o cookie não precisar ser lido pelo JavaScript.", where=f"cookie:{name}"))
        if "samesite" not in low:
            findings.append(F("cookie.samesite", f"Cookie {name} sem SameSite", "low", evidence=cookie[:180],
                              impact="Menos proteção contra envio cross-site.",
                              fix="Defina SameSite=Lax ou Strict conforme o fluxo.", where=f"cookie:{name}"))
    return {"findings": findings, "raw": {"cookies": len(cookies)}}


def audit_dockerfile(text: str):
    src = text or ""
    low = src.lower()
    findings = []
    if re.search(r"(?m)^\s*from\s+[^\n:]+:latest\s*$", low):
        findings.append(F("docker.latest", "Imagem Docker usa latest", "medium", evidence="FROM ...:latest",
                          impact="Builds podem mudar sem revisão.", fix="Use uma tag de versão ou digest revisado.", where="Dockerfile:FROM"))
    if not re.search(r"(?m)^\s*user\s+[^#\s]+", low):
        findings.append(F("docker.root", "Container não declara USER", "medium", evidence="nenhuma instrução USER encontrada",
                          impact="A aplicação pode iniciar como root dependendo da imagem.", fix="Crie um usuário sem privilégios e use USER.", where="Dockerfile:USER"))
    if re.search(r"(?m)^\s*add\s+", low):
        findings.append(F("docker.add", "Dockerfile usa ADD", "low", evidence="instrução ADD encontrada",
                          impact="ADD tem semântica extra de arquivos/URLs que pode surpreender.", fix="Prefira COPY quando não precisar da semântica do ADD.", where="Dockerfile:ADD"))
    if "--privileged" in low:
        findings.append(F("docker.privileged", "Execução privilegiada detectada", "high", evidence="--privileged encontrado",
                          impact="Aumenta muito o acesso do container ao host.", fix="Remova --privileged e conceda somente capacidades estritamente necessárias.", where="Dockerfile/runtime"))
    return {"findings": findings, "raw": {"has_user": bool(re.search(r"(?m)^\s*user\s+", low)), "has_latest": ":latest" in low}}


def audit_github_actions(text: str):
    src = text or ""
    low = src.lower()
    findings = []
    if "permissions:" not in low:
        findings.append(F("ci.permissions", "Workflow não declara permissions", "medium", evidence="permissions ausente",
                          impact="O token GITHUB_TOKEN pode receber permissões além do necessário.",
                          fix="Declare permissions mínimas no workflow.", where="workflow:permissions"))
    if re.search(r"(?m)^\s*permissions:\s*write-all", low):
        findings.append(F("ci.write_all", "Workflow usa write-all", "high", evidence="permissions: write-all",
                          impact="Concede amplo acesso de escrita ao token do workflow.", fix="Use somente permissões necessárias por job.", where="workflow:permissions"))
    if "pull_request_target" in low and "secrets." in low:
        findings.append(F("ci.pr_target_secrets", "pull_request_target combinado com secrets", "high", evidence="ambos encontrados",
                          impact="Código controlado por PR pode ganhar caminho até secrets dependendo do workflow.",
                          fix="Revise cuidadosamente checkout, origem do código e uso de secrets em pull_request_target.", where="workflow:trigger"))
    if re.search(r"uses:\s+[^@\s]+@main", low):
        findings.append(F("ci.action_branch", "Action referenciada por branch", "low", evidence="uses: ...@main",
                          impact="Uma mudança upstream altera o workflow sem revisão local.", fix="Fixe uma versão/tag/digest revisado.", where="workflow:uses"))
    return {"findings": findings, "raw": {"checks": 4}}


def analyze_api_security_text(text: str):
    src = text or ""
    low = src.lower()
    findings = []
    checks = [
        ("api.auth", "Autenticação não evidenciada", "high", r"(authenticate|login_required|bearer|oauth|session)", "Exija identidade antes de expor dados sensíveis.") ,
        ("api.authorization", "Autorização não evidenciada", "high", r"(authorize|permission|role|owner_id|tenant_id|capability)", "Cheque permissão no backend para cada objeto/ação sensível."),
        ("api.rate_limit", "Rate limit não evidenciado", "medium", r"(rate.?limit|limiter|429|throttle)", "Aplique limite no servidor para endpoints sensíveis."),
        ("api.validation", "Validação de entrada não evidenciada", "medium", r"(schema|validate|pydantic|marshmallow|allowlist|sanitize)", "Valide tipo, tamanho e valores permitidos no backend."),
        ("api.error_leak", "Tratamento de erro precisa de revisão", "low", r"(traceback|stacktrace|debug|exception)", "Não devolva stack traces/segredos ao cliente."),
    ]
    for rid,title,sev,pattern,fix in checks:
        if not re.search(pattern, low):
            findings.append(F(rid,title,sev,evidence="padrão defensivo não encontrado no texto fornecido",
                              impact="O controle pode existir em outra camada; este analisador não o encontrou aqui.", fix=fix, where="api-text"))
    return {"findings": findings, "raw": {"checks": len(checks)}}
