import os
import logging
import shutil
import subprocess
import threading
import time
import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter
import bleach
import markdown
from flask import Flask, abort, render_template, send_from_directory
from markupsafe import Markup
from werkzeug.utils import safe_join


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPO_DIR = DATA_DIR / "source"
PUBLIC_DIR = DATA_DIR / "public"
POSTS_PUBLIC_DIR = PUBLIC_DIR / "posts"
ASSETS_PUBLIC_DIR = PUBLIC_DIR / "assets"
CONTENT_DIR = BASE_DIR / "content"
MARKDOWN_EXTENSIONS = [
    "extra",
    "fenced_code",
    "sane_lists",
    "smarty",
    "toc",
    "pymdownx.highlight",
    "pymdownx.tasklist",
    "pymdownx.superfences",
    "pymdownx.tilde",
]
MARKDOWN_EXTENSION_CONFIGS = {
    "pymdownx.highlight": {
        "use_pygments": True,
        "css_class": "codehilite",
    },
    "pymdownx.tasklist": {"custom_checkbox": True},
}
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {
        "p",
        "pre",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "img",
        "span",
        "div",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "code",
        "input",
        "label",
    }
)
ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "input": ["type", "checked", "disabled"],
    "label": ["class"],
    "span": ["class"],
    "div": ["class"],
    "code": ["class"],
    "pre": ["class"],
}


def env_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass
class Settings:
    site_title: str = os.getenv("SITE_TITLE", "Maker's Diary")
    site_description: str = os.getenv(
        "SITE_DESCRIPTION",
        "A blog generated from an Obsidian-style markdown repository.",
    )
    site_description_file: str = os.getenv("SITE_DESCRIPTION_FILE", "content/site-description.md")
    repository_url: str = os.getenv("DIARY_REPOSITORY_URL", "").strip()
    repository_branch: str = os.getenv("DIARY_BRANCH", "main").strip()
    sync_interval_seconds: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
    posts_path: str = os.getenv("POSTS_PATH", ".").strip() or "."
    asset_directories: list[str] = None
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))

    def __post_init__(self) -> None:
        if self.asset_directories is None:
            self.asset_directories = env_list("ASSET_DIRECTORIES", "pasted images")


settings = Settings()
app = Flask(__name__)
content_lock = threading.Lock()
sync_lock = threading.Lock()
sync_started = False
content_cache: dict[str, Any] = {
    "posts": [],
    "posts_by_slug": {},
    "last_sync": None,
    "last_error": None,
}


def run_git(*args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=REPO_DIR if REPO_DIR.exists() else None,
        check=True,
        capture_output=True,
        text=True,
    )


