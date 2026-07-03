from collections import Counter, defaultdict
from urllib.parse import urldefrag
from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer
import json
import re
import os
import heapq

# Regex to match alphanumeric tokens (words and numbers)
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# HTML tags that are considered important (boosted in ranking)
IMPORTANT_TAGS = ["title", "h1", "h2", "h3", "b", "strong"]
HEADER_TAGS = ["h1", "h2", "h3"]
BOLD_TAGS = ["b", "strong"]

# How many documents to process before flushing the in-memory index to disk
# This prevents memory overload for large datasets
FLUSH_EVERY = 10000


def tokenize(text, stemmer, stem_cache):
    """
    Tokenizes the text into alphanumeric sequences and applies Porter stemming.
    stem_cache avoids repeated stemming for the same token.
    """
    tokens = TOKEN_RE.findall(text.lower())
    result = []

    for token in tokens:
        if token not in stem_cache:
            # stem the token once and store it
            stem_cache[token] = stemmer.stem(token)
        result.append(stem_cache[token])

    return result


def extract_text_fields(html_content):
    """
    Extract both full page text and important text (title/headings/bold)
    so important words can be boosted later during scoring.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # remove scripts/styles/noscript to avoid noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # full text of the page
    full_text = soup.get_text(separator=" ", strip=True)

    # important text from title/headings/bold
    important_text_parts = []
    for tag in soup.find_all(IMPORTANT_TAGS):
        important_text_parts.append(tag.get_text(separator=" ", strip=True))
    important_text = " ".join(important_text_parts)

    return full_text, important_text


def extract_document_fields(html_content):
    """
    Extract full text plus field-specific text used by ranking.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    full_text = soup.get_text(separator=" ", strip=True)
    title_text = " ".join(
        tag.get_text(separator=" ", strip=True) for tag in soup.find_all("title")
    )
    header_text = " ".join(
        tag.get_text(separator=" ", strip=True) for tag in soup.find_all(HEADER_TAGS)
    )
    bold_text = " ".join(
        tag.get_text(separator=" ", strip=True) for tag in soup.find_all(BOLD_TAGS)
    )

    return {
        "full_text": full_text,
        "title_text": title_text,
        "header_text": header_text,
        "bold_text": bold_text,
    }


def write_partial_index(inverted_index, output_folder, block_id):
    """
    Flush the current in-memory index to disk as a sorted partial index.
    Sorting helps later when merging partial indexes into the final index.
    """
    os.makedirs(output_folder, exist_ok=True)
    partial_path = os.path.join(output_folder, f"partial_index_{block_id}.json")

    with open(partial_path, "w", encoding="utf-8") as f:
        for term in sorted(inverted_index.keys()):
            line = json.dumps({term: inverted_index[term]}, separators=(",", ":"))
            f.write(line + "\n")

    return partial_path


def merge_partial_indexes(partial_paths, output_folder):
    """
    K-way merge of all sorted partial index files into one final index.
    Builds a term -> byte offset map for fast term lookup during search.
    """
    final_index_path = os.path.join(output_folder, "final_index.txt")
    term_offsets = {}

    # Open all partial index files for streaming
    file_handles = [open(p, "r", encoding="utf-8") for p in partial_paths]

    def read_next(fh):
        line = fh.readline()
        if not line:
            return None
        obj = json.loads(line.strip())
        term, postings = next(iter(obj.items()))
        return term, postings

    # Heap to maintain the smallest term from each partial file
    heap = []
    buffers = []
    for i, fh in enumerate(file_handles):
        entry = read_next(fh)
        buffers.append(entry)
        if entry:
            heapq.heappush(heap, (entry[0], i))

    # Write final index in binary mode for reliable byte offsets
    with open(final_index_path, "wb") as out:
        current_term = None
        merged_postings = []

        while heap:
            term, file_idx = heapq.heappop(heap)
            _, postings = buffers[file_idx]

            if term == current_term:
                # Same term from a different partial file — merge postings
                merged_postings.extend(postings)
            else:
                # Write previous term's postings to disk
                if current_term is not None:
                    term_offsets[current_term] = out.tell()
                    line = json.dumps(merged_postings, separators=(",", ":")) + "\n"
                    out.write(line.encode("utf-8"))

                current_term = term
                merged_postings = list(postings)

            # Advance file we just read from
            next_entry = read_next(file_handles[file_idx])
            buffers[file_idx] = next_entry
            if next_entry:
                heapq.heappush(heap, (next_entry[0], file_idx))

        # Write the last term
        if current_term is not None:
            term_offsets[current_term] = out.tell()
            line = json.dumps(merged_postings, separators=(",", ":")) + "\n"
            out.write(line.encode("utf-8"))

    # Close all file handles and remove partials
    for fh in file_handles:
        fh.close()
    for p in partial_paths:
        os.remove(p)

    # Save term -> offset map for fast search lookups
    offsets_path = os.path.join(output_folder, "term_offsets.json")
    with open(offsets_path, "w", encoding="utf-8") as f:
        json.dump(term_offsets, f, separators=(",", ":"))

    return final_index_path, offsets_path


