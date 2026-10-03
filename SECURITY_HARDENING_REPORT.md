# Tristan Thorne — Security Hardening Report

## Alterações realizadas

- Mantida a arquitetura Flask/Jinja/JavaScript existente.
- Reutilizado `services/tool_adapter.py` como camada central das ferramentas externas.
- Adicionados diagnóstico real de instalação e estados `installed`, `not_installed` e `config_required`.
- Adicionados ExifTool, strings e objdump ao catálogo existente.
- Mantida a execução externa sem `shell=True`, com argumentos controlados, escopo autorizado e timeouts.
- Criada a página `Security Scan`, que analisa somente o próprio projeto e não executa o código analisado.
- Removido o fallback previsível de `SECRET_KEY`; sem variável de ambiente, o processo usa chave aleatória.
- Removido `unsafe-eval` da CSP existente, preservando `unsafe-inline` porque a UI atual ainda possui scripts inline.
- Mantidas as proteções existentes de sessão, CSRF por origem, upload de imagens e autorização por backend.
- Adicionados 20 desafios Cyber Lab isolados, sem alvo de terceiros e sem execução de payloads.

## Relatório do scanner local

No teste realizado sobre a cópia de trabalho:

- Arquivos analisados: 81
- PASS: 7
- WARNING: 97
- ERROR: 0
- NEEDS REVIEW: 3

`WARNING` representa padrão técnico que merece revisão; não é uma afirmação automática de vulnerabilidade.
`NEEDS REVIEW` exige análise humana.

## PROBLEMA → CORREÇÃO → TESTE REALIZADO → RESULTADO

- `SECRET_KEY` previsível → fallback removido → compilação + scanner → sem ERROR de fallback.
- CSP com `unsafe-eval` → removido → inspeção estática → CSP continua presente sem `unsafe-eval`.
- Ferramentas externas sem status detalhado → detector real do `PATH` + versão → catálogo testado → 31 ferramentas catalogadas, incluindo todas as solicitadas e utilitários adicionais.
- Desafios insuficientes para Cyber Lab → 20 laboratórios isolados adicionados → todos iniciam como não resolvidos e validações corrigidas foram testadas → OK.
- Security Scan inexistente → página/API determinísticas → execução local do scanner → OK.
- Execução externa insegura → argumentos fixos, sem shell e com timeout/escopo → inspeção estática do adapter → OK.

## Limitação do teste

O ambiente de execução desta sessão não possui as dependências Flask do projeto e não conseguiu baixá-las porque não havia acesso à rede. Portanto, a suíte completa que inicializa o Flask não foi executada aqui. A compilação de todos os `.py` e os testes dos serviços novos foram executados com sucesso.

## v22 — Senhas/autenticação e headers

- Senha mestre: mínimo 12 caracteres, bloqueio de senhas comuns/previsíveis, troca exige senha atual e derruba as outras sessões. Corrigido: definir a senha pela primeira vez deslogava o próprio owner (faltava `tf_ver` na sessão).
- `MASTER_PASSWORD_HASH` (hash werkzeug) aceito no ambiente; `MASTER_PASSWORD` em texto puro continua funcionando (comparação corrigida para não quebrar com acentos).
- `auth.json` gravado de forma atômica e com permissão 600.
- Login: bloqueio por IP com escalonamento (10 min, 20, 40... até 24h), limite de tamanho de entrada, respostas 401/429 (contam no log de acessos).
- Sessão expira em 12h (`SESSION_HOURS`) e o cookie usa prefixo `__Host-` em HTTPS.
- CSRF: `Origin: null` recusado em métodos que mudam estado. `ALLOWED_HOSTS` (opcional) contra Host-header poisoning.
- Headers: Permissions-Policy corrigida (câmera/microfone liberados só para o próprio site; antes estavam bloqueados e quebravam gesto/palmas/voz), COOP/CORP `same-origin`, `form-action 'self'`, `upgrade-insecure-requests` em HTTPS, `Cache-Control: no-store` fora de /static.
- Preview de sites gerados roda em sandbox (CSP `sandbox` sem `allow-same-origin`): JS escrito por convidado/IA não alcança a sessão do painel. Desative com `PREVIEW_SANDBOX=0` se precisar de localStorage/cookies no preview.
- CORS permanece fechado (sem `Access-Control-Allow-*`): o app não tem API pública e o cookie é SameSite=Lax.
- Limitação conhecida: CSP ainda usa `unsafe-inline` em scripts (~57 handlers inline nos templates). Migrar para nonce exige mover os handlers para JS externo.
- Testes: `python -m unittest tests.test_access_log` (12 testes). A suíte que sobe o Flask não foi executada nesta sessão (sem Flask/rede).

