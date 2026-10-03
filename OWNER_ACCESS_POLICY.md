# OWNER ACCESS — TRISTAN THORNE

## Regra
As funções avançadas do Tristan Thorne são autorizadas no backend pelo papel `owner`.
Esconder controles no frontend não é usado como mecanismo de segurança.

## Owner-only
- Cyber Lab e ferramentas Cyber
- Security Center / Security Scan completo
- vulnerabilidades, evidências e relatórios completos
- ferramentas avançadas e diagnósticos
- modo Desenvolvedor/Admin do JARVIS
- criação/edição de desafios e acesso às soluções
- logs administrativos e configurações de segurança
- execução de ferramentas com escopo de laboratório
- administração de chaves/papéis

## Admin
O papel `admin` continua existindo para compatibilidade, mas não recebe capacidades de proprietário. Ele fica limitado a `chat`, ferramentas básicas e Creator.

## User / Guest
Continuam sujeitos às permissões já existentes e não recebem capacidades Cyber avançadas.

## Proteções
- autorização validada no backend
- rotas e APIs protegidas por capacidade
- tentativas negadas registradas em `auth.json` no `access_log`
- tentativas anônimas contra áreas protegidas também são registradas
- instâncias de desafios são protegidas mesmo quando a URL é acessada diretamente
- chaves de papel nunca armazenam o segredo em texto puro
- não existe senha/chave fixa adicionada ao código
