# V30.1 — JARVIS / Cyber Lab UI + Audit Update

## Preservado
- Rotas e APIs existentes
- Autenticação e permissões
- Scope/SSRF Guard e autorização de alvos
- Evidence Center, histórico e comparação de scans
- Registry e handlers reais do Cyber Lab
- Integrações de IA e ferramentas existentes

## Alterações
- Sidebar ocupa a altura total, com navegação agrupada, scroll interno e status JARVIS.
- Workspace deixa de ficar limitado a 1100px, removendo a grande área vazia em telas largas.
- Melhor contraste/foco de inputs, botões, cards e chat.
- Cyber Hub usa o registry real do JARVIS como catálogo principal e mantém o catálogo externo como referência.
- Cyber Lab ganhou barra de execução centralizada com alvo autorizado, modo SAFE/READ-ONLY, progresso e cancelamento da requisição pelo cliente.
- Relatórios de auditoria agora aceitam Markdown, JSON e HTML; HTML/JSON/Markdown podem ser baixados pela interface.
- Mantido o bloqueio de escopo no backend: a interface não substitui as verificações de autorização.
- Nenhum recurso de roubo de credenciais, malware operacional, persistência, evasão, destruição ou exfiltração foi adicionado.

## Validação
- Todos os 63 arquivos Python compilam sem erro de sintaxe.
- `static/js/cyber.js` passa no `node --check`.
- A suíte pytest completa não pôde ser executada neste ambiente porque as dependências Flask/Werkzeug não estão instaladas no runtime de validação.
