"""Security Center for sites generated/managed by Tristan Thorne.

Static, evidence-based checks only: never executes site code and never makes
network requests. Network scanners remain in tool_adapter + scope.
"""
import json
import os
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone

from services import sites_service as sites
from services.cyber import local
from services.evidence import make_finding, risk_score, risk_label

TEXT_EXT = {".html", ".js", ".css", ".json", ".yml", ".yaml", ".toml", ".env", ".txt", ".md", ".py"}
MAX_FILE = 400_000
MAX_HISTORY = 20


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE]
    except Exception:
        return ""


def _files(folder):
    for p in Path(folder).rglob("*"):
        if not p.is_file() or "node_modules" in p.parts or ".git" in p.parts:
            continue
        if p.suffix.lower() in TEXT_EXT or p.name in {"Procfile", "_headers", "netlify.toml"}:
            yield p


def _f(rule, title, severity, evidence, impact, fix, where, status="confirmed", autofix=False):
    f = make_finding(rule, title, severity, evidence=evidence, impact=impact, fix=fix, where=where)
    f.update({"status": status, "autofix": autofix})
    return f


def _review(rule, title, evidence, fix, where):
    return _f(rule, title, "info", evidence, "Não há evidência suficiente para confirmar uma vulnerabilidade.",
              fix, where, status="needs_review")