## v23 — Chaves de API e variáveis de ambiente

- PROBLEMA: `settings.html` renderizava TODAS as chaves de API em texto puro no HTML (`value="{{ config.xxx_api_key }}"`, inclusive em ~43 campos hidden repetidos). A própria tela afirmava que a chave "nunca é enviada ao navegador". CORREÇÃO: nenhum valor de chave vai mais para o HTML; a tela mostra só `••••` + 4 últimos caracteres e a origem (ambiente/arquivo). Campo vazio = manter a chave; checkbox "remover esta chave" apaga. Cada card salva só os seus campos. Chaves com espaço/quebra de linha são recusadas.
- `config.json` gravado de forma atômica e com permissão 600; arquivos antigos (`config.json`, `auth.json`, `.env`) são corrigidos para 600 na inicialização.
- Suporte a `.env` local (sem dependência extra); nunca sobrescreve variáveis reais do ambiente. `.env.example` documenta todas as variáveis.
- Rede de segurança: respostas JSON que ecoarem o valor exato de uma chave/segredo configurado saem com `[oculto]`.
- Card "Saúde dos segredos" em Configurações: chaves só em arquivo, permissões, SECRET_KEY ausente, senha em texto puro, `.gitignore` incompleto.
- `.gitignore` reforçado (`.env`, `.env.*`, `*.json.tmp`).
- `scripts/check_secrets.py`: procura chaves esquecidas no código (valores mascarados na saída; exit 1 se achar, serve de pre-commit). No projeto: 2 achados, ambos dados falsos de laboratório/teste.
- Pendências: tokens de uso único seguem em texto puro no `auth.json` (a chave por papel já é hasheada); se alguma chave já esteve em versões antigas do zip ou do Git, considere-a comprometida e gere outra.

## v24 — SSRF Guard centralizado

- `services/scope.py` continua sendo o ÚNICO ponto de decisão (nenhum sistema novo): agora concentra classificação de IP, resolução, conexão e registro. Todas as ferramentas que conectam em algo passam por ele.
- Classificação única (`classify_ip`) para IPv4 e IPv6, incluindo IPv4 embutido em IPv6 (`::ffff:a.b.c.d`, `::a.b.c.d`, NAT64, 6to4, Teredo). Sempre bloqueado, mesmo autorizado: link-local, multicast, `0.0.0.0/8`, broadcast, `::`, metadata (169.254.169.254, 169.254.170.2, fd00:ec2::254, 100.100.100.200, 192.0.0.192, 168.63.129.16) e nomes `metadata.google.internal` etc. Loopback/privado/reservado/CGNAT só passam no modo laboratório, com IP/CIDR explicitamente autorizado. Ferramentas públicas nunca alcançam rede interna.
- Anti-rebinding: o host é resolvido UMA vez e a conexão vai direto no IP validado (`scope.create_connection`, `PinnedHTTPConnection`, `PinnedHTTPSConnection`; TLS/SNI seguem usando o nome). Não existe segunda resolução DNS. Se o peer conectado não for o IP validado, a conexão é fechada e registrada.
- Redirects seguem manuais, revalidados a cada salto (contexto `redirect` no log), com teto de tempo total. DNS com timeout de 5 s; timeouts de conexão limitados (`clamp_timeout`, máx. 30 s).
- URLs ambíguas (barra invertida, espaço/controle) são recusadas; binários externos recebem URL reconstruída (`canonical_url`), nunca a string crua.
- Registro: toda negativa vai para o logger `ssrf_guard` e para o `audit_log` (tool=`ssrf_guard`, visível em `/api/cyber/audit`), com tipo (`metadata_ou_link_local`, `rede_interna`, `nao_autorizado`, `rebinding`, `url_ambigua`...).
- Novo: `add_target` recusa CIDR catch-all (`0.0.0.0/0`, `::/0`, menor que /8 em IPv4 ou /16 em IPv6), que anularia a proteção do modo laboratório.
- Corrigido: `tool_adapter._require_scope` devolvia a lista de IPs e quebrava nmap/gobuster/nikto/ffuf/whatweb (`TypeError`) quando o binário estava instalado. Agora devolve o host; o nmap recebe o IP já validado.
- Ferramentas integradas: web/API tester/website health/link checker/OWASP (`web.safe_get`), TLS, inventário e checagem de portas, diagnóstico de rede, whois (servidor referido), Ferramentas públicas (`basic_net`) e binários do `tool_adapter`.
- Limitação conhecida: nikto, gobuster, whatweb, ffuf e testssl resolvem o nome por conta própria; para eles só é possível validar imediatamente antes de executar. Para alvos hostis, rode o Cyber Lab em rede isolada.
- Testes: `python tests/test_ssrf_guard.py` (40 testes) + suíte existente `tests/test_cyberlab.py` (107 verificações) sem regressão.


