# JARVIS Game Studio 15 — Readability + Live Call + Character 2.0

## Correções
- Inputs, textareas, selects e placeholders da área Community/Onboarding agora têm contraste alto e texto visível.
- Eventos do YouTube agora aceitam URLs `/watch`, `youtu.be`, `/embed/` e `/live/`.
- Canais `lounge`/`stage` ganharam uma sala de voz WebRTC com microfone, mute e saída.
- O servidor funciona somente como sinalização; o áudio não é armazenado pelo JARVIS.
- A sala de voz usa HTTPS/getUserMedia e STUN público para descoberta de candidatos.

## Personagem 2.0
Além de nome/classe/título/estilo/moldura, o onboarding agora permite:
- origem
- especialidade
- companheiro
- habilidade principal
- frase do personagem
- cor do nome
- preview ampliado dessas informações

## Compatibilidade
- Flask/Jinja/JavaScript/CSS preservados.
- Não foi criado um segundo sistema de autenticação.
- Permissões administrativas não são concedidas por XP/personagem.
