#!/usr/bin/env python3
"""Procura segredos esquecidos no código ANTES de você fazer commit/deploy.

Uso:  python scripts/check_secrets.py [pasta]      (padrão: pasta do projeto)
Sai com código 1 se achar algo — serve como hook de pre-commit:
  printf '#!/bin/sh\\npython scripts/check_secrets.py\\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
O valor encontrado é mostrado mascarado (nunca inteiro).
"""
import re
import sys
from pathlib import Path

PATTERNS = {
    "OpenRouter/OpenAI (sk-...)": r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{24,}",
    "Groq (gsk_...)": r"\bgsk_[A-Za-z0-9]{24,}",
    "Google API (AIza...)": r"\bAIza[0-9A-Za-z_-]{30,}",
    "GitHub token": r"\b(?:ghp|gho|ghs)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}",
    "Hugging Face (hf_...)": r"\bhf_[A-Za-z0-9]{30,}",
    "Cerebras (csk-...)": r"\bcsk-[A-Za-z0-9]{24,}",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Slack token": r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
    "Chave privada": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "Atribuição suspeita": r"(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d|senha)\b\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']",
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "data", "sites", ".venv", "venv"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".db", ".zip", ".woff", ".woff2", ".pdf"}
PLACEHOLDER = re.compile(r"(?i)\.\.\.|x{4,}|example|exemplo|seu[_-]|your[_-]|changeme|<.*>|\{\{|\$\{|os\.getenv")


def mask(v):
    return v[:4] + "***" + f"({len(v)} chars)"


def scan(root: Path):
    hits = []
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() in SKIP_SUFFIX or SKIP_DIRS & set(f.relative_to(root).parts):
            continue
        if f.name in {".env.example", "check_secrets.py"} or f.stat().st_size > 2_000_000:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for label, pat in PATTERNS.items():
                m = re.search(pat, line)
                if m and not PLACEHOLDER.search(line):
                    hits.append((f.relative_to(root), n, label, mask(m.group(0))))
    return hits


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    found = scan(base)
    for path, n, label, val in found:
        print(f"{path}:{n}  {label}  {val}")
    print(f"\n{len(found)} possível(is) segredo(s) encontrado(s)." if found else "Nenhum segredo encontrado.")
    sys.exit(1 if found else 0)
