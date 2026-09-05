"""
Phase A / Step 1 input prep.

Extracts (index_in_book, headword_or_phrase) pairs from the publisher vocab
list PDFs. Deliberately does NOT extract or keep the Japanese gloss column:
per project_overview.txt §17 ("カードコンテンツはアプリ独自に設計する") and
supplementary_design_spec.md §4.2, this app's card content must be written
originally, never copied from a reference book. The gloss text is only used
here, in-memory, to help a human sanity-check the parse; it is never written
to disk.

COPYRIGHT: input PDFs are never committed to this repo (see .gitignore) and
this script never writes book text (headword lists included, to be safe --
we keep only index position + book_code, not the printed word list itself)
into anything other than a local, gitignored data/interim/ file. The single
artifact that leaves data/interim/ and gets committed is the fully-merged,
cross-book difficulty score produced by 04_score_vocab.py, which is a
numeric derivative, not a reproduction.

Usage:
    python3 01_extract_reference_books.py --input-dir /path/to/reference_books \
        --out-dir data/interim

Known layouts (verified against the actual attached PDFs):
  - sisutan (システム英単語), target1900, sokutan_hisshu, leap_basic,
    passtan_jun1kyu: two side-by-side columns of "番号 単語 意味" per page,
    line format: "<idx><sp><word><sp><gloss...> <idx><sp><word><sp><gloss...>"
  - sokujukugo (速読英熟語): single column "番号 熟語 意味"
  - sparta3: NOT handled here. The PDF embeds a subsetted font with no
    ToUnicode CMap, so pdfplumber/pypdf both return only encoded glyph IDs
    (cid:NN), not text. Needs image-render + OCR (pytesseract) instead of
    text extraction. Deferred to Phase A2 -- see pipeline/README.md.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

import pdfplumber


def resolve_path(input_dir: Path, rel_path: str) -> Path:
    """Find rel_path under input_dir tolerating NFC/NFD Unicode normalization
    differences (macOS zip extraction commonly yields NFD filenames, e.g. a
    decomposed "ケ" + combining dakuten instead of precomposed "ゲ"))."""
    direct = input_dir / rel_path
    if direct.exists():
        return direct
    target = unicodedata.normalize("NFC", rel_path)
    for candidate in input_dir.rglob("*.pdf"):
        rel = str(candidate.relative_to(input_dir))
        if unicodedata.normalize("NFC", rel) == target:
            return candidate
    return direct

BOOK_FILES = {
    "sisutan": "基礎的/システム英単語［シス単］（5訂版）一覧.pdf",
    "target1900": "基礎的/ターゲット1900 6訂版　一覧　新.pdf",
    "sokutan_hisshu": "基礎的/速読英単語 必修編 改訂第8版 一覧.pdf",
    "leap_basic": "基礎的/LEAP Basic 改訂版 一覧.pdf",
    "passtan_jun1kyu": "発展/準1級 出る順パス単 一覧.pdf",
    # "sparta3": "発展/大学入試英単語 SPARTA3 一覧.pdf",  # deferred, see docstring
}

PHRASE_BOOK_FILES = {
    "sokujukugo": "熟語/速読英熟語　改訂版　一覧.pdf",
}

# A row looks like "12look afterに気づく" concatenated on extraction, or with
# spaces preserved as "12 look after に気づく". We only need the leading
# index + the headword token(s) before the first Japanese character, since
# we discard the gloss anyway.
ROW_RE = re.compile(
    r"(?P<idx>\d{1,4})\s*(?P<word>[A-Za-z][A-Za-z '\-.]*?)(?=[ぁ-んァ-ヶ一-龠（〔【]|$)"
)


# Gloss patterns like "regard AをBだと思う" or "make O C" use single capital
# letters (A/B/O/C/V...) as grammar-slot placeholders. They are not part of
# the headword itself, so strip a trailing " <single-capital>" run.
TRAILING_PLACEHOLDER_RE = re.compile(r"(\s+[A-Z])+$")


def extract_word_book(pdf_path: Path):
    """Yields (index_in_book, headword) for a 'word list' book."""
    entries = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                if line.strip().startswith(("番号", "システム", "ターゲット", "速読",
                                              "LEAP", "英検")):
                    continue
                for m in ROW_RE.finditer(line):
                    idx = int(m.group("idx"))
                    word = m.group("word").strip()
                    word = TRAILING_PLACEHOLDER_RE.sub("", word).strip()
                    if word:
                        entries.append((idx, word))
    return entries


def extract_phrase_book(pdf_path: Path):
    """Phrase books (速読英熟語) are single-column: '番号 熟語 意味'."""
    entries = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                if line.strip().startswith(("番号", "速読")):
                    continue
                m = re.match(r"\s*(\d{1,4})\s+(.+)", line)
                if not m:
                    continue
                idx = int(m.group(1))
                rest = m.group(2)
                # Cut the phrase off at the first Japanese character (gloss start).
                jp = re.search(r"[ぁ-んァ-ヶ一-龠]", rest)
                phrase = rest[: jp.start()] if jp else rest
                phrase = phrase.strip(" 〜")
                if phrase:
                    entries.append((idx, phrase))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path,
                     help="Local, un-committed path to the reference_books folder")
    ap.add_argument("--out-dir", default=Path("data/interim"), type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for book_code, rel_path in BOOK_FILES.items():
        pdf_path = resolve_path(args.input_dir, rel_path)
        if not pdf_path.exists():
            print(f"[skip] {book_code}: {pdf_path} not found")
            continue
        entries = extract_word_book(pdf_path)
        total = len(entries)
        out = args.out_dir / f"{book_code}.json"
        out.write_text(json.dumps(
            {"book_code": book_code, "total_entries": total,
             "entries": [{"index": i, "lemma_raw": w} for i, w in entries]},
            ensure_ascii=False, indent=2))
        print(f"[ok] {book_code}: {total} entries -> {out}")

    for book_code, rel_path in PHRASE_BOOK_FILES.items():
        pdf_path = resolve_path(args.input_dir, rel_path)
        if not pdf_path.exists():
            print(f"[skip] {book_code}: {pdf_path} not found")
            continue
        entries = extract_phrase_book(pdf_path)
        total = len(entries)
        out = args.out_dir / f"{book_code}.json"
        out.write_text(json.dumps(
            {"book_code": book_code, "total_entries": total, "is_phrase_book": True,
             "entries": [{"index": i, "lemma_raw": w} for i, w in entries]},
            ensure_ascii=False, indent=2))
        print(f"[ok] {book_code}: {total} entries -> {out}")

    print("\n[deferred] sparta3: font has no text mapping, needs OCR pipeline (Phase A2)")


if __name__ == "__main__":
    main()