def _dedupe(findings):
    out, seen = [], set()
    for f in findings:
        key = f["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def scan_site(slug):
    folder = sites.SITES_DIR / slug
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Site não encontrado.")
    meta = sites.load_metadata(folder) or {}
    findings = []
    files = list(_files(folder))
    fmap = {str(p.relative_to(folder)): _read(p) for p in files}
    all_text = "\n".join(f"\n# {k}\n{v}" for k, v in fmap.items())

    # Reuse the existing local analyzers for concrete source evidence.
    for rel, text in fmap.items():
        if rel.endswith((".py", ".js")):
            findings.extend(local.scan_code(text, rel)["findings"])
        if rel.endswith((".py", ".js", ".json", ".env", ".yml", ".yaml")):
            findings.extend(local.scan_secrets(text, rel)["findings"])
        if rel in {"requirements.txt", "package.json"}:
            findings.extend(local.scan_dependencies(text, rel)["findings"])

    # Web-specific evidence.
    for rel, text in fmap.items():
        if not rel.endswith((".html", ".js")):
            continue
        if re.search(r"\.(?:innerHTML|outerHTML)\s*=|document\.write\s*\(", text):
            findings.append(_f("web.xss_sink", "Possível sink de XSS no cliente", "medium",
                f"{rel}: foi encontrado innerHTML/outerHTML ou document.write.",
                "Se dados controlados por usuário chegam ao sink sem sanitização, HTML/JS pode ser injetado.",
                "Prefira textContent e sanitize conteúdo HTML confiável antes de inserir no DOM.", rel))
        if re.search(r"\beval\s*\(", text):
            findings.append(_f("web.eval", "Uso de eval()", "high", f"{rel}: eval() encontrado.",
                "Execução dinâmica pode transformar entrada não confiável em código.",
                "Remova eval e use parsing/estruturas de dados seguras.", rel))
        if re.search(r"<form\b[^>]*\bmethod\s*=\s*[\"']?post", text, re.I):
            if not re.search(r"csrf|xsrf|token", text, re.I):
                findings.append(_review("web.csrf_review", "Formulário POST requer revisão de CSRF",
                    f"{rel}: formulário POST sem indicador de token CSRF no conteúdo estático.",
                    "Confirme proteção CSRF no backend. Não é possível confirmar a ausência de proteção apenas pelo HTML.", rel))
        if re.search(r"\bfetch\s*\(|XMLHttpRequest|axios\.", text, re.I):
            findings.append(_review("web.api_review", "Código cliente acessa APIs — revisar autorização",
                f"{rel}: chamadas fetch/XHR/axios encontradas.",
                "Confirme autenticação, autorização, validação de entrada e tratamento de erros no backend das APIs.", rel))
        if re.search(r"document\.cookie", text, re.I):
            findings.append(_review("web.cookie_review", "Acesso a document.cookie requer revisão",
                f"{rel}: document.cookie encontrado.",
                "Confirme que cookies de sessão usam HttpOnly, Secure e SameSite quando aplicável.", rel))
        if re.search(r"<input\b[^>]*type\s*=\s*[\"']file", text, re.I):
            findings.append(_review("web.upload_review", "Upload de arquivo requer revisão de backend",
                f"{rel}: input type=file encontrado.",
                "Valide nome, tamanho, tipo real e conteúdo no backend; armazene uploads fora de diretórios executáveis.", rel))
        for m in re.finditer(r"<a\b[^>]*target\s*=\s*[\"']_blank[\"'][^>]*>", text, re.I):
            tag = m.group(0)
            if not re.search(r"rel\s*=", tag, re.I):
                line = text[:m.start()].count("\n") + 1
                findings.append(_f("web.target_blank", "Link target=_blank sem rel protetivo", "low",
                    f"{rel}:{line}: {tag[:180]}",
                    "Uma nova aba pode manter referência à página de origem via opener.",
                    "Adicione rel=\"noopener noreferrer\" ao link.", f"{rel}:{line}", autofix=True))
        for m in re.finditer(r"https?://[^\"'\s)]+", text, re.I):
            url = m.group(0)
            if url.lower().startswith("http://") and rel.endswith((".html", ".js", ".css")):
                findings.append(_f("web.mixed_content", "Recurso HTTP em arquivo web", "medium", f"{rel}: {url[:180]}",
                    "Recursos HTTP em páginas HTTPS podem permitir alteração de conteúdo em trânsito.",
                    "Use HTTPS para recursos externos quando o serviço oferecer HTTPS.", rel))

    # Security headers are deployment properties; source alone cannot prove absence.
    headers = fmap.get("_headers", "") + "\n" + fmap.get("netlify.toml", "")
    if not re.search(r"content-security-policy|Content-Security-Policy", headers, re.I):
        findings.append(_review("headers.csp_review", "CSP precisa ser confirmada no ambiente publicado",
            "Não há política CSP evidenciada nos arquivos de configuração do site.",
            "Configure CSP no servidor/host após verificar os recursos legítimos do site.", "_headers/netlify.toml"))
    if not re.search(r"strict-transport-security|Strict-Transport-Security", headers, re.I):
        findings.append(_review("headers.hsts_review", "HSTS precisa ser confirmado no ambiente HTTPS",
            "Não há HSTS evidenciado nos arquivos de configuração do site.",
            "Se o site for servido exclusivamente por HTTPS, avalie HSTS no ambiente de publicação.", "_headers/netlify.toml"))

    # Static sites do not expose server-side auth/SQL/path traversal semantics.
    if re.search(r"login|signin|sign-in|senha|password", all_text, re.I):
        findings.append(_review("auth.backend_review", "Fluxo de autenticação requer revisão de backend",
            "O conteúdo contém referências a login/autenticação, mas o scanner não executa o backend.",
            "Confirme hash de senha, sessão, autorização por rota e proteção contra brute force no backend.", "projeto"))
    if re.search(r"select\s+.+\s+from|insert\s+into|update\s+.+\s+set|delete\s+from", all_text, re.I):
        findings.append(_review("sqli.backend_review", "Código relacionado a SQL requer revisão",
            "Foram encontradas referências a comandos SQL, mas não foi confirmada uma concatenação vulnerável.",
            "Use queries parametrizadas e valide entradas no backend.", "projeto"))
    else:
        findings.append(_review("sqli.not_applicable", "SQL Injection não é determinável neste site estático",
            "Não foram encontrados comandos SQL no conteúdo analisado.",
            "Se existir backend/API, analise o código do backend separadamente.", "projeto"))
    if "debug=true" in all_text.lower() or "debug = true" in all_text.lower():
        findings.append(_f("config.debug", "Debug explicitamente ativado", "medium",
            "Foi encontrado debug=true no conteúdo do site.", "Mensagens de depuração podem expor informações internas.",
            "Desative debug em produção.", "projeto", autofix=True))

    # Positive checks: factual absence/presence, not a claim that the site is invulnerable.
    if not any(f["rule"] in {"secret.aws_access_key", "secret.private_key", "secret.github_token", "secret.google_api_key", "secret.stripe_live", "secret.openai_key", "secret.db_url_password"} for f in findings):
        findings.append(_f("secrets.clean", "Nenhum segredo conhecido foi detectado", "info",
            "Os padrões de segredos suportados pelo scanner não encontraram correspondências.",
            "Isso não prova ausência de todos os segredos possíveis.", "Revise manualmente arquivos sensíveis e histórico do repositório.", "projeto", status="pass"))

    findings = _dedupe(findings)
    confirmed = [f for f in findings if f.get("status") == "confirmed" and f.get("severity") != "info"]
    score = risk_score(confirmed)
    counts = {k: 0 for k in ("critical", "high", "medium", "low", "info")}
    status_counts = {k: 0 for k in ("confirmed", "needs_review", "pass")}
    for f in findings:
        counts[f["severity"]] += 1
        status_counts[f.get("status", "confirmed")] += 1
    return {
        "ok": True, "slug": slug, "site": meta.get("name", slug),
        "scope": "somente arquivos do site criado/gerenciado pelo Tristan Thorne",
        "files_scanned": len(files), "findings": findings, "counts": counts,
        "status_counts": status_counts, "score": score, "risk": risk_label(score),
        "note": "Resultados baseados em evidência estática. NEEDS REVIEW não significa vulnerabilidade confirmada.",
    }


def scan_and_store(slug):
    result = scan_site(slug)
    folder = sites.SITES_DIR / slug
    meta = sites.load_metadata(folder) or {}
    history = meta.get("security_scans") or []
    previous = history[-1] if history else None
    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "score": result["score"], "risk": result["risk"],
        "findings": result["findings"], "counts": result["counts"],
        "status_counts": result["status_counts"], "files_scanned": result["files_scanned"],
    }
    history.append(snapshot)
    meta["security_scans"] = history[-MAX_HISTORY:]
    meta["security_last_scan"] = snapshot["ts"]
    meta["security_score"] = result["score"]
    meta.pop("slug", None)
    sites.save_metadata(folder, meta)
    if previous:
        before = {f["id"]: f for f in previous.get("findings", []) if f.get("status") == "confirmed"}
        after = {f["id"]: f for f in result["findings"] if f.get("status") == "confirmed"}
        result["comparison"] = {
            "resolved": [before[k] for k in before if k not in after],
            "persistent": [after[k] for k in after if k in before],
            "new": [after[k] for k in after if k not in before],
            "before_score": previous.get("score", 0), "after_score": result["score"],
        }
    else:
        result["comparison"] = None
    return result


