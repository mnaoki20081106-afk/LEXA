"""
Phase A2 candidate triage, step 1.5 (runs between 08_lemmatize_exam_corpus.py
and 09_filter_junior_high.py): extract the junior-high-level word list that
09 uses for exclusion, from two "出る順パス単" Eiken vocabulary-list PDFs
(英検4級, 英検3級 -- these two grades correspond to Japan's junior-high
curriculum level) LO supplied. Same publisher-series table format as the
existing 基礎/発展 reference books, parsed with the same style of regex as
01_extract_reference_books.py.

REGEX FIXES (found via 11_frequency_analysis.py's top-breadth sanity
check, which turned up "be/to/in/for/as/on/can/you" polluting the top of
the exam-only candidate list -- these should have been excluded as
junior-high words but silently fell through the first version of this
extraction):
  1. Some kanji in these specific PDFs extract as CJK Radical Supplement /
     Kangxi Radical codepoints (U+2E80-2EFF, U+2F00-2FDF) instead of
     ordinary CJK Unified Ideographs (U+4E00-9FA0) -- e.g. "行く" extracts
     as "⾏く" with a different "行". The original regex's Japanese-glyph
     lookahead only covered the ordinary range, so it never found the
     word/gloss boundary for these rows and silently dropped the whole
     entry. Fixed by widening the lookahead to include both CJK radical
     ranges.
  2. A few rows have no visible gloss text before the next entry's index
     number (e.g. "17 now 42 university ..." with nothing readable between
     "now" and "42" -- some extraction artifact upstream of us), so the
     lookahead needs "immediately followed by a digit" as an additional
     valid stop condition, not just Japanese glyphs/parens.
  3. Single-character results are dropped outright -- see
     12_filter_function_words.py's docstring on why (OCR/table-formatting
     noise, not real single-letter English content words).

RESIDUAL GAP (documented, not fixed by parsing): a handful of ultra-common
words (how/why/where/when/use/want/less/long/new/now) are genuinely absent
from both source PDFs as standalone headwords -- verified by grepping the
raw extracted text -- they only appear there embedded in phrases ("want to
do", "Why not?"). These are handled separately as
12_filter_function_words.py's ULTRA_BASIC_SUPPLEMENT, not by this script.

Usage:
    python3 08b_extract_junior_high_words.py \
        --eiken4-pdf /path/to/英検4級_出る順パス単.pdf \
        --eiken3-pdf /path/to/英検3級_出る順パス単.pdf \
        --out data/interim/junior_high_words.json
"""
import argparse
import json
import re
from pathlib import Path

import pdfplumber

ROW_RE = re.compile(
    r"(?P<idx>\d{1,4})\s*(?P<word>[A-Za-z][A-Za-z '\-.]*?)(?=[ぁ-んァ-ヶ一-龠⺀-⿟（〔【\d]|$)"
)


def extract_words(pdf_path: Path) -> set:
    words = set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                if line.strip().startswith(("番号", "英検", "出る順")):
                    continue
                for m in ROW_RE.finditer(line):
                    word = m.group("word").strip().lower()
                    if re.fullmatch(r"[a-z]+", word) and len(word) > 1:
                        words.add(word)
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eiken4-pdf", required=True, type=Path)
    ap.add_argument("--eiken3-pdf", required=True, type=Path)
    ap.add_argument("--out", default=Path("data/interim/junior_high_words.json"), type=Path)
    args = ap.parse_args()

    words = extract_words(args.eiken4_pdf) | extract_words(args.eiken3_pdf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sorted(words), ensure_ascii=False, indent=2))
    print(f"[ok] {len(words)} junior-high single-word candidates -> {args.out}")


if __name__ == "__main__":
    main()
