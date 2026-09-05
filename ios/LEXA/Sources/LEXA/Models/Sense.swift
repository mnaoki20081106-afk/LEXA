import Foundation
import SwiftData

/// A single word-sense or grammar pattern belonging to a `Word`.
/// card_ui_logic_spec.md §1.2: front/back display and SRS are both scoped to
/// this unit, not the whole Word — each sense has its own `UserSenseState`.
@Model
final class Sense {
    @Attribute(.unique) var senseID: String
    var word: Word?
    /// Display/definition order within the parent Word.
    var senseOrder: Int

    /// card_ui_logic_spec.md §1.2 — drives front/back rendering branches.
    /// `.meaning`: a word-sense (observe: 観察する/遵守する/祝う).
    /// `.pattern`: a grammar/idiom construction tied to this headword
    /// (suppose: "be supposed to V") — NOT rendered as a separate Word card.
    var kind: SenseKind

    /// Bracket tag shown on the back, e.g. "【他動】", "【熟】".
    var tag: String?
    /// Wider back-of-card label, e.g. "動詞", "熟語".
    var posLabel: String?

    /// Original app-authored Japanese gloss (never copied from a reference
    /// book — see pipeline/README.md copyright section).
    var meaningJA: String

    /// Only set when `kind == .pattern`. The construction shown verbatim on
    /// the card front, e.g. "Supposing (that) ~".
    var patternFront: String?

    /// Exactly one example sentence per sense (card_ui_logic_spec.md §1.2,
    /// §7: no additional collocation/example lists — that was explicitly
    /// rejected).
    var exampleEN: String
    var exampleJA: String

    init(
        senseID: String,
        senseOrder: Int,
        kind: SenseKind,
        tag: String? = nil,
        posLabel: String? = nil,
        meaningJA: String,
        patternFront: String? = nil,
        exampleEN: String,
        exampleJA: String
    ) {
        self.senseID = senseID
        self.senseOrder = senseOrder
        self.kind = kind
        self.tag = tag
        self.posLabel = posLabel
        self.meaningJA = meaningJA
        self.patternFront = patternFront
        self.exampleEN = exampleEN
        self.exampleJA = exampleJA
    }
}

enum SenseKind: String, Codable {
    case meaning
    case pattern
}
