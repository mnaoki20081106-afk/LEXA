import Foundation
import SwiftData

/// Per-user, per-Sense SRS state (project_overview.txt §45-46: "語義単位の
///習熟度" — e.g. observe's "観察する" can be mastered while "遵守する" is
/// still weak). Same shape as `UserWordState` but scoped one level deeper.
///
/// TBD (card_ui_logic_spec.md §8 item 1): the "定着済み" (mastered) threshold
/// used to decide exclusion-hint eligibility is not defined anywhere in the
/// spec. `masteryThresholdPlaceholder` documents the placeholder value used
/// until product defines the real one — see ios/README.md "Implementation
/// decisions" #2.
@Model
final class UserSenseState {
    var userID: String
    var senseID: String

    var mastery: Double
    var stability: Double?
    var srsDifficulty: Double?
    var dueDate: Date?
    var repetitions: Int
    var lapses: Int
    var lastRating: ReviewRating?

    init(
        userID: String,
        senseID: String,
        mastery: Double = 0.0,
        stability: Double? = nil,
        srsDifficulty: Double? = nil,
        dueDate: Date? = nil,
        repetitions: Int = 0,
        lapses: Int = 0,
        lastRating: ReviewRating? = nil
    ) {
        self.userID = userID
        self.senseID = senseID
        self.mastery = mastery
        self.stability = stability
        self.srsDifficulty = srsDifficulty
        self.dueDate = dueDate
        self.repetitions = repetitions
        self.lapses = lapses
        self.lastRating = lastRating
    }
}

/// PLACEHOLDER (card_ui_logic_spec.md §8 item 1: "定着済み（マスタリー）判定の
/// 閾値" is explicitly undecided). Chosen provisionally as "2 consecutive
/// Good/Easy ratings with no intervening Again" purely so the exclusion-hint
/// UI (card_ui_logic_spec.md §3.3) has something concrete to branch on during
/// Phase C. This is NOT a product decision — flag for review before ship.
enum MasteryThresholdPlaceholder {
    static let minConsecutiveGoodOrEasy = 2
}
