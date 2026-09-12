"""
STEP5 fact layer v3: extends the fact layer from 5,198 words (v1/v2,
STEP4-2 candidates only) to the FULL 26,737-word STEP5 evaluation
population, per LO's explicit instruction that STEP5 must not be
limited to the 5,198 STEP4-2-analyzed words.

POPULATION: identical filter to STEP4-1's pool (14_step4_sense_candidates.py):
  not is_function_word and not is_phrase and not is_noise_fragment
  and total_frequency > 0
Verified: this recomputes to exactly 26,737 words, matching
step4_sense_candidates.json's _metadata.pool_size_considered.

Of these 26,737:
  - 5,198 have STEP4-2 sense analysis -> analysis_tier="step4_2_analyzed"
  - 21,539 do not                      -> analysis_tier="facts_only"

All group_freq_percentile values are recomputed against the FULL
26,737-word distribution (not the narrower 5,198-word distribution
v1/v2 used) -- percentiles must be computed against the same
population being evaluated, per LO's data-integrity requirement.

v1 (step5_word_facts.json) and v2 (step5_word_facts_v2.json) are left
completely untouched. This is a new, additional file.

OUTPUT: data/interim/step5_word_facts_v3.json
"""
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
db = json.loads((ROOT / "data/interim/master_vocab_db.v2.json").read_text())["words"]
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
step4_2_lemmas = set(step4.keys())

GROUP_NAMES = {
    "kyuutei": "旧帝大", "tocky": "other_national (unconfirmed common name)",
    "kyoutsuu": "共通テスト・センター試験", "kankandoritsu": "関関同立",
    "nittokomasen": "日東駒専", "march": "MARCH", "soukeijouri": "早慶上理",
}
GROUP_SIZES = {"旧帝大": 7, "other_national (unconfirmed common name)": 5,
               "共通テスト・センター試験": 1, "関関同立": 4, "日東駒専": 4, "MARCH": 5, "早慶上理": 4}

# ---- STEP5 population: same filter as STEP4-1's pool ----
population = {l for l, e in db.items()
              if not e["is_function_word"] and not e["is_phrase"]
              and not e["is_noise_fragment"] and e["total_frequency"] > 0}
assert len(population) == 26737, f"expected 26737, got {len(population)}"

spec = importlib.util.spec_from_file_location("lemmatize_mod", ROOT / "08_lemmatize_exam_corpus.py")
lemmatize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lemmatize_mod)
lemmatize = lemmatize_mod.lemmatize

files = sorted((ROOT / "data/interim/exam_tokens").glob("*/*.json"))
print(f"[info] scanning {len(files)} exam_tokens files for the full 26,737-word population...")

group_uni_freq = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
year_freq = defaultdict(lambda: defaultdict(int))
uni_freq = defaultdict(lambda: defaultdict(int))

for fp in files:
    tier = fp.parent.name
    gname = GROUP_NAMES[tier]
    doc = json.loads(fp.read_text())
    uni, year = doc["university"], doc["year"]
    for surface, n in doc["token_freq"].items():
        lemma = surface if " " in surface else lemmatize(surface)
        if lemma not in population:
            continue
        group_uni_freq[lemma][gname][uni] += n
        year_freq[lemma][year] += n
        uni_freq[lemma][uni] += n

group_freq_lists = {g: [] for g in GROUP_SIZES}
for lemma, groups in group_uni_freq.items():
    for gname, unis in groups.items():
        group_freq_lists[gname].append(sum(unis.values()))
for g in group_freq_lists:
    group_freq_lists[g].sort()

import bisect


def percentile_rank(sorted_list, value):
    if not sorted_list:
        return 0.0
    idx = bisect.bisect_left(sorted_list, value)
    return round(100.0 * idx / len(sorted_list), 1)


facts = {}
for lemma in sorted(population):
    e = db[lemma]
    groups = group_uni_freq.get(lemma, {})
    group_out = {}
    for gname, unis in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        freq = sum(unis.values())
        uni_count = len(unis)
        max_share = max(unis.values()) / freq if freq else 0.0
        group_out[gname] = {
            "frequency": freq,
            "university_count_in_group": uni_count,
            "group_size": GROUP_SIZES[gname],
            "group_freq_percentile": percentile_rank(group_freq_lists[gname], freq),
            "university_coverage_ratio": round(uni_count / GROUP_SIZES[gname], 2),
            "concentration_ratio": round(max_share, 2),
            "per_university_frequency": dict(sorted(unis.items(), key=lambda kv: -kv[1])),
        }
    facts[lemma] = {
        "lemma": lemma,
        "analysis_tier": "step4_2_analyzed" if lemma in step4_2_lemmas else "facts_only",
        "total_frequency": e["total_frequency"],
        "university_count": e["university_count"],
        "year_count": e["year_count"],
        "in_reference_book": e["in_reference_book"],
        "reference_book_codes": e["reference_book_codes"],
        "book_count": e["book_count"],
        "is_junior_high": e["is_junior_high"],
        "is_function_word": e["is_function_word"],
        "is_noise_fragment": e["is_noise_fragment"],
        "is_phrase": e["is_phrase"],
        "common_test": ("observed" if "共通テスト・センター試験" in groups else "not_observed"),
        "group_frequency": group_out,
        "university_frequency": dict(sorted(uni_freq.get(lemma, {}).items(), key=lambda kv: -kv[1])),
        "year_frequency": dict(sorted(year_freq.get(lemma, {}).items())),
        "faculty_relevance": "unknown - no faculty data exists in exam_tokens/",
    }

mismatches = [l for l, f in facts.items()
              if sum(g["frequency"] for g in f["group_frequency"].values()) != f["total_frequency"]]
tier_counts = {"step4_2_analyzed": sum(1 for f in facts.values() if f["analysis_tier"] == "step4_2_analyzed"),
               "facts_only": sum(1 for f in facts.values() if f["analysis_tier"] == "facts_only")}

out_path = ROOT / "data/interim/step5_word_facts_v3.json"
out_path.write_text(json.dumps({
    "_metadata": {
        "generated_by": "step5_compute_facts_v3.py",
        "supersedes_note": "Extends v1 (step5_word_facts.json) / v2 (step5_word_facts_v2.json), "
                            "which covered only the 5,198 STEP4-2 candidates, to the FULL "
                            "26,737-word STEP5 evaluation population (same filter as STEP4-1's "
                            "pool: not function_word/phrase/noise_fragment, total_frequency>0). "
                            "v1 and v2 files are left untouched. Percentiles here are computed "
                            "against the full 26,737-word distribution, NOT the narrower 5,198 "
                            "one v1/v2 used -- these numbers are therefore not directly comparable "
                            "to v1/v2's percentiles for the same lemma.",
        "university_groups": GROUP_NAMES,
        "group_sizes": GROUP_SIZES,
        "total_words": len(facts),
        "tier_counts": tier_counts,
        "sum_vs_total_frequency_mismatches": len(mismatches),
    },
    "words": facts,
}, ensure_ascii=False, indent=2))
print(f"[ok] wrote {out_path} ({len(facts)} words)")
print(f"[check] tier_counts: {tier_counts}")
print(f"[check] group-frequency-sum vs total_frequency mismatches: {len(mismatches)}")
if mismatches:
    print("  ", mismatches[:10])