def index(root_folder, output_folder="index_output"):
    """
    Main indexer function:
    - Loops through all JSON files
    - Extracts full text and important text
    - Tokenizes and counts frequencies
    - Flushes partial indexes to disk periodically to save memory
    - Finally merges all partials into a single searchable index
    """
    inverted_index = defaultdict(list)
    stemmer = PorterStemmer()
    stem_cache = {}

    doc_map = {}
    doc_counter = 0
    partial_paths = []
    block_id = 0
    seen_urls = set()  # avoid duplicate URLs

    for root, dirs, files in os.walk(root_folder):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith('.json'):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Skip duplicate URLs or empty content
                    raw_url = data.get("url", "")
                    clean_url, _ = urldefrag(raw_url)
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    html_content = data.get('content', '')
                    if not html_content.strip():
                        continue

                    fields = extract_document_fields(html_content)

                    tokens = tokenize(fields["full_text"], stemmer, stem_cache)
                    title_tokens = tokenize(fields["title_text"], stemmer, stem_cache)
                    header_tokens = tokenize(fields["header_text"], stemmer, stem_cache)
                    bold_tokens = tokenize(fields["bold_text"], stemmer, stem_cache)
                    url_tokens = set(tokenize(clean_url, stemmer, stem_cache))

                    document_length = len(tokens)
                    if document_length == 0:
                        continue

                    doc_counter += 1
                    curr_doc_id = doc_counter

                    doc_map[curr_doc_id] = {
                        "url": clean_url,
                        "path": full_path,
                        "document_length": document_length,
                    }

                    term_freqs = Counter(tokens)
                    title_freqs = Counter(title_tokens)
                    header_freqs = Counter(header_tokens)
                    bold_freqs = Counter(bold_tokens)

                    for term, freq in term_freqs.items():
                        title_hits = title_freqs.get(term, 0)
                        header_hits = header_freqs.get(term, 0)
                        bold_hits = bold_freqs.get(term, 0)
                        inverted_index[term].append(
                            {
                                "doc_id": curr_doc_id,
                                "document_length": document_length,
                                "title_hits": title_hits,
                                "header_hits": header_hits,
                                "bold_hits": bold_hits,
                                "url_match_flag": 1 if term in url_tokens else 0,
                                "raw_term_frequency": freq,
                                "normalized_term_frequency": freq / document_length,
                                "important_term_frequency": title_hits + header_hits + bold_hits,
                            }
                        )

                    # Flush partial index periodically
                    if doc_counter % FLUSH_EVERY == 0:
                        block_id += 1
                        print(f"Flushing partial index #{block_id} at doc {doc_counter}...")
                        path = write_partial_index(inverted_index, output_folder, block_id)
                        partial_paths.append(path)
                        inverted_index = defaultdict(list)  # clear memory

                except Exception as e:
                    # Skip malformed files but continue
                    print(f"Error processing {full_path}: {e}")

    # Flush whatever is left
    if inverted_index:
        block_id += 1
        print(f"Flushing final partial index #{block_id} at doc {doc_counter}...")
        path = write_partial_index(inverted_index, output_folder, block_id)
        partial_paths.append(path)

    # Merge partials into final index
    print(f"\nMerging {len(partial_paths)} partial indexes...")
    final_index_path, offsets_path = merge_partial_indexes(partial_paths, output_folder)
    print("Merge complete.")

    return doc_map, final_index_path, offsets_path


def write_index_and_report(doc_map, final_index_path, offsets_path, output_folder="index_output"):
    """
    Writes the doc_map and a student-friendly report.
    The actual index is already on disk from the merge step.
    """
    os.makedirs(output_folder, exist_ok=True)

    doc_map_path = os.path.join(output_folder, "doc_map.json")
    metadata_path = os.path.join(output_folder, "index_metadata.json")
    report_path = os.path.join(output_folder, "report.txt")

    str_doc_map = {str(k): v for k, v in doc_map.items()}
    with open(doc_map_path, "w", encoding="utf-8") as f:
        json.dump(str_doc_map, f, indent=2)

    with open(offsets_path, "r", encoding="utf-8") as f:
        term_offsets = json.load(f)

    total_doc_length = sum(doc.get("document_length", 0) for doc in doc_map.values())
    avg_doc_len = total_doc_length / len(doc_map) if doc_map else 0
    metadata = {
        "postings_format": "v2",
        "ranking_default": "bm25",
        "num_documents": len(doc_map),
        "avg_doc_len": avg_doc_len,
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    index_size_kb = (
        os.path.getsize(final_index_path)
        + os.path.getsize(doc_map_path)
        + os.path.getsize(offsets_path)
        + os.path.getsize(metadata_path)
    ) / 1024

    num_documents = len(doc_map)
    num_unique_tokens = len(term_offsets)

    # Write report with friendly explanations for demo
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Indexer Analytics Report\n")
        f.write("========================\n\n")
        f.write(f"Number of indexed documents: {num_documents}\n")
        f.write(f"Number of unique tokens: {num_unique_tokens}\n")
        f.write(f"Average document length: {avg_doc_len:.2f} tokens\n")
        f.write(f"Total size of index on disk: {index_size_kb:.2f} KB\n")

    print("\n--- REPORT ---")
    print(f"Number of indexed documents: {num_documents}")
    print(f"Number of unique tokens: {num_unique_tokens}")
    print(f"Average document length: {avg_doc_len:.2f} tokens")
    print(f"Total size of index on disk: {index_size_kb:.2f} KB")
