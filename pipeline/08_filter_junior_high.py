"""
Phase A2 candidate triage, step 1 of N: rough first pass over the 36,507
exam-only words (open-vocabulary exam corpus words absent from all 7
reference books, see 07_reprocess_exam_corpus_open_vocab.py) per LO's
instruction: drop words easier than the reference books' "基礎" tier
(e.g. have/make/like -- taught at junior-high level), UNLESS the word is
already present in one of the 基礎 books (sisutan/target1900/
sokutan_hisshu/leap_basic) under a different sense/position -- those stay,
since the "基礎" tier itself is the line, not junior-high level specifically.

JUNIOR-HIGH WORD LIST SOURCE: LO supplied two "出る順パス単" vocabulary
list PDFs (英検4級 and 英検3級 -- these two Eiken grades correspond to
Japan's junior-high curriculum level) as the ground truth, extracted here
with the same table-parsing regex as 01_extract_reference_books.py (same
publisher series/format). Single-token headwords only (multi-word phrases
and full example sentences in these PDFs are not touched by this filter --
see docstring below on why).

WHY MULTI-WORD LEMMAS ARE UNTOUCHED: excluding a junior-high-level single
word (e.g. "make") does not touch a DIFFERENT string like "make up" in the
exam corpus's term_freq -- they're separate dictionary keys. So the "熟語
(idiom) exception" LO asked for is automatic: this filter only removes
single-word tokens, never multi-word phrase entries.

THIS IS ONLY A FIRST-PASS FILTER: removes ~600 words, leaving ~35,900
candidates -- nowhere near a final adoptable word list on its own.
Frequency/coverage thresholding (how many exam papers / how many
universities a word appears in) and inflection deduplication are separate,
not-yet-applied follow-up steps.

Usage:
    python3 08_filter_junior_high.py \
        --junior-high-list data/interim/junior_high_words.json \
        --exam-freq-dir data/interim \
        --merged data/processed/merged_lemmas.json \
        --out data/interim/exam_only_candidates.json
"""
import argparse
import json
from pathlib import Path

KISO_BOOKS = ["sisutan", "target1900", "sokutan_hisshu", "leap_basic"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--junior-high-list", default=Path("data/interim/junior_high_words.json"), type=Path)
    ap.add_argument("--exam-freq-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--out", default=Path("data/interim/exam_only_candidates.json"), type=Path)
    args = ap.parse_args()

    junior_high = set(json.loads(args.junior_high_list.read_text()))

    kiso_lemmas = set()
    for b in KISO_BOOKS:
        data = json.loads((args.exam_freq_dir / f"{b}.json").read_text())
        for e in data["entries"]:
            kiso_lemmas.add(e["lemma_raw"].strip().lower())

    exclude_set = junior_high - kiso_lemmas

    merged = json.loads(args.merged.read_text())
    book_lemmas = set(e["lemma"] for e in merged["lemmas"])

    word_info: dict[str, dict] = {}
    for fp in sorted(args.exam_freq_dir.glob("exam_freq_open_*.json")):
        tier = json.loads(fp.read_text())
        for uni, info in tier["universities"].items():
            for w, tf in info["term_freq"].items():
                if w in book_lemmas or w in exclude_set:
                    continue
                entry = word_info.setdefault(w, {"total_term_freq": 0, "total_doc_freq": 0, "universities": []})
                entry["total_term_freq"] += tf
                entry["total_doc_freq"] += info["doc_freq"].get(w, 0)
                entry["universities"].append(uni)

    args.out.write_text(json.dumps(word_info, ensure_ascii=False, indent=2))
    print(f"[ok] junior-high exclusion list: {len(junior_high)} words "
          f"({len(exclude_set)} not already in a 基礎 book, actually excluded)")
    print(f"[ok] {len(word_info)} exam-only candidates remain -> {args.out}")


if __name__ == "__main__":
    main()
