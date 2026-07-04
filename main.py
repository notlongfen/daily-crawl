from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from gemini_uploader import (
    build_client,
    delete_document_if_present,
    get_or_create_store,
    upload_markdown_file,
)
from manifest import load_manifest, save_json, save_manifest
from markdown_cleaner import article_slug, article_to_markdown
from scraper import fetch_articles


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def write_markdown(markdown_dir: Path, article: dict[str, Any]) -> tuple[Path, str]:
    markdown = article_to_markdown(article)
    digest = sha256_text(markdown)
    filename = f"{article_slug(article)}.md"
    path = markdown_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path, digest


def main() -> None:
    print("Starting daily crawl job...")
    print("Loading environment variables...")
    load_dotenv()

    data_dir = Path(os.getenv("DATA_DIR", "data"))
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    markdown_dir = data_dir / "markdown"
    manifest_path = data_dir / "manifest.json"
    last_run_path = log_dir / "last_run.json"

    article_limit = int_env("ARTICLE_LIMIT", 50)
    max_tokens = int_env("MAX_TOKENS_PER_CHUNK", 512)
    max_overlap = int_env("MAX_OVERLAP_TOKENS", 64)

    base_url = os.getenv("SUPPORT_BASE_URL", "https://support.optisigns.com")
    locale = os.getenv("HELP_CENTER_LOCALE", "en-us")

    print(f"Base URL: {base_url}")
    manifest = load_manifest(manifest_path)
    articles = fetch_articles(base_url=base_url, locale=locale, limit=article_limit)

    client = build_client()
    store_name = get_or_create_store(client, data_dir)

    added = 0
    updated = 0
    skipped = 0
    uploaded = 0
    deleted_old_documents = 0
    estimated_chunks = 0
    upload_errors: list[dict[str, str]] = []

    for article in articles:
        print(f"Processing article: {article.get('title')} (ID: {article.get('id')})")
        article_id = str(article.get("id"))
        md_path, digest = write_markdown(markdown_dir, article)
        previous = manifest.get(article_id)

        if previous and previous.get("hash") == digest:
            print(f"Skipping article {article_id} (no changes detected)")
            skipped += 1
            continue

        status = "added" if previous is None else "updated"
        if status == "added":
            added += 1
        else:
            updated += 1
            if delete_document_if_present(client, previous.get("document_name")):
                deleted_old_documents += 1

        try:
            print(f"Uploading markdown file for article {article_id} to Gemini File Search store '{store_name}'...")
            upload_result = upload_markdown_file(
                client=client,
                store_name=store_name,
                path=md_path,
                max_tokens_per_chunk=max_tokens,
                max_overlap_tokens=max_overlap,
            )
            uploaded += 1
            estimated_chunks += int(upload_result.get("estimated_chunks", 0))

            manifest[article_id] = {
                "title": article.get("title"),
                "url": article.get("html_url") or article.get("url"),
                "updated_at": article.get("updated_at"),
                "hash": digest,
                "markdown_path": str(md_path),
                "document_name": upload_result.get("document_name"),
                "last_uploaded_at": now_iso(),
            }
        except Exception as exc:
            upload_errors.append({"article_id": article_id, "file": str(md_path), "error": str(exc)})

    save_manifest(manifest_path, manifest)

    run_log = {
        "ran_at": now_iso(),
        "store_name": store_name,
        "articles_seen": len(articles),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "uploaded_files": uploaded,
        "deleted_old_documents": deleted_old_documents,
        "estimated_chunks_embedded": estimated_chunks,
        "chunking": {
            "max_tokens_per_chunk": max_tokens,
            "max_overlap_tokens": max_overlap,
        },
        "errors": upload_errors,
    }
    save_json(last_run_path, run_log)

    print(run_log)

    if upload_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
