import Foundation
import SwiftData

/// One flashcard. Root words, each independent Word-Family derived form
/// (respect / respectable / respectful / respectfully), and headless idioms
/// from the phrase book are all rows here — see `isPhrase` below.
///
/// Source of truth: card_ui_logic_spec.md §1.1, project_overview.txt §44-46.
/// `Word` holds only content + classification. Per-user SRS state lives
/// entirely in `UserWordState` / `UserSenseState` (project_overview.txt §44:
/// "WordデータとUserのSRS状態は分離する") — never add mutable review state
/// to this model.
@Model
final class Word {
    @Attribute(.unique) var wordID: String
    var lemma: String
    var posPrimary: String?

    /// Shared across every sense of this word (card_ui_logic_spec.md §1.1, §6).
    var etymology: String?

    // MARK: Word Family (card_ui_logic_spec.md §1.1, §4)
    // Modeled as flat fields on Word itself, not a separate graph entity —
    // this mirrors the spec's explicit rejection of a family "map" UI or
    // mastery-gated unlock (§4.3, §7).
    var familyID: String?
    var familyRole: FamilyRole?
    var familyOfLemma: String?

    /// DECISION (undocumented in any spec — see ios/README.md "Implementation
    /// decisions" #1): a headless idiom from 速読英熟語 (e.g. "at one's wit's
    /// end") has no headword to attach a `kind: .pattern` Sense to
    /// (card_ui_logic_spec.md §5, basis 3: does it stand on its own). Those
    /// become their own independent `Word` row with `isPhrase = true`, per
    /// project_overview.txt §15 ("phrase/熟語の独立レコード化"). A phrase
    /// anchored to a real headword (suppose → "be supposed to V", look →
    /// "look like") is NOT a separate Word; it's a `kind: .pattern` Sense on
    /// the headword's Word (card_ui_logic_spec.md §5).
    var isPhrase: Bool

    /// home_screen_design.md §0: exactly two decks — common-test (free) and
    /// school (paid) — as filter views over one shared Word pool.
    var requiredForCommonTest: Bool
    /// School IDs this word is required for. Empty when only needed for the
    /// common test. Kept even when a word is required by every registered
    /// school (project_overview.txt §11: 固有語彙 is preserved, not merged away).
    var requiredForSchoolIDs: [String]

    /// vocab_scoring_algorithm.txt §3. nil until the scoring pipeline has run.
    var difficultyLevel: Double?
    var baseScoreRaw: Double?
    /// Step 2 (past-exam TF-IDF boost) is not implemented yet — see
    /// pipeline/README.md "Deferred: Step 2". Always 0 until then.
    var boostScoreRaw: Double?

    /// Which reference books this lemma appeared in (pipeline output),
    /// used for the "既習教材の引き継ぎ" onboarding import (project_overview.txt §7-9).
    var referenceBookCodes: [String]

    @Relationship(deleteRule: .cascade, inverse: \Sense.word)
    var senses: [Sense] = []

    init(
        wordID: String,
        lemma: String,
        posPrimary: String? = nil,
        etymology: String? = nil,
        familyID: String? = nil,
        familyRole: FamilyRole? = nil,
        familyOfLemma: String? = nil,
        isPhrase: Bool = false,
        requiredForCommonTest: Bool = false,
        requiredForSchoolIDs: [String] = [],
        difficultyLevel: Double? = nil,
        baseScoreRaw: Double? = nil,
        boostScoreRaw: Double? = nil,
        referenceBookCodes: [String] = []
    ) {
        self.wordID = wordID
        self.lemma = lemma
        self.posPrimary = posPrimary
        self.etymology = etymology
        self.familyID = familyID
        self.familyRole = familyRole
        self.familyOfLemma = familyOfLemma
        self.isPhrase = isPhrase
        self.requiredForCommonTest = requiredForCommonTest
        self.requiredForSchoolIDs = requiredForSchoolIDs
        self.difficultyLevel = difficultyLevel
        self.baseScoreRaw = baseScoreRaw
        self.boostScoreRaw = boostScoreRaw
        self.referenceBookCodes = referenceBookCodes
    }
}

enum FamilyRole: String, Codable {
    case root
    case derived
}
