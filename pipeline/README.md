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
02_normalize_and_merge.py       per-book jsons -> data/processed/merged_lemmas.json (cross-book dedup)
03_score_vocab.py               merged lemmas -> data/processed/vocab_scored.json (0.0-10.0 difficulty)
```

Run:
```
pip install -r requirements.txt
python3 01_extract_reference_books.py --input-dir /path/to/reference_books --out-dir data/interim
python3 02_normalize_and_merge.py
python3 03_score_vocab.py
```

## Status (Phase A, this commit)

Done:
- Text extraction for 5 of 6 vocab-list PDFs (sisutan, target1900,
  sokutan_hisshu, leap_basic, passtan_jun1kyu) + the phrase book (sokujukugo).
- Cross-book lemma merge with duplicate detection (4,675 unique lemmas from
  the 6 books in the reference run).
- vocab_scoring_algorithm.txt Step 1 (percentile baseline + 0.9 duplicate
  discount) and Step 3 (0-10 normalization).

Deferred / TBD:
1. **SPARTA3 PDF**: the font is subsetted with no ToUnicode CMap, so
   `pdfplumber`/`pypdf` return only glyph IDs, not text. Needs a
   render-to-image + OCR step (`pdf2image` + `pytesseract`, neither
   installed in this environment yet). Not started.
2. **Step 2 (入試特異性ブースト)**: needs the past-exam corpus. Located at
   Google Drive `英単語LEXA/過去問.zip` — **2.7 GB, single zip, internal
   folder structure not yet inspected** (downloading and unzipping a file
   this size needs to happen deliberately, not as a side effect of a
   text-extraction script — see project brief's own instruction not to
   assume folder-naming conventions before looking). This is the next thing
   to investigate before Step 2 can be written. Until then `boost_score_raw`
   is hardcoded to `0.0` for every lemma (see `03_score_vocab.py` docstring);
   the schema and downstream code are already shaped for it so no rework is
   needed once real values exist.
3. **Extraction coverage**: index-position regex parsing is heuristic, not a
   real PDF-table parser. Spot-checked at ~75-95% coverage per book (e.g.
   sisutan: 1,560 of ~2,027 headwords). Good enough for Phase A's percentile
   baseline (missing entries just don't contribute a data point), but should
   be tightened before this is treated as authoritative.
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
