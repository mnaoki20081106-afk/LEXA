"""
STEP5 batch prep v2: builds batch input files for the FULL 26,737-word
STEP5 population, split into:
  - Tier A (5,198 words, analysis_tier="step4_2_analyzed"): senses[]
    carried over verbatim from STEP4-2. Same 140-word batch size as
    the original 38-batch STEP4-2 scheme (kept because these batches
    require more careful per-sense reasoning).
  - Tier B (21,539 words, analysis_tier="facts_only"): senses=[],
    senses_status="not_analyzed" explicitly (never inferred/guessed).
    Split into a small PILOT wave (2 batches, ~75 words each) first,
    then -- only after the pilot is reviewed and approved -- a MAIN
    wave sized at up to 300 words/batch.

Writes to a NEW directory (step5_evaluation_batches_v2/), never
touching step5_evaluation_batches/ (the old 5,198-word-only scheme,
already partially run) or any of master_vocab_db.v2.json /
step4_sense_analysis.json / step5_word_facts*.json.
"""
import json
import math
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
facts = json.loads((ROOT / "data/interim/step5_word_facts_v3.json").read_text())["words"]

PRIORITY_EMPHASIS = {
    "fine", "address", "subject", "bear", "mean", "account", "figure", "issue", "concern",
    "charge", "matter", "object", "present", "claim", "conduct", "feature", "record",
    "case", "point", "interest", "condition", "state", "support", "mark", "express",
    "produce", "remain", "represent", "apply", "approach", "range", "character", "term",
    "part", "right", "light", "common", "major", "general", "particular", "available",
    "significant", "current", "individual",
}

tier_a_items, tier_b_items = [], []
for lemma, fct in facts.items():
    base = {
        "lemma": lemma,
        "analysis_tier": fct["analysis_tier"],
        "is_junior_high": fct["is_junior_high"],
        "is_function_word": fct["is_function_word"],
        "is_noise_fragment": fct["is_noise_fragment"],
        "is_phrase": fct["is_phrase"],
        "in_reference_book": fct["in_reference_book"],
        "reference_book_codes": fct["reference_book_codes"],
        "book_count": fct["book_count"],
        "total_frequency": fct["total_frequency"],
        "university_count": fct["university_count"],
        "year_count": fct["year_count"],
        "common_test": fct["common_test"],
        "group_frequency": fct["group_frequency"],
        "priority_emphasis": lemma in PRIORITY_EMPHASIS,
    }
    if fct["analysis_tier"] == "step4_2_analyzed":
        s4 = step4[lemma]
        base.update({
            "senses_status": "analyzed",
            "senses": s4["senses"],
            "sense_split_needed": s4["sense_split_needed"],
            "original_candidate_priority": s4["original_candidate_priority"],
        })
        tier_a_items.append(base)
    else:
        base.update({
            "senses_status": "not_analyzed",
            "senses": [],
            "sense_split_needed": None,
            "original_candidate_priority": None,
        })
        tier_b_items.append(base)

assert len(tier_a_items) == 5198 and len(tier_b_items) == 21539

batches_dir = ROOT / "data/interim/step5_evaluation_batches_v2"
batches_dir.mkdir(parents=True, exist_ok=True)
input_dir = batches_dir / "_input"
input_dir.mkdir(exist_ok=True)


def write_batches(items, batch_size, prefix, sort_key):
    items = sorted(items, key=sort_key)
    n = math.ceil(len(items) / batch_size)
    buckets = [[] for _ in range(n)]
    for i, item in enumerate(items):
        buckets[i % n].append(item)
    manifest = []
    for i, bucket in enumerate(buckets):
        bid = f"{prefix}_{i:03d}"
        fp = input_dir / f"{bid}.json"
        fp.write_text(json.dumps({"batch_id": bid, "words": bucket}, ensure_ascii=False, indent=2))
        manifest.append({"batch_id": bid, "word_count": len(bucket),
                          "priority_emphasis_count": sum(1 for w in bucket if w["priority_emphasis"])})
    return n, manifest


# Tier A: same 140/batch scheme as the original STEP4-2-scale batching
n_a, manifest_a = write_batches(tier_a_items, 140, "tierA_batch",
                                 sort_key=lambda x: (not x["priority_emphasis"], -x["total_frequency"]))

# Tier B PILOT: 2 batches of ~75 words, drawn from a spread of frequency bands
# (not just the top) so the pilot review sees a representative mix, not only
# the highest-frequency facts_only words.
tier_b_sorted = sorted(tier_b_items, key=lambda x: -x["total_frequency"])
pilot_size = 150  # 2 batches x 75
step = max(1, len(tier_b_sorted) // pilot_size)
pilot_pool = [tier_b_sorted[i] for i in range(0, len(tier_b_sorted), step)][:pilot_size]
pilot_lemmas = {w["lemma"] for w in pilot_pool}
n_pilot, manifest_pilot = write_batches(pilot_pool, 75, "tierB_pilot_batch",
                                         sort_key=lambda x: -x["total_frequency"])

# Tier B MAIN: everything not in the pilot, pre-split at 300/batch so it's
# ready to dispatch once the pilot is reviewed and approved (generation is
# free; dispatch is what costs tokens and is gated on pilot review).
tier_b_main = [w for w in tier_b_sorted if w["lemma"] not in pilot_lemmas]
n_main, manifest_main = write_batches(tier_b_main, 300, "tierB_main_batch",
                                       sort_key=lambda x: -x["total_frequency"])

(batches_dir / "_manifest.json").write_text(json.dumps({
    "tier_a": {"n_batches": n_a, "batch_size": 140, "total_words": len(tier_a_items), "batches": manifest_a},
    "tier_b_pilot": {"n_batches": n_pilot, "batch_size": 75, "total_words": len(pilot_pool), "batches": manifest_pilot,
                      "note": "Spread across the tier_b frequency distribution (every Nth word by frequency), "
                              "not just the highest-frequency words, per LO's pilot review requirement."},
    "tier_b_main": {"n_batches": n_main, "batch_size": 300, "total_words": len(tier_b_main), "batches": manifest_main,
                     "note": "Pre-generated but NOT to be dispatched until the pilot batches are reviewed and approved."},
}, ensure_ascii=False, indent=2))

print(f"Tier A: {n_a} batches, {len(tier_a_items)} words")
print(f"Tier B pilot: {n_pilot} batches, {len(pilot_pool)} words")
print(f"Tier B main: {n_main} batches, {len(tier_b_main)} words (held, not dispatched yet)")
print(f"Total words accounted for: {len(tier_a_items) + len(pilot_pool) + len(tier_b_main)} (expect 26737)")
