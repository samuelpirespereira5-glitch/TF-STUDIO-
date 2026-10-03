"""JARVIS Kids Code + Game Lab.
Educational, local-first game creation layer. Reuses the existing Arcade catalog and
existing gamification. User-authored code is never executed on the server.
"""
from __future__ import annotations
import json, re, time, uuid, sqlite3
from datetime import datetime, timezone
from services import platform_ultra, gamification, phase5

DB = platform_ultra.DB

COURSES = [
    ('intro','Introdução à programação','Como programas pensam e como jogos são construídos.'),
    ('variables','Variáveis','Guarde velocidade, vidas, pontos e outras informações.'),
    ('conditions','Condições','Faça o jogo tomar decisões com if/else.'),
    ('loops','Loops','Repita ações de forma controlada.'),
    ('functions','Funções','Organize comportamentos em blocos reutilizáveis.'),
    ('events','Eventos','Responda a teclado, toque e ações do jogador.'),
    ('arrays','Listas e arrays','Organize vários itens do jogo.'),
    ('objects','Objetos','Modele jogadores, inimigos e itens.'),
    ('collision','Colisões','Descubra quando objetos se encostam.'),
    ('game-logic','Game Logic','Una regras, estados, vitória e derrota.'),
    ('debug','Debug','Encontre e corrija erros de programação.'),
    ('javascript','JavaScript','Crie interações reais no navegador.'),
    ('html','HTML','Monte a estrutura de uma página ou jogo.'),
    ('css','CSS','Crie visual, layout e interface.'),
    ('python','Python','Aprenda Python; nesta plataforma ele é estudado, não executado no servidor.'),
]

TEMPLATES = {
 'snake': ('Snake','ARCADE',['player','movement','collision','score','game-over']),
 'platformer': ('Platformer','PLATAFORMA',['player','movement','jump','gravity','collision','goal']),
 'space': ('Space Shooter','SPACE',['player','movement','enemies','score','health']),
 'maze': ('Maze','LABIRINTO',['player','movement','collision','key','door','goal']),
 'racing': ('Racing','CORRIDA',['player','movement','timer','levels','goal']),
 'quiz': ('Quiz','QUIZ',['events','score','levels']),
 'puzzle': ('Puzzle','PUZZLE',['events','conditions','score']),
 'clicker': ('Clicker','CLICKER',['events','score','timer']),
 'adventure': ('Adventure','AVENTURA',['player','dialogue','quests','items','levels']),
}

MECHANICS = {
 'movement': ('MOVEMENT','Mover o jogador com velocidade controlável.','player.x += speed','Altere speed e teste.'),
 'jump': ('JUMP','Um impulso vertical altera a velocidade do personagem.','player.vy = -jumpPower','Faça o salto ficar mais alto sem quebrar o movimento.'),
 'collision': ('COLLISION','Uma colisão acontece quando duas áreas se sobrepõem.','if (hit(player, enemy)) { loseLife(); }','Faça a colisão reduzir uma vida.'),
 'health': ('HEALTH','Vidas representam quanto o jogador ainda pode errar.','health -= 1','Crie uma regra que não deixe health ficar negativo.'),
 'score': ('SCORE','Pontuação registra o progresso do jogador.','score += 10','Faça uma moeda adicionar 10 pontos.'),
 'enemies': ('ENEMIES','Inimigos são entidades que seguem uma regra de movimento.','enemy.x -= enemy.speed','Faça o inimigo andar em direção ao jogador.'),
 'items': ('ITEMS','Itens são objetos que podem ser coletados.','if (touch(player, coin)) score += 10','Faça a moeda desaparecer depois de coletada.'),
 'levels': ('LEVELS','Níveis mudam o desafio progressivamente.','level += 1','Crie uma condição para avançar de nível.'),
 'timer': ('TIMER','Um temporizador cria pressão ou eventos por tempo.','timeLeft -= delta','Faça o jogo terminar quando chegar a zero.'),
 'checkpoint': ('CHECKPOINT','Um checkpoint guarda um ponto seguro de retorno.','checkpoint = player.position','Crie um ponto de retorno.'),
 'dialogue': ('DIALOGUE','Diálogos apresentam histórias e escolhas.','showMessage("Olá!")','Faça uma mensagem aparecer ao tocar um personagem.'),
 'quests': ('QUESTS','Missões organizam objetivos.','quest.done = true','Crie uma condição para completar a missão.'),
}

