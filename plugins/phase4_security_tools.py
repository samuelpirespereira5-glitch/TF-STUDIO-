"""Ferramentas da expansão 4. Somente análise defensiva/local ou alvo autorizado."""
from services.tool_registry import Registry
from services import phase4

def register(reg: Registry):
    TXT={"text":{"type":"string","required":True,"description":"Conteúdo fornecido ao laboratório"}}
    tools=[
      ("csp_analyzer","CSP Analyzer","web-security","Analisa Content-Security-Policy fornecida.",lambda p,c: phase4._analyze_text(p.get('text',''),'csp')),
      ("http_method_analyzer","HTTP Method Analyzer","web-security","Identifica métodos HTTP perigosos ou desnecessários em uma matriz fornecida.",lambda p,c: phase4._analyze_text(p.get('text',''),'methods')),
      ("redirect_analyzer","Redirect Analyzer","web-security","Analisa cadeia de redirects fornecida sem realizar navegação automática.",lambda p,c: phase4._analyze_text(p.get('text',''),'redirects')),
      ("cache_security_analyzer","Cache/Security Header Analyzer","web-security","Analisa headers de cache e segurança fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'cache')),
      ("jwt_security_analyzer_v4","JWT Security Analyzer","web-security","Analisa configuração/claims JWT fornecidas sem aceitar ou forjar tokens.",lambda p,c: phase4._analyze_text(p.get('text',''),'jwt')),
      ("api_schema_analyzer","API Schema Analyzer","api-security","Analisa esquema de API fornecido.",lambda p,c: phase4._analyze_text(p.get('text',''),'api')),
      ("openapi_security_checker","OpenAPI Security Checker","api-security","Verifica securitySchemes e requisitos de segurança em OpenAPI fornecido.",lambda p,c: phase4._analyze_text(p.get('text',''),'openapi')),
      ("dns_security_analyzer_v4","DNS Security Analyzer","network","Analisa registros DNS fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'dns')),
      ("tls_configuration_analyzer","TLS Configuration Analyzer","network","Analisa configuração TLS fornecida.",lambda p,c: phase4._analyze_text(p.get('text',''),'tls')),
      ("certificate_analyzer_v4","Certificate Analyzer","network","Analisa informações de certificado fornecidas.",lambda p,c: phase4._analyze_text(p.get('text',''),'cert')),
      ("service_configuration_analyzer","Service Configuration Analyzer","network","Analisa configuração de serviço fornecida.",lambda p,c: phase4._analyze_text(p.get('text',''),'service')),
      ("network_exposure_analyzer","Network Exposure Analyzer","network","Classifica exposição de serviços a partir de dados fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'exposure')),
      ("ioc_analyzer_v4","IOC Analyzer","blue-team","Analisa indicadores fornecidos sem contato com infraestrutura externa.",lambda p,c: phase4._analyze_text(p.get('text',''),'ioc')),
      ("log_correlation_analyzer","Log Correlation","blue-team","Correlaciona eventos por timestamp/request_id/IP redigido.",lambda p,c: phase4._analyze_text(p.get('text',''),'correlation')),
      ("authentication_event_analyzer","Authentication Event Analyzer","blue-team","Analisa eventos de autenticação fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'auth')),
      ("bruteforce_detection_simulator","Brute-force Detection Simulator","blue-team","Simula detecção sobre logs fornecidos; não gera tráfego.",lambda p,c: phase4._analyze_text(p.get('text',''),'bruteforce')),
      ("configuration_baseline_checker","Configuration Baseline Checker","blue-team","Compara baseline e configuração em texto/JSON fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'baseline')),
      ("dependency_audit_v4","Dependency Audit","blue-team","Analisa dependências e só reporta vulnerabilidades se um resultado de auditoria real for fornecido.",lambda p,c: phase4._analyze_text(p.get('text',''),'dependencies')),
      ("secret_detection_v4","Secret Detection","blue-team","Detecta padrões de secrets sem exibir valores.",lambda p,c: phase4._analyze_text(p.get('text',''),'secrets')),
      ("file_metadata_analyzer_v4","File Metadata Analyzer","forensics","Analisa metadados textuais fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'metadata')),
      ("hash_comparison_v4","Hash Comparison","forensics","Compara hashes fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'hash')),
      ("timeline_generator_v4","Timeline Generator","forensics","Ordena eventos fornecidos por timestamp.",lambda p,c: phase4._analyze_text(p.get('text',''),'timeline')),
      ("log_timeline_v4","Log Timeline","forensics","Normaliza eventos de log em linha do tempo.",lambda p,c: phase4._analyze_text(p.get('text',''),'logtimeline')),
      ("evidence_organizer_v4","Evidence Organizer","forensics","Organiza evidências fornecidas por tipo e timestamp.",lambda p,c: phase4._analyze_text(p.get('text',''),'evidence')),
      ("integrity_verification_v4","Integrity Verification","forensics","Verifica integridade usando hashes fornecidos.",lambda p,c: phase4._analyze_text(p.get('text',''),'integrity')),
      ("sast_basic_v4","SAST básico","secure-coding","Análise estática básica de padrões vulneráveis; não executa código.",lambda p,c: phase4._analyze_text(p.get('text',''),'sast')),
      ("insecure_config_detector_v4","Insecure Configuration Detection","secure-coding","Detecta padrões de configuração insegura.",lambda p,c: phase4._analyze_text(p.get('text',''),'config')),
      ("vulnerable_pattern_detector_v4","Vulnerable Pattern Detector","secure-coding","Identifica padrões de risco e explica correções.",lambda p,c: phase4._analyze_text(p.get('text',''),'patterns')),
    ]
    for tid,name,cat,desc,fn in tools:
        if reg.get(tid): continue
        reg.register(id=tid,name=name,category=cat,description=desc,cap='cyber',params=TXT,handler=fn,keywords=[name.lower()])

def _register_safe(reg): return register(reg)
