# JARVIS Community Space — atualização

## O que mudou

### Autenticação / sessão
- A sessão de produção deixou de usar 4 horas + 30 minutos de inatividade como padrão.
- Novo padrão: até 30 dias de sessão e 7 dias de inatividade.
- Os valores continuam configuráveis por `SESSION_HOURS` e `SESSION_IDLE_MINUTES`.
- A senha mestre continua sendo usada no login e ações críticas continuam podendo exigir step-up/reautenticação.

### Primeiro acesso
Depois do login, quem ainda não possui perfil recebe uma etapa única:
- nome de exibição;
- nome de usuário;
- bio;
- avatar;
- interesses;
- criação do personagem.

XP/gamificação/personagem não altera RBAC, admin ou permissões.

### Comunidade separada
Nova área `/comunidade` para:
- feed;
- perfil;
- estatísticas;
- minhas comunidades;
- meus clãs;
- publicações e curtidas.

### Comunidades & Clãs
Nova área `/comunidade/espacos` com criação separada de:
- comunidade pública/privada;
- clã público/privado;
- tags;
- descrição;
- canais básicos;
- entrada/saída;
- descoberta/pesquisa;
- convites para espaços privados;
- publicações por espaço.

### Arquivos novos
- `services/community_space.py`
- `templates/community_onboarding.html`
- `templates/community_spaces.html`
- `static/css/community-space.css`
- `static/js/community-space.js`

### Arquivos alterados
- `app.py`
- `services/auth.py`
- `render.yaml`
- `templates/base.html`
- `templates/comunidade_hub.html`

## Observação
A autenticação existente não foi substituída por outro sistema. A nova conta/perfil é uma camada de identidade dentro do JARVIS ligada à sessão autenticada existente.
