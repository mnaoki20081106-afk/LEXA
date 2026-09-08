"""
Phase A2 candidate triage, step 5: remove closed-class function words and
contraction-split OCR fragments from the exam-only candidates.

WHY THIS EXISTS: 11_frequency_analysis.py's top-10-by-breadth list was
dominated by "be, to, in, for, as, on, can, you" -- basic grammar words,
not vocabulary items. Root cause: 09_filter_junior_high.py's exclusion
list was built by regex-parsing two Eiken vocabulary-list PDFs, and the
regex missed some entries whose glosses wrap onto a second line with
leading Japanese parentheses (e.g. "in （場所・位置を示して）～の中に..."),
so words like "in"/"on"/"for"/"as"/"be"/"can" silently fell through.

Rather than patch the PDF-parsing regex (fragile, and these Eiken lists
were never meant to be an exhaustive closed-class word list anyway --
they're built for content vocabulary, not grammar), this uses a small,
hand-curated, linguistically well-established list: English closed-class
function words (articles, pronouns, prepositions, conjunctions,
auxiliary/modal verbs, common determiners/quantifiers) are a fixed,
well-known, stable inventory -- unlike open-class content vocabulary,
there is no ambiguity about what belongs on this list, so no external
source is needed for it.

CONTRACTION_FRAGMENTS handles a second, unrelated noise source: 06/07's
tokenizer splits on non-letter characters, so "it's"/"don't"/"we're" etc.
produce trailing fragments ("s", "t", "re", "ve", "ll", "d", "m") that
pass the hunspell real-word filter (hunspell recognizes some of these as
valid short words/abbreviations in isolation) but are never genuine
standalone vocabulary in this corpus.

Usage:
    python3 12_filter_function_words.py \
        --candidates data/interim/exam_only_candidates.json \
        --freq-stats data/interim/exam_only_frequency_stats.json
Rewrites both files in place, dropping any lemma in FUNCTION_WORDS or
CONTRACTION_FRAGMENTS.
"""
import argparse
import json
from pathlib import Path

FUNCTION_WORDS = {
    # articles
    "a", "an", "the",
    # personal / possessive / reflexive pronouns
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    "mine", "yours", "hers", "ours", "theirs",
    "myself", "yourself", "himself", "herself", "itself",
    "ourselves", "yourselves", "themselves",
    # demonstrative / relative / interrogative / indefinite pronouns
    "this", "that", "these", "those",
    "who", "whom", "whose", "which", "what",
    "someone", "somebody", "something",
    "anyone", "anybody", "anything",
    "everyone", "everybody", "everything",
    "nobody", "nothing",
    # prepositions
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "to", "from", "up", "down", "over", "under", "of", "off", "out", "as",
    "near", "since", "until", "upon", "within", "without", "along",
    "among", "around", "behind", "beside", "beyond", "despite", "except",
    "inside", "outside", "throughout", "toward", "towards", "via", "per",
    # conjunctions
    "and", "but", "or", "nor", "so", "yet", "although", "because",
    "unless", "while", "whereas", "if", "though", "whether",
    "either", "neither",
    # auxiliary / modal verbs
    "be", "is", "am", "are", "was", "were", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "done",
    "will", "would", "shall", "should", "can", "could", "may", "might",
    "must", "ought",
    # determiners / quantifiers
    "some", "any", "no", "every", "each", "all", "both", "several",
    "many", "much", "few", "little", "more", "most", "other", "another",
    "such", "own", "same", "own",
    # other common function/discourse words
    "not", "than", "there", "here", "very", "too", "also", "just",
    "only", "even", "still", "ever", "never", "one",
}

CONTRACTION_FRAGMENTS = {"s", "t", "re", "ve", "ll", "d", "m", "don"}

# Wh-words and a handful of ultra-common words that are genuinely absent as
# standalone headwords from both source Eiken PDFs (they only appear there
# embedded in phrases, e.g. "want to do", "Why not?") -- confirmed by
# grepping the raw PDF text, not a parsing gap. These are unambiguously
# below the reference books' 基礎 tier, so they belong in the same
# exclusion bucket as the PDF-derived junior-high list.
ULTRA_BASIC_SUPPLEMENT = {
    "how", "why", "where", "when", "use", "used", "want", "less", "long", "new", "now",
}

EXCLUDE = FUNCTION_WORDS | CONTRACTION_FRAGMENTS | ULTRA_BASIC_SUPPLEMENT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=Path("data/interim/exam_only_candidates.json"), type=Path)
    ap.add_argument("--freq-stats", default=Path("data/interim/exam_only_frequency_stats.json"), type=Path)
    args = ap.parse_args()

    candidates = json.loads(args.candidates.read_text())
    before = len(candidates)
    # Single-character tokens are never genuine multi-letter content vocabulary
    # in English (the only real single-letter words, "a"/"i", are already in
    # FUNCTION_WORDS) -- these are OCR/formatting artifacts (multiple-choice
    # option labels "(A)(B)(C)...", stray marks) that happen to pass the
    # hunspell real-word filter in 07 because hunspell recognizes many single
    # letters as valid abbreviations in isolation.
    is_noise = lambda w: w in EXCLUDE or len(w) <= 1
    removed_from_candidates = sorted(w for w in candidates if is_noise(w))
    candidates = {w: v for w, v in candidates.items() if not is_noise(w)}
    args.candidates.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    print(f"[ok] {args.candidates}: {before} -> {len(candidates)} "
          f"(removed {len(removed_from_candidates)}: {removed_from_candidates})")

    if args.freq_stats.exists():
        stats = json.loads(args.freq_stats.read_text())
        before2 = len(stats)
        stats = {w: v for w, v in stats.items() if not is_noise(w)}
        args.freq_stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
        print(f"[ok] {args.freq_stats}: {before2} -> {len(stats)}")


if __name__ == "__main__":
    main()
