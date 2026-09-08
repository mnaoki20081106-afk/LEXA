"""
Phase A2 candidate triage, REBUILD (v2): reconstruct STEP1 (inflection
merge) -> STEP2 (junior-high/function-word attributes) -> STEP3
(reference-book cross-reference) as ONE consistent, non-destructive master
DB, built from the current (post text-saving-rerun) exam_tokens/ cache.

WHY THIS REBUILD EXISTS: an audit (see conversation) found that the 3rd
OCR pass (07_reprocess_exam_corpus_open_vocab.py, run to stop discarding
extracted text) regenerated exam_freq_open_*.json from scratch as raw
surface forms, silently reverting the STEP1 lemmatization that had
previously been applied on top of it. The STEP2/STEP3 outputs
(exam_only_candidates.json, exam_only_frequency_stats.json,
vocab_candidate_master.json) were therefore stale snapshots computed
against a version of the data that no longer exists. This script
rebuilds all three steps against the current data in one consistent pass,
and -- per LO's explicit instruction -- changes two things about how the
result is stored:
  1. STEP1 no longer destructively merges surface forms into their lemma
     key (which discards which surface forms contributed how much).
     Every lemma entry keeps a `surface_forms` breakdown.
  2. STEP2 no longer excludes (drops) junior-high/function words from the
     output. Every lemma stays in the master DB; classification is
     recorded as `is_junior_high` / `is_function_word` boolean attributes.

SOURCE OF TRUTH: data/interim/exam_tokens/<tier>/<file>.json (one file per
processed exam paper: university, year, raw token_freq). This is the same
data 11_frequency_analysis.py read for its university/year counts, and is
authoritative for word/university/year frequency -- exam_freq_open_*.json
is a derived aggregate of it and is NOT read here, to avoid re-introducing
the same kind of staleness this rebuild exists to fix.

REUSED LOGIC (imported, not re-implemented, per LO's instruction not to
rewrite verified logic):
  - lemmatize() -- imported from 08_lemmatize_exam_corpus.py via
    importlib (that module's filename starts with a digit, so it can't be
    `import`ed normally). Identical disambiguation rule already verified
    in the audit (abandon family merges, act/action/active/actively/
    activity stay separate, number/singer/teacher protected from false
    merges).
  - FUNCTION_WORDS, CONTRACTION_FRAGMENTS, ULTRA_BASIC_SUPPLEMENT --
    imported from 12_filter_function_words.py the same way, rather than
    copy-pasted, so this master DB and that script can never silently
    drift apart on what counts as a function word.
  - Reference-book cross-reference fields (in_reference_book,
    reference_book_codes, book_count) -- same fields/semantics as
    10_cross_reference_candidates.py, recomputed here from
    merged_lemmas.json against the freshly-rebuilt lemma set.

DOES NOT TOUCH OR OVERWRITE any existing file (exam_freq_open_*.json,
exam_only_candidates.json, exam_only_frequency_stats.json,
vocab_candidate_master.json, junior_high_words.json all remain exactly as
they were). Output goes to a new, explicitly versioned path
(--out, default data/interim/master_vocab_db.v2.json) so this can never be
confused with the old (now-superseded) snapshots.

STOPS AFTER STEP 3 -- no priority scoring, no adoption threshold, no
STEP4 work of any kind. That is intentionally out of scope for this run.

Usage:
    python3 13_build_master_vocab_db.py \
        --tokens-dir data/interim/exam_tokens \
        --junior-high-list data/interim/junior_high_words.json \
        --merged data/processed/merged_lemmas.json \
        --lemma-list data/processed/lemma_list.txt \
        --out data/interim/master_vocab_db.v2.json
"""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent


