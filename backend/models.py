from pydantic import BaseModel, HttpUrl
from typing import List

class Article(BaseModel):
    title: str
    summary: str
    url: HttpUrl
    rating: int          # 1‑10 fuzzy‑puppy rating

class NewsResponse(BaseModel):
    articles: List[Article]