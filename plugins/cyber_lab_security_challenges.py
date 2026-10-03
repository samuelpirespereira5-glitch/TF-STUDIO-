"""
JARVIS Cyber Security Lab Challenges
------------------------------------
Desafios educacionais para ambiente de laboratório autorizado.

Tudo é local e determinístico: este plugin NÃO faz conexões de rede,
não executa comandos do sistema, não escaneia alvos e não altera
arquivos externos. Ele apenas entrega cenários simulados e valida
respostas/decisões do participante.

Registrado automaticamente pelo Tool Registry existente.
"""
from copy import deepcopy

CHALLENGES = [
    {
        "id": "log-bruteforce",
        "title": "Análise de logs: tentativas de login",
        "category": "Análise de logs",
        "difficulty": "Fácil",
        "mission": "Identifique o padrão de tentativas de login e indique a ação defensiva.",
        "evidence": [
            "22:10 LOGIN user=admin src=10.10.10.50 result=FAIL",
            "22:10 LOGIN user=admin src=10.10.10.50 result=FAIL",
            "22:11 LOGIN user=admin src=10.10.10.50 result=FAIL",
            "22:11 LOGIN user=admin src=10.10.10.50 result=SUCCESS",
        ],
        "question": "Qual é a melhor primeira resposta defensiva?",
        "options": [
            "Ignorar porque houve um login bem-sucedido",
            "Investigar a origem, revisar o login bem-sucedido e aplicar controles como rate limit/bloqueio conforme a política",
            "Apagar os logs para evitar novos alertas",
            "Desligar todos os servidores",
        ],
        "answer": 1,
        "explanation": "O padrão mostra várias falhas seguidas de sucesso para a mesma conta e origem. Isso merece investigação e contenção controlada.",
        "identify": "Correlacione horário, conta, origem e resultado das autenticações.",
        "fix": "Reforce autenticação, rate limiting/bloqueio conforme a política, revise o acesso bem-sucedido e preserve os logs para investigação.",
    },
    {
        "id": "ssh-hardening",
        "title": "Configuração: hardening de SSH",
        "category": "Configuração",
        "difficulty": "Fácil",
        "mission": "Analise uma configuração simulada e escolha a correção.",
        "evidence": [
            "PasswordAuthentication yes",
            "PermitRootLogin yes",
            "MaxAuthTries 20",
        ],
        "question": "Qual conjunto representa um hardening inicial adequado em laboratório?",
        "options": [
            "Manter tudo igual e aumentar MaxAuthTries para 50",
            "Restringir login de root, preferir autenticação por chave quando possível e reduzir tentativas de autenticação",
            "Remover todos os logs de autenticação",
            "Publicar a senha do administrador em um arquivo de configuração",
        ],
        "answer": 1,
        "explanation": "A configuração simulada amplia a superfície de autenticação privilegiada e permite muitas tentativas.",
        "identify": "Procure opções que permitam login privilegiado direto e excesso de tentativas.",
        "fix": "Use uma política de acesso mínimo, autenticação forte e limites de tentativa adequados ao ambiente.",
    },
    {
        "id": "secret-code",
        "title": "Código: segredo exposto",
        "category": "Análise de código",
        "difficulty": "Fácil",
        "mission": "Encontre a falha em um trecho de código simulado.",
        "evidence": [
            'API_KEY = "LAB-DEMO-123456"',
            'client.configure(api_key=API_KEY)',
            "print('cliente iniciado')",
        ],
        "question": "O que deve ser corrigido primeiro?",
        "options": [
            "Mover o segredo para configuração segura/variável de ambiente e substituir o segredo exposto",
            "Adicionar mais comentários ao código",
            "Colocar o mesmo segredo em outro arquivo público",
            "Imprimir a chave no log para facilitar o diagnóstico",
        ],
        "answer": 0,
        "explanation": "Segredos não devem ficar hardcoded no código-fonte nem ser expostos em logs.",
        "identify": "Procure tokens, senhas e chaves literais no código e no histórico do projeto.",
        "fix": "Use armazenamento seguro/variáveis de ambiente, rotacione qualquer segredo real que tenha sido exposto e evite registrá-lo em logs.",
    },
    {
        "id": "sqli-simulated",
        "title": "Vulnerabilidade simulada: SQL Injection",
        "category": "Vulnerabilidade simulada",
        "difficulty": "Médio",
        "mission": "Reconheça uma construção insegura sem executar nenhum ataque.",
        "evidence": [
            'query = "SELECT * FROM users WHERE name = \'" + username + "\'"',
            "db.execute(query)",
        ],
        "question": "Qual correção elimina a causa principal?",
        "options": [
            "Usar consultas parametrizadas/prepared statements",
            "Bloquear a palavra SELECT no navegador",
            "Ocultar a mensagem de erro no HTML",
            "Aumentar o tamanho máximo do campo username",
        ],
        "answer": 0,
        "explanation": "A consulta é construída concatenando entrada do usuário. O problema está na composição da query, não no tamanho do campo.",
        "identify": "Procure concatenação de entrada não confiável diretamente na consulta.",
        "fix": "Use parâmetros da biblioteca de banco, valide entradas conforme a regra de negócio e mantenha privilégios mínimos no usuário do banco.",
    },
    {
        "id": "xss-simulated",
        "title": "Vulnerabilidade simulada: XSS",
        "category": "Vulnerabilidade simulada",
        "difficulty": "Médio",
        "mission": "Identifique uma saída HTML insegura.",
        "evidence": [
            'const msg = new URLSearchParams(location.search).get("msg");',
            'document.getElementById("saida").innerHTML = msg;',
        ],
        "question": "Qual mudança reduz diretamente o risco nesse ponto?",
        "options": [
            "Usar textContent para texto simples em vez de inserir HTML não confiável",
            "Colocar a URL em letras maiúsculas",
            "Aumentar o limite da query string",
            "Adicionar um atraso de 1 segundo antes da renderização",
        ],
        "answer": 0,
        "explanation": "Entrada controlada pelo usuário está sendo tratada como HTML.",
        "identify": "Localize dados externos que chegam a sinks de HTML/DOM sem tratamento apropriado.",
        "fix": "Prefira APIs de texto quando HTML não é necessário e aplique sanitização contextual quando HTML realmente precisar ser permitido.",
    },
    {
        "id": "api-error",
        "title": "Diagnóstico: API simulada indisponível",
        "category": "Diagnóstico",
        "difficulty": "Médio",
        "mission": "Analise uma falha de serviço sem chamar uma API real.",
        "evidence": [
            "GET /api/profile -> 503 Service Unavailable",
            "frontend: 'Unexpected token < in JSON'",
            "backend log: upstream unavailable",
        ],
        "question": "Qual sequência é mais apropriada?",
        "options": [
            "Investigar o status do upstream, tratar respostas de erro no cliente e preservar detalhes úteis no log do servidor",
            "Tentar requisições infinitamente no navegador",
            "Ignorar o 503 e assumir que os dados chegaram",
            "Mostrar credenciais do servidor para o usuário",
        ],
        "answer": 0,
        "explanation": "Há uma falha upstream e o cliente também parece esperar JSON quando recebeu outra resposta.",
        "identify": "Separe a causa do 503 do erro secundário de parsing no frontend.",
        "fix": "Corrija/recupere o upstream, valide status/content-type antes de fazer parse e mantenha mensagens seguras para o usuário.",
    },
    {
        "id": "file-integrity",
        "title": "Forense defensiva: arquivo alterado",
        "category": "Análise / Forense",
        "difficulty": "Médio",
        "mission": "Compare evidências de integridade em um laboratório simulado.",
        "evidence": [
            "baseline SHA-256: AAAA...1111",
            "arquivo atual SHA-256: BBBB...2222",
            "alteração detectada fora da janela de manutenção",
        ],
        "question": "Qual é o próximo passo defensivo?",
        "options": [
            "Preservar evidências, registrar o evento e investigar a origem da alteração antes de restaurar",
            "Sobrescrever imediatamente todas as evidências",
            "Apagar o arquivo sem registrar nada",
            "Publicar o hash em qualquer site público",
        ],
        "answer": 0,
        "explanation": "A divergência fora da janela prevista é um indicador que precisa ser preservado e investigado.",
        "identify": "Compare hashes, horário da alteração e atividade administrativa conhecida.",
        "fix": "Preserve evidências, determine a causa, restaure a partir de uma fonte confiável e reforce controles de integridade/acesso.",
    },
    {
        "id": "incident-response",
        "title": "Mini incidente: resposta defensiva",
        "category": "Resposta a incidentes",
        "difficulty": "Difícil",
        "mission": "Escolha uma sequência de contenção e investigação em um laboratório.",
        "evidence": [
            "alerta: processo desconhecido em host de teste",
            "conexão externa simulada registrada",
            "usuário afetado: lab-user",
        ],
        "question": "Qual sequência é mais segura para o laboratório?",
        "options": [
            "Preservar evidências, isolar o host de teste, investigar indicadores e só depois remediar",
            "Apagar todos os logs e reiniciar sem registrar",
            "Executar comandos desconhecidos no host para descobrir o que fazem",
            "Ignorar o alerta porque é um laboratório",
        ],
        "answer": 0,
        "explanation": "Resposta a incidentes deve preservar evidências e limitar o impacto antes da erradicação.",
        "identify": "Correlacione alerta, processo, usuário e eventos registrados.",
        "fix": "Isole o ativo de laboratório, preserve evidências, determine a causa, remova a causa e valide a recuperação.",
    },
]


