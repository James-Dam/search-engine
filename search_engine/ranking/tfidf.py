import math


TITLE_WEIGHT = 2.5
HEADER_WEIGHT = 1.5
BOLD_WEIGHT = 1.2
URL_WEIGHT = 2.0


def score_term(posting, total_docs, doc_frequency, avg_doc_len=None):
    tf = posting["raw_term_frequency"]
    important_tf = posting["title_hits"] + posting["header_hits"] + posting["bold_hits"]
    idf = math.log(total_docs / doc_frequency) if doc_frequency > 0 else 0

    base_score = (1 + math.log(tf)) * idf if tf > 0 else 0
    importance_boost = (1 + math.log(important_tf)) * idf * 2 if important_tf > 0 else 0
    field_contribution = idf * (
        posting["title_hits"] * TITLE_WEIGHT
        + posting["header_hits"] * HEADER_WEIGHT
        + posting["bold_hits"] * BOLD_WEIGHT
        + posting["url_match_flag"] * URL_WEIGHT
    )

    total = base_score + importance_boost + field_contribution
    return total, {
        "model": "tfidf",
        "idf": idf,
        "raw_tf": tf,
        "document_length": posting["document_length"],
        "base_score": base_score,
        "importance_boost": importance_boost,
        "field_contribution": field_contribution,
        "total_term_score": total,
    }
