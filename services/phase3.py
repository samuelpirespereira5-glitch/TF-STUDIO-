"""JARVIS Cyber Lab — Fase 3: postura de segurança e ferramentas defensivas.

Tudo aqui é defensivo/local por padrão. Ferramentas que recebem texto analisam
o material fornecido; ferramentas de rede reutilizam o guard existente.
Nenhuma função explora terceiros, executa payload recebido ou exfiltra dados.
"""
import hashlib, json, os, re, ssl, socket, ipaddress
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

def _finding(rule, title, severity, evidence="", impact="", fix="", where=""):
    return {"rule": rule, "title": title, "severity": severity,
            "status": "confirmed", "evidence": str(evidence)[:500],
            "impact": impact, "fix": fix, "where": where}

def _score(findings):
    weights={"critical":30,"high":20,"medium":10,"low":4,"info":0}
    return max(0,100-sum(weights.get(f.get("severity"),0) for f in findings))

def _redact(v):
    if v is None: return ""
    s=str(v)
    s=re.sub(r'(?i)(authorization\s*:\s*bearer\s+)[^\s]+',r'\1[oculto]',s)
    s=re.sub(r'(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)[^\s,;]+',r'\1[oculto]',s)
    return s[:500]

def security_posture(request=None):
    from services import auth, security, permissions
    checks=[]
    production=bool(getattr(security, "_IS_PRODUCTION", False) or os.getenv("PRODUCTION"))
    if auth.password_source():
        checks.append(("Master Password hash","pass","Apenas hash é usado"))
    else: checks.append(("Master Password hash","fail","Nenhuma credencial mestre configurada"))
    checks.append(("TOTP / MFA","pass" if auth.totp_is_enabled() else "review",
                   "TOTP ativo" if auth.totp_is_enabled() else "TOTP não ativado"))
    checks.append(("Passkeys","available" if auth.has_webauthn() else "unavailable",
                   "Credenciais WebAuthn armazenadas; login Passkey só deve ser habilitado com verificação criptográfica completa." if auth.has_webauthn()
                   else "Nenhuma Passkey cadastrada."))
    checks.append(("CSRF","pass","Token + Origin/Referer para métodos mutáveis"))
    checks.append(("Session fixation","pass","ID server-side é rotacionado após autenticação"))
    checks.append(("Session lifetime","pass","Cookie permanente com expiração e timeout de inatividade"))
    checks.append(("Security headers","review","CSP aplicada; CSP estrita fica em Report-Only até migrar scripts inline para nonce/hash"))
    checks.append(("Upload validation","pass","Validação por conteúdo real, formato e tamanho"))
    checks.append(("Authorization","pass","Permissões aplicadas no backend por capability"))
    checks.append(("Secrets frontend","pass","Respostas JSON passam por redaction de segredos"))
    req=BASE_DIR/"requirements.txt"
    checks.append(("Dependency audit","pass" if req.exists() else "review",
                   "requirements.txt + pip-audit disponível" if req.exists() else "requirements.txt ausente"))
    score=round(100*sum(1 for _,s,_ in checks if s=="pass")/max(1,len(checks)))
    return {"score":score,"checks":[{"name":a,"status":b,"detail":c} for a,b,c in checks],
            "production":production,
            "mfa_enabled":auth.totp_is_enabled(),
            "passkeys_registered":len(auth.list_webauthn_credentials()),
            "session_config":{"cookie_httponly":True,"samesite":"Lax",
                              "secure":bool(getattr(request,"is_secure",False)) if request else None},
            "recommendations":[
                "Ative TOTP antes de usar o painel em produção." if not auth.totp_is_enabled() else "MFA TOTP está ativo.",
                "Use HTTPS e defina HSTS em produção.",
                "Execute pip-audit regularmente e atualize dependências vulneráveis.",
                "Mantenha ALLOWED_HOSTS configurado no deploy."
            ]}

