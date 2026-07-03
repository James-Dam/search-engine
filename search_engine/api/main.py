import os

from fastapi import FastAPI, HTTPException, Query

from search_engine.core.search import MissingIndexError
from search_engine.service.search_service import search_query


app = FastAPI(title="Disk-Based Search Engine API")
DEFAULT_INDEX_PATH = os.environ.get("SEARCH_INDEX_PATH", "index_output")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=100),
    ranking: str = Query("bm25", pattern="^(bm25|tfidf)$"),
    debug: bool = Query(False),
):
    try:
        return search_query(
            q,
            index_path=DEFAULT_INDEX_PATH,
            top_k=top_k,
            ranking_model=ranking,
            debug=debug,
        )
    except MissingIndexError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Index is missing or incomplete. Please run indexing first.",
                "index_folder": error.index_folder,
                "missing_files": error.missing_files,
            },
        ) from error
