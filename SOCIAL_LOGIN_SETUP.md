# JARVIS — login por Google/GitHub sem tokens por usuário

A senha mestre continua existindo e continua sendo o acesso do proprietário.
Para usuários comuns, o projeto agora suporta login federado opcional:

- Google (OpenID Connect)
- GitHub OAuth
- Passkey continua disponível para o fluxo já existente

## Por que isso resolve o problema

Você não precisa criar e entregar um token manual para cada pessoa. Cada pessoa
entra pela própria conta Google/GitHub e o JARVIS cria uma identidade local
`provider:id` e uma sessão normal. O projeto não guarda a senha do Google/GitHub
e não persiste os access tokens desses provedores.

## Variáveis no Render

Google:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI=https://SEU-DOMINIO/auth/google/callback`

GitHub:

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `GITHUB_REDIRECT_URI=https://SEU-DOMINIO/auth/github/callback`

Cadastre exatamente as URLs de callback no respectivo painel do provedor.

## Segurança

- state OAuth aleatório + validade de 10 minutos
- sessão criada no backend depois do callback
- role do login social é `user`, nunca `owner`
- senha mestre não é substituída
- segredos ficam somente em variáveis de ambiente
- access tokens dos provedores não são persistidos
- mudança normal de User-Agent do celular/navegador não derruba a sessão por padrão
- para ambiente extremamente restrito, `STRICT_SESSION_UA_BIND=1` reativa o bloqueio estrito
- sessão padrão de produção: até 30 dias, com inatividade configurada para 30 dias

## Importante

Não coloque `GOOGLE_CLIENT_SECRET` ou `GITHUB_CLIENT_SECRET` no HTML,
JavaScript, Git ou arquivos públicos.
