"""Analisadores que operam sobre TEXTO/ARQUIVOS fornecidos (sem rede):
segredos, código-fonte, dependências, logs, configurações."""
import json
import math
import re
from collections import Counter

from services.evidence import make_finding as F

MAX_CHARS = 400_000


def _mask(s, keep=4):
    s = s.strip()
    return s[:keep] + "…" + "*" * 6 if len(s) > keep else "*" * len(s)


def _lines(text):
    return text[:MAX_CHARS].splitlines()


def _entropy(s):
    if not s:
        return 0
    c = Counter(s)
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in c.values())


# ---------------------------------------------------------------- segredos
SECRET_RULES = [
    ("aws_access_key", "critical", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b", "Chave de acesso AWS"),
    ("private_key", "critical", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----", "Chave privada"),
    ("github_token", "critical", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "Token do GitHub"),
    ("slack_token", "high", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "Token do Slack"),
    ("google_api_key", "high", r"\bAIza[0-9A-Za-z_\-]{35}\b", "Chave de API do Google"),
    ("stripe_live", "critical", r"\bsk_live_[0-9a-zA-Z]{20,}\b", "Chave secreta Stripe (live)"),
    ("openai_key", "critical", r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}\b", "Chave de API tipo OpenAI"),
    ("jwt", "medium", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b", "JWT embutido"),
    ("db_url_password", "high", r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s/@]+:[^@\s]{3,}@", "String de conexão com senha"),
    ("generic_assign", "high",
     r"""(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*["']([^"'\s]{8,})["']""",
     "Credencial atribuída em texto"),
]
PLACEHOLDER = re.compile(r"(?i)^(x+|\*+|changeme|example|your[_-]?|<.*>|\$\{.*\}|process\.env|os\.environ|todo|test|dummy|senha|password)")


def scan_secrets(text, filename=""):
    findings, seen = [], set()
    for n, line in enumerate(_lines(text), 1):
        for rule, sev, pat, label in SECRET_RULES:
            m = re.search(pat, line)
            if not m:
                continue
            val = m.group(1) if m.groups() else m.group(0)
            if rule == "generic_assign" and (PLACEHOLDER.match(val) or _entropy(val) < 2.5):
                continue
            key = (rule, n)
            if key in seen:
                continue
            seen.add(key)
            findings.append(F(
                f"secret.{rule}", f"{label} exposto", sev,
                evidence=f"{filename or 'texto'}:{n}: {_mask(val)}",
                impact="Quem tiver acesso ao código/repositório pode usar essa credencial.",
                fix="Revogue/rotacione a credencial AGORA, remova do código (e do histórico git) e "
                    "carregue de variável de ambiente ou cofre de segredos.",
                where=f"{filename}:{n}:{rule}"))
    return {"findings": findings, "raw": {"lines": len(_lines(text)), "file": filename}}


# ---------------------------------------------------------------- código-fonte
CODE_RULES = [
    ("code.eval", "high", r"\beval\s*\(", "Uso de eval()", "Executa texto como código; injeção se houver entrada do usuário.", "Evite eval; use parsing seguro (json.loads, ast.literal_eval)."),
    ("code.exec", "high", r"\bexec\s*\(", "Uso de exec()", "Execução dinâmica de código.", "Remova ou isole."),
    ("code.shell_true", "high", r"subprocess\.\w+\([^)]*shell\s*=\s*True", "subprocess com shell=True", "Injeção de comando via entrada não sanitizada.", "Use lista de argumentos e shell=False."),
    ("code.os_system", "high", r"\bos\.(system|popen)\s*\(", "os.system/os.popen", "Injeção de comando.", "Use subprocess.run([...], shell=False)."),
    ("code.pickle", "high", r"\bpickle\.loads?\s*\(", "pickle.load em dados", "Desserialização insegura leva a execução de código.", "Use JSON ou formatos seguros."),
    ("code.yaml_load", "medium", r"\byaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)", "yaml.load sem SafeLoader", "Desserialização insegura.", "Use yaml.safe_load."),
    ("code.sql_concat", "high", r"""(?i)\b(execute|executemany|query|raw)\s*\(\s*(?:f["'][^"']*\b(?:select|insert|update|delete)\b[^"']*\{|["'][^"']*\b(?:select|insert|update|delete)\b[^"']*["']\s*(?:%|\+|\.format\())""", "SQL montado por concatenação/formatação", "SQL Injection.", "Use consultas parametrizadas (placeholders)."),
    ("code.innerhtml", "medium", r"\.(innerHTML|outerHTML)\s*=|document\.write\s*\(", "innerHTML/document.write", "XSS quando o conteúdo vem do usuário.", "Use textContent ou sanitize (DOMPurify)."),
    ("code.md5_sha1", "medium", r"\b(md5|sha1)\s*\(|hashlib\.(md5|sha1)\b", "Hash fraco (MD5/SHA1)", "Colisões; inadequado para senhas.", "Use bcrypt/argon2 para senhas e SHA-256+ para integridade."),
    ("code.verify_false", "medium", r"verify\s*=\s*False", "Verificação TLS desativada", "Permite man-in-the-middle.", "Remova verify=False."),
    ("code.debug_true", "medium", r"(?i)\bdebug\s*=\s*True\b|app\.run\([^)]*debug\s*=\s*True", "Debug ativado", "Expõe console/stack traces.", "Desative debug em produção."),
    ("code.weak_random", "low", r"\brandom\.(random|randint|choice)\s*\(", "random não-criptográfico", "Previsível se usado para tokens/senhas.", "Use secrets."),
    ("code.jwt_none", "high", r"(?i)algorithms?\s*=\s*\[?\s*[\"']none[\"']|verify_signature[\"']?\s*:\s*False", "JWT sem verificação de assinatura", "Tokens forjáveis.", "Sempre verifique a assinatura e fixe o algoritmo."),
    ("code.cors_any", "medium", r"(?i)Access-Control-Allow-Origin[\"']?\s*[,:]\s*[\"']\*|CORS\(\s*app\s*\)", "CORS aberto para qualquer origem", "Qualquer site lê respostas da API.", "Restrinja a origens confiáveis."),
    ("code.secret_default", "high", r"(?i)secret_key\s*=\s*[\"'][^\"']{0,40}[\"']", "SECRET_KEY fixa no código", "Sessões forjáveis se a chave vazar.", "Leia de variável de ambiente."),
    ("code.no_csrf", "info", r"(?i)csrf_exempt|WTF_CSRF_ENABLED\s*=\s*False", "CSRF desativado", "Requisições forjadas.", "Reative a proteção CSRF."),
    ("auth.plain_password", "high", r"(?i)password\s*==\s*[\"']|check.*password.*==", "Comparação de senha em texto", "Senha armazenada/comparada sem hash.", "Use hash com salt (werkzeug.security/bcrypt) e compare com função constante."),
    ("auth.hardcoded_admin", "medium", r"(?i)(user(name)?|login)\s*==\s*[\"']admin[\"']", "Usuário admin fixo", "Facilita adivinhação.", "Use papéis/permissões no backend."),
]


def scan_code(text, filename=""):
    findings = []
    for n, line in enumerate(_lines(text), 1):
        stripped = line.strip()
        if stripped.startswith(("#", "//", "*")):
            continue
        for rule, sev, pat, title, impact, fix in CODE_RULES:
            if re.search(pat, line):
                findings.append(F(rule, title, sev, evidence=f"{filename or 'texto'}:{n}: {stripped[:140]}",
                                  impact=impact, fix=fix, where=f"{filename}:{n}:{rule}"))
    return {"findings": findings, "raw": {"lines": len(_lines(text)), "file": filename}}


# ---------------------------------------------------------------- dependências
def parse_dependencies(text, filename=""):
    deps = []
    name = filename.lower()
    if name.endswith("package.json") or text.lstrip().startswith("{"):
        try:
            d = json.loads(text)
            for sect in ("dependencies", "devDependencies"):
                for k, v in (d.get(sect) or {}).items():
                    deps.append(("npm", k, v))
        except Exception:
            pass
    else:
        for line in _lines(text):
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(==|>=|<=|~=|>|<|!=)?\s*([\w.\-*]+)?", line)
            if m:
                deps.append(("PyPI", m.group(1).split("[")[0], (m.group(2) or "") + (m.group(3) or "")))
    return deps


def scan_dependencies(text, filename="", check_osv=False):
    deps = parse_dependencies(text, filename)
    findings = []
    for eco, name, ver in deps:
        pinned = ver.startswith("==") or re.match(r"^\d", ver or "")
        if not ver or ver in ("*", "latest") or ver.startswith(("^", "~", ">", "<")) and eco == "npm":
            findings.append(F("deps.unpinned", f"Dependência sem versão fixa: {name}", "low",
                              evidence=f"{name} {ver or '(sem versão)'}",
                              impact="Builds não reprodutíveis; risco de puxar versão comprometida.",
                              fix="Fixe a versão exata e use lockfile.", where=f"dep:{name}"))
        elif eco == "PyPI" and not pinned:
            findings.append(F("deps.unpinned", f"Dependência sem versão fixa: {name}", "low",
                              evidence=f"{name} {ver}", impact="Builds não reprodutíveis.",
                              fix="Use ==versão.", where=f"dep:{name}"))
    vulns = []
    osv_error = None
    if check_osv:
        try:
            import urllib.request
            queries = []
            for eco, name, ver in deps[:100]:
                v = re.sub(r"^[^\d]*", "", ver or "")
                if v:
                    queries.append({"package": {"name": name, "ecosystem": eco}, "version": v})
            if queries:
                req = urllib.request.Request("https://api.osv.dev/v1/querybatch",
                                             data=json.dumps({"queries": queries}).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    osv = json.loads(resp.read())
                for q, res in zip(queries, osv.get("results", [])):
                    for vuln in res.get("vulns", []) or []:
                        vulns.append({"package": q["package"]["name"], "version": q["version"], "id": vuln["id"]})
                        findings.append(F("deps.vuln", f"Vulnerabilidade conhecida em {q['package']['name']} {q['version']}",
                                          "high", evidence=vuln["id"] + " (OSV.dev)",
                                          impact="Versão com falha de segurança publicada.",
                                          fix="Atualize para uma versão corrigida (veja o aviso no OSV.dev).",
                                          where=f"dep:{q['package']['name']}:{vuln['id']}", ref=f"https://osv.dev/{vuln['id']}"))
        except Exception as e:
            osv_error = f"Consulta OSV.dev indisponível: {str(e)[:100]}"
    return {"findings": findings, "raw": {"dependencies": [{"eco": e, "name": n, "version": v} for e, n, v in deps],
                                          "vulns": vulns, "osv_checked": check_osv, "osv_error": osv_error}}


# ---------------------------------------------------------------- logs
_ACCESS = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) ')
ATTACK_PATTERNS = [
    ("sqli", r"(?i)(union(\s|%20|\+)+select|or(\s|%20|\+)+1(\s|%20|\+)*=(\s|%20|\+)*1|sleep\(\d|information_schema)", "Padrão de SQL Injection"),
    ("xss", r"(?i)(<script|%3Cscript|javascript:|onerror=)", "Padrão de XSS"),
    ("traversal", r"(\.\./|%2e%2e%2f|/etc/passwd)", "Path traversal"),
    ("scanner", r"(?i)(wp-login|xmlrpc\.php|/\.env|/\.git/|phpmyadmin|/admin\.php|/cgi-bin/)", "Sondagem de caminhos sensíveis"),
]


def analyze_logs(text):
    findings, ips_4xx, ips_ssh_fail, attacks = [], Counter(), Counter(), Counter()
    status = Counter()
    total = 0
    for line in _lines(text):
        total += 1
        m = _ACCESS.match(line)
        if m:
            ip, method, path, code = m.groups()
            status[code[0] + "xx"] += 1
            if code.startswith("4"):
                ips_4xx[ip] += 1
            for key, pat, label in ATTACK_PATTERNS:
                if re.search(pat, path):
                    attacks[(key, ip, label)] += 1
        sm = re.search(r"Failed password for (?:invalid user )?(\S+) from (\S+)", line)
        if sm:
            ips_ssh_fail[sm.group(2)] += 1
    for ip, n in ips_ssh_fail.items():
        if n >= 5:
            findings.append(F("logs.ssh_bruteforce", f"Possível força bruta SSH de {ip}", "high" if n >= 20 else "medium",
                              evidence=f"{n} falhas de senha", impact="Tentativas repetidas de adivinhar credenciais.",
                              fix="Use chaves SSH, desative senha, fail2ban/rate-limit e bloqueie o IP.", where=f"ssh:{ip}"))
    for ip, n in ips_4xx.items():
        if n >= 30:
            findings.append(F("logs.many_4xx", f"Muitos erros 4xx de {ip}", "medium", evidence=f"{n} respostas 4xx",
                              impact="Típico de varredura/enumeração.", fix="Rate limiting e WAF.", where=f"4xx:{ip}"))
    for (key, ip, label), n in attacks.items():
        findings.append(F(f"logs.{key}", f"{label} vindo de {ip}", "medium" if key != "scanner" else "low",
                          evidence=f"{n} requisição(ões) suspeita(s)", impact="Tentativa de exploração ou reconhecimento.",
                          fix="Confirme que a aplicação valida entradas; considere WAF e bloqueio do IP.", where=f"{key}:{ip}"))
    return {"findings": findings, "raw": {"lines": total, "status": dict(status),
            "top_4xx_ips": ips_4xx.most_common(5), "ssh_failures": ips_ssh_fail.most_common(5)}}


# ---------------------------------------------------------------- configs
def audit_config(text, kind="auto"):
    findings = []
    low = text.lower()
    if kind == "auto":
        kind = "sshd" if "permitrootlogin" in low or "passwordauthentication" in low else \
               "nginx" if "server {" in low or "server_tokens" in low or "listen " in low else \
               "env" if re.search(r"^\w+=", text, re.M) else "generic"

    def add(rule, title, sev, ev, impact, fix):
        findings.append(F(f"config.{kind}.{rule}", title, sev, evidence=ev, impact=impact, fix=fix, where=f"{kind}:{rule}"))

    if kind == "sshd":
        if re.search(r"(?im)^\s*PermitRootLogin\s+yes", text):
            add("rootlogin", "SSH permite login como root", "high", "PermitRootLogin yes", "Alvo direto de força bruta.", "PermitRootLogin no")
        if re.search(r"(?im)^\s*PasswordAuthentication\s+yes", text):
            add("passauth", "SSH aceita senha", "medium", "PasswordAuthentication yes", "Força bruta contra senhas.", "Use chaves e PasswordAuthentication no")
        if re.search(r"(?im)^\s*PermitEmptyPasswords\s+yes", text):
            add("emptypass", "SSH aceita senha vazia", "critical", "PermitEmptyPasswords yes", "Login sem senha.", "PermitEmptyPasswords no")
        if re.search(r"(?im)^\s*Protocol\s+1", text):
            add("proto1", "SSH protocolo 1", "critical", "Protocol 1", "Protocolo quebrado.", "Use somente protocolo 2.")
    elif kind == "nginx":
        if "server_tokens off" not in low:
            add("tokens", "nginx expõe versão", "low", "server_tokens não está off", "Facilita fingerprint.", "server_tokens off;")
        if re.search(r"ssl_protocols[^;]*TLSv1(\s|;)|ssl_protocols[^;]*TLSv1\.1", text):
            add("tls_old", "nginx habilita TLS antigo", "high", "ssl_protocols com TLSv1/1.1", "Downgrade.", "ssl_protocols TLSv1.2 TLSv1.3;")
        if "autoindex on" in low:
            add("autoindex", "Listagem de diretórios ativa", "medium", "autoindex on", "Expõe arquivos.", "autoindex off;")
        if "add_header strict-transport-security" not in low and "ssl" in low:
            add("hsts", "HSTS ausente na config", "low", "sem add_header Strict-Transport-Security", "Downgrade.", 'add_header Strict-Transport-Security "max-age=31536000" always;')
    elif kind == "env":
        for n, line in enumerate(_lines(text), 1):
            if re.match(r"(?i)^\s*(DEBUG|FLASK_DEBUG)\s*=\s*(1|true)", line):
                add(f"debug{n}", "Debug ligado", "medium", line.strip(), "Vaza detalhes internos.", "Desligue em produção.")
            if re.match(r"(?i)^\s*\w*(SECRET|KEY|PASSWORD|TOKEN)\w*\s*=\s*\S{4,}", line) and "example" not in low:
                add(f"secret{n}", "Segredo em arquivo .env", "info", line.split("=")[0] + "=…", "Não versionar .env.", "Adicione .env ao .gitignore e use cofre em produção.")
    else:
        if re.search(r"(?i)password\s*[:=]\s*(admin|root|123|password|senha)\b", text):
            add("weakpw", "Senha padrão/fraca na config", "high", "senha padrão encontrada", "Acesso trivial.", "Defina senha forte e única.")
    return {"findings": findings, "raw": {"kind": kind}}
