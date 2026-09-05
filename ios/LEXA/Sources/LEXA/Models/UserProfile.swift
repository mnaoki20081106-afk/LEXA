import Foundation
import SwiftData

/// Single-device user profile (no server account in this phase).
/// home_screen_design.md §2 Step 3: grade is the one onboarding field that
/// cannot be skipped, because it gates the common-test countdown (§2.1).
@Model
final class UserProfile {
    @Attribute(.unique) var userID: String
    var grade: Grade?
    var isSubscribed: Bool
    var notificationsEnabled: Bool
    /// Reference books the user selected during onboarding / settings
    /// (project_overview.txt §7, home_screen_design.md §2 Step 4). Drives the
    /// "既習教材の引き継ぎ" import — matched against `Word.referenceBookCodes`.
    var selectedReferenceBookCodes: [String]

    init(
        userID: String,
        grade: Grade? = nil,
        isSubscribed: Bool = false,
        notificationsEnabled: Bool = true,
        selectedReferenceBookCodes: [String] = []
    ) {
        self.userID = userID
        self.grade = grade
        self.isSubscribed = isSubscribed
        self.notificationsEnabled = notificationsEnabled
        self.selectedReferenceBookCodes = selectedReferenceBookCodes
    }
}

enum Grade: String, Codable {
    case highSchool1 = "hs1"
    case highSchool2 = "hs2"
    case highSchool3 = "hs3"
    case graduate     // 既卒（浪人）— home_screen_design.md §2 Step 3

    /// home_screen_design.md §2.1: only these two grades see the common-test
    /// countdown, since only they are sitting the *next* confirmed exam date.
    var isEligibleForCommonTestCountdown: Bool {
        self == .highSchool3 || self == .graduate
    }
}
