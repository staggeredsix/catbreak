import httpx
from bs4 import BeautifulSoup
from newspaper import Article as NewsArticle
import sqlite3
import random
import json
import logging
from typing import List, Tuple

DB_PATH = "cache.db"

# ---------------------------------------------
# Logging for the scraper – we reuse the same logger hierarchy as the app.
# ---------------------------------------------
logger = logging.getLogger("backend.scraper")

def init_db():
    logger.info("Initializing SQLite cache database at %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS watched (
                    url TEXT PRIMARY KEY,
                    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()

def is_watched(url: str) -> bool:
    logger.debug("Checking if URL has been watched: %s", url)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM watched WHERE url = ?", (url,))
    found = cur.fetchone() is not None
    conn.close()
    return found

def mark_watched(url: str):
    logger.info("Marking URL as watched: %s", url)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO watched (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

def duckduckgo_search(query: str, max_results: int = 20) -> List[str]:
    """Lightweight DuckDuckGo HTML search – returns a list of result URLs.
    ``max_results`` caps the number of URLs returned.
    """
    logger.info("Performing DuckDuckGo search for query: %s (max %d results)", query, max_results)
    resp = httpx.get(
        "https://duckduckgo.com/html/",
        params={"q": query},
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links: List[str] = []
    for a in soup.select("a.result__a"):
        href = a.get("href")
        if href:
            links.append(href)
        if len(links) >= max_results:
            break
    logger.debug("DuckDuckGo returned %d URLs", len(links))
    return links

def fetch_article(url: str) -> Tuple[str, str]:
    """Download and parse an article via ``newspaper3k``.
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
    Positive words add points, negative words subtract. Result is clamped to 1‑10.
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
    score = sum(word in content_lc for word in positives) - sum(word in content_lc for word in negatives)
    rating = max(1, min(10, score + 5))
    logger.debug("Rating article – score: %d, final rating: %d", score, rating)
    return rating

def get_few_good_articles() -> List[dict]:
    """Entry point used by the API – returns up to 5 feel‑good articles with rating.
    The function:
    1. Ensures the DB exists.
    2. Searches DuckDuckGo.
    3. Walks the URLs, skipping any already‑watched.
    4. Fetches, rates and stores each article.
    """
    logger.info("Fetching a fresh batch of feel‑good articles")
    init_db()
    query = "feel good news positive uplifting recent"
    urls = duckduckgo_search(query, max_results=30)

    articles: List[dict] = []
    for url in urls:
        if is_watched(url):
            logger.debug("Skipping already‑watched URL: %s", url)
            continue
        try:
            title, summary = fetch_article(url)
            rating = rate_article(summary)
            articles.append({"title": title, "summary": summary, "url": url, "rating": rating})
            mark_watched(url)
            logger.info("Collected article %d – %s", len(articles), title[:60])
        except Exception as exc:  # pragma: no cover – individual article failures are expected
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