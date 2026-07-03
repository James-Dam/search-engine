from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
from search_engine.ranking.scorer import SUPPORTED_MODELS, score_term
import json
import os
import re


INDEX_FOLDER = "index_output"
INDEX_PATH = os.path.join(INDEX_FOLDER, "final_index.txt")
OFFSETS_PATH = os.path.join(INDEX_FOLDER, "term_offsets.json")
DOC_MAP_PATH = os.path.join(INDEX_FOLDER, "doc_map.json")

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


class MissingIndexError(FileNotFoundError):
    def __init__(self, index_folder, missing_files):
        self.index_folder = index_folder
        self.missing_files = missing_files
        message = f"Missing or incomplete index folder: {index_folder}"
        super().__init__(message)


def get_index_paths(index_folder):
    return {
        "index": os.path.join(index_folder, "final_index.txt"),
        "offsets": os.path.join(index_folder, "term_offsets.json"),
        "doc_map": os.path.join(index_folder, "doc_map.json"),
        "metadata": os.path.join(index_folder, "index_metadata.json"),
    }


def get_missing_index_files(index_folder):
    paths = get_index_paths(index_folder)
    required_paths = [paths["index"], paths["offsets"], paths["doc_map"]]

    if not os.path.isdir(index_folder):
        return required_paths

    return [path for path in required_paths if not os.path.isfile(path)]


def validate_index_folder(index_folder):
    return not get_missing_index_files(index_folder)


def raise_if_index_missing(index_folder):
    missing_files = get_missing_index_files(index_folder)
    if missing_files:
        raise MissingIndexError(index_folder, missing_files)


def load_index(index_folder=INDEX_FOLDER):
    """
    Loads the term offsets and doc map from disk into memory.
    Returns:
        tuple: (term_offsets dict, doc_map dict)
    """
    paths = get_index_paths(index_folder)

    with open(paths["offsets"], "r", encoding="utf-8") as f:
        term_offsets = json.load(f)

    with open(paths["doc_map"], "r", encoding="utf-8") as f:
        doc_map = json.load(f)

    return term_offsets, doc_map


def load_index_metadata(index_folder, doc_map):
    paths = get_index_paths(index_folder)
    if os.path.isfile(paths["metadata"]):
        with open(paths["metadata"], "r", encoding="utf-8") as f:
            return json.load(f)

    lengths = [
        doc.get("document_length", 0)
        for doc in doc_map.values()
        if isinstance(doc, dict)
    ]
    avg_doc_len = sum(lengths) / len(lengths) if lengths else 1
    return {
        "postings_format": "legacy",
        "ranking_default": "bm25",
        "num_documents": len(doc_map),
        "avg_doc_len": avg_doc_len,
    }


def tokenize_query(query, stemmer):
    """
    Tokenizes, stopword-filters, and stems a query string.
    """
    tokens = TOKEN_RE.findall(query.lower())
    return [stemmer.stem(t) for t in tokens if t not in STOPWORDS]


def get_raw_query_terms(query):
    return [t for t in TOKEN_RE.findall(query.lower()) if t not in STOPWORDS]


def get_postings(term, term_offsets, index_file):
    """
    Gets the postings list for one term without loading the full index.
    """
    if term not in term_offsets:
        return None

    offset = term_offsets[term]
    index_file.seek(offset)

    line = index_file.readline()
    if not line:
        return None

    return json.loads(line.strip())


def get_doc_info(doc_map, doc_id):
    return doc_map.get(str(doc_id)) or doc_map.get(doc_id) or {}


