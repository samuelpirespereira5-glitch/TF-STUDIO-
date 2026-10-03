"""JARVIS Learning + Game Studio 8.0.
Progressive educational content with anti-repetition and real user progress.
No arbitrary code execution is performed here.
"""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from services import platform_ultra

TRACKS = [
    {"id":"foundations","title":"Primeiros Passos","subjects":["lógica","algoritmos","variáveis","condições","loops","funções"]},
    {"id":"web","title":"Web","subjects":["HTML","CSS","JavaScript","DOM","eventos","HTTP","JSON","APIs","responsividade"]},
    {"id":"python","title":"Python","subjects":["sintaxe","tipos","condições","loops","funções","listas","dicionários","módulos","arquivos","exceções","classes"]},
    {"id":"backend","title":"Backend","subjects":["servidor","rotas","APIs","autenticação","banco","sessões","validação"]},
    {"id":"database","title":"Database","subjects":["tabelas","relacionamentos","SQL","índices","consultas","JOIN","modelagem"]},
    {"id":"games","title":"Game Dev","subjects":["game loop","input","colisão","sprites","animação","física","câmera","níveis","inimigos","UI"]},
    {"id":"ai","title":"IA","subjects":["modelos","prompts","APIs","embeddings","RAG","agentes","ferramentas","avaliação"]},
    {"id":"security","title":"Segurança defensiva","subjects":["autenticação","autorização","hashing","sessões","validação","segurança web","segurança de APIs","defesa"]},
]

