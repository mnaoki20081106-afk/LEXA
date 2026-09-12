"""
STEP5 fact layer v2: rebuilds the per-university-group facts from
exam_tokens/ directly (same source as v1, data/interim/step5_word_facts.json,
which is kept as-is, not overwritten), additionally computing the
mechanical statistics the RELEVANCE RUBRIC needs so the STEP5 judgment
layer never has to invent a frequency number, per LO's rule
"AIの主観だけでHIGH/MEDIUM/LOWを決めない":

For each lemma x university_group (only groups where frequency>0):
  - frequency, university_count_in_group        (facts, as in v1)
  - group_freq_percentile   : this lemma's group-frequency percentile
    against all 5,198 candidates' frequencies within that same group
  - university_coverage_ratio : university_count_in_group / total
    universities known to belong to that group
  - concentration_ratio : the largest single-university share of this
    lemma's frequency WITHIN that group (1.0 = all occurrences in the
    group come from one university; low value = broad spread across
    the group's universities) -- this is what lets the judgment layer
    tell "1大学に集中している高頻度語" apart from "多数大学に広く出現する語"

None of these are learning-value labels -- they are still facts/mechanical
derivations. Labeling (HIGH/MEDIUM/LOW relevance) is done by the
judgment layer using STEP5_RUBRIC.md as a starting point, with room to
deviate when sense-level context warrants it, provided it records why.

OUTPUT: data/interim/step5_word_facts_v2.json (new file; v1 untouched).
"""
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")
db = json.loads((ROOT / "data/interim/master_vocab_db.v2.json").read_text())["words"]
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
candidate_lemmas = set(step4.keys())

GROUP_NAMES = {
    "kyuutei": "旧帝大", "tocky": "other_national (unconfirmed common name)",
    "kyoutsuu": "共通テスト・センター試験", "kankandoritsu": "関関同立",
    "nittokomasen": "日東駒専", "march": "MARCH", "soukeijouri": "早慶上理",
}
GROUP_SIZES = {"旧帝大": 7, "other_national (unconfirmed common name)": 5,
               "共通テスト・センター試験": 1, "関関同立": 4, "日東駒専": 4, "MARCH": 5, "早慶上理": 4}

spec = importlib.util.spec_from_file_location("lemmatize_mod", ROOT / "08_lemmatize_exam_corpus.py")
lemmatize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lemmatize_mod)
lemmatize = lemmatize_mod.lemmatize

files = sorted((ROOT / "data/interim/exam_tokens").glob("*/*.json"))
print(f"[info] scanning {len(files)} exam_tokens files for group x university breakdown...")

# lemma -> group -> university -> freq
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
        if lemma not in candidate_lemmas:
            continue
        group_uni_freq[lemma][gname][uni] += n
        year_freq[lemma][year] += n
        uni_freq[lemma][uni] += n

# ---- per-group frequency distributions (for percentile ranking) ----
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
for lemma in sorted(candidate_lemmas):
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

# sanity: sum of group frequencies must equal master DB total_frequency
mismatches = [l for l, f in facts.items()
              if sum(g["frequency"] for g in f["group_frequency"].values()) != f["total_frequency"]]

out_path = ROOT / "data/interim/step5_word_facts_v2.json"
out_path.write_text(json.dumps({
    "_metadata": {
        "generated_by": "step5_compute_facts_v2.py",
        "supersedes_note": "Adds group_freq_percentile/university_coverage_ratio/"
                            "concentration_ratio/per_university_frequency/common_test on top "
                            "of step5_word_facts.json (v1, kept unmodified). Still a pure FACT "
                            "layer -- no learning-value or relevance label is assigned here.",
        "university_groups": GROUP_NAMES,
        "group_sizes": GROUP_SIZES,
        "total_words": len(facts),
        "sum_vs_total_frequency_mismatches": len(mismatches),
    },
    "words": facts,
}, ensure_ascii=False, indent=2))
print(f"[ok] wrote {out_path} ({len(facts)} words)")
print(f"[check] group-frequency-sum vs total_frequency mismatches: {len(mismatches)}")
if mismatches:
    print("  ", mismatches[:10])

for l in ["fine", "address"]:
    if l in facts:
        f = facts[l]
        print(f"  {l}: common_test={f['common_test']}")
        for g, v in f["group_frequency"].items():
            print(f"    {g}: freq={v['frequency']} pct={v['group_freq_percentile']} "
                  f"coverage={v['university_coverage_ratio']} concentration={v['concentration_ratio']}")
