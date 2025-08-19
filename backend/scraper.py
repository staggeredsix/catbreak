"""Utilities for collecting and rating feel‑good news articles.

The module caches processed URLs in a small SQLite database to avoid
duplicating work. Articles are fetched and scored before being returned to
the caller.

Earlier versions queried the Tavily API using GET requests or through direct
``httpx`` calls which yielded ``405 Method Not Allowed`` responses. Tavily
requires POST requests with specific headers, so we now invoke the endpoint
via the system ``curl`` command and send the JSON payload manually.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
from typing import List, Tuple

from newspaper import Article as NewsArticle

# ---------------------------------------------------------------------------
# Configuration & logging
# ---------------------------------------------------------------------------

DB_PATH = "cache.db"
logger = logging.getLogger("backend.scraper")

_tavily_api_key = os.getenv(
    "TAVILY_API_KEY", "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"
)


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Initialise the SQLite database used for caching processed URLs."""

    logger.info("Initializing SQLite cache database at %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS watched (
            url TEXT PRIMARY KEY,
            watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def is_watched(url: str) -> bool:
    """Return ``True`` if ``url`` has already been processed."""

    logger.debug("Checking if URL has been watched: %s", url)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM watched WHERE url = ?", (url,))
    found = cur.fetchone() is not None
    conn.close()
    return found


def mark_watched(url: str) -> None:
    """Persist ``url`` in the cache so we do not process it again."""

    logger.info("Marking URL as watched: %s", url)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO watched (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tavily search helper
# ---------------------------------------------------------------------------


def tavily_search(query: str, max_results: int = 30) -> List[str]:
    """Search Tavily for ``query`` and return a list of result URLs."""

    logger.info(
        "Performing Tavily search for query: %s (max %d results)", query, max_results
    )
    payload = {
        "query": query,
        "topic": "general",
        "search_depth": "basic",
        "max_results": max_results,
    }
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--request",
        "POST",
        "--url",
        "https://api.tavily.com/search",
        "--header",
        f"Authorization: Bearer {_tavily_api_key}",
        "--header",
        "Content-Type: application/json",
        "--data",
        json.dumps(payload),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=True
        )
        data = json.loads(result.stdout or "{}")
        urls = [r["url"] for r in data.get("results", [])]
        logger.debug("Tavily returned %d URLs", len(urls))
        return urls
    except subprocess.CalledProcessError as exc:  # pragma: no cover - curl errors
        logger.error("Tavily curl call failed: %s", exc)
    except json.JSONDecodeError:  # pragma: no cover - bad response
        logger.exception("Failed to decode Tavily response")
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error while querying Tavily")
    return []


# ---------------------------------------------------------------------------
# Article fetching & rating
# ---------------------------------------------------------------------------


def fetch_article(url: str) -> Tuple[str, str]:
    """Download and parse an article using ``newspaper3k``.

    Returns a tuple ``(title, summary)``.
    """

    logger.info("Fetching article from URL: %s", url)
    article = NewsArticle(url)
    article.download()
    article.parse()
    article.nlp()
    logger.debug("Fetched article – title: %s", article.title[:60])
    return article.title, article.summary


def rate_article(content: str) -> int:
    """Very naive "feel‑good" scorer.

    Positive words add points, negative words subtract.
    Result is clamped to the range 1‑10.
    """

    positives = [
        "help",
        "kind",
        "success",
        "hope",
        "inspire",
        "joy",
        "uplift",
        "community",
        "cure",
        "breakthrough",
    ]

    negatives = ["war", "crime", "death", "disaster", "crisis", "fail", "tragedy"]
    content_lc = content.lower()
    score = sum(word in content_lc for word in positives) - sum(
        word in content_lc for word in negatives
    )
    rating = max(1, min(10, score + 5))
    logger.debug("Rating article – score: %d, final rating: %d", score, rating)
    return rating


def get_few_good_articles() -> List[dict]:
    """Return up to five feel‑good articles with basic metadata."""

    logger.info("Fetching a fresh batch of feel‑good articles")
    init_db()
    query = "feel good news positive uplifting recent"
    urls = tavily_search(query, max_results=30)

    articles: List[dict] = []
    for url in urls:
        if is_watched(url):
            logger.debug("Skipping already‑watched URL: %s", url)
            continue
        try:
            title, summary = fetch_article(url)
            rating = rate_article(summary)
            articles.append(
                {"title": title, "summary": summary, "url": url, "rating": rating}
            )
            mark_watched(url)
            logger.info("Collected article %d – %s", len(articles), title[:60])
        except Exception:  # pragma: no cover – individual failures are expected
            logger.exception("Failed to process URL %s", url)
            continue
        if len(articles) >= 5:
            break

    if len(articles) < 5:
        logger.warning(
            "Only %d articles were collected; fewer than the desired 5.", len(articles)
        )
        # In a real project you might fallback to cached data here.

    return articles


__all__ = [
    "fetch_article",
    "get_few_good_articles",
    "init_db",
    "is_watched",
    "mark_watched",
    "rate_article",
    "tavily_search",
]