def normalize_posting(posting, term, doc_map):
    """
    Supports both legacy postings [doc_id, tf, important_tf] and v2 dict postings.
    """
    if isinstance(posting, dict):
        doc_id = int(posting.get("doc_id"))
        doc_info = get_doc_info(doc_map, doc_id)
        document_length = int(
            posting.get("document_length")
            or doc_info.get("document_length")
            or posting.get("raw_term_frequency", 1)
            or 1
        )
        raw_tf = int(
            posting.get("raw_term_frequency")
            or posting.get("tf")
            or posting.get("term_frequency")
            or 0
        )
        return {
            "doc_id": doc_id,
            "document_length": max(document_length, 1),
            "title_hits": int(posting.get("title_hits", 0)),
            "header_hits": int(posting.get("header_hits", 0)),
            "bold_hits": int(posting.get("bold_hits", 0)),
            "url_match_flag": int(posting.get("url_match_flag", 0)),
            "raw_term_frequency": raw_tf,
            "normalized_term_frequency": float(
                posting.get("normalized_term_frequency")
                or raw_tf / max(document_length, 1)
            ),
        }

    doc_id = int(posting[0])
    raw_tf = int(posting[1])
    important_tf = int(posting[2]) if len(posting) > 2 else 0
    doc_info = get_doc_info(doc_map, doc_id)
    document_length = int(doc_info.get("document_length") or raw_tf or 1)
    url = doc_info.get("url", "").lower()

    return {
        "doc_id": doc_id,
        "document_length": max(document_length, 1),
        "title_hits": 0,
        "header_hits": 0,
        "bold_hits": important_tf,
        "url_match_flag": 1 if term in url else 0,
        "raw_term_frequency": raw_tf,
        "normalized_term_frequency": raw_tf / max(document_length, 1),
    }


def normalize_url(url):
    """
    Normalizes URLs so near-duplicate URLs are treated as the same.
    """
    url = url.lower().strip()
    url = url.rstrip("/")

    if url.endswith("/index.php"):
        url = url[:-10]

    if url.endswith("/index"):
        url = url[:-6]

    return url


def get_url_score_multiplier(url):
    """
    Gives lower scores to noisy/list/archive pages.
    This is general, not query-specific.
    """
    url = url.lower()
    multiplier = 1.0

    bad_patterns = [
        "/tag/",
        "/category/",
        "/page/",
        "/community/news/",
        "view_news",
        "view_article",
        "mailman/listinfo",
        "notes_",
        "wordlist",
        ".txt",
    ]

    for pattern in bad_patterns:
        if pattern in url:
            multiplier *= 0.5

    return multiplier


def get_url_query_boost(url, raw_query_terms):
    """
    Gives a small boost when query terms appear in the URL.
    Helps pages whose URL directly matches the user's intent.
    """
    url = url.lower()
    url = url.replace("-", " ")
    url = url.replace("_", " ")

    boost = 0
    for term in raw_query_terms:
        if term in url:
            boost += 2

    return boost


def get_and_candidates(query_terms, term_postings):
    """
    Finds documents that contain every query term.
    """
    for term in query_terms:
        if term not in term_postings:
            return set()

    sets = [set(posting["doc_id"] for posting in term_postings[t]) for t in query_terms]
    sets.sort(key=len)

    common_doc_ids = sets[0]
    for s in sets[1:]:
        common_doc_ids = common_doc_ids & s

    return common_doc_ids


def get_or_candidates(term_postings):
    """
    Finds documents that contain at least one query term.
    Used when strict AND retrieval finds no results.
    """
    doc_ids = set()

    for term in term_postings:
        for posting in term_postings[term]:
            doc_ids.add(posting["doc_id"])

    return doc_ids


def get_matched_term_counts(doc_ids, term_postings):
    """
    Counts how many query terms each document matched.
    Used to help OR fallback ranking.
    """
    matched_counts = {doc_id: 0 for doc_id in doc_ids}

    for term in term_postings:
        for posting in term_postings[term]:
            doc_id = posting["doc_id"]
            if doc_id in doc_ids:
                matched_counts[doc_id] += 1

    return matched_counts


def get_posting_matched_fields(posting):
    fields = set()
    field_hits = (
        posting["title_hits"]
        + posting["header_hits"]
        + posting["bold_hits"]
    )

    if posting["title_hits"] > 0:
        fields.add("title")
    if posting["header_hits"] > 0:
        fields.add("header")
    if posting["bold_hits"] > 0:
        fields.add("bold")
    if posting["url_match_flag"]:
        fields.add("url")
    if posting["raw_term_frequency"] > field_hits:
        fields.add("body")

    return fields


def extract_title_and_text(doc_info):
    path = doc_info.get("path")
    if not path or not os.path.isfile(path):
        return "", ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "", ""

    html_content = data.get("content", "")
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    text = soup.get_text(separator=" ", strip=True)
    return title, re.sub(r"\s+", " ", text)


