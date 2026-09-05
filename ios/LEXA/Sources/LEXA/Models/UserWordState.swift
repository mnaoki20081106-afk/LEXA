import Foundation
import SwiftData

/// Per-user, per-Word SRS state. Exactly one row per (user, word) even when
/// the word is required by both the common-test deck and the school deck —
/// home_screen_design.md §0: "学習履歴は1つ". Reviewing it in either deck
/// updates the same state, so it is never re-introduced as a new card in
/// the other deck.
///
/// project_overview.txt §4-5, §25: a row created from onboarding import
/// ("既習教材の引き継ぎ") is a *candidate* seed, never treated as proof of
/// mastery — `isImportedCandidate` distinguishes that from a state produced
/// by real in-app review.
@Model
final class UserWordState {
    var userID: String
    var wordID: String

    var mastery: Double
    /// FSRS stability/difficulty — nil until the first real review.
    /// Note: distinct from `Word.difficultyLevel` (vocab_scoring_algorithm.txt's
    /// static 0-10 lemma difficulty), this is the FSRS per-user/per-card value.
    var stability: Double?
    var srsDifficulty: Double?
    var dueDate: Date?
    var repetitions: Int
    var lapses: Int
    var lastRating: ReviewRating?

    var isImportedCandidate: Bool
    var importedFromBookCode: String?

    init(
        userID: String,
        wordID: String,
        mastery: Double = 0.0,
        stability: Double? = nil,
        srsDifficulty: Double? = nil,
        dueDate: Date? = nil,
        repetitions: Int = 0,
        lapses: Int = 0,
        lastRating: ReviewRating? = nil,
        isImportedCandidate: Bool = false,
        importedFromBookCode: String? = nil
    ) {
        self.userID = userID
        self.wordID = wordID
        self.mastery = mastery
        self.stability = stability
        self.srsDifficulty = srsDifficulty
        self.dueDate = dueDate
        self.repetitions = repetitions
        self.lapses = lapses
        self.lastRating = lastRating
        self.isImportedCandidate = isImportedCandidate
        self.importedFromBookCode = importedFromBookCode
    }
}

enum ReviewRating: String, Codable {
    case again
    case hard
    case good
    case easy
}
