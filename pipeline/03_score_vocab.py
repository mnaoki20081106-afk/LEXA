"""
Phase A: difficulty scoring per vocab_scoring_algorithm.txt §3.

Implements:
  Step 1 - Base_Score: mean percentile position across the books a lemma
           appears in, with a duplicate-appearance discount (0.9 per the
           spec's example factor) applied multiplicatively per extra book.
  Step 2 - Boost_Score: past-exam TF-IDF specificity boost (see boost_score
           below). Each university's pooled corpus (across all its
           processed years) is treated as one TF-IDF "document"; Boost_Score
           for a lemma is the max TF-IDF over all universities it appears
           in, per vocab_scoring_algorithm.txt §3 Step2's formula.
  Step 3 - Normalize Base_Score + Boost_Score to 0.0-10.0.

IMPLEMENTATION DECISIONS (not specified in any doc; documented per the
project's "no silent decisions" rule rather than left as a TODO):
  - IDF: idf(w) = ln(N / df(w)), where N = number of universities and
    df(w) = number of universities containing w at least once. Deliberately
    UNsmoothed (no "+1" anywhere) -- this is a closed corpus (not an
    inference-time unseen-term situation), so a word appearing in literally
    every university should get idf = ln(N/N) = 0, i.e. zero specificity
    boost. An earlier version used sklearn-style "+1" smoothing, which kept
    idf floored at 1.0 even for universally-common words -- that let sheer
    raw frequency alone (e.g. "end", "conversation", commonly-occurring
    words with no school-specificity at all) leak into Boost_Score. Verified
    by hand against the exam corpus before shipping this version.
  - Normalization scale for Boost_Score: raw TF-IDF-max values are strongly
    right-skewed (most lemmas cluster near 0, a small number of genuinely
    school-specific technical terms have much larger values). A plain
    min-max normalization would compress nearly everything toward 0 and let
    one extreme value set the whole scale; a hard percentile clip (tried
    first) instead created false ties by clipping many distinct lemmas to
    the same 1.0 ceiling regardless of how different their real specificity
    was. Both were rejected. Instead: log-transform the nonzero values, then
    min-max normalize the logs to (0, 1] -- this preserves the full rank
    ordering among every nonzero lemma (no ties introduced) while still
    compressing the long tail sensibly. Lemmas with raw boost 0 (absent from
    the exam corpus, or -- after the IDF fix above -- universally common)
    stay at exactly 0.0.
  - BOOST_WEIGHT: multiplies the normalized 0..1 boost before adding to
    Base_Score. Default 1.0 (equal footing with Base_Score, which is also
    a 0..1-ish percentile value). Adjust here if boost should dominate or
    be subordinate to reference-book position; not specified in the spec
    ("実際の重みは開発・検証しながら決める" -- vocab_scoring_algorithm.txt
    leaves the coefficient for iteration).

Usage:
    python3 03_score_vocab.py --merged data/processed/merged_lemmas.json \
        --exam-freq-dir data/interim --out data/processed/vocab_scored.json
"""
import argparse
import json
import math
from pathlib import Path

DUPLICATE_DISCOUNT = 0.9  # vocab_scoring_algorithm.txt §3 Step1 example value
BOOST_WEIGHT = 1.0  # see docstring "IMPLEMENTATION DECISIONS"


def base_score(sources: dict) -> float:
    percentiles = [info["index"] / info["total"] for info in sources.values()]
    mean_percentile = sum(percentiles) / len(percentiles)
    # Apply the duplicate discount once per additional book beyond the first,
    # per "重複して掲載されている単語は...重複割引係数（例: 0.9）を掛けて
    # 難易度を下げる" -- lower score = easier/more foundational.
    extra_books = len(sources) - 1
    return mean_percentile * (DUPLICATE_DISCOUNT ** extra_books)


def load_university_corpora(exam_freq_dir: Path) -> dict:
    """Merge every tier's exam_freq_*.json into one {university: {term_freq, doc_freq, doc_count}} dict."""
    universities = {}
    for fp in sorted(exam_freq_dir.glob("exam_freq_*.json")):
        tier = json.loads(fp.read_text())
        for uni, info in tier.get("universities", {}).items():
            if uni in universities:
                raise ValueError(f"university {uni!r} appears in more than one tier file (found again in {fp})")
            universities[uni] = info
    return universities


def compute_boost_scores(lemmas: list, universities: dict) -> dict:
    """Returns {lemma: boost_score_raw} using max-TF-IDF-across-universities."""
    total_terms = {uni: sum(info["term_freq"].values()) or 1 for uni, info in universities.items()}
    n_universities = len(universities)

    raw_tfidf_max = {}
    for entry in lemmas:
        lemma = entry["lemma"]
        df = sum(1 for info in universities.values() if info["term_freq"].get(lemma, 0) > 0)
        if df == 0 or df == n_universities:
            # Absent everywhere, or present everywhere (idf = ln(N/N) = 0):
            # zero specificity boost either way. See docstring "IDF".
            raw_tfidf_max[lemma] = 0.0
            continue
        idf = math.log(n_universities / df)
        best = 0.0
        for uni, info in universities.items():
            tf_count = info["term_freq"].get(lemma, 0)
            if tf_count == 0:
                continue
            tf = tf_count / total_terms[uni]
            best = max(best, tf * idf)
        raw_tfidf_max[lemma] = best

    nonzero_items = [(lemma, v) for lemma, v in raw_tfidf_max.items() if v > 0]
    if not nonzero_items:
        return {lemma: 0.0 for lemma in raw_tfidf_max}

    logs = [math.log(v) for _, v in nonzero_items]
    lo_log, hi_log = min(logs), max(logs)
    span = (hi_log - lo_log) or 1.0

    boost = {lemma: 0.0 for lemma in raw_tfidf_max}
    for (lemma, v), log_v in zip(nonzero_items, logs):
        boost[lemma] = BOOST_WEIGHT * (log_v - lo_log) / span
    return boost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--exam-freq-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--out", default=Path("data/processed/vocab_scored.json"), type=Path)
    args = ap.parse_args()

    data = json.loads(args.merged.read_text())
    lemmas = data["lemmas"]

    universities = load_university_corpora(args.exam_freq_dir)
    boost_scores = compute_boost_scores(lemmas, universities)
    print(f"[ok] loaded exam corpus: {len(universities)} universities")

    raw_scores = []
    for entry in lemmas:
        b = base_score(entry["sources"])
        entry["base_score_raw"] = b
        entry["boost_score_raw"] = round(boost_scores[entry["lemma"]], 6)
        entry["raw_score"] = b + entry["boost_score_raw"]
        raw_scores.append(entry["raw_score"])

    lo, hi = min(raw_scores), max(raw_scores)
    span = (hi - lo) or 1.0
    for entry in lemmas:
        entry["difficulty_level"] = round(10.0 * (entry["raw_score"] - lo) / span, 3)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"lemmas": lemmas}, ensure_ascii=False, indent=2))

    lemmas_sorted = sorted(lemmas, key=lambda e: e["difficulty_level"])
    boosted = sorted(lemmas, key=lambda e: -e["boost_score_raw"])
    print(f"[ok] scored {len(lemmas)} lemmas -> {args.out}")
    print("  easiest 5:", [(e["lemma"], e["difficulty_level"]) for e in lemmas_sorted[:5]])
    print("  hardest 5:", [(e["lemma"], e["difficulty_level"]) for e in lemmas_sorted[-5:]])
    print("  highest exam-boost 5:", [(e["lemma"], e["boost_score_raw"]) for e in boosted[:5]])


if __name__ == "__main__":
    main()
