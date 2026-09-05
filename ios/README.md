# LEXA iOS app

SwiftUI + SwiftData, iOS 17+, MVVM. Built and developed from a Linux cloud
session with no Xcode/macOS available — see "Build environment" below for
what that means in practice.

## Build environment

This session cannot run `xcodebuild`, boot the iOS Simulator, or open Xcode
— there is no macOS host here. Two consequences:

1. **No `.xcodeproj` is checked in.** A hand-edited `.pbxproj` risks silent
   corruption with no way to verify it here. Instead, `project.yml`
   ([XcodeGen](https://github.com/yonaskolb/XcodeGen) format) describes the
   target, and Swift source lives in a plain `Sources/` tree. On a Mac:
   ```
   brew install xcodegen
   cd ios/LEXA
   xcodegen generate
   open LEXA.xcodeproj
   ```
2. **Nothing in this phase has been compiled or run in a simulator.** The
   Swift below is written carefully against SwiftData/SwiftUI APIs but is
   unverified until someone with a Mac generates the project and builds it.
   `supplementary_design_spec.md` §4.4 anticipates exactly this split
   (pipeline/data work in the cloud, actual iOS build on a Mac later), so
   this isn't a surprise deviation — flagging it here so it's explicit per
   commit rather than assumed.

## What's implemented (Phase A)

`Sources/LEXA/Models/` — the SwiftData schema: `Word`, `Sense`,
`UserWordState`, `UserSenseState`, `School`/`UserSchool`, `UserProfile`.
Field-level source is cited in each file's doc comments (card_ui_logic_spec.md
§1, project_overview.txt §44-46, home_screen_design.md §0).

Not implemented yet: onboarding/home/library/analysis/settings UI (Phase D),
SRS scheduling (Phase B), card UI state machine (Phase C), importing the
pipeline's `vocab_scored.json` into the SwiftData store.

## Implementation decisions (not specified in any attached doc)

Per the project brief's instruction to flag, not guess, undecided points:

1. **Headless phrases are independent `Word` rows.** card_ui_logic_spec.md §5
   only covers phrases anchored to a real headword (suppose → "be supposed to
   V"). An idiom like "at one's wit's end" (from 速読英熟語) has no headword
   to attach a `kind: .pattern` Sense to. Modeled as its own `Word` with
   `isPhrase = true`, per project_overview.txt §15's instruction that
   phrases get independent records. See `Word.swift` doc comment.
2. **Mastery threshold placeholder**: card_ui_logic_spec.md §8 item 1 leaves
   the "定着済み" threshold undefined. Provisionally: 2 consecutive Good/Easy
   ratings with no intervening Again (`MasteryThresholdPlaceholder` in
   `UserSenseState.swift`). This gates the exclusion-hint UI in Phase C and
   must be revisited before ship.
3. **School priority ordering**: home_screen_design.md §8 leaves undecided
   how multiple registered schools are prioritized when allocating daily
   review counts. Placeholder: registration order (`UserSchool.addedOrder`).
4. **Bundle ID** (`com.lexa.app.LEXA` in `project.yml`) is a placeholder —
   not specified anywhere. Change before archiving.

## Deliberately not built

card_ui_logic_spec.md §7 lists features explicitly rejected during design
(Word Family roadmap bar, mastery-gated derived-word unlock, "confusable
construction" comparison cards, listing multiple collocations per sense).
None of these exist in this codebase and none should be added later without
a spec change.
