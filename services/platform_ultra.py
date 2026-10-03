"""JARVIS Ultra Platform — incremental account, arcade, diagnostics and UX layer.
Reuses existing auth, gamification, telemetry and Ultra/SOC stores. Defensive/local only.
"""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, time, difflib
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from services import auth, phase5, gamification, ultra_ops

BASE = Path(__file__).resolve().parent.parent
DB = BASE / 'data' / 'cyberlab.db'

GAMES = [
 ('snake','Snake','Arcade clássico com controles por teclado e toque','ARCADE'),
 ('pong','Pong','Duelo local contra a IA do jogo','ARCADE'),
 ('breakout','Breakout','Quebre blocos e aumente sua pontuação','ARCADE'),
 ('memory','Memory','Encontre pares de conceitos do JARVIS','PUZZLE'),
 ('tictactoe','Tic-Tac-Toe','Jogo de estratégia em grade 3x3','PUZZLE'),
 ('2048','2048','Combine números e alcance 2048','PUZZLE'),
 ('reaction','Reaction Test','Teste de tempo de reação','ARCADE'),
 ('typing','Typing Challenge','Digite conceitos de tecnologia rapidamente','EDUCATIONAL'),
 ('maze','Maze','Encontre a saída do labirinto','PUZZLE'),
 ('cyber-quiz','Cyber Quiz','Perguntas defensivas de cybersecurity','CYBER'),
 ('code-puzzle','Code Puzzle','Puzzles de programação segura','EDUCATIONAL'),
 ('cyber-memory','Cyber Memory','Memória com conceitos de segurança','EDUCATIONAL'),
 ('code-runner','Code Runner','Identifique a saída segura','EDUCATIONAL'),
 ('logic-grid','Logic Grid','Desafios de lógica defensiva','PUZZLE'),
 ('password-defense','Password Defense','Escolha controles de autenticação','CYBER'),
 ('packet-defender','Packet Defender','Classifique eventos fictícios','CYBER'),
 ('binary-challenge','Binary Challenge','Binário, hexadecimal e ASCII','EDUCATIONAL'),
 ('cipher-lab','Cipher Lab','Puzzles de codificação e conceitos','CYBER'),
 ('security-tower','Security Tower','Responda a eventos defensivos','CYBER'),
 ('bug-hunter','Bug Hunter','Encontre problemas em código fictício','CYBER'),
 ('terminal-puzzle','Terminal Puzzle','Puzzles seguros de terminal','EDUCATIONAL'),
]
QUIZZES = {
 'python': ('Python',[('Qual palavra inicia uma função?',['def','func','fn','lambda'],0,'def inicia uma função em Python.'),('Qual estrutura é iterável?',['list','int','bool','None'],0,'Listas são iteráveis.')]),
 'javascript': ('JavaScript',[('Qual declaração cria uma constante?',['const','letvar','fixed','static'],0,'const cria uma ligação que não pode ser reatribuída.')]),
 'web-security': ('Web Security',[('Qual controle ajuda contra CSRF?',['Token anti-CSRF','Base64','DNS','gzip'],0,'Tokens anti-CSRF vinculam requisições a uma sessão/contexto.')]),
 'cyber-security': ('Cyber Security',[('O que é least privilege?',['Menor privilégio necessário','Acesso total','Senha curta','Sem autenticação'],0,'Concede somente os privilégios necessários.')]),
 'networking': ('Networking',[('Qual protocolo é orientado a conexão?',['TCP','UDP','ARP','ICMP'],0,'TCP estabelece uma conexão e oferece entrega ordenada.')]),
 'linux': ('Linux',[('Qual comando lista arquivos?',['ls','pwdx','show','dirall'],0,'ls lista entradas de diretório.')]),
 'git': ('Git',[('Qual comando cria um commit?',['git commit','git save','git push-only','git snapshot'],0,'git commit registra alterações no histórico local.')]),
 'apis': ('APIs',[('Qual método HTTP é normalmente usado para leitura?',['GET','DELETE','PATCH','CONNECT'],0,'GET é usado para recuperar uma representação.')]),
 'cloud': ('Cloud',[('O que IAM controla?',['Identidade e acesso','Imagens','Logs de vídeo','Compressão'],0,'IAM gerencia identidades, autenticação e autorização.')]),
 'devsecops': ('DevSecOps',[('SAST analisa principalmente o quê?',['Código-fonte','Tráfego de terceiros','Hardware','DNS público'],0,'SAST analisa código sem precisar executá-lo.')]),
}
PATHS = {
 'programming':['Python','JavaScript','Git','Quiz'], 'web-development':['HTML/CSS','JavaScript','APIs','Secure Coding'],
 'cybersecurity':['Authentication','Web Security','Security Basics','Challenges'], 'blue-team':['SOC','Logging','Incident Response','Alert Triage'],
 'soc':['Events','Alerts','Cases','Timeline'], 'devsecops':['Secure Coding','Dependencies','CI/CD','Secrets'], 'networking':['TCP/IP','DNS','HTTP','Defensive Monitoring']
}
LEVEL_NAMES = ['NOVATO','EXPLORADOR','ANALISTA','OPERADOR','ESPECIALISTA','ARQUITETO']


