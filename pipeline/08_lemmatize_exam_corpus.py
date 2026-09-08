"""
Phase A2 candidate triage, step 0 (runs BEFORE the junior-high filter):
collapse inflectional surface-form variants in the open-vocabulary exam
corpus (07_reprocess_exam_corpus_open_vocab.py's exam_freq_open_*.json)
into a single lemma, WITHOUT collapsing derivationally-related words.

Per LO: "abandon/abandoned/abandoning/abandons" must merge into one lemma,
but "act/action/active/actively/activity" must stay five separate lemmas.
That's the inflection-vs-derivation distinction: -ed/-ing/-s (verb) and
plural -s (noun) and comparative -er/-est (adjective) are INFLECTIONAL (same
word, different grammatical form); -tion/-ive/-ly/-ity are DERIVATIONAL
(different words, related but distinct meanings) and must not be touched.

WHY NOT A STEMMER: a stemmer (Porter/Snowball) truncates suffixes
mechanically and does not know this distinction -- it would just as
happily chop "action" down toward "act". A lemmatizer looks up whether a
form is a genuine inflection of some base word, which is exactly what's
needed here.

WHY NOT A CONTEXT-AWARE LEMMATIZER (spaCy/NLTK POS-tagged): the corpus was
already reduced to bag-of-words token counts per document
(data/interim/exam_tokens/, see 07's docstring on why -- only counts are
kept, not original text/word order, for copyright reasons), so there is no
sentence context left to POS-tag against. Re-doing the entire OCR pass a
third time just to keep context was judged not worth ~9-10 more hours of
sequential OCR for this refinement.

LIBRARY: lemminflect (pure-Python, ships its own WordNet-derived lookup
tables -- no runtime download, unlike nltk/spacy model downloads which
this sandbox's egress policy blocks). getAllLemmas(word) returns, for
every POS lemminflect recognizes the word under, that POS's lemma --
without needing to know which POS actually applies here (no context).

DISAMBIGUATION RULE (context-free, conservative by design):
  1. If lemminflect doesn't recognize the word at all -> leave unchanged
     (this catches proper nouns, rare/technical words, OCR artifacts that
     happen to pass the hunspell filter, etc.)
  2. If ANY recognized POS maps the word to ITSELF (i.e., under at least
     one plausible reading it's already a base form) -> leave unchanged.
     This is the safety rule: e.g. "number" has ADJ->'numb' (wrong reading)
     but NOUN->'number' (itself) -- since a valid reading says "already
     base form", we do not force the (wrong) ADJ merge. Cost: some
     genuinely-always-inflected words with a spurious identity reading
     under some POS won't get merged (e.g. "better"/"best" both have a
     NOUN/VERB self-mapping alongside the correct ADJ->'good', so they are
     conservatively left unmerged rather than risk false merges elsewhere).
     Verified against number/singer/teacher/faster/leaves/went/abandoned/
     actions/actively before shipping -- see commit message for the test
     transcript.
  3. Otherwise every recognized POS agrees the word is inflected. Collect
     the distinct lemma value(s); if more than one distinct value (a truly
     ambiguous form, e.g. "leaves" -> NOUN gives ('leave','leaf'), VERB
     gives 'leave'), break the tie by POS priority NOUN > VERB > ADJ > ADV
     (arbitrary, documented -- picks the more common reading in expository
     exam text over verb/adverb readings when genuinely ambiguous).

Usage:
    python3 08_lemmatize_exam_corpus.py --exam-freq-dir data/interim
Rewrites each data/interim/exam_freq_open_<tier>.json's term_freq/doc_freq
in place, merging surface forms into their lemma. Idempotent: running it
again on already-lemmatized files is a no-op (lemmatize(lemma) == lemma).
"""
import argparse
import json
from pathlib import Path

from lemminflect import getAllLemmas

POS_PRIORITY = ("NOUN", "VERB", "ADJ", "ADV")
_cache: dict[str, str] = {}


def lemmatize(word: str) -> str:
    if word in _cache:
        return _cache[word]
    candidates = getAllLemmas(word)
    if not candidates:
        result = word
    elif any(word in lemmas for lemmas in candidates.values()):
        result = word
    else:
        result = word
        for pos in POS_PRIORITY:
            if pos in candidates:
                result = candidates[pos][0]
                break
    _cache[word] = result
    return result


def merge_university(info: dict) -> dict:
    new_term_freq: dict[str, int] = {}
    new_doc_freq: dict[str, int] = {}
    for word, n in info["term_freq"].items():
        lemma = lemmatize(word) if " " not in word else word  # multi-word phrases untouched
        new_term_freq[lemma] = new_term_freq.get(lemma, 0) + n
    for word, n in info["doc_freq"].items():
        lemma = lemmatize(word) if " " not in word else word
        new_doc_freq[lemma] = new_doc_freq.get(lemma, 0) + n
    return {"doc_count": info["doc_count"], "term_freq": new_term_freq, "doc_freq": new_doc_freq}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam-freq-dir", default=Path("data/interim"), type=Path)
    args = ap.parse_args()

    before_total, after_total = 0, 0
    for fp in sorted(args.exam_freq_dir.glob("exam_freq_open_*.json")):
        data = json.loads(fp.read_text())
        before_words = set()
        after_words = set()
        merged_universities = {}
        for uni, info in data["universities"].items():
            before_words.update(info["term_freq"].keys())
            merged = merge_university(info)
            after_words.update(merged["term_freq"].keys())
            merged_universities[uni] = merged
        data["universities"] = merged_universities
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        before_total += len(before_words)
        after_total += len(after_words)
        print(f"[ok] {fp.name}: {len(before_words)} surface forms -> {len(after_words)} lemmas")

    print(f"[done] lemmatization cache size: {len(_cache)} words looked up")


if __name__ == "__main__":
    main()
