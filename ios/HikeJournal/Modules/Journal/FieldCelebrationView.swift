import HikeJournalDomain
import SwiftUI

struct FieldCelebrationView: View {
    let celebration: FieldCelebration
    let dismiss: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var revealed = false
    @State private var orbit = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.06, green: 0.16, blue: 0.12), Color(red: 0.19, green: 0.35, blue: 0.27)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            CelebrationRings(progress: orbit ? 1 : 0)
                .opacity(0.45)
                .ignoresSafeArea()
                .accessibilityHidden(true)

            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("HIKEJOURNAL")
                        .font(HikeJournalTheme.display(44, relativeTo: .largeTitle))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                        .accessibilityAddTraits(.isHeader)
                    Text(celebration.eyebrow)
                        .font(HikeJournalTheme.label(12))
                        .tracking(1.7)
                        .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                        .padding(.top, 4)

                    if let image = celebration.imageUrls.first, !image.isEmpty {
                        JournalRemoteImage(urlString: image, fallback: "leaf.fill")
                            .frame(height: 285)
                            .clipped()
                            .overlay(alignment: .bottom) {
                                LinearGradient(
                                    colors: [.clear, Color(red: 0.06, green: 0.16, blue: 0.12).opacity(0.72)],
                                    startPoint: .center,
                                    endPoint: .bottom
                                )
                                .frame(height: 120)
                            }
                            .padding(.top, 22)
                    } else {
                        Image(systemName: symbol)
                            .font(.system(size: 75, weight: .ultraLight))
                            .foregroundStyle(Color(red: 0.95, green: 0.60, blue: 0.34))
                            .frame(maxWidth: .infinity, minHeight: 190)
                            .padding(.top, 10)
                            .accessibilityHidden(true)
                    }

                    Text(celebration.title)
                        .font(HikeJournalTheme.display(46, relativeTo: .largeTitle))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 22)
                    Text(celebration.detail)
                        .font(HikeJournalTheme.body(18))
                        .foregroundStyle(Color(red: 0.80, green: 0.85, blue: 0.81))
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 8)

                    if !celebration.highlights.isEmpty {
                        Divider().overlay(.white.opacity(0.2)).padding(.vertical, 23)
                        HStack(alignment: .top, spacing: 0) {
                            ForEach(Array(celebration.highlights.enumerated()), id: \.offset) { index, highlight in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(highlight.value)
                                        .font(HikeJournalTheme.display(31, relativeTo: .title))
                                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                                    Text(highlight.label.uppercased())
                                        .font(HikeJournalTheme.label(10))
                                        .tracking(0.9)
                                        .foregroundStyle(Color(red: 0.72, green: 0.79, blue: 0.74))
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                if index < celebration.highlights.count - 1 {
                                    Divider().overlay(.white.opacity(0.16)).padding(.horizontal, 9)
                                }
                            }
                        }
                    }

                    if let badgeTitle = celebration.badgeTitle {
                        Label(badgeTitle, systemImage: "medal.fill")
                            .font(HikeJournalTheme.label(18, relativeTo: .headline))
                            .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                            .padding(.top, 26)
                    }
                    if let badgeProgress = celebration.badgeProgress {
                        Text(badgeProgress)
                            .font(HikeJournalTheme.body(14))
                            .foregroundStyle(Color(red: 0.76, green: 0.82, blue: 0.77))
                            .padding(.top, 3)
                    }

                    Button(celebration.actionLabel, action: dismiss)
                        .buttonStyle(TrailButtonStyle())
                        .padding(.top, 30)
                }
                .padding(.horizontal, 24)
                .padding(.top, 24)
                .padding(.bottom, 40)
                .opacity(revealed ? 1 : 0)
                .offset(y: revealed || reduceMotion ? 0 : 18)
            }
            .scrollIndicators(.hidden)
        }
        .onAppear {
            if reduceMotion {
                revealed = true
                orbit = true
            } else {
                withAnimation(.easeOut(duration: 0.48)) { revealed = true }
                withAnimation(.easeInOut(duration: 2.6).repeatForever(autoreverses: true)) { orbit = true }
            }
        }
    }

    private var symbol: String {
        switch celebration.kind {
        case .identification: "checkmark.seal"
        case .discovery: "sparkles"
        case .rediscovery: "arrow.trianglehead.2.clockwise.rotate.90"
        case .milestone: "medal"
        }
    }
}

private struct CelebrationRings: View {
    let progress: CGFloat

    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width * 0.82, y: size.height * 0.18)
            for index in 0..<5 {
                let radius = (70 + CGFloat(index) * 42) * (0.94 + progress * 0.06)
                context.stroke(
                    Path(ellipseIn: CGRect(
                        x: center.x - radius,
                        y: center.y - radius,
                        width: radius * 2,
                        height: radius * 2
                    )),
                    with: .color(.white.opacity(0.05)),
                    lineWidth: 1.2
                )
            }
        }
    }
}
