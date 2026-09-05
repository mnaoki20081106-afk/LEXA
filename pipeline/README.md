# LEXA data pipeline (Phase A)

Builds the common vocabulary DB described in `project_overview.txt` §7-9 and
scores each lemma per `vocab_scoring_algorithm.txt`.

## Copyright handling (read before touching this directory)

- Publisher PDFs (システム英単語, ターゲット1900, 速読英単語必修編, LEAP Basic,
  準1級パス単, SPARTA3, 速読英熟語) and the past-exam corpus are **never
  committed to this repo** (`.gitignore` excludes `pipeline/data/raw/` and
  `*.pdf`). They live only on the machine running the pipeline.
- The scripts extract *positions* (index-in-book) and *headword text* only.
  Japanese glosses printed in the books are read only to help a human verify
  the parse; they are discarded, never written to `data/interim/` or
  `data/processed/`, and never become app content. Card content
  (`meaning_ja`, `example_en/ja` in `schema.sql`) is written originally by
  the app team, per `project_overview.txt` §17 / `supplementary_design_spec.md` §4.2.
- `data/processed/vocab_scored.json` (the only pipeline output meant to be
  committed) contains lemmas + numeric scores + book membership flags only —
  a statistical derivative, not a reproduction of any book.

## Pipeline stages

```
01_extract_reference_books.py   PDF -> data/interim/<book>.json (index, headword)
01b_ocr_sparta3.py              SPARTA3 PDF (image-render + OCR) -> data/interim/sparta3.json
02_normalize_and_merge.py       per-book jsons -> data/processed/merged_lemmas.json (cross-book dedup)
03_score_vocab.py               merged lemmas -> data/processed/vocab_scored.json (0.0-10.0 difficulty)
04_build_word_families.py       merged lemmas -> data/processed/word_families.json (Word Family groups,
                                 phrase-to-headword attachment candidates -- REVIEW list, not authoritative)
05_build_word_table.py          scored lemmas + families -> data/processed/vocab_master.json
                                 (final Word-row skeleton: word_id, family fields, is_phrase,
                                 difficulty, source books -- NO sense/gloss content, see its docstring)
```

Run:
```
pip install -r requirements.txt
apt-get install -y tesseract-ocr tesseract-ocr-eng   # for 01b only
python3 01_extract_reference_books.py --input-dir /path/to/reference_books --out-dir data/interim
python3 01b_ocr_sparta3.py --pdf "/path/to/大学入試英単語 SPARTA3 一覧.pdf" --out-dir data/interim
python3 02_normalize_and_merge.py
python3 03_score_vocab.py
python3 04_build_word_families.py
python3 05_build_word_table.py
```

## Status (Phase A, this commit)

Done:
- Text extraction for all 6 vocab-list PDFs (sisutan, target1900,
  sokutan_hisshu, leap_basic, passtan_jun1kyu, sparta3) + the phrase book
  (sokujukugo). SPARTA3 needed OCR (see `01b_ocr_sparta3.py` docstring for
  why and how — its font has no text mapping at all, verified empirically,
  and the initial straightforward OCR attempt silently mis-read most rows
  until the table's grid lines were stripped out first).
- Cross-book lemma merge with duplicate detection (5,255 unique lemmas from
  the 7 books in the reference run).
- vocab_scoring_algorithm.txt Step 1 (percentile baseline + 0.9 duplicate
  discount) and Step 3 (0-10 normalization).
- Word Family grouping (card_ui_logic_spec.md §1.1/§4/§5) via suffix rules:
  262 families / 279 derived words detected (e.g. respect → respectable).
  **Spot-checked with a random sample and found real false positives**
  (author→authority, pose→position, tend→tender — coincidental suffix
  matches, not real derivations). `word_families.json` is a review worklist,
  not an authoritative Word Family table — see `04_build_word_families.py`
  docstring for why (basis 1 from the spec, "use the source book's own
  structure," isn't answerable from flat "一覧" list PDFs — they carry no
  section/heading markup at all, only basis 2 form-based rules are usable
  here) and for the phrase→headword attachment heuristic (429 of 1,031
  phrases flagged as candidates, same caveat).
- `vocab_master.json`: final Word-row skeleton assembled from all of the
  above (5,255 rows). Still has no Sense/gloss content — that's original
  content to be authored later, out of pipeline scope by design.

Deferred / TBD:
1. **Step 2 (入試特異性ブースト)**: needs the past-exam corpus. Located at
   Google Drive `英単語LEXA/過去問.zip` — **2.7 GB, single zip**. This
   environment's network policy blocks direct connections to
   `drive.google.com` outright (confirmed: proxy returns 403 on CONNECT),
   and the Google Drive MCP tool only offers whole-file download as a
   base64 string, which would try to inline ~3.6 GB of base64 text into
   the session — not viable at any size, let alone this one. **This corpus
   cannot be fetched or inspected from this environment as currently set
   up.** Needs a decision from the project owner: e.g. re-share the corpus
   as an already-unzipped Drive folder (so individual PDFs, each small, can
   be listed and pulled one at a time — which is also what
   `supplementary_design_spec.md` §4.1 already mandates: process one file
   at a time, never load the whole corpus at once), or another distribution
   channel this session can reach. Until resolved, `boost_score_raw` stays
   hardcoded to `0.0` for every lemma (see `03_score_vocab.py` docstring);
   schema and downstream code are already shaped for it so no rework is
   needed once real values exist.
2. **Known algorithm limitation, flagging rather than silently patching**:
   `vocab_scoring_algorithm.txt` §3 Step 1 defines Base_Score purely as
   average index-percentile across the books a lemma appears in, with no
   per-book tier weight. This produces a visible distortion for SPARTA3
   specifically, since it's categorized "発展" (advanced) rather than "基礎的"
   (foundational) in the source material, yet its *internal* ordering is
   still index-1-first. A word like "solicit" (SPARTA3 index #2) currently
   scores as one of the *easiest* lemmas in the whole merged set purely
   because it's early in an advanced-only book — clearly wrong. The spec as
   written doesn't account for this, and I'm not silently inventing a
   tier-weight correction since that's a real scoring-methodology choice,
   not an implementation gap. Flagging for a decision (e.g. weight
   基礎的-tier books higher than 発展-tier books when averaging percentiles).
3. **Extraction coverage**: index-position regex/OCR parsing is heuristic,
   not a real PDF-table parser. Spot-checked at ~75-98% coverage per book
   (e.g. sisutan: 1,560 of ~2,027 headwords; sparta3 OCR: 948 of ~1,000).
   Good enough for Phase A's percentile baseline (missing entries just
   don't contribute a data point), but should be tightened before this is
   treated as authoritative.
4. **Lemmatization is a placeholder** (`02_normalize_and_merge.py`):
   lowercase + whitespace collapse only, no real morphological analyzer.
   Inflected-form variants across books (e.g. "arise" vs "arisen") will
   under-merge. No English lemmatizer is installed in this environment
   (no spaCy/NLTK). Swap in a real one before treating merged counts as final.
5. **Word Family / phrase classification** (card_ui_logic_spec.md §5) is not
   yet run — this pipeline only produces flat lemmas + `is_phrase` (a lemma
   containing a space, or sourced from the phrase book). The 3-tier
   root/derived/pattern classification described in §5 needs a follow-up
   pass and is Phase A's next step, not done in this commit.