def _load_module(filename: str):
    spec = importlib.util.spec_from_file_location(filename[:-3], HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens-dir", default=Path("data/interim/exam_tokens"), type=Path)
    ap.add_argument("--junior-high-list", default=Path("data/interim/junior_high_words.json"), type=Path)
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--lemma-list", default=Path("data/processed/lemma_list.txt"), type=Path)
    ap.add_argument("--out", default=Path("data/interim/master_vocab_db.v2.json"), type=Path)
    args = ap.parse_args()

    lemmatize_mod = _load_module("08_lemmatize_exam_corpus.py")
    lemmatize = lemmatize_mod.lemmatize
    fw_mod = _load_module("12_filter_function_words.py")
    FUNCTION_WORDS = fw_mod.FUNCTION_WORDS
    CONTRACTION_FRAGMENTS = fw_mod.CONTRACTION_FRAGMENTS
    ULTRA_BASIC_SUPPLEMENT = fw_mod.ULTRA_BASIC_SUPPLEMENT

    junior_high_words = set(json.loads(args.junior_high_list.read_text()))

    # ---- STEP 1: aggregate raw exam_tokens surface forms into lemmas ----
    files = sorted(args.tokens_dir.glob("*/*.json"))
    raw_surface_forms: set[str] = set()
    master: dict[str, dict] = {}

    for fp in files:
        doc = json.loads(fp.read_text())
        uni, year = doc["university"], doc["year"]
        for surface, n in doc["token_freq"].items():
            raw_surface_forms.add(surface)
            lemma = surface if " " in surface else lemmatize(surface)
            entry = master.setdefault(lemma, {
                "surface_forms": {}, "total_frequency": 0,
                "universities": set(), "years": set(),
            })
            entry["surface_forms"][surface] = entry["surface_forms"].get(surface, 0) + n
            entry["total_frequency"] += n
            entry["universities"].add(uni)
            entry["years"].add(year)

    count_before_step1 = len(raw_surface_forms)
    count_after_step1 = len(master)

    # Sanity-check representative examples from LO's audit before proceeding.
    checks = [
        ("abandon", ["abandon", "abandoned", "abandoning", "abandons"], True),
        ("abandonment", ["abandonment"], False),
        ("act", ["act"], False),
        # "running" is intentionally NOT expected here: lemminflect gives it a
        # NOUN reading of itself ("running" the noun, e.g. gerund-as-noun), so
        # the documented conservative rule ("any POS mapping to itself blocks
        # the merge") correctly keeps it separate -- same tradeoff as the
        # already-approved better/best case, not a bug.
        ("run", ["run", "ran", "runs"], True),
        ("number", ["number"], False),
        ("singer", ["singer"], False),
        ("teacher", ["teacher"], False),
    ]
    check_results = []
    for expected_lemma, surfaces, expect_merge in checks:
        entry = master.get(expected_lemma)
        present_surfaces = sorted(entry["surface_forms"].keys()) if entry else []
        ok = entry is not None and (not expect_merge or all(s in entry["surface_forms"] for s in surfaces))
        check_results.append({"expected_lemma": expected_lemma, "expected_surfaces": surfaces,
                               "actual_surface_forms_present": present_surfaces, "ok": ok})

    # ---- STEP 2: junior-high / function-word attributes (non-destructive) ----
    for lemma, entry in master.items():
        entry["is_junior_high"] = lemma in junior_high_words or lemma in ULTRA_BASIC_SUPPLEMENT
        entry["is_function_word"] = lemma in FUNCTION_WORDS
        entry["is_noise_fragment"] = lemma in CONTRACTION_FRAGMENTS or len(lemma) <= 1
    count_after_step2 = len(master)  # STEP2 only attributes, never removes

    fw_check = {w: {"is_junior_high": w in junior_high_words or w in ULTRA_BASIC_SUPPLEMENT,
                     "is_function_word": w in FUNCTION_WORDS}
                for w in ["in", "on", "for", "as", "be", "can", "to", "fine"]}

    # ---- STEP 3: reference-book cross-reference (adds book-only lemmas too) ----
    merged = json.loads(args.merged.read_text())
    book_info = {e["lemma"]: {"reference_book_codes": sorted(e["sources"].keys()),
                               "book_count": e["book_count"], "is_phrase": e["is_phrase"]}
                 for e in merged["lemmas"]}

    for lemma, b in book_info.items():
        if lemma not in master:
            master[lemma] = {
                "surface_forms": {}, "total_frequency": 0,
                "universities": set(), "years": set(),
                "is_junior_high": lemma in junior_high_words or lemma in ULTRA_BASIC_SUPPLEMENT,
                "is_function_word": lemma in FUNCTION_WORDS,
                "is_noise_fragment": lemma in CONTRACTION_FRAGMENTS or len(lemma) <= 1,
            }
        master[lemma]["in_reference_book"] = True
        master[lemma]["reference_book_codes"] = b["reference_book_codes"]
        master[lemma]["book_count"] = b["book_count"]
        master[lemma]["is_phrase"] = b["is_phrase"]

    for lemma, entry in master.items():
        entry.setdefault("in_reference_book", False)
        entry.setdefault("reference_book_codes", [])
        entry.setdefault("book_count", 0)
        entry.setdefault("is_phrase", " " in lemma)

    count_after_step3 = len(master)
    book_lemma_missing = [l for l in book_info if l not in master]  # should be empty

    # ---- finalize: serialize sets, assemble output with metadata ----
    words_out = {}
    for lemma, entry in sorted(master.items()):
        words_out[lemma] = {
            "lemma": lemma,
            "surface_forms": entry["surface_forms"],
            "total_frequency": entry["total_frequency"],
            "universities": sorted(entry["universities"]),
            "years": sorted(entry["years"]),
            "university_count": len(entry["universities"]),
            "year_count": len(entry["years"]),
            "is_junior_high": entry["is_junior_high"],
            "is_function_word": entry["is_function_word"],
            "is_noise_fragment": entry["is_noise_fragment"],
            "in_reference_book": entry["in_reference_book"],
            "reference_book_codes": entry["reference_book_codes"],
            "book_count": entry["book_count"],
            "is_phrase": entry["is_phrase"],
        }

    output = {
        "_metadata": {
            "generated_by": "13_build_master_vocab_db.py",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_exam_tokens_dir": str(args.tokens_dir),
            "source_exam_tokens_file_count": len(files),
            "source_reference_books": sorted({code for b in book_info.values() for code in b["reference_book_codes"]}),
            "counts": {
                "raw_surface_forms_before_step1": count_before_step1,
                "distinct_lemmas_after_step1": count_after_step1,
                "distinct_lemmas_after_step2": count_after_step2,
                "distinct_lemmas_after_step3": count_after_step3,
            },
            "supersedes_note": (
                "This file (v2) is the authoritative rebuild. It does NOT overwrite or "
                "delete data/interim/exam_only_candidates.json, "
                "data/interim/exam_only_frequency_stats.json, or "
                "data/interim/vocab_candidate_master.json -- those are earlier, now-stale "
                "snapshots computed before the 3rd OCR pass and are kept as-is for reference "
                "but should not be used going forward."
            ),
        },
        "words": words_out,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # ---- report ----
    print(f"[step1] raw surface forms: {count_before_step1} -> lemmas: {count_after_step1}")
    print("[step1] sanity checks:")
    for c in check_results:
        print(f"    {c['expected_lemma']}: surface_forms present = {c['actual_surface_forms_present']} "
              f"-> {'OK' if c['ok'] else 'MISMATCH'}")
    print(f"[step2] lemma count unchanged (attributes only): {count_after_step2}")
    print("[step2] function/junior-high checks:", json.dumps(fw_check, ensure_ascii=False))
    print(f"[step3] lemma count after book cross-reference: {count_after_step3}")
    print(f"[step3] reference-book lemmas missing from master (should be 0): {len(book_lemma_missing)}")
    if book_lemma_missing:
        print("  MISSING:", book_lemma_missing[:20])
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
