import Foundation
import SwiftData

/// A university/faculty a user can register as a target (project_overview.txt
/// §10-12). Required-vocabulary computation (which Words belong to this
/// school) is a Phase A2/B pipeline output, not user data — this model only
/// holds identity; the school↔word relationship lives on `Word.requiredForSchoolIDs`.
@Model
final class School {
    @Attribute(.unique) var schoolID: String
    var universityName: String
    var facultyName: String

    init(schoolID: String, universityName: String, facultyName: String) {
        self.schoolID = schoolID
        self.universityName = universityName
        self.facultyName = facultyName
    }
}

/// A user's registration of a `School`, including their own exam date.
/// home_screen_design.md §2 Step 6 / §7: exam dates are always user-entered,
/// never auto-guessed, since they vary by faculty and by year.
@Model
final class UserSchool {
    var userID: String
    var schoolID: String
    var examDate: Date?
    /// Registration order — home_screen_design.md §8 leaves the school-
    /// priority ordering for review count allocation undecided; order-added
    /// is the placeholder tiebreaker (see ios/README.md "Implementation
    /// decisions" #3).
    var addedOrder: Int

    init(userID: String, schoolID: String, examDate: Date? = nil, addedOrder: Int) {
        self.userID = userID
        self.schoolID = schoolID
        self.examDate = examDate
        self.addedOrder = addedOrder
    }
}
