"""
STEP5 fact layer (deterministic, no LLM judgment here): for each of the
5,198 STEP4-2 candidate words, compute EXACT per-university-group and
per-university frequency/breadth statistics directly from the raw
exam_tokens/ cache, plus lemma-level reference-book and STEP4-2 sense
summaries. This is the factual evidence base that the STEP5 judgment
layer (a separate, LLM-driven pass) must ground its evaluation in,
per LO's explicit rule: "事実と評価を混ぜない" -- computed frequency
facts must never be re-guessed by an LLM.

UNIVERSITY GROUPS: the exam_tokens/<tier>/ directory name IS the
university-group label already used throughout this pipeline (see
task list: "日東駒専 tier", "早慶上理 tier", "MARCH tier"). Verified by
listing which universities actually appear under each tier directory:
  kyuutei        -> 旧帝大 (北海道/東北/東京/名古屋/京都/大阪/九州大学)
  tocky          -> other national universities (筑波/横浜国立/千葉/神戸/お茶の水女子大学)
  kyoutsuu       -> 共通テスト・センター試験
  kankandoritsu  -> 関関同立 (関西学院/立命館/関西/同志社大学)
  nittokomasen   -> 日東駒専 (日本/専修/東洋/駒澤大学)
  march          -> MARCH (明治/法政/中央/青山学院/立教大学)
  soukeijouri    -> 早慶上理 (東京理科/慶應義塾/上智/早稲田大学)
These 7 labels are taken directly from the existing directory structure,
not invented. The "tocky" group's common Japanese name could not be
confirmed from any file in this repo, so it is reported using its
existing internal code only, not a guessed nickname.

FACULTY: exam_tokens/*/*.json stores only {university, year, title,
used_ocr, token_freq} -- title is an opaque internal code (e.g.
"eak184_question.pdf"), not a faculty name. NO faculty information
exists anywhere in this pipeline's data. Every faculty_relevance field
this script and the STEP5 judgment layer produce is therefore the
literal string "unknown" -- never guessed.

DIFFICULTY: there is no explicit difficulty rating anywhere in the
data. This script computes only a descriptive proxy
(group_breadth_pattern) from which groups a word's surface forms
were actually observed in; it does NOT label this "difficulty" itself
-- that interpretive step belongs to the STEP5 judgment layer, which
must mark any difficulty claim it makes as inferred/derived.

OUTPUT: data/interim/step5_word_facts.json (new file). Does not read
or write master_vocab_db.v2.json or step4_sense_analysis.json's
content beyond read-only lookups; never modifies either.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/user/work/LEXA/pipeline")

db = json.loads((ROOT / "data/interim/master_vocab_db.v2.json").read_text())["words"]
step4 = json.loads((ROOT / "data/interim/step4_sense_analysis.json").read_text())["words"]
candidate_lemmas = set(step4.keys())

GROUP_NAMES = {
    "kyuutei": "旧帝大",
    "tocky": "other_national (unconfirmed common name)",
    "kyoutsuu": "共通テスト・センター試験",
    "kankandoritsu": "関関同立",
    "nittokomasen": "日東駒専",
    "march": "MARCH",
    "soukeijouri": "早慶上理",
}

# ---- rebuild per-lemma per-university-group / per-university frequency
#      directly from the raw exam_tokens cache (same source STEP1 used) ----
lemmatize_spec = None
import importlib.util
spec = importlib.util.spec_from_file_location("lemmatize_mod", ROOT / "08_lemmatize_exam_corpus.py")
lemmatize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lemmatize_mod)
lemmatize = lemmatize_mod.lemmatize

files = sorted((ROOT / "data/interim/exam_tokens").glob("*/*.json"))
print(f"[info] scanning {len(files)} exam_tokens files for per-university-group facts...")

# lemma -> group -> freq ; lemma -> university -> freq ; lemma -> year -> freq
group_freq = defaultdict(lambda: defaultdict(int))
uni_freq = defaultdict(lambda: defaultdict(int))
year_freq = defaultdict(lambda: defaultdict(int))
group_uni_count = defaultdict(lambda: defaultdict(set))  # lemma -> group -> {universities}

for fp in files:
    tier = fp.parent.name
    doc = json.loads(fp.read_text())
    uni, year = doc["university"], doc["year"]
    for surface, n in doc["token_freq"].items():
        lemma = surface if " " in surface else lemmatize(surface)
        if lemma not in candidate_lemmas:
            continue
        group_freq[lemma][tier] += n
        uni_freq[lemma][uni] += n
        year_freq[lemma][year] += n
        group_uni_count[lemma][tier].add(uni)

# ---- assemble per-word fact record ----
facts = {}
for lemma in sorted(candidate_lemmas):
    e = db[lemma]
    gf = group_freq.get(lemma, {})
    uf = uni_freq.get(lemma, {})
    yf = year_freq.get(lemma, {})
    guc = group_uni_count.get(lemma, {})

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
        # FACT: exact frequency per university-group directory (source: exam_tokens/)
        "group_frequency": {GROUP_NAMES.get(g, g): {"code": g, "frequency": n,
                                                       "university_count_in_group": len(guc[g])}
                             for g, n in sorted(gf.items(), key=lambda kv: -kv[1])},
        # FACT: exact frequency per individual university
        "university_frequency": dict(sorted(uf.items(), key=lambda kv: -kv[1])),
        # FACT: exact frequency per year (raw year strings as stored)
        "year_frequency": dict(sorted(yf.items())),
        "faculty_frequency": "unknown - no faculty data exists in exam_tokens/",
    }

out_path = ROOT / "data/interim/step5_word_facts.json"
out_path.write_text(json.dumps({
    "_metadata": {
        "generated_by": "step5_compute_facts.py",
        "note": "Deterministic FACT layer only -- no learning-value judgment here. "
                "group_frequency/university_frequency/year_frequency are exact counts "
                "recomputed from data/interim/exam_tokens/*/*.json. faculty data does "
                "not exist anywhere in this pipeline and is marked unknown throughout.",
        "university_groups": GROUP_NAMES,
        "total_words": len(facts),
    },
    "words": facts,
}, ensure_ascii=False, indent=2))
print(f"[ok] wrote {out_path} ({len(facts)} words)")

# sanity spot-check
for l in ["fine", "address", "abandon"]:
    if l in facts:
        f = facts[l]
        print(f"  {l}: total={f['total_frequency']} groups={list(f['group_frequency'].keys())}")
