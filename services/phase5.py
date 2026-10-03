"""JARVIS Cyber Lab — Mega Expansion / Operations Layer.
Reuses existing Evidence Center, Phase 2 assets, Phase 4 CTF and telemetry.
All active analysis is local/authorized and resource-bounded.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent.parent
DB=BASE_DIR/'data'/'cyberlab.db'
_lock=threading.Lock()
SEVERITIES=('critical','high','medium','low','info')
STATUSES=('new','investigating','contained','resolved')
CATEGORIES=['Web Security','API Security','Authentication','Sessions','Cryptography','Networking','Linux Fundamentals','Forensics','Logs','Secure Coding','OSINT','Cloud Security','Blue Team','Incident Response']

ACADEMY=[
 {'id':'fundamentos','title':'Fundamentos','lessons':['CIA Triad','Threat Modeling','Authentication vs Authorization','Security Logging'],'skills':['fundamentals']},
 {'id':'web-security','title':'Web Security','lessons':['XSS','CSRF','IDOR','SSRF','Path Traversal','Security Headers'],'skills':['web']},
 {'id':'network-security','title':'Network Security','lessons':['DNS','TLS','Services','Segmentation'],'skills':['network']},
 {'id':'blue-team','title':'Blue Team','lessons':['Logs','IOC','Detection Rules','Baselines'],'skills':['blue-team']},
 {'id':'forensics','title':'Forensics','lessons':['Hashes','Metadata','Timeline','Evidence Handling'],'skills':['forensics']},
 {'id':'api-security','title':'API Security','lessons':['Schemas','JWT','CORS','Rate Limiting','Authorization'],'skills':['api']},
 {'id':'secure-coding','title':'Secure Coding','lessons':['Input Validation','Secrets','SAST','Dependencies'],'skills':['secure-code']},
 {'id':'incident-response','title':'Incident Response','lessons':['Triage','Containment','Eradication','Recovery','Lessons Learned'],'skills':['ir']},
]

LABS=[
 {'id':'api-auth','category':'API Security','title':'API Auth Lab','stages':['identify authentication boundary','inspect simulated response','propose secure control']},
 {'id':'api-access','category':'API Security','title':'API Authorization Lab','stages':['map resources','identify access-control evidence','write remediation']},
 {'id':'web-xss','category':'Web Security','title':'XSS Lab','stages':['inspect simulated input/output','identify unsafe sink','propose encoding/CSP']},
 {'id':'web-sqli','category':'Web Security','title':'SQL Injection Lab','stages':['inspect query construction','identify untrusted interpolation','propose parameterization']},
 {'id':'web-csrf','category':'Web Security','title':'CSRF Lab','stages':['inspect state-changing request','identify missing anti-CSRF control','propose defense']},
 {'id':'web-idor','category':'Web Security','title':'IDOR Lab','stages':['inspect object reference','identify authorization gap','propose server-side check']},
 {'id':'web-ssrf','category':'Web Security','title':'SSRF Lab','stages':['inspect simulated fetch','identify trust boundary','propose allowlist/network egress control']},
 {'id':'web-upload','category':'Web Security','title':'Secure Upload Lab','stages':['inspect upload policy','identify unsafe file handling','propose isolation and validation']},
]

def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]

def conn():
 DB.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS p5_incidents(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,title TEXT NOT NULL,severity TEXT NOT NULL,status TEXT NOT NULL,summary TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,closed_at TEXT)''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_vulns(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,finding_key TEXT NOT NULL,title TEXT NOT NULL,severity TEXT NOT NULL,priority TEXT NOT NULL,status TEXT NOT NULL,evidence TEXT DEFAULT '',cause TEXT DEFAULT '',impact TEXT DEFAULT '',fix TEXT DEFAULT '',owner TEXT DEFAULT '',sla_hours INTEGER DEFAULT 168,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,retest_scan INTEGER, UNIQUE(owner_uid,finding_key))''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_ioc(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,kind TEXT NOT NULL,value TEXT NOT NULL,tag TEXT DEFAULT '',source TEXT DEFAULT '',confidence TEXT DEFAULT 'unknown',simulated INTEGER DEFAULT 0,created_at TEXT NOT NULL, UNIQUE(owner_uid,kind,value))''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_progress(owner_uid TEXT PRIMARY KEY,xp INTEGER DEFAULT 0,lessons TEXT DEFAULT '[]',labs TEXT DEFAULT '[]',streak INTEGER DEFAULT 0,last_day TEXT)''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_settings(owner_uid TEXT PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,action TEXT NOT NULL,target TEXT DEFAULT '',details TEXT DEFAULT '',ts TEXT NOT NULL,prev_hash TEXT DEFAULT '',entry_hash TEXT NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS p5_workflows(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL,result TEXT DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
 return c

def audit(uid_,action,target='',details=''):
 details=str(details)[:1000]; ts=now()
 with _lock,conn() as c:
  prev=c.execute('SELECT entry_hash FROM p5_audit ORDER BY id DESC LIMIT 1').fetchone(); ph=prev['entry_hash'] if prev else ''
  payload=f'{uid(uid_)}|{action}|{target}|{details}|{ts}|{ph}'
  eh=hashlib.sha256(payload.encode()).hexdigest()
  c.execute('INSERT INTO p5_audit(owner_uid,action,target,details,ts,prev_hash,entry_hash) VALUES(?,?,?,?,?,?,?)',(uid(uid_),action,target,details,ts,ph,eh))

def verify_audit():
 with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM p5_audit ORDER BY id').fetchall()]
 prev=''; bad=[]
 for r in rows:
  payload=f"{r['owner_uid']}|{r['action']}|{r['target']}|{r['details']}|{r['ts']}|{r['prev_hash']}"
  expected=hashlib.sha256(payload.encode()).hexdigest()
  if r['prev_hash']!=prev or r['entry_hash']!=expected: bad.append(r['id'])
  prev=r['entry_hash']
 return {'valid':not bad,'entries':len(rows),'invalid_ids':bad}

def events(owner):
 from services import access_log, telemetry, evidence
 out=[]
 for x in access_log.recent(80): out.append({'type':'access','ts':x.get('ts'),'severity':'high' if int(x.get('status',0)) in (401,403) else 'info','title':f"{x.get('method')} {x.get('path')}",'status':x.get('status'),'source':'access_log'})
 for x in telemetry.recent(80): out.append({'type':'tool','ts':x.get('ts'),'severity':'medium' if not x.get('ok') else 'info','title':f"Tool: {x.get('tool')}",'target':x.get('target'),'source':'telemetry'})
 for x in evidence.history(limit=40):
  sev=max((f.get('severity','info') for f in x.get('findings',[])), key=lambda s:SEVERITIES.index(s) if s in SEVERITIES else 4, default='info')
  out.append({'type':'scan','ts':x.get('ts'),'severity':sev,'title':f"Scan: {x.get('tool')}",'target':x.get('target'),'scan_id':x.get('id'),'source':'evidence'})
 out.sort(key=lambda x:x.get('ts') or '',reverse=True); return out[:200]

def soc(owner,query='',severity='',status=''):
 ev=events(owner); q=query.lower().strip()
 if q: ev=[e for e in ev if q in json.dumps(e,ensure_ascii=False).lower()]
 if severity: ev=[e for e in ev if e.get('severity')==severity]
 with conn() as c: inc=[dict(r) for r in c.execute('SELECT * FROM p5_incidents WHERE owner_uid=? ORDER BY id DESC LIMIT 100',(uid(owner),)).fetchall()]
 if status: inc=[x for x in inc if x['status']==status]
 counts={s:sum(1 for e in ev if e.get('severity')==s) for s in SEVERITIES}
 return {'events':ev,'incidents':inc,'counts':counts,'generated_at':now()}

def create_incident(owner,title,severity='medium',summary=''):
 if severity not in SEVERITIES: raise ValueError('Severidade inválida')
 t=(title or '').strip()[:180]
 if not t: raise ValueError('Título obrigatório')
 with _lock,conn() as c:
  cur=c.execute('INSERT INTO p5_incidents(owner_uid,title,severity,status,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(uid(owner),t,severity,'new',(summary or '')[:2000],now(),now())); iid=cur.lastrowid
 audit(owner,'incident.create',str(iid),t); return get_incident(owner,iid)

def get_incident(owner,iid):
 with conn() as c:
  r=c.execute('SELECT * FROM p5_incidents WHERE id=? AND owner_uid=?',(int(iid),uid(owner))).fetchone(); return dict(r) if r else None

def update_incident(owner,iid,status=None,severity=None,summary=None):
 if status and status not in STATUSES: raise ValueError('Status inválido')
 if severity and severity not in SEVERITIES: raise ValueError('Severidade inválida')
 row=get_incident(owner,iid)
 if not row: return None
 fields=[]; vals=[]
 for k,v in [('status',status),('severity',severity),('summary',summary)]:
  if v is not None: fields.append(k+'=?'); vals.append(str(v)[:2000])
 if not fields: return row
 fields.append('updated_at=?'); vals.append(now()); vals += [int(iid),uid(owner)]
 with _lock,conn() as c: c.execute('UPDATE p5_incidents SET '+','.join(fields)+' WHERE id=? AND owner_uid=?',vals)
 audit(owner,'incident.update',str(iid),json.dumps({'status':status,'severity':severity},ensure_ascii=False)); return get_incident(owner,iid)

def vulnerabilities(owner):
 from services import evidence
 scans=evidence.history(limit=300)
 with _lock,conn() as c:
  for s in scans:
   for f in s.get('findings',[]):
    sev=f.get('severity','info'); key=f"{s['id']}:{f.get('id','unknown')}"
    c.execute('''INSERT OR IGNORE INTO p5_vulns(owner_uid,finding_key,title,severity,priority,status,evidence,cause,impact,fix,owner,sla_hours,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(uid(owner),key,f.get('title','Finding'),sev,sev,'open',f.get('evidence',''),f.get('cause',''),f.get('impact',''),f.get('fix',''),'','168',s.get('ts',now()),now()))
  rows=[dict(r) for r in c.execute('SELECT * FROM p5_vulns WHERE owner_uid=? ORDER BY CASE severity WHEN "critical" THEN 0 WHEN "high" THEN 1 WHEN "medium" THEN 2 WHEN "low" THEN 3 ELSE 4 END,id DESC',(uid(owner),)).fetchall()]
 return rows

def update_vuln(owner,iid,status=None,priority=None,owner_name=None,retest_scan=None):
 allowed={'open','investigating','in_progress','resolved','accepted','false_positive'}
 if status and status not in allowed: raise ValueError('Status inválido')
 sets=[]; vals=[]
 for k,v in [('status',status),('priority',priority),('owner',owner_name),('retest_scan',retest_scan)]:
  if v is not None: sets.append(k+'=?'); vals.append(v)
 sets.append('updated_at=?'); vals.append(now()); vals += [int(iid),uid(owner)]
 with _lock,conn() as c: c.execute('UPDATE p5_vulns SET '+','.join(sets)+' WHERE id=? AND owner_uid=?',vals)
 audit(owner,'vulnerability.update',str(iid),json.dumps({'status':status,'priority':priority},ensure_ascii=False))
 return vulnerabilities(owner)

def assets(owner):
 from services import cyber_phase2
 rows=cyber_phase2.list_assets(owner)
 out=[]
 for a in rows:
  target=a.get('target',''); out.append({**a,'domain':target,'ip':'','service':'','application':a.get('name',''),'api':'','certificate':'','technology':'','version':'','status':'active','last_analysis':a.get('updated_at'),'risks':[]})
 return out

def add_ioc(owner,kind,value,tag='',source='',confidence='unknown',simulated=False):
 if kind not in {'ip','domain','url','hash','file','event'}: raise ValueError('Tipo de IOC inválido')
 v=(value or '').strip()[:500]
 if not v: raise ValueError('Indicador obrigatório')
 with _lock,conn() as c:
  c.execute('INSERT OR IGNORE INTO p5_ioc(owner_uid,kind,value,tag,source,confidence,simulated,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid(owner),kind,v,(tag or '')[:80],(source or '')[:180],(confidence or 'unknown')[:30],1 if simulated else 0,now()))
 audit(owner,'ioc.add',kind,v); return list_iocs(owner)

def list_iocs(owner):
 with conn() as c: return [dict(r) for r in c.execute('SELECT * FROM p5_ioc WHERE owner_uid=? ORDER BY id DESC',(uid(owner),)).fetchall()]

def progress(owner):
 with conn() as c:
  r=c.execute('SELECT * FROM p5_progress WHERE owner_uid=?',(uid(owner),)).fetchone()
 if not r: return {'xp':0,'level':1,'lessons':[],'labs':[],'streak':0,'badges':[]}
 xp=int(r['xp']); lessons=json.loads(r['lessons']); labs=json.loads(r['labs']);
 badges=[]
 if len(lessons)>=3: badges.append('Academy Starter')
 if len(labs)>=3: badges.append('Lab Operator')
 if xp>=1000: badges.append('Security Learner')
 return {'xp':xp,'level':1+xp//300,'lessons':lessons,'labs':labs,'streak':r['streak'],'badges':badges}

def award(owner,xp=0,lesson=None,lab=None):
 p=progress(owner); lessons=p['lessons']; labs=p['labs'];
 if lesson and lesson not in lessons: lessons.append(lesson)
 if lab and lab not in labs: labs.append(lab)
 day=datetime.now(timezone.utc).date().isoformat()
 with _lock,conn() as c:
  old=c.execute('SELECT last_day FROM p5_progress WHERE owner_uid=?',(uid(owner),)).fetchone(); streak=1
  if old and old['last_day']:
   if old['last_day']==day: streak=0
   elif old['last_day']==(datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat(): streak=p['streak']+1
  total=p['xp']+int(xp)
  c.execute('INSERT INTO p5_progress(owner_uid,xp,lessons,labs,streak,last_day) VALUES(?,?,?,?,?,?) ON CONFLICT(owner_uid) DO UPDATE SET xp=excluded.xp,lessons=excluded.lessons,labs=excluded.labs,streak=excluded.streak,last_day=excluded.last_day',(uid(owner),total,json.dumps(lessons),json.dumps(labs),max(1,streak),day))
 audit(owner,'progress.award',lesson or lab or 'xp',str(xp)); return progress(owner)

def settings(owner):
 defaults={'mfa_required':False,'session_timeout_minutes':60,'rate_limit_profile':'standard','password_policy':'strong','log_retention_days':90,'notifications':True,'tool_policy':'authorized-only','allowlist_required':True}
 with conn() as c: r=c.execute('SELECT data FROM p5_settings WHERE owner_uid=?',(uid(owner),)).fetchone()
 if r: defaults.update(json.loads(r['data']))
 return defaults

def update_settings(owner,data):
 current=settings(owner); critical={'mfa_required','session_timeout_minutes','rate_limit_profile','password_policy','allowlist_required'}
 if any(k in critical and data.get(k)!=current.get(k) for k in data): return {'ok':False,'requires_reauth':True,'settings':current}
 current.update({k:v for k,v in data.items() if k in current});
 with _lock,conn() as c: c.execute('INSERT INTO p5_settings(owner_uid,data,updated_at) VALUES(?,?,?) ON CONFLICT(owner_uid) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(uid(owner),json.dumps(current),now()))
 audit(owner,'settings.update','security',json.dumps(data,ensure_ascii=False)); return {'ok':True,'settings':current}

def dashboard(owner):
 s=soc(owner); vs=vulnerabilities(owner); p=progress(owner); assets_=assets(owner); audit_state=verify_audit()
 counts={sev:sum(1 for v in vs if v['severity']==sev and v['status'] not in ('resolved','false_positive')) for sev in SEVERITIES}
 risk=min(100,counts['critical']*30+counts['high']*20+counts['medium']*10+counts['low']*4)
 return {'security_score':max(0,100-risk),'risk':risk,'events':len(s['events']),'incidents':len(s['incidents']),'vulnerabilities':counts,'assets':len(assets_),'sessions':0,'progress':p,'audit_chain':audit_state,'generated_at':now()}

def report(owner):
 d=dashboard(owner); vs=vulnerabilities(owner); lines=[f'# JARVIS SOC Report\n\nData: {d["generated_at"]}','\n## Executive Summary',f'Security Score: {d["security_score"]}/100',f'Eventos: {d["events"]}',f'Incidentes: {d["incidents"]}',f'Ativos: {d["assets"]}','\n## Vulnerabilidades']
 for v in vs[:100]: lines.append(f"- **{v['severity'].upper()}** {v['title']} · status={v['status']} · evidência: {v['evidence']} · correção: {v['fix']}")
 lines.append('\n## Integridade do Audit Log'); lines.append(json.dumps(d['audit_chain'],ensure_ascii=False))
 return '\n'.join(lines)
