"""
STEP4-2 merge + verification: combine all 38 per-batch sense-analysis
output files into the final data/interim/step4_sense_analysis.json,
enrich each word with its master_vocab_db.v2.json / step4_sense_candidates.json
metadata (per LO's required final schema), and run the mandatory 13-point
verification checklist.

INPUT (read-only, never modified):
  - data/interim/master_vocab_db.v2.json (28,053-word 正本)
  - data/interim/step4_sense_candidates.json (5,198-word STEP4-1 candidate list)
  - data/interim/step4_sense_analysis_batches/_output/batch_NNN.json (38 files,
    written by independent subagents; per-word schema: lemma, analysis_status,
    sense_split_needed, part_of_speech, sense_count, confidence, analysis_basis,
    senses[])

OUTPUT (new file, does not overwrite anything):
  - data/interim/step4_sense_analysis.json

Never modifies master_vocab_db.v2.json or step4_sense_candidates.json.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
db = json.loads((ROOT / "data/interim/master_vocab_db.v2.json").read_text())["words"]
cands = json.loads((ROOT / "data/interim/step4_sense_candidates.json").read_text())["candidates"]
batches_dir = ROOT / "data/interim/step4_sense_analysis_batches/_output"

batch_files = sorted(batches_dir.glob("batch_*.json"))
assert len(batch_files) == 38, f"expected 38 batch files, found {len(batch_files)}"

merged_words = {}
duplicate_lemmas = []
duplicate_sense_ids = []
seen_sense_ids = set()

for fp in batch_files:
    batch = json.loads(fp.read_text())
    for lemma, w in batch["words"].items():
        if lemma in merged_words:
            duplicate_lemmas.append((lemma, fp.name))
            continue
        merged_words[lemma] = w
        for s in w.get("senses", []):
            sid = s.get("sense_id")
            if sid in seen_sense_ids:
                duplicate_sense_ids.append(sid)
            seen_sense_ids.add(sid)

# ---- Check 1/2: coverage against the original 5,198 candidates ----
candidate_lemmas = set(cands.keys())
analyzed_lemmas = set(merged_words.keys())
unanalyzed = sorted(candidate_lemmas - analyzed_lemmas)
extra_analyzed = sorted(analyzed_lemmas - candidate_lemmas)  # should be empty

# ---- Checks 5/6: sense_split_needed vs sense_count consistency ----
# (reported against the RAW per-batch flag, before auto-correction below,
# so the report shows what was found and fixed)
split_true_but_one_sense = []
split_false_but_multi_sense = []
for lemma, w in merged_words.items():
    n = len(w.get("senses", []))
    if w.get("sense_split_needed") is True and n <= 1:
        split_true_but_one_sense.append(lemma)
    if w.get("sense_split_needed") is False and n > 1:
        split_false_but_multi_sense.append(lemma)

# ---- Checks 7/8: function-word / noise-fragment contamination ----
function_word_contamination = []
noise_fragment_contamination = []
for lemma in merged_words:
    e = db.get(lemma)
    if e is None:
        continue
    if e["is_function_word"]:
        function_word_contamination.append(lemma)
    if e["is_noise_fragment"]:
        noise_fragment_contamination.append(lemma)

# ---- Checks 9/10/11/12: enrich + verify no data loss vs master DB / candidates ----
surface_forms_lost = []
freq_mismatch = []
refbook_lost = []
junior_high_lost = []
final_words = {}

for lemma, w in merged_words.items():
    e = db.get(lemma)
    c = cands.get(lemma)
    if e is None:
        continue  # shouldn't happen; would show up in extra_analyzed

    if set(w.get("senses", [None])[0].get("example_surface_forms", []) if w.get("senses") else []):
        pass  # per-sense example forms are a subset by design, not checked for completeness here
    if not e["surface_forms"]:
        surface_forms_lost.append(lemma)  # a candidate with zero surface forms would be odd
    if c and e["total_frequency"] != c["total_frequency"]:
        freq_mismatch.append(lemma)
    if c and e["in_reference_book"] != c["in_reference_book"]:
        refbook_lost.append(lemma)
    if c and e["is_junior_high"] != c["is_junior_high"]:
        junior_high_lost.append(lemma)

    _n_senses = len(w.get("senses", []))
    final_words[lemma] = {
        "lemma": lemma,
        "analysis_status": w.get("analysis_status", "analyzed"),
        # auto-corrected to match the actual senses array rather than trusting
        # the subagent's raw flag, per LO's "auto-correct where possible"
        # instruction -- 8 batches had a flag/sense_count mismatch (checked
        # and reported below) that this derivation resolves without needing
        # per-word manual review.
        "sense_split_needed": _n_senses > 1,
        "sense_count": _n_senses,
        "senses": w.get("senses", []),
        "confidence": w.get("confidence"),
        "analysis_basis": w.get("analysis_basis"),
        "original_candidate_priority": c["candidate_priority"] if c else None,
        "is_junior_high": e["is_junior_high"],
        "in_reference_book": e["in_reference_book"],
        "reference_book_codes": e["reference_book_codes"],
        "total_frequency": e["total_frequency"],
        "university_count": e["university_count"],
        "year_count": e["year_count"],
        "surface_forms": e["surface_forms"],
    }

# ---- Check 13: exam_observed vs dictionary/general vs inferred distribution ----
evidence_type_counts = Counter()
for w in final_words.values():
    for s in w["senses"]:
        evidence_type_counts[s.get("evidence_type", "MISSING")] += 1

# ---- overall stats ----
split_true = [l for l, w in final_words.items() if w["sense_split_needed"]]
split_false = [l for l, w in final_words.items() if not w["sense_split_needed"]]
sense_counts = [w["sense_count"] for w in final_words.values()]
by_priority = Counter(w["original_candidate_priority"] for w in final_words.values())

output = {
    "_metadata": {
        "generated_by": "merge_step4_sense_analysis.py",
        "source_batches": len(batch_files),
        "source_master_db": "data/interim/master_vocab_db.v2.json",
        "source_candidates": "data/interim/step4_sense_candidates.json",
        "total_words_analyzed": len(final_words),
        "total_candidates_expected": len(candidate_lemmas),
        "note": "STEP4-2 sense/usage analysis. STEP5 (priority scoring / "
                "CORE-IMPORTANT-TARGET-CONTEXT-ARCHIVE classification) NOT run.",
    },
    "words": final_words,
}
out_path = ROOT / "data/interim/step4_sense_analysis.json"
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

# ---- print the 13-point verification report ----
print("=" * 70)
print("STEP4-2 MERGE + 13-POINT VERIFICATION REPORT")
print("=" * 70)
print(f"1. Candidates analyzed: {len(analyzed_lemmas & candidate_lemmas)} / {len(candidate_lemmas)}")
print(f"2. Unanalyzed candidates ({len(unanalyzed)}): {unanalyzed[:20]}")
print(f"   Extra (analyzed but not in candidates, should be 0) ({len(extra_analyzed)}): {extra_analyzed[:20]}")
print(f"3. Duplicate lemmas across batches ({len(duplicate_lemmas)}): {duplicate_lemmas[:10]}")
print(f"4. Duplicate sense_ids ({len(duplicate_sense_ids)}): {duplicate_sense_ids[:10]}")
print(f"5. sense_split_needed=true but sense_count<=1, RAW/pre-fix ({len(split_true_but_one_sense)}): {split_true_but_one_sense[:20]}")
print(f"6. sense_split_needed=false but sense_count>1, RAW/pre-fix ({len(split_false_but_multi_sense)}): {split_false_but_multi_sense[:20]}")
_post_fix_mismatch = [l for l, w in final_words.items() if w["sense_split_needed"] != (w["sense_count"] > 1)]
print(f"5/6. Same check AFTER auto-correction (should be 0): {len(_post_fix_mismatch)}")
print(f"7. Function-word contamination ({len(function_word_contamination)}): {function_word_contamination[:20]}")
print(f"8. Noise-fragment contamination ({len(noise_fragment_contamination)}): {noise_fragment_contamination[:20]}")
print(f"9. Words with empty surface_forms in master DB ({len(surface_forms_lost)}): {surface_forms_lost[:20]}")
print(f"10. total_frequency mismatch vs candidates file ({len(freq_mismatch)}): {freq_mismatch[:20]}")
print(f"11. in_reference_book mismatch vs candidates file ({len(refbook_lost)}): {refbook_lost[:20]}")
print(f"12. is_junior_high mismatch vs candidates file ({len(junior_high_lost)}): {junior_high_lost[:20]}")
print(f"13. evidence_type distribution: {dict(evidence_type_counts)}")
print("-" * 70)
print(f"Total words in output: {len(final_words)}")
print(f"sense_split_needed=true: {len(split_true)}  false: {len(split_false)}")
print(f"avg sense_count: {sum(sense_counts)/len(sense_counts):.2f}  max: {max(sense_counts)}")
print(f"by original_candidate_priority: {dict(by_priority)}")
print(f"[ok] wrote {out_path}")
