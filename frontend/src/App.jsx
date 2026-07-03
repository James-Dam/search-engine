import { useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function decodeHtmlEntities(value) {
  const element = document.createElement("textarea");
  element.innerHTML = value;
  return element.value;
}

function renderHighlightedSnippet(value) {
  if (!value) {
    return null;
  }

  return value.split(/(<mark>.*?<\/mark>)/gi).map((part, index) => {
    const match = part.match(/^<mark>(.*?)<\/mark>$/i);
    if (match) {
      return <mark key={index}>{decodeHtmlEntities(match[1])}</mark>;
    }
    return <span key={index}>{decodeHtmlEntities(part)}</span>;
  });
}

function formatScore(score) {
  const value = Number(score);
  return Number.isFinite(value) ? value.toFixed(4) : "0.0000";
}

function ResultCard({ result }) {
  const title = result.title?.trim() || result.url;
  const snippet = result.highlighted_snippet || result.snippet;
  const hasDebug = Boolean(result.debug);

  return (
    <article className="result-card">
      <div className="result-header">
        <div className="result-title-group">
          <h2>{title}</h2>
          <a href={result.url} target="_blank" rel="noreferrer">
            {result.url}
          </a>
        </div>
        <div className="score-block">
          <span className="score">{formatScore(result.score)}</span>
          <span className="model">{result.ranking_model?.toUpperCase()}</span>
        </div>
      </div>

      <div className="badges" aria-label="Matched fields">
        {(result.matched_fields || []).map((field) => (
          <span className="badge" key={field}>
            {field}
          </span>
        ))}
      </div>

      {snippet ? (
        <p className="snippet">
          {result.highlighted_snippet
            ? renderHighlightedSnippet(result.highlighted_snippet)
            : result.snippet}
        </p>
      ) : (
        <p className="snippet muted">No snippet available.</p>
      )}

      {hasDebug && (
        <details className="debug-panel">
          <summary>Debug details</summary>
          <div className="debug-content">
            {(result.debug.terms || []).map((term, index) => (
              <div className="debug-row" key={`${term.term}-${index}`}>
                <span>{term.term}</span>
                <span>score {formatScore(term.total_term_score)}</span>
                <span>len {term.document_length}</span>
                <span>field {formatScore(term.field_contribution)}</span>
              </div>
            ))}
            {result.debug.adjustments && (
              <div className="debug-adjustments">
                <span>final {formatScore(result.debug.adjustments.final_score)}</span>
                <span>url boost {formatScore(result.debug.adjustments.url_query_boost)}</span>
                <span>coverage {formatScore(result.debug.adjustments.or_coverage_boost)}</span>
              </div>
            )}
          </div>
        </details>
      )}
    </article>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [ranking, setRanking] = useState("bm25");
  const [debug, setDebug] = useState(false);
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const trimmedQuery = useMemo(() => query.trim(), [query]);

  async function handleSearch(event) {
    event.preventDefault();

    if (!trimmedQuery) {
      setStatus("error");
      setError("Enter a query to search.");
      setResults([]);
      return;
    }

    setStatus("loading");
    setError("");

    const params = new URLSearchParams({
      q: trimmedQuery,
      top_k: String(topK),
      ranking,
      debug: String(debug)
    });

    try {
      const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
      const data = await response.json();

      if (!response.ok) {
        const message = data?.detail?.message || "Search request failed.";
        const command = data?.detail?.command ? ` ${data.detail.command}` : "";
        throw new Error(`${message}${command}`);
      }

      setResults(Array.isArray(data) ? data : []);
      setStatus(data.length ? "results" : "empty");
    } catch (requestError) {
      setResults([]);
      setStatus("error");
      setError(requestError.message || "Unable to reach the search API.");
    }
  }

  return (
    <main className="app-shell">
      <section className="search-panel">
        <div className="title-row">
          <div>
            <p className="eyebrow">Portfolio Search Engine System</p>
            <h1>ZotSearch</h1>
          </div>
        </div>

        <form className="search-form" onSubmit={handleSearch}>
          <div className="query-row">
            <input
              aria-label="Search query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="machine learning"
            />
            <button type="submit" disabled={status === "loading"}>
              {status === "loading" ? "Searching" : "Search"}
            </button>
          </div>

          <div className="controls-row">
            <label>
              Top K
              <input
                type="number"
                min="1"
                max="100"
                value={topK}
                onChange={(event) => setTopK(event.target.valueAsNumber || 10)}
              />
            </label>

            <label>
              Ranking
              <select value={ranking} onChange={(event) => setRanking(event.target.value)}>
                <option value="bm25">BM25</option>
                <option value="tfidf">TF-IDF</option>
              </select>
            </label>

            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={debug}
                onChange={(event) => setDebug(event.target.checked)}
              />
              Debug
            </label>
          </div>
        </form>
      </section>

      <section className="results-section" aria-live="polite">
        {status === "idle" && (
          <div className="state-box">
            <h2>Ready</h2>
            <p>Enter a query to begin.</p>
          </div>
        )}

        {status === "loading" && (
          <div className="state-box">
            <h2>Searching</h2>
            <p>Retrieving ranked results.</p>
          </div>
        )}

        {status === "error" && (
          <div className="state-box error-box">
            <h2>Search unavailable</h2>
            <p>{error}</p>
          </div>
        )}

        {status === "empty" && (
          <div className="state-box">
            <h2>No results</h2>
            <p>No documents matched this query.</p>
          </div>
        )}

        {status === "results" && (
          <div className="results-list">
            <div className="results-meta">
              <span>{results.length} results</span>
              <span>{ranking.toUpperCase()}</span>
            </div>
            {results.map((result) => (
              <ResultCard key={`${result.doc_id}-${result.url}`} result={result} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
