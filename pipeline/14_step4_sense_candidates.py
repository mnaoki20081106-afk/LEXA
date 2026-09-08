"""
Phase A2 STEP4-1: mechanically extract candidates for later sense/usage
analysis (STEP4-2+, NOT run by this script) from master_vocab_db.v2.json.

SCOPE: this does NOT judge word senses. No LLM call, no per-word semantic
decision. It only combines signals already present in the master DB
(frequency, breadth, reference-book membership, is_junior_high, and a
morphology-based noun/verb dual-use check) into a prioritized shortlist,
so STEP4-2's (future, out of scope here) actual sense analysis has a
manageable, justified starting list instead of all 28,053 words.

INPUT: master_vocab_db.v2.json ONLY. The older exam_only_candidates.json /
exam_only_frequency_stats.json / vocab_candidate_master.json snapshots are
deliberately not read (per LO: they are stale, superseded by v2).

CANDIDATE POOL: excludes is_function_word=true and is_phrase=true words
from candidacy (per LO: function words are out of scope for sense
analysis by default), is_noise_fragment=true (contraction remnants /
single-character OCR artifacts -- not real words to analyze the sense of;
an early version of this script forgot this exclusion and "don" briefly
leaked into the HIGH list, caught and fixed before this was reported),
and words with total_frequency=0 (reference-book words never observed in
the exam corpus -- nothing to analyze usage of yet). None of these are
removed from the master DB; they are simply not written into this
candidate file. is_junior_high is used only as a SIGNAL, never as a
reason to exclude (this was flagged explicitly).

SIGNALS (mechanical, all computed from fields already in the master DB):
  A. junior_high_but_high_frequency: is_junior_high AND (total_frequency
     in the top decile of the candidate pool, OR broad university
     breadth AND broad year breadth) -- a "basic" word whose sheer
     entrance-exam presence suggests an advanced sense is doing real work.
  B. multi_pos_surface_pattern: the lemma's actual observed surface_forms
     include BOTH a validated noun-inflection form (plural/3rd-person -s)
     AND a validated verb-inflection form (past -ed or gerund -ing) --
     "validated" means lemminflect's generated candidate form also passes
     the system hunspell dictionary AND was actually seen in this word's
     surface_forms (not just grammatically hypothesizable -- e.g.
     "teacher" generates a hypothetical "teachered" but that fails the
     hunspell check, so teacher is correctly NOT flagged; "fine" has
     hunspell-valid "fines"/"fined"/"fining" that were actually observed,
     so it IS flagged). This is the strongest, most literal implementation
     of "the word's own inflected forms suggest it's used as both a noun
     and a verb" available without POS-tagging actual corpus sentences.
  C. high_frequency_high_diversity: total_frequency in the top 5% of the
     pool AND 4+ distinct surface forms observed -- very heavy, richly
     inflected real usage, independent of the junior-high flag.
  D. reference_book_plus_advanced_use: in_reference_book AND (signal B,
     OR top-5%-frequency with 3+ surface forms) -- "the word book covers
     the basic sense, but entrance-exam usage looks richer than that".
  E. broad_persistent_usage: university_count AND year_count both in the
     top decile of the pool -- sustained presence across many schools and
     many exam years, independent of raw frequency (a word that appears
     moderately often but EVERYWHERE, every year, is a different signal
     than one that's merely frequent overall).

PRIORITY: HIGH if 2+ distinct signals fire, or signal B fires together
with top-decile frequency; MEDIUM if exactly one of the "strong" signals
(A, B, D) fires alone; LOW if only C and/or E fire alone (breadth/volume
without the more specific junior-high-mismatch or dual-POS evidence).

Usage:
    python3 14_step4_sense_candidates.py \
        --master-db data/interim/master_vocab_db.v2.json \
        --out data/interim/step4_sense_candidates.json
"""
import argparse
import datetime
import json
import subprocess
from pathlib import Path

from lemminflect import getInflection


def hunspell_valid(words: set) -> set:
    if not words:
        return set()
    proc = subprocess.run(["hunspell", "-d", "en_US", "-G"], input="\n".join(sorted(words)),
                           capture_output=True, text=True)
    return set(line.strip() for line in proc.stdout.splitlines() if line.strip())


