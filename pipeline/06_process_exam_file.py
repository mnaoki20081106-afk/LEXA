"""
Phase A2: process ONE past-exam PDF already fetched via the Google Drive MCP
tool, and fold its vocabulary into a per-tier frequency aggregate.

This is deliberately a single-file-at-a-time CLI (supplementary_design_spec.md
§4.1: never load the whole corpus at once; §4.2/4.3: PDF text is used only
transiently for counting, then discarded -- never persisted).

Why this exists as a shared script rather than ad-hoc code per worker: the
past-exam corpus is large enough (thousands of files across 7 tiers) that
multiple background agents process it in parallel, one tier each. This
script is the one piece of logic all of them call, so extraction/OCR/
matching behavior is identical and tested once, not reimplemented per agent.

Input: the LOCAL FILE PATH of a saved Google Drive MCP tool-result (the
harness auto-saves `download_file_content` results that are too large to
inline, as {"content": "<base64>", "id", "mimeType", "title"} JSON -- see
this repo's session notes). This script never receives or prints the raw
base64/PDF bytes to stdout; it reads the JSON straight off disk, decodes to
a temp file, extracts text, deletes the temp file, and only ever prints/
writes small numeric aggregates.

Matching: tokenizes extracted text into lowercase [a-z]+ runs for single-
word lemma matching, AND does whitespace-normalized substring search for
multi-word phrase lemmas (e.g. "look forward to"). Both come from
`lemma_list.txt` (one lemma per line, produced by 05_build_word_table.py's
output).

Usage (one call per file):
    python3 06_process_exam_file.py \
        --tool-result /path/to/saved-mcp-result.txt \
        --university "東京大学" \
        --year 2024 \
        --lemma-list data/processed/lemma_list.txt \
        --agg-out data/interim/exam_freq_kyuutei.json

Repeated calls with the same --agg-out accumulate into one aggregate file
(read-modify-write; fine for a single sequential worker per tier).
"""
import argparse
import base64
import json
import re
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
import pytesseract

WORD_RE = re.compile(r"[a-zA-Z]+")
MIN_TEXT_LEN_BEFORE_OCR = 200  # alphabetic chars; below this, assume scanned


def load_lemmas(path: Path):
    single, multi = set(), []
    for line in path.read_text().splitlines():
        lemma = line.strip().lower()
        if not lemma:
            continue
        if " " in lemma:
            multi.append(lemma)
        else:
            single.add(lemma)
    return single, multi


def extract_text_pdfplumber(pdf_path: Path) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n".join(parts)


def extract_text_ocr(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    parts = []
    mat = fitz.Matrix(200 / 72, 200 / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_png:
            pix.save(tmp_png.name)
            parts.append(pytesseract.image_to_string(tmp_png.name, lang="eng"))
    return "\n".join(parts)


def count_matches(text: str, single: set, multi: list) -> dict:
    lowered = text.lower()
    normalized = re.sub(r"\s+", " ", lowered)
    counts: dict[str, int] = {}
    for tok in WORD_RE.findall(lowered):
        if tok in single:
            counts[tok] = counts.get(tok, 0) + 1
    for phrase in multi:
        n = normalized.count(phrase)
        if n:
            counts[phrase] = counts.get(phrase, 0) + n
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool-result", required=True, type=Path,
                     help="Path to the saved MCP download_file_content JSON result")
    ap.add_argument("--university", required=True,
                     help="Aggregation key, e.g. a university name or tier name")
    ap.add_argument("--year", default="")
    ap.add_argument("--lemma-list", required=True, type=Path)
    ap.add_argument("--agg-out", required=True, type=Path)
    args = ap.parse_args()

    result = json.loads(args.tool_result.read_text())
    raw_bytes = base64.b64decode(result["content"])

    single, multi = load_lemmas(args.lemma_list)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_pdf:
        tmp_pdf.write(raw_bytes)
        tmp_pdf.flush()
        pdf_path = Path(tmp_pdf.name)

        text = extract_text_pdfplumber(pdf_path)
        alpha_len = len(re.sub(r"[^a-zA-Z]", "", text))
        used_ocr = False
        if alpha_len < MIN_TEXT_LEN_BEFORE_OCR:
            text = extract_text_ocr(pdf_path)
            used_ocr = True

        counts = count_matches(text, single, multi)
        # `text` and `raw_bytes` go out of scope with the temp file deletion
        # (NamedTemporaryFile delete=True) -- nothing exam-derived is written
        # to disk beyond this function call, per copyright policy.

    agg = {"tier_or_university": {}}
    if args.agg_out.exists():
        agg = json.loads(args.agg_out.read_text())

    bucket = agg.setdefault("universities", {}).setdefault(
        args.university, {"doc_count": 0, "term_freq": {}, "doc_freq": {}})
    bucket["doc_count"] += 1
    for lemma, n in counts.items():
        bucket["term_freq"][lemma] = bucket["term_freq"].get(lemma, 0) + n
        bucket["doc_freq"][lemma] = bucket["doc_freq"].get(lemma, 0) + 1

    agg.setdefault("files_processed", []).append({
        "university": args.university, "year": args.year,
        "title": result.get("title"), "used_ocr": used_ocr,
        "matched_lemma_count": len(counts),
    })

    args.agg_out.parent.mkdir(parents=True, exist_ok=True)
    args.agg_out.write_text(json.dumps(agg, ensure_ascii=False, indent=2))
    print(f"[ok] {result.get('title')}: {len(counts)} distinct lemmas matched "
          f"(ocr={used_ocr}) -> {args.agg_out}")


if __name__ == "__main__":
    main()