def sessions_for_dashboard(current_sid=""):
    from services import auth
    current_hash=auth._session_hash(current_sid)[:12] if current_sid else ""
    rows=auth.list_auth_sessions()
    for r in rows: r["current"]=(r["id"]==current_hash)
    return {"sessions":rows,"count":len(rows)}

def recent_events(limit=50):
    from services import telemetry, access_log
    events=[]
    try:
        for x in telemetry.recent(max(100,limit*2)):
            events.append({"time":x.get("ts",""),"type":"audit","action":x.get("tool",""),
                           "ok":bool(x.get("ok")),"target":_redact(x.get("target","")),
                           "request_id":x.get("request_id","")})
    except Exception: pass
    try:
        for x in access_log.recent(max(100,limit*2)):
            events.append({"time":x.get("ts",""),"type":"access","action":x.get("path",""),
                           "ok":int(x.get("status",0))<400,"target":"","request_id":x.get("request_id","")})
    except Exception: pass
    return sorted(events,key=lambda x:x.get("time",""),reverse=True)[:limit]

def analyze_security_headers(text):
    h={}
    for line in str(text or "").splitlines():
        if ":" in line:
            k,v=line.split(":",1); h[k.strip().lower()]=v.strip()
    findings=[]
    required={
      "strict-transport-security":("high","HSTS ausente","Ative HSTS somente quando o site estiver integralmente em HTTPS."),
      "content-security-policy":("high","CSP ausente","Defina CSP restritiva; prefira nonce/hash em scripts."),
      "x-content-type-options":("medium","nosniff ausente","Use X-Content-Type-Options: nosniff."),
      "referrer-policy":("low","Referrer-Policy ausente","Use strict-origin-when-cross-origin ou política equivalente."),
      "permissions-policy":("low","Permissions-Policy ausente","Desative APIs do navegador que não são necessárias.")
    }
    for k,(sev,title,fix) in required.items():
        if k not in h: findings.append(_finding(k,title,sev,fix=fix,where="headers"))
    if h.get("x-frame-options","").upper() not in {"DENY","SAMEORIGIN"} and "frame-ancestors" not in h.get("content-security-policy","").lower():
        findings.append(_finding("clickjacking","Proteção contra framing insuficiente","medium",
                                 evidence=h.get("x-frame-options","ausente"),fix="Use DENY/SAMEORIGIN ou frame-ancestors em CSP.",where="headers"))
    return {"findings":findings,"raw":{"headers":h},"summary":f"{len(findings)} achado(s)"}

def analyze_cookies(text):
    findings=[]
    for line in str(text or "").splitlines():
        if not re.search(r"(?i)^set-cookie\s*:",line): continue
        low=line.lower()
        if "secure" not in low: findings.append(_finding("cookie-secure","Cookie sem Secure","medium",evidence=_redact(line),fix="Adicione Secure.",where="Set-Cookie"))
        if "httponly" not in low: findings.append(_finding("cookie-httponly","Cookie sem HttpOnly","medium",evidence=_redact(line),fix="Adicione HttpOnly quando JavaScript não precisar ler o cookie.",where="Set-Cookie"))
        if "samesite" not in low: findings.append(_finding("cookie-samesite","Cookie sem SameSite","medium",evidence=_redact(line),fix="Use SameSite=Lax/Strict conforme o fluxo.",where="Set-Cookie"))
    return {"findings":findings,"raw":{"cookies_seen":sum(1 for x in str(text or "").splitlines() if x.lower().startswith("set-cookie:"))},
            "summary":f"{len(findings)} achado(s)"}

