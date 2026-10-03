"""JARVIS Evolution 2 — incremental orchestration layer.
Reuses the existing SQLite database, auth/RBAC, telemetry, gamification and project services.
Only local/defensive operations are exposed. No arbitrary code execution is added here.
"""
from __future__ import annotations
import hashlib, json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from services import platform_ultra, core2, telemetry, ultra_ops, auth, security, gamification, mega_expansion

BASE = Path(__file__).resolve().parent.parent
DB = BASE / 'data' / 'cyberlab.db'

def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'anon')[:120]

def conn():
    c = platform_ultra.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS evo_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,title TEXT NOT NULL,description TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'TODO',priority TEXT NOT NULL DEFAULT 'NORMAL',due_at TEXT DEFAULT '',category TEXT DEFAULT 'GENERAL',checklist_json TEXT DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS evo_task_events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER NOT NULL,owner_uid TEXT NOT NULL,event TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS evo_workflows(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'DRAFT',steps_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS evo_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,project_key TEXT NOT NULL,label TEXT NOT NULL,manifest_json TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS evo_ai_modes(owner_uid TEXT PRIMARY KEY,mode TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    return c

def _safe_status(status):
    return status if status in {'TODO','IN PROGRESS','DONE','BLOCKED','CANCELLED'} else 'TODO'

def tasks(owner, status=''):
    with conn() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM evo_tasks WHERE owner_uid=? ORDER BY updated_at DESC LIMIT 200',(uid(owner),)).fetchall()]
    for r in rows:
        try:r['checklist']=json.loads(r.pop('checklist_json') or '[]')
        except Exception:r['checklist']=[]
    if status: rows=[r for r in rows if r['status']==_safe_status(status)]
    return rows

def task_create(owner, data):
    title=str(data.get('title') or '').strip()[:160]
    if not title: raise ValueError('Título obrigatório.')
    status=_safe_status(str(data.get('status') or 'TODO').upper())
    priority=str(data.get('priority') or 'NORMAL').upper()[:20]
    category=str(data.get('category') or 'GENERAL')[:60]
    desc=str(data.get('description') or '')[:2000]
    due=str(data.get('due_at') or '')[:80]
    checklist=data.get('checklist') if isinstance(data.get('checklist'),list) else []
    checklist=[{'text':str(x.get('text') if isinstance(x,dict) else x)[:200],'done':bool(x.get('done')) if isinstance(x,dict) else False} for x in checklist[:30]]
    t=now()
    with conn() as c:
        cur=c.execute('INSERT INTO evo_tasks(owner_uid,title,description,status,priority,due_at,category,checklist_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid(owner),title,desc,status,priority,due,category,json.dumps(checklist,ensure_ascii=False),t,t))
        tid=cur.lastrowid;c.execute('INSERT INTO evo_task_events(task_id,owner_uid,event,created_at) VALUES(?,?,?,?)',(tid,uid(owner),'CREATED',t))
    try: security.audit_event('TASK_CREATED',target=title,ok=True,role=permissions_role())
    except Exception: pass
    return task_get(owner,tid)

def permissions_role():
    # Avoid importing Flask request/session from this service.
    return os.getenv('JARVIS_ROLE_CONTEXT','')[:30] or 'authenticated'

def task_get(owner, tid):
    with conn() as c:r=c.execute('SELECT * FROM evo_tasks WHERE id=? AND owner_uid=?',(int(tid),uid(owner))).fetchone()
    if not r:return None
    d=dict(r)
    try:d['checklist']=json.loads(d.pop('checklist_json') or '[]')
    except Exception:d['checklist']=[]
    return d

def task_update(owner, tid, data):
    current=task_get(owner,tid)
    if not current: raise ValueError('Tarefa não encontrada.')
    fields=[];vals=[]
    for key in ('title','description','due_at','category'):
        if key in data: fields.append(key+'=?');vals.append(str(data.get(key) or '')[:2000])
    if 'status' in data: fields.append('status=?');vals.append(_safe_status(str(data.get('status') or 'TODO').upper()))
    if 'priority' in data: fields.append('priority=?');vals.append(str(data.get('priority') or 'NORMAL').upper()[:20])
    if 'checklist' in data and isinstance(data['checklist'],list):
        cl=[{'text':str(x.get('text') if isinstance(x,dict) else x)[:200],'done':bool(x.get('done')) if isinstance(x,dict) else False} for x in data['checklist'][:30]]
        fields.append('checklist_json=?');vals.append(json.dumps(cl,ensure_ascii=False))
    if not fields:return current
    t=now();vals.extend([t,int(tid),uid(owner)])
    with conn() as c:
        c.execute('UPDATE evo_tasks SET '+','.join(fields)+',updated_at=? WHERE id=? AND owner_uid=?',vals)
        c.execute('INSERT INTO evo_task_events(task_id,owner_uid,event,created_at) VALUES(?,?,?,?)',(int(tid),uid(owner),'UPDATED',t))
    return task_get(owner,tid)

def workflows(owner):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM evo_workflows WHERE owner_uid=? ORDER BY updated_at DESC',(uid(owner),)).fetchall()]
    for r in rows:
        try:r['steps']=json.loads(r.pop('steps_json'))
        except Exception:r['steps']=[]
    if not rows:
        rows=[{'id':0,'name':'Criar site','status':'TEMPLATE','steps':['IDEIA','PLANEJAMENTO','ESTRUTURA','DESIGN','CÓDIGO','PREVIEW','SECURITY CHECK','PUBLICAÇÃO']}, {'id':0,'name':'Análise de projeto','status':'TEMPLATE','steps':['RECEBER','ANALISAR','TESTAR','SECURITY CHECK','RELATÓRIO']}]
    return rows

def workflow_create(owner,name,steps):
    name=str(name or '').strip()[:120]
    clean=[str(x)[:100] for x in (steps if isinstance(steps,list) else [])][:30]
    if not name or not clean: raise ValueError('Workflow inválido.')
    t=now()
    with conn() as c:cur=c.execute('INSERT INTO evo_workflows(owner_uid,name,status,steps_json,created_at,updated_at) VALUES(?,?,?,?,?,?)',(uid(owner),name,'DRAFT',json.dumps(clean,ensure_ascii=False),t,t))
    return {'id':cur.lastrowid,'name':name,'status':'DRAFT','steps':clean,'created_at':t,'updated_at':t}

def snapshots(owner, project_key=''):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT id,project_key,label,created_at,manifest_json FROM evo_snapshots WHERE owner_uid=? ORDER BY id DESC LIMIT 100',(uid(owner),)).fetchall()]
    for r in rows:
        try:r['manifest']=json.loads(r.pop('manifest_json'))
        except Exception:r['manifest']={}
    return [r for r in rows if not project_key or r['project_key']==str(project_key)[:160]]

def snapshot_create(owner,project_key,label,manifest=None):
    project_key=str(project_key or 'project')[:160];label=str(label or 'Snapshot')[:160]
    safe_manifest=manifest if isinstance(manifest,dict) else {}
    # Only metadata is persisted; secrets and file contents are deliberately excluded.
    safe_manifest={k:v for k,v in safe_manifest.items() if k in {'files','version','status','note'}}
    t=now()
    with conn() as c:cur=c.execute('INSERT INTO evo_snapshots(owner_uid,project_key,label,manifest_json,created_at) VALUES(?,?,?,?,?)',(uid(owner),project_key,label,json.dumps(safe_manifest,ensure_ascii=False),t))
    return {'id':cur.lastrowid,'project_key':project_key,'label':label,'manifest':safe_manifest,'created_at':t}

def agents():
    return [{'id':'general','name':'JARVIS GENERAL','purpose':'Orquestra tarefas gerais.'},{'id':'code','name':'CODE AGENT','purpose':'Análise, explicação e revisão de código fornecido.'},{'id':'security','name':'SECURITY AGENT','purpose':'Revisão defensiva e Security Center.'},{'id':'web','name':'WEB AGENT','purpose':'Sites, HTML, CSS, acessibilidade e SEO.'},{'id':'game','name':'GAME AGENT','purpose':'Projetos e jogos locais.'},{'id':'study','name':'STUDY AGENT','purpose':'Ensino, exercícios e revisão.'},{'id':'project','name':'PROJECT AGENT','purpose':'Planejamento e organização de projetos.'}]

def route_agent(text):
    q=str(text or '').lower()
    rules=[('security',['segurança','security','vulnerab','csrf','xss','scan']),('code',['código','codigo','python','javascript','bug','erro']),('game',['jogo','game','arcade']),('study',['estude','estudo','explique','aprender','python']),('web',['site','html','css','seo']),('project',['projeto','project','arquivo'])]
    for agent,words in rules:
        if any(w in q for w in words):return next(x for x in agents() if x['id']==agent)
    return agents()[0]

def ai_mode(owner, mode=None):
    allowed={'NORMAL','DEEP ANALYSIS','CODING','SECURITY','STUDY','CREATIVE','PROJECT'}
    if mode:
        mode=str(mode).upper()[:30]
        if mode not in allowed: raise ValueError('Modo inválido.')
        with conn() as c:c.execute('INSERT OR REPLACE INTO evo_ai_modes(owner_uid,mode,updated_at) VALUES(?,?,?)',(uid(owner),mode,now()))
    with conn() as c:r=c.execute('SELECT mode,updated_at FROM evo_ai_modes WHERE owner_uid=?',(uid(owner),)).fetchone()
    return {'mode':r['mode'] if r else 'NORMAL','updated_at':r['updated_at'] if r else None,'allowed':sorted(allowed)}

def study_catalog():
    return [{'id':'python','name':'Python','levels':['BEGINNER','INTERMEDIATE','ADVANCED'],'modules':['sintaxe','funções','estruturas','projetos']},{'id':'web','name':'Web Development','levels':['BEGINNER','INTERMEDIATE'],'modules':['HTML','CSS','JavaScript','APIs']},{'id':'cyber','name':'Cybersecurity','levels':['BEGINNER','INTERMEDIATE','ADVANCED'],'modules':['Authentication','Web Security','SOC','Incident Response']},{'id':'math','name':'Matemática','levels':['BEGINNER','INTERMEDIATE'],'modules':['frações','geometria','problemas']}]

def search(owner,q,limit=50):
    q=' '.join(str(q or '').lower().split())[:120]
    if not q:return []
    out=[]
    for x in tasks(owner):
        if q in (x['title']+' '+x['description']).lower():out.append({'type':'task','title':x['title'],'detail':x['status'],'id':x['id']})
    for x in platform_ultra.arcade_catalog(owner):
        if q in (x['name']+' '+x['description']).lower():out.append({'type':'game','title':x['name'],'detail':x['category'],'id':x['id']})
    for x in mega_expansion.project_center(owner):
        s=json.dumps(x,ensure_ascii=False).lower()
        if q in s:out.append({'type':'project','title':str(x.get('name') or x.get('id') or 'Projeto'),'detail':'project','id':x.get('id')})
    return out[:max(1,min(int(limit),100))]

def status(owner):
    diag=platform_ultra.diagnostics(); ws=core2.webauthn_service.status() if hasattr(core2,'webauthn_service') else {}
    try: services=mega_expansion.service_status()
    except Exception: services=[]
    return {'AI':'ONLINE' if any(os.getenv(k) for k in ('OPENROUTER_API_KEY','GEMINI_API_KEY','ANTHROPIC_API_KEY')) else 'UNKNOWN','DATABASE':diag['database']['status'],'AUTH':'READY' if auth.has_master_password() else 'NOT READY','WEBAUTHN':'ENABLED' if ws.get('enabled') else 'UNKNOWN','STORAGE':'READY','TOOLS':'READY','ARCADE':'READY','MAPS':'READY','HOLOGRAM':'READY','services':services,'generated_at':now()}

def performance():
    rows=telemetry.recent(100)
    return {'events_sampled':len(rows),'ok':sum(1 for x in rows if x.get('ok')),'errors':sum(1 for x in rows if x.get('ok') is False),'note':'Amostra do telemetry existente; métricas de memória/CPU só aparecem quando fornecidas pelo runtime.'}

def database_health():
    try:
        with conn() as c:
            c.execute('SELECT 1').fetchone(); tables=c.execute("SELECT count(*) n FROM sqlite_master WHERE type='table'").fetchone()['n']
        return {'status':'HEALTHY','connection':'OK','tables':tables,'migrations':'NOT TRACKED HERE','backups':platform_ultra.backup_safety(),'errors':[]}
    except Exception as e:return {'status':'ERROR','connection':'ERROR','tables':None,'errors':['database check failed']}

def integrity():
    files=[BASE/'app.py',BASE/'routes_cyber.py',BASE/'services'/'auth.py',BASE/'services'/'permissions.py']
    return [{'file':str(p.relative_to(BASE)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'status':'PRESENT' if p.exists() else 'MISSING'} for p in files]

def dependency_status():
    req=BASE/'requirements.txt'; lines=[]
    for line in req.read_text(encoding='utf-8').splitlines() if req.exists() else []:
        s=line.strip()
        if s and not s.startswith('#'):lines.append(s)
    return {'declared':lines,'audit':'NOT EXECUTED','note':'Use pip-audit in the deployment environment for current advisories.'}

def security_report():
    sec=core2.security_overview(); counts=sec['counts']
    return {'title':'JARVIS SECURITY REPORT','generated_at':now(),'results':counts,'controls':sec['controls'],'recommendations':[x['control'] for x in sec['controls'] if x['status'] in ('FAIL','WARNING','NOT TESTED')]}
