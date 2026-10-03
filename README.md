# Tristan Thorne — Web Edition

Versão do Tristan Thorne como um site de verdade (Flask), sem depender do Claude
nem de nada por fora: você hospeda isso onde quiser e fica público, com o link
que quiser compartilhar.

Inclui: gerador de sites com IA (multi-país/idioma), editor com IA, tradução
de sites, publicação no Netlify, o Jarvis (chat + voz pelo navegador) e um
conjunto de mais de 20 ferramentas (validador de CPF/CNPJ, gerador de senha,
QR code, conversor de unidades/moeda, SEO, legendas para redes sociais etc.).
**Não inclui** o gerador de vídeo com IA (removido a pedido).

## 1. Rodar localmente

```bash
cd tf_studio_web
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env e cole sua OPENROUTER_API_KEY (ou configure depois pela tela
# "Configurações" já rodando — ela grava em config.json no servidor)

python app.py
```

Abra `http://localhost:5000`.

A chave da OpenRouter é gratuita: crie a sua em https://openrouter.ai/keys.

## 2. Onde hospedar (para ficar público de verdade)

Qualquer um destes serve. Resumo rápido para quem nunca hospedou nada:

### Opção mais fácil: Render.com
1. Suba esta pasta para um repositório no GitHub.
2. Em https://render.com → "New +" → "Web Service" → conecte o repositório.
3. Build command: `pip install -r requirements.txt`
4. Start command: já vem pronta no `Procfile` incluso.
5. Em "Environment", adicione `OPENROUTER_API_KEY` e uma `SECRET_KEY` estável.
   **Não deixe `SECRET_KEY` vazia em produção.** Se usar Render Blueprints, o
   `render.yaml` deste projeto pode gerar a `SECRET_KEY` automaticamente e de
   forma persistente para o serviço; no painel manual, crie a variável uma vez.
6. **Importante:** o disco do plano gratuito do Render é temporário — os
   sites gerados (pasta `sites/`) somem a cada novo deploy. Para guardar de
   verdade, adicione um "Persistent Disk" (pago, poucos dólares/mês) montado
   em `/opt/render/project/src/sites`, ou use a Opção 3 (VPS) abaixo.

### Opção 2: Railway.app
Mesma ideia do Render: conecta o GitHub, ele detecta o `Procfile` sozinho.
Railway tem "Volumes" para guardar a pasta `sites/` de forma persistente —
vale a pena configurar um volume apontando para `/app/sites`.

### Opção 3: VPS próprio (Linux) — a mais "de verdade"
Recomendado se você quer controle total e armazenamento permanente sem
pegadinha de plano gratuito.

```bash
# no servidor (Ubuntu, por exemplo)
sudo apt update && sudo apt install python3-venv nginx -y
git clone <seu-repositorio> tf_studio_web
cd tf_studio_web
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edite com sua chave

# rode com gunicorn (mesmo comando do Procfile)
gunicorn app:app --workers 1 --threads 8 --timeout 300 --bind 0.0.0.0:8000

# para deixar rodando sempre, crie um serviço systemd chamando esse comando,
# e configure o nginx como proxy reverso (porta 80/443) apontando para 127.0.0.1:8000
```

Com um VPS você também consegue instalar o **Netlify CLI** para o botão
"Publicar no Netlify" funcionar:
```bash
npm install -g netlify-cli
netlify login
```

## 3.1 Terminal Kali real (opcional)

A página **Kali Linux** possui um terminal web seguro. Ele não executa `bash`/shell
arbitrário: os comandos são traduzidos para ferramentas já registradas no Tool
Registry e continuam sujeitos a permissões, escopo autorizado, SSRF Guard,
timeouts e sandbox.

No Render/PaaS, a imagem Python comum não vem com Nmap, Gobuster, Nikto, ffuf etc.
Para ter essas ferramentas instaladas no próprio servidor, existe uma opção
aditiva que não altera o deploy padrão: `Dockerfile.kali` + `render-kali.yaml`.
Esse perfil usa Kali Linux como imagem base e instala apenas as ferramentas
permitidas pelo terminal. O deploy padrão continua usando o `Procfile`.

Comandos disponíveis no terminal: `nmap`, `gobuster`, `nikto`, `ffuf`, `whatweb`,
`testssl`, `dns`, `tls`, `ports`, `whois`, além de `help`, `tools`, `status` e
`clear`. Ferramentas que não estejam instaladas mostram o motivo e a instrução
de instalação em vez de fingir uma execução.

## 3. Coisas importantes que você deve saber