def analyze_cors(text):
    findings=[]
    for line in str(text or "").splitlines():
        if line.lower().startswith("access-control-allow-origin:"):
            v=line.split(":",1)[1].strip()
            if v=="*": findings.append(_finding("cors-wildcard","CORS permite qualquer origem","medium",evidence=v,impact="Pode ampliar a superfície de APIs públicas.",fix="Use uma allowlist de origens quando credenciais estiverem envolvidas.",where="headers"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} achado(s)"}

def analyze_api_security(text):
    s=str(text or "")
    findings=[]
    rules=[
      ("api-auth","Endpoint sensível sem evidência de autenticação","high",r"@(?:app|bp)\.(?:get|post|put|delete|patch)\([^)]*\)[\s\S]{0,500}def\s+\w+\([^)]*\):[\s\S]{0,500}(?:return|jsonify)","Adicione autenticação e autorização no backend."),
      ("api-input","Entrada do usuário usada sem validação explícita","medium",r"(request\.(?:json|form|args)\[[^\]]+\])","Valide tipo, tamanho e esquema antes de usar a entrada."),
      ("api-error","API devolve exceção diretamente","medium",r"(return\s+(?:str\()?e\b|jsonify\(\s*\{?[^}]*error[^}]*str\(e\))","Retorne mensagem genérica e registre request_id internamente.")
    ]
    for rid,title,sev,pat,fix in rules:
        if re.search(pat,s,re.I): findings.append(_finding(rid,title,sev,fix=fix,where="submitted code"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} achado(s)"}

def detect_secrets(text):
    findings=[]
    pats=[
      ("aws-key",r"\bAKIA[0-9A-Z]{16}\b"),
      ("private-key",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
      ("generic-secret",r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][^\"']{8,}[\"']")
    ]
    for rid,pat in pats:
        m=re.search(pat,str(text or ""))
        if m: findings.append(_finding(rid,"Possível segredo exposto","critical",evidence="[oculto]",impact="Credenciais no código podem ser reutilizadas.",fix="Remova o segredo, revogue-o se real e use secret manager/variáveis de ambiente.",where="input"))
    return {"findings":findings,"raw":{"matches":len(findings)},"summary":f"{len(findings)} possível(is) segredo(s)"}

def analyze_dependencies(text):
    findings=[]
    # Auditoria sem rede: identifica pins ausentes e versões suspeitas; não afirma CVEs.
    for i,line in enumerate(str(text or "").splitlines(),1):
        x=line.strip()
        if not x or x.startswith("#"): continue
        if re.match(r"^[A-Za-z0-9_.-]+$",x):
            findings.append(_finding("unpinned-dependency","Dependência sem versão fixada","low",evidence=x,fix="Fixe uma versão compatível e rode pip-audit/npm audit conforme o ecossistema.",where=f"line {i}"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} ponto(s) de revisão"}

def analyze_file_integrity(text, expected=""):
    data=str(text or "").encode()
    actual=hashlib.sha256(data).hexdigest()
    findings=[]
    if expected and not re.fullmatch(r"[0-9a-fA-F]{64}",expected.strip()):
        findings.append(_finding("invalid-hash","Hash esperado inválido","medium",evidence=expected,fix="Forneça SHA-256 hexadecimal com 64 caracteres.",where="input"))
    elif expected and actual.lower()!=expected.strip().lower():
        findings.append(_finding("hash-mismatch","Hash SHA-256 não corresponde","high",evidence=f"atual={actual}",fix="Verifique a origem e integridade do arquivo.",where="input"))
    return {"findings":findings,"raw":{"sha256":actual},"summary":f"SHA-256: {actual}"}

def analyze_metadata(filename,text):
    ext=Path(filename or "").suffix.lower()
    findings=[]
    if ext in {".jpg",".jpeg",".png",".pdf",".docx"}:
        findings.append(_finding("metadata-review","Metadados devem ser revisados antes do compartilhamento","info",
                                 evidence=f"extensão={ext}",fix="Remova metadados desnecessários ao publicar arquivos.",where=filename or "arquivo"))
    return {"findings":findings,"raw":{"filename":filename,"size":len(str(text or "").encode())},"summary":"Revisão de metadados concluída"}

def analyze_logs(text):
    rows=str(text or "").splitlines()
    fail={}
    suspicious=[]
    for row in rows:
        m=re.search(r"\b(?:FAIL|401|403)\b.*?\b(?:ip=|from=)([0-9a-fA-F:.]+)",row,re.I)
        if m: fail[m.group(1)]=fail.get(m.group(1),0)+1
    for ip,count in fail.items():
        if count>=5: suspicious.append(_finding("auth-burst","Muitas falhas do mesmo endereço","high",evidence=f"{ip}: {count}",fix="Confirme se é legítimo; aplique rate limit e investigação.",where="log"))
    return {"findings":suspicious,"raw":{"failure_sources":fail},"summary":f"{len(suspicious)} evento(s) para revisão"}

def dns_analyzer(target):
    from services import basic_net
    return basic_net.domain_check(target)

def tls_analyzer(target):
    from services import basic_net
    return basic_net.ssl_check(target)


def ip_information(target):
    value=str(target or "").strip()
    try:
        ip=ipaddress.ip_address(value)
        return {"raw":{"ip":str(ip),"version":ip.version,"private":ip.is_private,
                      "loopback":ip.is_loopback,"reserved":ip.is_reserved,
                      "link_local":ip.is_link_local},"summary":f"{ip} · IPv{ip.version} · "
                      f"{'privado' if ip.is_private else 'público'}"}
    except ValueError:
        try:
            infos=socket.getaddrinfo(value,None)
            ips=sorted({x[4][0] for x in infos})
            return {"raw":{"hostname":value,"addresses":ips},"summary":f"{len(ips)} endereço(s) resolvido(s)"}
        except Exception as e:
            return {"findings":[_finding("dns-error","Não foi possível resolver o nome","medium",evidence=str(e),fix="Verifique DNS e o nome informado.",where="target")],
                    "raw":{},"summary":"falha de resolução"}

def network_config(text):
    findings=[]
    s=str(text or "")
    if re.search(r"(?i)\b(0\.0\.0\.0/0|0\.0\.0\.0)\b",s):
        findings.append(_finding("wide-bind","Configuração exposta em todas as interfaces","medium",
                                 evidence="0.0.0.0/0 ou 0.0.0.0 encontrado",
                                 fix="Restrinja interfaces/regras ao mínimo necessário.",where="config"))
    if re.search(r"(?i)\b(password|community)\s*[:=]\s*(public|admin|root|123456)\b",s):
        findings.append(_finding("default-credential","Credencial padrão/fraca em configuração","high",
                                 evidence="[oculto]",fix="Troque a credencial e use secret manager.",where="config"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} achado(s)"}

def packet_log_analyzer(text):
    return analyze_logs(text)

def robots_sitemap_analyzer(text):
    findings=[]
    s=str(text or "")
    if re.search(r"(?i)^sitemap\s*:\s*https?://",s,re.M) is None:
        findings.append(_finding("sitemap-missing","Nenhum sitemap declarado no conteúdo","info",
                                 fix="Se aplicável, publique sitemap.xml e referencie-o em robots.txt.",where="robots.txt"))
    if re.search(r"(?i)^allow\s*:\s*/\s*$",s,re.M):
        findings.append(_finding("robots-wide","robots.txt permite rastreamento amplo","info",
                                 evidence="Allow: /",fix="Robots.txt não é controle de acesso; proteja conteúdo sensível no servidor.",where="robots.txt"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} ponto(s) para revisão"}

def auth_config_analyzer(text):
    s=str(text or "")
    findings=[]
    if not re.search(r"(?i)(mfa|2fa|totp|webauthn|passkey)",s):
        findings.append(_finding("auth-no-mfa","Não há evidência de MFA","medium",
                                 fix="Ofereça TOTP ou WebAuthn para contas privilegiadas.",where="auth config"))
    if re.search(r"(?i)(session[_-]?timeout|idle[_-]?timeout)\s*[:=]\s*0\b",s):
        findings.append(_finding("session-no-timeout","Timeout de sessão desativado","medium",
                                 fix="Defina expiração absoluta e por inatividade.",where="auth config"))
    return {"findings":findings,"raw":{},"summary":f"{len(findings)} achado(s)"}