def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]

def conn():
    c=phase5.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS u2_flags(key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,updated_by TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS u2_game_scores(owner_uid TEXT NOT NULL,game_id TEXT NOT NULL,score INTEGER NOT NULL,duration_ms INTEGER DEFAULT 0,played_at TEXT NOT NULL,PRIMARY KEY(owner_uid,game_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS u2_game_history(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,game_id TEXT NOT NULL,score INTEGER NOT NULL,duration_ms INTEGER DEFAULT 0,played_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u2_daily(owner_uid TEXT NOT NULL,day TEXT NOT NULL,mission TEXT NOT NULL,done INTEGER DEFAULT 0,PRIMARY KEY(owner_uid,day,mission))''')
    c.execute('''CREATE TABLE IF NOT EXISTS u2_errors(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT DEFAULT '',error_id TEXT NOT NULL,message TEXT NOT NULL,route TEXT DEFAULT '',status INTEGER DEFAULT 0,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u2_exports(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL,allowed INTEGER DEFAULT 1)''')
    return c


def account_security(owner):
    sessions=[x for x in auth.list_auth_sessions() if x.get('uid')==uid(owner)]
    enabled=bool(auth.totp_is_enabled())
    passkeys=auth.list_webauthn_credentials()
    return {'status':'PROTEGIDO' if enabled or passkeys else 'RECOMENDADO','authentication':'CONFIGURED' if auth.has_master_password() else 'PENDING','two_factor':enabled,'passkeys':passkeys,'sessions':sessions,'session_count':len(sessions),'recovery_codes_remaining':auth.totp_recovery_codes_remaining(),'owner_email_configured':bool(auth.get_owner_email()),'activity_note':'Segredos, tokens e códigos não são exibidos.'}


def revoke_session(owner,prefix):
    sessions={x['id'] for x in account_security(owner)['sessions']}
    if prefix not in sessions: return False
    ok=auth.revoke_session_id(prefix)
    if ok: phase5.audit(owner,'SESSION_REVOKED',prefix,'session security center')
    return ok


def current_session_prefix(session_id):
    return hashlib.sha256((session_id or '').encode('utf-8')).hexdigest()[:12]

def revoke_others(owner,current_prefix=''):
    n=0
    current_prefix=current_prefix or current_session_prefix('')
    for s in account_security(owner)['sessions']:
        if s['id']==current_prefix: continue
        if auth.revoke_session_id(s['id']): n+=1
    phase5.audit(owner,'SESSIONS_REVOKED_OTHERS','account',str(n))
    return n


def feature_flags(owner=None):
    defaults={'HOLOGRAM_V2':True,'ARCADE':True,'PASSKEY':bool(auth.list_webauthn_credentials()),'NEW_DASHBOARD':True,'COMMAND_CENTER':True,'PROJECT_WORKSPACE':True}
    with conn() as c:
        rows={r['key']:bool(r['enabled']) for r in c.execute('SELECT key,enabled FROM u2_flags').fetchall()}
    return {k:rows.get(k,v) for k,v in defaults.items()}


def set_flag(owner,key,enabled):
    key=str(key or '')[:60].upper()
    if key not in feature_flags(owner): raise ValueError('Feature flag não reconhecida')
    with conn() as c:c.execute('INSERT OR REPLACE INTO u2_flags(key,enabled,updated_at,updated_by) VALUES(?,?,?,?)',(key,int(bool(enabled)),now(),uid(owner)))
    phase5.audit(owner,'FEATURE_FLAG_CHANGED',key,str(bool(enabled)))
    return feature_flags(owner)


def arcade_catalog(owner):
    with conn() as c:
        scores={r['game_id']:dict(r) for r in c.execute('SELECT * FROM u2_game_scores WHERE owner_uid=?',(uid(owner),)).fetchall()}
    difficulty = {'snake':'Médio','pong':'Médio','breakout':'Médio','memory':'Fácil','tictactoe':'Fácil','2048':'Difícil','reaction':'Fácil','typing':'Médio','maze':'Médio','cyber-quiz':'Fácil','code-puzzle':'Médio'}
    return [{'id':gid,'name':name,'description':desc,'category':cat,'difficulty':difficulty.get(gid,'Médio'),'record':scores.get(gid,{}).get('score',0),'xp':min(100,max(10,50)),'status':'READY','last_played':scores.get(gid,{}).get('played_at')} for gid,name,desc,cat in GAMES]


def submit_game(owner,game_id,score,duration_ms=0):
    if game_id not in {x[0] for x in GAMES}: raise ValueError('Jogo não encontrado')
    # Guardrails against client-side score inflation. Games remain educational, not a trust boundary.
    score=max(0,min(int(score or 0),100000)); duration=max(0,min(int(duration_ms or 0),3600000)); t=now()
    with conn() as c:
        old=c.execute('SELECT score FROM u2_game_scores WHERE owner_uid=? AND game_id=?',(uid(owner),game_id)).fetchone()
        best=max(score,int(old['score']) if old else 0)
        c.execute('INSERT OR REPLACE INTO u2_game_scores(owner_uid,game_id,score,duration_ms,played_at) VALUES(?,?,?,?,?)',(uid(owner),game_id,best,duration,t))
        c.execute('INSERT INTO u2_game_history(owner_uid,game_id,score,duration_ms,played_at) VALUES(?,?,?,?,?)',(uid(owner),game_id,score,duration,t))
    # Reuses the existing gamification store instead of creating a second XP system.
    xp=min(50,max(5,score//100 if score else 5))
    gamification.add_activity(owner,'game',game_id,score) if hasattr(gamification,'add_activity') else None
    if hasattr(gamification,'record_game_result'): gamification.record_game_result(owner,game_id,xp)
    phase5.audit(owner,'ARCADE_GAME',game_id,f'score={score}')
    return {'game_id':game_id,'score':score,'record':best,'xp_awarded':xp,'played_at':t}


def arcade_profile(owner):
    cat=arcade_catalog(owner); played=sum(1 for x in cat if x['last_played']); best=sum(int(x['record'] or 0) for x in cat)
    u=gamification.public_user(owner)
    level=min(len(LEVEL_NAMES)-1,(int(u.get('level',1))-1)//3)
    return {'xp':u['xp'],'level':u['level'],'rank_name':LEVEL_NAMES[level],'games_played':played,'records':sum(1 for x in cat if x['record']),'best_score_total':best,'achievements':u['achievements']}


def daily_missions(owner):
    day=datetime.now(timezone.utc).date().isoformat(); missions=['Complete 1 desafio','Jogue 1 partida','Leia 1 artigo','Analise 1 finding']
    with conn() as c:
        for m in missions:c.execute('INSERT OR IGNORE INTO u2_daily(owner_uid,day,mission,done) VALUES(?,?,?,0)',(uid(owner),day,m))
        rows=[dict(r) for r in c.execute('SELECT mission,done FROM u2_daily WHERE owner_uid=? AND day=?',(uid(owner),day)).fetchall()]
    return rows


def quiz_catalog(): return [{'id':k,'name':v[0],'questions':len(v[1])} for k,v in QUIZZES.items()]
def quiz_get(qid):
    q=QUIZZES.get(qid); 
    if not q:return None
    return {'id':qid,'name':q[0],'questions':[{'question':x[0],'options':x[1]} for x in q[1]]}
def quiz_check(owner,qid,index,answer):
    q=QUIZZES.get(qid); 
    if not q or not (0<=int(index)<len(q[1])): raise ValueError('Quiz inválido')
    item=q[1][int(index)]; ok=int(answer)==int(item[2]);
    return {'correct':ok,'explanation':item[3],'xp':10 if ok else 0}


def diagnostics():
    py=list(BASE.rglob('*.py')); templates=list((BASE/'templates').rglob('*.html')); js=list((BASE/'static').rglob('*.js')); css=list((BASE/'static').rglob('*.css'))
    compile_errors=[]
    import py_compile
    for p in py:
        try: py_compile.compile(str(p),doraise=True)
        except Exception as e: compile_errors.append({'file':str(p.relative_to(BASE)),'error':str(e)[:300]})
    db_ok=True; db_error=''
    try: phase5.conn().execute('SELECT 1').fetchone()
    except Exception as e: db_ok=False; db_error=str(e)[:300]
    return {'status':'ERROR' if compile_errors or not db_ok else 'OK','backend':{'python_files':len(py),'compile_errors':compile_errors[:30]},'frontend':{'templates':len(templates),'javascript':len(js),'css':len(css)},'database':{'status':'OK' if db_ok else 'ERROR','error':db_error},'generated_at':now()}


def backup_safety():
    candidates=[]
    for p in [DB, BASE/'data'/'gamification.json']:
        if p.exists():
            b=p.read_bytes(); candidates.append({'file':str(p.relative_to(BASE)),'exists':True,'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'modified':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()})
    return {'files':candidates,'note':'Hash de integridade; nenhum conteúdo sensível é exibido.'}


def security_checklist():
    base=ultra_ops.baseline(); mapping={x['control']:x for x in base}
    names=['DEBUG','Secure Cookies','HttpOnly','SameSite','CSRF','CSP','Rate Limit','Session Timeout','2FA','RBAC','Audit Logs','Secret Management','Upload Restrictions','Error Handling']
    return [{'control':n,'status':mapping.get(n,{}).get('status','NOT CHECKED'),'evidence':mapping.get(n,{}).get('evidence','Sem evidência local disponível.'),'fix':mapping.get(n,{}).get('fix','Verificar no Security Center.')} for n in names]


def system_health():
    return {'services':[
        {'name':'JARVIS CORE','status':'ONLINE'}, {'name':'AI','status':'ONLINE' if bool(os.getenv('OPENROUTER_API_KEY') or os.getenv('GEMINI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')) else 'DEGRADED'},
        {'name':'DATABASE','status':'ONLINE' if diagnostics()['database']['status']=='OK' else 'OFFLINE'}, {'name':'SECURITY','status':'ONLINE'},
        {'name':'CYBER LAB','status':'ONLINE'}, {'name':'ARCADE','status':'ONLINE'}, {'name':'HOLOGRAM','status':'ONLINE'}, {'name':'PROJECTS','status':'ONLINE'}]}


def release_info():
    return {'version':os.getenv('JARVIS_VERSION','Ultra Platform'),'build':os.getenv('RENDER_GIT_COMMIT','unknown'),'environment':os.getenv('FLASK_ENV','production'),'generated_at':now(),'changelog':['Ultra Platform: account security, diagnostics, arcade, learning, command integration.']}


def activity(owner):
    rows=ultra_ops.timeline(owner,30)[:100]
    return rows


def project_templates():
    return [{'id':k,'name':k.replace('-',' ').title(),'description':d} for k,d in [('flask','Flask web app'),('html-css-js','HTML/CSS/JS app'),('api','Defensive API project'),('dashboard','Dashboard'),('portfolio','Portfolio'),('cyber-lab','Cyber Lab'),('landing-page','Landing Page'),('study-app','Study application')]]


def learning_paths(): return [{'id':k,'name':k.replace('-',' ').title(),'modules':v,'progress':0} for k,v in PATHS.items()]


def code_diff(before,after,filename='arquivo'):
    a=str(before or '').splitlines(); b=str(after or '').splitlines()
    if len(a)>5000 or len(b)>5000: raise ValueError('Diff muito grande; limite de 5000 linhas.')
    return {'file':filename[:160],'diff':'\n'.join(difflib.unified_diff(a,b,fromfile='ANTES',tofile='DEPOIS',lineterm=''))}