def apply_fix(slug, finding_id):
    folder = sites.SITES_DIR / slug
    result = scan_site(slug)
    finding = next((f for f in result["findings"] if f["id"] == finding_id), None)
    if not finding:
        raise ValueError("Achado não encontrado no scan atual.")
    if not finding.get("autofix"):
        raise ValueError("Este item não possui correção automática segura. Use 'Ver correção' e faça a alteração manualmente.")
    where = finding.get("where", "")
    rel = where.split(":", 1)[0]
    path = folder / rel
    text = _read(path)
    if finding["rule"] == "web.target_blank":
        new = re.sub(r'(<a\b[^>]*target\s*=\s*[\"\']_blank[\"\'][^>]*)(>)',
                     lambda m: m.group(1) + ' rel="noopener noreferrer"' + m.group(2), text, count=1, flags=re.I)
    elif finding["rule"] == "config.debug":
        new = re.sub(r"\bdebug\s*=\s*true\b", "debug=False", text, count=1, flags=re.I)
    else:
        raise ValueError("Correção automática não disponível para esta regra.")
    if new == text:
        raise ValueError("A correção não produziu nenhuma alteração.")
    path.write_text(new, encoding="utf-8")
    return {"ok": True, "changed": rel, "message": "Correção aplicada. Execute 'Verificar novamente' para confirmar."}


def dashboard():
    sites_list = sites.list_sites()
    analyzed = [s for s in sites_list if s.get("security_last_scan")]
    pending = corrected = vulnerabilities = 0
    history = []
    for s in analyzed:
        snap = (s.get("security_scans") or [])[-1]
        fs = snap.get("findings", [])
        vulnerabilities += sum(1 for f in fs if f.get("status") == "confirmed" and f.get("severity") != "info")
        pending += sum(1 for f in fs if f.get("status") == "needs_review")
        if len(s.get("security_scans") or []) > 1:
            prev = s["security_scans"][-2]
            b = {f["id"] for f in prev.get("findings", []) if f.get("status") == "confirmed"}
            a = {f["id"] for f in fs if f.get("status") == "confirmed"}
            corrected += len(b - a)
        history.append({"slug": s.get("slug"), "name": s.get("name"), "ts": snap.get("ts"),
                        "score": snap.get("score", 0), "risk": snap.get("risk", "limpo")})
    history.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return {"sites_analyzed": len(analyzed), "scans": sum(len(s.get("security_scans") or []) for s in analyzed),
            "vulnerabilities": vulnerabilities, "corrected": corrected, "pending_reviews": pending,
            "history": history[:20]}



