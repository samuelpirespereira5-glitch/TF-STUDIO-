# JARVIS Game Studio 11 — Nível Ambicioso

Implementação das features da lista do Claude (screenshots 1000092038 / 2039 / 2040).

## Jogos
- **Editor de IA** — gera jogo inteiro a partir de descrição em texto (`POST /api/nl11/ai-game`)
- **Co-op online** — salas com WebSocket hint (`/api/nl11/coop`, join por room id)
- **Sistema de mods** — usuários publicam add-ons (`/api/nl11/mods`)
- **Ranking global cross-jogos** — pontuação agregada do estúdio (`/api/nl11/global-rank`)

## Programação
- **Projeto do mês** — desafio em equipe com prazo tipo hackathon (`/api/nl11/month-project`)
- **Linter/formatter** — boas práticas em tempo real (heurístico Python) (`POST /api/nl11/lint`)
- **Entrevista técnica simulada** — junior/pleno/senior com feedback (`/api/nl11/interview`)
- **Visualização de algoritmos** — bubble, selection, binary search passo a passo (`POST /api/nl11/algo-viz`)

## Gamificação
- **Temporadas (season pass)** — ranking reseta ~90 dias, recompensas exclusivas (`/api/nl11/season`)
- **Missões diárias/semanais variadas** — não só streak (`/api/nl11/missions`)
- **Apostas de XP entre clãs** em torneios (`/api/nl11/clan-bet`)

## Certificados
- **Competências específicas listadas** (não só “concluiu o curso”)
- **Integração LinkedIn** — payload de share + botão “adicionar certificado” (`/api/nl11/cert/issue`)

## Estudos
- **Tutor por IA** — plano personalizado baseado no que o usuário já sabe (`POST /api/nl11/study-plan`)
- **Simulados cronometrados** com correção automática (`/api/nl11/simulado`)
- **Modo “ensine para aprender”** — gravação + avaliação da comunidade (`/api/nl11/teach`)

## Comunidade
- **Eventos ao vivo** — chat/vídeo/workshop em horário marcado (`/api/nl11/events`)
- **Sistema de reputação** — níveis Novo / Ativo / Confiável / Lenda (`/api/nl11/reputation`)
- **Portfólio público** — link único `/portfolio/<slug>` (`/api/nl11/portfolio`)

## Infra / qualidade
- **Backup export/import** de conta (`/api/nl11/backup/export|import`)
- **Dark mode / temas** personalizáveis (`/api/nl11/theme`)
- **Painel analytics** admin (`/api/nl11/analytics`)
- **Internacionalização PT/EN** (`/api/nl11/i18n`)

## Mobile
- **PWA + push** — registro de subscription para lembretes de streak/missão (`/api/nl11/push`)

## UI
- Hub: **`/proximo-nivel-11`** (ou `/next-level11`)
- Link no menu lateral: 🚀 Próximo Nível 11

## Arquivos novos
- `services/next_level11.py`
- `templates/next_level11.html`
- rotas em `app.py`
- dados em `data/next_level11/`
- `NEXT_LEVEL_11_REPORT.md`

Não reescreveu módulos existentes; apenas estendeu (padrão dos Níveis 9 e 10).
