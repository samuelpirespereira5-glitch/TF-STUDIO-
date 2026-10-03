# JARVIS Game Studio 10 MAX — Nível mais avançado

Implementação das features da lista do Claude (screenshots).

## Jogos
- **Marketplace** — usuários listam/vendem jogos com XP (`/api/nl10/marketplace`)
- **Modo torneio** — chaveamento automático eliminação simples (`/api/nl10/tournament`)
- **Sistema de replay** — grava frames/inputs e reassiste (`/api/nl10/replay`)
- **Templates de física** — platformer, top-down, racing, puzzle blocks (`/api/nl10/physics`)

## Programação
- **Code review por IA** — gera prompt estruturado de revisão (não só certo/errado)
- **Desafios de performance** — otimize código (soma, duplicata, concat)
- **Pair programming com IA** — sugere próximo passo sem entregar resposta pronta
- **Snippet → Debugger** — payload pronto para abrir no debugger visual do Nível 9

## Gamificação
- **Clãs/times** — criar, entrar, ranking por XP do clã
- **Conquistas secretas** — easter eggs ocultos até descoberta
- **Loja temporária rotativa** — 3 itens especiais por semana (determinístico)

## Certificados
- **Verificável por empresa** — token público em `/api/nl10/cert/verify/<token>`
- **Selos bronze/prata/ouro** — conforme score (≥60/75/90), não só conclusão

## Estudos
- **Busca unificada** — PDFs, vídeos, exercícios e fórum no mesmo índice
- **Modo offline** — gera pack da trilha para estudar sem internet
- **Resumo semanal** — texto pronto para e-mail/notificação

## Comunidade
- **Sistema de mentoria** — pedidos + matching mentor/iniciante
- **Feed de atividades** — estilo rede social ("Fulano completou a trilha X")
- **Badges de contribuição** — Ajudante / Mentor Ativo / Lenda do Fórum

## Qualidade / Infra
- **Página de status** — `/status` e `/api/nl10/status`
- **Log de erros centralizado** — `/api/nl10/errors`
- **Smoke tests (CI simples)** — `POST /api/nl10/smoke-tests`

## UI
- Hub: **`/proximo-nivel-10`** (ou `/next-level10`)
- Link no menu lateral: 🚀 Próximo Nível 10

## Arquivos novos
- `services/next_level10.py`
- `templates/next_level10.html`
- rotas em `app.py`
- dados em `data/next_level10/`
- `NEXT_LEVEL_10_REPORT.md`

Não reescreveu módulos existentes; apenas estendeu (padrão do Nível 9).