## v25 — Hardening integrado do projeto inteiro

### Implementado
- CSRF real por token de sessão, validado no backend para POST/PUT/PATCH/DELETE, mantendo Origin/Referer como segunda camada. O frontend recebe o token por meta tag/arquivo JS e formulários existentes são preenchidos automaticamente.
- Request ID validado/criado no início de cada requisição, devolvido em `X-Request-ID`, incluído nos access/audit logs e nas respostas JSON de erro.
- `SECRET_KEY` obrigatória quando o ambiente é explicitamente identificado como produção/PaaS; não há geração aleatória em produção. Desenvolvimento mantém chave efêmera.
- `MASTER_PASSWORD` em texto puro deixou de ser aceito em produção; `MASTER_PASSWORD_HASH` continua sendo a fonte recomendada.
- Tokens de uso único existentes são migrados para chaves SHA-256 sem invalidar o segredo apresentado ao usuário. A interface não lista mais o token bruto; o segredo é mostrado somente no momento de criação. Sessões novas guardam apenas o identificador do token.
- Uploads de imagem passaram a validar tamanho e conteúdo real, rejeitar SVG/outros formatos, derivar extensão do conteúdo e gerar nomes aleatórios. Galeria limitada a 8 imagens.
- Execução de ferramentas externas foi centralizada no adapter com `shell=False`, ambiente reduzido, diretório temporário isolado, timeout e limites POSIX de CPU/memória/descriptors quando disponíveis.
- Preview recebeu política CSP específica para bloquear `connect`, frames e objetos, além do sandbox existente, preservando recursos web necessários.
- Backup do Security Center agora possui manifesto SHA-256, verificação antes de uso, retenção configurável e restauração com backup de segurança antes da troca.
- Security Center passou a expor estado de autenticação, auditoria, access log, ferramentas, backups, dependências e alertas derivados dos logs com cooldown.
- `pip-audit` foi incluído em `requirements.txt` com faixa de versão e `scripts/check_dependencies.py` para auditoria sem atualização automática.
- Respostas JSON passam por redaction adicional de padrões de credenciais além dos segredos configurados.
- Eventos sensíveis passaram a ser associados ao audit log existente: login, logout, senha, tokens, configurações, ações administrativas, scans, edição/publicação/exclusão de sites, Cyber Lab e restauração de backup.

### Validação
- Todos os `.py`: compilação sem erros.
- Todos os `.js`: `node --check` sem erros.
- `tests.test_ssrf_guard`: 40/40 aprovados.
- `tests.test_security_center_static`: 1/1 aprovado.
- `tests.test_access_log.SenhaEHeadersTests`: 6/6 aprovados em ambiente local com stub mínimo apenas para Werkzeug, porque as dependências do projeto não estão instaladas nesta sessão.
- Testes direcionados de hash de tokens e upload seguro: aprovados.
- Teste direcionado de backup: manifesto/integridade/restauração aprovados.
- A suíte completa não pôde ser executada porque Flask/Werkzeug não estão instalados no ambiente e a tentativa de instalar `requirements.txt` falhou por ausência de acesso à rede/DNS.

### Pendências/riscos
- CSP ainda mantém `unsafe-inline` em `script-src` porque a UI atual possui 57 handlers inline e 10 blocos `<script>` inline; remover tudo de uma vez poderia quebrar telas. A migração para handlers externos/nonces deve ser feita gradualmente.
- Ferramentas externas que fazem a própria resolução DNS continuam dependendo da validação imediatamente antes da execução; o uso deve permanecer restrito ao escopo autorizado/lab.
- Limites de CPU/memória do sandbox de processos são aplicados quando o sistema operacional oferece `resource`; Windows não recebe esses limites POSIX.
- A auditoria de dependências requer instalação efetiva de `requirements.txt`/`pip-audit` no ambiente de deploy.
- Não foi possível executar testes de integração Flask nesta sessão por falta das dependências.
