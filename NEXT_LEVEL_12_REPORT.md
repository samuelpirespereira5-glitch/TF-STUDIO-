# JARVIS Game Studio 12 — Polimento + Novas Áreas

Implementação das features da lista do Claude (screenshots de acessibilidade, admin, sustentabilidade, integrações, insights, conteúdo, ferramentas, engajamento, “uau”, visual, inteligência real + checklist de polimento).

## Acessibilidade
- Preferências TTS (texto para fala) — `/api/nl12/a11y`, `/api/nl12/tts`
- Alto contraste + escala de fonte ajustável
- Mapa de atalhos de teclado completos (navegar sem mouse)

## Controle / Admin
- Modo **sala de aula**: criar turma, alunos, atribuir exercícios, relatório da turma
- Painel pais/professores (vínculo de contas + progresso)
- Moderação de conteúdo com fila de revisão (approve / remove / warn)

## Sustentabilidade
- Planos **free × premium** com limites e features
- Programa de parceria com escolas/cursos (solicitação + listagem)

## Integrações externas
- API key pública documentada (Bearer) — docs embutidas na resposta
- Login social stub (Google, GitHub)
- Export de progresso/certificado como **JSON aberto** (`jarvis-game-studio-progress/v1`)

## Dados e insights
- Relatório mensal pessoal (“seu mês em números”: horas, jogos, XP, exercícios)
- Série de evolução (XP acumulado / horas) para gráfico

## Conteúdo extra
- Banco de perguntas de múltipla escolha geradas a partir de texto/PDF
- Trilhas por interesse (“jogos de terror”, “site de loja”, “Python + jogo”, “cyber web”)
- Digest de notícias de tecnologia resumidas (cache diário)

## Ferramentas do dia a dia
- Gerador de paleta de cores + ícones sugeridos
- Conversor de formatos imagem/áudio (job stub → ffmpeg/Pillow em produção)
- Templates de currículo/portfólio (dev júnior, criador de jogos, analista cyber)

## Engajamento extra
- Recompensas surpresa aleatórias ao completar tarefas
- Convite de amigos com bônus de XP para os dois

## “Uau” de verdade
- Assistente **Jarvis** único: intenção → roteiro (trilha + projeto + certificado)
- Onboarding cinematográfico (cenas, não tutorial de texto)
- Modo **um clique**: ideia → jogo publicado (fluxo simulado < 2 min)

## Identidade visual
- Tema sci-fi/holograma consistente (`jarvis-hologram`)
- Mascote Jarvis com dicas contextuais
- Toggle de sons de interface

## Inteligência real
- Registro de padrão de uso (horário / ações) e sugestão do próximo passo
- Detecção de frustração: 3 erros no mesmo exercício → ajuda proativa

## Polimento (antes do Nível 13+)
- Checklist persistente: unificar navegação, deduplicar funções, testar fluxo do zero, performance, a11y, visual, API docs
- Hub: **`/proximo-nivel-12`** ou **`/next-level12`**
- Link no menu lateral: ✨ Próximo Nível 12

## Arquivos novos / alterados
- `services/next_level12.py`
- `templates/next_level12.html`
- rotas em `app.py`
- link em `templates/base.html`
- dados em `data/next_level12/`
- `NEXT_LEVEL_12_REPORT.md`

Não reescreveu módulos existentes; apenas estendeu (padrão dos Níveis 9–11).
