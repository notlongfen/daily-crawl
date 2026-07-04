from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from google import genai

STORE_FILE = "store.json"


def get_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")


def build_client():
    if not get_api_key():
        raise RuntimeError("Missing GEMINI_API_KEY or API_KEY environment variable.")
    return genai.Client()


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _store_path(data_dir: Path) -> Path:
    return data_dir / STORE_FILE


def load_store_name(data_dir: Path) -> str | None:
    env_name = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME")
    if env_name:
        return env_name

    path = _store_path(data_dir)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("name")
    except json.JSONDecodeError:
        return None


def save_store_name(data_dir: Path, name: str, display_name: str) -> None:
    path = _store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "display_name": display_name}, indent=2),
        encoding="utf-8",
    )


def get_or_create_store(client: Any, data_dir: Path) -> str:
    existing_name = load_store_name(data_dir)
    if existing_name:
        return existing_name

    display_name = os.getenv("GEMINI_FILE_SEARCH_STORE_DISPLAY_NAME", "daily-crawl-store")

    try:
        for store in client.file_search_stores.list():
            if _get_attr(store, "display_name", "displayName") == display_name:
                name = _get_attr(store, "name")
                if name:
                    save_store_name(data_dir, name, display_name)
                    return name
    except Exception:
        pass

    store = client.file_search_stores.create(
        config={
            "display_name": display_name,
            "embedding_model": "models/gemini-embedding-001",
        }
    )
    name = _get_attr(store, "name")
    if not name:
        raise RuntimeError(f"Could not read File Search store name from response: {store!r}")
    save_store_name(data_dir, name, display_name)
    return name


def estimate_chunks(markdown: str, max_tokens: int, overlap_tokens: int) -> int:
    """Rough local chunk estimate for logging.

    Gemini performs the actual chunking server-side. The API does not always expose
    exact chunk counts, so this estimate is used for the required run log.
    """
    words = markdown.split()
    if not words:
        return 0
    estimated_tokens = int(len(words) / 0.75) + 1
    step = max(1, max_tokens - overlap_tokens)
    return max(1, ((estimated_tokens - 1) // step) + 1)


def _wait_for_operation(client: Any, operation: Any, poll_seconds: int = 5) -> Any:
    while not _get_attr(operation, "done", default=False):
        time.sleep(poll_seconds)
        operation = client.operations.get(operation)
    error = _get_attr(operation, "error")
    if error:
        raise RuntimeError(f"Gemini File Search operation failed: {error}")
    return operation


def _extract_document_name(operation: Any) -> str | None:
    """Best-effort extraction of uploaded document resource name."""
    visited: set[int] = set()

    def walk(value: Any) -> str | None:
        if id(value) in visited:
            return None
        visited.add(id(value))

        if isinstance(value, str):
            if "/documents/" in value or value.startswith("fileSearchStores/") and "documents" in value:
                return value
            return None

        if isinstance(value, dict):
            for key in ("name", "document", "file_search_document", "fileSearchDocument"):
                if key in value:
                    found = walk(value[key])
                    if found:
                        return found
            for child in value.values():
                found = walk(child)
                if found:
                    return found
            return None

        for attr in ("response", "metadata", "name", "document"):
            if hasattr(value, attr):
                found = walk(getattr(value, attr))
                if found:
                    return found
        return None

    return walk(operation)


def delete_document_if_present(client: Any, document_name: str | None) -> bool:
    if not document_name:
        return False
    try:
        client.file_search_stores.documents.delete(name=document_name, config={"force": True})
        return True
    except Exception:
        return False


def upload_markdown_file(
    client: Any,
    store_name: str,
    path: Path,
    max_tokens_per_chunk: int,
    max_overlap_tokens: int,
) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    estimated_chunks = estimate_chunks(content, max_tokens_per_chunk, max_overlap_tokens)

    operation = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store_name,
        file=str(path),
        config={
            "display_name": path.name,
            "chunking_config": {
                "white_space_config": {
                    "max_tokens_per_chunk": max_tokens_per_chunk,
                    "max_overlap_tokens": max_overlap_tokens,
                }
            },
        },
    )
    operation = _wait_for_operation(client, operation)
    document_name = _extract_document_name(operation)

    return {
        "file": str(path),
        "document_name": document_name,
        "estimated_chunks": estimated_chunks,
    }
