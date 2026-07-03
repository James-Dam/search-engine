# Disk-Based Search Engine

A disk-backed search engine for a crawled web corpus. The project builds an inverted index from JSON documents, stores the index on disk, and exposes both a terminal search interface and a FastAPI backend.

This began as a university course project and is now being evolved into a polished search application suitable for portfolio and recruiter review. The current architecture separates core indexing/search logic from CLI and HTTP interfaces.

## Quick Start

The repository includes `analyst.zip`, a smaller dataset intended for fast local setup. The full `DEV/` dataset is optional, too large for GitHub, and not included.

Step 1: unzip analyst.zip -> produces ANALYST/

```powershell
Expand-Archive analyst.zip -DestinationPath .
```

On macOS or Linux:

```bash
unzip analyst.zip
```

Step 2: install dependencies

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Step 3: run indexing using ANALYST/

```bash
python index.py --input ANALYST --output index_output
```

Step 4: run terminal search

```bash
python search.py --index index_output
```

Step 5: run the API server

```bash
uvicorn api.main:app --reload
```

Step 6: run the React frontend

```bash
cd frontend
npm install
npm run dev
```

## Current Architecture

```text
.
|-- index.py                         # CLI wrapper for indexing
|-- search.py                        # CLI wrapper for terminal search
|-- api/
|   |-- __init__.py
|   `-- main.py                      # Uvicorn entry point shim
|-- frontend/
|   |-- index.html
|   |-- package.json
|   |-- vite.config.js
|   `-- src/
|       |-- App.jsx
|       |-- main.jsx
|       `-- styles.css
|-- search_engine/
|   |-- __init__.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- index.py                 # Core indexing logic
|   |   `-- search.py                # Core lookup and ranking logic
|   |-- service/
|   |   |-- __init__.py
|   |   `-- search_service.py        # Reusable service wrapper
|   |-- ranking/
|   |   |-- __init__.py
|   |   |-- bm25.py                  # Default BM25 scorer
|   |   |-- tfidf.py                 # TF-IDF baseline scorer
|   |   `-- scorer.py                # Ranking model selector
|   `-- api/
|       |-- __init__.py
|       `-- main.py                  # FastAPI application
|-- requirements.txt
|-- analyst.zip                      # Included default dataset archive
|-- ANALYST/                         # Extracted default dataset, ignored by git
|-- index_output/                    # Generated index files, ignored by git
`-- DEV/                             # Optional full dataset, not included
```

Separation of concerns:

- CLI: user interaction and command-line arguments only.
- Core: indexing, disk lookup, and ranking logic.
- Service: reusable function boundary for CLI and API callers.
- API: HTTP interface built with FastAPI.
- Frontend: React/Vite web interface that calls the FastAPI backend.

## CLI Usage

The default indexer command is:

```bash
python index.py
```

This is equivalent to:

```bash
python index.py --input ANALYST --output index_output
```

If `ANALYST/` is missing, the indexer prints:

```text
Missing dataset. Please unzip analyst.zip to create ANALYST/
```

Run terminal search:

```bash
python search.py --index index_output
```

Optional result count:

```bash
python search.py --index index_output --top-k 10
```

Ranking model toggle:

```bash
python search.py --index index_output --ranking bm25
python search.py --index index_output --ranking tfidf
```

Debug mode shows per-term scores, document length, and field contribution:

```bash
python search.py --index index_output --ranking bm25 --debug
```

Run tests:

```bash
pytest
```

Example terminal queries:

```text
machine learning
computer science
informatics
graduate admissions
artificial intelligence
database systems
```

## API Usage

Start the backend:

```bash
uvicorn api.main:app --reload
```

The API uses `index_output` by default. To point it at a different generated index folder, set `SEARCH_INDEX_PATH` before starting Uvicorn.

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{"status":"ok"}
```

Search request:

```bash
curl "http://127.0.0.1:8000/search?q=machine%20learning&top_k=10"
```

Use TF-IDF or debug mode through query parameters:

```bash
curl "http://127.0.0.1:8000/search?q=machine%20learning&top_k=10&ranking=tfidf&debug=true"
```

Example response:

```json
[
  {
    "doc_id": 42,
    "url": "https://example.edu/page",
    "score": 12.3456,
    "title": "Example Page",
    "snippet": "...machine learning excerpt...",
    "highlighted_snippet": "...<mark>machine</mark> <mark>learning</mark> excerpt...",
    "ranking_model": "bm25",
    "matched_fields": ["body", "title"]
  }
]
```

If the generated index is missing or incomplete, the API returns HTTP 503 with details telling you to run indexing first.

