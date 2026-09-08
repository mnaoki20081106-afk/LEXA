"""
Phase A2 candidate triage, step 4: frequency-based screening of the
exam-only candidates (09_filter_junior_high.py's output). Per LO, this is
the first step that actually screens the ~22,000 candidates, using three
numbers per lemma:
  1) total occurrences across the whole past-exam corpus (term frequency)
  2) number of distinct universities it appears in
  3) number of distinct exam YEARS it appears in

("ubiquitous: 18 times, 7 universities, 9 years" is the kind of signal
that argues for adoption; "专門用語X: 1 time, 1 university, 1 year" argues
against it -- but see 10_cross_reference_candidates.py: this script does
not itself drop anything, it only computes and records the three numbers.
The actual adopt/reject decision and threshold are a separate, later step.)

WHY RECOMPUTED FROM THE PER-FILE TOKEN CACHE, NOT exam_freq_open_*.json:
the year-level breakdown (metric 3) was never aggregated anywhere --
exam_freq_open_*.json only has per-UNIVERSITY totals across all years
combined. The per-file bag-of-words caches under data/interim/exam_tokens/
(one file per exam paper, from 07_reprocess_exam_corpus_open_vocab.py)
each carry their own university+year+token_freq, so year-level counting
requires scanning those directly. Re-applies the same lemmatization
function as 08_lemmatize_exam_corpus.py to each file's raw surface-form
tokens on the fly, so the resulting per-lemma counts are consistent with
the already-lemmatized candidate list (09's exam_only_candidates.json
supplies the fixed set of lemmas to report on; this script does not
introduce new candidate lemmas, it only adds the year dimension to
existing ones).

Usage:
    python3 11_frequency_analysis.py \
        --candidates data/interim/exam_only_candidates.json \
        --tokens-dir data/interim/exam_tokens \
        --out data/interim/exam_only_frequency_stats.json
"""
import argparse
import json
from pathlib import Path

from lemminflect import getAllLemmas

POS_PRIORITY = ("NOUN", "VERB", "ADJ", "ADV")
_cache: dict[str, str] = {}


def lemmatize(word: str) -> str:
    if word in _cache:
        return _cache[word]
    candidates = getAllLemmas(word)
    if not candidates:
        result = word
    elif any(word in lemmas for lemmas in candidates.values()):
        result = word
    else:
        result = word
        for pos in POS_PRIORITY:
            if pos in candidates:
                result = candidates[pos][0]
                break
    _cache[word] = result
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=Path("data/interim/exam_only_candidates.json"), type=Path)
    ap.add_argument("--tokens-dir", default=Path("data/interim/exam_tokens"), type=Path)
    ap.add_argument("--out", default=Path("data/interim/exam_only_frequency_stats.json"), type=Path)
    args = ap.parse_args()

    candidate_lemmas = set(json.loads(args.candidates.read_text()).keys())

    stats: dict[str, dict] = {
        lemma: {"total_term_freq": 0, "universities": set(), "years": set()}
        for lemma in candidate_lemmas
    }

    files = list(args.tokens_dir.glob("*/*.json"))
    for i, fp in enumerate(files, start=1):
        doc = json.loads(fp.read_text())
        uni, year = doc["university"], doc["year"]
        for word, n in doc["token_freq"].items():
            if " " in word:
                continue  # multi-word phrase lemmas aren't part of this candidate set
            lemma = lemmatize(word)
            if lemma not in stats:
                continue
            s = stats[lemma]
            s["total_term_freq"] += n
            s["universities"].add(uni)
            s["years"].add(year)
        if i % 500 == 0:
            print(f"[..] scanned {i}/{len(files)} files")

    out = {
        lemma: {
            "total_term_freq": s["total_term_freq"],
            "university_count": len(s["universities"]),
            "year_count": len(s["years"]),
            "universities": sorted(s["universities"]),
            "years": sorted(s["years"]),
        }
        for lemma, s in stats.items()
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    ranked = sorted(out.items(), key=lambda kv: (-kv[1]["university_count"], -kv[1]["year_count"], -kv[1]["total_term_freq"]))
    print(f"[ok] {len(out)} candidates scored -> {args.out}")
    print("  top 10 by breadth (universities, years, then raw freq):")
    for lemma, v in ranked[:10]:
        print(f"    {lemma}: {v['total_term_freq']} times, {v['university_count']} universities, {v['year_count']} years")
    low = sum(1 for v in out.values() if v["university_count"] <= 1 and v["year_count"] <= 1)
    print(f"  candidates seen in only 1 university AND 1 year: {low}")


if __name__ == "__main__":
    main()
