# JARVIS Cyber Lab — Expansão v34 Partes 2, 3 e 4

## Parte 2 — Ferramentas defensivas aprofundadas
Novos em `services/cyber/defensive_tools_extra.py` (registrados no registry):
- subdomain_enum (allowlist, wordlist limitada)
- http_scanner
- config_checker
- code_scanner (SAST heurístico, sem execução)
- service_banner
- cookie_analyzer
- hardening_checklist

Todas usam `validation.preflight` + `scope` (SSRF Guard).

## Parte 3 — Desafios, XP, conquistas, ranking
- `services/cyber_challenges_v34.py` — 12 desafios novos (fácil → expert)
- Categorias: tls-lab, api-lab, forense-lab, supply-chain, zero-trust
- `services/gamification.py` — XP, níveis, 10 conquistas, ranking local (`data/gamification.json`)
- UI em `/desafios` com conquistas e leaderboard
- Uso de ferramentas registra progresso (tool_registry → gamification)

## Parte 4 — Dashboard, Desenvolvedor, relatórios
- `services/cyber_dashboard.py` — agrega evidence + severidade + recomendações + status
- `/cyber/dashboard` + API dashboard enriquecida
- `/cyber/developer` — modo Desenvolvedor (cap `developer` real)
- `/api/cyber/report/export` — relatório JSON/Markdown exportável
- `/api/cyber/gamification` — estado XP/conquistas/ranking

## Rotas úteis
| Rota | Descrição |
|------|-----------|
| /cyber/hub | Central de Ferramentas |
| /cyber/politicas | Políticas e limites |
| /cyber/dashboard | Dashboard |
| /cyber/developer | Modo Desenvolvedor |
| /desafios | Desafios + XP + conquistas |
| /api/cyber/policies | Limites JSON |
| /api/cyber/dashboard | Dashboard JSON |
| /api/cyber/gamification | XP/ranking |
| /api/cyber/report/export | Relatório |

## Segurança (inalterada / reforçada)
- Sem malware real, sem evasão, sem exfiltração, sem ataques a terceiros
- Allowlist + bloqueio metadata/privado
- Rate limits e mensagens claras de política
