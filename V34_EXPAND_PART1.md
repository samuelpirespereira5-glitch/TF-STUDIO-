# JARVIS Cyber Lab — Expansão v34 Parte 1

## O que foi adicionado (sem remover funcionalidades existentes)

### Novos módulos
- `services/cyber/tool_limits.py` — limites por ferramenta (rate, timeout, tamanho, concorrência, ativo/passivo)
- `services/cyber/validation.py` — validação rigorosa de IP/domínio/URL/porta/arquivo; bloqueio de comandos arbitrários; redaction
- `services/cyber/central_categories.py` — Central de Ferramentas com categorias oficiais
- `services/cyber/defensive_tools.py` — ferramentas defensivas registradas no registry

### Ferramentas defensivas registradas
| ID | Categoria | Tipo |
|----|-----------|------|
| port_scanner | Rede | Ativo (allowlist) |
| dns_lookup_tool | Reconhecimento | Passivo |
| header_analyzer | Web | Passivo (URL autorizada) |
| ssl_tls_analyzer | Web | Passivo (host autorizado) |
| hash_analyzer | Criptografia | Local |
| file_analyzer | Forense | Local (bloqueia executáveis) |
| log_analyzer | Blue Team | Local (sanitiza secrets) |
| secrets_scanner | Blue Team | Local (heurístico) |
| dependency_scanner | Blue Team | Local |
| ip_analyzer | Reconhecimento | Local / DNS passivo |
| api_tester_safe | Segurança de APIs | Ativo seguro (GET/HEAD/OPTIONS) |
| malware_sandbox | Malware Analysis | Estático isolado (sem rede, sem execução) |

### UI / rotas
- `/cyber/politicas` e `/cyber/policies` — página Políticas de Segurança
- `/api/cyber/policies` — JSON com limites, RBAC multipliers, categorias, mensagens
- Cyber Hub atualizado com categorias oficiais e link para políticas

### Segurança
- Todas as tools novas passam por `preflight` + `scope` (SSRF Guard existente)
- Mensagens: "Alvo não autorizado", "Limite de requisições atingido", "Entrada inválida", "Operação bloqueada pela política de segurança"
- Secrets nunca vão para logs (`audit_params` redaction)
- Rate limit por ferramenta + multiplicador por role

## Partes seguintes (ainda não nesta entrega)
- Parte 2: aprofundar cada ferramenta + subdomínios autorizados + config checker
- Parte 3: desafios cyber com XP/níveis/conquistas/ranking
- Parte 4: dashboard avançado + modo Desenvolvedor + relatórios exportáveis
