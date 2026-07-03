from search_engine.core.search import search_query as core_search_query


def search_query(
    query: str,
    index_path: str = "index_output",
    top_k: int = 10,
    ranking_model: str = "bm25",
    debug: bool = False,
):
    return core_search_query(
        query=query,
        index_path=index_path,
        top_k=top_k,
        ranking_model=ranking_model,
        debug=debug,
    )
