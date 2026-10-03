# JARVIS Experience + Auth + Performance + Game Lab 6.0

## Escopo
Esta fase foi aplicada incrementalmente sobre o projeto existente. Não foi criado um segundo sistema de login, segundo RBAC ou segundo Game Lab.

## Autenticação / UX
- Sessões autenticadas continuam válidas para navegação normal.
- Foi criado `services/experience6.py` com estado de confiança da sessão.
- Step-up é explícito e limitado a ações importantes/críticas.
- O endpoint de step-up exige a credencial mestre no backend e concede uma janela curta vinculada à ação.
- Navegação normal, jogos, estudos, projetos e consultas não receberam step-up global.
- O RBAC existente continua sendo a fonte de autorização.

## Performance
- Foi adicionado monitoramento bounded em memória das requisições da instância.
- Desenvolvedores autorizados podem consultar `/api/jarvis/experience6/performance`.
- O painel de desenvolvedor mostra média, requisições lentas e críticas e amostras recentes.
- O monitor não guarda corpo de requisição, cookies, tokens ou segredos.

## Game Lab
Foram corrigidos problemas concretos sem trocar o engine:
- timers temporários do jogo agora entram em uma lista de cleanup;
- sair/reiniciar limpa timers, RAF e input;
- movimento do Maze teve a expressão condicional corrigida;
- comida do Snake não nasce sobre o próprio corpo;
- loops de jogo continuam com um único `requestAnimationFrame` ativo;
- o estado do jogo continua MENU/PLAYING/PAUSED/GAME_OVER/VICTORY;
- Physics Lab não mantém RAF ativo quando a aba do laboratório está oculta;
- desafios ganharam contexto, conceito, missão, dicas e desafio extra sob demanda.

## JARVIS / educação
- catálogo de modos: GENERAL, CODER, TEACHER, GAME DEV, PROJECT, DEBUG, SECURITY e CREATOR;
- endpoint educativo de detalhes de desafios;
- integração com a UI existente do Game Lab para explicar o desafio antes da resposta.

## JARVIS World / performance de experiências
- animações de Algorithm Lab e Experiment Lab agora cancelam o RAF anterior antes de iniciar outro;
- trocar de área não acumula loops de Canvas desses módulos.

## Segurança
- nenhum segredo foi colocado no frontend;
- o código educacional continua sendo executado apenas no cliente/sandbox quando permitido;
- step-up é validado no backend;
- não foram adicionadas capacidades para atacar terceiros, roubar credenciais, malware, persistência ou evasão.

## Validação executada
- Python `compileall`: PASS
- `scripts/final_expansion_check.py`: PASS — 91 arquivos Python, 292 rotas, 0 duplicações, 0 erros estruturais
- `node --check` em JavaScript: PASS
- parse de todos os templates Jinja: PASS
- assertions estáticas da Fase 6: PASS

## Validação não executada
O ambiente de build não possui Flask/Werkzeug instalados. Portanto não foi possível executar o servidor Flask, testes HTTP reais, WebAuthn físico, Chrome/Android ou console real de jogos. Esses itens não são declarados como PASS.