LESSONS = {
 "variables": {"track":"foundations","title":"Variáveis que mudam o estado de um programa","prereq":[],"concept":"variáveis","intro":"Você vai aprender a guardar valores e acompanhar como eles mudam.","why":"Quase todo programa precisa manter estado.","example":"let score = 0;\nscore += 10;\nconsole.log(score);","line":"score += 10;","experiment":"Mude 10 para 25 e observe o novo resultado.","exercise":"Crie uma variável lives com valor 3 e reduza uma vida.","challenge":"Crie score e lives e faça a vitória acontecer quando score >= 100.","common":["usar = quando queria comparar","usar uma variável antes de criá-la"],"extra":"Adicione um combo que aumenta a pontuação por acerto.","project":"Mini placar de jogo"},
 "conditions": {"track":"foundations","title":"Condições e decisões","prereq":["variables"],"concept":"condições","intro":"Programas tomam decisões com base no estado.","why":"É o que permite reagir a situações diferentes.","example":"if (score >= 100) {\n  win();\n} else {\n  keepPlaying();\n}","line":"score >= 100","experiment":"Troque o limite e veja quando a decisão muda.","exercise":"Mostre 'aprovado' quando nota >= 6.","challenge":"Combine score e lives para decidir vitória ou game over.","common":["confundir = com ==/===","esquecer chaves ou indentação"],"extra":"Crie três faixas: fácil, médio e difícil.","project":"Sistema de classificação"},
 "loops": {"track":"foundations","title":"Loops para repetir trabalho sem copiar código","prereq":["conditions"],"concept":"loops","intro":"Loops automatizam tarefas repetitivas.","why":"Jogos, listas e processamento de dados usam repetição o tempo todo.","example":"for (let i = 0; i < 5; i++) {\n  console.log(i);\n}","line":"i++","experiment":"Mude 5 para 10.","exercise":"Some os números de 1 a 10.","challenge":"Percorra um inventário e conte apenas itens disponíveis.","common":["condição que nunca termina","limite errado"],"extra":"Compare for e while no mesmo problema.","project":"Contador de inventário"},
 "functions": {"track":"foundations","title":"Funções para organizar comportamento","prereq":["loops"],"concept":"funções","intro":"Funções agrupam uma tarefa em uma unidade reutilizável.","why":"Elas reduzem repetição e deixam sistemas maiores mais organizados.","example":"function add(a, b) {\n  return a + b;\n}","line":"return a + b;","experiment":"Crie uma função multiply.","exercise":"Faça uma função que receba nome e devolva uma saudação.","challenge":"Separe validação, cálculo e apresentação em funções diferentes.","common":["esquecer return","misturar parâmetros e argumentos"],"extra":"Faça uma função que receba outra função.","project":"Biblioteca de utilidades"},
 "http-api": {"track":"web","title":"APIs: conectando interfaces e serviços","prereq":["conditions"],"concept":"HTTP e APIs","intro":"Você vai acompanhar o caminho de uma requisição até a resposta.","why":"Aplicações reais trocam dados por APIs.","example":"fetch('/api/demo')\n  .then(r => r.json())\n  .then(data => console.log(data));","line":"r.json()","experiment":"Observe método, status e JSON no API Lab.","exercise":"Identifique método, URL, headers e body em uma requisição.","challenge":"Modele um endpoint GET de tarefas com resposta JSON.","common":["confundir status HTTP com conteúdo","não tratar erro"],"extra":"Modele POST + validação sem enviar dados para terceiros.","project":"Mini API de tarefas"},
 "joins": {"track":"database","title":"JOIN: relacionando informações de tabelas","prereq":["http-api"],"concept":"JOIN","intro":"Você vai juntar dados relacionados sem duplicar informações.","why":"Bancos relacionais separam dados e usam chaves para relacioná-los.","example":"SELECT users.name, orders.total\nFROM users\nJOIN orders ON orders.user_id = users.id;","line":"ON orders.user_id = users.id","experiment":"Troque JOIN por LEFT JOIN no sandbox e compare.","exercise":"Liste usuários que possuem pedidos.","challenge":"Calcule o total por usuário usando GROUP BY.","common":["juntar colunas sem chave","usar condição de JOIN incorreta"],"extra":"Compare INNER JOIN e LEFT JOIN com dados vazios.","project":"Relatório de vendas"},
 "game-loop": {"track":"games","title":"Game loop e estados","prereq":["loops","functions"],"concept":"game loop","intro":"Você vai entender atualização, desenho e estados de um jogo.","why":"Um loop controlado é a base de gameplay fluido.","example":"function tick(time) {\n  update(dt);\n  draw();\n  requestAnimationFrame(tick);\n}","line":"requestAnimationFrame(tick)","experiment":"Pause o loop e observe a diferença.","exercise":"Defina MENU, PLAYING e GAME_OVER.","challenge":"Impeça dois loops de rodarem ao mesmo tempo.","common":["criar RAF duplicado","não limpar timers ao sair"],"extra":"Adicione PAUSED e STEP no debugger.","project":"Mini jogo com máquina de estados"},
 "async": {"track":"web","title":"Assíncrono sem perder o controle do fluxo","prereq":["functions","http-api"],"concept":"async/await","intro":"Você vai aprender a esperar resultados sem congelar a interface.","why":"Rede, arquivos e outras tarefas não terminam instantaneamente.","example":"async function load() {\n  const response = await fetch('/api/demo');\n  return await response.json();\n}","line":"await fetch('/api/demo')","experiment":"Adicione try/catch e mostre um erro amigável.","exercise":"Descreva os estados ENVIANDO, RESPONDENDO e ERRO.","challenge":"Cancele uma requisição usando AbortController.","common":["não tratar rejeições","criar requisições duplicadas"],"extra":"Adicione timeout e retry limitado.","project":"Painel de dados assíncrono"},
 "testing": {"track":"backend","title":"Testes que protegem mudanças","prereq":["functions","conditions"],"concept":"testes","intro":"Você vai transformar comportamento esperado em verificações repetíveis.","why":"Testes ajudam a detectar regressões antes de publicar.","example":"assert add(2, 3) == 5","line":"assert add(2, 3) == 5","experiment":"Troque o resultado esperado e veja o teste falhar.","exercise":"Crie três casos para uma função de desconto.","challenge":"Encontre qual caso quebra uma implementação com bug lógico.","common":["testar só o caminho feliz","testes dependentes entre si"],"extra":"Separe teste unitário de integração.","project":"Suíte de testes de uma API"},
 "architecture": {"track":"backend","title":"Arquitetura: separando responsabilidades","prereq":["http-api","testing"],"concept":"arquitetura","intro":"Você vai separar interface, regras, serviços e dados.","why":"Separação reduz acoplamento e facilita manutenção.","example":"UI → API → Service → Repository → Database","line":"Service → Repository","experiment":"Mova uma regra de negócio para o service.","exercise":"Classifique arquivos do projeto por responsabilidade.","challenge":"Desenhe o fluxo de login sem colocar regra de autorização no frontend.","common":["misturar UI e banco","confiar em esconder botão como autorização"],"extra":"Identifique um ponto de acoplamento e proponha uma interface.","project":"Arquitetura de um sistema de tarefas"},
}

DAILY = ["variables","conditions","loops","functions","http-api","joins","game-loop","async","testing","architecture"]

def now(): return datetime.now(timezone.utc).isoformat()
def uid(owner): return str(owner or 'owner')[:120]

def conn():
    c=platform_ultra.conn()
    c.execute('''CREATE TABLE IF NOT EXISTS learning8_progress(owner_uid TEXT PRIMARY KEY,xp INTEGER NOT NULL DEFAULT 0,completed_json TEXT NOT NULL DEFAULT '[]',mistakes_json TEXT NOT NULL DEFAULT '{}',mode TEXT NOT NULL DEFAULT 'coding',updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS learning8_events(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_uid TEXT NOT NULL,event TEXT NOT NULL,item TEXT,detail TEXT,created_at TEXT NOT NULL)''')
    return c

