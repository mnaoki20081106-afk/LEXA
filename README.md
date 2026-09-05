# LEXA

大学受験生向け英単語アプリ。「単語を覚えるアプリ」ではなく、志望校に必要な
語彙を試験日までに覚え切るアプリ。設計思想の全文は
`docs/project_overview.txt` を参照。

## Repository layout

```
pipeline/   Python: reference-book parsing, lemma merge, difficulty scoring
            (see pipeline/README.md for copyright handling and pipeline status)
ios/        SwiftUI + SwiftData iOS app, XcodeGen project (see ios/README.md
            for why there's no checked-in .xcodeproj and what that means)
docs/       The attached specification documents, unmodified, for reference
```

## Development environment note

This project is being built from a Claude Code cloud session with no
macOS/Xcode access. Data-layer work (pipeline, SwiftData models) can be
fully built and, where possible, tested here (the Python pipeline runs and
its output is verified). The iOS app itself cannot be compiled or run in a
simulator from this environment — see `ios/README.md`.

## Phase status

Priority order when specs conflict (per project brief):
`card_ui_logic_spec.md` > `home_screen_design.md` (+ `supplementary_design_spec.md`,
which only fills gaps in the first two) > `vocab_scoring_algorithm.txt` >
`project_overview.txt`.

| Phase | Scope | Status |
|---|---|---|
| A | Vocab DB foundation (Word/Sense/UserWordState models, reference-book parsing, difficulty scoring, Word Family fields) | **In progress** — see below |
| A2 | Past-exam corpus analysis (TF-IDF exam-specificity boost) | **Blocked** — corpus located but unreachable from this environment (see below) |
| B | SRS core (FSRS, ported from AnkiDroid's scheduler logic) | Not started |
| C | Card UI state machine | Not started |
| D | Onboarding / home / library / analysis / settings UI | Not started |
| E | Multi-school integration, exam-date backward planning | Not started |

### Phase A — done this commit

- `pipeline/01_extract_reference_books.py` + `01b_ocr_sparta3.py`: text/OCR
  extraction for all 6 vocab-list PDFs + the phrase book (sokujukugo).
  SPARTA3's font had no text mapping at all — handled via image-render +
  grid-line removal + tesseract OCR, verified page-by-page. Verified against
  the actual attached PDFs (run output in `pipeline/README.md`).
- `pipeline/02_normalize_and_merge.py`, `03_score_vocab.py`: cross-book lemma
  merge (5,255 unique lemmas from the 7 books) and `vocab_scoring_algorithm.txt`
  Step 1 + Step 3 scoring (Step 2 — past-exam boost — blocked, see below). A
  real scoring-methodology gap was found and flagged, not silently patched:
  see `pipeline/README.md` item 2 (advanced-tier books like SPARTA3 distort
  the pure index-percentile baseline).
- `pipeline/04_build_word_families.py`: Word Family grouping (262 families)
  and phrase-to-headword attachment candidates. Spot-checked and found real
  false positives (suffix coincidences) — treated as a review worklist, not
  an authoritative table. See `pipeline/README.md` for why the spec's
  preferred method (reading the source book's own section structure) isn't
  usable with these particular "一覧" list PDFs.
- `pipeline/05_build_word_table.py`: final `vocab_master.json` Word-row
  skeleton (5,255 rows) combining scoring + family data. No Sense/gloss
  content yet — that's original content, authored separately.
- `pipeline/schema.sql`: full DDL for Word/Sense/UserWordState/UserSenseState/
  School/exam-frequency tables.
- `ios/LEXA/Sources/LEXA/Models/*.swift`: matching SwiftData models.

### Known constraints / blockers (see linked READMEs for detail)

1. **Past-exam corpus is unreachable from this environment.** Located at
   Google Drive `英単語LEXA/過去問.zip`, **2.7 GB as a single zip file**.
   This session's network policy blocks direct connections to
   `drive.google.com` (confirmed 403 at the proxy), and the Google Drive
   MCP tool can only return a whole file as base64 — inlining ~3.6 GB of
   base64 text isn't viable regardless of file size limits. **This needs a
   decision from you**: the cleanest fix is to re-share the corpus as an
   already-unzipped Drive folder (individual PDFs can then be listed and
   pulled one at a time, which matches `supplementary_design_spec.md` §4.1's
   own requirement to process the corpus one file at a time anyway) — or
   suggest another way to get it to this session. Blocks
   `vocab_scoring_algorithm.txt` Step 2 (入試特異性ブースト) and all of
   Phase A2/Phase E school-vocabulary generation until resolved.
2. **No Xcode/macOS in this environment** — the iOS app is written but
   unbuilt/unverified. → `ios/README.md`
3. Several product decisions are explicitly undefined in the specs (mastery
   threshold, session-boundary for exclusion hints, sense-tab count limit,
   settings-screen delete behavior, export format, etc.) — all are listed
   with their placeholder values in `card_ui_logic_spec.md` §8,
   `home_screen_design.md` §8, `supplementary_design_spec.md` §3, and in the
   code comments referencing them (`ios/README.md` "Implementation decisions").

## Docs

The four attached specification documents are copied into `docs/` unmodified
for reference. UI mockup images and app icon assets are intentionally **not**
committed here (large binary references only needed during design, not part
of the buildable product) — ask if you need them re-added.
