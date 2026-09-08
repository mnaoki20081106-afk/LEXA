"""
Phase A2 REDO: re-process the entire past-exam corpus with OPEN-vocabulary
word extraction, replacing 06_process_exam_file.py's closed-list matching.

WHY THIS EXISTS: 06_process_exam_file.py only counted occurrences of the
5255 lemmas already in the reference-book-derived lemma_list.txt. Any word
that appears in an actual exam paper but isn't in one of the 7 reference
books was never even looked for -- it wasn't filtered out, it was simply
never a candidate. That contradicts the project's actual goal (see
docs conversation: reference books are a difficulty BENCHMARK, not an
inclusion filter -- nearly 100% of exam-appearing vocabulary should be
adopted). This script fixes that by extracting every real English word
token from every exam paper, not just the ones already known.

REUSES CACHED DOWNLOADS: every PDF this needs was already downloaded once
via the Google Drive MCP tool during the original (buggy) run, and the
harness's tool-result cache still has them on disk (see
data/interim/_title_to_cache_map.json, built by matching each exam paper's
title -- recorded in the original exam_freq_*.json files_processed lists --
against the embedded title field of each cached tool-result file). So this
does NOT need to re-download anything from Google Drive. It DOES need to
redo text extraction/OCR, because the original run discarded extracted text
immediately after matching (never persisted it) -- see 06_process_exam_file.py
docstring "PDF text is used only transiently for counting, then discarded".

WORD VALIDITY FILTER: OCR on scanned exam pages produces plenty of garbage
tokens (misread glyphs, stray marks). Rather than a fixed lemma list, this
uses the system hunspell en_US dictionary (`hunspell -d en_US -G`, batched:
all unique tokens in a document piped through hunspell ONCE, not once per
word) to keep only tokens that are real English words. This is the same
"real word or not" signal a fixed lemma list gave us, just open-ended
instead of closed to 5255 pre-selected words.

NOT DONE HERE (explicitly out of scope, flag rather than silently skip):
  - No lemmatization beyond lowercase (same documented limitation as
    02_normalize_and_merge.py -- no lemmatizer installed). "runs"/"running"/
    "ran" are counted as distinct tokens here; a later merge step already
    does simple normalize_lemma() and would need a real lemmatizer to do
    better. Flagging, not fixing, since that's a pre-existing, separately
    documented decision.
  - No open-ended MULTI-WORD phrase discovery (e.g. finding a new idiom that
    isn't in any reference book). Phrase matching here is still against the
    known multi-word lemmas from lemma_list.txt (substring search, as
    06_process_exam_file.py did) -- discovering arbitrary new phrases from
    free text is a much harder NLP problem and wasn't asked for here
    ("単語も全部抽出して" = extract all the WORDS).

PER-FILE TOKEN CACHE + FULL TEXT (revised per LO's explicit instruction):
for every processed file, this writes a bag-of-words file under
data/interim/exam_tokens/<tier>/<safe-title>.json: {university, year, title,
used_ocr, token_freq: {word: count}}, AND -- as of this revision -- the
full extracted text under data/interim/exam_text/<tier>/<safe-title>.txt.

Earlier versions of this script deliberately discarded the extracted text
after counting (see 06_process_exam_file.py's docstring), on the reasoning
that only a numeric derivative (word counts), not the original wording,
should ever leave the temp file. That turned out to be too aggressive: it
made two later refinements impossible for lack of any context --
POS-aware lemmatization (08_lemmatize_exam_corpus.py had to fall back to a
context-free heuristic) and, concretely, telling apart a junior-high sense
of a word from a distinct, more advanced sense (e.g. "fine" = "元気な" at
junior-high level vs. "罰金" as a noun -- a real case LO raised; without
the surrounding sentence there is no way to tell which occurrence is
which). LO's explicit instruction: stop discarding the text; save it
instead. This is a full-corpus re-run (3rd OCR pass) specifically to
capture it -- see RESUMABLE below for why cached token_freq alone couldn't
just be reused this time.

RESUMABLE: safe to interrupt and re-run. A file only counts as "already
done" once BOTH its token_freq cache AND its saved text file exist -- on
this run that means every file gets reprocessed once (the token_freq
caches already existed from the previous run, but none of the text files
do yet), after which future interruptions resume cleanly. Processes
strictly one file at a time (same OCR-safety constraint as
06_process_exam_file.py / the incident that motivated it -- never
parallelize this).

Usage:
    python3 07_reprocess_exam_corpus_open_vocab.py \
        --title-map data/interim/_title_to_cache_map.json \
        --lemma-list data/processed/lemma_list.txt \
        --tokens-dir data/interim/exam_tokens \
        --agg-dir data/interim \
        [--limit 50] [--only-tier march]
"""
import argparse
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
import pytesseract

WORD_RE = re.compile(r"[a-zA-Z]+")
MIN_TEXT_LEN_BEFORE_OCR = 200

TIER_FILE_TO_CODE = {
    "exam_freq_kankandoritsu.json": "kankandoritsu",
    "exam_freq_kyoutsuu.json": "kyoutsuu",
    "exam_freq_kyuutei.json": "kyuutei",
    "exam_freq_march.json": "march",
    "exam_freq_nittokomasen.json": "nittokomasen",
    "exam_freq_soukeijouri.json": "soukeijouri",
    "exam_freq_tocky.json": "tocky",
}


