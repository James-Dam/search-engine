# Disk-Based Search Engine

A disk-backed search engine for a crawled web corpus. The project builds an inverted index from JSON documents, stores the index on disk, and provides a terminal search interface that ranks matching URLs with TF-IDF style scoring.

This began as a university course project and is now being evolved into a polished search application suitable for portfolio and recruiter review. The current goal is to make the original terminal workflow easy to run from a fresh clone before adding a backend, frontend, containers, or tests.

## Quick Start

The repository includes `analyst.zip`, a smaller dataset intended for fast local setup. The full `DEV/` dataset is optional, too large for GitHub, and not included.

Step 1: unzip analyst.zip → produces ANALYST/

```powershell
Expand-Archive analyst.zip -DestinationPath .
```

On macOS or Linux:

```bash
unzip analyst.zip
```

Step 2: run indexing using ANALYST/

```bash
python index.py --input ANALYST --output index_output
```

Step 3: run search

```bash
python search.py --index index_output
```

Then enter queries at the prompt. Type `quit` to exit.

## Why This Project Exists

The goal is to demonstrate the core systems work behind a search engine without relying on a database or hosted search service. The indexer processes a local corpus, writes compact searchable files to disk, and the search program retrieves postings by byte offset instead of loading the entire index into memory.

## Features

- Disk-based inverted index built from local JSON documents.
- HTML text extraction with Beautiful Soup.
- Tokenization and Porter stemming for normalized term matching.
- Duplicate URL filtering during indexing.
- Partial index flushing to limit memory usage on large corpora.
- K-way merge into a final index file.
- Byte-offset lookup table for fast term retrieval at search time.
- Configurable input, output, and index paths.
- Terminal search with AND matching and OR fallback.
- TF-IDF style scoring with boosts for title, heading, bold, and URL matches.
- Simple index analytics report with document count, token count, and index size.

## Current Architecture

```text
.
|-- index.py              # Builds the disk-based inverted index
|-- search.py             # Runs the interactive terminal search program
|-- requirements.txt      # Minimal Python runtime dependencies
|-- README.md             # Project documentation
|-- analyst.zip           # Included default dataset archive
|-- ANALYST/              # Extracted default dataset, ignored by git
|-- index_output/         # Generated index files, ignored by git
`-- DEV/                  # Optional full dataset, not included
```

The default local workflow uses:

- Dataset archive: `analyst.zip`
- Input corpus: `ANALYST/`
- Generated index folder: `index_output/`
- Final index file: `index_output/final_index.txt`
- Term offset map: `index_output/term_offsets.json`
- Document map: `index_output/doc_map.json`
- Index report: `index_output/report.txt`

Each input document is expected to be a JSON file with at least:

- `url`: the source URL for the page
- `content`: the raw HTML content for the page

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

The current runtime dependencies are intentionally small: Beautiful Soup for HTML parsing and NLTK for Porter stemming.

## Run the Indexer

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

You can also index another compatible corpus:

```bash
python index.py --input path/to/corpus --output path/to/index_output
```

## Run Terminal Search

The default search command is:

```bash
python search.py
```

This is equivalent to:

```bash
python search.py --index index_output
```

If the index folder or required index files are missing, the search program tells you to run indexing first.

Example queries:

```text
machine learning
computer science
informatics
graduate admissions
artificial intelligence
database systems
```

## How Indexing Works

`index.py` walks the input directory recursively and processes JSON files. For each page, it removes URL fragments, skips duplicate URLs, extracts visible HTML text, and separately extracts important text from tags such as `title`, `h1`, `h2`, `h3`, `b`, and `strong`.

The indexer tokenizes alphanumeric terms, lowercases them, applies Porter stemming, and stores postings in the format:

```text
[doc_id, term_frequency, important_term_frequency]
```

To keep memory usage manageable, the indexer periodically writes sorted partial index files to disk. After the corpus is processed, it performs a k-way merge into `final_index.txt`. The final index stores one postings list per line, while `term_offsets.json` maps each term to its byte offset in the final index for direct lookup during search.

## How Searching Works

`search.py` loads `term_offsets.json` and `doc_map.json`, then opens `final_index.txt` on demand. Query terms are tokenized and stemmed the same way as indexed terms.

For a query, the search program:

1. Looks up each query term's postings list using the byte offset map.
2. Retrieves documents that contain all query terms.
3. Falls back to documents that contain any query term if no strict AND match exists.
4. Scores candidates with TF-IDF style ranking.
5. Boosts terms found in important HTML tags.
6. Applies URL-based adjustments for noisy pages and query terms in URLs.
7. Prints the top results with scores and search latency.

## Current Limitations

- The default dataset is the smaller `ANALYST/` corpus from `analyst.zip`.
- The optional full `DEV/` dataset is not included because it is too large for GitHub.
- The search program is terminal-only.
- Index files must already exist before running `search.py`.
- There is no automated test suite yet.
- There is no API layer or web interface yet.
- Ranking is intentionally simple and explainable rather than production-grade.
- Generated index files can be large and are treated as local build artifacts.

## Planned Improvements

- Add a FastAPI backend around the existing search functionality.
- Add a React frontend for query entry and result display.
- Add Docker support for repeatable local setup.
- Add tests for tokenization, indexing, offset lookup, and ranking behavior.
- Add safer recovery for interrupted indexing runs.

## Repository Status

This step focuses on making the project easy to run from scratch. The existing indexing algorithm, TF-IDF logic, disk-based index format, and ranking system are preserved.
