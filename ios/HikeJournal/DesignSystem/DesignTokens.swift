import SwiftUI
import UIKit

enum HikeJournalTheme {
    static let moss = adaptive(light: 0x183A2D, dark: 0xB7C8B5)
    static let mossSurface = adaptive(light: 0x315844, dark: 0x233C31)
    static let fern = adaptive(light: 0x76916D, dark: 0x91AA88)
    static let trail = adaptive(light: 0xD17D42, dark: 0xE69961)
    static let trailText = adaptive(light: 0x9B4D27, dark: 0xF2B184)
    static let parchment = adaptive(light: 0xF4F0E5, dark: 0x141A16)
    static let paper = adaptive(light: 0xFFFCF3, dark: 0x1B241E)
    static let ink = adaptive(light: 0x1D241F, dark: 0xF5F0E4)
    static let inkMuted = adaptive(light: 0x526057, dark: 0xB9C3BA)
    static let line = adaptive(light: 0xD8D3C7, dark: 0x3B463F)
    static let lichen = adaptive(light: 0xDCE5D6, dark: 0x2B4033)
    static let error = adaptive(light: 0x9E3F34, dark: 0xF09587)

    static func display(_ size: CGFloat, relativeTo style: Font.TextStyle = .largeTitle) -> Font {
        .custom("CormorantGaramond-SemiBold", size: size, relativeTo: style)
    }

    static func body(_ size: CGFloat = 17, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("SourceSans3-Roman_Regular", size: size, relativeTo: style)
    }

    static func bodyMedium(_ size: CGFloat = 16, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("SourceSans3-Roman_Medium", size: size, relativeTo: style)
    }

    static func label(_ size: CGFloat = 13, relativeTo style: Font.TextStyle = .caption) -> Font {
        .custom("SourceSans3-Roman_SemiBold", size: size, relativeTo: style)
    }

    private static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

enum HikeJournalSpacing {
    static let compact: CGFloat = 8
    static let standard: CGFloat = 16
    static let roomy: CGFloat = 24
    static let section: CGFloat = 36
}

private extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}

struct ParchmentBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [HikeJournalTheme.paper, HikeJournalTheme.parchment],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            ContourPattern(color: HikeJournalTheme.moss.opacity(0.055))
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

struct TrailButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.paper)
            .frame(maxWidth: .infinity, minHeight: 52)
            .padding(.horizontal, 18)
            .background(HikeJournalTheme.moss, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.975 : 1)
            .opacity(configuration.isPressed ? 0.88 : 1)
            .animation(.snappy(duration: 0.18), value: configuration.isPressed)
    }
}

private struct ContourPattern: View {
    let color: Color

    var body: some View {
        Canvas { context, size in
            for index in 0..<9 {
                var path = Path()
                let baseline = size.height * (CGFloat(index) / 8) - 18
                path.move(to: CGPoint(x: -20, y: baseline))
                for step in 0...20 {
                    let x = size.width * CGFloat(step) / 20
                    let wave = sin((CGFloat(step) * 0.62) + CGFloat(index) * 0.9) * 12
                    path.addLine(to: CGPoint(x: x, y: baseline + wave))
                }
                context.stroke(path, with: .color(color), lineWidth: 0.8)
            }
        }
    }
}