CHALLENGES = [
 {'id':'speed','title':'Deixe o jogador mais rápido','concept':'variáveis','starter':'speed = 5','target':'speed = 10','hint1':'Procure a variável que controla a velocidade.','hint2':'Ela aparece perto do movimento.','explain':'Aumentar a variável muda o valor usado pelo movimento.'},
 {'id':'coin','title':'Faça uma moeda dar pontos','concept':'condições','starter':'score = 0','target':'score += 10','hint1':'Procure o trecho que acontece quando a moeda é tocada.','hint2':'A pontuação é uma variável que pode ser aumentada.','explain':'+= adiciona um valor ao que já existe.'},
 {'id':'jump','title':'Faça o personagem pular','concept':'eventos','starter':'jumpPower = 8','target':'player.vy = -jumpPower','hint1':'Pular altera a velocidade vertical.','hint2':'Procure a variável jumpPower.','explain':'O evento de pulo aplica um impulso vertical.'},
 {'id':'enemy','title':'Faça o inimigo se mover','concept':'movimento','starter':'enemy.x = 400','target':'enemy.x -= enemy.speed','hint1':'O inimigo precisa alterar sua posição.','hint2':'Procure a propriedade x.','explain':'Subtrair velocidade de x move o inimigo para a esquerda.'},
 {'id':'condition','title':'Crie uma condição de vitória','concept':'condições','starter':'score = 0','target':'if (score >= 100) win()','hint1':'Uma condição começa com if.','hint2':'Compare a pontuação com 100.','explain':'if executa uma ação somente quando a condição é verdadeira.'},
]


def now(): return datetime.now(timezone.utc).isoformat()
def _uid(v): return str(v or 'owner')[:120]

