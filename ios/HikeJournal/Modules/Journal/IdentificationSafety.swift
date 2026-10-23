import Combine
import Foundation
import SwiftUI

@MainActor
final class IdentificationSafetyStore: ObservableObject {
    nonisolated static let noticeVersion = 1
    nonisolated static let versionKey = "identificationSafety.acknowledgedNoticeVersion"
    @Published private(set) var hasAcknowledged: Bool
    private let defaults: UserDefaults
    private let requiredNoticeVersion: Int

    init(defaults: UserDefaults, requiredNoticeVersion: Int = IdentificationSafetyStore.noticeVersion) {
        self.defaults = defaults
        self.requiredNoticeVersion = requiredNoticeVersion
        hasAcknowledged = defaults.integer(forKey: Self.versionKey) >= requiredNoticeVersion
    }

    func acknowledge() {
        defaults.set(requiredNoticeVersion, forKey: Self.versionKey)
        hasAcknowledged = true
    }
}

enum IdentificationSafetyNotice {
    static let title = "Identification safety"
    static let affiliation = "HikeJournal is an independent app. It is not an official iNaturalist app or channel, and is not affiliated with or endorsed by iNaturalist."
    static let accuracy = "Identifications from photos, automated suggestions, community observations, and saved or confirmed labels may be incomplete or wrong. A confidence score or a confirmed label is not a guarantee."
    static let verification = "Treat every identification as a starting point for learning. Verify it independently with a qualified local expert and reliable field references."
    static let consumption = "Never eat, taste, prepare food or drink from, or use any wild organism based on an identification shown in HikeJournal. Do not use the app to decide whether an organism is edible, non-toxic, medicinal, or safe to touch or handle."
    static let purpose = "HikeJournal is for nature journaling and education. It is not a foraging, medical, or safety-advice service."
    static let acknowledgment = "I understand these limits and will not use app identifications to make consumption or safety decisions."
    static let reminder = "IDs may be wrong, even when marked confirmed. Verify independently with a qualified expert. Never use an app ID to decide what to eat or what is safe to touch or use."
    static let guidanceURL = URL(string: "https://help.inaturalist.org/en/support/solutions/articles/151000170369-why-can-t-computer-vision-identify-my-photo-correctly-")!
}

struct IdentificationSafetyGate<Content: View>: View {
    @ObservedObject var store: IdentificationSafetyStore
    @ViewBuilder var content: () -> Content

    var body: some View {
        if store.hasAcknowledged {
            content()
        } else {
            IdentificationSafetyView(onAcknowledge: store.acknowledge)
        }
    }
}

struct IdentificationSafetyView: View {
    var onAcknowledge: (() -> Void)? = nil
    @State private var understood = false

    var body: some View {
        ZStack {
            ParchmentBackground()
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("HikeJournal")
                        .font(HikeJournalTheme.display(40, relativeTo: .largeTitle))
                        .foregroundStyle(HikeJournalTheme.moss)
                    Text(IdentificationSafetyNotice.title)
                        .font(HikeJournalTheme.display(30, relativeTo: .title))
                        .accessibilityAddTraits(.isHeader)
                    Text(IdentificationSafetyNotice.affiliation)
                    Text(IdentificationSafetyNotice.accuracy)
                    Text(IdentificationSafetyNotice.verification)
                    Text(IdentificationSafetyNotice.consumption)
                    Text(IdentificationSafetyNotice.purpose)
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                    Link("About iNaturalist suggestions", destination: IdentificationSafetyNotice.guidanceURL)
                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                    if onAcknowledge != nil {
                        Toggle(IdentificationSafetyNotice.acknowledgment, isOn: $understood)
                            .accessibilityIdentifier("identificationSafetyAcknowledgment")
                    }
                }
                .font(HikeJournalTheme.body(17))
                .foregroundStyle(HikeJournalTheme.ink)
                .padding(24)
            }
        }
        .safeAreaInset(edge: .bottom) {
            if let onAcknowledge {
                Button("Acknowledge and continue", action: onAcknowledge)
                    .buttonStyle(TrailButtonStyle())
                    .disabled(!understood)
                    .opacity(understood ? 1 : 0.45)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(HikeJournalTheme.paper)
            }
        }
    }
}

struct IdentificationSafetyReminder: View {
    var color: Color = HikeJournalTheme.inkMuted

    var body: some View {
        Text(IdentificationSafetyNotice.reminder)
            .font(HikeJournalTheme.body(13))
            .foregroundStyle(color)
    }
}
