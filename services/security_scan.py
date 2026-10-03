"""Scanner determinístico do próprio Tristan Thorne.

Analisa somente arquivos do diretório da aplicação. Não faz requisições de rede,
não executa o código analisado e não modifica arquivos.
"""
from pathlib import Path
import re
from services.cyber import local
from services.evidence import make_finding as F

TEXT_EXT = {".py",".js",".css",".html",".txt",".md",".json",".yml",".yaml",".toml",".ini",".cfg",".conf",".env",".sh"}
SKIP_DIRS = {".git","__pycache__","node_modules",".venv","venv","dist","build","tests"}

def _files(base):
    for p in Path(base).rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_EXT or p.name in {"Procfile","requirements.txt"}:
            yield p

def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:400_000]
    except Exception:
        return ""

def _finding(rule,title,severity,evidence,impact,fix,where):
    return F(rule,title,severity,evidence=evidence,impact=impact,fix=fix,where=where)

def scan_project(base):
    base = Path(base).resolve()
    findings=[]
    files=list(_files(base))
    file_map={str(p.relative_to(base)): _read(p) for p in files}
    app=file_map.get("app.py","")
    security=file_map.get("services/security.py","")
    routes=file_map.get("routes_cyber.py","")
    perms=file_map.get("services/permissions.py","")
    all_text="\n".join(f"\n# FILE {k}\n{v}" for k,v in file_map.items())

    # Reuse the existing deterministic analyzers instead of a second scanner.
    for rel,text in file_map.items():
        # Não varrer como código os próprios enunciados de laboratório/plugins:
        # eles contêm exemplos vulneráveis de propósito.
        lab_corpus = rel in {"services/cyber_challenges.py", "plugins/cyber_lab_security_challenges.py"}
        if not lab_corpus and rel.endswith((".py",".js")):
            findings.extend(local.scan_code(text,rel)["findings"])
        if not lab_corpus and rel.endswith((".py",".js",".json",".env",".yml",".yaml")):
            findings.extend(local.scan_secrets(text,rel)["findings"])

    req=file_map.get("requirements.txt")
    if req:
        findings.extend(local.scan_dependencies(req,"requirements.txt")["findings"])

    # Concrete project-level controls.
    if re.search(r'app\.secret_key\s*=\s*os\.getenv\(["\']SECRET_KEY["\']\s*,', app):
        findings.append(_finding("config.secret_key_fallback","SECRET_KEY possui fallback previsível",
            "high","app.py: app.secret_key usa valor padrão quando SECRET_KEY não existe.",
            "Uma chave de sessão previsível pode permitir falsificação de sessão.",
            "Exigir SECRET_KEY em produção e falhar com mensagem segura quando ausente.",
            "app.py:33"))
    else:
        findings.append(_finding("config.secret_key","SECRET_KEY sem fallback previsível","info",
            "Não foi encontrado o padrão de fallback previsível do scanner.",
            "Reduz risco de sessões forjáveis.","Manter segredo fora do código.","app.py:secret_key"))

    if re.search(r"SESSION_COOKIE_HTTPONLY\s*=\s*True",app) and re.search(r"SESSION_COOKIE_SAMESITE",app):
        findings.append(_finding("session.flags","Flags básicas de sessão configuradas","info",
            "SESSION_COOKIE_HTTPONLY=True e SESSION_COOKIE_SAMESITE configurados.",
            "Reduz acesso indevido e envio cross-site do cookie.","Manter Secure ativo em produção HTTPS.","app.py:39-41"))
    else:
        findings.append(_finding("session.flags","Flags de sessão precisam de revisão","high",
            "Não foram encontradas as configurações esperadas de sessão.",
            "Cookie de sessão mais exposto a roubo/CSRF.","Ativar HttpOnly, Secure e SameSite.","app.py"))

    if "security.check_origin(request)" in app and "MUTATING_METHODS" in security:
        findings.append(_finding("csrf.origin","Proteção CSRF por Origin/Referer presente","info",
            "app.before_request chama security.check_origin para mutações.",
            "Rejeita origens externas quando Origin/Referer está presente.","Manter e adicionar token CSRF em fluxos que exijam garantia adicional.","app.py:before_request"))
    else:
        findings.append(_finding("csrf.origin","Proteção CSRF global não evidenciada","high",
            "Não foi localizada a chamada esperada a security.check_origin.",
            "Rotas mutáveis podem aceitar requisições cross-site.","Aplicar proteção CSRF no backend.","app.py:before_request"))

    if "Content-Security-Policy" in security and "object-src 'none'" in security:
        sev="warning" if "'unsafe-eval'" in security else "info"
        findings.append(_finding("headers.csp","CSP configurada","medium" if sev=="warning" else "info",
            "CSP encontrada; a política atual ainda contém unsafe-eval." if sev=="warning" else "CSP encontrada sem unsafe-eval.",
            "unsafe-eval amplia superfícies de execução no navegador.","Remover unsafe-eval se nenhum recurso legítimo depender dele.","services/security.py:88-95"))
    else:
        findings.append(_finding("headers.csp","CSP não evidenciada","high",
            "Não foi encontrada Content-Security-Policy.","Menor defesa contra XSS e carregamento indevido.","Definir CSP compatível com a aplicação.","services/security.py"))

    if "secure_filename" in app and "validate_image_upload" in app:
        findings.append(_finding("upload.validation","Upload de imagem valida nome e conteúdo","info",
            "secure_filename e validate_image_upload encontrados no endpoint de upload.",
            "Reduz risco de nomes maliciosos e arquivos disfarçados.","Manter allowlist e validação de conteúdo.","app.py:789-817"))
    else:
        findings.append(_finding("upload.validation","Upload requer revisão","high",
            "Não foram encontradas as duas proteções esperadas.","Upload pode aceitar conteúdo inesperado.","Validar nome, tipo real e conteúdo no backend.","app.py"))

    if "send_from_directory" in app:
        findings.append(_finding("path_traversal.preview","Preview usa send_from_directory","info",
            "A entrega do preview usa send_from_directory.","O framework confina o arquivo ao diretório servido.","Manter e validar slugs antes de montar caminhos.","app.py:577-583"))

    if "enforce_path" in perms and '("/api/cyber", "cyber")' in perms:
        findings.append(_finding("authz.backend","Autorização por prefixo no backend","info",
            "permissions.enforce_path protege /api/cyber e outras áreas sensíveis.",
            "Impede depender somente do frontend para esconder funções.","Continuar usando require_cap para exceções mais sensíveis.","services/permissions.py:32-46"))

    if re.search(r'Access-Control-Allow-Origin',all_text):
        findings.append(_finding("cors.review","Há lógica de CORS no projeto","medium",
            "Foram encontradas referências a Access-Control-Allow-Origin; o scanner exige revisão da origem permitida.",
            "CORS incorreto pode permitir leitura cross-origin indevida.","Restringir origens a uma allowlist e evitar reflexão automática.","projeto"))
    else:
        findings.append(_finding("cors.review","Nenhuma configuração CORS da aplicação encontrada","info",
            "Não foi encontrada configuração de CORS no backend principal.",
            "Sem CORS explícito, o navegador normalmente aplica same-origin policy.","Revisar caso uma API precise ser consumida por outra origem.","projeto"))

    # Explicit review buckets, without inventing vulnerabilities.
    def bucket(f):
        sev=f.get("severity")
        if sev=="critical": return "ERROR"
        if sev in ("high","medium"): return "WARNING"
        return "NEEDS REVIEW" if sev=="low" else "PASS"

    rows=[]
    for f in findings:
        status=bucket(f)
        rows.append({
            "status":status, "rule":f["id"], "problem":f["title"],
            "location":f.get("where",""), "description":f.get("impact",""),
            "impact":f.get("impact",""), "evidence":f.get("evidence",""),
            "fix":f.get("fix",""), "severity":f.get("severity","info"),
        })
    # Do not duplicate the same exact rule/location pair.
    unique=[]; seen=set()
    for row in rows:
        key=(row["rule"],row["location"])
        if key in seen: continue
        seen.add(key); unique.append(row)

    counts={s:sum(1 for r in unique if r["status"]==s) for s in ("PASS","WARNING","ERROR","NEEDS REVIEW")}
    return {
        "ok": True, "scope": "somente o próprio projeto Tristan Thorne",
        "files_scanned": len(files), "findings": unique, "counts": counts,
        "note": "Resultados determinísticos baseados em evidência encontrada no código. NEEDS REVIEW não significa vulnerabilidade confirmada.",
    }
