from search_engine.ranking import bm25, tfidf


SUPPORTED_MODELS = {"bm25", "tfidf"}


def score_term(model, posting, total_docs, doc_frequency, avg_doc_len):
    normalized_model = model.lower()

    if normalized_model == "bm25":
        return bm25.score_term(posting, total_docs, doc_frequency, avg_doc_len)

    if normalized_model == "tfidf":
        return tfidf.score_term(posting, total_docs, doc_frequency, avg_doc_len)

    raise ValueError(f"Unsupported ranking model: {model}")