def _public_challenge(c):
    return {
        k: deepcopy(c[k])
        for k in ("id", "title", "category", "difficulty", "mission",
                  "evidence", "question", "options")
    }


def list_challenges():
    return [_public_challenge(c) for c in CHALLENGES]


def get_challenge(challenge_id):
    return next((c for c in CHALLENGES if c["id"] == challenge_id), None)


def solve_challenge(challenge_id, option):
    c = get_challenge(challenge_id)
    if not c:
        return {"ok": False, "error": "Desafio não encontrado."}
    try:
        selected = int(option)
    except (TypeError, ValueError):
        return {"ok": False, "error": "A opção deve ser um número."}
    if selected < 0 or selected >= len(c["options"]):
        return {"ok": False, "error": "Opção inválida."}
    passed = selected == c["answer"]
    return {
        "ok": True,
        "passed": passed,
        "challenge_id": c["id"],
        "selected": selected,
        "correct_option": c["answer"] if passed else None,
        "explanation": c["explanation"],
        "identify": c["identify"],
        "fix": c["fix"],
        "summary": "Desafio concluído corretamente." if passed else "Resposta incorreta. Revise a evidência e tente novamente.",
    }


def register(registry):
    registry.register(
        id="cyber_lab_challenges",
        name="Cyber Security Lab — Desafios",
        category="training",
        description=(
            "Desafios defensivos e de diagnóstico em ambiente simulado e autorizado. "
            "Não executa ataques, comandos, conexões ou scans externos."
        ),
        cap="cyber",
        params={
            "action": {
                "required": True,
                "description": "list | solve"
            },
            "challenge_id": {
                "required": False,
                "description": "ID do desafio quando action=solve"
            },
            "option": {
                "required": False,
                "description": "Índice da opção quando action=solve"
            },
        },
        handler=lambda p, ctx: (
            {"summary": "Desafios disponíveis.", "challenges": list_challenges()}
            if p.get("action") == "list"
            else solve_challenge(p.get("challenge_id"), p.get("option"))
            if p.get("action") == "solve"
            else {"summary": "Use action=list ou action=solve."}
        ),
        keywords=[
            "desafios cyber", "cyber lab", "laboratório", "treinamento",
            "análise de logs", "defesa", "hardening", "vulnerabilidade simulada",
            "sql injection simulada", "xss simulada", "resposta a incidentes",
        ],
    )
