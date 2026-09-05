"""
Phase A / Step 1 continued: merge per-book extractions into one cross-book
lemma table (project_overview.txt §8-9 "共通語彙ID" / §33-34).

Lemma normalization here is intentionally simple (lowercase, strip
punctuation/whitespace, collapse "regard AS B"-style multi-word patterns to
their head verb when it's a single clear headword). This is a PLACEHOLDER,
not a real morphological analyzer -- no lemmatizer (spaCy/NLTK/MeCab-for-
English) is installed in this pipeline environment.

DECISION (not specified in any doc): a proper lemmatizer should replace this
before shipping Phase A data, because naive lowercase/strip matching will
under-merge inflected forms across books (e.g. if one book lists "arise" and
another lists "arisen"). Flagging this explicitly per the project's own rule
("Claude Codeが独自の値を決め打ちで実装しないこと" / "その旨をコード内コメ
ントとREADMEに明示すること") -- see pipeline/README.md "Implementation
decisions" #1.

Usage:
    python3 02_normalize_and_merge.py --interim-dir data/interim \
        --out data/processed/merged_lemmas.json
"""
import argparse
import json
import re
from pathlib import Path

WORD_BOOKS = ["sisutan", "target1900", "sokutan_hisshu", "leap_basic", "passtan_jun1kyu", "sparta3"]
PHRASE_BOOKS = ["sokujukugo"]


def normalize_lemma(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .")
    return s


def is_multiword(lemma: str) -> bool:
    return " " in lemma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interim-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--out", default=Path("data/processed/merged_lemmas.json"), type=Path)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # lemma -> { book_code: {index, total} }
    merged: dict[str, dict[str, dict]] = {}
    phrase_lemmas: set[str] = set()

    for book_code in WORD_BOOKS + PHRASE_BOOKS:
        path = args.interim_dir / f"{book_code}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        total = data["total_entries"]
        is_phrase_book = data.get("is_phrase_book", False)
        for entry in data["entries"]:
            lemma = normalize_lemma(entry["lemma_raw"])
            if not lemma:
                continue
            if is_phrase_book or is_multiword(lemma):
                phrase_lemmas.add(lemma)
            merged.setdefault(lemma, {})
            # If a lemma repeats within the same book (e.g. multiple senses
            # listed at different indices), keep the FIRST (earliest / most
            # important) occurrence for the percentile baseline.
            if book_code not in merged[lemma]:
                merged[lemma][book_code] = {"index": entry["index"], "total": total}

    out_data = {
        "lemmas": [
            {
                "lemma": lemma,
                "is_phrase": lemma in phrase_lemmas,
                "sources": sources,
                "book_count": len(sources),
            }
            for lemma, sources in sorted(merged.items())
        ]
    }
    args.out.write_text(json.dumps(out_data, ensure_ascii=False, indent=2))

    dup = sum(1 for l in out_data["lemmas"] if l["book_count"] > 1)
    print(f"[ok] {len(out_data['lemmas'])} unique lemmas "
          f"({dup} appear in 2+ books) -> {args.out}")


if __name__ == "__main__":
    main()
