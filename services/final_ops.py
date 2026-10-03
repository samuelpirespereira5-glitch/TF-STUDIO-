"""Final integrated operations layer for JARVIS Cyber Lab.
Reuses phase5, telemetry, existing auth/permissions and the existing SQLite DB.
No offensive execution; all actions are local/authorized and bounded.
"""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from services import phase5

BASE=Path(__file__).resolve().parent.parent
DB=BASE/'data'/'cyberlab.db'

def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]

def conn():
    c=phase5.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS f_cases(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,title TEXT NOT NULL,description TEXT DEFAULT '',severity TEXT NOT NULL,status TEXT NOT NULL,assignee TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,closed_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_case_links(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER NOT NULL,kind TEXT NOT NULL,ref_id TEXT NOT NULL,owner_uid TEXT NOT NULL,UNIQUE(case_id,kind,ref_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_detections(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,name TEXT NOT NULL,severity TEXT NOT NULL,enabled INTEGER DEFAULT 1,tags TEXT DEFAULT '[]',conditions TEXT DEFAULT '{}',cooldown_seconds INTEGER DEFAULT 300,false_positive INTEGER DEFAULT 0,mitre TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,rule_id INTEGER,title TEXT NOT NULL,severity TEXT NOT NULL,status TEXT NOT NULL,confidence TEXT DEFAULT 'unknown',event_count INTEGER DEFAULT 0,first_seen TEXT,last_seen TEXT,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_jobs(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,progress INTEGER DEFAULT 0,message TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,result TEXT DEFAULT '{}',error TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',priority TEXT DEFAULT 'normal',source TEXT DEFAULT '',read_at TEXT,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_assets_meta(owner_uid TEXT NOT NULL,asset_id TEXT NOT NULL,environment TEXT DEFAULT 'lab',hostname TEXT DEFAULT '',url TEXT DEFAULT '',authorized_ip TEXT DEFAULT '',owner_name TEXT DEFAULT '',criticality TEXT DEFAULT 'medium',tags TEXT DEFAULT '[]',technology TEXT DEFAULT '',status TEXT DEFAULT 'active',updated_at TEXT NOT NULL,PRIMARY KEY(owner_uid,asset_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS f_backups(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,label TEXT NOT NULL,path TEXT DEFAULT '',size INTEGER DEFAULT 0,sha256 TEXT DEFAULT '',verified INTEGER DEFAULT 0,created_at TEXT NOT NULL)''')
    return c

def _audit(owner,action,target='',details=''):
    phase5.audit(owner,action,target,details)

def cases(owner):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM f_cases WHERE owner_uid=? ORDER BY id DESC',(uid(owner),)).fetchall()]
    return rows

def create_case(owner,title,description='',severity='medium',assignee=''):
    if severity not in phase5.SEVERITIES: raise ValueError('Severidade inválida')
    if not title: raise ValueError('Título obrigatório')
    t=now()
    with conn() as c:
        cur=c.execute('INSERT INTO f_cases(owner_uid,title,description,severity,status,assignee,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(uid(owner),title[:180],description[:4000],severity,'new',assignee[:120],t,t)); cid=cur.lastrowid
    _audit(owner,'case.create',str(cid),title[:180]); notify(owner,'Novo caso criado',title,'high','case'); return case(owner,cid)

def case(owner,cid):
    with conn() as c:
        r=c.execute('SELECT * FROM f_cases WHERE id=? AND owner_uid=?',(int(cid),uid(owner))).fetchone()
        links=[dict(x) for x in c.execute('SELECT kind,ref_id FROM f_case_links WHERE case_id=? AND owner_uid=?',(int(cid),uid(owner))).fetchall()]
    if not r:return None
    d=dict(r); d['links']=links; return d

def update_case(owner,cid,**kw):
    allowed={'description','severity','status','assignee'}; vals=[]; sets=[]
    if kw.get('status') and kw['status'] not in phase5.STATUSES: raise ValueError('Status inválido')
    if kw.get('severity') and kw['severity'] not in phase5.SEVERITIES: raise ValueError('Severidade inválida')
    for k in allowed:
        if k in kw and kw[k] is not None: sets.append(k+'=?'); vals.append(str(kw[k])[:4000])
    if not sets:return case(owner,cid)
    sets.append('updated_at=?'); vals.append(now()); vals += [int(cid),uid(owner)]
    with conn() as c:c.execute('UPDATE f_cases SET '+','.join(sets)+' WHERE id=? AND owner_uid=?',vals)
    _audit(owner,'case.update',str(cid),json.dumps(kw,ensure_ascii=False)); return case(owner,cid)

def link_case(owner,cid,kind,ref_id):
    if kind not in {'incident','alert','asset','vulnerability','ioc','evidence','scan'}: raise ValueError('Tipo de relação inválido')
    with conn() as c:c.execute('INSERT OR IGNORE INTO f_case_links(case_id,kind,ref_id,owner_uid) VALUES(?,?,?,?)',(int(cid),kind,str(ref_id)[:160],uid(owner)))
    _audit(owner,'case.link',str(cid),f'{kind}:{ref_id}'); return case(owner,cid)

def detections(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM f_detections WHERE owner_uid=? ORDER BY id DESC',(uid(owner),)).fetchall()]

def create_detection(owner,name,severity='medium',conditions=None,tags=None,mitre=''):
    if severity not in phase5.SEVERITIES: raise ValueError('Severidade inválida')
    t=now()
    with conn() as c:
        cur=c.execute('INSERT INTO f_detections(owner_uid,name,severity,tags,conditions,mitre,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(uid(owner),name[:180],severity,json.dumps(tags or []),json.dumps(conditions or {}),mitre[:80],t,t)); did=cur.lastrowid
    _audit(owner,'detection.create',str(did),name[:180]); return detections(owner)

def set_detection(owner,did,enabled=None,suppress=False):
    sets=[];vals=[]
    if enabled is not None:sets.append('enabled=?');vals.append(1 if enabled else 0)
    if suppress:sets.append('cooldown_seconds=?');vals.append(86400)
    sets.append('updated_at=?');vals.append(now());vals += [int(did),uid(owner)]
    with conn() as c:c.execute('UPDATE f_detections SET '+','.join(sets)+' WHERE id=? AND owner_uid=?',vals)
    _audit(owner,'detection.update',str(did),json.dumps({'enabled':enabled,'suppress':suppress})); return detections(owner)

def correlate(owner,window_minutes=15):
    ev=phase5.events(owner); cutoff=time.time()-max(1,min(int(window_minutes),120))*60
    # ISO timestamps are compared via parsed epoch where possible.
    recent=[]
    for e in ev:
        try:
            dt=datetime.fromisoformat((e.get('ts') or '').replace('Z','+00:00')).timestamp()
            if dt>=cutoff: recent.append(e)
        except Exception: continue
    rules=detections(owner); alerts=[]
    for r in rules:
        if not r['enabled']:continue
        cond=json.loads(r['conditions'] or '{}')
        typ=cond.get('type','failed_access')
        matches=[e for e in recent if (typ=='failed_access' and e.get('type')=='access' and int(e.get('status') or 0) in (401,403)) or (typ=='tool_error' and e.get('type')=='tool' and e.get('severity')!='info')]
        threshold=max(1,int(cond.get('threshold',3)))
        if len(matches)>=threshold:
            alerts.append({'rule_id':r['id'],'title':r['name'],'severity':r['severity'],'confidence':'medium','event_count':len(matches),'first_seen':matches[-1].get('ts'),'last_seen':matches[0].get('ts')})
            with conn() as c:c.execute('INSERT INTO f_alerts(owner_uid,rule_id,title,severity,status,confidence,event_count,first_seen,last_seen,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid(owner),r['id'],r['name'],r['severity'],'new','medium',len(matches),matches[-1].get('ts'),matches[0].get('ts'),now()))
            notify(owner,'Alerta de detecção',f"{r['name']} · {len(matches)} eventos",'high','detection')
    return alerts

def alerts(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM f_alerts WHERE owner_uid=? ORDER BY id DESC LIMIT 200',(uid(owner),)).fetchall()]

def notify(owner,title,body='',priority='normal',source='system'):
    with conn() as c:c.execute('INSERT INTO f_notifications(owner_uid,title,body,priority,source,created_at) VALUES(?,?,?,?,?,?)',(uid(owner),title[:180],body[:1000],priority[:20],source[:60],now()))

def notifications(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM f_notifications WHERE owner_uid=? ORDER BY id DESC LIMIT 100',(uid(owner),)).fetchall()]

def posture(owner):
    checks=[]
    s=phase5.settings(owner)
    checks.append(('MFA', 'OK' if s.get('mfa_required') else 'WARNING','MFA obrigatório no perfil de segurança.'))
    checks.append(('Allowlist', 'OK' if s.get('allowlist_required') else 'CRITICAL','Alvos ativos devem exigir allowlist.'))
    checks.append(('Audit chain','OK' if phase5.verify_audit()['valid'] else 'CRITICAL','Integridade da cadeia de auditoria.'))
    checks.append(('Rate limit','OK' if s.get('rate_limit_profile') else 'NOT CONFIGURED','Perfil de rate limit configurado.'))
    checks.append(('Session timeout','OK' if int(s.get('session_timeout_minutes',0))>0 else 'CRITICAL','Timeout de sessão.'))
    checks.append(('Tool policy','OK' if s.get('tool_policy')=='authorized-only' else 'WARNING','Política de ferramentas.'))
    return [{'control':a,'status':b,'evidence':c,'impact':'Revisar configuração' if b!='OK' else 'Controle presente','remediation':'Ajustar nas Security Settings' if b!='OK' else 'Nenhuma'} for a,b,c in checks]

def health():
    t=time.time(); ok=True; db_ms=None; err=''
    try:
        st=time.perf_counter();
        with conn() as c:c.execute('SELECT 1').fetchone()
        db_ms=round((time.perf_counter()-st)*1000,2)
    except Exception as e:ok=False;err=str(e)[:160]
    return {'status':'ok' if ok else 'degraded','database':{'ok':ok,'latency_ms':db_ms},'timestamp':now(),'error':err}

def api_governance():
    return {'note':'Endpoint governance is generated from the registered Flask route map at runtime; backend authorization remains authoritative.','checks':['auth','capability','csrf-for-state-changing','rate-limit','logging']}

def rbac():
    from services.permissions import CAPS,ROLES
    return [{'role':r,'capabilities':sorted(CAPS.get(r,set()))} for r in ROLES]

def config_security():
    keys=['SECRET_KEY','MASTER_PASSWORD_HASH','FLASK_DEBUG','SESSION_COOKIE_SECURE','SESSION_COOKIE_HTTPONLY','SESSION_COOKIE_SAMESITE','MAX_CONTENT_LENGTH']
    out=[]
    for k in keys:
        v=os.getenv(k)
        out.append({'name':k,'configured':bool(v),'value':'[REDACTED]' if v else None})
    return out

def audit_filtered(owner,q='',action='',limit=200):
    with conn() as c:
        rows=[dict(r) for r in c.execute('SELECT id,action,target,details,ts,entry_hash FROM p5_audit WHERE owner_uid=? ORDER BY id DESC LIMIT 500',(uid(owner),)).fetchall()]
    if q:rows=[r for r in rows if q.lower() in json.dumps(r,ensure_ascii=False).lower()]
    if action:rows=[r for r in rows if r['action']==action]
    return rows[:max(1,min(int(limit),500))]

def jobs(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM f_jobs WHERE owner_uid=? ORDER BY created_at DESC LIMIT 100',(uid(owner),)).fetchall()]

def create_job(owner,kind):
    import uuid
    jid=uuid.uuid4().hex;t=now()
    with conn() as c:c.execute('INSERT INTO f_jobs(id,owner_uid,kind,status,created_at,updated_at) VALUES(?,?,?,?,?,?)',(jid,uid(owner),kind[:80],'queued',t,t))
    _audit(owner,'job.create',jid,kind);return jid

def update_job(owner,jid,status=None,progress=None,message=None,result=None,error=None):
    sets=[];vals=[]
    for k,v in [('status',status),('progress',progress),('message',message),('result',json.dumps(result) if result is not None else None),('error',error)]:
        if v is not None:sets.append(k+'=?');vals.append(v)
    sets.append('updated_at=?');vals.append(now());vals += [jid,uid(owner)]
    with conn() as c:c.execute('UPDATE f_jobs SET '+','.join(sets)+' WHERE id=? AND owner_uid=?',vals)
    return next((x for x in jobs(owner) if x['id']==jid),None)

def compare_scans(owner,a,b):
    from services import evidence
    sa=next((x for x in evidence.history(limit=500) if str(x.get('id'))==str(a)),None); sb=next((x for x in evidence.history(limit=500) if str(x.get('id'))==str(b)),None)
    if not sa or not sb:return {'error':'Scan não encontrado'}
    def keys(s):return {str(f.get('id') or f.get('title')):f for f in s.get('findings',[])}
    ka,kb=keys(sa),keys(sb)
    return {'before':a,'after':b,'new':sorted(set(kb)-set(ka)),'resolved':sorted(set(ka)-set(kb)),'unchanged':sorted(set(ka)&set(kb))}

def executive_report(owner):
    d=phase5.dashboard(owner); p=posture(owner); inc=phase5.soc(owner)['incidents']; al=alerts(owner); vs=phase5.vulnerabilities(owner)
    return {'generated_at':now(),'summary':{'security_score':d['security_score'],'risk':d['risk'],'incidents':len(inc),'alerts':len(al),'open_vulnerabilities':sum(v['status'] not in ('resolved','false_positive') for v in vs)},'posture':p,'recommendations':[x['remediation'] for x in p if x['status']!='OK']}