def progress(owner):
    with conn() as c:r=c.execute('SELECT * FROM learning8_progress WHERE owner_uid=?',(uid(owner),)).fetchone()
    if not r:
        with conn() as c:c.execute('INSERT OR IGNORE INTO learning8_progress(owner_uid,updated_at) VALUES(?,?)',(uid(owner),now()))
        return {'xp':0,'completed':[],'mistakes':{},'mode':'coding'}
    return {'xp':r['xp'],'completed':json.loads(r['completed_json'] or '[]'),'mistakes':json.loads(r['mistakes_json'] or '{}'),'mode':r['mode']}

def record(owner,item,correct=True,mode=None):
    p=progress(owner)
    if correct:
        p['xp']+=20
        if item in LESSONS and item not in p['completed']: p['completed'].append(item)
    else:
        p['mistakes'][item]=int(p['mistakes'].get(item,0))+1
    if mode: p['mode']=mode
    with conn() as c:c.execute('UPDATE learning8_progress SET xp=?,completed_json=?,mistakes_json=?,mode=?,updated_at=? WHERE owner_uid=?',(p['xp'],json.dumps(p['completed']),json.dumps(p['mistakes']),p['mode'],now(),uid(owner)))
    with conn() as c:c.execute('INSERT INTO learning8_events(owner_uid,event,item,detail,created_at) VALUES(?,?,?,?,?)',(uid(owner),'LESSON_PROGRESS',item,json.dumps({'correct':correct,'mode':mode}),now()))
    return p

def recommend(owner):
    p=progress(owner); done=set(p['completed'])
    candidates=[]
    for key,l in LESSONS.items():
        if key in done: continue
        if all(x in done for x in l['prereq']):
            candidates.append(key)
    if not candidates: candidates=[k for k in LESSONS if k not in done]
    candidates.sort(key=lambda k:(-p['mistakes'].get(k,0), len(LESSONS[k]['prereq'])))
    return candidates[0] if candidates else None

def lesson(owner,key):
    if key not in LESSONS: raise KeyError(key)
    l=dict(LESSONS[key]);p=progress(owner);l['id']=key;l['completed']=key in p['completed'];l['previous']=l['prereq'];l['next']=recommend(owner);l['levels']={
      'CRIANÇA':'Use uma analogia visual e experimente pequenas mudanças.',
      'INICIANTE':'Entenda a ideia, depois copie e modifique o exemplo.',
      'INTERMEDIÁRIO':'Compare alternativas e trate casos de erro.',
      'AVANÇADO':'Analise trade-offs, arquitetura, testes e performance.'}
    # Phase 9 rich sections (§3) — derived from existing fields without rewriting all lessons
    l['sections']={
      'simple': l.get('intro',''),
      'detailed': l.get('why',''),
      'example': l.get('example',''),
      'real_world': l.get('project',''),
      'code': l.get('example',''),
      'line_by_line': l.get('line',''),
      'exercise': l.get('exercise',''),
      'challenge': l.get('challenge',''),
      'common_errors': l.get('common',[]),
      'tips': l.get('extra',''),
      'experiment': l.get('experiment',''),
      'mini_project': l.get('project',''),
      'review': 'Revise: conceito, exemplo, exercício e erros comuns antes de avançar.',
    }
    l['explain_styles']=['analogia','exemplo_jogo','exemplo_visual','exemplo_tecnico','exemplo_cotidiano']
    l['mode_profiles']={
      'crianca': 'Conte como história ou missão de jogo. Personagens e recompensas.',
      'adolescente': 'Mostre aplicação web/Python e um mini projeto real.',
      'adulto': 'Foque em arquitetura, testes, edge cases e performance.',
    }
    return l

def overview(owner):
    p=progress(owner);rec=recommend(owner);day=DAILY[datetime.now(timezone.utc).timetuple().tm_yday%len(DAILY)]
    return {'tracks':TRACKS,'lessons':[{'id':k,'title':v['title'],'track':v['track'],'concept':v['concept'],'completed':k in p['completed'],'prereq':v['prereq']} for k,v in LESSONS.items()], 'progress':p,'recommended':lesson(owner,rec) if rec else None,'daily':lesson(owner,day),'modes':['🎮 APRENDER JOGANDO','📚 APRENDER COM AULAS','💻 APRENDER PROGRAMANDO','🧪 APRENDER EXPERIMENTANDO','🚀 APRENDER CRIANDO PROJETOS']}

def search(owner,q):
    q=str(q or '').strip().lower();p=progress(owner);out=[]
    for k,l in LESSONS.items():
        hay=' '.join([k,l['title'],l['concept'],l['intro'],l['why']]).lower()
        if q and q in hay: out.append({'id':k,'title':l['title'],'track':l['track'],'completed':k in p['completed']})
    return out[:30]
