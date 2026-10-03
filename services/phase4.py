"""JARVIS Cyber Lab — Expansão 4: Security Center 2.0, CTF 2.0 e IR Lab.
Tudo local/defensivo. Não executa payloads recebidos e não realiza exploração contra terceiros.
"""
from __future__ import annotations
import ast, hashlib, json, os, re, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "phase4_state.json"
_lock = threading.Lock()

CATEGORIES = ["Web Security","API Security","Authentication","Sessions","Cryptography","Networking","Linux Fundamentals","Forensics","Logs","Secure Coding","OSINT","Cloud Security","Blue Team","Incident Response"]


def _now(): return datetime.now(timezone.utc).isoformat()

def _load():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists(): return {"users":{},"audits":[]}
    try:
        d=json.loads(STATE_FILE.read_text(encoding="utf-8")); return d if isinstance(d,dict) else {"users":{},"audits":[]}
    except Exception: return {"users":{},"audits":[]}

def _save(d):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp=STATE_FILE.with_suffix('.tmp'); tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(STATE_FILE)

def _finding(rule,title,severity,evidence="",impact="",fix="",where=""):
    return {"id":rule,"rule":rule,"title":title,"severity":severity,"status":"confirmed","evidence":str(evidence)[:600],"impact":impact,"fix":fix,"where":where}

def _risk(findings):
    w={"critical":30,"high":20,"medium":10,"low":4,"info":0}
    return min(100,max(0,sum(w.get(f.get('severity'),0) for f in findings)))

def _score(findings, checks):
    # Score is based only on executed checks; untested controls are not counted as passes.
    executed=max(1,len(checks)); penalties=sum({"critical":30,"high":20,"medium":10,"low":4,"info":0}.get(f.get('severity'),0) for f in findings)
    return max(0, min(100, round(100 - (penalties / max(1,executed)))))

def _files():
    exts={'.py','.js','.html','.css','.json','.yml','.yaml','.toml','.ini','.cfg','.env','.txt','.md'}
    skip={'.git','__pycache__','node_modules','venv','.venv'}
    for p in BASE_DIR.rglob('*'):
        if p.is_file() and not any(x in skip for x in p.parts) and (p.suffix.lower() in exts or p.name.startswith('.env')):
            yield p

