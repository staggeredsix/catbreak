import asyncio
import os
import httpx
from fastapi import FastAPI, HTTPException
from models import NewsResponse, Article
from scraper import get_few_good_articles

app = FastAPI(title="Feel‑Good News Backend")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = "llama3.1:8b-instruct"

async def summarize_with_ollama(text: str) -> str:
    """
    Calls Ollama's `/api/generate` endpoint to ask the LLM for a short 2‑sentence summary.
    """
    payload = {
        "model": MODEL,
        "prompt": f"Summarise the following article in 2‑3 sentences, keep it upbeat and feel‑good:\n\n{text}",
        "stream": False,
        "options": {"temperature": 0.7}
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()

@app.get("/news", response_model=NewsResponse)
async def get_news():
    raw_articles = get_few_good_articles()
    if not raw_articles:
        raise HTTPException(status_code=503, detail="Could not fetch articles")
    # Ask LLM for a nicer summary for each article (optional but demonstrates the model)
    summarized = []
    for art in raw_articles:
        try:
            short = await summarize_with_ollama(art["summary"])
        except Exception:
            short = art["summary"][:300] + "…"   # fallback
        summarized.append(Article(
            title=art["title"],
            summary=short,
            url=art["url"],
            rating=art["rating"]
        ))
    return NewsResponse(articles=summarized)

@app.get("/health")
def health():
    return {"status": "ok"}