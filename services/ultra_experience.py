"""JARVIS Ultra Platform experience layer.
Incremental, local/educational systems only. No arbitrary server-side code execution.
"""
from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from services import platform_ultra, mega_expansion, game_lab, evolution2

BASE=Path(__file__).resolve().parent.parent

def now(): return datetime.now(timezone.utc).isoformat()
def clean(v,n=240): return str(v or '').strip()[:n]
def conn():
    c=platform_ultra.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS ux_progress(owner_uid TEXT PRIMARY KEY, onboarding_done INTEGER DEFAULT 0, interests_json TEXT DEFAULT '[]', updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ux_skills(owner_uid TEXT NOT NULL, skill_id TEXT NOT NULL, unlocked INTEGER DEFAULT 0, progress INTEGER DEFAULT 0, updated_at TEXT NOT NULL, PRIMARY KEY(owner_uid,skill_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS ux_projects(id TEXT PRIMARY KEY, owner_uid TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, difficulty TEXT NOT NULL, objective TEXT DEFAULT '', technology TEXT DEFAULT '', visual TEXT DEFAULT '', stage TEXT NOT NULL, data_json TEXT DEFAULT '{}', public INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ux_ideas(id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL, title TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ux_activity(id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL, event TEXT NOT NULL, detail TEXT DEFAULT '', created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ux_daily(owner_uid TEXT NOT NULL, challenge_key TEXT NOT NULL, completed INTEGER DEFAULT 0, updated_at TEXT NOT NULL, PRIMARY KEY(owner_uid,challenge_key))''')
    return c

def uid(owner): return clean(owner or 'anon',120) or 'anon'

SKILLS={
 'variables':('VARIABLES',None,'PROGRAMMING'),'conditions':('CONDITIONS','variables','PROGRAMMING'),'loops':('LOOPS','conditions','PROGRAMMING'),'functions':('FUNCTIONS','loops','PROGRAMMING'),'game_logic':('GAME LOGIC','functions','GAMES'),
 'html':('HTML','variables','WEB'),'css':('CSS','html','WEB'),'javascript':('JAVASCRIPT','html','WEB'),'apis':('APIs','javascript','WEB'),
 'ai_patterns':('AI PATTERNS','variables','AI'),'chatbots':('CHATBOTS','ai_patterns','AI'),'security_basics':('SECURITY BASICS','conditions','CYBERSECURITY'),'defense':('DEFENSIVE SECURITY','security_basics','CYBERSECURITY'),
 'design':('DESIGN','variables','DESIGN'),'animation':('ANIMATION','design','DESIGN'),'logic':('LOGIC','conditions','LOGIC')}

def _log(owner,event,detail=''):
    with conn() as c:c.execute('INSERT INTO ux_activity(owner_uid,event,detail,created_at) VALUES(?,?,?,?)',(uid(owner),clean(event,80),clean(detail,400),now()))

def overview(owner):
    owner=uid(owner); c=conn()
    with c:
        p=c.execute('SELECT * FROM ux_progress WHERE owner_uid=?',(owner,)).fetchone()
        if not p:
            t=now();c.execute('INSERT INTO ux_progress(owner_uid,updated_at) VALUES(?,?)',(owner,t));p=c.execute('SELECT * FROM ux_progress WHERE owner_uid=?',(owner,)).fetchone()
        projects=[dict(r) for r in c.execute('SELECT id,name,kind,difficulty,objective,technology,visual,stage,public,created_at,updated_at FROM ux_projects WHERE owner_uid=? ORDER BY updated_at DESC LIMIT 100',(owner,)).fetchall()]
        acts=[dict(r) for r in c.execute('SELECT event,detail,created_at FROM ux_activity WHERE owner_uid=? ORDER BY id DESC LIMIT 30',(owner,)).fetchall()]
        skills=[dict(r) for r in c.execute('SELECT skill_id,unlocked,progress FROM ux_skills WHERE owner_uid=?',(owner,)).fetchall()]
    done=sum(1 for x in skills if x['unlocked']); total=len(SKILLS); learned=sum(1 for x in skills if x['progress']>=100)
    return {'learning':{'level':min(6,1+learned//3),'completed_skills':learned,'unlocked_skills':done,'total_skills':total,'progress':round((learned/total)*100) if total else 0},'projects':projects,'activities':acts,'skills':skills,'onboarding':bool(p['onboarding_done']),'challenge':daily(owner)}

def set_onboarding(owner, interests):
    interests=[clean(x,40) for x in (interests if isinstance(interests,list) else [])[:8]]
    with conn() as c:c.execute('INSERT OR REPLACE INTO ux_progress(owner_uid,onboarding_done,interests_json,updated_at) VALUES(?,?,?,?)',(uid(owner),1,json.dumps(interests),now()))
    _log(owner,'ONBOARDING_COMPLETE',','.join(interests));return overview(owner)['learning']

def skills(owner):
    owner=uid(owner); nowv=now();
    with conn() as c:
        for sid,(name,parent,cat) in SKILLS.items():
            r=c.execute('SELECT * FROM ux_skills WHERE owner_uid=? AND skill_id=?',(owner,sid)).fetchone()
            if not r:c.execute('INSERT INTO ux_skills(owner_uid,skill_id,unlocked,progress,updated_at) VALUES(?,?,?,?,?)',(owner,sid,0,0,nowv))
        rows=[dict(r) for r in c.execute('SELECT skill_id,unlocked,progress FROM ux_skills WHERE owner_uid=?',(owner,)).fetchall()]
    m={r['skill_id']:r for r in rows}
    # First nodes are unlocked; children unlock only after parent reaches 70%.
    for sid,(name,parent,cat) in SKILLS.items():
        if not parent or m.get(parent,{}).get('progress',0)>=70:m[sid]['unlocked']=1
    return [{'id':sid,'name':v[0],'parent':v[1],'category':v[2],**m[sid]} for sid,v in SKILLS.items()]

def skill_update(owner,sid,progress):
    if sid not in SKILLS: raise ValueError('Habilidade inexistente.')
    p=max(0,min(100,int(progress or 0))); unlocked=1 if p>=0 else 0
    with conn() as c:c.execute('INSERT OR REPLACE INTO ux_skills(owner_uid,skill_id,unlocked,progress,updated_at) VALUES(?,?,?,?,?)',(uid(owner),sid,unlocked,p,now()))
    _log(owner,'SKILL_PROGRESS',f'{sid}:{p}');return skills(owner)

def ideas(owner,prompt=''):
    q=clean(prompt,240).lower()
    bank=[('Space Explorer','game','Jogo com exploração espacial e coleta de recursos.'),('Maze Robot','game','Programe um robô para atravessar um labirinto.'),('Interactive Portfolio','web','Site pessoal com projetos, tecnologias e aprendizados.'),('API Explorer','web','Visualizador educativo de request, response e JSON.'),('Mini Chatbot','ai','Bot de regras com personalidade configurável.'),('Sorting Visualizer','programming','Animações para comparar algoritmos de ordenação.'),('Digital Circuit','logic','Monte portas AND, OR, NOT e XOR em um circuito.'),('Science Sandbox','experiment','Simule gravidade, movimento, luz e energia.'),('Cyber Defense Scenario','security','Investigue um cenário fictício de eventos e proteção.'),('Story Adventure','creative','História interativa com escolhas e consequências.')]
    if q:
        keys=q.split(); bank=[x for x in bank if any(k in (' '.join(x)).lower() for k in keys)] or bank
    out=[]
    for title,kind,desc in bank[:8]:
        with conn() as c:r=c.execute('SELECT id FROM ux_ideas WHERE owner_uid=? AND title=?',(uid(owner),title)).fetchone()
        if r:out.append({'id':r['id'],'title':title,'kind':kind,'description':desc})
        else:
            with conn() as c:cur=c.execute('INSERT INTO ux_ideas(owner_uid,title,kind,description,created_at) VALUES(?,?,?,?,?)',(uid(owner),title,kind,desc,now()));out.append({'id':cur.lastrowid,'title':title,'kind':kind,'description':desc})
    return out

def create_project(owner,d):
    name=clean(d.get('name') or 'Novo Projeto',100); kind=clean(d.get('kind') or 'programming',40); diff=clean(d.get('difficulty') or 'BEGINNER',30); objective=clean(d.get('objective'),300);tech=clean(d.get('technology'),100);visual=clean(d.get('visual'),100)
    pid='ux-'+uuid.uuid4().hex[:12];t=now(); data={'files':initial_files(kind),'modules':['IDEIA','PLANEJAMENTO','CONSTRUÇÃO','TESTE','CORREÇÃO','VERSÃO FINAL'],'safe_execution':True}
    with conn() as c:c.execute('INSERT INTO ux_projects(id,owner_uid,name,kind,difficulty,objective,technology,visual,stage,data_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,uid(owner),name,kind,diff,objective,tech,visual,'IDEIA',json.dumps(data),t,t))
    _log(owner,'PROJECT_CREATED',name);return project(owner,pid)

def initial_files(kind):
    k=kind.lower()
    if k in ('web','site'):return [{'name':'index.html','purpose':'Estrutura da página'},{'name':'style.css','purpose':'Estilos'},{'name':'app.js','purpose':'Interações'}]
    if k in ('python','programming'):return [{'name':'main.py','purpose':'Ponto de entrada'},{'name':'README.md','purpose':'Objetivo e aprendizados'}]
    if k in ('game','rpg'):return [{'name':'game.js','purpose':'Lógica do jogo'},{'name':'index.html','purpose':'Canvas e interface'}]
    return [{'name':'README.md','purpose':'Objetivo, etapas e aprendizados'},{'name':'notes.json','purpose':'Configuração segura do projeto'}]

def project(owner,pid):
    with conn() as c:r=c.execute('SELECT * FROM ux_projects WHERE id=? AND owner_uid=?',(clean(pid,80),uid(owner))).fetchone()
    if not r:return None
    d=dict(r)
    try:d['data']=json.loads(d.pop('data_json'))
    except Exception:d['data']={}
    return d

def project_stage(owner,pid,stage):
    allowed=['IDEIA','PLANEJAMENTO','CONSTRUÇÃO','TESTE','CORREÇÃO','VERSÃO FINAL']
    stage=clean(stage,40).upper()
    if stage not in allowed:raise ValueError('Etapa inválida.')
    with conn() as c:c.execute('UPDATE ux_projects SET stage=?,updated_at=? WHERE id=? AND owner_uid=?',(stage,now(),clean(pid,80),uid(owner)))
    _log(owner,'PROJECT_STAGE',f'{pid}:{stage}');return project(owner,pid)

def project_public(owner,pid,value):
    with conn() as c:c.execute('UPDATE ux_projects SET public=?,updated_at=? WHERE id=? AND owner_uid=?',(1 if value else 0,now(),clean(pid,80),uid(owner)))
    return project(owner,pid)

def portfolio(owner):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT id,name,kind,difficulty,objective,technology,visual,stage,public,created_at,updated_at FROM ux_projects WHERE owner_uid=? AND public=1 ORDER BY updated_at DESC',(uid(owner),)).fetchall()]
    counts={}
    for r in rows:counts[r['kind']]=counts.get(r['kind'],0)+1
    return {'projects':rows,'counts':counts,'total':len(rows)}

def daily(owner):
    key=datetime.now(timezone.utc).date().isoformat();
    challenges=[('programming','Faça uma função que retorne o dobro de um número.'),('logic','Descubra o próximo termo de uma sequência simples.'),('game','Defina uma condição de vitória para um jogo.'),('ai','Explique com suas palavras o que é classificação.'),('security','Identifique qual evento de um log merece investigação primeiro.')]
    idx=sum(ord(x) for x in key)%len(challenges);kind,text=challenges[idx]
    with conn() as c:r=c.execute('SELECT completed FROM ux_daily WHERE owner_uid=? AND challenge_key=?',(uid(owner),key)).fetchone()
    return {'key':key,'kind':kind,'text':text,'completed':bool(r and r['completed'])}

def complete_daily(owner):
    key=daily(owner)['key'];withv=now()
    with conn() as c:c.execute('INSERT OR REPLACE INTO ux_daily(owner_uid,challenge_key,completed,updated_at) VALUES(?,?,1,?)',(uid(owner),key,withv))
    _log(owner,'DAILY_COMPLETE',key);return daily(owner)

def learning(owner):
    o=overview(owner)['learning']; levels=[('Conhecendo programação','variables'),('Criando seu primeiro jogo','game_logic'),('Aprendendo lógica','logic'),('Criando um site','html'),('Aprendendo segurança','security_basics'),('Criando um projeto completo','functions')]
    sk={x['id']:x for x in skills(owner)}; out=[]
    for i,(name,sid) in enumerate(levels,1):out.append({'level':i,'name':name,'progress':sk.get(sid,{}).get('progress',0),'unlocked':bool(sk.get(sid,{}).get('unlocked'))})
    return {'levels':out,'summary':o}

def analytics(owner):
    o=overview(owner); acts=o['activities']; return {'skills_learned':o['learning']['completed_skills'],'projects_created':len(o['projects']),'projects_public':sum(1 for x in o['projects'] if x['public']),'activities':len(acts),'recent':acts[:10],'note':'Tempo de estudo só é exibido quando uma sessão educativa existente fornece esse dado; esta camada não inventa métricas.'}

def observatory(owner):
    try: status=evolution2.status(owner)
    except Exception: status={}
    return {'services':status.get('services',[]),'database':status.get('DATABASE'),'auth':status.get('AUTH'),'ai':status.get('AI'),'arcade':status.get('ARCADE'),'maps':status.get('MAPS'),'storage':status.get('STORAGE'),'generated_at':now()}

def search(owner,q):
    q=clean(q,120).lower();out=[]
    for p in overview(owner)['projects']:
        if q in json.dumps(p,ensure_ascii=False).lower():out.append({'type':'project','id':p['id'],'title':p['name'],'detail':p['stage']})
    with conn() as c:
        rows=c.execute('SELECT id,title,kind FROM ux_ideas WHERE owner_uid=? ORDER BY id DESC LIMIT 50',(uid(owner),)).fetchall()
    for i in rows:
        if q in (i['title']+' '+i['kind']).lower():out.append({'type':'idea','id':i['id'],'title':i['title'],'detail':i['kind']})
    return out[:30]

def memory_board(owner):
    with conn() as c: rows=[dict(r) for r in c.execute('SELECT name,stage,updated_at,data_json FROM ux_projects WHERE owner_uid=? ORDER BY updated_at DESC LIMIT 20',(uid(owner),)).fetchall()]
    return [{'project':r['name'],'stage':r['stage'],'last_change':r['updated_at'],'note':'metadados do projeto; conteúdo sensível não é copiado para o painel'} for r in rows]

def guide(topic):
    guides={'first-game':['Escolha um gênero.','Crie o personagem.','Defina o objetivo.','Adicione regras.','Teste e ajuste.'],'python':['Comece por variáveis.','Pratique condições.','Use loops.','Crie funções.','Monte um pequeno projeto.'],'website':['Defina objetivo.','Estruture HTML.','Estilize com CSS.','Adicione interações.','Teste responsividade.']}
    key=clean(topic,40).lower();return {'topic':key,'steps':guides.get(key,guides['first-game'])}

def command(owner,text):
    q=clean(text,180).lower(); routes=[('game','/cyber/game-lab',['jogo','game','arcade']),('project','/cyber/ultra-platform',['projeto','project']),('maps','/cyber/ultra-platform',['mapa','mapas']),('python','/cyber/ultra-platform',['python','aula']),('cyber','/cyber',['segurança','cyber'])]
    for target,path,words in routes:
        if any(w in q for w in words):return {'target':target,'path':path,'reason':'intenção reconhecida por regras locais'}
    return {'target':'hub','path':'/cyber/ultra-platform','reason':'nenhuma intenção específica reconhecida'}
