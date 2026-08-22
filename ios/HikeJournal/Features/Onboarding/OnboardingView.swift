import SwiftUI

private struct OnboardingPage: Identifiable {
    let id: Int
    let eyebrow: String
    let title: String
    let body: String
    let symbol: String
    let symbolLabel: String
}

private let onboardingPages = [
    OnboardingPage(
        id: 0,
        eyebrow: "A FIELD JOURNAL FOR THE OUTDOORS",
        title: "Keep the whole outing.",
        body: "Track the walk, notice what you find, and build a field journal you can return to.",
        symbol: "leaf.fill",
        symbolLabel: "Leaf"
    ),
    OnboardingPage(
        id: 1,
        eyebrow: "CAPTURE THE WALK",
        title: "Let the trail tell its story.",
        body: "Keep route, active time, and distance without a signal. Location access is requested only when you set out.",
        symbol: "figure.hiking",
        symbolLabel: "Hiker"
    ),
    OnboardingPage(
        id: 2,
        eyebrow: "NOTICE WHAT IS AROUND YOU",
        title: "Turn a find into a record.",
        body: "Add original photos, field marks, and observations. Photo access waits until you choose media for your journal.",
        symbol: "camera.macro",
        symbolLabel: "Nature camera"
    ),
    OnboardingPage(
        id: 3,
        eyebrow: "REVISIT AND SHARE",
        title: "Build a living map of your time outside.",
        body: "Return to routes, places, and seasonal finds—then connect iNaturalist when you are ready to share.",
        symbol: "map.fill",
        symbolLabel: "Map"
    )
]

struct OnboardingView: View {
    @ObservedObject var model: AppModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var pageIndex = 0
    @State private var direction = 1
    @State private var hasAppeared = false
    @State private var trailProgress: CGFloat = 0.03

    private var page: OnboardingPage { onboardingPages[pageIndex] }

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(spacing: 0) {
                        hero(height: min(max(geometry.size.height * 0.40, 270), 350))
                        pageBody
                    }
                }
                .scrollIndicators(.hidden)
            }
        }
        .onAppear {
            guard !hasAppeared else { return }
            if reduceMotion {
                hasAppeared = true
                trailProgress = 1
            } else {
                withAnimation(.easeOut(duration: 0.55)) { hasAppeared = true }
                withAnimation(.easeInOut(duration: 1.05).delay(0.15)) { trailProgress = 1 }
            }
        }
    }

    private func hero(height: CGFloat) -> some View {
        BrandLandscape(trailProgress: trailProgress)
            .frame(height: height)
            .overlay(alignment: .top) {
                HStack(alignment: .firstTextBaseline) {
                    Text("HIKEJOURNAL")
                        .font(HikeJournalTheme.display(39, relativeTo: .largeTitle))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button("Skip") {
                        model.completeOnboarding()
                    }
                    .font(HikeJournalTheme.label(15, relativeTo: .body))
                    .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                    .frame(minWidth: 44, minHeight: 44)
                }
                .padding(.horizontal, 22)
                .padding(.top, 10)
            }
            .overlay(alignment: .bottomLeading) {
                Text("\(pageIndex + 1) / \(onboardingPages.count)")
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.4)
                    .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                    .contentTransition(.numericText())
                    .padding(22)
            }
            .opacity(hasAppeared ? 1 : 0)
            .offset(y: hasAppeared ? 0 : -12)
    }

    private var pageBody: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    Image(systemName: page.symbol)
                        .font(.system(size: 21, weight: .semibold))
                        .foregroundStyle(HikeJournalTheme.moss)
                        .frame(width: 46, height: 46)
                        .background(HikeJournalTheme.lichen, in: Circle())
                        .accessibilityLabel(page.symbolLabel)
                    Text(page.eyebrow)
                        .font(HikeJournalTheme.label(12))
                        .tracking(1.15)
                        .foregroundStyle(HikeJournalTheme.trailText)
                }

                Text(page.title)
                    .font(HikeJournalTheme.display(42, relativeTo: .largeTitle))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)

                Text(page.body)
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .id(page.id)
            .transition(pageTransition)

            progress
                .padding(.top, 28)

            HStack(spacing: 18) {
                if pageIndex > 0 {
                    Button {
                        move(to: pageIndex - 1)
                    } label: {
                        Label("Back", systemImage: "chevron.left")
                            .font(HikeJournalTheme.label(16, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.moss)
                            .frame(minHeight: 52)
                    }
                }

                Button {
                    if pageIndex == onboardingPages.count - 1 {
                        model.completeOnboarding(openRecording: true)
                    } else {
                        move(to: pageIndex + 1)
                    }
                } label: {
                    HStack {
                        Text(pageIndex == onboardingPages.count - 1 ? "Set out" : "Next")
                        Spacer()
                        Image(systemName: pageIndex == onboardingPages.count - 1 ? "figure.hiking" : "arrow.right")
                    }
                }
                .buttonStyle(TrailButtonStyle())
            }
            .padding(.top, 24)
        }
        .padding(.horizontal, 24)
        .padding(.top, 26)
        .padding(.bottom, 34)
        .animation(reduceMotion ? nil : .snappy(duration: 0.38), value: pageIndex)
    }

    private var progress: some View {
        HStack(spacing: 6) {
            ForEach(onboardingPages.indices, id: \.self) { index in
                Capsule()
                    .fill(index <= pageIndex ? HikeJournalTheme.trail : HikeJournalTheme.line)
                    .frame(height: 4)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Onboarding progress")
        .accessibilityValue("Page \(pageIndex + 1) of \(onboardingPages.count)")
    }

    private var pageTransition: AnyTransition {
        guard !reduceMotion else { return .opacity }
        return .asymmetric(
            insertion: .move(edge: direction > 0 ? .trailing : .leading).combined(with: .opacity),
            removal: .move(edge: direction > 0 ? .leading : .trailing).combined(with: .opacity)
        )
    }

    private func move(to nextPage: Int) {
        direction = nextPage > pageIndex ? 1 : -1
        pageIndex = nextPage
    }
}
