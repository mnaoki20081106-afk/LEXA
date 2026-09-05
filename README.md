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
| A2 | Past-exam corpus analysis (TF-IDF exam-specificity boost) | Not started — corpus located, not yet downloaded/inspected (see below) |
| B | SRS core (FSRS, ported from AnkiDroid's scheduler logic) | Not started |
| C | Card UI state machine | Not started |
| D | Onboarding / home / library / analysis / settings UI | Not started |
| E | Multi-school integration, exam-date backward planning | Not started |

### Phase A — done this commit

- `pipeline/01_extract_reference_books.py`: text extraction for 5 of 6 vocab
  list PDFs + the phrase book (sokujukugo). Verified against the actual
  attached PDFs (run output in `pipeline/README.md`).
- `pipeline/02_normalize_and_merge.py`, `03_score_vocab.py`: cross-book lemma
  merge (4,675 unique lemmas from the 6 books) and `vocab_scoring_algorithm.txt`
  Step 1 + Step 3 scoring (Step 2 — past-exam boost — deferred, see below).
- `pipeline/schema.sql`: full DDL for Word/Sense/UserWordState/UserSenseState/
  School/exam-frequency tables.
- `ios/LEXA/Sources/LEXA/Models/*.swift`: matching SwiftData models.

### Known constraints / deferred work (see linked READMEs for detail)

1. **SPARTA3 vocab PDF** (`大学入試英単語 SPARTA3 一覧.pdf`) uses a subsetted
   font with no text mapping — needs OCR, not started. → `pipeline/README.md`
2. **Past-exam corpus**: located at Google Drive `英単語LEXA/過去問.zip`,
   **2.7 GB as a single zip file**. Internal folder/naming structure has not
   been inspected yet (downloading/unzipping a file this size is a
   deliberate, separate step — not something to do as a side effect of
   another script). This blocks `vocab_scoring_algorithm.txt` Step 2 (入試
   特異性ブースト) and the whole of Phase A2/Phase E school-vocabulary
   generation. **Next concrete step, reported rather than assumed per the
   project brief's own instruction.**
3. **No Xcode/macOS in this environment** — the iOS app is written but
   unbuilt/unverified. → `ios/README.md`
4. Several product decisions are explicitly undefined in the specs (mastery
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
