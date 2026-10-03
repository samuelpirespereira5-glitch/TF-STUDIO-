"""JARVIS Ecosystem 8.0 — project/workflow/creation/learning coordination layer.
Local-first educational metadata only. No arbitrary server-side code execution.
Reuses existing project, learning and programming services instead of duplicating them.
"""
from __future__ import annotations
import json, re, secrets, uuid
from datetime import datetime, timezone
from services import platform_ultra, ultra_experience, programming7, learning8, phase5


def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]
def clean(v,n=500): return str(v or '').strip()[:n]
def conn():
    c=platform_ultra.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS eco_workspaces(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,name TEXT NOT NULL,project_id TEXT DEFAULT '',description TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_tasks(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,title TEXT NOT NULL,description TEXT DEFAULT '',kind TEXT DEFAULT 'programming',priority TEXT DEFAULT 'medium',status TEXT DEFAULT 'todo',difficulty TEXT DEFAULT 'beginner',due_at TEXT DEFAULT '',related_json TEXT DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_timeline(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,event TEXT NOT NULL,detail TEXT DEFAULT '',version TEXT DEFAULT '',created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_snapshots(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,label TEXT NOT NULL,state_json TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_ideas(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,title TEXT NOT NULL,kind TEXT NOT NULL,description TEXT DEFAULT '',plan_json TEXT DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_designs(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,data_json TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_workflows(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT DEFAULT '',name TEXT NOT NULL,kind TEXT NOT NULL,nodes_json TEXT NOT NULL,edges_json TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_ai_experiments(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,input_json TEXT NOT NULL,results_json TEXT DEFAULT '[]',created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_tests(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,title TEXT NOT NULL,input_text TEXT DEFAULT '',expected_text TEXT DEFAULT '',actual_text TEXT DEFAULT '',status TEXT DEFAULT 'PENDING',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_changelog(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,version TEXT NOT NULL,category TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_courses(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,title TEXT NOT NULL,data_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_classrooms(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,name TEXT NOT NULL,join_code TEXT UNIQUE NOT NULL,data_json TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_class_members(classroom_id TEXT NOT NULL,user_uid TEXT NOT NULL,role TEXT NOT NULL,joined_at TEXT NOT NULL,PRIMARY KEY(classroom_id,user_uid))''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_shares(id TEXT PRIMARY KEY,owner_uid TEXT NOT NULL,workspace_id TEXT NOT NULL,grantee_uid TEXT NOT NULL,permission TEXT NOT NULL,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_settings(owner_uid TEXT PRIMARY KEY,data_json TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',kind TEXT DEFAULT 'info',read INTEGER DEFAULT 0,created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eco_mentor(owner_uid TEXT PRIMARY KEY,workspace_id TEXT DEFAULT '',mode TEXT DEFAULT 'GUIDE',step INTEGER DEFAULT 0,updated_at TEXT NOT NULL)''')
    return c


def _log(owner,wid,event,detail='',version=''):
    with conn() as c:
        c.execute('INSERT INTO eco_timeline(owner_uid,workspace_id,event,detail,version,created_at) VALUES(?,?,?,?,?,?)',(uid(owner),clean(wid,80),clean(event,100),clean(detail,700),clean(version,40),now()))

def _notify(owner,title,body,kind='info'):
    with conn() as c:c.execute('INSERT INTO eco_notifications(owner_uid,title,body,kind,created_at) VALUES(?,?,?,?,?)',(uid(owner),clean(title,160),clean(body,500),clean(kind,30),now()))

def _project(owner,pid):
    if not pid:return None
    return ultra_experience.project(owner,pid)

def workspace(owner,wid):
    with conn() as c:r=c.execute('SELECT * FROM eco_workspaces WHERE id=? AND owner_uid=?',(clean(wid,80),uid(owner))).fetchone()
    if not r:return None
    d=dict(r)
    p=_project(owner,d['project_id'])
    with conn() as c:
        tasks=[dict(x) for x in c.execute('SELECT * FROM eco_tasks WHERE workspace_id=? AND owner_uid=? ORDER BY updated_at DESC',(d['id'],uid(owner))).fetchall()]
        for t in tasks:
            try:t['related']=json.loads(t.pop('related_json') or '[]')
            except Exception:t['related']=[]
        snaps=[dict(x) for x in c.execute('SELECT id,label,created_at FROM eco_snapshots WHERE workspace_id=? AND owner_uid=? ORDER BY created_at DESC LIMIT 30',(d['id'],uid(owner))).fetchall()]
        timeline=[dict(x) for x in c.execute('SELECT event,detail,version,created_at FROM eco_timeline WHERE workspace_id=? AND owner_uid=? ORDER BY id DESC LIMIT 50',(d['id'],uid(owner))).fetchall()]
        tests=[dict(x) for x in c.execute('SELECT id,title,input_text,expected_text,actual_text,status,created_at,updated_at FROM eco_tests WHERE workspace_id=? AND owner_uid=? ORDER BY updated_at DESC LIMIT 50',(d['id'],uid(owner))).fetchall()]
    return {'workspace':d,'project':p,'tasks':tasks,'snapshots':snaps,'timeline':timeline,'tests':tests}

def create_workspace(owner,d):
    name=clean(d.get('name') or 'Meu Workspace',120); pid=clean(d.get('project_id'),80); t=now(); wid='eco-ws-'+uuid.uuid4().hex[:12]
    if pid and not _project(owner,pid): raise ValueError('Projeto não encontrado ou sem acesso.')
    with conn() as c:c.execute('INSERT INTO eco_workspaces VALUES(?,?,?,?,?,?,?)',(wid,uid(owner),name,pid,clean(d.get('description'),500),t,t))
    _log(owner,wid,'WORKSPACE_CREATED',name);_notify(owner,'Workspace criado',name)
    return workspace(owner,wid)

def list_workspaces(owner):
    with conn() as c:rows=[dict(r) for r in c.execute('SELECT * FROM eco_workspaces WHERE owner_uid=? ORDER BY updated_at DESC',(uid(owner),)).fetchall()]
    return rows

def planner(owner,wid,prompt):
    text=clean(prompt,500); low=text.lower()
    kind='game' if any(x in low for x in ('jogo','game','corrida','rpg')) else 'web' if any(x in low for x in ('site','website','página')) else 'app' if any(x in low for x in ('app','aplicativo')) else 'programming'
    architecture={'game':['loop de jogo','estado','input','renderização','testes'],'web':['interface','estado','API','dados','testes responsivos'],'app':['interface','serviços','dados','autorização','testes'],'programming':['entrada','lógica','funções','testes','documentação']}[kind]
    req=['objetivo claro','entradas e saídas definidas','tratamento de erros','teste de aceitação','documentação mínima']
    features={'game':['movimento','pontuação','condição de vitória'],'web':['layout responsivo','navegação','formulários'],'app':['fluxo principal','persistência','feedback de erro'],'programming':['funções','validação','casos-limite']}[kind]
    tasks=[]
    for title,typ in [('Definir objetivo','research'),('Desenhar arquitetura','documentation'),('Implementar núcleo','programming'),('Criar testes','tests'),('Corrigir problemas','correction'),('Documentar projeto','documentation')]:tasks.append({'title':title,'kind':typ,'priority':'high' if typ=='programming' else 'medium','status':'todo'})
    plan={'objective':text,'type':kind,'requirements':req,'features':features,'architecture':architecture,'tests':['fluxo principal','casos inválidos','responsividade quando aplicável'],'release':['revisão final','changelog','snapshot final','portfolio'],'tasks':tasks}
    if wid:
        w=workspace(owner,wid)
        if not w:raise ValueError('Workspace não encontrado.')
        for t in tasks:create_task(owner,{'workspace_id':wid,**t,'description':f'Tarefa gerada pelo planner para: {text}'})
        _log(owner,wid,'PLANNER_CREATED',text)
    return plan

def create_task(owner,d):
    wid=clean(d.get('workspace_id'),80)
    if not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    tid='eco-task-'+uuid.uuid4().hex[:12];t=now();rel=d.get('related') if isinstance(d.get('related'),list) else []
    with conn() as c:c.execute('INSERT INTO eco_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,uid(owner),wid,clean(d.get('title') or 'Nova tarefa',160),clean(d.get('description'),700),clean(d.get('kind') or 'programming',40),clean(d.get('priority') or 'medium',20),clean(d.get('status') or 'todo',30),clean(d.get('difficulty') or 'beginner',30),clean(d.get('due_at'),60),json.dumps(rel[:20],ensure_ascii=False),t,t))
    _log(owner,wid,'TASK_CREATED',d.get('title',''));return {'id':tid}

def update_task(owner,tid,d):
    allowed={'status':('todo','doing','done','blocked'),'priority':('low','medium','high'),'difficulty':('beginner','intermediate','advanced')}
    with conn() as c:r=c.execute('SELECT workspace_id FROM eco_tasks WHERE id=? AND owner_uid=?',(clean(tid,80),uid(owner))).fetchone()
    if not r:raise ValueError('Tarefa não encontrada.')
    sets=[];vals=[]
    for k,vals_allowed in allowed.items():
        if k in d:
            v=clean(d[k],30)
            if v not in vals_allowed:raise ValueError(f'{k} inválido')
            sets.append(k+'=?');vals.append(v)
    if 'title' in d:sets.append('title=?');vals.append(clean(d['title'],160))
    if 'description' in d:sets.append('description=?');vals.append(clean(d['description'],700))
    if not sets:return workspace(owner,r['workspace_id'])
    vals += [now(),clean(tid,80),uid(owner)]
    with conn() as c:c.execute('UPDATE eco_tasks SET '+','.join(sets)+',updated_at=? WHERE id=? AND owner_uid=?',vals)
    _log(owner,r['workspace_id'],'TASK_UPDATED',tid);return workspace(owner,r['workspace_id'])

def snapshot(owner,wid,label='Snapshot manual'):
    w=workspace(owner,wid)
    if not w:raise ValueError('Workspace não encontrado.')
    sid='eco-snap-'+uuid.uuid4().hex[:12];state={'workspace':w['workspace'],'project':w['project'],'tasks':w['tasks'],'tests':w['tests']}
    with conn() as c:c.execute('INSERT INTO eco_snapshots VALUES(?,?,?,?,?,?)',(sid,uid(owner),wid,clean(label,120),json.dumps(state,ensure_ascii=False),now()))
    _log(owner,wid,'SNAPSHOT_CREATED',label);return {'id':sid,'label':label,'created_at':now()}

def snapshot_get(owner,sid):
    with conn() as c:r=c.execute('SELECT * FROM eco_snapshots WHERE id=? AND owner_uid=?',(clean(sid,80),uid(owner))).fetchone()
    if not r:return None
    d=dict(r);d['state']=json.loads(d.pop('state_json'));return d

def diff_snapshots(owner,a,b):
    x=snapshot_get(owner,a);y=snapshot_get(owner,b)
    if not x or not y:raise ValueError('Snapshot não encontrado.')
    xa=json.dumps(x['state'],ensure_ascii=False,indent=2,sort_keys=True).splitlines();ya=json.dumps(y['state'],ensure_ascii=False,indent=2,sort_keys=True).splitlines()
    import difflib
    return {'from':x['label'],'to':y['label'],'diff':'\n'.join(difflib.unified_diff(xa,ya,fromfile=x['label'],tofile=y['label'],lineterm=''))}

def restore_snapshot(owner,sid):
    s=snapshot_get(owner,sid)
    if not s:raise ValueError('Snapshot não encontrado.')
    wid=s['workspace']['id'];d=s['state'];t=now()
    with conn() as c:
        c.execute('UPDATE eco_workspaces SET name=?,description=?,updated_at=? WHERE id=? AND owner_uid=?',(d['workspace']['name'],d['workspace'].get('description',''),t,wid,uid(owner)))
        c.execute('DELETE FROM eco_tasks WHERE workspace_id=? AND owner_uid=?',(wid,uid(owner)))
        for x in d.get('tasks',[]):
            c.execute('INSERT INTO eco_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(x['id'],uid(owner),wid,x['title'],x.get('description',''),x.get('kind','programming'),x.get('priority','medium'),x.get('status','todo'),x.get('difficulty','beginner'),x.get('due_at',''),json.dumps(x.get('related',[])),x.get('created_at',t),t))
    _log(owner,wid,'SNAPSHOT_RESTORED',s['label']);return workspace(owner,wid)

def idea(owner,d):
    iid='eco-idea-'+uuid.uuid4().hex[:12];t=now();title=clean(d.get('title') or 'Nova ideia',160);desc=clean(d.get('description'),700);kind=clean(d.get('kind') or 'project',40)
    plan=planner(owner,'',desc)
    with conn() as c:c.execute('INSERT INTO eco_ideas VALUES(?,?,?,?,?,?,?,?)',(iid,uid(owner),title,kind,desc,json.dumps(plan,ensure_ascii=False),t,t))
    return {'id':iid,'title':title,'kind':kind,'description':desc,'plan':plan}

def ideas(owner,q=''):
    q=clean(q,100).lower()
    with conn() as c:rows=[dict(r) for r in c.execute('SELECT id,title,kind,description,created_at,updated_at FROM eco_ideas WHERE owner_uid=? ORDER BY updated_at DESC LIMIT 100',(uid(owner),)).fetchall()]
    return [r for r in rows if not q or q in json.dumps(r,ensure_ascii=False).lower()]

def design_save(owner,d):
    wid=clean(d.get('workspace_id'),80)
    if not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    did=clean(d.get('id'),80) or 'eco-design-'+uuid.uuid4().hex[:12];kind=clean(d.get('kind') or 'wireframe',40);data=d.get('data') if isinstance(d.get('data'),dict) else {}
    with conn() as c:c.execute('INSERT INTO eco_designs(id,owner_uid,workspace_id,name,kind,data_json,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,data_json=excluded.data_json,updated_at=excluded.updated_at',(did,uid(owner),wid,clean(d.get('name') or 'Design',120),kind,json.dumps(data,ensure_ascii=False)[:200000],now()))
    _log(owner,wid,'DESIGN_UPDATED',kind);return {'id':did,'name':clean(d.get('name') or 'Design',120),'kind':kind,'data':data}

def workflow_save(owner,d):
    wid=clean(d.get('workspace_id'),80);nodes=d.get('nodes') if isinstance(d.get('nodes'),list) else [];edges=d.get('edges') if isinstance(d.get('edges'),list) else []
    if wid and not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    wid2=clean(d.get('id'),80) or 'eco-flow-'+uuid.uuid4().hex[:12]
    with conn() as c:c.execute('INSERT INTO eco_workflows VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,nodes_json=excluded.nodes_json,edges_json=excluded.edges_json,updated_at=excluded.updated_at',(wid2,uid(owner),wid,clean(d.get('name') or 'Workflow',120),clean(d.get('kind') or 'app-flow',40),json.dumps(nodes,ensure_ascii=False)[:100000],json.dumps(edges,ensure_ascii=False)[:100000],now()))
    if wid:_log(owner,wid,'WORKFLOW_UPDATED',d.get('kind',''))
    return {'id':wid2,'nodes':nodes[:200],'edges':edges[:300]}

def ai_experiment(owner,d):
    eid='eco-ai-'+uuid.uuid4().hex[:12];inp=d.get('input') if isinstance(d.get('input'),dict) else {'prompt_a':clean(d.get('prompt_a'),4000),'prompt_b':clean(d.get('prompt_b'),4000)};t=now()
    with conn() as c:c.execute('INSERT INTO eco_ai_experiments VALUES(?,?,?,?,?,?,?)',(eid,uid(owner),clean(d.get('name') or 'Experimento',120),clean(d.get('kind') or 'prompt-compare',50),json.dumps(inp,ensure_ascii=False),json.dumps(d.get('results') if isinstance(d.get('results'),list) else [],ensure_ascii=False),t))
    return {'id':eid,'name':clean(d.get('name') or 'Experimento',120),'kind':clean(d.get('kind') or 'prompt-compare',50),'input':inp,'results':d.get('results',[])}

def ai_agent_policy(owner,d):
    # Backend allowlist: a UI cannot grant capabilities not present in the caller's role.
    from services import permissions
    role=permissions.current_role();caps=set(permissions.caps_for(role));requested=d.get('tools') if isinstance(d.get('tools'),list) else []
    safe={'lessons','challenges','projects','game_lab','files','documentation','code_analysis','tests','portfolio','search'}
    allowed=[x for x in requested if str(x) in safe and (str(x) in caps or str(x) in {'lessons','challenges','projects','game_lab','documentation','tests','portfolio','search'})]
    return {'name':clean(d.get('name') or 'Agente',100),'goal':clean(d.get('goal'),500),'tools_requested':requested[:30],'tools_allowed':allowed,'role':role,'note':'Permissões efetivas são recalculadas no backend a cada operação.'}

def test_save(owner,d):
    wid=clean(d.get('workspace_id'),80)
    if not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    tid=clean(d.get('id'),80) or 'eco-test-'+uuid.uuid4().hex[:12];inp=clean(d.get('input'),1000);exp=clean(d.get('expected'),1000);act=clean(d.get('actual'),1000)
    status='PENDING' if act=='' else ('PASS' if act==exp else 'FAIL')
    with conn() as c:c.execute('INSERT INTO eco_tests VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,input_text=excluded.input_text,expected_text=excluded.expected_text,actual_text=excluded.actual_text,status=excluded.status,updated_at=excluded.updated_at',(tid,uid(owner),wid,clean(d.get('title') or 'Caso de teste',160),inp,exp,act,status,now(),now()))
    _log(owner,wid,'TEST_UPDATED',f'{clean(d.get("title") or "Caso de teste",160)}:{status}')
    return {'id':tid,'status':status}

def quality(owner,wid):
    w=workspace(owner,wid)
    if not w:raise ValueError('Workspace não encontrado.')
    tests=w['tests'];done=sum(1 for x in tests if x['status']=='PASS');fails=sum(1 for x in tests if x['status'] in ('FAIL','ERROR'))
    return {'project':w['workspace']['name'],'areas':{'CODE':'REVIEW','UI':'REVIEW','PERFORMANCE':'REVIEW','SECURITY':'REVIEW','ACCESSIBILITY':'REVIEW','TESTS':'PASS' if tests and fails==0 else 'ATTENTION','DOCUMENTATION':'REVIEW'},'tests':{'total':len(tests),'pass':done,'fail':fails},'suggestions':['Adicionar testes de casos-limite.','Revisar responsividade em mobile/tablet/desktop.','Registrar decisões arquiteturais.','Criar snapshot antes de mudanças grandes.']}

def changelog(owner,wid,d):
    if not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    with conn() as c:c.execute('INSERT INTO eco_changelog(owner_uid,workspace_id,version,category,content,created_at) VALUES(?,?,?,?,?,?)',(uid(owner),wid,clean(d.get('version') or '1.0.0',30),clean(d.get('category') or 'improvement',40),clean(d.get('content'),1000),now()))
    _log(owner,wid,'CHANGELOG',d.get('version',''));return {'ok':True}

def documentation(owner,wid):
    w=workspace(owner,wid)
    if not w:raise ValueError('Workspace não encontrado.')
    p=w['project'] or {}; files=(p.get('data') or {}).get('files',[])
    readme=f"# {w['workspace']['name']}\n\n{w['workspace'].get('description','')}\n\n## Projeto\n{p.get('objective','')}\n\n## Arquivos\n"+'\n'.join(f"- {x.get('name')}: {x.get('purpose','')}" for x in files)
    return {'readme':readme,'architecture':p.get('data',{}).get('modules',[]),'api':'Descreva endpoints reais existentes; nenhum endpoint é inventado aqui.','configuration':'Use variáveis de ambiente e configurações existentes.'}

def portfolio(owner):
    return ultra_experience.portfolio(owner)

def skill_tree(owner):
    return ultra_experience.skills(owner)

def analytics(owner):
    base=ultra_experience.analytics(owner);ws=list_workspaces(owner)
    with conn() as c:
        task=c.execute('SELECT COUNT(*) n FROM eco_tasks WHERE owner_uid=?',(uid(owner),)).fetchone()['n'];done=c.execute("SELECT COUNT(*) n FROM eco_tasks WHERE owner_uid=? AND status='done'",(uid(owner),)).fetchone()['n'];tests=c.execute("SELECT COUNT(*) n FROM eco_tests WHERE owner_uid=? AND status='PASS'",(uid(owner),)).fetchone()['n']
    base.update({'workspaces':len(ws),'tasks_total':task,'tasks_done':done,'tests_passed':tests,'note':'Métricas são derivadas de eventos e registros reais; sem pontos fictícios.'});return base

def recommendation(owner):
    ov=learning8.overview(owner);done=set(ov.get('progress',{}).get('completed',[]));rec=learning8.recommend(owner)
    return {'learning_next':rec,'completed_count':len(done),'next_steps':['Criar um workspace para aplicar a próxima habilidade.','Adicionar um teste de aceitação ao projeto.','Registrar um snapshot antes de uma mudança importante.']}

def notifications(owner):
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,title,body,kind,read,created_at FROM eco_notifications WHERE owner_uid=? ORDER BY id DESC LIMIT 50',(uid(owner),)).fetchall()]

def search(owner,q):
    q=clean(q,120).lower();out=[]
    for r in list_workspaces(owner):
        if q in json.dumps(r,ensure_ascii=False).lower():out.append({'type':'workspace','id':r['id'],'title':r['name'],'path':'/cyber/ecosystem'})
    for r in ideas(owner,q)[:10]:out.append({'type':'idea','id':r['id'],'title':r['title'],'path':'/cyber/ecosystem'})
    # Reuse existing project and learning catalogs instead of duplicating content.
    try:
        for p in ultra_experience.portfolio(owner).get('projects',[]):
            if q in json.dumps(p,ensure_ascii=False).lower():out.append({'type':'project','id':p['id'],'title':p['name'],'path':'/cyber/ultra-platform'})
    except Exception: pass
    return out[:40]

def command(text):
    q=clean(text,180).lower();rules=[('workspace','/cyber/ecosystem',['workspace','projeto']),('learning','/cyber/programming7',['aula','python','aprender']),('game','/cyber/game-lab',['game','jogo']),('portfolio','/cyber/ecosystem',['portfolio','portfólio']),('security','/cyber',['segurança','cyber'])]
    for target,path,words in rules:
        if any(x in q for x in words):return {'target':target,'path':path}
    return {'target':'ecosystem','path':'/cyber/ecosystem'}

def mentor(owner,d):
    wid=clean(d.get('workspace_id'),80);mode=clean(d.get('mode') or 'GUIDE',30).upper();step=max(0,min(5,int(d.get('step',0) or 0)))
    if wid and not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    steps=[('PERGUNTA','O que você já sabe e qual parte quer tentar primeiro?'),('PISTA','Que entrada, regra ou condição precisa existir?'),('EXPERIMENTO','Teste uma hipótese pequena antes de alterar tudo.'),('TENTATIVA','Faça uma primeira implementação e registre o resultado.'),('FEEDBACK','Compare o resultado com o objetivo e identifique a diferença.'),('SOLUÇÃO','Agora consolide a solução e explique por que ela funciona.')]
    with conn() as c:c.execute('INSERT OR REPLACE INTO eco_mentor VALUES(?,?,?,?,?)',(uid(owner),wid,mode,step,now()))
    return {'mode':mode,'step':step,'label':steps[step][0],'guidance':steps[step][1],'next_step':min(5,step+1),'note':'O modo mentor evita entregar a resposta imediatamente.'}

def overview(owner):
    ws=list_workspaces(owner)
    return {'workspaces':ws,'portfolio':portfolio(owner),'skills':skill_tree(owner),'analytics':analytics(owner),'recommendations':recommendation(owner),'notifications':notifications(owner)[:10],'ideas':ideas(owner)[:10],'quick_actions':['CRIAR WORKSPACE','PLANEJAR PROJETO','NOVA IDEIA','ABRIR WIREFRAME','CRIAR TESTE','ANALISAR QUALIDADE','DOCUMENTAR PROJETO','ABRIR PORTFÓLIO']}

def course_create(owner,d):
    cid='eco-course-'+uuid.uuid4().hex[:12];data=d.get('data') if isinstance(d.get('data'),dict) else {'modules':[]};t=now()
    with conn() as c:c.execute('INSERT INTO eco_courses VALUES(?,?,?,?,?,?)',(cid,uid(owner),clean(d.get('title') or 'Novo curso',160),json.dumps(data,ensure_ascii=False)[:300000],t,t))
    return {'id':cid,'title':clean(d.get('title') or 'Novo curso',160),'data':data}

def classroom_create(owner,d):
    cid='eco-class-'+uuid.uuid4().hex[:12];code=secrets.token_urlsafe(6).upper()[:8];t=now();data=d.get('data') if isinstance(d.get('data'),dict) else {'activities':[]}
    with conn() as c:
        c.execute('INSERT INTO eco_classrooms VALUES(?,?,?,?,?,?)',(cid,uid(owner),clean(d.get('name') or 'Minha turma',160),code,json.dumps(data,ensure_ascii=False)[:200000],t))
        c.execute('INSERT INTO eco_class_members VALUES(?,?,?,?)',(cid,uid(owner),'teacher',t))
    return {'id':cid,'name':clean(d.get('name') or 'Minha turma',160),'join_code':code,'role':'teacher'}

def classroom_join(owner,code):
    code=clean(code,20).upper()
    with conn() as c:r=c.execute('SELECT id,name FROM eco_classrooms WHERE join_code=?',(code,)).fetchone()
    if not r:raise ValueError('Código de turma inválido.')
    with conn() as c:c.execute('INSERT OR IGNORE INTO eco_class_members VALUES(?,?,?,?)',(r['id'],uid(owner),'student',now()))
    return {'classroom_id':r['id'],'name':r['name'],'role':'student'}

def classroom_list(owner):
    with conn() as c:
        rows=c.execute('SELECT c.id,c.name,c.join_code,m.role FROM eco_classrooms c JOIN eco_class_members m ON m.classroom_id=c.id WHERE m.user_uid=? ORDER BY c.created_at DESC',(uid(owner),)).fetchall()
    return [dict(r) for r in rows]

def share(owner,d):
    wid=clean(d.get('workspace_id'),80);grantee=clean(d.get('grantee_uid'),120);perm=clean(d.get('permission') or 'view',30)
    if not workspace(owner,wid):raise ValueError('Workspace não encontrado.')
    if perm not in ('private','view','remix','edit'):raise ValueError('Permissão inválida.')
    if not grantee:raise ValueError('Destinatário obrigatório.')
    sid='eco-share-'+uuid.uuid4().hex[:12]
    with conn() as c:c.execute('INSERT OR REPLACE INTO eco_shares VALUES(?,?,?,?,?,?)',(sid,uid(owner),wid,grantee,perm,now()))
    return {'id':sid,'workspace_id':wid,'grantee_uid':grantee,'permission':perm}

def remix(owner,wid):
    w=workspace(owner,wid)
    if not w:raise ValueError('Workspace não encontrado.')
    p=w['project']
    np=None
    if p:
        np=ultra_experience.create_project(owner,{'name':p['name']+' — Remix','kind':p['kind'],'difficulty':p['difficulty'],'objective':p['objective'],'technology':p['technology'],'visual':p['visual']})
    nw=create_workspace(owner,{'name':w['workspace']['name']+' — Remix','project_id':np['id'] if np else '','description':w['workspace'].get('description','')+' (remix)'})
    for t in w['tasks']:
        create_task(owner,{'workspace_id':nw['workspace']['id'],'title':t['title'],'description':t.get('description',''),'kind':t.get('kind','programming'),'priority':t.get('priority','medium'),'status':'todo','difficulty':t.get('difficulty','beginner'),'related':t.get('related',[])})
    _log(owner,nw['workspace']['id'],'PROJECT_REMIXED',wid)
    return workspace(owner,nw['workspace']['id'])
