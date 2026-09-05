-- LEXA vocabulary database schema (Phase A: data foundation)
--
-- Source of truth for field-level decisions:
--   1. card_ui_logic_spec.md  §1 (Word / Sense)
--   2. home_screen_design.md  §0 (required_for_common_test / required_for_schools)
--   3. vocab_scoring_algorithm.txt (difficulty_level, source book tracking)
--   4. project_overview.txt   §44-46 (Word / UserWordState / Sense split)
--
-- IMPORTANT (copyright, project_overview.txt §32-35, supplementary_design_spec.md §4.2):
-- This schema stores STATISTICS and ORIGINAL app content only. It never stores
-- verbatim text extracted from a reference book or a past-exam PDF (no book
-- glosses, no exam passages/questions). meaning_ja / example_en / example_ja
-- on `sense` are original content the app team writes, not copied text.

-- ============================================================
-- Word: one row = one flashcard (root word, derived Word-Family
-- member, or a headless phrase/idiom -- see is_phrase below).
-- ============================================================
CREATE TABLE word (
    word_id                 TEXT PRIMARY KEY,      -- e.g. "W000123"
    lemma                   TEXT NOT NULL,          -- "respect" or, for a headless
                                                     -- idiom, the full phrase text
                                                     -- e.g. "at one's wit's end"
    pos_primary             TEXT,                   -- display label, e.g. "動詞"
    etymology               TEXT,                   -- shared across all senses of this Word

    -- Word Family (card_ui_logic_spec.md §1.1 / §4): relationship is stored as
    -- flat fields on Word itself, NOT a separate graph entity. This mirrors the
    -- spec's explicit choice not to build a family "map" UI or unlock logic.
    family_id               TEXT,                   -- NULL if not part of a family
    family_role             TEXT CHECK (family_role IN ('root','derived') OR family_role IS NULL),
    family_of_lemma         TEXT,                    -- parent lemma, for derived badge text

    -- DECISION (not specified in any doc -- see pipeline/README.md "Implementation
    -- decisions" and ios/LEXA README): a headless idiom from 速読英熟語 (e.g.
    -- "at one's wit's end") has no natural single-word head to attach a
    -- kind="pattern" sense to (card_ui_logic_spec.md §5 basis 3: "does it stand
    -- on its own"). We model these as their own independent Word row with
    -- is_phrase = 1, matching project_overview.txt §15 "phrase/熟語の独立レコード化".
    -- Phrases anchored to a real headword (e.g. suppose -> "be supposed to V",
    -- look -> "look like") are NOT separate Word rows; they are a
    -- kind="pattern" Sense on the headword's Word row per card_ui_logic_spec.md §5.
    is_phrase               INTEGER NOT NULL DEFAULT 0,

    -- Curriculum placement (home_screen_design.md §0: exactly two decks,
    -- filter-views over one common Word pool, not separate content sets)
    required_for_common_test INTEGER NOT NULL DEFAULT 0,

    -- Difficulty scoring (vocab_scoring_algorithm.txt §3)
    difficulty_level        REAL,                   -- 0.0-10.0, NULL until scored
    base_score_raw          REAL,                   -- Step 1 output, pre-normalization
    boost_score_raw         REAL,                   -- Step 2 output (exam-specificity boost)
                                                     -- Phase A: always 0.0 / NULL -- see
                                                     -- pipeline/README.md "Deferred: Step 2"

    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which reference books this lemma was found in, and at what index position
-- within that book (needed for vocab_scoring_algorithm.txt Step 1 percentile
-- calculation, and for "既習教材の引き継ぎ" import matching).
CREATE TABLE reference_book_source (
    word_id                 TEXT NOT NULL REFERENCES word(word_id),
    book_code               TEXT NOT NULL,          -- e.g. "sisutan", "target1900"
    index_in_book           INTEGER NOT NULL,       -- 1-based position as printed
    book_total_entries      INTEGER NOT NULL,       -- for percentile = index/total
    PRIMARY KEY (word_id, book_code)
);

-- Per-university/faculty exam-frequency statistics (vocab_scoring_algorithm.txt
-- Step 2 / project_overview.txt §13, §44 exam_frequency / school_profiles).
-- Populated in Phase A2 once the past-exam corpus is processed. Never stores
-- the source passage/question text -- counts and TF-IDF weights only.
CREATE TABLE exam_frequency_stat (
    word_id                 TEXT NOT NULL REFERENCES word(word_id),
    school_id               TEXT NOT NULL,          -- e.g. "keio_ri_kou"
    raw_frequency           INTEGER NOT NULL DEFAULT 0,
    tfidf_score             REAL,
    PRIMARY KEY (word_id, school_id)
);

CREATE TABLE school (
    school_id               TEXT PRIMARY KEY,
    university_name         TEXT NOT NULL,
    faculty_name             TEXT NOT NULL,
    -- exam_date is per-USER (a user enters the concrete sitting date for a
    -- year they are applying), so it lives on user_school, not here.
    required_vocab_computed  INTEGER NOT NULL DEFAULT 0 -- 0 until Phase A2 computes required set
);

CREATE TABLE school_required_word (
    school_id                TEXT NOT NULL REFERENCES school(school_id),
    word_id                  TEXT NOT NULL REFERENCES word(word_id),
    PRIMARY KEY (school_id, word_id)
);

-- ============================================================
-- Sense: language content for one Word. SRS state lives in
-- user_sense_state, NOT here (project_overview.txt §44/§45:
-- Word content and per-user state are always separate tables).
-- ============================================================
CREATE TABLE sense (
    sense_id                 TEXT PRIMARY KEY,
    word_id                  TEXT NOT NULL REFERENCES word(word_id),
    sense_order               INTEGER NOT NULL,      -- display/definition order within the Word
    kind                      TEXT NOT NULL CHECK (kind IN ('meaning','pattern')),
    tag                       TEXT,                  -- e.g. "【他動】", "【熟】"
    pos_label                 TEXT,                  -- e.g. "動詞", "熟語"
    meaning_ja                TEXT NOT NULL,          -- ORIGINAL app content (never copied from a book)
    pattern_front             TEXT,                  -- only for kind='pattern', e.g. "be supposed to V"
    example_en                TEXT NOT NULL,          -- ORIGINAL example sentence
    example_ja                TEXT NOT NULL
);

-- ============================================================
-- Per-user state. One row per (user, word) -- shared across the
-- common-test deck and the school deck (home_screen_design.md §0:
-- "学習履歴は1つ"). One row per (user, sense) for sense-level mastery
-- (project_overview.txt §45-46).
-- ============================================================
CREATE TABLE user_word_state (
    user_id                   TEXT NOT NULL,
    word_id                   TEXT NOT NULL REFERENCES word(word_id),
    mastery                   REAL NOT NULL DEFAULT 0.0,
    stability                 REAL,                   -- FSRS state, NULL until first review; see ios SRS module
    difficulty                REAL,                   -- FSRS per-card difficulty (distinct from word.difficulty_level)
    due_date                  TEXT,
    repetitions                INTEGER NOT NULL DEFAULT 0,
    lapses                     INTEGER NOT NULL DEFAULT 0,
    last_rating                TEXT CHECK (last_rating IN ('again','hard','good','easy') OR last_rating IS NULL),
    -- "既習候補" seed vs. real review history (project_overview.txt §4-5, §25)
    imported_from_book_code    TEXT,                  -- non-NULL only for a state created by onboarding import
    is_imported_candidate      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, word_id)
);

CREATE TABLE user_sense_state (
    user_id                    TEXT NOT NULL,
    sense_id                   TEXT NOT NULL REFERENCES sense(sense_id),
    mastery                    REAL NOT NULL DEFAULT 0.0,
    stability                  REAL,
    difficulty                 REAL,
    due_date                   TEXT,
    repetitions                 INTEGER NOT NULL DEFAULT 0,
    lapses                      INTEGER NOT NULL DEFAULT 0,
    last_rating                 TEXT CHECK (last_rating IN ('again','hard','good','easy') OR last_rating IS NULL),
    PRIMARY KEY (user_id, sense_id)
);

CREATE TABLE user_school (
    user_id                     TEXT NOT NULL,
    school_id                   TEXT NOT NULL REFERENCES school(school_id),
    exam_date                   TEXT,                 -- user-entered, never auto-guessed (home_screen_design.md §2/§7)
    added_order                 INTEGER NOT NULL,
    PRIMARY KEY (user_id, school_id)
);

CREATE TABLE user_profile (
    user_id                      TEXT PRIMARY KEY,
    grade                        TEXT CHECK (grade IN ('hs1','hs2','hs3','graduate') OR grade IS NULL),
    is_subscribed                INTEGER NOT NULL DEFAULT 0,
    notifications_enabled        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE user_reference_book (
    user_id                       TEXT NOT NULL,
    book_code                     TEXT NOT NULL,
    PRIMARY KEY (user_id, book_code)
);
