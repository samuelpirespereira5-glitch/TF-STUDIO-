# Política de Segurança e Uso Autorizado

## Segurança e uso autorizado

Nossa plataforma inclui recursos de segurança para ajudar desenvolvedores
a identificar, corrigir e prevenir vulnerabilidades em sites criados,
hospedados ou explicitamente autorizados dentro da plataforma.

As análises são permitidas apenas em:
- Ambientes de preview criados pela própria plataforma;
- Projetos pertencentes à organização do usuário;
- Domínios vinculados ao projeto e verificados por DNS TXT, arquivo
  `/.well-known` ou meta tag;
- Ambientes de staging ou produção para os quais exista autorização comprovada.

É estritamente proibido usar a plataforma para testar, atacar, coletar dados,
explorar falhas ou acessar sistemas que não pertençam ao usuário ou para os
quais ele não tenha autorização expressa.

A plataforma **não fornece, não executa e não permite** recursos voltados a
ataque ou intrusão contra terceiros, incluindo:

- Scanners de SQL Injection (SQLi), Cross-Site Scripting (XSS) ou
  Server-Side Request Forgery (SSRF) contra alvos não autorizados;
- Geração, distribuição ou uso de payloads ofensivos;
- Payload factory, reverse shells, web shells ou execução remota de comandos;
- Cracking, quebra ou tentativa de recuperação de hashes, senhas, tokens,
  chaves privadas ou credenciais;
- Bypass, evasão ou tentativa de contornar autenticação, JWT, CORS, IDOR,
  controles de acesso, rate limit, WAF, CAPTCHA ou mecanismos de segurança;
- OSINT, busca, coleta, indexação ou divulgação de leaks, secrets,
  credenciais ou dados de terceiros;
- Enumeração de usuários, portas, subdomínios, serviços, APIs ou recursos
  de sistemas sem autorização;
- Qualquer atividade que viole leis, contratos, políticas de provedores ou
  direitos de terceiros.

A plataforma pode executar somente **verificações defensivas e controladas**,
como auditoria de dependências, detecção de segredos em repositórios
conectados pelo proprietário, análise de headers HTTP, HTTPS, cookies, CSP,
CORS, configurações de produção, validação de autenticação e testes de
autorização usando contas de teste do mesmo projeto.

Para proteção contra abuso, todas as análises exigem autenticação, validação
de escopo, verificação de propriedade do domínio quando aplicável, limites
de uso e registro de auditoria. Violações podem resultar em bloqueio
imediato da conta, preservação de registros e comunicação às autoridades
competentes quando necessário.

## Uso permitido

As ferramentas de segurança desta plataforma são destinadas exclusivamente
a sites, aplicações, repositórios, domínios e ambientes que pertençam ao
usuário ou tenham autorização explícita para teste.

Não permitimos scanners SQLi/XSS/SSRF contra terceiros, payload factory,
reverse shells, cracking de hashes, bypass de JWT/CORS/IDOR, coleta de
leaks/secrets, enumeração ou qualquer tentativa de ataque, evasão ou acesso
não autorizado.

Nossas verificações são defensivas e incluem análise de dependências,
segredos em repositórios autorizados, headers, HTTPS, cookies, CSP, CORS,
autenticação, autorização e configurações de produção.

## Tela de confirmação (antes de cada análise)

> Ao iniciar esta análise, você confirma que possui o sistema, domínio,
> repositório ou ambiente selecionado, ou que recebeu autorização expressa
> do proprietário para testá-lo.
>
> É proibido utilizar esta plataforma para executar scanners SQLi/XSS/SSRF,
> gerar payloads, reverse shells, cracking de hashes, bypass de
> JWT/CORS/IDOR, OSINT de leaks/secrets ou qualquer atividade contra
> terceiros sem autorização.
>
> Todos os testes são registrados em logs de auditoria e limitados ao
> escopo verificado do projeto.

## Restrito a desenvolvedores (owner/admin)

Este documento e o Cyber Lab que ele descreve **não são destinados ao
usuário final** — são ferramentas de desenvolvedor. No backend isso já é
validado, não só escondido na interface:

- `services/permissions.py`: as capabilities `cyber`, `cyber_targets` e
  `cyber_advanced` só existem nos papéis `owner` e `admin` (parcial); os
  papéis `user` e `guest` não têm essas capabilities de forma alguma.
- `enforce_path()` intercepta *todo* prefixo `/api/cyber`, `/cyber` e
  `/api/security` **antes** de qualquer rota rodar — um `user`/`guest`
  recebe 403 mesmo se adivinhar a URL direto, sem depender do frontend
  esconder o menu.
- O papel `owner` exige `MASTER_PASSWORD`; `admin` é criado por convite do
  owner (`services/auth.create_role_key`). Não há caminho de auto-promoção.

Se o painel de desenvolvedores tiver uma tela própria (fora do Cyber Lab
atual), ela deve repetir a mesma regra: gate por `require_cap("cyber")` ou
equivalente no backend, nunca só por `if role === 'admin'` no JS.

## Onde isto já está aplicado no código

- **`services/scope.py`** — `check_host` / `check_url` / `check_name_only`
  bloqueiam qualquer alvo que não esteja na lista de autorizados
  (`data/authorized_targets.json`), bloqueiam SEMPRE faixas de metadata de
  nuvem/link-local/multicast, e exigem autorização explícita do IP quando um
  nome resolve para rede interna.
- **`services/scope.add_target`** — exige `confirm_ownership=True`
  (checkbox de "confirmo que este alvo é meu ou tenho autorização") antes
  de aceitar qualquer alvo novo; é a tela de confirmação descrita acima.
- **`services/permissions.py`** — RBAC: todo o Cyber Lab avançado exige a
  capability `cyber_advanced`/`cyber_targets`, restrita ao papel `owner`
  autenticado por `MASTER_PASSWORD`.
- **`services/telemetry.py`** — log de auditoria de toda execução de
  ferramenta (`/api/cyber/audit`).
- **Fora de escopo por decisão do produto** — o roadmap deste app
  deliberadamente **não** inclui scanners de SQLi/XSS/SSRF, payload
  factory/reverse shells, cracking de hashes ou bypass de JWT/CORS/IDOR
  contra terceiros. Essas categorias ficam fora mesmo com escopo
  "autorizado", porque a ferramenta em si teria uso dual perigoso; o app
  cobre a parte defensiva (headers, TLS, dependências, config, DNS) descrita
  acima.
