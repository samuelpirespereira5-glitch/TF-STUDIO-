import json
import shutil
from datetime import datetime
from pathlib import Path
from services import security

from .utils import safe_name, now_text, netlify_command, run_command, extract_json, find_urls

BASE_DIR = Path(__file__).resolve().parent.parent
SITES_DIR = BASE_DIR / "sites"
SITES_DIR.mkdir(exist_ok=True)


def new_site_folder(name):
    slug = safe_name(name)
    folder = SITES_DIR / slug
    if folder.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        folder = SITES_DIR / f"{slug}-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "assets").mkdir(exist_ok=True)
    return folder


def save_metadata(folder, data):
    path = Path(folder) / "site.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_metadata(folder):
    path = Path(folder) / "site.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["slug"] = Path(folder).name
        return data
    except Exception:
        return None


def list_sites():
    sites = []
    for folder in sorted(SITES_DIR.iterdir()):
        if folder.is_dir():
            meta = load_metadata(folder)
            if meta:
                sites.append(meta)
    sites.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sites


def get_site(slug):
    folder = SITES_DIR / slug
    if not folder.exists():
        return None
    return load_metadata(folder)


def duplicate_site(slug):
    site = get_site(slug)
    if not site:
        raise RuntimeError("Site não encontrado.")
    src = SITES_DIR / slug
    new_slug = f"{slug}-copia-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    dst = SITES_DIR / new_slug
    shutil.copytree(src, dst)

    meta = load_metadata(dst)
    meta["netlify_site_id"] = ""
    meta["netlify_url"] = ""
    meta["netlify_slug"] = ""
    meta["updated_at"] = now_text()
    meta.pop("slug", None)
    save_metadata(dst, meta)
    return new_slug


def delete_site(slug):
    folder = SITES_DIR / slug
    if folder.exists():
        shutil.rmtree(folder)


def copy_assets_and_replace(html, assets_folder, logo=None, cover=None, gallery=None):
    """Salva em assets/ os arquivos já lidos em memória (tuplas
    (nome_do_arquivo, bytes)) e troca os tokens ASSET_* pelo caminho
    relativo real. Recebe bytes prontos (e não FileStorage) de propósito:
    o Flask fecha/apaga os arquivos temporários da requisição assim que
    ela termina, e essa função roda depois, numa thread em segundo
    plano — então os bytes precisam já ter sido lidos antes."""
    gallery = gallery or []

    def save(item, base_name):
        if not item:
            return ""
        filename, content = item
        if not filename or not content:
            return ""
        suffix = security.image_extension_from_bytes(content)
        out_name = security.random_asset_name(base_name, suffix)
        assets_root = Path(assets_folder).resolve()
        dest = assets_root / out_name
        if assets_root not in dest.parents:
            raise ValueError("Caminho de upload inválido.")
        dest.write_bytes(content)
        return f"assets/{out_name}"

    logo_path = save(logo, "logo")
    cover_path = save(cover, "cover")

    gallery_paths = []
    for i, item in enumerate(gallery[:8], start=1):
        path = save(item, f"gallery-{i}")
        if path:
            gallery_paths.append(path)

    if logo_path:
        html = html.replace("ASSET_LOGO", logo_path)
    if cover_path:
        html = html.replace("ASSET_COVER", cover_path)
    for i, image in enumerate(gallery_paths, start=1):
        html = html.replace(f"ASSET_GALLERY_{i}", image)

    return html


def zip_site(slug):
    folder = SITES_DIR / slug
    if not folder.exists():
        raise RuntimeError("Site não encontrado.")
    zip_base = BASE_DIR / "tmp_downloads" / slug
    zip_base.parent.mkdir(parents=True, exist_ok=True)
    zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=folder)
    return zip_path


# ------------------------------------------------------------------
# Publicação no Netlify (usa o Netlify CLI já logado no servidor)
# ------------------------------------------------------------------

def publish_to_netlify(slug, status_cb=None):
    def report(msg):
        if status_cb:
            status_cb(msg)

    netlify = netlify_command()
    if not netlify:
        raise RuntimeError(
            "Netlify CLI não encontrado no servidor. Instale com: "
            "npm install -g netlify-cli   e depois rode: netlify login"
        )

    folder = SITES_DIR / slug
    if not folder.exists() or not (folder / "index.html").exists():
        raise RuntimeError("Site ou index.html não encontrado.")

    site = load_metadata(folder)
    site_id = (site.get("netlify_site_id") or "").strip()

    if not site_id:
        report("☁ Criando projeto no Netlify...")
        unique_slug = "tf-studio-" + safe_name(site["name"]) + "-" + datetime.now().strftime("%m%d%H%M%S")
        code, out, err = run_command(
            [netlify, "sites:create", "--name", unique_slug, "--json"], cwd=folder, timeout=120
        )
        combined = out + "\n" + err
        data = extract_json(combined)
        site_id = data.get("id") or data.get("site_id") or data.get("siteId") or ""

        if not site_id:
            state_file = folder / ".netlify" / "state.json"
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    site_id = state.get("siteId") or state.get("site_id") or ""
                except Exception:
                    pass

        if not site_id:
            raise RuntimeError(
                "Não consegui criar o projeto no Netlify. Verifique se "
                f"'netlify login' foi feito no servidor.\n\nDetalhes:\n{combined[-1500:]}"
            )

        site["netlify_site_id"] = site_id
        site["netlify_slug"] = unique_slug
        site_url = data.get("ssl_url") or data.get("url") or ""
        if site_url:
            site["netlify_url"] = site_url

    report("📤 Enviando arquivos para o Netlify...")
    code, out, err = run_command(
        [netlify, "deploy", "--prod", "--dir", ".", "--site", site_id, "--json"],
        cwd=folder,
        timeout=180,
    )
    combined = out + "\n" + err

    if code != 0:
        raise RuntimeError(f"O Netlify retornou um erro:\n\n{combined[-2000:]}")

    data = extract_json(combined)
    url = data.get("ssl_url") or data.get("url") or data.get("deploy_url") or site.get("netlify_url", "")
    if not url:
        for candidate in find_urls(combined):
            if "netlify.app" in candidate:
                url = candidate
                break
    if url:
        site["netlify_url"] = url.rstrip(".,);]")

    site["updated_at"] = now_text()
    site.pop("slug", None)
    save_metadata(folder, site)
    return site
