#!/usr/bin/env python3
"""Security dependency gate: reports vulnerable packages without changing them."""
import subprocess
import sys

def main():
    cmd=[sys.executable,"-m","pip_audit","-r","requirements.txt","--format","json"]
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("pip-audit não está instalado. Rode: python -m pip install -r requirements.txt", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
