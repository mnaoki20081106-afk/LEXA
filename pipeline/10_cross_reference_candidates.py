"""
Phase A2 candidate triage, step 3: cross-reference every lemma this
project knows about (both the 5,255 reference-book lemmas and the 22,206
exam-only candidates from 09_filter_junior_high.py) into one annotated
table. This does NOT decide or delete anything -- it only records, per
lemma:
  - whether it's in a reference book, and if so which one(s) / how many
  - how much it actually appears in the past-exam corpus (term/doc
    frequency, how many universities)

WHY THIS EXISTS (per LO): reference-book membership is a strong positive
signal ("最優先グループ"), but its ABSENCE is not a negative signal --
a word missing from all 7 reference books can still be exam-important.
This table exists to give the next triage step (whatever threshold/rule
comes after this) more axes to sort on, not to pre-judge which axis wins.
No word is dropped here, from either side.

Usage:
    python3 10_cross_reference_candidates.py \
        --merged data/processed/merged_lemmas.json \
        --exam-freq-dir data/interim \
        --out data/interim/vocab_candidate_master.json
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--exam-freq-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--out", default=Path("data/interim/vocab_candidate_master.json"), type=Path)
    args = ap.parse_args()

    merged = json.loads(args.merged.read_text())
    book_info = {e["lemma"]: {"reference_book_codes": sorted(e["sources"].keys()),
                               "book_count": e["book_count"],
                               "is_phrase": e["is_phrase"]}
                 for e in merged["lemmas"]}

    exam_stats: dict[str, dict] = {}
    for fp in sorted(args.exam_freq_dir.glob("exam_freq_open_*.json")):
        tier = json.loads(fp.read_text())
        for uni, info in tier["universities"].items():
            for lemma, tf in info["term_freq"].items():
                s = exam_stats.setdefault(lemma, {"total_term_freq": 0, "total_doc_freq": 0, "universities": set()})
                s["total_term_freq"] += tf
                s["total_doc_freq"] += info["doc_freq"].get(lemma, 0)
                s["universities"].add(uni)

    all_lemmas = set(book_info) | set(exam_stats)
    table = {}
    for lemma in sorted(all_lemmas):
        b = book_info.get(lemma)
        e = exam_stats.get(lemma)
        in_book = b is not None
        in_exam = e is not None
        table[lemma] = {
            "in_reference_book": in_book,
            "reference_book_codes": b["reference_book_codes"] if b else [],
            "book_count": b["book_count"] if b else 0,
            "is_phrase": b["is_phrase"] if b else (" " in lemma),
            "exam_total_term_freq": e["total_term_freq"] if e else 0,
            "exam_total_doc_freq": e["total_doc_freq"] if e else 0,
            "exam_university_count": len(e["universities"]) if e else 0,
            "source": "both" if (in_book and in_exam) else ("reference_book_only" if in_book else "exam_only"),
        }

    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=2))

    both = sum(1 for v in table.values() if v["source"] == "both")
    book_only = sum(1 for v in table.values() if v["source"] == "reference_book_only")
    exam_only = sum(1 for v in table.values() if v["source"] == "exam_only")
    multi_book = sum(1 for v in table.values() if v["book_count"] >= 2)
    print(f"[ok] {len(table)} total lemmas -> {args.out}")
    print(f"  in reference book AND in exam corpus (both): {both}")
    print(f"  reference book only (never seen in processed exams): {book_only}")
    print(f"  exam-only (not in any reference book): {exam_only}")
    print(f"  appear in 2+ reference books: {multi_book}")


if __name__ == "__main__":
    main()