def ensure_repo() -> None:
    if not settings.repository_url:
        raise RuntimeError("DIARY_REPOSITORY_URL is required.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not REPO_DIR.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                settings.repository_branch,
                settings.repository_url,
                str(REPO_DIR),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    run_git("fetch", "origin", settings.repository_branch, "--depth", "1")
    run_git("checkout", settings.repository_branch)
    run_git("reset", "--hard", f"origin/{settings.repository_branch}")
    run_git("clean", "-fd")


def slugify(path: Path) -> str:
    return str(path.with_suffix("")).replace("\\", "/").replace(" ", "-").lower()


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def replace_obsidian_embeds(text: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        file_name = Path(target).name
        return f"![{file_name}](/assets/{file_name})"

    return re.sub(r"!\[\[(.+?)\]\]", replacement, text)


def build_post_link_index(relative_paths: list[Path]) -> dict[str, str]:
    link_index: dict[str, str] = {}
    basename_to_slug: dict[str, str | None] = {}

    for relative_path in relative_paths:
        slug = slugify(relative_path)
        with_suffix = relative_path.as_posix().lower()
        without_suffix = relative_path.with_suffix("").as_posix().lower()
        basename = relative_path.name.lower()
        stem = relative_path.stem.lower()

        link_index[with_suffix] = slug
        link_index[without_suffix] = slug
        basename_to_slug[basename] = (
            slug if basename not in basename_to_slug else None
        )
        basename_to_slug[stem] = slug if stem not in basename_to_slug else None

    for key, slug in basename_to_slug.items():
        if slug:
            link_index[key] = slug

    return link_index


def resolve_post_target(
    target: str,
    source_relative_path: Path | None,
    link_index: dict[str, str] | None,
) -> str | None:
    if not link_index:
        return None

    candidate = target.strip()
    if not candidate:
        return None
    if "://" in candidate or candidate.startswith(("mailto:", "#", "/assets/")):
        return None

    fragment = ""
    if "#" in candidate:
        candidate, fragment_part = candidate.split("#", 1)
        fragment = f"#{fragment_part}"

    normalized = candidate.replace("\\", "/").strip()
    if not normalized:
        return None

    path_candidate = Path(normalized.lstrip("/"))
    candidate_keys: list[str] = []

    if source_relative_path and not normalized.startswith("/"):
        source_dir = source_relative_path.parent
        resolved = (source_dir / path_candidate).as_posix().lower()
        candidate_keys.append(resolved)
        candidate_keys.append(Path(resolved).with_suffix("").as_posix().lower())

    as_posix = path_candidate.as_posix().lower()
    candidate_keys.append(as_posix)
    candidate_keys.append(Path(as_posix).with_suffix("").as_posix().lower())
    candidate_keys.append(path_candidate.name.lower())
    candidate_keys.append(path_candidate.stem.lower())

    for key in dict.fromkeys(candidate_keys):
        slug = link_index.get(key)
        if slug:
            return f"/posts/{slug}/{fragment}"

    return None


def replace_obsidian_links(
    text: str,
    source_relative_path: Path | None,
    link_index: dict[str, str] | None,
) -> str:
    def replacement(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        target, separator, label = raw_target.partition("|")
        href = resolve_post_target(target, source_relative_path, link_index)
        if not href:
            return match.group(0)

        if separator:
            link_text = label.strip() or Path(target).stem
        else:
            display_target = target.split("#", 1)[0].rstrip("/")
            link_text = Path(display_target).stem or display_target

        return f'<a href="{html.escape(href, quote=True)}">{html.escape(link_text)}</a>'

    return re.sub(r"(?<!!)\[\[([^\]]+)\]\]", replacement, text)


def rewrite_markdown_file_links(
    rendered_html: str,
    source_relative_path: Path | None,
    link_index: dict[str, str] | None,
) -> str:
    def replacement(match: re.Match[str]) -> str:
        quote = match.group(1)
        href = html.unescape(match.group(2))
        if not href.lower().endswith((".md", ".markdown")) and ".md#" not in href.lower():
            return match.group(0)

        resolved = resolve_post_target(href, source_relative_path, link_index)
        if not resolved:
            return match.group(0)

        return f'href={quote}{html.escape(resolved, quote=True)}{quote}'

    return re.sub(r'href=(["\'])(.+?)\1', replacement, rendered_html)


def render_markdown(
    text: str,
    source_relative_path: Path | None = None,
    link_index: dict[str, str] | None = None,
) -> str:
    processed = replace_obsidian_embeds(text)
    processed = replace_obsidian_links(processed, source_relative_path, link_index)
    rendered = markdown.markdown(
        processed,
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
        output_format="html5",
    )
    rendered = rewrite_markdown_file_links(rendered, source_relative_path, link_index)
    return bleach.clean(rendered, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


def get_site_description_text() -> str:
    description_path = Path(settings.site_description_file)
    if not description_path.is_absolute():
        description_path = BASE_DIR / description_path

    if description_path.exists():
        return description_path.read_text(encoding="utf-8")

    return settings.site_description


def load_site_description() -> Markup:
    return Markup(render_markdown(get_site_description_text()))


@app.context_processor
def inject_site_description() -> dict[str, Any]:
    site_description_html = load_site_description()
    site_description_text = bleach.clean(
        get_site_description_text(),
        tags=[],
        strip=True,
    ).replace("\n", " ").strip()
    return {
        "site_description_html": site_description_html,
        "site_description_text": site_description_text or settings.site_description,
    }


def copy_tree_contents(source: Path, destination: Path) -> None:
    if not source.exists():
        return

    for item in source.rglob("*"):
        if item.is_dir():
            continue
        relative_path = item.relative_to(source)
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def build_content() -> dict[str, Any]:
    repo_posts_dir = (REPO_DIR / settings.posts_path).resolve()
    if not repo_posts_dir.exists():
        raise RuntimeError(f"POSTS_PATH does not exist inside the repository: {settings.posts_path}")

    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    POSTS_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    for asset_dir in settings.asset_directories:
        copy_tree_contents(REPO_DIR / asset_dir, ASSETS_PUBLIC_DIR)

    posts: list[dict[str, Any]] = []
    posts_by_slug: dict[str, dict[str, Any]] = {}
    skipped_directories = {Path(asset_dir).parts[0] for asset_dir in settings.asset_directories}
    discovered_posts: list[tuple[Path, frontmatter.Post, Path, str]] = []

    for path in sorted(repo_posts_dir.rglob("*.md")):
        if any(part.startswith(".") for part in path.parts):
            continue
        if skipped_directories.intersection(path.relative_to(repo_posts_dir).parts):
            continue

        relative_path = path.relative_to(repo_posts_dir)
        slug = slugify(relative_path)
        discovered_posts.append((path, frontmatter.load(path), relative_path, slug))

    link_index = build_post_link_index([relative_path for _, _, relative_path, _ in discovered_posts])

    for path, post, relative_path, slug in discovered_posts:
        created = normalize_date(post.metadata.get("created"))
        html = render_markdown(post.content, relative_path, link_index)
        output_path = POSTS_PUBLIC_DIR / f"{slug}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        title = post.metadata.get("title") or path.stem
        tags = post.metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        entry = {
            "slug": slug,
            "title": title,
            "created": created,
            "created_display": created.isoformat() if created else "Unknown date",
            "tags": tags,
            "content": Markup(html),
            "source_path": str(path.relative_to(REPO_DIR)).replace("\\", "/"),
        }
        posts.append(entry)
        posts_by_slug[slug] = entry

    posts.sort(key=lambda item: (item["created"] or date.min, item["title"].lower()), reverse=True)
    return {"posts": posts, "posts_by_slug": posts_by_slug}


def sync_once() -> None:
    ensure_repo()
    result = build_content()
    with content_lock:
        content_cache.update(result)
        content_cache["last_sync"] = datetime.now().isoformat(timespec="seconds")
        content_cache["last_error"] = None


def sync_loop() -> None:
    while True:
        try:
            sync_once()
        except Exception as exc:  # pragma: no cover
            logging.exception("Background sync failed")
            with content_lock:
                content_cache["last_error"] = str(exc)
        time.sleep(settings.sync_interval_seconds)


def start_sync() -> None:
    global sync_started
    with sync_lock:
        if sync_started:
            return
        sync_started = True

    try:
        sync_once()
    except Exception as exc:  # pragma: no cover
        logging.exception("Initial sync failed")
        with content_lock:
            content_cache["last_error"] = str(exc)

    threading.Thread(target=sync_loop, daemon=True).start()


@app.route("/")
def index():
    with content_lock:
        posts = list(content_cache["posts"])
    return render_template(
        "index.html",
        posts=posts,
        settings=settings,
    )


@app.route("/posts/<path:slug>/")
def post_detail(slug: str):
    with content_lock:
        post = content_cache["posts_by_slug"].get(slug)
    if not post:
        abort(404)
    return render_template("post.html", post=post, settings=settings)


@app.route("/assets/<path:asset_path>")
def assets(asset_path: str):
    full_path = safe_join(str(ASSETS_PUBLIC_DIR), asset_path)
    if not full_path:
        abort(404)
    return send_from_directory(ASSETS_PUBLIC_DIR, asset_path)


@app.route("/healthz")
def healthcheck():
    with content_lock:
        status = {
            "posts": len(content_cache["posts"]),
            "last_sync": content_cache["last_sync"],
            "last_error": content_cache["last_error"],
        }
    return status


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    start_sync()
    app.run(host=settings.host, port=settings.port, debug=False)