def safe_filename(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", title)[:150]


def load_multiword_lemmas(path: Path) -> list:
    multi = []
    for line in path.read_text().splitlines():
        lemma = line.strip().lower()
        if lemma and " " in lemma:
            multi.append(lemma)
    return multi


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


def hunspell_valid_words(tokens: set) -> set:
    """Batch-check every unique token at once (one subprocess call per
    document, not one per word -- word-by-word would be far too slow across
    thousands of documents)."""
    if not tokens:
        return set()
    proc = subprocess.run(
        ["hunspell", "-d", "en_US", "-G"],
        input="\n".join(sorted(tokens)),
        capture_output=True, text=True,
    )
    return set(line.strip() for line in proc.stdout.splitlines() if line.strip())


def extract_open_vocab(text: str, multiword_lemmas: list) -> dict:
    lowered = text.lower()
    all_tokens = WORD_RE.findall(lowered)
    unique = set(all_tokens)
    valid = hunspell_valid_words(unique)

    counts: dict[str, int] = {}
    for tok in all_tokens:
        if tok in valid:
            counts[tok] = counts.get(tok, 0) + 1

    normalized = re.sub(r"\s+", " ", lowered)
    for phrase in multiword_lemmas:
        n = normalized.count(phrase)
        if n:
            counts[phrase] = counts.get(phrase, 0) + n
    return counts


def process_one(title: str, entry: dict, multiword_lemmas: list, tokens_dir: Path, text_dir: Path) -> dict:
    cached_path = Path(entry["cached_file"])
    result = json.loads(cached_path.read_text())
    raw_bytes = base64.b64decode(result["content"])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_pdf:
        tmp_pdf.write(raw_bytes)
        tmp_pdf.flush()
        pdf_path = Path(tmp_pdf.name)

        try:
            text = extract_text_pdfplumber(pdf_path)
        except Exception:
            text = ""
        alpha_len = len(re.sub(r"[^a-zA-Z]", "", text))
        used_ocr = False
        if alpha_len < MIN_TEXT_LEN_BEFORE_OCR:
            text = extract_text_ocr(pdf_path)
            used_ocr = True

        token_freq = extract_open_vocab(text, multiword_lemmas)

    tier_code = TIER_FILE_TO_CODE[Path(entry["tier_file"]).name]
    tier_tok_dir = tokens_dir / tier_code
    tier_tok_dir.mkdir(parents=True, exist_ok=True)
    (tier_tok_dir / f"{safe_filename(title)}.json").write_text(json.dumps({
        "university": entry["university"], "year": entry["year"], "title": title,
        "used_ocr": used_ocr, "token_freq": token_freq,
    }, ensure_ascii=False, indent=2))

    tier_text_dir = text_dir / tier_code
    tier_text_dir.mkdir(parents=True, exist_ok=True)
    (tier_text_dir / f"{safe_filename(title)}.txt").write_text(text)

    return {"tier_code": tier_code, "university": entry["university"],
            "year": entry["year"], "title": title, "used_ocr": used_ocr,
            "token_freq": token_freq}


def already_done(title: str, tier_code: str, tokens_dir: Path, text_dir: Path) -> bool:
    return ((tokens_dir / tier_code / f"{safe_filename(title)}.json").exists()
            and (text_dir / tier_code / f"{safe_filename(title)}.txt").exists())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title-map", default=Path("data/interim/_title_to_cache_map.json"), type=Path)
    ap.add_argument("--lemma-list", default=Path("data/processed/lemma_list.txt"), type=Path)
    ap.add_argument("--tokens-dir", default=Path("data/interim/exam_tokens"), type=Path)
    ap.add_argument("--text-dir", default=Path("data/interim/exam_text"), type=Path)
    ap.add_argument("--agg-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only-tier", default=None, help="e.g. march, kyuutei")
    args = ap.parse_args()

    title_map = json.loads(args.title_map.read_text())
    multiword_lemmas = load_multiword_lemmas(args.lemma_list)

    items = list(title_map.items())
    if args.only_tier:
        items = [(t, e) for t, e in items
                 if TIER_FILE_TO_CODE[Path(e["tier_file"]).name] == args.only_tier]

    todo = [(t, e) for t, e in items
            if not already_done(t, TIER_FILE_TO_CODE[Path(e["tier_file"]).name], args.tokens_dir, args.text_dir)]
    print(f"[ok] {len(items)} total, {len(items) - len(todo)} already cached, {len(todo)} remaining")

    if args.limit:
        todo = todo[: args.limit]

    for i, (title, entry) in enumerate(todo, start=1):
        try:
            r = process_one(title, entry, multiword_lemmas, args.tokens_dir, args.text_dir)
        except Exception as e:
            print(f"[error] {i}/{len(todo)} {title}: {e}")
            continue

        agg_path = args.agg_dir / f"exam_freq_open_{r['tier_code']}.json"
        agg = {"universities": {}}
        if agg_path.exists():
            agg = json.loads(agg_path.read_text())
        bucket = agg.setdefault("universities", {}).setdefault(
            r["university"], {"doc_count": 0, "term_freq": {}, "doc_freq": {}})
        bucket["doc_count"] += 1
        for lemma, n in r["token_freq"].items():
            bucket["term_freq"][lemma] = bucket["term_freq"].get(lemma, 0) + n
            bucket["doc_freq"][lemma] = bucket["doc_freq"].get(lemma, 0) + 1
        agg.setdefault("files_processed", []).append({
            "university": r["university"], "year": r["year"], "title": r["title"],
            "used_ocr": r["used_ocr"], "distinct_word_count": len(r["token_freq"]),
        })
        agg_path.write_text(json.dumps(agg, ensure_ascii=False, indent=2))

        print(f"[ok] {i}/{len(todo)} {title} ({r['university']} {r['year']}): "
              f"{len(r['token_freq'])} distinct words (ocr={r['used_ocr']})")

    print(f"[done] processed {len(todo)} files this run")


if __name__ == "__main__":
    main()
