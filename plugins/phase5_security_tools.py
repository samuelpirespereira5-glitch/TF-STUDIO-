"""Phase 5 tools: local defensive analysis only. No network exploitation."""
import json,re,hashlib
from services.tool_registry import Registry

def _findings(text):
 s=str(text or '')[:200000]; low=s.lower(); f=[]
 def add(i,t,sev,e,fix): f.append({'id':i,'title':t,'severity':sev,'evidence':e[:500],'fix':fix,'status':'confirmed'})
 if re.search(r'password\s*=\s*["\'][^"\']+["\']',s,re.I): add('secret.password','Possible hardcoded password','high','Password-like assignment found; value omitted.','Move secret to managed environment/secret storage and rotate if real.')
 if 'debug=true' in low: add('config.debug','Debug enabled','medium','debug=true supplied in configuration.','Disable debug outside controlled development.')
 if 'verify=false' in low: add('tls.verify','TLS verification disabled','high','verify=false supplied.','Enable certificate verification.')
 if 'allow_origins=*' in low or 'access-control-allow-origin: *' in low: add('cors.wildcard','Wildcard CORS','medium','Wildcard origin supplied.','Use an explicit origin allowlist where credentials/sensitive data are involved.')
 return f

def register(reg:Registry):
 defs=[
 ('sast_secure_code_v5','SAST básico · Operations','secure-coding','Analisa padrões seguros fornecidos localmente.'),
 ('ioc_matcher_v5','IOC Matcher','blue-team','Compara indicadores fornecidos com uma lista local fornecida pelo usuário.'),
 ('log_correlation_v5','SOC Log Correlator','blue-team','Correlaciona linhas de log fornecidas localmente por timestamp/request id.'),
 ('baseline_diff_v5','Baseline Diff','blue-team','Compara baseline e configuração fornecidos.'),
 ('forensics_integrity_v5','Forensics Integrity','forensics','Calcula SHA-256 de conteúdo fornecido e compara com referência.'),
 ('api_schema_v5','API Schema Guard','api-security','Valida presença de autenticação/segurança em schema fornecido.'),
 ]
 def handler(p,c):
  text=str(p.get('text',''))[:200000]; f=_findings(text)
  return {'summary':f'{len(f)} achado(s) defensivos identificados no material fornecido.','findings':f,'raw':{'bytes':len(text.encode())}}
 for tid,name,cat,desc in defs:
  if reg.get(tid): continue
  reg.register(id=tid,name=name,category=cat,description=desc,cap='cyber',params={'text':{'type':'string','required':True,'description':'Conteúdo local fornecido ao laboratório'}},handler=handler,keywords=[name.lower()],persist=False)
