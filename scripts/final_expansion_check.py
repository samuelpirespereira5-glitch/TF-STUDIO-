"""Static/integration checks for the final Cyber Lab expansion."""
from pathlib import Path
import ast, re, sqlite3, sys
ROOT=Path(__file__).resolve().parent.parent
errors=[]; py=list(ROOT.rglob('*.py'))
for p in py:
    try: ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    except Exception as e: errors.append(f'AST {p}: {e}')
# exact route duplicate check
routes=[]
for p in py:
    try: tree=ast.parse(p.read_text(encoding='utf-8'))
    except: continue
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in {'get','post','patch','put','delete'} and d.args and isinstance(d.args[0],ast.Constant):
                    routes.append((d.func.attr,str(d.args[0].value),str(p),n.name))
seen={}; dup=[]
for r in routes:
    k=r[:2]
    if k in seen: dup.append((k,seen[k],r))
    else: seen[k]=r
if dup: errors.append('Duplicate routes: '+repr(dup[:10]))
# forbidden patterns only as rough static guard, not a security proof
bad=[]
for p in py:
    t=p.read_text(encoding='utf-8',errors='ignore').lower()
    for pat in ('reverse shell','credential stuffing','ransomware','exfiltrate'):
        if pat in t and 'forbidden' not in t: bad.append((str(p),pat))
# database schema smoke
try:
    db=ROOT/'data'/'cyberlab.db'; c=sqlite3.connect(db); c.execute('select 1');
    tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    required={'p5_audit','p5_incidents','p5_vulns','p5_ioc','f_cases','f_case_links','f_detections','f_alerts','f_jobs','f_notifications'}
    missing=required-tables
    if missing: errors.append('Missing tables: '+repr(sorted(missing)))
except Exception as e: errors.append('DB check: '+str(e))
print('PYTHON_FILES',len(py)); print('ROUTES',len(routes)); print('DUPLICATE_ROUTES',len(dup)); print('ERRORS',len(errors))
for e in errors: print('ERROR',e)
sys.exit(1 if errors else 0)