- **A chave da OpenRouter fica no servidor e é compartilhada por todos os
  visitantes.** Como isto é um servidor público único (não multi-usuário com
  login), quem acessar o site vai gerar sites usando essa chave/seu crédito.
  Se quiser controlar isso, a forma mais simples é colocar o site atrás de
  autenticação (ex: usuário/senha básica do nginx) ou adaptar para pedir a
  chave de cada visitante — não incluí isso para manter o projeto simples.
- **Rode sempre com 1 worker** (`--workers 1`, já configurado no `Procfile`).
  O acompanhamento de progresso ("gerando site...", "publicando...") usa
  memória do processo; com mais de um worker, cada requisição pode cair num
  processo diferente e o progresso "sumir".
- **Geração de imagem com IA** usa o serviço gratuito Pollinations
  (`image.pollinations.ai`) — não precisa de chave, mas depende do servidor
  ter acesso à internet.
- O sistema de **licença/ativação** do app original foi removido — não fazia
  sentido para algo que agora é público. Se quiser restringir o acesso,
  a forma mais simples é habilitar autenticação básica no nginx/nível de
  servidor.

## 4. Estrutura do projeto

```
app.py                  → todas as rotas Flask
services/ai_engine.py   → prompts e chamadas à IA (OpenRouter)
services/maps_service.py → holograma de "lugar real" (Google Maps: geocoding, elevação, satélite)
services/live_data.py   → dados ao vivo e grátis pro Jarvis (clima Open-Meteo, resumo Wikipédia)
services/sites_service.py → criação/gestão de sites e publicação Netlify
services/jobs.py        → acompanhamento de tarefas em segundo plano
templates/              → páginas HTML (Jinja2)
static/                 → CSS e JS
sites/                  → onde cada site gerado é salvo (1 pasta por site)
```

## 5. Holograma de lugar real (Google Maps)

Além do holograma procedural (mapa/objeto/rede gerados por texto), agora existe
um modo de **lugar real**: em Ferramentas → Holograma 3D, digite um lugar de
verdade (ex: "Torre Eiffel") e clique em "🛰 Trazer lugar real" — ou peça pro
Jarvis: *"coloca a Torre Eiffel no holograma real"* / *"holograma real de Paris"*.

O app busca, na hora, pelo Google Maps Platform:
- **Geocoding API** → coordenadas reais do lugar
- **Elevation API** → malha de altitudes reais do relevo ao redor
- **Maps Static API** → imagem de satélite real, usada como textura do terreno

Precisa de uma chave em Configurações → "🛰 Google Maps (holograma de lugar
real)", com essas 3 APIs ativadas no [Google Cloud
Console](https://console.cloud.google.com/google/maps-apis/credentials) (tem
cota grátis mensal generosa, mas exige cartão cadastrado no projeto).

## 6. Jarvis com dados ao vivo

O Jarvis agora também busca dado real, 100% grátis e sem chave nenhuma, antes
de responder perguntas de dois tipos:
- **Clima/temperatura** de qualquer cidade (via Open-Meteo)
- **"O que é / quem é" algo** (resumo real da Wikipédia)

Isso é detectado por padrão de texto (não é function-calling de verdade, já
que nem todo modelo grátis do OpenRouter suporta isso de forma confiável) e
injetado como contexto antes da resposta — se não bater com nenhum padrão, a
conversa segue normal, sem custo extra.

---

## Evolução: Jarvis Tool Router + Cyber Lab + Permissões (Fase 1)

### Papéis (validados no BACKEND)
| Papel | Como entra | Acesso |
|---|---|---|
| owner | senha mestre (ou uso local sem senha, direto na máquina) | tudo, inclui Configurações, alvos autorizados e chaves |
| admin | chave `tf_a_…` (campo "token" do login) | Cyber Lab, Creator, diagnósticos, ferramentas avançadas |
| user | chave `tf_u_…` | só ferramentas básicas + chat |
| guest | token de uso único (já existia) | só criar 1 site |

Chaves são criadas em `POST /api/admin/keys` (owner) e só aparecem uma vez; no disco fica o hash.
Sem senha mestre, **só** acesso direto de `127.0.0.1` (sem proxy) vira owner; acesso remoto vira `user`.
Mapa de rotas → permissão: `services/permissions.py` (`PATH_CAPS`). Descubra o seu papel em `GET /api/me`.

