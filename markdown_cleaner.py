from __future__ import annotations

import re
from html import unescape
from typing import Any

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from slugify import slugify


def clean_html_to_markdown(html: str) -> str:
    """Convert Zendesk article HTML body to readable Markdown."""
    soup = BeautifulSoup(html or "", "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    for pre in soup.find_all("pre"):
        text = pre.get_text("\n")
        pre.string = text.strip("\n")

    markdown = md(str(soup), heading_style="ATX", bullets="-")
    markdown = unescape(markdown)

    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = markdown.strip()
    return markdown


def article_slug(article: dict[str, Any]) -> str:
    title = article.get("title") or f"article-{article.get('id', 'unknown')}"
    slug = slugify(title, lowercase=True, max_length=90)
    article_id = article.get("id")
    return f"{slug}-{article_id}" if article_id else slug


def article_to_markdown(article: dict[str, Any]) -> str:
    title = article.get("title", "Untitled Article").strip()
    article_id = article.get("id", "")
    updated_at = article.get("updated_at", "")
    url = article.get("html_url") or article.get("url") or ""
    body_md = clean_html_to_markdown(article.get("body", ""))

    return f"""---
title: {title}
article_id: {article_id}
updated_at: {updated_at}
source_url: {url}
---

# {title}

Article URL: {url}

{body_md}
""".strip() + "\n"
