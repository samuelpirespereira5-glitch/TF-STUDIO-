# v33 — legibilidade, senha no primeiro acesso, mais ferramentas e desafios

## 1. Texto mais fácil de ler
- Causa principal: a camada de linhas `.scanlines` ficava **por cima** de todo o texto (z-index 9999). Agora fica atrás.
- Base de texto 16px → 17px, mais contraste nos textos secundários e nenhum texto abaixo de ~12,5px (antes havia 9–11px em badges, cartões, rodapé, holograma).
- Canto da tela: **A−**, **A+** e **👁 Modo leitura** (remove animações/efeitos). A escolha fica salva no navegador.
- Tudo é um bloco no **fim** de `static/css/style.css` (procure `v33 · LEGIBILIDADE`); para desfazer, apague o bloco e a tag `readability.js` do `base.html`.

## 2. Senha no primeiro acesso
- Antes: sem `MASTER_PASSWORD`/`MASTER_PASSWORD_HASH` o site abria direto, sem nenhuma tela de senha.
- Agora: sem senha definida, qualquer página leva a **/primeiro-acesso**, onde você cria a senha mestre (mínimo 12 caracteres, frase longa vale; confirmação; bloqueia senhas comuns). Depois disso o site passa a pedir a senha no `/login`.
- A criação só funciona **no próprio computador** (127.0.0.1, sem proxy na frente). Acesso remoto vê uma explicação e não consegue criar a senha.
- Em produção nada muda: `MASTER_PASSWORD_HASH` (ou `MASTER_PASSWORD`) continua obrigatório.
- Quem quiser o modo aberto antigo: `FIRST_ACCESS_SETUP=0`.
- Esqueceu a senha (uso local)? Apague `auth.json` (pasta `data/`) e reinicie: a tela de criação volta.

## 3. Ferramentas novas (12) — locais, sem rede, sem alvo, liberadas para todos os papéis
Gerador de senha/frase-senha · Gerador de hash · Conversor de timestamp · Inspetor de URL (phishing) · Analisador de cabeçalhos HTTP · Analisador de CSP · Analisador de cookies · Analisador de cabeçalho de e-mail (SPF/DKIM/DMARC) · Calculadora CVSS 3.1 · Referência de portas · Referência de status HTTP · Inspetor de Base64.
Código: `services/cyber/extra_tools.py` (registro em `services/builtin_tools.py`). Total de ferramentas: 89 → 101.

## 4. Desafios novos (36) — total 92 → 128
JWT (3) · NoSQL · SSTI · Clickjacking · Log injection · Rate limit · Senhas (2) · Cloud/IaC (2) · Docker (3) · Phishing (2) · Logs/blue team (2) · Forense · CTF (6: Base64, Hex, César, JWT, URL, código-fonte) · CORS · IDOR/download · YAML · eval · Privacidade/LGPD (2) · Sessão · Resposta a incidentes (3).
Código: `services/cyber_challenges_v33.py`. Cada desafio tem solução de referência (`TEST_SOLUTIONS`) e os testes garantem que ele **falha quebrado e passa corrigido**.

## Testes
`python tests/test_cyberlab.py` (107 verificações) e `python -m unittest discover -s tests -p "test_[!c]*.py"` (74 testes, incluindo `tests/test_v33_additions.py`).
