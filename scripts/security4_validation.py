"""Deterministic validation for JARVIS Security + Authentication 4.0.
Only claims PASS for checks actually executed in this script.
"""
from pathlib import Path
import ast
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
errors=[]

def check(name, fn):
    try:
        ok,msg=fn()
        print(f"{'PASS' if ok else 'FAIL'} {name}: {msg}")
        if not ok: errors.append(name)
    except Exception as exc:
        print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        errors.append(name)

def ast_all():
    files=list(ROOT.rglob('*.py'))
    for p in files: ast.parse(p.read_text(encoding='utf-8',errors='replace'))
    return True, f'{len(files)} Python files parsed'

def js_check():
    js=list((ROOT/'static').rglob('*.js'))
    for p in js:
        r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True)
        if r.returncode: return False,f'{p.relative_to(ROOT)}: {r.stderr[:300]}'
    return True,f'{len(js)} JS files parsed by Node'

def routes_check():
    text=(ROOT/'routes_cyber.py').read_text(encoding='utf-8')
    required=['/api/account/security4','/api/cyber/security4/checkup','/api/cyber/security4/audit','/security-4']
    return all(x in text for x in required), 'required Security 4 routes present'

def service_check():
    from services import security4
    uid='__security4_validation__'
    # Start from a clean test identity.
    with security4.conn() as c:
        c.execute('DELETE FROM s4_audit WHERE uid=?',(uid,))
        c.execute('DELETE FROM s4_notifications WHERE uid=?',(uid,))
        c.execute('DELETE FROM s4_incidents WHERE uid=?',(uid,))
        c.execute('DELETE FROM s4_evidence WHERE uid=?',(uid,))
        c.execute('DELETE FROM s4_preferences WHERE uid=?',(uid,))
    security4.notify(uid,'test','Validation','Synthetic test notification','info')
    inc=security4.create_incident(uid,'Validation incident','Synthetic only','low')
    security4.update_incident(uid,inc['id'],'investigating','medium')
    ev=security4.add_evidence(uid,inc['id'],'sample.log',b'JARVIS-S4-TEST',source='validation')
    integ=security4.verify_integrity()
    assert ev['sha256']
    assert integ['ok']
    assert security4.notifications(uid)
    assert security4.incidents(uid)[0]['status']=='investigating'
    # Cleanup synthetic state.
    with security4.conn() as c:
        for table in ('s4_audit','s4_notifications','s4_incidents','s4_evidence','s4_preferences'):
            c.execute(f'DELETE FROM {table} WHERE uid=?',(uid,))
    return True,'audit chain, notifications, incidents, evidence hash and cleanup executed'

def secret_fields_check():
    s=(ROOT/'services/security4.py').read_text(encoding='utf-8')
    forbidden=['MASTER_PASSWORD =','API_KEY =','PRIVATE_KEY =']
    return not any(x in s for x in forbidden),'no hard-coded secret assignment patterns found'

check('PYTHON AST',ast_all)
check('JAVASCRIPT SYNTAX',js_check)
check('ROUTE INVENTORY',routes_check)
check('SECURITY4 SERVICE SMOKE',service_check)
check('NO HARDCODED SECRET PATTERNS',secret_fields_check)
print(f'FINAL: {"PASS" if not errors else "FAIL"}; failed={len(errors)}')
raise SystemExit(1 if errors else 0)