### Cyber Lab: só alvos AUTORIZADOS
Nenhuma ferramenta do Cyber Lab toca em um host que não esteja em `data/authorized_targets.json`
(o owner adiciona via `POST /api/cyber/targets`, confirmando propriedade/autorização).
Metadata de nuvem (169.254.0.0/16) é sempre bloqueada; rede interna/loopback só se autorizada
explicitamente (modo laboratório/CTF). Redirects são revalidados a cada salto.
As ferramentas públicas antigas (Ferramentas › headers/SSL/robots/latência/domínio) continuam abertas
para sites públicos, mas agora **não alcançam rede interna** (proteção SSRF).

Módulos: HTTP/Headers/Cookies/CSP/CORS/Fingerprint (`web_analyzer`), TLS, DNS (SPF/DMARC/CAA),
Subdomínios, Portas/Serviços, Links, Segredos, Código, Dependências (+OSV.dev opcional), Logs,
Configurações (sshd/nginx/.env), **Security Investigator**, Evidence Center (SQLite), histórico,
antes/depois, reteste, dashboard de risco e relatório em Markdown.

### Jarvis controla ferramentas
`services/tool_router.py` escolhe a(s) ferramenta(s), extrai o alvo, combina várias quando faz
sentido e executa em streaming (`POST /api/jarvis/run`, NDJSON) com **auto-diagnóstico**
(erro → causa → correção segura → reteste). No chat: "audite a segurança de meusite.com",
"verifique SPF e DMARC de meusite.com", "lembre-se que…" (memória persistente).

### Plugins
Coloque `plugins/meu_plugin.py` com `def register(reg): reg.register(id=..., name=..., handler=...)`
(veja o docstring de `services/tool_registry.py`). Plugin quebrado nunca derruba o app: aparece em
`GET /api/jarvis/tools` (para admin) e no diagnóstico.

### Testes
`python tests/test_cyberlab.py` — sobe um servidor de laboratório local e roda 98 verificações
(escopo, SSRF, analisadores, DNS, evidências, router, investigator, permissões via Flask).
Nenhuma dependência nova: o Cyber Lab usa só a biblioteca padrão do Python.

## IP real e log de acessos (v21)

- `services/security.client_ip(request)` devolve o IP real do visitante. Atrás de proxy/hospedagem (Heroku, Render, Railway, Fly, Cloud Run) o app detecta sozinho 1 proxy; para outro caso defina `TRUSTED_PROXY_HOPS` (0 = sem proxy, 2 = ex.: Cloudflare + hospedagem). O header `X-Forwarded-For` nunca é lido sem proxy configurado, então não dá para forjar o IP.
- `services/access_log.py` grava cada requisição (IP, método, rota sem query string, status, papel) na tabela `access_log` do `data/cyberlab.db`. Estáticos e o polling `/api/admin/online` são ignorados.
- Retenção automática de 90 dias (LGPD); ajuste com `ACCESS_LOG_RETENTION_DAYS`.
- Visualização: Configurações → "Todos os acessos (IP)" (IPs mais ativos em 24h e últimas 100 requisições) ou `GET /api/admin/access-log?ip=...&limit=...&hours=...` (somente owner).
- Testes: `python -m unittest tests.test_access_log`.

## Chaves de API e `.env` (v23)

- Produção: cadastre as chaves como variáveis de ambiente da hospedagem (lista em `.env.example`). Desenvolvimento: copie `.env.example` para `.env` (ignorado pelo Git).
- A tela de Configurações nunca exibe chaves; mostra só os 4 últimos caracteres. Campo vazio mantém a chave atual.
- Antes de commitar/deployar: `python scripts/check_secrets.py`. Como hook: `printf '#!/bin/sh\npython scripts/check_secrets.py\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`.
- Testes: `python -m unittest tests.test_access_log`.

## Acesso do proprietário em produção

O Tristan Thorne não inicia em produção sem uma senha mestre configurada. Isso evita que um deploy novo fique aberto acidentalmente.

1. Gere o hash localmente:
   `python scripts/generate_master_hash.py`
2. No Render, crie/defina `MASTER_PASSWORD_HASH` com o hash gerado.
3. Mantenha `SECRET_KEY` configurada e estável.
4. Depois do deploy, a primeira tela será `/login` e a senha mestre dará papel `owner`.

`MASTER_PASSWORD` em texto puro não é aceito em produção.

### Configurações

`Configurações` é uma área de proprietário (`owner`). Usuários comuns e tokens de uso único não recebem essa capacidade; o link é ocultado para esses papéis e a rota continua protegida no backend.

### Kali Lab

O terminal Kali usa somente comandos registrados no Tool Registry. Shell arbitrário, `bash`, `python` e `apt` não são executados pelo servidor. As ferramentas passam pelas permissões, escopo autorizado e controles de segurança existentes.
