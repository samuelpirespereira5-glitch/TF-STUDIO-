"""JARVIS Programming Universe 7.0.

Educational/local-first programming workspace. Reuses the existing project DB and
Game Lab concepts, but never executes user-authored code on the main server.
"""
from __future__ import annotations
import json, re, sqlite3, uuid, hashlib
from datetime import datetime, timezone
from services import platform_ultra, game_lab, phase5

LANGUAGES = [
    ('html','HTML','WEB','Preview local'),('css','CSS','WEB','Preview local'),
    ('javascript','JavaScript','WEB','Worker/preview local'),('python','Python','GENERAL','Análise; sem execução no servidor'),
    ('java','Java','GENERAL','Editor + análise'),('c','C','GENERAL','Editor + análise'),
    ('cpp','C++','GENERAL','Editor + análise'),('csharp','C#','GENERAL','Editor + análise'),
    ('sql','SQL','DATA','Sandbox SQLite'),('json','JSON','DATA','Validação local'),('markdown','Markdown','DOCS','Preview local')
]

TRACKS = [
 ('beginner','INICIANTE',['HTML','CSS','JavaScript','Python']),
 ('intermediate','INTERMEDIÁRIO',['DOM','APIs','SQL','Git','Algoritmos']),
 ('advanced','AVANÇADO',['Backend','Arquitetura','Performance','Testes','Projetos'])
]

TEMPLATES = {
 'html-basic':('HTML básico','html','<!doctype html>\n<h1>Olá, JARVIS!</h1>'),
 'responsive-site':('Site responsivo','html','<main><h1>Meu site</h1><p>Responsivo.</p></main>'),
 'javascript':('JavaScript','javascript','const numbers = [1, 2, 3];\nconsole.log(numbers);'),
 'python':('Python','python','def hello(name):\n    return f"Olá, {name}!"\n\nprint(hello("JARVIS"))'),
 'api':('API educativa','javascript','const request = { method: "GET", url: "/api/demo" };\nconsole.log(request);'),
 'game-2d':('Jogo 2D','javascript','let score = 0;\nfunction update(){ score += 1; }'),
 'quiz':('Quiz','javascript','const questions = [{ text: "2+2?", answer: 4 }];'),
 'dashboard':('Dashboard','html','<section class="card"><h2>Dashboard</h2></section>'),
 'chatbot':('Chatbot','javascript','function reply(text){ return `Você disse: ${text}`; }'),
 'portfolio':('Portfólio','html','<header><h1>Meu Portfólio</h1></header>')
}

DAILY = [
 ('logic','Corrija uma condição que deveria aceitar somente notas de 0 a 10.'),
 ('programming','Crie uma função que receba dois números e retorne o maior.'),
 ('debugging','Encontre por que uma variável de contador não aumenta.'),
 ('web','Faça um card que se adapte a telas pequenas.'),
 ('algorithms','Implemente busca linear e conte as comparações.'),
 ('games','Adicione um estado PAUSED a um game loop.')
]

ACHIEVEMENTS = {
 'first_code':('Primeiro programa','Salvou seu primeiro código.'),
 'bug_fixed':('Caçador de bugs','Concluiu um desafio de debugging.'),
 'first_algorithm':('Primeiro algoritmo','Explorou um algoritmo.'),
 'first_api':('Primeira API','Abriu o API Lab.'),
 'first_database':('Primeiro banco','Executou uma consulta no SQL Lab.'),
 'first_site':('Primeiro site','Abriu o HTML/CSS Lab.'),
 'first_game':('Primeiro jogo','Abriu o Game Dev Lab.'),
 'first_project':('Primeiro projeto','Criou um projeto de programação.'),
 'daily':('Desafio diário','Concluiu um desafio diário.'),
}


def now(): return datetime.now(timezone.utc).isoformat()
def uid(v): return str(v or 'owner')[:120]

