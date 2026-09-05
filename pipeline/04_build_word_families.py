"""
Phase A: Word Family grouping + phrase/headword attachment
(card_ui_logic_spec.md §1.1 family_id/family_role/family_of_lemma, §5).

IMPORTANT CAVEAT — read before trusting this script's output:

card_ui_logic_spec.md §5's basis 1 ("最優先: 参照教材の構造をそのまま使う") is
NOT applicable to our input data. It asks us to check whether the *source
book* lists a form under a "派生語/Word Family" heading vs. a "熟語/語法"
heading. But our reference-book inputs are all "一覧" (flat index list)
PDFs — number + headword + gloss only, with no section/heading markup at
all (verified: e.g. LEAP Basic mixes "get in touch with" at index 26 in the
same flat numbered list as ordinary single words — there is no structural
signal distinguishing it). So this script always falls through to:

  - basis 2 (form-based): a derivational suffix (-tion/-ment/-able/-ful/
    -ive/-ous/-ize/-ly/-ness/agent-noun -er, etc.) groups two single-word
    lemmas into a Word Family (root + derived).
  - basis 3 (stands-alone test) for multi-word phrase entries: if the first
    token of a phrase matches a known single-word lemma AND the phrase is
    short, we *guess* it's a pattern anchored to that headword (candidate
    for a kind="pattern" Sense — actual Sense authoring is separate, later
    work, not done here). Otherwise it's left as its own independent Word
    (`is_phrase = true`, already set in 02_normalize_and_merge.py).

Both of these are heuristics with known false positives/negatives — e.g.
"look like" correctly attaches to "look", but a phrase that happens to
start with a real headword purely coincidentally (not semantically related)
would be wrongly flagged as attachable. This script's output
(`attach_candidate`) should be treated as a worklist for human/product
review, not an authoritative classification — consistent with the
project's own instruction not to let Claude Code decide such things
silently.

One more open question this surfaces, not resolved here (flagging per the
project's "don't guess, report" instruction): agent-noun "-er" (observe ->
observer, changes part of speech, arguably basis-2's "POS-changing
suffix" category) vs. inflectional comparative "-er" (big -> bigger,
explicitly listed in basis 2 as NOT a Word Family case) use the identical
suffix. This script only applies the "-er" rule to verb-like roots (root
also found as a lemma AND root + "er"/"or" forms a plausible agent noun),
which will still occasionally misfire on real comparatives if the base
adjective happens to also be a known lemma (e.g. it would NOT trigger for
"big"/"bigger" since "bigg" isn't a real root, but could misfire on
purely coincidental cases). Flagged, not silently assumed correct.

Usage:
    python3 04_build_word_families.py --merged data/processed/merged_lemmas.json \
        --out data/processed/word_families.json
"""
import argparse
import json
from pathlib import Path

# (suffix, [candidate root-suffix replacements to try, longest/most-specific first])
SUFFIX_RULES = [
    ("fully", ["ful"]),                      # respectfully -> respectful
    ("ibly", ["ible"]),
    ("ably", ["able"]),
    ("ment", [""]),                          # development -> develop
    ("ation", ["e", ""]),                    # correlation -> correlate; creation -> create
    ("ition", ["e", ""]),                    # supposition -> suppose
    ("sion", ["de", "se", ""]),              # decision -> decide
    ("ance", ["e", ""]),
    ("ence", ["e", ""]),
    ("able", ["e", ""]),                     # respectable -> respect; usable -> use
    ("ible", ["e", ""]),
    ("ful", ["e", ""]),                      # hopeful -> hope; respectful -> respect
    ("ive", ["e", ""]),                      # creative -> create
    ("ous", ["e", ""]),                      # famous -> fame; dangerous -> danger
    ("ize", [""]),
    ("ise", [""]),
    ("ness", [""]),                          # kindness -> kind
    ("ity", ["e", ""]),
    ("er", ["e", ""]),                       # observer -> observe (agent noun; see caveat above)
    ("or", ["e", ""]),
    ("ly", [""]),                            # quickly -> quick (checked after "fully"/"ibly"/"ably")
]

MAX_PHRASE_WORDS_FOR_ATTACHMENT = 5


def find_root(lemma: str, known: set[str]) -> tuple[str, str] | None:
    """Try each suffix rule; return (root, suffix_used) if root is a known lemma."""
    for suffix, replacements in SUFFIX_RULES:
        if not lemma.endswith(suffix) or len(lemma) <= len(suffix) + 2:
            continue
        stem = lemma[: -len(suffix)]
        for repl in replacements:
            candidate = stem + repl
            if candidate != lemma and candidate in known:
                return candidate, suffix
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=Path("data/processed/merged_lemmas.json"), type=Path)
    ap.add_argument("--out", default=Path("data/processed/word_families.json"), type=Path)
    args = ap.parse_args()

    data = json.loads(args.merged.read_text())
    lemmas = data["lemmas"]
    single_word = {e["lemma"] for e in lemmas if not e["is_phrase"]}

    families: dict[str, dict] = {}  # root lemma -> {members: [{lemma, suffix}]}
    family_of: dict[str, str] = {}  # lemma -> root lemma

    for entry in lemmas:
        lemma = entry["lemma"]
        if entry["is_phrase"] or lemma in family_of:
            continue
        found = find_root(lemma, single_word)
        if found:
            root, suffix = found
            families.setdefault(root, {"root": root, "members": []})
            families[root]["members"].append({"lemma": lemma, "suffix": suffix})
            family_of[lemma] = root

    # Phrase -> headword attachment candidates (basis 3 heuristic, see caveat).
    attach_candidates = []
    for entry in lemmas:
        if not entry["is_phrase"]:
            continue
        tokens = entry["lemma"].split(" ")
        head = tokens[0]
        if head in single_word and 1 < len(tokens) <= MAX_PHRASE_WORDS_FOR_ATTACHMENT:
            attach_candidates.append({"phrase": entry["lemma"], "headword": head})

    out = {
        "families": list(families.values()),
        "family_count": len(families),
        "derived_word_count": len(family_of),
        "phrase_attach_candidates": attach_candidates,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"[ok] {len(families)} families, {len(family_of)} derived words -> {args.out}")
    print(f"[ok] {len(attach_candidates)} phrase-attachment candidates "
          f"(of {sum(1 for e in lemmas if e['is_phrase'])} phrases) -- REVIEW, not authoritative")
    sample = list(families.values())[:5]
    for fam in sample:
        print("  ", fam["root"], "->", [m["lemma"] for m in fam["members"]])


if __name__ == "__main__":
    main()
