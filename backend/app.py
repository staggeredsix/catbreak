import asyncio
import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from models import NewsResponse, Article
from scraper import get_few_good_articles

# CORS configuration
app = FastAPI(title="Feel‑Good News Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = "llama3.1:8b-instruct-q8_0"

# Logging configuration – write a rotating log file to ./logs/app.log
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger("backend")

# Middleware – log every incoming HTTP request and its response status
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = datetime.utcnow().isoformat()
    logger.info(f"{request_id} | INCOMING | {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(
            f"{request_id} | RESPONSE | {request.method} {request.url.path} -> {response.status_code}"
        )
        return response
    except Exception as exc:  # pragma: no cover – catching unexpected errors
        logger.exception(f"{request_id} | EXCEPTION | {request.method} {request.url.path}")
        raise exc

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
    logger.info("Fetching fresh articles via scraper")
    raw_articles = get_few_good_articles()
    if not raw_articles:
        raise HTTPException(status_code=503, detail="Could not fetch articles")
    summarized = []
    for art in raw_articles:
        try:
            short = await summarize_with_ollama(art["summary"])
        except Exception as exc:
            logger.exception("LLM summarisation failed, using fallback")
            short = art["summary"][:300] + "…"
        summarized.append(
            Article(
                title=art["title"],
                summary=short,
                url=art["url"],
                rating=art["rating"],
            )
        )
    return NewsResponse(articles=summarized)

@app.get("/health")
def health():
    logger.info("Health check invoked")
    return {"status": "ok"}

# Serve a simple self‑hosted landing page that mirrors the extension UI.
# The static files live in ./static and include an index.html that fetches
# /news and renders it.
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True))
