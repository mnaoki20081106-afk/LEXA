"""
Phase A: assemble the final Word-table skeleton (schema.sql `word` +
`reference_book_source` rows) from the outputs of 02/03/04.

This produces STRUCTURE only (word_id, lemma, family fields, is_phrase,
difficulty_level, which books it came from) — never Sense content
(meaning_ja/example_en/ja), since that must be authored originally
(project_overview.txt §17). Sense authoring is separate, later work.

`required_for_common_test` is deliberately left `false` for every row here.
Which lemmas belong in the free "共通テスト単語帳" deck is a product/content
decision (e.g. a difficulty_level threshold, or "must appear in a minimum
number of foundational books") that is NOT specified anywhere in the
attached specs — home_screen_design.md just says the deck exists, not which
words populate it. Flagging rather than guessing a threshold.

Usage:
    python3 05_build_word_table.py \
        --scored data/processed/vocab_scored.json \
        --families data/processed/word_families.json \
        --out data/processed/vocab_master.json
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", default=Path("data/processed/vocab_scored.json"), type=Path)
    ap.add_argument("--families", default=Path("data/processed/word_families.json"), type=Path)
    ap.add_argument("--out", default=Path("data/processed/vocab_master.json"), type=Path)
    args = ap.parse_args()

    scored = json.loads(args.scored.read_text())["lemmas"]
    fam_data = json.loads(args.families.read_text())

    family_of_lemma: dict[str, str] = {}
    family_role: dict[str, str] = {}
    family_id_of_root: dict[str, str] = {}
    for i, fam in enumerate(sorted(fam_data["families"], key=lambda f: f["root"]), start=1):
        root = fam["root"]
        family_id_of_root[root] = f"F{i:05d}"
        family_of_lemma[root] = root
        family_role[root] = "root"
        for m in fam["members"]:
            family_of_lemma[m["lemma"]] = root
            family_role[m["lemma"]] = "derived"

    words = []
    for i, entry in enumerate(sorted(scored, key=lambda e: e["lemma"]), start=1):
        lemma = entry["lemma"]
        words.append({
            "word_id": f"W{i:06d}",
            "lemma": lemma,
            "is_phrase": entry["is_phrase"],
            "family_id": family_id_of_root.get(family_of_lemma.get(lemma)),
            "family_role": family_role.get(lemma),
            "family_of_lemma": family_of_lemma.get(lemma) if family_role.get(lemma) == "derived" else None,
            "difficulty_level": entry["difficulty_level"],
            "base_score_raw": entry["base_score_raw"],
            "boost_score_raw": entry["boost_score_raw"],  # always 0.0 in Phase A, see 03_score_vocab.py
            "reference_book_codes": sorted(entry["sources"].keys()),
            "required_for_common_test": False,  # TBD, see docstring
            "required_for_school_ids": [],       # populated in Phase A2/B once school vocab sets exist
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"words": words}, ensure_ascii=False, indent=2))
    print(f"[ok] {len(words)} Word rows -> {args.out}")
    families_used = sum(1 for w in words if w["family_id"])
    print(f"[ok] {families_used} words carry a family_id "
          f"({fam_data['family_count']} families, {fam_data['derived_word_count']} derived)")


if __name__ == "__main__":
    main()
