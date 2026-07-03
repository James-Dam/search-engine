import math


K1 = 1.5
B = 0.75
TITLE_WEIGHT = 2.5
HEADER_WEIGHT = 1.5
BOLD_WEIGHT = 1.2
URL_WEIGHT = 2.0


def score_term(posting, total_docs, doc_frequency, avg_doc_len, k1=K1, b=B):
    tf = posting["raw_term_frequency"]
    doc_len = max(posting["document_length"], 1)
    avg_len = max(avg_doc_len, 1)

    idf = math.log(1 + ((total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5)))
    denominator = tf + k1 * (1 - b + b * (doc_len / avg_len))
    bm25 = idf * ((tf * (k1 + 1)) / denominator) if denominator else 0

    field_contribution = idf * (
        posting["title_hits"] * TITLE_WEIGHT
        + posting["header_hits"] * HEADER_WEIGHT
        + posting["bold_hits"] * BOLD_WEIGHT
        + posting["url_match_flag"] * URL_WEIGHT
    )

    total = bm25 + field_contribution
    return total, {
        "model": "bm25",
        "idf": idf,
        "raw_tf": tf,
        "document_length": doc_len,
        "avg_doc_len": avg_len,
        "base_score": bm25,
        "field_contribution": field_contribution,
        "total_term_score": total,
    }