def conn():
    c = phase5.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS kids_projects(
        id TEXT PRIMARY KEY, owner_uid TEXT NOT NULL, name TEXT NOT NULL, description TEXT DEFAULT '',
        template TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, progress INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'DRAFT', data_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kids_project_versions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, owner_uid TEXT NOT NULL,
        version INTEGER NOT NULL, changes TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kids_progress(
        owner_uid TEXT PRIMARY KEY, level INTEGER NOT NULL DEFAULT 1, xp INTEGER NOT NULL DEFAULT 0,
        concepts_json TEXT NOT NULL DEFAULT '[]', challenges_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kids_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_uid TEXT NOT NULL, started_at TEXT NOT NULL,
        duration_seconds INTEGER DEFAULT 0, challenges INTEGER DEFAULT 0, correct INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0, concepts_json TEXT NOT NULL DEFAULT '[]', xp INTEGER DEFAULT 0)''')
    return c


def _progress(owner):
    with conn() as c:
        r=c.execute('SELECT * FROM kids_progress WHERE owner_uid=?',(_uid(owner),)).fetchone()
        if not r:
            c.execute('INSERT INTO kids_progress(owner_uid,updated_at) VALUES(?,?)',(_uid(owner),now()))
            return {'level':1,'xp':0,'concepts':[],'challenges':[]}
        return {'level':r['level'],'xp':r['xp'],'concepts':json.loads(r['concepts_json'] or '[]'),'challenges':json.loads(r['challenges_json'] or '[]')}


def _award(owner,xp,concept=None,challenge=None):
    p=_progress(owner); p['xp'] += max(0,int(xp));
    if concept and concept not in p['concepts']: p['concepts'].append(concept)
    if challenge and challenge not in p['challenges']: p['challenges'].append(challenge)
    p['level']=1 + min(9,p['xp']//100)
    with conn() as c:c.execute('UPDATE kids_progress SET level=?,xp=?,concepts_json=?,challenges_json=?,updated_at=? WHERE owner_uid=?',(p['level'],p['xp'],json.dumps(p['concepts']),json.dumps(p['challenges']),now(),_uid(owner)))
    return p


def catalog(owner):
    games=platform_ultra.arcade_catalog(owner)
    enrich={
      'snake':('🐍','Variáveis, movimento, colisão e pontuação.'), 'pong':('🏓','Eventos, movimento e regras de vitória.'),
      'breakout':('🧱','Loops, colisões, blocos e pontuação.'), 'memory':('🧠','Arrays, estado e comparação.'),
      'tictactoe':('⭕','Condições, turnos e lógica.'), '2048':('🔢','Arrays, regras e estados.'),
      'reaction':('⚡','Eventos, tempo e condições.'), 'typing':('⌨️','Eventos, texto e pontuação.'),
      'maze':('🧩','Movimento, colisão, chave e objetivo.'), 'cyber-quiz':('🛡️','Condições, perguntas e feedback.'),
      'code-puzzle':('💻','Sequência lógica e programação.'), 'cyber-memory':('🧠','Estado, comparação e memória.'),
      'code-runner':('▶️','Entrada, lógica e resultado seguro.'), 'logic-grid':('🧩','Condições e raciocínio.'),
      'password-defense':('🔐','Regras, condições e segurança.'), 'packet-defender':('📦','Classificação e decisões.'),
      'binary-challenge':('01','Números e conversão.'), 'cipher-lab':('🔤','Transformações e lógica.'),
      'security-tower':('🏰','Eventos e decisões defensivas.'), 'bug-hunter':('🐞','Debug e correção.'), 'terminal-puzzle':('⌨️','Sequência e lógica.'),
    }
    return [{**g,'icon':enrich.get(g['id'],('🎮','Aprenda como este jogo funciona.'))[0],'learning':enrich.get(g['id'],('🎮',''))[1],
             'features':['JOGAR','COMO FUNCIONA','VER CÓDIGO','EXPERIMENTAR','DESAFIO']} for g in games]


def game_detail(owner,gid):
    game=next((g for g in catalog(owner) if g['id']==gid),None)
    if not game:return None
    code={
      'snake': {'beginner':['const speed = 5;','player.x += speed;','if (collision(player, food)) score += 10;'], 'intermediate':['function movePlayer(){ player.x += speed; }','if (collision(player, wall)) gameOver();'], 'advanced':['function update(dt){ movePlayer(dt); detectCollisions(); updateScore(dt); }']},
      'maze': {'beginner':['const speed = 5;','player.x += dx;'], 'intermediate':['if (!wallAt(next)) player.position = next;'], 'advanced':['function update(){ readInput(); resolveCollision(); checkGoal(); }']},
      'pong': {'beginner':['const speed = 4;','ball.x += ball.vx;'], 'intermediate':['if (hit(player, ball)) ball.vx *= -1;'], 'advanced':['function update(dt){ physics(dt); ai(dt); scoreState(); }']},
    }.get(gid,{'beginner':['let score = 0;','score += 10;'], 'intermediate':['if (score >= 100) win();'], 'advanced':['function update(){ /* regras do jogo */ }']})
    return {'game':game,'code':code,'explanations':{
      'player':'Representa o personagem que o jogador controla.','movement':'Muda a posição do personagem.','collision':'Verifica se dois objetos encostaram.','score':'Guarda a pontuação atual.','game-over':'Encerra a partida quando uma regra é atingida.'}}


def experiment(owner,gid,values):
    allowed={'speed':(0,30,5),'score':(0,100,10),'enemies':(0,10,3),'gravity':(0,10,1),'jumpPower':(0,30,8)}
    out={}
    for k,(lo,hi,default) in allowed.items():
        try:v=float(values.get(k,default)); v=max(lo,min(hi,v)); out[k]=int(v) if v.is_integer() else v
        except Exception:out[k]=default
    _award(owner,5,'experiment')
    return {'game_id':gid,'values':out,'safe':True,'message':'Experimento aplicado apenas ao preview do navegador.'}


def challenge_check(owner,cid,answer):
    c=next((x for x in CHALLENGES if x['id']==cid),None)
    if not c: raise ValueError('Desafio não encontrado')
    normalized=re.sub(r'\s+','',str(answer or '')).lower(); target=re.sub(r'\s+','',c['target']).lower()
    ok=normalized==target
    p=_award(owner,25 if ok else 0,c['concept'] if ok else None,cid if ok else None)
    return {'correct':ok,'explanation':c['explain'],'hint':c['hint1'],'xp':25 if ok else 0,'progress':p}


def create_project(owner,data):
    name=str(data.get('name') or 'Meu Jogo')[:100]; template=str(data.get('template') or 'platformer')[:40]
    if template not in TEMPLATES: raise ValueError('Template inválido')
    pid=uuid.uuid4().hex[:16]; t=now(); payload={'language':'javascript','blocks':[],'code':'// Comece aqui\nlet score = 0;','settings':{'age_level':'BEGINNER','controls':['keyboard','touch']},'requirements':TEMPLATES[template][2]}
    with conn() as c:
        c.execute('INSERT INTO kids_projects VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,_uid(owner),name,str(data.get('description') or '')[:500],template,1,0,'DRAFT',json.dumps(payload),t,t))
        c.execute('INSERT INTO kids_project_versions(project_id,owner_uid,version,changes,data_json,created_at) VALUES(?,?,?,?,?,?)',(pid,_uid(owner),1,'Projeto criado a partir do template',json.dumps(payload),t))
    phase5.audit(owner,'GAME_PROJECT_CREATED',pid,template); _award(owner,10,'game-creation')
    return project(owner,pid)


def project(owner,pid):
    with conn() as c:r=c.execute('SELECT * FROM kids_projects WHERE id=? AND owner_uid=?',(pid,_uid(owner))).fetchone()
    if not r:return None
    d=dict(r); d['data']=json.loads(d.pop('data_json')); return d


def projects(owner):
    with conn() as c:rows=c.execute('SELECT * FROM kids_projects WHERE owner_uid=? ORDER BY updated_at DESC',(_uid(owner),)).fetchall()
    return [{**dict(r),'data':json.loads(r['data_json'])} for r in rows]


def save_project(owner,pid,data):
    p=project(owner,pid)
    if not p: raise ValueError('Projeto não encontrado')
    old=p['version']; new=old+1; t=now(); safe={'language':str(data.get('language') or p['data'].get('language') or 'javascript'),'blocks':data.get('blocks') or [],'code':str(data.get('code') or '')[:20000],'settings':data.get('settings') or p['data'].get('settings',{}),'requirements':p['data'].get('requirements',[])}
    progress=max(0,min(100,int(data.get('progress',p['progress']) or 0)))
    changes=str(data.get('changes') or 'Alterações do projeto')[:500]
    with conn() as c:
        c.execute('UPDATE kids_projects SET version=?,progress=?,data_json=?,updated_at=? WHERE id=? AND owner_uid=?',(new,progress,json.dumps(safe),t,pid,_uid(owner)))
        c.execute('INSERT INTO kids_project_versions(project_id,owner_uid,version,changes,data_json,created_at) VALUES(?,?,?,?,?,?)',(pid,_uid(owner),new,changes,json.dumps(safe),t))
    phase5.audit(owner,'GAME_PROJECT_SAVED',pid,f'version={new}'); return project(owner,pid)


def remix(owner,pid):
    p=project(owner,pid)
    if not p: raise ValueError('Projeto não encontrado')
    return create_project(owner,{'name':p['name']+' — Remix','description':'Remix independente de '+p['name'],'template':p['template']})


def block_code(blocks):
    mapping={'start':'// quando começar','move':'player.x += 10;','jump':'player.vy = -jumpPower;','collision':'if (hit(player, enemy)) { loseLife(); }','score':'score += 10;','enemy':'enemy.x -= enemy.speed;','win':'win();','lose':'gameOver();'}
    return '\n'.join(mapping.get(str(b.get('type') if isinstance(b,dict) else b),'// bloco não reconhecido') for b in blocks[:50])



def friendly_error(name, message):
    n=str(name or '')
    if n == 'ReferenceError': return '⚠️ O jogo tentou usar uma variável ou função que ainda não existe.'
    if n == 'SyntaxError': return '⚠️ Há um pequeno erro de escrita no código. Confira parênteses, chaves e pontos e vírgulas.'
    if n == 'TypeError': return '⚠️ O jogo tentou usar um valor de um jeito que não combina com ele.'
    return '⚠️ O jogo encontrou um erro durante o teste. O JARVIS pode explicar a linha.'

def validate_code(code):
    text=str(code or '')[:20000]
    blocked=[(r'\bfetch\s*\(', 'Acesso de rede não é permitido no Game Lab.'),(r'WebSocket', 'WebSocket não é permitido.'),(r'document\.cookie', 'Cookies não são acessíveis.'),(r'localStorage|sessionStorage|indexedDB', 'Armazenamentos do navegador não são usados no preview.'),(r'window\.(top|parent|opener)', 'Acesso à janela externa não é permitido.'),(r'\bimport\s+|\bimport\(', 'Importações não são permitidas no preview.'),(r'\beval\s*\(|\bFunction\s*\(', 'Execução dinâmica de código não é permitida.'),(r'location\.(href|assign|replace)', 'Navegação não é permitida no preview.'),(r'<\s*script', 'HTML/script embutido não é permitido.')]
    errors=[msg for pat,msg in blocked if re.search(pat,text,re.I)]
    return {'safe':not errors,'errors':errors,'warnings':['O preview executa JavaScript somente em Worker sandbox local; nunca no servidor.'],'length':len(text)}

def teacher_explain(code,level='BEGINNER'):
    text=str(code or '')[:3000]
    rules=[(r'\bif\b','if verifica uma condição e só executa o bloco quando ela é verdadeira.'),(r'\bfor\b|\bwhile\b','for/while repetem uma ação seguindo uma regra.'),(r'function|=>','Uma função agrupa instruções que podem ser usadas quando precisamos daquele comportamento.'),(r'\+=','+= adiciona um valor ao que a variável já tinha.'),(r'\bconst\b|\blet\b','const/let criam variáveis para guardar informações do programa.'),(r'\.x\b|\.y\b','x e y representam posições no espaço do jogo.')]
    found=[msg for pat,msg in rules if re.search(pat,text,re.I)]
    return {'level':str(level).upper(),'explanation':found[:5] or ['Esse trecho é código do jogo. Podemos analisar variável por variável e testar pequenas mudanças.'],'safe':True}


def session_report(owner,started,duration,challenges,correct,errors,concepts):
    xp=max(0,int(correct)*15); p=_award(owner,xp)
    with conn() as c:c.execute('INSERT INTO kids_sessions(owner_uid,started_at,duration_seconds,challenges,correct,errors,concepts_json,xp) VALUES(?,?,?,?,?,?,?,?)',(_uid(owner),started,int(duration),int(challenges),int(correct),int(errors),json.dumps(concepts[:30]),xp))
    return {'duration_seconds':int(duration),'challenges':int(challenges),'correct':int(correct),'errors':int(errors),'concepts':concepts[:30],'xp':xp,'next_step':'Escolha um conceito ainda não aprendido e crie uma pequena mecânica.','progress':p}


def overview(owner):
    p=_progress(owner); projs=projects(owner); return {'progress':p,'projects':len(projs),'games':catalog(owner),'courses':[{'id':a,'name':b,'description':c} for a,b,c in COURSES],'challenges':CHALLENGES,'mechanics':{k:{'name':v[0],'explanation':v[1],'code':v[2],'challenge':v[3]} for k,v in MECHANICS.items()},'templates':[{'id':k,'name':v[0],'category':v[1],'features':v[2]} for k,v in TEMPLATES.items()]}


# Phase 9 educational games catalog (metadata; play in /cyber/phase9)
PHASE9_EDU_GAMES = [
  "robot_code","code_maze","bug_hunter","algorithm_race",
  "space_programmer","logic_factory","database_quest","api_adventure",
]
