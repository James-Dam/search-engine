from nltk.stem import PorterStemmer

from search_engine.core.search import get_raw_query_terms, tokenize_query


def test_tokenize_query_filters_stopwords_and_stems_terms():
    stemmer = PorterStemmer()

    assert tokenize_query("the machine learning and systems", stemmer) == [
        "machin",
        "learn",
        "system",
    ]


def test_raw_query_terms_filters_stopwords():
    assert get_raw_query_terms("the database systems") == ["database", "systems"]
