"""
STEP5 batch prep: combine step4_sense_analysis.json (senses) with
step5_word_facts_v2.json (facts) into per-word input records, then
split into batches (same round-robin-by-priority-emphasis pattern as
STEP4-2's prepare_step4_batches.py) for the judgment-layer subagents.

Never modifies step4_sense_analysis.json, master_vocab_db.v2.json, or
either step5_word_facts*.json file.
"""
import json
import math
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
facts = json.loads((ROOT / "data/interim/step5_word_facts_v2.json").read_text())["words"]

assert set(step4.keys()) == set(facts.keys()), "step4 and facts word sets must match exactly"

# same priority-emphasis word list used in STEP4-2, still relevant here
PRIORITY_EMPHASIS = {
    "fine", "address", "subject", "bear", "mean", "account", "figure", "issue", "concern",
    "charge", "matter", "object", "present", "claim", "conduct", "feature", "record",
    "case", "point", "interest", "condition", "state", "support", "mark", "express",
    "produce", "remain", "represent", "apply", "approach", "range", "character", "term",
    "part", "right", "light", "common", "major", "general", "particular", "available",
    "significant", "current", "individual",
}

items = []
for lemma, s4 in step4.items():
    fct = facts[lemma]
    items.append({
        "lemma": lemma,
        "original_candidate_priority": s4["original_candidate_priority"],
        "senses": s4["senses"],
        "sense_split_needed": s4["sense_split_needed"],
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
    })

items.sort(key=lambda x: (not x["priority_emphasis"], -x["total_frequency"]))

BATCH_SIZE = 140
batches_dir = ROOT / "data/interim/step5_evaluation_batches"
batches_dir.mkdir(parents=True, exist_ok=True)
input_dir = batches_dir / "_input"
input_dir.mkdir(exist_ok=True)

n_batches = math.ceil(len(items) / BATCH_SIZE)
buckets = [[] for _ in range(n_batches)]
for i, item in enumerate(items):
    buckets[i % n_batches].append(item)

manifest = []
for i, bucket in enumerate(buckets):
    fp = input_dir / f"batch_{i:03d}.json"
    fp.write_text(json.dumps({"batch_id": f"batch_{i:03d}", "words": bucket}, ensure_ascii=False, indent=2))
    manifest.append({"batch_id": f"batch_{i:03d}", "word_count": len(bucket),
                      "priority_emphasis_count": sum(1 for w in bucket if w["priority_emphasis"])})

(batches_dir / "_manifest.json").write_text(json.dumps({"n_batches": n_batches, "batch_size": BATCH_SIZE,
                                                          "total_words": len(items), "batches": manifest},
                                                         ensure_ascii=False, indent=2))
print(f"prepared {n_batches} batches, {len(items)} total words, ~{BATCH_SIZE}/batch")