## Frontend Usage

Start the backend first:

```bash
uvicorn api.main:app --reload
```

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, usually:

```text
http://127.0.0.1:5173
```

The frontend calls:

```text
http://127.0.0.1:8000/search
```

To point the frontend at another backend URL, set `VITE_API_BASE_URL` in `frontend/.env.local`.

## Reusable Search Function

The service layer exposes:

```python
from search_engine.service.search_service import search_query

results = search_query(
    "machine learning",
    index_path="index_output",
    top_k=10,
    ranking_model="bm25",
    debug=False,
)
```

Return format:

```python
[
    {
        "doc_id": 42,
        "url": "https://example.edu/page",
        "score": 12.3456,
        "title": "Example Page",
        "snippet": "...machine learning excerpt...",
        "highlighted_snippet": "...<mark>machine</mark> <mark>learning</mark> excerpt...",
        "matched_fields": ["body", "title"],
        "ranking_model": "bm25",
    }
]
```

`debug=True` adds per-term scorer details and document-level adjustments to each result.
`highlighted_snippet` is safe, simple markup intended for future UI rendering; the plain `snippet` field is preserved for clients that do not render HTML.

## How Indexing Works

`search_engine.core.index` walks the input directory recursively and processes JSON files. For each page, it removes URL fragments, skips duplicate URLs, extracts visible HTML text, and separately extracts important text from tags such as `title`, `h1`, `h2`, `h3`, `b`, and `strong`.

The indexer tokenizes alphanumeric terms, lowercases them, applies Porter stemming, and stores v2 postings in this format:

```json
{
  "doc_id": 42,
  "document_length": 731,
  "title_hits": 1,
  "header_hits": 2,
  "bold_hits": 0,
  "url_match_flag": 1,
  "raw_term_frequency": 8,
  "normalized_term_frequency": 0.0109,
  "important_term_frequency": 3
}
```

Legacy postings shaped like `[doc_id, term_frequency, important_term_frequency]` are still supported at search time. Re-indexing creates the richer v2 postings and writes `index_metadata.json` with average document length for BM25.

To keep memory usage manageable, the indexer periodically writes sorted partial index files to disk. After the corpus is processed, it performs a k-way merge into `final_index.txt`. The final index still stores one postings list per line, while `term_offsets.json` maps each term to its byte offset in the final index for direct lookup during search.

## How Searching Works

`search_engine.core.search` loads `term_offsets.json` and `doc_map.json`, then opens `final_index.txt` on demand. Query terms are tokenized and stemmed the same way as indexed terms.

For a query, the search logic:

1. Looks up each query term's postings list using the byte offset map.
2. Retrieves documents that contain all query terms.
3. Falls back to documents that contain any query term if no strict AND match exists.
4. Scores candidates with BM25 by default.
5. Optionally scores with TF-IDF using `--ranking tfidf` or `ranking=tfidf`.
6. Uses field contributions from title, header, bold, and URL matches.
7. Applies URL-based adjustments for noisy pages and query terms in URLs.
8. Builds small snippets from matched source documents when available.
9. Returns structured results for CLI or API presentation.

## Ranking

BM25 is the default ranking model. It uses tunable constants `k1=1.5` and `b=0.75`, document length normalization, document frequency, and average document length from `index_metadata.json`.

The TF-IDF scorer remains available as a baseline:

```bash
python search.py --index index_output --ranking tfidf
```

Both ranking models keep disk-based term lookup. Only postings for query terms are read from `final_index.txt`.

## Current Limitations

- The default dataset is the smaller `ANALYST/` corpus from `analyst.zip`.
- The optional full `DEV/` dataset is not included because it is too large for GitHub.
- Index files must already exist before running search.
- Snippets are best-effort and depend on the original JSON file still being present at the path recorded in `doc_map.json`.
- Highlighting is literal query-term markup and does not perform semantic matching.
- The test suite is intentionally small and focused on query processing, snippets, and API basics.
- The React frontend is intentionally simple and calls the local FastAPI backend.
- There is no Docker setup yet.
- Ranking is more realistic with BM25, but still intentionally explainable rather than production-grade.
- Generated index files can be large and are treated as local build artifacts.

## Planned Improvements

- Add Docker support for repeatable local setup.
- Add tests for tokenization, indexing, offset lookup, API responses, and ranking behavior.
- Add safer recovery for interrupted indexing runs.
- Tune BM25 and field weights with a larger evaluation set.

## Repository Status

This step upgrades postings and ranking while preserving disk-based lookup, partial index flushing, k-way merge, and byte-offset term access.
