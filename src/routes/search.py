from fastapi import APIRouter
from pydantic import BaseModel
from src.rag.searcher import search

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_n: int = 3


@router.post("/")
def search_candidates(request: SearchRequest):
    """
    Search for candidates using natural language query.
    Returns top N ranked candidates with Gemini explanation.
    """
    result = search(user_query=request.query, top_n=request.top_n)
    return result