# JARVIS Game Studio 16 — Social Auth + Session UX

## Entregue
- Login opcional com Google e GitHub para usuários comuns.
- Senha mestre preservada para o proprietário.
- Nenhum token manual por usuário é necessário quando OAuth está configurado.
- Contas sociais recebem identidade server-side estável e onboarding existente.
- OAuth usa `state` e callback HTTPS configurável.
- Tokens de acesso de provedores não são persistidos.
- Sessão deixa de expulsar automaticamente por simples mudança de User-Agent, salvo `STRICT_SESSION_UA_BIND=1`.
- Timeout de inatividade de produção aumentado para 30 dias; limite absoluto continua 30 dias por sessão.
- Documentação de configuração em `SOCIAL_LOGIN_SETUP.md`.
