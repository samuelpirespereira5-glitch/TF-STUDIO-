# JARVIS Game Studio 9 MAX — Próximo Nível

Implementação das features sugeridas (lista do Claude).

## Jogos
- **Multiplayer local** — `POST /api/nl9/multiplayer` adiciona flag + mapeamento WASD / Setas
- **Editor de níveis** — CRUD em grid (`/api/nl9/levels`) separado do sprite editor
- **Remix** — `POST /api/nl9/remix` clona jogo de outro usuário
- **PWA export** — manifest + HTML instalável (`/api/nl9/pwa`)

## Programação
- **Debugger visual** — passo a passo com variáveis (`/api/nl9/debugger/*`)
- **Playground colaborativo** — salas com polling (`/api/nl9/collab`)
- **Git simplificado** — salvar/listar/restaurar versões (`/api/nl9/versions`)
- **Snippets** — biblioteca pronta + custom (`/api/nl9/snippets`)

## Gamificação
- **Loja cosmética** — avatares, molduras, títulos por pontos/XP
- **Eventos sazonais** — desafio da semana auto-gerado
- **Streak** — dias seguidos (estilo Duolingo)

## Certificados
- **PDF/HTML + QR** — `POST /api/nl9/cert/issue` + download HTML com QR de verificação pública

## Estudos
- **Explicar de novo** — conta erros e gera prompt/IA
- **Biblioteca de PDFs/apostilas** por assunto
- **Fórum/mural** de dúvidas com respostas

## Comunidade
- **Perfil público** (jogos, certificados, cosméticos, streak)
- **Curtidas e comentários** na galeria de jogos

## UI
- Hub completo: **`/proximo-nivel`** (ou `/next-level9`)
- Link no menu lateral: 🚀 Próximo Nível 9

## Arquivos novos
- `services/next_level9.py`
- `templates/next_level9.html`
- rotas em `app.py`
- dados em `data/next_level9/`

Não reescreveu módulos existentes; apenas estendeu.