def conn():
    c=platform_ultra.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS prog7_workspace(
      owner_uid TEXT PRIMARY KEY, language TEXT DEFAULT 'javascript', code TEXT DEFAULT '',
      updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prog7_snapshots(
      id TEXT PRIMARY KEY, owner_uid TEXT NOT NULL, label TEXT NOT NULL,
      language TEXT NOT NULL, code TEXT NOT NULL, created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prog7_progress(
      owner_uid TEXT PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0,
      concepts_json TEXT NOT NULL DEFAULT '[]', achievements_json TEXT NOT NULL DEFAULT '[]',
      track TEXT NOT NULL DEFAULT 'beginner', updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prog7_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL, event TEXT NOT NULL,
      detail TEXT DEFAULT '', created_at TEXT NOT NULL)''')
    return c

def progress(owner):
    with conn() as c:r=c.execute('SELECT * FROM prog7_progress WHERE owner_uid=?',(uid(owner),)).fetchone()
    if not r:
        with conn() as c:c.execute('INSERT OR IGNORE INTO prog7_progress(owner_uid,updated_at) VALUES(?,?)',(uid(owner),now()))
        return {'xp':0,'concepts':[],'achievements':[],'track':'beginner'}
    return {'xp':r['xp'],'concepts':json.loads(r['concepts_json'] or '[]'),'achievements':json.loads(r['achievements_json'] or '[]'),'track':r['track']}

def award(owner,xp=0,concept=None,achievement=None):
    p=progress(owner);p['xp']+=max(0,int(xp))
    if concept and concept not in p['concepts']:p['concepts'].append(concept)
    if achievement and achievement in ACHIEVEMENTS and achievement not in p['achievements']:p['achievements'].append(achievement)
    p['track']='advanced' if p['xp']>=600 else 'intermediate' if p['xp']>=200 else 'beginner'
    with conn() as c:c.execute('UPDATE prog7_progress SET xp=?,concepts_json=?,achievements_json=?,track=?,updated_at=? WHERE owner_uid=?',(p['xp'],json.dumps(p['concepts']),json.dumps(p['achievements']),p['track'],now(),uid(owner)))
    return p

def event(owner,name,detail=''):
    with conn() as c:c.execute('INSERT INTO prog7_events(owner_uid,event,detail,created_at) VALUES(?,?,?,?)',(uid(owner),name,str(detail)[:500],now()))

def overview(owner):
    p=progress(owner); day=DAILY[datetime.now(timezone.utc).weekday()%len(DAILY)]
    return {'languages':[{'id':a,'name':b,'category':c,'execution':d} for a,b,c,d in LANGUAGES],
      'tracks':[{'id':a,'name':b,'subjects':c} for a,b,c in TRACKS], 'templates':[{'id':k,'name':v[0],'language':v[1]} for k,v in TEMPLATES.items()],
      'progress':p,'daily':{'category':day[0],'mission':day[1]},'achievements':[{'id':k,'name':v[0],'description':v[1],'unlocked':k in p['achievements']} for k,v in ACHIEVEMENTS.items()],
      'game_projects':game_lab.projects(owner)[:12]}

def workspace(owner):
    with conn() as c:r=c.execute('SELECT * FROM prog7_workspace WHERE owner_uid=?',(uid(owner),)).fetchone()
    return dict(r) if r else {'owner_uid':uid(owner),'language':'javascript','code':''}

def save_workspace(owner,language,code):
    language=str(language or 'javascript').lower();code=str(code or '')[:300000]
    if language not in {x[0] for x in LANGUAGES}:raise ValueError('Linguagem não suportada')
    with conn() as c:c.execute('INSERT INTO prog7_workspace(owner_uid,language,code,updated_at) VALUES(?,?,?,?) ON CONFLICT(owner_uid) DO UPDATE SET language=excluded.language,code=excluded.code,updated_at=excluded.updated_at',(uid(owner),language,code,now()))
    award(owner,5,'code', 'first_code');event(owner,'CODE_SAVED',language);return workspace(owner)

def snapshot(owner,label='Snapshot'):
    w=workspace(owner);sid=uuid.uuid4().hex[:16]
    with conn() as c:c.execute('INSERT INTO prog7_snapshots VALUES(?,?,?,?,?,?)',(sid,uid(owner),str(label)[:100],w.get('language','javascript'),w.get('code',''),now()))
    return {'id':sid,'label':label,'language':w.get('language'),'code':w.get('code'),'created_at':now()}

def snapshots(owner):
    with conn() as c:rows=c.execute('SELECT id,label,language,created_at FROM prog7_snapshots WHERE owner_uid=? ORDER BY created_at DESC LIMIT 50',(uid(owner),)).fetchall()
    return [dict(r) for r in rows]

def json_lab(text):
    raw=str(text or '')
    try:
        data=json.loads(raw);return {'valid':True,'formatted':json.dumps(data,ensure_ascii=False,indent=2),'minified':json.dumps(data,ensure_ascii=False,separators=(',',':')),'tree':_json_tree(data),'error':None}
    except Exception as e:return {'valid':False,'formatted':raw,'minified':raw,'tree':None,'error':str(e)}

def _json_tree(x,key='root',depth=0):
    if depth>8:return {'key':key,'type':'depth-limit','value':'…'}
    if isinstance(x,dict):return {'key':key,'type':'object','children':[_json_tree(v,str(k),depth+1) for k,v in x.items()]}
    if isinstance(x,list):return {'key':key,'type':'array','children':[_json_tree(v,str(i),depth+1) for i,v in enumerate(x[:100])]}
    return {'key':key,'type':type(x).__name__,'value':x}

def regex_lab(pattern,text,flags=''):
    try:
        f=re.I if 'i' in flags else 0
        matches=[{'start':m.start(),'end':m.end(),'text':m.group(0),'groups':list(m.groups())} for m in re.finditer(pattern,str(text or ''),f)][:200]
        return {'valid':True,'matches':matches,'explain':regex_explain(pattern),'error':None}
    except Exception as e:return {'valid':False,'matches':[],'explain':regex_explain(pattern),'error':str(e)}

def regex_explain(pattern):
    p=str(pattern);parts=[]
    if '^' in p:parts.append('^ ancora o início do texto')
    if '$' in p:parts.append('$ ancora o fim do texto')
    if '\\d' in p:parts.append(r'\d representa um dígito')
    if '\\w' in p:parts.append(r'\w representa caractere de palavra')
    if '+' in p:parts.append('+ indica uma ou mais ocorrências')
    if '*' in p:parts.append('* indica zero ou mais ocorrências')
    if '?' in p:parts.append('? torna o elemento opcional ou altera a quantificação')
    if '(' in p:parts.append('( ) cria um grupo de captura')
    if '[' in p:parts.append('[ ] cria uma classe de caracteres')
    return parts or ['Expressão literal simples ou padrão sem metacaracteres reconhecidos.']

def explain(code,level='INICIANTE'):
    s=str(code or '');lines=s.count('\n')+1;features=[]
    patterns=[('variáveis',r'\b(let|const|var|int|float|string|boolean)\b|\b[A-Za-z_]\w*\s*='),('funções',r'\b(function|def|class)\b|=>'),('condições',r'\b(if|else|elif|switch|case)\b'),('loops',r'\b(for|while|foreach)\b'),('classes',r'\bclass\b'),('entrada/saída',r'\b(print|console\.log|input)\b'),('dependências',r'\b(import|from|require)\b')]
    for n,p in patterns:
        if re.search(p,s):features.append(n)
    return {'level':level.upper(),'lines':lines,'features':features,'summary':f'Código com {lines} linha(s). Conceitos detectados: {", ".join(features) if features else "nenhum padrão básico detectado"}.','steps':[f'Observe a estrutura das {lines} linha(s).','Identifique dados e mudanças de estado.','Siga condições e loops na ordem em que podem executar.','Confira entradas, saídas e dependências.']}

def quality(code,language='javascript'):
    s=str(code or '');issues=[]
    if len(s)>8000:issues.append(('WARNING','Arquivo grande para uma única unidade; considere dividir responsabilidades.'))
    if re.search(r'\b(eval|exec)\s*\(',s):issues.append(('ERROR','Execução dinâmica detectada; evite eval/exec em código de aplicação.'))
    if language in ('javascript','python') and re.search(r'password\s*=\s*["\']',s,re.I):issues.append(('ERROR','Possível segredo hardcoded. Use configuração segura/secret manager.'))
    if s.count('if ') + s.count('if(') > 12:issues.append(('WARNING','Muitas condições no mesmo arquivo; avalie decompor a lógica.'))
    if s.count('\n\n\n')>=2:issues.append(('INFO','Há blocos muito espaçados; organização visual pode melhorar.'))
    if not re.search(r'\b(function|def|class)\b',s) and len(s)>250:issues.append(('INFO','Considere extrair responsabilidades em funções quando fizer sentido.'))
    return {'summary':{'errors':sum(x[0]=='ERROR' for x in issues),'warnings':sum(x[0]=='WARNING' for x in issues),'info':sum(x[0]=='INFO' for x in issues)},'issues':[{'severity':a,'message':b} for a,b in issues]}

def debug(code,language='javascript'):
    s=str(code or '');errs=[]
    if s.count('{')!=s.count('}'):errs.append(('Syntax Error','Chaves desbalanceadas.'))
    if s.count('(')!=s.count(')'):errs.append(('Syntax Error','Parênteses desbalanceados.'))
    if re.search(r'\bconsole\.log\(\s*([A-Za-z_]\w*)\s*\)',s) and not re.search(r'\b(?:let|const|var)\s+\1\b',s):errs.append(('Reference Error','Uma variável usada no log pode não estar declarada.'))
    if re.search(r'while\s*\(\s*true\s*\)',s,re.I):errs.append(('Logic Error','Loop potencialmente infinito; adicione uma condição de saída.'))
    return {'ok':not errs,'errors':[{'type':a,'message':b} for a,b in errs],'next_steps':['Leia a primeira ocorrência de erro.','Confirme a linha e o estado das variáveis.','Faça uma alteração pequena e teste novamente.']}

def algorithm(kind):
    data={
      'linear-search':{'name':'Busca linear','complexity':'O(n)','steps':['começa no primeiro item','compara com o alvo','avança um item','repete até achar ou terminar'],'code':'for (const item of items) { if (item === target) return item; }'},
      'binary-search':{'name':'Busca binária','complexity':'O(log n)','steps':['usa dados ordenados','olha o meio','descarta metade','repete'],'code':'while (left <= right) { const mid = Math.floor((left+right)/2); }'},
      'bubble-sort':{'name':'Bubble Sort','complexity':'O(n²)','steps':['compara vizinhos','troca quando necessário','repete passadas'],'code':'for (...) for (...) if (a[j] > a[j+1]) swap(a,j,j+1);'},
      'recursion':{'name':'Recursão','complexity':'depende do algoritmo','steps':['entra na função','reduz o problema','chega ao caso base','retorna'],'code':'function fact(n){ if(n<=1) return 1; return n*fact(n-1); }'},
      'stack':{'name':'Pilha','complexity':'O(1) no topo','steps':['push adiciona','peek observa','pop remove'],'code':'stack.push(value); const top = stack.pop();'},
      'queue':{'name':'Fila','complexity':'O(1) conceitual','steps':['enqueue entra no fim','dequeue sai do início'],'code':'queue.push(value); const first = queue.shift();'},
      'tree':{'name':'Árvore','complexity':'depende do balanceamento','steps':['raiz','filhos','percurso'],'code':'node.left = child; node.right = child;'},
      'graph':{'name':'Grafo','complexity':'depende da representação','steps':['vértices','arestas','percurso'],'code':'graph[A].push(B);'},
      'hash-table':{'name':'Hash table','complexity':'O(1) médio','steps':['gera hash','localiza bucket','salva/consulta valor'],'code':'map.set(key, value); map.get(key);'},
    }
    return data.get(kind, data['linear-search'])

def sql_lab(query):
    q=str(query or '').strip()[:10000]
    if re.search(r'\b(attach|detach|pragma\s+load_extension|vacuum|reindex)\b',q,re.I):return {'ok':False,'error':'Comando não permitido no sandbox educativo.'}
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    try:
        db.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,age INTEGER);CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL);INSERT INTO users VALUES(1,"Ana",15),(2,"Bruno",17),(3,"Carla",16);INSERT INTO orders VALUES(1,1,20.5),(2,1,8.0),(3,2,30.0);')
        cur=db.execute(q)
        rows=[dict(r) for r in cur.fetchmany(200)] if cur.description else []
        return {'ok':True,'columns':[x[0] for x in cur.description] if cur.description else [],'rows':rows,'row_count':len(rows),'explain':'Consulta executada somente em banco SQLite em memória; nada é salvo no banco do aplicativo.'}
    except Exception as e:return {'ok':False,'error':str(e),'explain':'Verifique sintaxe, nomes de tabelas, colunas e condições.'}
    finally:db.close()

def project_health(code,language='javascript'):
    q=quality(code,language);d=debug(code,language);return {'code_quality':q,'debug':d,'performance':{'note':'Métricas reais de requisições continuam no Performance Center 6.0.'},'security':{'note':'Análise educativa; não substitui revisão de segurança.'},'dependencies':{'note':'Dependências são inferidas apenas do código fornecido.'}}

def api_demo():
    return {'request':{'method':'GET','url':'/api/demo','headers':{'Accept':'application/json'},'body':None},'response':{'status':200,'headers':{'Content-Type':'application/json'},'body':{'message':'Olá do sandbox'}}}

def create_project(owner,name,template):
    if template not in TEMPLATES:raise ValueError('Template inválido')
    n=str(name or TEMPLATES[template][0])[:100];lang=TEMPLATES[template][1];code=TEMPLATES[template][2]
    save_workspace(owner,lang,code);sid=snapshot(owner,'Template '+n);award(owner,20,'project','first_project');event(owner,'PROJECT_CREATED',template)
    return {'name':n,'template':template,'language':lang,'code':code,'snapshot':sid}
