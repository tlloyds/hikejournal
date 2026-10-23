import Combine
import CoreText
import Foundation
import SwiftUI
import UIKit

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

private enum SafetyReadingPalette {
    static let surface = color(light: 0xFFFFFF, dark: 0x131B16)
    static let surfaceEnd = color(light: 0xF4F6F0, dark: 0x1A241D)
    static let ink = color(light: 0x101A14, dark: 0xF4F8F0)
    static let link = color(light: 0x164D33, dark: 0xC3E7CC)
    static let button = color(light: 0x183A2D, dark: 0xC4DEC8)
    static let buttonInk = color(light: 0xFFFFFF, dark: 0x122018)
    static let disabledButton = color(light: 0xD9E0D7, dark: 0x344037)
    static let disabledButtonInk = color(light: 0x344237, dark: 0xEFF4EB)

    private static func color(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            let value = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((value >> 16) & 0xFF) / 255,
                           green: CGFloat((value >> 8) & 0xFF) / 255,
                           blue: CGFloat(value & 0xFF) / 255, alpha: 1)
        })
    }
}

private enum SafetyReadingTypography {
    // Both bundled fonts default to a light variation. Select the actual wght
    // axis, while callers supply Dynamic Type-scaled sizes.
    static func body(_ size: CGFloat, weight: CGFloat = 500) -> Font {
        font("SourceSans3-Roman", size: size, weight: weight)
    }

    static func display(_ size: CGFloat, weight: CGFloat = 600) -> Font {
        font("CormorantGaramond-Light", size: size, weight: weight)
    }

    private static func font(_ name: String, size: CGFloat, weight: CGFloat) -> Font {
        let descriptor = CTFontDescriptorCreateWithNameAndSize(name as CFString, size)
        let weighted = CTFontDescriptorCreateCopyWithVariation(descriptor, NSNumber(value: 0x77676874), weight)
        return Font(CTFontCreateWithFontDescriptor(weighted, size, nil))
    }
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
    @ScaledMetric(relativeTo: .body) private var bodySize: CGFloat = 18
    @ScaledMetric(relativeTo: .headline) private var labelSize: CGFloat = 17
    @ScaledMetric(relativeTo: .largeTitle) private var brandSize: CGFloat = 40
    @ScaledMetric(relativeTo: .title) private var titleSize: CGFloat = 30
    @Environment(\.legibilityWeight) private var legibilityWeight

    var body: some View {
        ZStack {
            LinearGradient(colors: [SafetyReadingPalette.surface, SafetyReadingPalette.surfaceEnd],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("HikeJournal")
                        .font(SafetyReadingTypography.display(brandSize, weight: legibilityWeight == .bold ? 700 : 600))
                        .foregroundStyle(HikeJournalTheme.moss)
                    Text(IdentificationSafetyNotice.title)
                        .font(SafetyReadingTypography.display(titleSize, weight: legibilityWeight == .bold ? 700 : 600))
                        .accessibilityAddTraits(.isHeader)
                    Text(IdentificationSafetyNotice.affiliation)
                    Text(IdentificationSafetyNotice.accuracy)
                    Text(IdentificationSafetyNotice.verification)
                    Text(IdentificationSafetyNotice.consumption)
                        .font(SafetyReadingTypography.body(bodySize, weight: legibilityWeight == .bold ? 700 : 600))
                    Text(IdentificationSafetyNotice.purpose)
                    Link("About iNaturalist suggestions", destination: IdentificationSafetyNotice.guidanceURL)
                        .font(SafetyReadingTypography.body(labelSize, weight: 600))
                        .foregroundStyle(SafetyReadingPalette.link)
                        .underline()
                    if onAcknowledge != nil {
                        Toggle(IdentificationSafetyNotice.acknowledgment, isOn: $understood)
                            .accessibilityIdentifier("identificationSafetyAcknowledgment")
                    }
                }
                .font(SafetyReadingTypography.body(bodySize, weight: legibilityWeight == .bold ? 600 : 500))
                .lineSpacing(5)
                .foregroundStyle(SafetyReadingPalette.ink)
                .frame(maxWidth: 640, alignment: .leading)
                .padding(24)
                .frame(maxWidth: .infinity, alignment: .center)
            }
        }
        .safeAreaInset(edge: .bottom) {
            if let onAcknowledge {
                Button("Acknowledge and continue", action: onAcknowledge)
                    .buttonStyle(SafetyReadingButtonStyle())
                    .disabled(!understood)
                    .frame(maxWidth: 640)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .frame(maxWidth: .infinity)
                    .background(SafetyReadingPalette.surface)
            }
        }
    }
}

struct IdentificationSafetyReminder: View {
    var color: Color = SafetyReadingPalette.ink
    @ScaledMetric(relativeTo: .callout) private var fontSize: CGFloat = 15
    @Environment(\.legibilityWeight) private var legibilityWeight

    var body: some View {
        Text(IdentificationSafetyNotice.reminder)
            .font(SafetyReadingTypography.body(fontSize, weight: legibilityWeight == .bold ? 600 : 500))
            .lineSpacing(4)
            .foregroundStyle(color)
    }
}

private struct SafetyReadingButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ScaledMetric(relativeTo: .headline) private var labelSize: CGFloat = 17

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(SafetyReadingTypography.body(labelSize, weight: 600))
            .multilineTextAlignment(.center)
            .foregroundStyle(isEnabled ? SafetyReadingPalette.buttonInk : SafetyReadingPalette.disabledButtonInk)
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity, minHeight: 56)
            .background(isEnabled ? SafetyReadingPalette.button : SafetyReadingPalette.disabledButton,
                        in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .scaleEffect(reduceMotion || !configuration.isPressed ? 1 : 0.985)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: configuration.isPressed)
    }
}
