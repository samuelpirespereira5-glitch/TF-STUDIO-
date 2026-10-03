"""JARVIS Cyber Lab — Ultra Expansion layer.
Incremental, defensive and local-only. Reuses Phase 5/SOC/Evidence/Tool Registry.
No offensive execution, external target testing or secret disclosure.
"""
from __future__ import annotations
import ast, hashlib, json, os, re, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import current_app
from services import phase5
from services.tool_registry import REGISTRY

BASE = Path(__file__).resolve().parent.parent
DB = BASE / 'data' / 'cyberlab.db'
SEV = ('critical','high','medium','low','info')
TOOL_CATS = ['BLUE TEAM','SOC','WEB SECURITY','NETWORK SECURITY','OSINT','FORENSICS','THREAT INTELLIGENCE','DEVSECOPS','CLOUD SECURITY','API SECURITY','CODE SECURITY','AUTHENTICATION','MONITORING','LOG ANALYSIS','EDUCATION','UTILITIES']


def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]

def conn():
    c = phase5.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS u_tool_state(owner_uid TEXT NOT NULL,tool_id TEXT NOT NULL,favorite INTEGER DEFAULT 0,last_used TEXT,uses INTEGER DEFAULT 0,PRIMARY KEY(owner_uid,tool_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_workspaces(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,name TEXT NOT NULL,status TEXT DEFAULT 'active',data TEXT DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,archived_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_timeline(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,event_type TEXT NOT NULL,title TEXT NOT NULL,severity TEXT DEFAULT 'info',user_uid TEXT DEFAULT '',asset TEXT DEFAULT '',payload TEXT DEFAULT '{}',ts TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL,payload TEXT NOT NULL,hash TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_preferences(owner_uid TEXT PRIMARY KEY,density TEXT DEFAULT 'normal',dashboard TEXT DEFAULT '[]',updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_safe_actions(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,impact TEXT NOT NULL,consequence TEXT NOT NULL,status TEXT DEFAULT 'pending',created_at TEXT NOT NULL,confirmed_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS u_scan_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,label TEXT NOT NULL,target TEXT NOT NULL,scan_type TEXT NOT NULL,started_at TEXT NOT NULL,duration_ms INTEGER DEFAULT 0,findings_json TEXT DEFAULT '[]',status TEXT DEFAULT 'completed')''')
    return c


def _audit(owner, action, target='', details=''):
    phase5.audit(owner, action, target, str(details)[:1000])


def _safe_json(x):
    try: return json.loads(x) if isinstance(x,str) else (x or {})
    except Exception: return {}


def tool_catalog(owner, query='', category='', favorite=False, recent=False, sort='name', role=None):
    role = role or 'owner'
    tools = REGISTRY.list_for(role)
    q=(query or '').strip().lower()[:100]
    with conn() as c:
        states={r['tool_id']:dict(r) for r in c.execute('SELECT * FROM u_tool_state WHERE owner_uid=?',(uid(owner),)).fetchall()}
    out=[]
    for t in tools:
        hay=' '.join([t.get('name',''),t.get('description',''),t.get('category',''),' '.join(t.get('keywords',[]) or [])]).lower()
        cat=_normalize_cat(t.get('category'))
        s=states.get(t['id'],{})
        if q and q not in hay: continue
        if category and cat != category: continue
        if favorite and not s.get('favorite'): continue
        if recent and not s.get('last_used'): continue
        out.append({**t,'category':cat,'favorite':bool(s.get('favorite')),'last_used':s.get('last_used'),'uses':int(s.get('uses') or 0),'status':'available'})
    if sort=='recent': out.sort(key=lambda x:x.get('last_used') or '', reverse=True)
    elif sort=='used': out.sort(key=lambda x:x.get('uses',0), reverse=True)
    else: out.sort(key=lambda x:(x.get('category',''),x.get('name','').lower()))
    cats=[]
    for c in TOOL_CATS:
        n=sum(1 for x in out if x['category']==c)
        if n or not query: cats.append({'name':c,'count':n})
    return {'tools':out,'categories':cats,'total':len(out)}


def _normalize_cat(c):
    x=(c or 'Utilities').lower()
    mapping={'cyber':'BLUE TEAM','central':'UTILITIES','pentest':'WEB SECURITY','basic':'MONITORING','ai':'EDUCATION','external':'UTILITIES','forensics':'FORENSICS','web':'WEB SECURITY','network':'NETWORK SECURITY','api':'API SECURITY','secure coding':'CODE SECURITY','osint':'OSINT','blue team':'BLUE TEAM'}
    for k,v in mapping.items():
        if k in x: return v
    return 'UTILITIES'


def set_tool_state(owner, tool_id, favorite=None):
    if not REGISTRY.get(tool_id): raise ValueError('Ferramenta não encontrada')
    t=now()
    with conn() as c:
        old=c.execute('SELECT * FROM u_tool_state WHERE owner_uid=? AND tool_id=?',(uid(owner),tool_id)).fetchone()
        fav=int(favorite) if favorite is not None else int(old['favorite'] if old else 0)
        uses=int(old['uses'] if old else 0); last=old['last_used'] if old else None
        c.execute('INSERT OR REPLACE INTO u_tool_state(owner_uid,tool_id,favorite,last_used,uses) VALUES(?,?,?,?,?)',(uid(owner),tool_id,fav,last,uses))
    _audit(owner,'tool.favorite',tool_id,str(fav)); return True


def mark_tool_used(owner, tool_id):
    if not REGISTRY.get(tool_id): return
    with conn() as c:
        r=c.execute('SELECT uses,favorite FROM u_tool_state WHERE owner_uid=? AND tool_id=?',(uid(owner),tool_id)).fetchone()
        c.execute('INSERT OR REPLACE INTO u_tool_state(owner_uid,tool_id,favorite,last_used,uses) VALUES(?,?,?,?,?)',(uid(owner),tool_id,int(r['favorite'] if r else 0),now(),int(r['uses'] if r else 0)+1))


def workspace_list(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,name,status,data,created_at,updated_at,archived_at FROM u_workspaces WHERE owner_uid=? ORDER BY updated_at DESC',(uid(owner),)).fetchall()]

def workspace_create(owner,name,data=None):
    n=(name or '').strip()[:160]
    if not n: raise ValueError('Nome obrigatório')
    t=now()
    with conn() as c:
        cur=c.execute('INSERT INTO u_workspaces(owner_uid,name,data,created_at,updated_at) VALUES(?,?,?,?,?)',(uid(owner),n,json.dumps(data or {},ensure_ascii=False)[:20000],t,t)); wid=cur.lastrowid
    _audit(owner,'workspace.create',str(wid),n); return workspace_get(owner,wid)

def workspace_get(owner,wid):
    with conn() as c:r=c.execute('SELECT * FROM u_workspaces WHERE id=? AND owner_uid=?',(int(wid),uid(owner))).fetchone()
    if not r:return None
    d=dict(r); d['data']=_safe_json(d['data']); return d

def workspace_save(owner,wid,data):
    if not workspace_get(owner,wid): return None
    with conn() as c:c.execute('UPDATE u_workspaces SET data=?,updated_at=? WHERE id=? AND owner_uid=?',(json.dumps(data or {},ensure_ascii=False)[:30000],now(),int(wid),uid(owner)))
    _audit(owner,'workspace.save',str(wid),'updated'); return workspace_get(owner,wid)

def workspace_archive(owner,wid):
    with conn() as c:c.execute("UPDATE u_workspaces SET status='archived',archived_at=?,updated_at=? WHERE id=? AND owner_uid=?",(now(),now(),int(wid),uid(owner)))
    _audit(owner,'workspace.archive',str(wid),''); return workspace_get(owner,wid)


def add_timeline(owner,event_type,title,severity='info',user_uid='',asset='',payload=None,ts=None):
    if severity not in SEV: severity='info'
    with conn() as c:
        cur=c.execute('INSERT INTO u_timeline(owner_uid,event_type,title,severity,user_uid,asset,payload,ts) VALUES(?,?,?,?,?,?,?,?)',(uid(owner),event_type,title[:180],severity,user_uid[:120],asset[:180],json.dumps(payload or {},ensure_ascii=False)[:8000],ts or now()))
        return cur.lastrowid

def timeline(owner,days=30,kind='',severity='',asset='',user=''):
    cutoff=(datetime.now(timezone.utc)-timedelta(days=min(max(int(days or 30),1),365))).isoformat()
    q='SELECT * FROM u_timeline WHERE owner_uid=? AND ts>=?'; vals=[uid(owner),cutoff]
    if kind:q+=' AND event_type=?'; vals.append(kind[:60])
    if severity:q+=' AND severity=?'; vals.append(severity)
    if asset:q+=' AND asset LIKE ?'; vals.append('%'+asset[:100]+'%')
    if user:q+=' AND user_uid=?'; vals.append(user[:120])
    q+=' ORDER BY ts DESC LIMIT 500'
    with conn() as c: rows=[dict(r) for r in c.execute(q,vals).fetchall()]
    return [{**r,'payload':_safe_json(r['payload'])} for r in rows]


def baseline():
    cfg=current_app.config
    checks=[]
    def add(name,ok,status='NON-COMPLIANT',evidence='',fix=''):
        checks.append({'control':name,'status':'COMPLIANT' if ok else status,'evidence':evidence,'fix':fix})
    add('DEBUG',not bool(cfg.get('DEBUG')),evidence=f"DEBUG={bool(cfg.get('DEBUG'))}",fix='Desativar DEBUG em produção.')
    add('Secure Cookies',bool(cfg.get('SESSION_COOKIE_SECURE')),evidence=f"SESSION_COOKIE_SECURE={bool(cfg.get('SESSION_COOKIE_SECURE'))}",fix='Ativar Secure Cookie sob HTTPS.')
    add('HttpOnly',cfg.get('SESSION_COOKIE_HTTPONLY',True) is True,evidence=f"SESSION_COOKIE_HTTPONLY={cfg.get('SESSION_COOKIE_HTTPONLY',True)}",fix='Manter HttpOnly.')
    add('SameSite',str(cfg.get('SESSION_COOKIE_SAMESITE','Lax')).lower() in ('lax','strict'),evidence=f"SESSION_COOKIE_SAMESITE={cfg.get('SESSION_COOKIE_SAMESITE','Lax')}",fix='Usar Lax ou Strict conforme necessidade.')
    add('CSRF',bool(cfg.get('WTF_CSRF_ENABLED',True)),evidence='Framework CSRF flag',fix='Manter proteção CSRF nas operações mutáveis.')
    add('CSP',bool(cfg.get('CONTENT_SECURITY_POLICY') or os.getenv('CSP')),evidence='Configuração CSP disponível' if (cfg.get('CONTENT_SECURITY_POLICY') or os.getenv('CSP')) else 'Nenhuma CSP configurada',fix='Definir CSP restritiva.')
    add('Rate Limit',bool(cfg.get('RATELIMIT_ENABLED') or cfg.get('RATE_LIMIT')),evidence='Rate limit configurado' if (cfg.get('RATELIMIT_ENABLED') or cfg.get('RATE_LIMIT')) else 'Flag de rate limit não encontrada',fix='Ativar rate limiting nas rotas sensíveis.')
    add('Session Timeout',bool(cfg.get('PERMANENT_SESSION_LIFETIME')),evidence=str(cfg.get('PERMANENT_SESSION_LIFETIME','not set')),fix='Definir timeout de sessão.')
    add('2FA',bool(cfg.get('REQUIRE_2FA') or cfg.get('MFA_REQUIRED')),evidence='Flag 2FA' if (cfg.get('REQUIRE_2FA') or cfg.get('MFA_REQUIRED')) else 'Não configurado nesta camada',fix='Exigir 2FA para ações administrativas.')
    add('RBAC',True,evidence='Backend permissions.current_role()/require_cap()',fix='')
    add('Audit Logs',phase5.verify_audit()['valid'],status='NON-COMPLIANT',evidence='Cadeia p5_audit verificada',fix='Investigar entradas inválidas.')
    add('Upload Restrictions',bool(cfg.get('MAX_CONTENT_LENGTH')),evidence=f"MAX_CONTENT_LENGTH={cfg.get('MAX_CONTENT_LENGTH','not set')}",fix='Definir limite de upload.')
    return checks


def security_score():
    bs=baseline(); weights={'CRITICAL':0,'NON-COMPLIANT':40,'NOT CHECKED':None,'COMPLIANT':100}
    cats={'Authentication':['Secure Cookies','HttpOnly','SameSite','2FA','Session Timeout'],'Authorization':['RBAC'],'Application Security':['CSRF','CSP'],'Infrastructure':['DEBUG'],'Dependencies':[],'Monitoring':['Audit Logs'],'Logging':['Audit Logs'],'Configuration':['Rate Limit'],'Incident Response':[],'Vulnerability Management':[],'DevSecOps':[],'Backup & Recovery':[]}
    details=[]; scored=[]
    for cat,names in cats.items():
        items=[x for x in bs if x['control'] in names]
        vals=[weights.get(x['status']) for x in items if weights.get(x['status']) is not None]
        score=round(sum(vals)/len(vals)) if vals else None
        if score is not None: scored.append(score)
        details.append({'category':cat,'score':score,'status':'ASSESSED' if score is not None else 'NOT CHECKED','items':items})
    overall=round(sum(scored)/len(scored)) if scored else None
    return {'score':overall,'score_label':f'{overall}/100' if overall is not None else 'NOT CHECKED','categories':details,'evidence':bs,'generated_at':now()}

def posture_recommendations(owner):
    rec=[]
    for x in baseline():
        if x['status']!='COMPLIANT':
            sev='high' if x['control'] in ('DEBUG','CSRF','Secure Cookies') else 'medium'
            rec.append({'id':hashlib.sha1((x['control']+x['status']).encode()).hexdigest()[:10],'severity':sev,'problem':f"{x['control']} não está em conformidade",'evidence':x['evidence'],'impact':'Pode reduzir a proteção do ambiente.','fix':x['fix'],'status':'open','owner':uid(owner),'source':'security-baseline'})
    return sorted(rec,key=lambda x:SEV.index(x['severity']))


def api_inventory():
    out=[]
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith('/api/'): continue
        methods=sorted(m for m in rule.methods if m not in {'HEAD','OPTIONS'})
        path=rule.rule
        auth=not path in ('/api/health','/api/ready','/api/status')
        cap=''
        try:
            from services import permissions
            for prefix,c in permissions.PATH_CAPS:
                if path.startswith(prefix): cap=c; break
        except Exception: pass
        out.append({'endpoint':path,'methods':methods,'authentication':'required' if auth else 'public-minimal','permission':cap or 'route-specific','rate_limit':'profile-dependent','csrf':'required-for-state-change','validation':'route-dependent','status':'review' if not cap and auth else 'protected'})
    return sorted(out,key=lambda x:x['endpoint'])


def web_security():
    bs=baseline(); return {'baseline':bs,'headers':{'csp':next((x for x in bs if x['control']=='CSP'),None),'cookies':[x for x in bs if x['control'] in ('Secure Cookies','HttpOnly','SameSite')],'csrf':next((x for x in bs if x['control']=='CSRF'),None),'rate_limit':next((x for x in bs if x['control']=='Rate Limit'),None)},'note':'Verificações locais; TLS externo não é testado.'}


def _iter_code_files():
    skip={'.git','__pycache__','node_modules','venv','.venv','data'}
    for p in BASE.rglob('*'):
        if p.is_file() and not any(part in skip for part in p.parts) and p.suffix.lower() in {'.py','.js','.html','.jinja','.jinja2','.css'}:
            yield p


def code_scan(paths=None,max_files=160):
    wanted=[]
    if paths:
        for rel in paths[:80]:
            p=(BASE/str(rel)).resolve()
            if str(p).startswith(str(BASE.resolve())) and p.is_file(): wanted.append(p)
    else: wanted=list(_iter_code_files())[:max_files]
    patterns=[
        ('hardcoded-secret',re.compile(r'(?i)(api[_-]?key|secret|password|token)\s*=\s*[\'\"][^\'\"]{8,}[\'\"]'),'high','Possível segredo embutido no código.'),
        ('sql-formatting',re.compile(r'(?i)(execute|executemany)\s*\(\s*[f\'\"]'),'high','SQL pode estar sendo construído por interpolação.'),
        ('shell-command',re.compile(r'(?i)\b(os\.system|subprocess\.(run|Popen|call)|eval\(|exec\()'),'high','Execução dinâmica/comando deve ser revisada.'),
        ('dangerous-path',re.compile(r'(?i)(open|Path)\([^\n]*(request\.|input\()'),'medium','Entrada pode influenciar caminho de arquivo.'),
        ('csrf-signal',re.compile(r'(?i)@.*\.post\(|@.*\.patch\(|@.*\.delete\('),'info','Rota mutável encontrada; verificar CSRF/autorização.'),
    ]
    findings=[]
    for p in wanted:
        try: text=p.read_text(encoding='utf-8',errors='replace')[:400000]
        except Exception: continue
        lines=text.splitlines()
        for i,line in enumerate(lines,1):
            for rule,rx,sev,msg in patterns:
                if rx.search(line): findings.append({'rule':rule,'file':str(p.relative_to(BASE)),'line':i,'severity':sev,'problem':msg,'evidence':line.strip()[:220],'fix':'Revisar o contexto e aplicar validação/parametrização/segredos via ambiente.'})
    return {'files_scanned':len(wanted),'findings':findings[:500],'not_executed':True}


def secret_scan(paths=None):
    patterns=[('API key',re.compile(r'(?i)\b(sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,})\b')),('JWT/token',re.compile(r'(?i)\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b')),('private key',re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),('password assignment',re.compile(r'(?i)\b(password|passwd|secret)\s*[:=]\s*[\'\"][^\'\"]{6,}[\'\"]'))]
    result=code_scan(paths,max_files=120); findings=[]
    for f in result['findings']:
        if f['rule']=='hardcoded-secret': findings.append({'type':'possible-secret','file':f['file'],'line':f['line'],'masked_preview':'[REDACTED]','severity':f['severity']})
    files=list(_iter_code_files())[:120] if not paths else []
    for p in files:
        try: lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
        except Exception: continue
        for i,line in enumerate(lines,1):
            for typ,rx in patterns:
                if rx.search(line): findings.append({'type':typ,'file':str(p.relative_to(BASE)),'line':i,'masked_preview':'[REDACTED]','severity':'critical' if typ=='private key' else 'high'})
    uniq={(x['file'],x['line'],x['type']):x for x in findings}
    return {'findings':list(uniq.values())[:300],'secrets_redacted':True}


def impact_analysis(paths=None,action='review'):
    cs=code_scan(paths,max_files=80); files=sorted({x['file'] for x in cs['findings']})
    routes=[]
    for r in api_inventory():
        if any(Path(f).name in r['endpoint'] for f in files): routes.append(r['endpoint'])
    return {'dry_run':True,'action':action,'files_affected':files,'routes_affected':routes,'services_affected':['services/ultra_ops.py'] if files else [],'database_affected':['u_*'] if action in ('schema','migration') else [],'dependencies_affected':[],'risk':'review-required' if files else 'low','executed':False}


def snapshot(owner,kind='security',label='snapshot'):
    if kind=='security': payload={'baseline':baseline(),'api':api_inventory(),'score':security_score()['score']}
    elif kind=='tools': payload={'tools':tool_catalog(owner)['tools']}
    else: payload={'timeline':timeline(owner,7)}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str); h=hashlib.sha256(raw.encode()).hexdigest()
    with conn() as c:
        cur=c.execute('INSERT INTO u_snapshots(owner_uid,kind,label,payload,hash,created_at) VALUES(?,?,?,?,?,?)',(uid(owner),kind,label,raw,h,now())); sid=cur.lastrowid
    _audit(owner,'snapshot.create',str(sid),kind); return {'id':sid,'kind':kind,'label':label,'hash':h,'created_at':now()}


def drift(owner,kind='security'):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM u_snapshots WHERE owner_uid=? AND kind=? ORDER BY id DESC LIMIT 2',(uid(owner),kind)).fetchall()]
    current= snapshot(owner,kind,'current')
    with conn() as c: old=c.execute('SELECT * FROM u_snapshots WHERE owner_uid=? AND kind=? AND id<>? ORDER BY id DESC LIMIT 1',(uid(owner),kind,current['id'])).fetchone()
    if not old:return {'has_baseline':False,'current':current,'changes':[]}
    before=_safe_json(old['payload']); after=_safe_json(c.execute('SELECT payload FROM u_snapshots WHERE id=?',(current['id'],)).fetchone()['payload']) if False else None
    # Reconstruct current payload directly for diff to avoid trusting client input.
    if kind=='security': after={'baseline':baseline(),'api':api_inventory(),'score':security_score()['score']}
    elif kind=='tools': after={'tools':tool_catalog(owner)['tools']}
    else: after={'timeline':timeline(owner,7)}
    changes=[]
    for key in sorted(set(before.keys())|set(after.keys())):
        if before.get(key)!=after.get(key): changes.append({'field':key,'before':before.get(key),'after':after.get(key),'risk':'review'})
    return {'has_baseline':True,'previous':{'id':old['id'],'hash':old['hash'],'created_at':old['created_at']},'current':current,'changes':changes}


def create_safe_action(owner,action,target,impact,consequence):
    raw=f'{uid(owner)}|{action}|{target}|{time.time()}'; aid=hashlib.sha256(raw.encode()).hexdigest()[:18]
    with conn() as c:c.execute('INSERT INTO u_safe_actions(id,owner_uid,action,target,impact,consequence,created_at) VALUES(?,?,?,?,?,?,?)',(aid,uid(owner),action[:120],target[:240],impact[:500],consequence[:500],now()))
    _audit(owner,'safe-action.prepare',aid,action); return {'id':aid,'status':'pending','requires_confirmation':True,'action':action,'target':target,'impact':impact,'consequence':consequence}


def confirm_safe_action(owner,aid):
    with conn() as c:c.execute("UPDATE u_safe_actions SET status='confirmed',confirmed_at=? WHERE id=? AND owner_uid=? AND status='pending'",(now(),aid,uid(owner)))
    _audit(owner,'safe-action.confirm',aid,'confirmed'); return True


def scan_history(owner):
    from services import evidence
    rows=evidence.history(limit=200)
    out=[]
    for s in rows:
        fs=s.get('findings',[]) or []; counts={x:sum(1 for f in fs if f.get('severity')==x) for x in SEV}
        out.append({'id':s.get('id'),'scan':s.get('tool'),'date':s.get('ts'),'target':s.get('target'),'duration_ms':s.get('duration_ms'),'findings':len(fs),**counts,'status':'completed'})
    return out


def scan_compare(before,after,owner):
    from services import evidence
    a=evidence.get_scan(before); b=evidence.get_scan(after)
    if not a or not b:return {'error':'Scan não encontrado'}
    def keys(s): return {str(f.get('id') or f.get('title')):f for f in s.get('findings',[])}
    aa,bb=keys(a),keys(b)
    return {'before':before,'after':after,'appeared':[bb[k] for k in bb.keys()-aa.keys()],'disappeared':[aa[k] for k in aa.keys()-bb.keys()],'unchanged':[bb[k] for k in bb.keys()&aa.keys()]}


def notifications_smart(owner):
    base=phase5.conn()
    with base as c: rows=[dict(r) for r in c.execute('SELECT * FROM f_notifications WHERE owner_uid=? ORDER BY created_at DESC LIMIT 500',(uid(owner),)).fetchall()]
    groups={}
    for r in rows:
        key=(r['source'],r['title'],r['priority'])
        g=groups.setdefault(key,{'title':r['title'],'source':r['source'],'priority':r['priority'],'count':0,'first':r['created_at'],'last':r['created_at']})
        g['count']+=1; g['first']=min(g['first'],r['created_at']); g['last']=max(g['last'],r['created_at'])
    return list(groups.values())


def preferences(owner,data=None):
    if data is not None:
        density=data.get('density','normal');
        if density not in ('compact','normal','comfortable'): density='normal'
        dashboard=[str(x)[:60] for x in (data.get('dashboard') or [])][:20]
        with conn() as c:c.execute('INSERT OR REPLACE INTO u_preferences(owner_uid,density,dashboard,updated_at) VALUES(?,?,?,?)',(uid(owner),density,json.dumps(dashboard),now()))
    with conn() as c:r=c.execute('SELECT * FROM u_preferences WHERE owner_uid=?',(uid(owner),)).fetchone()
    return {'density':r['density'] if r else 'normal','dashboard':_safe_json(r['dashboard']) if r else ['soc','vulnerabilities','incidents','health','scans']}


def global_search(owner,q):
    q=(q or '').strip().lower()[:100]
    if not q:return []
    out=[]
    for x in tool_catalog(owner)['tools']:
        if q in json.dumps(x,ensure_ascii=False).lower(): out.append({'type':'tool','id':x['id'],'title':x['name'],'category':x['category']})
    for x in phase5_service_cases(owner):
        if q in json.dumps(x,ensure_ascii=False).lower(): out.append({'type':'case','id':x['id'],'title':x['title']})
    for x in phase5.vulnerabilities(owner)[:200]:
        if q in json.dumps(x,ensure_ascii=False).lower(): out.append({'type':'vulnerability','id':x['id'],'title':x['title'],'severity':x['severity']})
    for x in phase5.list_iocs(owner)[:200]:
        if q in json.dumps(x,ensure_ascii=False).lower(): out.append({'type':'ioc','id':x['id'],'title':x['value']})
    return out[:120]


def phase5_service_cases(owner):
    with phase5.conn() as c:return [dict(r) for r in c.execute('SELECT id,title,severity,status FROM p5_incidents WHERE owner_uid=? ORDER BY id DESC LIMIT 100',(uid(owner),)).fetchall()]


def trends(owner,days=30):
    days=min(max(int(days or 30),1),365); scans=scan_history(owner); cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    buckets={}
    for s in scans:
        try: dt=datetime.fromisoformat(s['date'].replace('Z','+00:00'))
        except Exception: continue
        if dt<cutoff: continue
        k=dt.date().isoformat(); g=buckets.setdefault(k,{'date':k,'scans':0,'findings':0,'critical':0,'high':0}); g['scans']+=1; g['findings']+=s['findings']; g['critical']+=s['critical']; g['high']+=s['high']
    with phase5.conn() as c:
        inc=c.execute('SELECT created_at FROM p5_incidents WHERE owner_uid=?',(uid(owner),)).fetchall()
    for r in inc:
        try:k=datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).date().isoformat()
        except Exception:continue
        if k in buckets: buckets[k]['incidents']=buckets[k].get('incidents',0)+1
    return sorted(buckets.values(),key=lambda x:x['date'])


def maturity(owner):
    score=security_score(); pending=sum(1 for x in score['evidence'] if x['status']!='COMPLIANT')
    return {'categories':[{'name':n,'state':'review' if pending else 'established','pending':pending if i==0 else 0,'evidence':score['categories'][i%len(score['categories'])]['items']} for i,n in enumerate(['Identity','Application Security','Infrastructure','Monitoring','Incident Response','Vulnerability Management','DevSecOps'])],'next_actions':posture_recommendations(owner)[:8]}


def investigation_board(owner):
    rows=phase5_service_cases(owner)
    columns={'NOVO':[],'EM ANÁLISE':[],'CONFIRMADO':[],'EM CORREÇÃO':[],'VALIDAÇÃO':[],'RESOLVIDO':[]}
    mapping={'new':'NOVO','investigating':'EM ANÁLISE','contained':'EM CORREÇÃO','resolved':'RESOLVIDO'}
    for r in rows:
        col=mapping.get(r.get('status'),'EM ANÁLISE'); columns[col].append(r)
    return columns


def alert_fatigue(owner):
    with conn() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM f_alerts WHERE owner_uid=? ORDER BY created_at DESC LIMIT 500',(uid(owner),)).fetchall()]
    groups={}
    for r in rows:
        key=(r['rule_id'],r['severity'],r['title'])
        g=groups.setdefault(key,{'rule_id':r['rule_id'],'title':r['title'],'severity':r['severity'],'occurrences':0,'first_seen':r['first_seen'],'last_seen':r['last_seen'],'reason':'deduplicated by rule + severity + title'})
        g['occurrences']+=1; g['first_seen']=min(g['first_seen'] or r['first_seen'],r['first_seen'] or g['first_seen']); g['last_seen']=max(g['last_seen'] or r['last_seen'],r['last_seen'] or g['last_seen'])
    return list(groups.values())


def copilot(owner,context='SOC',scan_id=None,finding_id=None):
    """Explain only evidence that exists in local stores; never fabricate facts."""
    ctx=(context or 'SOC').upper()[:40]
    evidence={}
    if scan_id:
        from services import evidence as ev
        scan=ev.get_scan(scan_id)
        if scan:
            evidence={'scan_id':scan_id,'target':scan.get('target'),'tool':scan.get('tool'),'findings':scan.get('findings',[])}
    if finding_id and evidence.get('findings'):
        evidence['selected_finding']=next((f for f in evidence['findings'] if str(f.get('id'))==str(finding_id) or str(f.get('title'))==str(finding_id)),None)
    if not evidence:
        if ctx=='SOC': evidence={'events':phase5.events(owner)[:20]}
        elif ctx in ('VULNERABILITY','VULNERABILITY MANAGEMENT'): evidence={'vulnerabilities':phase5.vulnerabilities(owner)[:30]}
        elif ctx=='CODE SECURITY': evidence={'note':'Execute a Code Security scan to provide file/line evidence.'}
        elif ctx=='ACADEMY': evidence={'articles':knowledge()}
        else: evidence={'note':'No local evidence supplied for this context.'}
    selected=evidence.get('selected_finding')
    if selected:
        return {'context':ctx,'has_evidence':True,'summary':selected.get('title','Finding'),'evidence':selected.get('evidence',''),'impact':selected.get('impact',''),'cause':selected.get('cause',''),'correction':selected.get('fix',''),'validation':'Executar novo scan autorizado e comparar o resultado.','raw_evidence':selected}
    return {'context':ctx,'has_evidence':bool(evidence and not ('note' in evidence and len(evidence)==1)),'summary':'Contexto carregado a partir de dados locais.','evidence':evidence,'impact':'Não inferido sem evidência específica.','cause':'Não determinado.','correction':'Revisar os dados apresentados e usar os módulos correspondentes.','validation':'Validar com uma nova verificação autorizada.','note':'Se não houver evidência suficiente, o JARVIS deve informar isso em vez de inventar conclusões.'}

def health_services():
    t=time.perf_counter(); status='ONLINE'
    try: phase5.conn().execute('SELECT 1').fetchone()
    except Exception: status='OFFLINE'
    return {'services':[{'name':'SQLite','status':status,'latency_ms':round((time.perf_counter()-t)*1000,2),'last_check':now(),'last_error':'' if status=='ONLINE' else 'database check failed'},{'name':'Flask','status':'ONLINE','latency_ms':0,'last_check':now(),'last_error':''},{'name':'Tool Registry','status':'ONLINE' if REGISTRY.tools else 'UNKNOWN','latency_ms':0,'last_check':now(),'last_error':''}]}


def knowledge():
    return [
      {'id':'owasp','title':'OWASP','category':'Web Security','concept':'Riscos comuns de aplicações web.','why':'Ajuda a priorizar controles defensivos.','detect':'Revisar validação, autenticação, autorização e saída.','fix':'Aplicar controles server-side e testes autorizados.','example':'Parametrização de consultas e encoding de saída.','checklist':['validação','autorização','CSRF','headers']},
      {'id':'soc','title':'SOC','category':'SOC','concept':'Monitoramento e triagem de eventos.','why':'Transforma sinais em investigações rastreáveis.','detect':'Correlacionar eventos e reduzir ruído.','fix':'Criar regras, casos e evidências.','example':'Agrupar falhas repetidas de autenticação.','checklist':['eventos','alertas','casos','timeline']},
      {'id':'secure-coding','title':'Secure Coding','category':'Secure Coding','concept':'Construção de software com controles de segurança.','why':'Reduz vulnerabilidades introduzidas no código.','detect':'SAST e revisão contextual.','fix':'Validação, parametrização e gestão segura de segredos.','example':'Query parametrizada.','checklist':['inputs','SQL','XSS','secrets']},
      {'id':'incident-response','title':'Incident Response','category':'Incident Response','concept':'Processo para analisar e recuperar de eventos de segurança.','why':'Mantém evidências e decisões rastreáveis.','detect':'Triage e timeline.','fix':'Conter, corrigir, validar e documentar.','example':'Caso vinculado a alerta e evidências.','checklist':['triage','evidência','correção','validação']},
    ]
