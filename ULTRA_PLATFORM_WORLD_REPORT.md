# JARVIS ULTRA PLATFORM — World / Experience Layer

## Escopo
Implementação incremental sobre o projeto existente, sem reescrita da arquitetura Flask/Jinja/JavaScript/CSS.

## Sistemas novos
- JARVIS World / hub de navegação modular.
- Learning Path com seis níveis e progresso persistido.
- Skill Tree com pré-requisitos e progresso.
- Project Journey: IDEIA → PLANEJAMENTO → CONSTRUÇÃO → TESTE → CORREÇÃO → VERSÃO FINAL.
- Idea Lab e Project Generator com estruturas iniciais seguras.
- Project Center, Portfolio e Project Review.
- Learning Analytics baseado em dados persistidos; sem números inventados.
- Universal Command Center e Search Everything.
- Smart Onboarding.
- JARVIS Guide / ajuda contextual.
- HTML/CSS Playground com preview sandbox.
- JavaScript Playground em Web Worker com bloqueio explícito de APIs de rede/armazenamento.
- Python Learning Lab educativo por análise local; não executa Python no servidor.
- Algorithm Lab / Bubble Sort visual e Pathfinding Lab.
- Experiment Lab e Science Lab com simulações locais.
- Robot Lab / Robot Maze com comandos locais.
- HTTP Visualizer, API Lab e Internet Simulator totalmente simulados.
- Cyber Defense Simulator, Digital Forensics Puzzle e Security Escape Room fictícios.
- Creative Lab: Story, RPG, World, Level, NPC, Quest e Chatbot Builder.
- Game Jam e Creator Challenges.
- Daily Challenge.
- System Observatory reutilizando estados dos serviços existentes.
- Project Memory Board apenas com metadados apropriados.
- Map Explorer apontando para o sistema de mapas existente.
- Virtual Museum.
- Safe Kids Mode informativo, separado de capacidades administrativas.
- PWA básica: manifest + service worker para recursos apropriados.

## Segurança
- Todas as novas APIs ficam sob `/api/cyber` e herdam o controle de capacidade existente.
- Não foram adicionadas rotas de administração, leitura de segredos ou acesso direto a banco administrativo.
- Código educacional não é executado no servidor.
- JavaScript educacional é executado no navegador em Worker e bloqueia APIs de rede/armazenamento no playground.
- Preview HTML/CSS usa iframe sandbox.
- Simuladores de rede e Cyber Defense não fazem chamadas a alvos externos.
- Nenhuma senha, token, API key ou secret é renderizado.
- Projetos ficam privados por padrão; publicação exige ação explícita.

## Performance
- O World carrega uma única interface e chama APIs sob demanda.
- Simulações são ativadas somente quando abertas.
- Não há carregamento automático de todos os jogos, mapas ou módulos pesados.
- PWA cacheia somente recursos estáticos apropriados; `/api/` não é cacheado.

## Validação executada
- `python scripts/final_expansion_check.py`: PASS — 88 Python files, 265 routes, 0 duplicate routes, 0 errors.
- Jinja parse: PASS.
- `node --check static/js/jarvis-world.js`: PASS.
- `python -m compileall -q .`: PASS.

## Não executado neste ambiente
- Browser/Chrome real em Android.
- Fluxo HTTP real completo do Flask em runtime.
- Teste real de WebAuthn.
- Testes de provedores externos de mapas.

Esses itens não são declarados como PASS.
