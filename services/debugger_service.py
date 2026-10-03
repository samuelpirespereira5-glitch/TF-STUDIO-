"""Analisa o index.html de um site em busca de problemas reais.

Tudo aqui é checagem estática de verdade (não é a IA "chutando" que
pode haver um erro): olha o HTML, o CSS e o JS que estão realmente no
arquivo e compara com o que existe em disco (ex: assets/ do site).
"""
import re
from html.parser import HTMLParser

# Tags que não precisam ser fechadas (elementos "void" do HTML5).
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr", "!doctype",
}


class _TagTracker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.unclosed = []
        self.seen_ids = {}
        self.duplicate_ids = []
        self.img_srcs = []  # (src, has_alt)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if "id" in attrs_dict and attrs_dict["id"]:
            _id = attrs_dict["id"]
            self.seen_ids[_id] = self.seen_ids.get(_id, 0) + 1
            if self.seen_ids[_id] == 2:
                self.duplicate_ids.append(_id)
        if tag == "img":
            self.img_srcs.append((attrs_dict.get("src", ""), bool(attrs_dict.get("alt"))))
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        # <tag ... /> — não empilha, já é auto-fechada
        pass

    def handle_endtag(self, tag):
        if tag in self.stack:
            # remove a ocorrência mais recente dessa tag da pilha
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] == tag:
                    del self.stack[i]
                    break

    def close(self):
        super().close()
        self.unclosed = self.stack[:]


def _check_js_balance(js_code):
    """Checagem heurística (não é um parser de JS de verdade): conta
    chaves/parênteses/colchetes fora de strings e comentários. Serve
    para pegar o caso comum de uma edição de IA cortar o código no
    meio, não para validar JS 100% corretamente."""
    depth = {"{": 0, "(": 0, "[": 0}
    pairs = {"}": "{", ")": "(", "]": "["}
    in_string = None
    in_line_comment = False
    in_block_comment = False
    i = 0
    n = len(js_code)
    while i < n:
        c = js_code[i]
        nxt = js_code[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if c == "\n":
                in_line_comment = False
        elif in_block_comment:
            if c == "*" and nxt == "/":
                in_block_comment = False
                i += 1
        elif in_string:
            if c == "\\":
                i += 1
            elif c == in_string:
                in_string = None
        else:
            if c == "/" and nxt == "/":
                in_line_comment = True
                i += 1
            elif c == "/" and nxt == "*":
                in_block_comment = True
                i += 1
            elif c in ("'", '"', "`"):
                in_string = c
            elif c in depth:
                depth[c] += 1
            elif c in pairs:
                depth[pairs[c]] -= 1
        i += 1
    return {k: v for k, v in depth.items() if v != 0}


def analyze_site(folder):
    """Retorna uma lista de problemas encontrados no index.html deste
    site. Cada item: {severidade, tipo, descricao}."""
    issues = []
    index_path = folder / "index.html"
    if not index_path.exists():
        return [{"severidade": "alto", "tipo": "arquivo", "descricao": "index.html não encontrado."}]

    html = index_path.read_text(encoding="utf-8")
    assets_dir = folder / "assets"

    # 1) Imagens locais que apontam para arquivo inexistente
    tracker = _TagTracker()
    try:
        tracker.feed(html)
        tracker.close()
    except Exception:
        pass

    for src, has_alt in tracker.img_srcs:
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        rel = src.split("assets/")[-1] if "assets/" in src else src
        candidate = assets_dir / rel
        if not candidate.exists():
            issues.append({
                "severidade": "alto",
                "tipo": "imagem quebrada",
                "descricao": f'A imagem "{src}" é referenciada no HTML mas o arquivo não existe em assets/.',
            })
        elif not has_alt:
            issues.append({
                "severidade": "baixo",
                "tipo": "acessibilidade",
                "descricao": f'A imagem "{src}" não tem atributo alt.',
            })

    # 2) IDs duplicados
    for dup in tracker.duplicate_ids:
        issues.append({
            "severidade": "médio",
            "tipo": "html inválido",
            "descricao": f'O id "{dup}" aparece mais de uma vez no HTML (ids devem ser únicos).',
        })

    # 3) Tags não fechadas
    if tracker.unclosed:
        contagem = {}
        for t in tracker.unclosed:
            contagem[t] = contagem.get(t, 0) + 1
        for tag, qtd in contagem.items():
            issues.append({
                "severidade": "alto",
                "tipo": "html inválido",
                "descricao": f'{qtd}x <{tag}> aberta(s) sem a tag de fechamento correspondente.',
            })

    # 4) JS com chaves/parênteses/colchetes desbalanceados
    for script_match in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", html, re.IGNORECASE):
        js = script_match.group(1)
        if not js.strip():
            continue
        unbalanced = _check_js_balance(js)
        if unbalanced:
            partes = ", ".join(f"{simbolo} (diferença de {qtd})" for simbolo, qtd in unbalanced.items())
            issues.append({
                "severidade": "alto",
                "tipo": "javascript",
                "descricao": f"Um bloco <script> parece ter símbolos desbalanceados: {partes}. Isso geralmente quebra o JavaScript da página.",
            })

    # 5) Links wa.me/mailto vazios (href="" ou só "#")
    for m in re.finditer(r'href=["\'](#|)["\']', html):
        issues.append({
            "severidade": "baixo",
            "tipo": "link vazio",
            "descricao": 'Existe um link (href="" ou href="#") sem destino real.',
        })
        break  # um aviso já basta, não repete pra cada ocorrência

    return issues


def format_issues_for_prompt(issues):
    if not issues:
        return "Nenhum problema encontrado."
    lines = []
    for it in issues:
        lines.append(f"- [{it['severidade'].upper()}] ({it['tipo']}) {it['descricao']}")
    return "\n".join(lines)
