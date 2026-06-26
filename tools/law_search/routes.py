from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.law_search import law_search_tool

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    num_results: int = 10

@router.post("/api/search")
async def search_laws(request: SearchRequest):
    try:
        results, text = law_search_tool.search(request.query, num_results=request.num_results, verify=True)
        return {"success": True, "query": request.query, "results": results, "text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/api/search")
async def search_laws_get(query: str, num_results: int = 10):
    try:
        results, text = law_search_tool.search(query, num_results=num_results, verify=True)
        return {"success": True, "query": query, "results": results, "text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
