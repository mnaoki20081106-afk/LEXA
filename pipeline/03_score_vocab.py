"""
Phase A: difficulty scoring per vocab_scoring_algorithm.txt §3.

Implements:
  Step 1 - Base_Score: mean percentile position across the books a lemma
           appears in, with a duplicate-appearance discount (0.9 per the
           spec's example factor) applied multiplicatively per extra book.
  Step 3 - Normalize Base_Score (+ Boost_Score, currently 0) to 0.0-10.0.

Step 2 (入試特異性ブースト / past-exam TF-IDF boost) is NOT implemented yet.
It requires the past-exam PDF corpus (Google Drive 過去問.zip, 2.7GB) which
needs a separate OCR + TF-IDF pipeline (mixed scanned/text PDFs) that hasn't
been built yet -- see pipeline/README.md "Deferred: Step 2 / past-exam
corpus". boost_score_raw is written as 0.0 for every lemma so the schema
and app-side code can be written against the final shape now; re-running
this script after Step 2 exists will backfill real boost values without
requiring any schema change.

Usage:
    python3 03_score_vocab.py --merged data/processed/merged_lemmas.json \
        --out data/processed/vocab_scored.json
"""
import argparse
import json
from pathlib import Path

DUPLICATE_DISCOUNT = 0.9  # vocab_scoring_algorithm.txt §3 Step1 example value


def base_score(sources: dict) -> float:
    percentiles = [info["index"] / info["total"] for info in sources.values()]
    mean_percentile = sum(percentiles) / len(percentiles)
    # Apply the duplicate discount once per additional book beyond the first,
    # per "重複して掲載されている単語は...重複割引係数（例: 0.9）を掛けて
    # 難易度を下げる" -- lower score = easier/more foundational.
    extra_books = len(sources) - 1
    return mean_percentile * (DUPLICATE_DISCOUNT ** extra_books)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--out", default=Path("data/processed/vocab_scored.json"), type=Path)
    args = ap.parse_args()

    data = json.loads(args.merged.read_text())
    lemmas = data["lemmas"]

    raw_scores = []
    for entry in lemmas:
        b = base_score(entry["sources"])
        entry["base_score_raw"] = b
        entry["boost_score_raw"] = 0.0  # TBD: Step 2, see docstring
        entry["raw_score"] = b + entry["boost_score_raw"]
        raw_scores.append(entry["raw_score"])

    lo, hi = min(raw_scores), max(raw_scores)
    span = (hi - lo) or 1.0
    for entry in lemmas:
        entry["difficulty_level"] = round(10.0 * (entry["raw_score"] - lo) / span, 3)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"lemmas": lemmas}, ensure_ascii=False, indent=2))

    lemmas_sorted = sorted(lemmas, key=lambda e: e["difficulty_level"])
    print(f"[ok] scored {len(lemmas)} lemmas -> {args.out}")
    print("  easiest 5:", [(e["lemma"], e["difficulty_level"]) for e in lemmas_sorted[:5]])
    print("  hardest 5:", [(e["lemma"], e["difficulty_level"]) for e in lemmas_sorted[-5:]])


if __name__ == "__main__":
    main()
