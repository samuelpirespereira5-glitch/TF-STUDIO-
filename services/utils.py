import json
import re
import shutil
import subprocess
from datetime import datetime


def safe_name(text):
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text.lower()[:45] or "meu-site"


def now_text():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def extract_json(text):
    if not text:
        return {}
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


def extract_html(text):
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^```html\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.lower().find("<!doctype html>")
    if start == -1:
        start = text.lower().find("<html")
    if start >= 0:
        text = text[start:]

    end = text.lower().rfind("</html>")
    if end >= 0:
        text = text[: end + len("</html>")]

    return text.strip()


def find_urls(text):
    if not text:
        return []
    return re.findall(r"https?://[^\s\"'<>]+", text)


def run_command(args, cwd=None, timeout=180):
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -2, "", "O comando demorou demais."
    except Exception as e:
        return -1, "", str(e)


def netlify_command():
    for candidate in (shutil.which("netlify"), shutil.which("netlify.cmd")):
        if candidate:
            return candidate
    return None