def self_audit():
    findings=[]; checks=[]; stats={"files":0,"python":0,"routes":0,"secrets_matches":0}
    py_files=[]
    for p in _files():
        stats['files']+=1
        if p.suffix=='.py': py_files.append(p); stats['python']+=1
    # Python syntax/AST and risky patterns — static only.
    # Scanner implementation and generated reports are excluded from secret/config pattern checks
    # to avoid matching their own detection regexes (false positives).
    scanner_files={Path(__file__).resolve(), BASE_DIR/"plugins"/"phase4_security_tools.py"}
    for p in py_files:
        try:
            text=p.read_text(encoding="utf-8",errors="ignore")
            ast.parse(text); checks.append({"check":"python_syntax","file":str(p.relative_to(BASE_DIR)),"status":"pass"})
        except SyntaxError as e:
            findings.append(_finding('self.syntax','Erro de sintaxe Python','high',f'{p.name}:{e.lineno}',fix='Corrija a sintaxe antes do deploy.',where=str(p.relative_to(BASE_DIR))))
        if p.resolve() in scanner_files:
            continue
        try:
            tree=ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node,(ast.Assign,ast.AnnAssign)):
                    names=[]
                    targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                    for t in targets:
                        if isinstance(t,ast.Name): names.append(t.id.lower())
                    if any(k in n for n in names for k in ('password','passwd','api_key','apikey','secret','token')) and isinstance(getattr(node,'value',None),ast.Constant) and isinstance(node.value.value,str) and len(node.value.value)>=8:
                        findings.append(_finding('self.hardcoded_secret','Possível segredo hardcoded','critical','constante suspeita detectada; valor omitido',fix='Revogue o segredo se real e mova para secret manager.',where=str(p.relative_to(BASE_DIR))))
        except Exception:
            pass
        # Config-only patterns; do not infer them from arbitrary Python source.
        if p.suffix.lower() in {'.env','.yml','.yaml','.toml','.ini','.cfg','.json'}:
            if re.search(r'(?i)debug\s*[=:]\s*true',text):
                findings.append(_finding('self.debug','Debug habilitado em configuração','medium','valor de debug detectado',fix='Desabilite debug em produção.',where=str(p.relative_to(BASE_DIR))))
            if re.search(r'(?i)verify\s*[=:]\s*false',text):
                findings.append(_finding('self.tls_verify','Verificação TLS desabilitada','high','verify=false detectado',fix='Mantenha validação de certificado habilitada.',where=str(p.relative_to(BASE_DIR))))
    checks.append({"check":"python_files_parsed","status":"pass","count":len(py_files)})
    # Route inventory and duplicate path/method detection.
    routes={}; route_count=0
    for p in py_files:
        text=p.read_text(encoding='utf-8',errors='ignore')
        for m in re.finditer(r'@(?:app|bp)\.(?:route|get|post|put|patch|delete)\([\"\']([^\"\']+)',text):
            route_count+=1; route=m.group(1); owners=routes.setdefault(route,set()); owners.add(str(p.relative_to(BASE_DIR)))
    stats['routes']=route_count
    for route,owners in routes.items():
        if len(owners)>1 and route not in ('/','/api/<path:path>'):
            findings.append(_finding('self.duplicate_route','Possível rota duplicada','medium',route,fix='Revise handlers para evitar conflito de roteamento.',where=', '.join(sorted(owners)[:4])))
    checks.append({"check":"route_inventory","status":"pass","count":route_count})
    # Dependency pinning; vulnerability status is reported only if pip-audit actually runs.
    req=BASE_DIR/'requirements.txt'; dep_status='not_run'
    if req.exists():
        unp=[]
        for line in req.read_text(encoding='utf-8',errors='ignore').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and not re.search(r'(==|~=|>=|<=|>|<)',line): unp.append(line)
        if unp: findings.append(_finding('self.dependencies_unpinned','Dependências sem versão fixada','low',', '.join(unp[:20]),fix='Fixe versões testadas e audite em CI.',where='requirements.txt'))
        checks.append({"check":"dependency_inventory","status":"pass","count":len([x for x in req.read_text(encoding='utf-8').splitlines() if x.strip() and not x.strip().startswith('#')])})
        try:
            proc=subprocess.run([sys.executable,'-m','pip_audit','-r',str(req),'--format','json'],cwd=str(BASE_DIR),capture_output=True,text=True,timeout=25)
            if proc.returncode in (0,1):
                data=json.loads(proc.stdout or '[]')
                vulns=0
                for item in data if isinstance(data,list) else data.get('dependencies',[]):
                    vulns += len(item.get('vulns',[]) or [])
                dep_status='executed'; checks.append({"check":"pip_audit","status":"pass" if vulns==0 else "review","vulnerabilities":vulns})
                if vulns:
                    findings.append(_finding('self.dependency_vuln','Dependências com vulnerabilidades reportadas pelo pip-audit','high',f'{vulns} vulnerabilidade(s)',fix='Atualize para versões corrigidas e rode os testes.',where='requirements.txt'))
            else: checks.append({"check":"pip_audit","status":"error","detail":"pip-audit retornou erro; nenhum resultado foi inferido."})
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            checks.append({"check":"pip_audit","status":"not_available","detail":"pip-audit não disponível ou não respondeu no limite; vulnerabilidades não foram inferidas."})
    else: checks.append({"check":"dependency_inventory","status":"review","detail":"requirements.txt não encontrado"})
    # Secrets scan over tracked-like text, never returning matched secret values.
    secret_patterns=[r'AKIA[0-9A-Z]{16}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'(?i)(?:api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\']{8,}["\']']
    secret_files=[]
    for p in _files():
        if p.name in {'.env.example','README.md'} or 'challenge' in p.name.lower() or p.parts[-2:] == ('plugins','cyber_lab_security_challenges.py'): continue
        text=p.read_text(encoding='utf-8',errors='ignore')[:2_000_000]
        if any(re.search(x,text) for x in secret_patterns): secret_files.append(str(p.relative_to(BASE_DIR)))
    if secret_files:
        findings.append(_finding('self.secrets','Possíveis secrets encontrados','critical',f'{len(secret_files)} arquivo(s) com padrão; valores omitidos',fix='Revogue segredos reais, remova do código e use secret manager.',where=', '.join(secret_files[:20])))
    checks.append({"check":"secret_detection","status":"pass","matches":len(secret_files)})
    # Security config presence.
    for fn,label in [('services/security.py','security service'),('services/permissions.py','permissions'),('services/scope.py','scope guard'),('services/tool_registry.py','tool registry')]:
        ok=(BASE_DIR/fn).exists(); checks.append({"check":label,"status":"pass" if ok else "fail"})
        if not ok: findings.append(_finding('self.control_missing',f'Controle ausente: {label}','high',fn,fix='Restaure o controle ou substitua por mecanismo equivalente.',where=fn))
    score=_score(findings,checks)
    return {"score":score,"risk":_risk(findings),"findings":findings,"checks":checks,"stats":stats,"generated_at":_now(),"scope":"JARVIS local project"}

def security_center(uid):
    from services import phase3, auth, telemetry, access_log
    audit=self_audit()
    posture=phase3.security_posture()
    sessions=phase3.sessions_for_dashboard('')
    events=phase3.recent_events(50)
    rec=[]
    for f in audit['findings']:
        if f['severity'] in ('critical','high','medium'): rec.append({"priority":f['severity'],"title":f['title'],"fix":f['fix']})
    if not rec: rec.append({"priority":"info","title":"Nenhum achado prioritário no conjunto de verificações executadas","fix":"Continue executando auditorias após alterações."})
    return {"security_score":audit['score'],"audit":audit,"posture":posture,"sessions":sessions,
            "auth":{"mfa":auth.totp_is_enabled(),"passkeys":len(auth.list_webauthn_credentials())},
            "events":events,"recommendations":rec[:20],"generated_at":_now()}

def report(data,fmt='md'):
    d=data or self_audit(); ts=d.get('generated_at') or _now()
    if fmt=='json': return json.dumps(d,ensure_ascii=False,indent=2)
    lines=[f'# JARVIS Security Report\n\nData: {ts}\n\nSecurity Score: **{d.get("score",d.get("security_score","—"))}/100**','\n## Resumo','Verificações executadas: '+str(len(d.get('checks',[]))),'Achados: '+str(len(d.get('findings',[])))]
    lines.append('\n## Descobertas')
    for f in d.get('findings',[]): lines.append(f"- **{f['severity'].upper()}** {f['title']} — {f.get('evidence','')} — Correção: {f.get('fix','')}")
    lines.append('\n## Testes realizados')
    for c in d.get('checks',[]): lines.append(f"- {c.get('status','?')} · {c.get('check','')}")
    return '\n'.join(lines)


def hardening_checklist():
    return [{"id":"auth-mfa","area":"Autenticação","title":"MFA/Passkeys","action":"Ative MFA e cadastre Passkeys quando suportadas.","risk":"alto"},
            {"id":"session","area":"Sessões","title":"Expiração e rotação","action":"Mantenha rotação pós-login, timeout e revogação global.","risk":"alto"},
            {"id":"cookies","area":"Cookies","title":"Secure/HttpOnly/SameSite","action":"Use atributos apropriados e HTTPS.","risk":"alto"},
            {"id":"headers","area":"Web","title":"Headers","action":"Use CSP, HSTS, nosniff, Referrer-Policy e Permissions-Policy.","risk":"médio"},
            {"id":"api","area":"APIs","title":"Auth + rate limit + validação","action":"Valide esquema, autorização por requisição e limite operações caras.","risk":"alto"},
            {"id":"uploads","area":"Uploads","title":"Isolamento de arquivos","action":"Valide conteúdo, tamanho, extensão e caminho final; não execute uploads.","risk":"alto"},
            {"id":"deps","area":"Dependências","title":"Auditoria contínua","action":"Fixe versões e rode pip-audit em CI/deploy.","risk":"médio"},
            {"id":"logs","area":"Logs","title":"Redação de segredos","action":"Nunca registre senha, token, cookie ou chave privada.","risk":"alto"},
            {"id":"permissions","area":"Permissões","title":"Least privilege","action":"Verifique capability no backend em cada operação protegida.","risk":"alto"},
            {"id":"errors","area":"Erros","title":"Erros seguros","action":"Não exponha stack traces em produção; use request_id para correlação.","risk":"médio"}]

CHALLENGES=[
{"id":"p4-csp","title":"CSP em camadas","category":"Web Security","difficulty":"iniciante","xp":120,"objective":"Identificar diretivas CSP ausentes e propor política sem quebrar scripts necessários.","scenario":"Uma resposta possui CSP permissiva e scripts inline.","context":"Você recebeu apenas headers e um inventário de scripts.","evidence":"Content-Security-Policy: default-src * 'unsafe-inline'","target":"headers-lab","files":["headers.txt"],"hints":["Comece por default-src.","Separe scripts inline de origens externas."],"answer_patterns":[r"default-src",r"script-src",r"nonce|hash"],"solution":"Defina uma CSP restritiva por origem e migre inline scripts para nonce/hash quando necessário.","explanation":"CSP reduz impacto de XSS ao limitar origens e formas de execução.","impact":"Scripts não confiáveis podem ganhar execução no contexto da aplicação.","detect":"Analise a política e procure wildcards/unsafe-inline.","fix":"Use allowlists mínimas e nonce/hash."},
{"id":"p4-openapi","title":"OpenAPI sem autenticação","category":"API Security","difficulty":"intermediário","xp":180,"objective":"Encontrar endpoints sensíveis sem securitySchemes/regras de segurança.","scenario":"Um OpenAPI documenta operações administrativas, mas não declara autenticação.","context":"O documento pode ser analisado estaticamente.","evidence":"paths: /admin/users, /admin/logs","target":"openapi-lab","files":["openapi.yaml"],"hints":["Procure securitySchemes.","Verifique operações administrativas."],"answer_patterns":[r"securitySchemes",r"security",r"/admin"],"solution":"Declare mecanismos de autenticação e security requirements adequados no contrato e imponha-os também no backend.","explanation":"Documentar segurança ajuda, mas a proteção real deve existir no servidor.","impact":"Clientes podem acreditar que uma API está protegida quando não está.","detect":"Compare paths sensíveis com security requirements.","fix":"Adicionar esquema e autorização server-side."},
{"id":"p4-auth-events","title":"Correlacionando logins","category":"Authentication","difficulty":"intermediário","xp":180,"objective":"Correlacionar falhas, sucesso e troca de sessão.","scenario":"Eventos de autenticação estão embaralhados.","context":"Você precisa reconstruir a sequência sem executar nada.","evidence":"FAIL user=admin; SUCCESS user=admin; SESSION_ROTATED user=admin","target":"auth-log","files":["auth.log"],"hints":["Ordene por timestamp.","Compare IP e request_id."],"answer_patterns":[r"FAIL",r"SUCCESS",r"SESSION_ROTATED"],"solution":"Ordene eventos, correlacione request_id/IP e determine a sequência sem presumir comprometimento.","explanation":"Correlação reduz falsos positivos em investigação.","impact":"Uma sequência incomum pode exigir revisão de sessão e origem.","detect":"Agrupe por usuário, IP e request_id.","fix":"Melhore logging estruturado e alertas."},
{"id":"p4-jwt-claims","title":"Claims JWT inconsistentes","category":"Sessions","difficulty":"avançado","xp":240,"objective":"Identificar validação ausente de exp/aud/iss.","scenario":"O serviço aceita tokens sem validar todas as claims de contexto.","context":"A análise é somente de código/configuração.","evidence":"decode(token, verify_signature=True); sem exp/aud/iss","target":"jwt-lab","files":["validator.py"],"hints":["Assinatura não é toda a política.","Pense em audiência e emissor."],"answer_patterns":[r"exp",r"aud",r"iss"],"solution":"Valide expiração, issuer e audience conforme a arquitetura, além da assinatura e algoritmo permitido.","explanation":"Claims de contexto limitam onde e por quanto tempo um token é válido.","impact":"Tokens podem ser aceitos fora do contexto previsto.","detect":"Revise o validador de claims.","fix":"Defina política server-side e testes de rejeição."},
{"id":"p4-timeline","title":"Timeline de incidente","category":"Forensics","difficulty":"intermediário","xp":200,"objective":"Construir uma linha do tempo a partir de logs, FIM e autenticação.","scenario":"Há quatro evidências independentes.","context":"Nenhum arquivo é executado.","evidence":"login-fail.txt + fim.json + app.log + auth.json","target":"timeline-lab","files":["login.log","fim.json","app.log"],"hints":["Use timestamps UTC.","Relacione request_id quando existir."],"answer_patterns":[r"timeline|linha do tempo|timestamp|request_id"],"solution":"Normalize timestamps, ordene eventos e correlacione IDs antes de formular a hipótese.","explanation":"Timeline é base para entender sequência e impacto.","impact":"Sem correlação, eventos isolados podem induzir conclusões erradas.","detect":"Normalize e agrupe evidências.","fix":"Use logs estruturados e sincronização de relógio."},
{"id":"p4-config-baseline","title":"Baseline de configuração","category":"Blue Team","difficulty":"iniciante","xp":120,"objective":"Encontrar desvios entre baseline e configuração atual.","scenario":"Uma configuração foi alterada fora da janela de mudança.","context":"Somente comparação de valores fornecidos.","evidence":"baseline.json vs current.json","target":"baseline-lab","files":["baseline.json","current.json"],"hints":["Liste somente diferenças.","Priorize controles de segurança."],"answer_patterns":[r"diff|diferença|changed|alterad"],"solution":"Compare chaves e valores e destaque desvios de controles críticos.","explanation":"Baseline reduz drift de configuração.","impact":"Drift pode remover controles esperados.","detect":"Comparação periódica.","fix":"Controle de mudanças e baseline versionada."},
{"id":"p4-cloud-policy","title":"Cloud policy simulada","category":"Cloud Security","difficulty":"avançado","xp":240,"objective":"Identificar bucket público e privilégio excessivo em política simulada.","scenario":"Você recebe JSON de uma conta fictícia.","context":"Nada é aplicado em cloud real.","evidence":"Allow Principal=* Action=s3:* Resource=*","target":"cloud-sim","files":["policy.json"],"hints":["Observe Principal e Resource.","Least privilege é a pista."],"answer_patterns":[r"Principal",r"Resource",r"Action",r"\*"],"solution":"Restringir principal, ações e recursos ao mínimo necessário.","explanation":"Políticas amplas aumentam impacto potencial.","impact":"Acesso excessivo a dados/recursos simulados.","detect":"Audite statements Allow e wildcards.","fix":"Least privilege e revisão periódica."},
{"id":"p4-osint","title":"OSINT com fontes públicas","category":"OSINT","difficulty":"iniciante","xp":100,"objective":"Separar fatos verificáveis de inferências em fontes públicas fornecidas.","scenario":"Um conjunto de páginas públicas foi salvo no laboratório.","context":"Não há coleta contra pessoas reais além dos arquivos fornecidos.","evidence":"sources.json","target":"osint-lab","files":["sources.json"],"hints":["Cite a fonte.","Não transforme ausência de evidência em evidência de ausência."],"answer_patterns":[r"fonte|source|evidence|evidência"],"solution":"Registre cada afirmação com sua fonte e diferencie fato observado de inferência.","explanation":"OSINT exige rastreabilidade e cautela epistemológica.","impact":"Inferências sem fonte podem contaminar uma investigação.","detect":"Revise cada claim contra sua fonte.","fix":"Mantenha cadeia de fontes e timestamps."},
{"id":"p4-sast","title":"SAST de validação","category":"Secure Coding","difficulty":"intermediário","xp":180,"objective":"Identificar entrada controlada pelo usuário que chega a uma operação sensível sem validação.","scenario":"Um pequeno trecho Python contém fluxo inseguro.","context":"A tarefa é localizar o fluxo e sugerir correção, não executar o código.","evidence":"request.args -> open(path)","target":"sast-lab","files":["sample.py"],"hints":["Siga a origem da entrada.","Valide o caminho antes do sink."],"answer_patterns":[r"request",r"validate|sanit",r"safe_join|resolve|secure_filename"],"solution":"Valide e normalize a entrada, imponha um diretório raiz e rejeite escapes.","explanation":"SAST procura padrões de fluxo perigosos antes da execução.","impact":"Entradas não confiáveis podem controlar operações sensíveis.","detect":"Triage de source-to-sink.","fix":"Validação contextual e allowlists."},
{"id":"p4-ir-containment","title":"Containment sem destruir evidências","category":"Incident Response","difficulty":"intermediário","xp":200,"objective":"Escolher ações de contenção que preservem evidências no laboratório.","scenario":"Há sinais de comprometimento simulado.","context":"As ações são apenas decisões textuais, sem execução.","evidence":"alerts.json + auth.log + fim.json","target":"ir-lab","files":["alerts.json","auth.log","fim.json"],"hints":["Preserve logs antes de limpar.","Revogue credenciais somente após registrar o contexto."],"answer_patterns":[r"preserv|evidência|contain|contenção|revog"],"solution":"Registrar evidências, isolar logicamente o serviço e revogar credenciais comprometidas conforme plano.","explanation":"Contenção precisa reduzir risco sem apagar o rastro necessário à investigação.","impact":"Limpeza prematura pode destruir evidências.","detect":"Checklist IR e timeline.","fix":"Playbooks, snapshots e cadeia de custódia."},
]

def list_challenges():
    return [{k:c[k] for k in ('id','title','category','difficulty','xp')} for c in CHALLENGES]

def get_challenge(cid,reveal=False):
    c=next((x for x in CHALLENGES if x['id']==cid),None)
    if not c:return None
    out=dict(c)
    if not reveal: out.pop('solution',None)
    return out

def check_challenge(uid,cid,answer,hint=False,reveal=False):
    c=next((x for x in CHALLENGES if x['id']==cid),None)
    if not c:return {"ok":False,"error":"Desafio não encontrado."}
    d=str(answer or '')
    if hint:
        st=_load(); u=st['users'].setdefault(uid,{"xp":0,"completed":[],"history":[],"hints":{}}); idx=int(u.setdefault('hints',{}).get(cid,0)); hints=c.get('hints',[]); idx=min(idx+1,len(hints)); u['hints'][cid]=idx; _save(st)
        return {"ok":True,"hint":hints[idx-1] if idx else hints[0] if hints else "Sem pista disponível."}
    passed=all(re.search(p,d,re.I) for p in c.get('answer_patterns',[]))
    st=_load(); u=st['users'].setdefault(uid,{"xp":0,"completed":[],"history":[],"hints":{}})
    already=cid in u.get('completed',[])
    if passed and not already:
        u['completed'].append(cid); u['xp']=int(u.get('xp',0))+int(c['xp']); u['history'].append({"challenge":cid,"at":_now(),"xp":c['xp']}); u['history']=u['history'][-200:]
        _save(st)
    out={"ok":True,"passed":passed,"already_completed":already,"xp_awarded":0 if already else c['xp'] if passed else 0,"criteria":c['answer_patterns']}
    if passed or reveal: out.update({"explanation":c['explanation'],"solution":c['solution'],"impact":c['impact'],"detect":c['detect'],"fix":c['fix']})
    return out

def progression(uid):
    st=_load(); u=st['users'].setdefault(uid,{"xp":0,"completed":[],"history":[],"hints":{}}); xp=int(u.get('xp',0)); level=1+xp//300
    completed=set(u.get('completed',[])); bycat={cat:0 for cat in CATEGORIES}
    for c in CHALLENGES:
        if c['id'] in completed: bycat[c['category']]=bycat.get(c['category'],0)+1
    badges=[]
    if len(completed)>=1: badges.append({"id":"first","name":"Primeiro Desafio","icon":"🎯"})
    if len(completed)>=5: badges.append({"id":"five","name":"Analista em Formação","icon":"🔎"})
    if len(completed)>=10: badges.append({"id":"ten","name":"Lab Specialist","icon":"🛡️"})
    if any(v>=2 for v in bycat.values()): badges.append({"id":"mastery","name":"Categoria em Progresso","icon":"📚"})
    return {"xp":xp,"level":level,"xp_into_level":xp%300,"xp_per_level":300,"completed":list(completed),"completed_count":len(completed),"badges":badges,"category_mastery":bycat,"history":u.get('history',[])[-50:],"local_ranking":[{"label":"Você","xp":xp,"completed":len(completed)}]}

def incident_catalog():
    return [
      {"id":"ir-web-01","title":"Acesso suspeito e alteração de arquivo","difficulty":"intermediário","xp":250,"events":["FAIL admin 10:01","SUCCESS admin 10:04","file_changed /srv/app.py 10:05","new_session 10:05"],"tasks":["identificar incidente","correlacionar eventos","montar timeline","classificar severidade","propor contenção","gerar relatório"]},
      {"id":"ir-api-01","title":"API com falhas e pico de requisições","difficulty":"avançado","xp":300,"events":["429 spike /api/login","FAIL user=service","config_changed rate_limit","token_rotated"],"tasks":["encontrar indicador","determinar causa provável","propor contenção","plano de correção"]}
    ]

def _analyze_text(text,kind):
    s=str(text or ''); low=s.lower(); findings=[]
    def add(rule,title,sev,fix,evidence=''): findings.append(_finding(rule,title,sev,evidence=evidence,fix=fix,impact='Revisar o controle no ambiente autorizado.',where=kind))
    if kind=='csp':
        if 'content-security-policy' not in low: add('csp.missing','CSP ausente','high','Defina CSP por origem e nonce/hash para scripts necessários.')
        if '*' in s or 'unsafe-inline' in low: add('csp.permissive','CSP permissiva','medium','Remova wildcards e reduza unsafe-inline/unsafe-eval.')
    elif kind=='methods':
        for m in re.findall(r'(?i)\b(?:GET|POST|PUT|PATCH|DELETE|TRACE|CONNECT|OPTIONS|HEAD)\b',s):
            if m.upper() in ('TRACE','CONNECT'): add('http.method','Método HTTP sensível habilitado','medium','Desabilite métodos não necessários.',m.upper())
    elif kind=='redirects':
        if 'http://' in low: add('redirect.http','Redirect para HTTP','high','Mantenha a cadeia em HTTPS.',s[:300])
        if re.search(r'(?i)location:\s*(?:https?:)?//',s): add('redirect.external','Redirect externo detectado','low','Use allowlist de destinos quando o destino for controlado por entrada.')
    elif kind=='cache':
        if 'cache-control' not in low: add('cache.missing','Cache-Control ausente','medium','Defina política de cache conforme sensibilidade do conteúdo.')
        if 'public' in low and any(x in low for x in ('authorization','set-cookie','private')): add('cache.sensitive','Possível cache público de conteúdo sensível','high','Use private/no-store para respostas sensíveis.')
    elif kind=='jwt':
        for claim in ('exp','aud','iss'):
            if claim not in low: add('jwt.claim','Claim JWT ausente na configuração fornecida','medium',f'Valide {claim} conforme a arquitetura.')
        if 'none' in low or 'verify=false' in low: add('jwt.weak','Configuração JWT insegura','high','Use allowlist de algoritmos e verificação criptográfica server-side.')
    elif kind in ('api','openapi'):
        if 'securityschemes' not in low and 'authorization' not in low: add('api.auth','Não há evidência de mecanismo de autenticação','high','Defina autenticação e autorização no contrato e backend.')
        if 'admin' in low and 'security' not in low: add('api.admin','Endpoint administrativo sem requisito de segurança declarado','high','Declare security requirement e imponha-o no backend.')
    elif kind=='dns':
        if 'dnssec' not in low: add('dns.dnssec','DNSSEC não indicado no material','low','Avalie DNSSEC quando suportado pelo domínio.')
    elif kind=='tls':
        if re.search(r'(?i)tls\s*1\.[01]\b|sslv',s): add('tls.legacy','Protocolo TLS legado indicado','high','Use TLS moderno e desative versões obsoletas.')
    elif kind=='cert':
        if 'expired' in low or 'notafter' in low and 'past' in low: add('cert.expired','Certificado aparentemente expirado','high','Renove o certificado e valide a cadeia.')
    elif kind=='service':
        if 'root' in low or 'privileged=true' in low: add('service.priv','Serviço com privilégios elevados','high','Use usuário dedicado e menor privilégio.')
    elif kind=='exposure':
        for port in re.findall(r'\b(?:21|23|25|139|445|3389|5900)\b',s): add('network.exposed','Serviço sensível listado','medium','Restrinja exposição e autenticação; mantenha apenas o necessário.',port)
    elif kind in ('ioc','correlation','auth','bruteforce'):
        fails=len(re.findall(r'(?i)\b(?:fail|failed|denied|invalid|401|403)\b',s)); successes=len(re.findall(r'(?i)\b(?:success|successful|200)\b',s))
        if fails>=5: add('auth.burst','Rajada de eventos de falha','medium','Agrupe por identidade/origem e aplique rate limit/alerta.',f'{fails} falhas')
        if fails and successes: add('auth.correlation','Falhas e sucesso presentes no mesmo conjunto','low','Correlacione timestamps, request_id e sessão antes de concluir.',f'{fails} falhas / {successes} sucessos')
    elif kind=='baseline':
        if 'changed' in low or 'modified' in low or 'dif' in low: add('baseline.drift','Desvio de baseline detectado','medium','Revise mudança e atualize baseline somente após aprovação.')
    elif kind=='dependencies':
        if re.search(r'(?m)^[A-Za-z0-9_.-]+\s*$',s): add('deps.unpinned','Dependência sem versão fixada','low','Fixe versões testadas e rode auditoria de vulnerabilidades.')
        if 'vulnerability' in low or 'cve-' in low: add('deps.reported','Vulnerabilidade reportada no material fornecido','high','Confirme com o auditor de dependências e atualize para versão corrigida.',s[:300])
    elif kind=='secrets':
        if re.search(r'AKIA[0-9A-Z]{16}|PRIVATE KEY|(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\']{8,}',s): add('secret.found','Possível segredo exposto','critical','Revogue se real, remova do código e use secret manager.','[valor omitido]')
    elif kind in ('metadata','evidence'):
        if 'author' in low or 'gps' in low or 'location' in low: add('metadata.sensitive','Metadado potencialmente sensível','low','Remova metadados não necessários antes de compartilhar.')
    elif kind in ('hash','integrity'):
        hs=re.findall(r'\b[a-fA-F0-9]{64}\b',s); 
        if len(hs)>=2 and hs[0].lower()!=hs[1].lower(): add('hash.mismatch','Hashes SHA-256 diferentes','high','Investigue a alteração e compare com referência confiável.')
    elif kind in ('timeline','logtimeline'):
        stamps=re.findall(r'\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d',s)
        if stamps: add('timeline.generated','Eventos temporais identificados','info','Normalize timezone e ordene cronologicamente.',f'{len(stamps)} timestamps')
    elif kind=='sast':
        patterns=[(r'open\([^\n]*request\.', 'Entrada pode alcançar open()', 'high','Normalize o caminho e mantenha-o dentro de um root permitido.'),(r'execute\([^\n]*(request\.|input\()', 'Entrada pode alcançar execução de comando/consulta', 'high','Use APIs parametrizadas e validação contextual.')]
        for pat,t,sev,fix in patterns:
            if re.search(pat,s,re.I): add('sast.pattern',t,sev,fix)
    elif kind in ('config','patterns'):
        if re.search(r'(?i)debug\s*[=:]\s*true|verify\s*[=:]\s*false|allow_all\s*[=:]\s*true',s): add('config.insecure','Configuração potencialmente insegura','high','Desative debug, mantenha TLS verification e reduza allowlists permissivas.')
    return {'findings':findings,'raw':{'kind':kind},'summary':f'{len(findings)} achado(s)'}
