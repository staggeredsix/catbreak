import httpx
from bs4 import BeautifulSoup
from newspaper import Article as NewsArticle
import sqlite3
import random
import json
from typing import List, Tuple

DB_PATH = "cache.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS watched (
                    url TEXT PRIMARY KEY,
                    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    conn.commit()
    conn.close()

def is_watched(url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM watched WHERE url = ?", (url,))
    found = cur.fetchone() is not None
    conn.close()
    return found

def mark_watched(url: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO watched (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

def duckduckgo_search(query: str, max_results: int = 20) -> List[str]:
    """
    Very lightweight DuckDuckGo HTML search.
    Returns a list of result URLs.
    """
    resp = httpx.get(
        "https://duckduckgo.com/html/",
        params={"q": query},
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.select("a.result__a"):
        href = a.get("href")
        if href:
            links.append(href)
        if len(links) >= max_results:
            break
    return links

def fetch_article(url: str) -> Tuple[str, str]:
    """
    Uses newspaper3k to download and parse the article.
    Returns (title, summary).
    """
    article = NewsArticle(url)
    article.download()
    article.parse()
    article.nlp()
    return article.title, article.summary

def rate_article(content: str) -> int:
    """
    Very naive “feel‑good” scorer:
      - positive words add points, negative words subtract.
    Returns a rating from 1‑10.
    """
    positives = ["help", "kind", "success", "hope", "inspire", "joy", "uplift", "community", "cure", " breakthrough"]
    negatives = ["war", "crime", "death", "disaster", "crisis", "fail", "tragedy"]
    score = sum(word in content.lower() for word in positives) - sum(word in content.lower() for word in negatives)
    # Clamp to 1‑10
    return max(1, min(10, score + 5))

def get_few_good_articles() -> List[dict]:
    """
    Main entry point used by the API.
    Returns up to 5 feel‑good articles with rating.
    """
    init_db()
    query = "feel good news positive uplifting recent"
    urls = duckduckgo_search(query, max_results=30)

    articles = []
    for url in urls:
        if is_watched(url):
            continue
        try:
            title, summary = fetch_article(url)
            rating = rate_article(summary)
            articles.append({"title": title, "summary": summary, "url": url, "rating": rating})
            mark_watched(url)
        except Exception:
            continue
        if len(articles) >= 5:
            break

    # If we still have fewer than 5, fill with random cached ones (no re‑rating)
    if len(articles) < 5:
        # In a real project you would store already‑fetched articles; here we just reuse the ones we have.
        pass

    return articles