def build_snippet(doc_info, raw_query_terms, max_chars=180):
    title, text = extract_title_and_text(doc_info)
    if not text:
        return title, ""

    lowered = text.lower()
    positions = [
        lowered.find(term)
        for term in raw_query_terms
        if term and lowered.find(term) >= 0
    ]
    center = min(positions) if positions else 0
    start = max(0, center - max_chars // 3)
    end = min(len(text), start + max_chars)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return title, snippet


def search(
    query,
    term_offsets,
    doc_map,
    metadata=None,
    top_n=10,
    index_path=INDEX_PATH,
    ranking_model="bm25",
    debug=False,
):
    """
    Search the index without loading the full index into memory.
    """
    ranking_model = ranking_model.lower()
    if ranking_model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported ranking model: {ranking_model}")

    stemmer = PorterStemmer()
    query_terms = tokenize_query(query, stemmer)
    raw_query_terms = get_raw_query_terms(query)

    if not query_terms:
        return []

    total_docs = len(doc_map)
    avg_doc_len = (metadata or {}).get("avg_doc_len") or 1
    term_postings = {}

    with open(index_path, "r", encoding="utf-8") as index_file:
        for term in query_terms:
            postings = get_postings(term, term_offsets, index_file)
            if postings is not None:
                term_postings[term] = [
                    normalize_posting(posting, term, doc_map)
                    for posting in postings
                ]

    if not term_postings:
        return []

    common_doc_ids = get_and_candidates(query_terms, term_postings)
    use_or_fallback = False

    if not common_doc_ids:
        use_or_fallback = True
        common_doc_ids = get_or_candidates(term_postings)

    if not common_doc_ids:
        return []

    scores = {}
    matched_fields = {}
    debug_details = {}

    for term in term_postings:
        postings = term_postings[term]
        doc_frequency = len(postings)

        for posting in postings:
            doc_id = posting["doc_id"]
            if doc_id not in common_doc_ids:
                continue

            term_score, details = score_term(
                ranking_model,
                posting,
                total_docs,
                doc_frequency,
                avg_doc_len,
            )

            scores[doc_id] = scores.get(doc_id, 0) + term_score
            matched_fields.setdefault(doc_id, set()).update(
                get_posting_matched_fields(posting)
            )

            if debug:
                debug_details.setdefault(doc_id, []).append(
                    {
                        "term": term,
                        **details,
                    }
                )

    matched_counts = get_matched_term_counts(common_doc_ids, term_postings)
    adjusted_scores = {}
    adjustment_debug = {}

    for doc_id in scores:
        doc_info = get_doc_info(doc_map, doc_id)
        if not doc_info:
            continue

        url = doc_info["url"]
        multiplier = get_url_score_multiplier(url)
        boost = get_url_query_boost(url, raw_query_terms)
        coverage_boost = matched_counts.get(doc_id, 0) * 5 if use_or_fallback else 0

        adjusted_scores[doc_id] = (scores[doc_id] * multiplier) + boost + coverage_boost
        if debug:
            adjustment_debug[doc_id] = {
                "pre_adjustment_score": scores[doc_id],
                "url_multiplier": multiplier,
                "url_query_boost": boost,
                "or_coverage_boost": coverage_boost,
                "final_score": adjusted_scores[doc_id],
            }

    ranked = sorted(adjusted_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    seen_urls = set()

    for doc_id, score in ranked:
        doc_info = get_doc_info(doc_map, doc_id)
        if not doc_info:
            continue

        url = doc_info["url"]
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue

        seen_urls.add(normalized)
        title, snippet = build_snippet(doc_info, raw_query_terms)
        result = {
            "doc_id": doc_id,
            "url": url,
            "score": float(score),
            "title": title,
            "snippet": snippet,
            "matched_fields": sorted(matched_fields.get(doc_id, set())),
        }

        if debug:
            result["debug"] = {
                "ranking_model": ranking_model,
                "terms": debug_details.get(doc_id, []),
                "adjustments": adjustment_debug.get(doc_id, {}),
            }

        results.append(result)
        if len(results) == top_n:
            break

    return results


def search_query(
    query: str,
    index_path: str,
    top_k: int = 10,
    ranking_model: str = "bm25",
    debug: bool = False,
):
    """
    Search a generated index folder and return structured results.
    """
    index_folder = os.path.normpath(index_path)
    raise_if_index_missing(index_folder)

    paths = get_index_paths(index_folder)
    term_offsets, doc_map = load_index(index_folder)
    metadata = load_index_metadata(index_folder, doc_map)

    return search(
        query,
        term_offsets,
        doc_map,
        metadata=metadata,
        top_n=top_k,
        index_path=paths["index"],
        ranking_model=ranking_model,
        debug=debug,
    )
