import json

from search_engine.core.search import build_snippet, highlight_snippet


def write_doc(tmp_path, html):
    path = tmp_path / "doc.json"
    path.write_text(
        json.dumps({"url": "https://example.edu", "content": html}),
        encoding="utf-8",
    )
    return path


def test_build_snippet_prefers_matched_query_terms(tmp_path):
    path = write_doc(
        tmp_path,
        """
        <html>
          <head><title>Search Demo</title></head>
          <body>
            Intro text that should be trimmed before the useful passage.
            Machine learning appears in the important middle of this document
            with enough surrounding words to form a compact search result.
          </body>
        </html>
        """,
    )

    title, snippet = build_snippet({"path": str(path)}, ["machine"], max_chars=120)

    assert title == "Search Demo"
    assert "Machine learning" in snippet
    assert len(snippet) <= 126


def test_build_snippet_handles_missing_source_file_gracefully():
    assert build_snippet({"path": "missing.json"}, ["machine"]) == ("", "")


def test_highlight_snippet_escapes_html_and_marks_terms():
    highlighted = highlight_snippet("Machine <learning> is useful", ["machine", "learning"])

    assert "<mark>Machine</mark>" in highlighted
    assert "&lt;<mark>learning</mark>&gt;" in highlighted