# --- v13 Security Hunter extensions: incremental over the existing Security Center ---
_LEARN = {
    "web.xss_sink": {
        "concept":"XSS (Cross-Site Scripting)",
        "simple":"É quando conteúdo controlado por alguém consegue virar HTML ou JavaScript executável no navegador.",
        "why":"Um sink como innerHTML só é perigoso quando recebe dados não confiáveis sem sanitização adequada.",
        "impact":"Pode alterar a interface, executar ações em nome da vítima ou acessar dados disponíveis ao contexto da página.",
        "fix":"Prefira textContent para texto. Quando HTML for realmente necessário, use sanitização apropriada e uma CSP restritiva.",
        "example":"element.textContent = userInput;",
    },
    "code.sql_concat": {
        "concept":"SQL Injection",
        "simple":"Acontece quando entrada externa é misturada diretamente à consulta SQL.",
        "why":"O banco pode interpretar parte da entrada como código SQL em vez de apenas dados.",
        "impact":"Pode permitir leitura ou alteração indevida de dados, dependendo das permissões da conta do banco.",
        "fix":"Use consultas parametrizadas/placeholders e valide entradas no backend.",
        "example":"cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    },
    "web.csrf_review": {
        "concept":"CSRF",
        "simple":"É uma requisição forjada que tenta fazer um navegador autenticado executar uma ação sem intenção do usuário.",
        "why":"A análise estática do HTML não prova sozinha se o backend possui proteção.",
        "impact":"Pode afetar ações que alteram dados quando cookies de sessão são enviados automaticamente.",
        "fix":"Use proteção CSRF no backend, SameSite apropriado e validação de origem quando aplicável.",
        "example":"Validar um token CSRF único no servidor antes de aceitar uma mutação.",
    },
    "code.cors_any": {
        "concept":"CORS excessivamente permissivo",
        "simple":"CORS define quais origens podem ler respostas de uma API pelo navegador.",
        "why":"Permitir qualquer origem pode ampliar quem consegue ler respostas quando outros controles também estiverem fracos.",
        "impact":"Pode expor dados de APIs a origens não previstas, especialmente em conjunto com credenciais.",
        "fix":"Use uma allowlist de origens necessárias e revise credenciais/cookies.",
        "example":"Access-Control-Allow-Origin: https://app.exemplo.com",
    },
    "web.cookie_review": {
        "concept":"Cookies e sessão",
        "simple":"Cookies de autenticação devem ser protegidos contra leitura por JavaScript e envio cross-site quando apropriado.",
        "why":"HttpOnly reduz acesso por JavaScript; Secure exige HTTPS; SameSite reduz cenários cross-site.",
        "impact":"Configurações fracas podem aumentar o risco de roubo ou abuso de sessão.",
        "fix":"Revise Secure, HttpOnly, SameSite, expiração, rotação e invalidação no backend.",
        "example":"Set-Cookie: session=...; Secure; HttpOnly; SameSite=Lax",
    },
    "code.shell_true": {
        "concept":"Command Injection",
        "simple":"Entrada não confiável pode acabar sendo interpretada como comandos pelo shell.",
        "why":"shell=True e APIs como os.system aumentam o risco quando argumentos vêm de entrada externa.",
        "impact":"Pode permitir execução de comandos com as permissões do processo.",
        "fix":"Prefira listas de argumentos e shell=False; valide entradas com allowlists.",
        "example":"subprocess.run([tool, user_value], shell=False, check=True)",
    },
    "code.os_system": {
        "concept":"Command Injection",
        "simple":"os.system/os.popen executam comandos do sistema e exigem cuidado especial com entrada externa.",
        "why":"Se dados controlados pelo usuário chegam ao comando sem validação, o shell pode interpretar metacaracteres.",
        "impact":"Execução de comandos com as permissões do processo.",
        "fix":"Use subprocess com argumentos separados, shell=False e allowlists.",
        "example":"subprocess.run([binary, argument], shell=False, check=True)",
    },
    "code.secret_default": {
        "concept":"Segredo fixo no código",
        "simple":"Uma chave secreta escrita diretamente no código pode acabar em repositórios, backups ou logs.",
        "why":"Qualquer pessoa que obtenha o código pode reutilizar a chave.",
        "impact":"Pode permitir falsificação de sessões ou acesso a serviços, dependendo do segredo.",
        "fix":"Use variáveis de ambiente/secret manager e faça rotação se o segredo já foi exposto.",
        "example":"SECRET_KEY = os.environ['SECRET_KEY']",
    },
}

def _hunter_status(f):
    # Static heuristics are not automatically equivalent to exploitable vulnerabilities.
    possible_rules={"code.eval","code.exec","code.shell_true","code.os_system","code.innerhtml","web.xss_sink","code.md5_sha1","code.weak_random","web.mixed_content"}
    if f.get("status") in {"needs_review","pass","possible"}:
        return f.get("status")
    if f.get("rule") in possible_rules:
        f["status"]="possible"
    else:
        f.setdefault("status","confirmed")
    return f["status"]

def _hunter_enrich(f):
    _hunter_status(f)
    learn=_LEARN.get(f.get("rule"), {})
    f.setdefault("category", "Security Hunter")
    f["concept"]=learn.get("concept", f.get("title", "Security finding"))
    f["simple_explanation"]=learn.get("simple", f.get("impact", "Resultado baseado em evidência estática."))
    f["why"]=learn.get("why", "A evidência encontrada merece revisão no contexto da aplicação.")
    f["possible_impact"]=f.get("impact", "O impacto depende do contexto e das permissões envolvidas.")
    f["correction"]=f.get("fix", "Revise e corrija no backend quando aplicável.")
    f["example_fix"]=learn.get("example", "Consulte a correção sugerida e teste novamente.")
    f["verification"]= "Reexecute o scan após a correção; o desaparecimento da evidência é necessário para considerar o achado resolvido."
    return f

def _deep_checks(folder, fmap, all_text):
    extra=[]
    def rev(rule,title,evidence,fix,where,category="Security Hunter"):
        f=make_finding(rule,title,"info",evidence=evidence,
            impact="Não há evidência suficiente para confirmar uma vulnerabilidade.",fix=fix,where=where)
        f.update({"status":"needs_review","autofix":False,"category":category})
        return f
    # Exposed config / env files: presence is evidence of exposure risk, not proof of public exposure.
    for rel in fmap:
        low=rel.lower()
        if low.endswith((".env",".env.local",".env.production")) or low in {"config.json","config.yaml","config.yml"}:
            extra.append(rev("exposure.config_file", "Arquivo de configuração sensível presente no projeto",
                f"{rel}: arquivo de ambiente/configuração encontrado no conteúdo do site.",
                "Não publique segredos; mantenha configurações sensíveis fora do diretório público e use secret management.",rel))
    # Path traversal/LFI indicators.
    if re.search(r"\.\./|\.\.\\|send_file\s*\([^)]*(?:request|args|query|form)|open\s*\([^)]*(?:request|args|query|form)", all_text, re.I):
        extra.append(rev("path_traversal.review","Padrão relacionado a caminho controlado por entrada requer revisão",
            "Foram encontrados padrões de caminho/arquivo combinados com possíveis entradas de requisição.",
            "Normalize/canonicalize caminhos, use allowlists e mantenha o arquivo servido dentro de um diretório permitido.","projeto"))
    # Administrative endpoints.
    if re.search(r"/(?:admin|administrator|manage|internal|debug)(?:/|\b)", all_text, re.I):
        extra.append(rev("admin.endpoint_review","Endpoint administrativo detectado — revisar autorização",
            "Foram encontrados caminhos com nomes administrativos/internos no código.",
            "Exija autenticação e autorização no backend e não dependa apenas de esconder links.","projeto"))
    # Authentication/session semantics.
    if re.search(r"login|signin|sign-in|password|senha|session|jwt|authorization", all_text, re.I):
        extra.append(rev("auth.security_review","Mecanismos de autenticação/sessão requerem revisão",
            "Foram encontrados termos de autenticação, sessão ou autorização no projeto.",
            "Revise hashing de senhas, expiração/rotação de sessão, autorização por objeto/rota, MFA quando necessário e proteção contra brute force.","projeto"))
    # Error information disclosure.
    if re.search(r"traceback|stack trace|exception|print\s*\([^)]*(?:password|secret|token|key)", all_text, re.I):
        extra.append(rev("error.disclosure_review","Possível exposição de informações em erros/logs",
            "Foram encontradas referências a stack traces/exceções ou impressão de valores sensíveis.",
            "Evite retornar stack traces ao cliente e redija/mascare segredos nos logs.","projeto"))
    # Rate limiting is runtime behavior.
    extra.append(rev("ratelimit.runtime_review","Rate limiting precisa ser validado em runtime",
        "Não é possível provar limites de requisições por análise estática do site.",
        "Teste endpoints sensíveis e confirme limites, respostas 429 e controles de brute force no backend.","backend"))
    # TLS is deployment behavior.
    extra.append(rev("tls.runtime_review","HTTPS/TLS precisa ser validado no ambiente publicado",
        "A análise local não observa o certificado ou protocolo negociado pelo servidor.",
        "Use testssl.sh ou ferramenta equivalente somente no domínio/ambiente autorizado.","deployment"))
    # File permissions from the actual filesystem.
    for p in folder.rglob("*"):
        if not p.is_file() or ".git" in p.parts or "node_modules" in p.parts: continue
        try:
            mode=p.stat().st_mode & 0o777
            if mode & 0o002:
                extra.append(rev("permissions.world_writable","Arquivo gravável por qualquer usuário do sistema",
                    f"{p.relative_to(folder)} possui permissão {oct(mode)}.",
                    "Remova escrita para outros usuários e aplique o menor privilégio necessário.",str(p.relative_to(folder))))
        except OSError: pass
    return extra

# --- v12 Security Center extensions: incremental, no replacement of existing engine ---
import shutil as _shutil
from pathlib import Path as _Path
from datetime import datetime as _datetime, timezone as _timezone

_V12_DATA = _Path(__file__).resolve().parent.parent / "data"
_V12_BACKUPS = _V12_DATA / "security_backups"
_V12_REPORTS = _V12_DATA / "security_reports"
_V12_LOG = _V12_DATA / "security_center.log"

def _v12_now():
    return _datetime.now(_timezone.utc).isoformat()

def _v12_log(action, slug="", detail=None, user="owner"):
    _V12_DATA.mkdir(parents=True, exist_ok=True)
    with _V12_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts":_v12_now(),"action":action,"site":slug,
                             "user":user,"detail":detail or {}}, ensure_ascii=False, default=str)+"\n")

