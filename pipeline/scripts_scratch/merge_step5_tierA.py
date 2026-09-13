"""
STEP5 Tier A merge + verification: combine all 38 tierA_batch_NNN.json
output files into a single step5_tier_a_evaluation.json, then run
integrity checks (coverage, duplicates, facts-verbatim, schema
completeness) against the source data. Never modifies any input file.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
facts_v3 = json.loads((ROOT / "data/interim/step5_word_facts_v3.json").read_text())["words"]
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
batches_dir = ROOT / "data/interim/step5_evaluation_batches_v2/_output"

batch_files = sorted(batches_dir.glob("tierA_batch_*.json"))
assert len(batch_files) == 38, f"expected 38 tierA batches, found {len(batch_files)}"

merged = {}
duplicate_lemmas = []
for fp in batch_files:
    batch = json.loads(fp.read_text())
    for lemma, w in batch["words"].items():
        if lemma in merged:
            duplicate_lemmas.append((lemma, fp.name))
            continue
        merged[lemma] = w

expected_lemmas = {l for l, f in facts_v3.items() if f["analysis_tier"] == "step4_2_analyzed"}
missing = expected_lemmas - set(merged.keys())
extra = set(merged.keys()) - expected_lemmas

# facts verbatim check: group_frequency facts in output must match step5_word_facts_v3.json exactly
facts_mismatches = []
for lemma, w in merged.items():
    fct = facts_v3.get(lemma)
    if fct is None:
        continue
    for gname, ginfo in w.get("target_relevance", {}).get("university_groups", {}).items():
        src = fct["group_frequency"].get(gname)
        out_facts = ginfo.get("facts", {})
        if src is None:
            facts_mismatches.append((lemma, gname, "group not in source"))
            continue
        for k in ("frequency", "group_freq_percentile", "university_coverage_ratio", "concentration_ratio"):
            if out_facts.get(k) != src.get(k):
                facts_mismatches.append((lemma, gname, k, out_facts.get(k), src.get(k)))

# schema completeness check
required_word_fields = ["final_role", "overall_learning_value", "exam_necessity", "reference_coverage",
                         "lexa_added_value", "learner_category", "confidence", "reason", "common_test",
                         "target_relevance", "senses", "facts_summary"]
allowed_roles = {"CORE", "IMPORTANT", "TARGET", "CONTEXT", "ARCHIVE", "EXCLUDE_FROM_LEARNING"}
schema_issues = []
for lemma, w in merged.items():
    for field in required_word_fields:
        if field not in w:
            schema_issues.append((lemma, f"missing field {field}"))
    if w.get("final_role") not in allowed_roles:
        schema_issues.append((lemma, f"invalid final_role {w.get('final_role')}"))
    if w.get("target_relevance", {}).get("faculties") != "unknown - no faculty data exists in exam_tokens/":
        schema_issues.append((lemma, "faculties field violation"))
    n_step4_senses = len(step4.get(lemma, {}).get("senses", []))
    n_out_senses = len(w.get("senses", []))
    if n_step4_senses != n_out_senses:
        schema_issues.append((lemma, f"sense count mismatch: step4={n_step4_senses} out={n_out_senses}"))

# sense_id preservation
sense_id_mismatches = []
for lemma, w in merged.items():
    step4_ids = {s["sense_id"] for s in step4.get(lemma, {}).get("senses", [])}
    out_ids = {s["sense_id"] for s in w.get("senses", [])}
    if step4_ids != out_ids:
        sense_id_mismatches.append((lemma, step4_ids, out_ids))

final_role_dist = Counter(w["final_role"] for w in merged.values())
lexa_added_value_dist = Counter(w["lexa_added_value"] for w in merged.values())
reference_coverage_dist = Counter(w["reference_coverage"] for w in merged.values())

out_path = ROOT / "data/interim/step5_tier_a_evaluation.json"
out_path.write_text(json.dumps({
    "_metadata": {
        "generated_by": "merge_step5_tierA.py",
        "source_batches": len(batch_files),
        "total_words": len(merged),
        "note": "Tier A only (5,198 STEP4-2-analyzed words). Tier B (21,539 facts-only words) "
                "is merged separately once its pilot+main batches complete.",
    },
    "words": merged,
}, ensure_ascii=False, indent=2))

print("=" * 70)
print("STEP5 TIER A MERGE + VERIFICATION REPORT")
print("=" * 70)
print(f"1. Words merged: {len(merged)} / expected {len(expected_lemmas)}")
print(f"2. Missing lemmas ({len(missing)}): {list(missing)[:20]}")
print(f"   Extra lemmas ({len(extra)}): {list(extra)[:20]}")
print(f"3. Duplicate lemmas across batches ({len(duplicate_lemmas)}): {duplicate_lemmas[:10]}")
print(f"4. Facts-verbatim mismatches ({len(facts_mismatches)}): {facts_mismatches[:10]}")
print(f"5. Schema issues ({len(schema_issues)}): {schema_issues[:20]}")
print(f"6. Sense-ID mismatches ({len(sense_id_mismatches)}): {[m[0] for m in sense_id_mismatches][:20]}")
print(f"7. final_role distribution: {dict(final_role_dist)}")
print(f"8. lexa_added_value distribution: {dict(lexa_added_value_dist)}")
print(f"9. reference_coverage distribution: {dict(reference_coverage_dist)}")
print(f"[ok] wrote {out_path}")
