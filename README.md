# ZotSearch

ZotSearch is a full-stack, disk-based search engine for UCI-related web pages. It began as a university search engine project and has been polished into a portfolio application with a Python indexing/search backend, FastAPI API, and React frontend.

The project demonstrates search systems fundamentals without relying on a database or hosted search product: partial index flushing, k-way merge, byte-offset term lookup, disk-backed postings, BM25 ranking, field-aware scoring, snippets, and a web UI.



## Why UCI-Focused

The included `analyst.zip` dataset contains UCI-related crawled pages from the original course project. The larger `DEV/` corpus is useful locally, but it is too large for GitHub and is not included. To run the project from a fresh clone, unzip `analyst.zip` into `ANALYST/` and index that dataset.

## Architecture

```text
.
|-- index.py                         # CLI wrapper for indexing
|-- search.py                        # CLI wrapper for terminal search
|-- api/
|   `-- main.py                      # Uvicorn entry point shim
|-- frontend/
|   |-- Dockerfile
|   |-- package.json
|   |-- vite.config.js
|   `-- src/
|       |-- App.jsx
|       |-- main.jsx
|       `-- styles.css
|-- search_engine/
|   |-- core/
|   |   |-- index.py                 # Core indexing logic
|   |   `-- search.py                # Core lookup and result shaping
|   |-- ranking/
|   |   |-- bm25.py                  # Default BM25 scorer
|   |   |-- tfidf.py                 # Optional TF-IDF scorer
|   |   `-- scorer.py                # Ranking selector
|   |-- service/
|   |   `-- search_service.py        # Reusable service wrapper
|   `-- api/
|       `-- main.py                  # FastAPI app
|-- tests/
|-- Dockerfile.backend
|-- docker-compose.yml
|-- requirements.txt
|-- analyst.zip                      # Included dataset archive
|-- ANALYST/                         # Extracted dataset, ignored by git
|-- index_output/                    # Generated index, ignored by git
`-- DEV/                             # Optional full dataset, not included
```

## Local Run

Step 1: unzip the included dataset.

```powershell
Expand-Archive analyst.zip -DestinationPath .
```

On macOS/Linux:

```bash
unzip analyst.zip
```

Step 2: install backend dependencies.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Step 3: build the disk index.

```bash
python index.py --input ANALYST --output index_output
```

Step 4: start the backend.

```bash
uvicorn api.main:app --reload
```

Step 5: start the frontend in a second terminal.

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Docker Run

Indexing is intentionally kept as a documented pre-step so Docker does not need to bundle or generate large corpus artifacts.

```bash
python index.py --input ANALYST --output index_output
docker compose up --build
```

Services:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

Docker Compose mounts local `index_output/` into the backend container. If `index_output/` does not exist, the API will return a 503 response instructing you to run indexing first.

## CLI Usage

Index:

```bash
python index.py --input ANALYST --output index_output
```

Search:

```bash
python search.py --index index_output --ranking bm25 --top-k 10
```

Use TF-IDF:

```bash
python search.py --index index_output --ranking tfidf
```

Show ranking details:

```bash
python search.py --index index_output --ranking bm25 --debug
```

## API Usage

Health:

```bash
curl http://127.0.0.1:8000/health
```

Search:

```bash
curl "http://127.0.0.1:8000/search?q=machine%20learning&top_k=10&ranking=bm25&debug=false"
```

Example response:

```json
[
  {
    "doc_id": 42,
    "url": "https://example.uci.edu/page",
    "title": "Example Page",
    "score": 12.3456,
    "snippet": "...machine learning excerpt...",
    "highlighted_snippet": "...<mark>machine</mark> <mark>learning</mark> excerpt...",
    "matched_fields": ["body", "title"],
    "ranking_model": "bm25"
  }
]
```

The API supports development CORS for:

- `http://127.0.0.1:5173`
- `http://localhost:5173`

The frontend uses `VITE_API_BASE_URL` when provided and defaults to:

```text
http://127.0.0.1:8000
```

## Frontend Usage

The React/Vite UI provides:

- Search input with Enter-key submit
- Top-K control
- BM25 / TF-IDF selector
- Optional debug checkbox
- Loading, error, empty, and results states
- Clickable URLs
- Highlighted snippets
- Matched-field badges
- Collapsible debug details

Optional frontend override:

```text
frontend/.env.local
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Tests

Run the backend/unit tests:

```bash
pytest
```

Current tests cover:

- `/health`
- Empty query returns 400
- Missing index returns 503
- Invalid ranking selector returns 422
- Query tokenization and stopword filtering
- Snippet and highlight helpers

## Search Internals

The indexer walks JSON documents, extracts HTML text, tokenizes and stems terms, writes partial inverted indexes, then performs a k-way merge into `final_index.txt`. `term_offsets.json` maps terms to byte offsets so search can read only the posting lists needed for the current query.

New indexes store v2 postings with document length, raw and normalized term frequency, title/header/bold hits, and URL match flags. BM25 is the default ranking model, with TF-IDF retained as an optional baseline.

## Current Limitations

- `analyst.zip` must be unzipped into `ANALYST/` before indexing.
- `index_output/` must be generated locally and is not committed.
- The full `DEV/` dataset is not included because it is too large for GitHub.
- Docker Compose expects a local `index_output/` mount for full search.
- Snippets depend on source JSON paths recorded in `doc_map.json`.
- Highlighting is literal query-term markup, not semantic highlighting.
- No authentication or database layer is included.