def has_dual_pos_pattern(lemma: str, surface_forms: dict) -> bool:
    observed = set(surface_forms.keys())
    noun_candidates = set(getInflection(lemma, tag="NNS")) | set(getInflection(lemma, tag="VBZ"))
    verb_candidates = set(getInflection(lemma, tag="VBD")) | set(getInflection(lemma, tag="VBG"))
    to_check = (noun_candidates | verb_candidates) & observed
    valid = hunspell_valid(to_check)
    has_noun_evidence = bool(noun_candidates & observed & valid) or lemma in observed
    has_verb_evidence = bool(verb_candidates & observed & valid)
    return has_noun_evidence and has_verb_evidence


def percentile(sorted_list, p):
    if not sorted_list:
        return 0
    idx = min(int(len(sorted_list) * p), len(sorted_list) - 1)
    return sorted_list[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master-db", default=Path("data/interim/master_vocab_db.v2.json"), type=Path)
    ap.add_argument("--out", default=Path("data/interim/step4_sense_candidates.json"), type=Path)
    args = ap.parse_args()

    db = json.loads(args.master_db.read_text())
    words = db["words"]

    pool = {w: e for w, e in words.items()
            if not e["is_function_word"] and not e["is_phrase"] and not e["is_noise_fragment"]
            and e["total_frequency"] > 0}

    freqs = sorted(e["total_frequency"] for e in pool.values())
    unis = sorted(e["university_count"] for e in pool.values())
    yrs = sorted(e["year_count"] for e in pool.values())
    P90_FREQ, P95_FREQ = percentile(freqs, 0.90), percentile(freqs, 0.95)
    P90_UNI, P75_YR, P90_YR = percentile(unis, 0.90), percentile(yrs, 0.75), percentile(yrs, 0.90)

    candidates = {}
    for lemma, e in pool.items():
        reasons = []
        sf_count = len(e["surface_forms"])

        if e["is_junior_high"] and (e["total_frequency"] >= P90_FREQ
                                     or (e["university_count"] >= P90_UNI and e["year_count"] >= P75_YR)):
            reasons.append("junior_high_but_high_frequency")

        dual_pos = has_dual_pos_pattern(lemma, e["surface_forms"])
        if dual_pos:
            reasons.append("multi_pos_surface_pattern")

        if e["total_frequency"] >= P95_FREQ and sf_count >= 4:
            reasons.append("high_frequency_high_diversity")

        if e["in_reference_book"] and (dual_pos or (e["total_frequency"] >= P95_FREQ and sf_count >= 3)):
            reasons.append("reference_book_plus_advanced_use")

        if e["university_count"] >= P90_UNI and e["year_count"] >= P90_YR:
            reasons.append("broad_persistent_usage")

        if not reasons:
            continue

        strong = {"junior_high_but_high_frequency", "multi_pos_surface_pattern", "reference_book_plus_advanced_use"}
        n_strong = len(strong & set(reasons))
        if len(reasons) >= 2 or ("multi_pos_surface_pattern" in reasons and e["total_frequency"] >= P90_FREQ):
            priority = "HIGH"
        elif n_strong >= 1:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        candidates[lemma] = {
            "lemma": lemma,
            "candidate_priority": priority,
            "is_junior_high": e["is_junior_high"],
            "is_function_word": e["is_function_word"],
            "in_reference_book": e["in_reference_book"],
            "reference_book_codes": e["reference_book_codes"],
            "total_frequency": e["total_frequency"],
            "university_count": e["university_count"],
            "year_count": e["year_count"],
            "surface_forms": e["surface_forms"],
            "candidate_reasons": reasons,
        }

    output = {
        "_metadata": {
            "generated_by": "14_step4_sense_candidates.py",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_master_db": str(args.master_db),
            "source_master_db_generated_at": db["_metadata"]["generated_at"],
            "pool_size_considered": len(pool),
            "total_words_in_master_db": len(words),
            "thresholds": {"P90_FREQ": P90_FREQ, "P95_FREQ": P95_FREQ,
                            "P90_UNI": P90_UNI, "P75_YR": P75_YR, "P90_YR": P90_YR},
            "note": "STEP4-1 candidate extraction only. No sense/meaning has been "
                    "determined for any word. STEP4-2+ not run.",
        },
        "candidates": candidates,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    by_priority = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for lemma, c in candidates.items():
        by_priority[c["candidate_priority"]].append(lemma)
    print(f"[ok] pool considered: {len(pool)} / {len(words)} total words")
    print(f"[ok] candidates: HIGH={len(by_priority['HIGH'])} MEDIUM={len(by_priority['MEDIUM'])} "
          f"LOW={len(by_priority['LOW'])} not_candidate={len(pool) - len(candidates)}")
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