def _v12_file_hash(path):
    h=hashlib.sha256()
    with open(path,"rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _v12_manifest(folder):
    rows=[]
    root=_Path(folder).resolve()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append({"path":str(p.relative_to(root)).replace("\\","/"),
                         "sha256":_v12_file_hash(p),"size":p.stat().st_size})
    return {"version":1,"created_at":_v12_now(),"files":rows}

def _v12_verify_backup(backup):
    backup=_Path(backup).resolve()
    manifest_path=backup/"backup_manifest.json"
    if not manifest_path.exists():
        raise ValueError("Manifesto do backup ausente.")
    data=json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in data.get("files",[]):
        p=backup/row["path"]
        if not p.is_file() or p.stat().st_size != int(row["size"]) or _v12_file_hash(p) != row["sha256"]:
            return False
    return True

def _v12_prune_backups():
    keep=max(1,int(os.getenv("SECURITY_BACKUP_RETENTION","10")))
    items=sorted([p for p in _V12_BACKUPS.iterdir() if p.is_dir()], key=lambda p:p.stat().st_mtime, reverse=True)
    for old in items[keep:]:
        _shutil.rmtree(old, ignore_errors=True)

def _v12_backup(slug, reason="before-fix", user="owner"):
    folder=sites.SITES_DIR/slug
    if not folder.exists(): raise ValueError("Site não encontrado.")
    _V12_BACKUPS.mkdir(parents=True,exist_ok=True)
    try: _V12_BACKUPS.chmod(0o700)
    except OSError: pass
    stamp=_datetime.now(_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst=_V12_BACKUPS/f"{slug}-{stamp}-{reason}"
    _shutil.copytree(folder,dst)
    manifest=_v12_manifest(dst)
    (dst/"backup_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    try: (dst/"backup_manifest.json").chmod(0o600)
    except OSError: pass
    ok=_v12_verify_backup(dst)
    if not ok:
        _shutil.rmtree(dst,ignore_errors=True)
        raise ValueError("Falha na verificação de integridade do backup.")
    _v12_prune_backups()
    _v12_log("backup_created",slug,{"path":str(dst),"reason":reason,"integrity":"verified"},user)
    return dst

def list_backups(slug=""):
    _V12_BACKUPS.mkdir(parents=True,exist_ok=True)
    prefix=f"{slug}-" if slug else ""
    out=[]
    for p in sorted(_V12_BACKUPS.glob(prefix+"*"), key=lambda x:x.stat().st_mtime, reverse=True):
        if not p.is_dir(): continue
        ok=False
        try: ok=_v12_verify_backup(p)
        except Exception: pass
        out.append({"name":p.name,"path":str(p),"integrity":ok,
                    "created_at":_datetime.fromtimestamp(p.stat().st_mtime,_timezone.utc).isoformat()})
    return out

def restore_backup(slug, backup_name, user="owner", confirm=False):
    if not confirm:
        raise ValueError("Confirmação obrigatória antes da restauração.")
    source=(_V12_BACKUPS/backup_name).resolve()
    root=_V12_BACKUPS.resolve()
    if root not in source.parents or not source.is_dir():
        raise ValueError("Backup inválido.")
    if not _v12_verify_backup(source):
        raise ValueError("Backup reprovado na verificação de integridade.")
    if not backup_name.startswith(f"{slug}-"):
        raise ValueError("Backup não pertence ao site informado.")
    folder=(sites.SITES_DIR/slug).resolve()
    sites_root=sites.SITES_DIR.resolve()
    if sites_root not in folder.parents:
        raise ValueError("Caminho do site inválido.")
    safety=_v12_backup(slug,"before-restore",user)
    temp=sites_root/f".restore-{slug}-{hashlib.sha256(backup_name.encode()).hexdigest()[:12]}"
    if temp.exists(): _shutil.rmtree(temp)
    _shutil.copytree(source,temp,ignore=_shutil.ignore_patterns("backup_manifest.json"))
    if folder.exists(): _shutil.rmtree(folder)
    temp.rename(folder)
    _v12_log("backup_restored",slug,{"source":backup_name,"safety_backup":str(safety)},user)
    return {"restored":True,"backup":backup_name,"safety_backup":str(safety)}

_V12_ORIGINAL_SCAN_SITE = scan_site

def scan_site(slug, mode="full"):
    mode=(mode or "full").lower()
    if mode not in {"quick","full","hardening","rescan","deep"}: mode="full"
    result=_V12_ORIGINAL_SCAN_SITE(slug)
    # Keep the existing evidence engine; modes only control additional deterministic checks.
    if mode in {"full","hardening","rescan","deep"}:
        folder=sites.SITES_DIR/slug
        headers=""
        for name in ("_headers","netlify.toml"):
            p=folder/name
            if p.exists():
                try: headers += p.read_text(encoding="utf-8",errors="replace")[:100000]
                except Exception: pass
        extra=[]
        def review(rule,title,evidence,fix,where):
            f=make_finding(rule,title,"info",evidence=evidence,
                impact="Não há evidência suficiente para confirmar uma vulnerabilidade.",
                fix=fix,where=where)
            f.update({"status":"needs_review","autofix":False,"category":"Security Center"})
            return f
        if not re.search(r"Permissions-Policy|Referrer-Policy|X-Content-Type-Options",headers,re.I):
            extra.append(review("headers.baseline","Headers de segurança precisam de revisão",
                "Não foram evidenciados X-Content-Type-Options, Referrer-Policy e/ou Permissions-Policy.",
                "Configure headers de segurança no host publicado e valide os recursos legítimos.","_headers/netlify.toml"))
        extra.extend([
            review("authz.review","Autorização requer revisão","A autorização por rota/objeto depende do backend.",
                   "Teste acesso com usuários/tenants diferentes e valide autorização no servidor.","backend"),
            review("session.review","Sessões requerem revisão","A segurança de sessão não é comprovável pelo HTML estático.",
                   "Confirme rotação, expiração, invalidação e proteção de cookies.","backend"),
            review("ratelimit.review","Rate limiting requer revisão","Não há evidência estática suficiente de rate limiting.",
                   "Teste limites e respostas 429 por rota sensível.","backend"),
            review("permissions.review","Permissões requerem revisão","Permissões de arquivos/rotas não são totalmente inferíveis pelo conteúdo.",
                   "Revise ACLs, permissões e autorização por rota.","backend"),
            review("error.review","Tratamento de erros requer revisão","Mensagens de erro dependem do runtime.",
                   "Confirme que stack traces, caminhos e segredos não são expostos.","backend"),
            review("admin.review","Endpoints administrativos requerem revisão","Não é possível confirmar proteção de endpoints administrativos por análise estática.",
                   "Enumere endpoints administrativos e confirme autenticação/autorização.","backend"),
            review("tls.review","HTTPS/TLS requer verificação no ambiente publicado","TLS real depende do host.",
                   "Use testssl.sh somente contra o site autorizado.","deployment"),
        ])
        if not re.search(r"debug\s*=\s*(?:false|0)|DEBUG\s*=\s*False", "\n".join(
                p.read_text(encoding="utf-8",errors="replace")[:100000] for p in folder.rglob("*")
                if p.is_file() and p.suffix.lower() in {".py",".js",".json",".env",".toml",".yml",".yaml"}), re.I):
            pass
        if mode == "deep":
            folder=sites.SITES_DIR/slug
            extra.extend(_deep_checks(folder, fmap if 'fmap' in locals() else {str(p.relative_to(folder)):_read(p) for p in _files(folder)},
                                      "\n".join(_read(p) for p in _files(folder))))
        # stable dedupe + Security Hunter explanations
        seen=set(); merged=[]
        for f in result["findings"]+extra:
            _hunter_enrich(f)
            if f["id"] not in seen: seen.add(f["id"]); merged.append(f)
        result["findings"]=merged
        result["mode"]=mode
        result["note"]="Resultados baseados em evidência. NEEDS REVIEW não significa vulnerabilidade confirmada."
        result["status_counts"]={k:0 for k in ("confirmed","possible","needs_review","pass")}
        for f in merged: result["status_counts"][f.get("status","confirmed")]+=1
    else:
        result["mode"]="quick"
        for f in result["findings"]: _hunter_enrich(f)
        result["status_counts"]={k:0 for k in ("confirmed","possible","needs_review","pass")}
        for f in result["findings"]: result["status_counts"][f.get("status","confirmed")]+=1
    confirmed=[f for f in result["findings"] if f.get("status") in ("confirmed","possible") and f.get("severity")!="info"]
    result["score"]=risk_score(confirmed); result["risk"]=risk_label(result["score"])
    result["counts"]={k:0 for k in ("critical","high","medium","low","info")}
    for f in result["findings"]: result["counts"][f["severity"]]+=1
    _v12_log("scan_completed",slug,{"mode":mode,"score":result["score"],"findings":len(result["findings"])})
    return result

def scan_and_store(slug, mode="full", user="owner"):
    result=scan_site(slug,mode)
    folder=sites.SITES_DIR/slug; meta=sites.load_metadata(folder) or {}
    history=meta.get("security_scans") or []; previous=history[-1] if history else None
    snap={"ts":_v12_now(),"mode":mode,"score":result["score"],"risk":result["risk"],
          "findings":result["findings"],"counts":result["counts"],
          "status_counts":result["status_counts"],"files_scanned":result["files_scanned"]}
    history.append(snap); meta["security_scans"]=history[-MAX_HISTORY:]
    meta["security_last_scan"]=snap["ts"]; meta["security_score"]=result["score"]; meta.pop("slug",None)
    sites.save_metadata(folder,meta)
    if previous:
        b={f["id"]:f for f in previous.get("findings",[]) if f.get("status")=="confirmed"}
        a={f["id"]:f for f in snap["findings"] if f.get("status")=="confirmed"}
        result["comparison"]={"before_score":previous.get("score",0),"after_score":snap["score"],
            "resolved":[b[k] for k in b if k not in a],"persistent":[a[k] for k in a if k in b],
            "new":[a[k] for k in a if k not in b]}
    else: result["comparison"]=None
    _v12_log("scan_saved",slug,{"mode":mode,"score":result["score"]},user)
    return result

_V12_ORIGINAL_APPLY_FIX = apply_fix

def apply_fix(slug,finding_id,user="owner",confirm=False):
    if not confirm:
        raise ValueError("Confirmação obrigatória antes de alterar o site.")
    backup=_v12_backup(slug,"before-fix",user)
    try:
        out=_V12_ORIGINAL_APPLY_FIX(slug,finding_id)
    except Exception:
        # Preserve the backup even if the fix fails; never silently mutate further.
        raise
    out["backup"]=str(backup)
    _v12_log("fix_applied",slug,{"finding_id":finding_id,"backup":str(backup),
                                  "changed":out.get("changed")},user)
    # Always verify an automatic fix immediately; callers still receive the full rescan.
    after=scan_and_store(slug, mode="rescan", user=user)
    out["rescan"]=after
    old_ids={finding_id}
    out["verification"]={"status":"corrigido" if not any(f.get("id") in old_ids for f in after.get("findings",[])) else "ainda presente"}
    _v12_log("fix_verified",slug,{"finding_id":finding_id,"status":out["verification"]["status"]},user)
    return out

def export_report(slug):
    folder=sites.SITES_DIR/slug; meta=sites.load_metadata(folder) or {}
    history=meta.get("security_scans") or []
    if not history: raise ValueError("Nenhum scan realizado.")
    snap=history[-1]
    _V12_REPORTS.mkdir(parents=True,exist_ok=True)
    stamp=_datetime.now(_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out=_V12_REPORTS/f"{slug}-{stamp}.md"
    confirmed=[f for f in snap["findings"] if f.get("status") in ("confirmed","possible") and f.get("severity")!="info"]
    reviews=[f for f in snap["findings"] if f.get("status")=="needs_review"]
    lines=[f"# Security Report — {meta.get('name',slug)}","",
           f"- Data: {snap['ts']}",f"- Security Score: {snap['score']}",
           f"- Risco: {snap['risk']}",f"- Modo: {snap.get('mode','full')}","",
           "## Resumo",f"- Arquivos analisados: {snap.get('files_scanned',0)}",
           f"- Evidências confirmadas/fortes: {sum(1 for f in confirmed if f.get('status')=='confirmed')}",
           f"- Possíveis (heurística): {sum(1 for f in confirmed if f.get('status')=='possible')}",
           f"- Necessitam revisão: {len(reviews)}","",
           "## Vulnerabilidades"]
    for f in confirmed:
        lines += [f"### {f['title']} — {f['severity']}",f"- Local: {f['where']}",
                  f"- Evidência: {f['evidence']}",f"- Impacto: {f['impact']}",
                  f"- Correção: {f['fix']}",f"- Status: {f.get('status')}",""]
    lines += ["## Pendências / NEEDS REVIEW"]
    for f in reviews: lines.append(f"- {f['title']} — {f['where']}: {f['evidence']}")
    lines += ["","## Ferramentas utilizadas",
              "- Nenhuma ferramenta externa é declarada como utilizada sem execução real.",
              "- O inventário de ferramentas usa detecção real de disponibilidade.",
              "","## Testes realizados",
              "- Scan do projeto/site e comparação com o scan anterior quando disponível."]
    out.write_text("\n".join(lines),encoding="utf-8")
    _v12_log("report_exported",slug,{"path":str(out)})
    return {"ok":True,"path":str(out),"report":out.read_text(encoding="utf-8")}

_V12_ORIGINAL_DASHBOARD = dashboard

def dashboard():
    d=_V12_ORIGINAL_DASHBOARD()
    # Extend existing dashboard rather than replacing its data model.
    d["critical"]=sum(1 for s in d.get("history",[]) if s.get("risk")=="crítico")
    comparisons=[]
    for site in sites.list_sites():
        hs=site.get("security_scans") or []
        if len(hs)>1:
            before,after=hs[-2],hs[-1]
            b={f["id"]:f for f in before.get("findings",[]) if f.get("status")=="confirmed"}
            a={f["id"]:f for f in after.get("findings",[]) if f.get("status")=="confirmed"}
            comparisons.append({"slug":site.get("slug"),"name":site.get("name"),
                "before_score":before.get("score",0),"after_score":after.get("score",0),
                "appeared":[a[k] for k in a if k not in b],
                "fixed":[b[k] for k in b if k not in a],
                "persistent":[a[k] for k in a if k in b]})
    d["comparisons"]=comparisons
    try:
        from services import telemetry, auth, access_log, tool_registry
        d["security_state"] = {
            "authentication": {"master_password_source": auth.password_source(),
                               "session_version": auth.current_session_version()},
            "audit_events": telemetry.recent(25),
            "access_log": access_log.recent(25),
            "tools": {"registered": len(tool_registry.REGISTRY.tools)},
            "backups": {"retention": max(1, int(os.getenv("SECURITY_BACKUP_RETENTION","10"))),
                        "verified": sum(1 for x in list_backups() if x["integrity"])},
            "dependencies": {"pip_audit_installed": __import__("importlib.util").util.find_spec("pip_audit") is not None},
            "alerts": __import__("services.security", fromlist=["security_alerts"]).security_alerts(50),
        }
    except Exception:
        d["security_state"] = {}
    return d
