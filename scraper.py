from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import requests


class ScrapeError(RuntimeError):
    pass


def fetch_articles(
    base_url: str = "https://support.optisigns.com",
    locale: str = "en-us",
    limit: int = 50,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Fetch public Zendesk Help Center articles.

    Uses Zendesk's Help Center Articles API, not browser scraping. This avoids nav,
    cookie banners, and ads while still pulling real article HTML bodies.
    """
    url = urljoin(base_url.rstrip("/") + "/", f"api/v2/help_center/{locale}/articles.json")
    params = {"per_page": 100}
    articles: list[dict[str, Any]] = []

    while url and len(articles) < limit:
        response = requests.get(
            url,
            params=params if "?" not in url else None,
            timeout=timeout,
            headers={"User-Agent": "daily-crawl/1.0"},
        )
        if response.status_code != 200:
            raise ScrapeError(f"Failed to fetch articles: HTTP {response.status_code} {response.text[:200]}")

        print(f"Fetched {len(articles)} articles so far; next page: {url}")
        payload = response.json()
        page_articles = payload.get("articles", [])
        articles.extend(page_articles)
        url = payload.get("next_page")
        params = None

        time.sleep(0.2)

    return articles[:limit]
