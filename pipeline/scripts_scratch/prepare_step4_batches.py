import json
import math
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
db = json.loads((ROOT / "data/interim/master_vocab_db.v2.json").read_text())["words"]
cands = json.loads((ROOT / "data/interim/step4_sense_candidates.json").read_text())["candidates"]

PRIORITY_EMPHASIS = {
    "fine", "address", "subject", "bear", "mean", "account", "figure", "issue", "concern",
    "charge", "matter", "object", "present", "claim", "conduct", "feature", "record",
    "case", "point", "interest", "condition", "state", "support", "mark", "express",
    "produce", "remain", "represent", "apply", "approach", "range", "character", "term",
    "part", "right", "light", "common", "major", "general", "particular", "available",
    "significant", "current", "individual",
}

items = []
for lemma, c in cands.items():
    e = db[lemma]
    items.append({
        "lemma": lemma,
        "candidate_priority": c["candidate_priority"],
        "candidate_reasons": c["candidate_reasons"],
        "is_junior_high": e["is_junior_high"],
        "in_reference_book": e["in_reference_book"],
        "reference_book_codes": e["reference_book_codes"],
        "total_frequency": e["total_frequency"],
        "university_count": e["university_count"],
        "year_count": e["year_count"],
        "surface_forms": e["surface_forms"],
        "priority_emphasis": lemma in PRIORITY_EMPHASIS,
    })

# sort so priority_emphasis words are spread across batches (each batch gets a fair share),
# and within that by descending frequency (do the most exam-important words first within each batch)
items.sort(key=lambda x: (not x["priority_emphasis"], -x["total_frequency"]))

BATCH_SIZE = 140
batches_dir = ROOT / "data/interim/step4_sense_analysis_batches"
batches_dir.mkdir(parents=True, exist_ok=True)
input_dir = batches_dir / "_input"
input_dir.mkdir(exist_ok=True)

n_batches = math.ceil(len(items) / BATCH_SIZE)
# round-robin distribution so priority_emphasis words spread across batches, not clumped in batch 0
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
print("priority_emphasis words found in pool:", sum(1 for it in items if it["priority_emphasis"]), "/", len(PRIORITY_EMPHASIS))
