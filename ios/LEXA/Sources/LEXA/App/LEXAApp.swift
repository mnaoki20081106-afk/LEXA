import SwiftUI
import SwiftData

@main
struct LEXAApp: App {
    let modelContainer: ModelContainer = {
        let schema = Schema([
            Word.self,
            Sense.self,
            UserWordState.self,
            UserSenseState.self,
            School.self,
            UserSchool.self,
            UserProfile.self,
        ])
        let configuration = ModelConfiguration(schema: schema)
        do {
            return try ModelContainer(for: schema, configurations: [configuration])
        } catch {
            fatalError("Failed to create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            // Placeholder root view — onboarding/home/library/analysis/settings
            // are Phase D. This just proves the SwiftData stack boots.
            Text("LEXA — Phase A data foundation")
        }
        .modelContainer(modelContainer)
    }
}
