import HikeJournalDomain
import SwiftUI

struct TrailMedalsView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var selectedBadge: TrailBadge?
    @State private var appeared = false

    init(model: AppModel) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        medalHeader

                        if isLoading {
                            Label("Refreshing trail progress…", systemImage: "arrow.triangle.2.circlepath")
                                .font(HikeJournalTheme.body(15))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                .padding(.horizontal, 22)
                                .padding(.top, 15)
                        }

                        ForEach(BadgeCategory.allCases, id: \.self) { category in
                            medalSection(category)
                        }
                    }
                    .padding(.bottom, 46)
                }
                .scrollIndicators(.hidden)
            }
            .toolbarBackground(HikeJournalTheme.moss, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await refresh() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(isLoading)
                    .accessibilityLabel("Refresh trail medals")
                }
            }
            .sheet(item: $selectedBadge) { badge in
                TrailMedalDetailView(badge: badge)
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
            }
            .task {
                guard !appeared else { return }
                withAnimation(reduceMotion ? nil : .easeOut(duration: 0.45)) {
                    appeared = true
                }
                await refresh()
            }
        }
    }

    private var medals: [TrailBadge] {
        calculateTrailBadges(
            hikes: journal.hikes,
            species: journal.species,
            quests: journal.quests
        )
    }

    private var earnedCount: Int { medals.count(where: \.earned) }

    private var nextMedal: TrailBadge? {
        medals
            .filter { !$0.earned }
            .max {
                if $0.progress != $1.progress { return $0.progress < $1.progress }
                return $0.definition.target > $1.definition.target
            }
    }

    private var isLoading: Bool {
        journal.isRefreshingHikes
            || journal.activeLoads.contains("field-guide")
            || journal.activeLoads.contains("quests")
    }

    private var medalHeader: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("HIKEJOURNAL")
                .font(HikeJournalTheme.label(12))
                .tracking(1.8)
                .foregroundStyle(HikeJournalTheme.fern)
            Text("Trail medals")
                .font(HikeJournalTheme.display(44, relativeTo: .largeTitle))
                .foregroundStyle(HikeJournalTheme.paper)
            Text("\(earnedCount) OF \(medals.count) EARNED · LIFETIME PROGRESS")
                .font(HikeJournalTheme.label(12))
                .tracking(0.8)
                .foregroundStyle(HikeJournalTheme.trail)
                .padding(.top, 4)

            if let nextMedal {
                HStack(spacing: 17) {
                    TrailMedalSeal(badge: nextMedal, preview: true)
                        .frame(width: 104, height: 112)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("NEXT MEDAL")
                            .font(HikeJournalTheme.label(11))
                            .tracking(1.4)
                            .foregroundStyle(HikeJournalTheme.fern)
                        Text(nextMedal.definition.title)
                            .font(HikeJournalTheme.display(27, relativeTo: .title2))
                            .foregroundStyle(HikeJournalTheme.paper)
                        Text(medalProgressLabel(nextMedal))
                            .font(HikeJournalTheme.body(15))
                            .foregroundStyle(HikeJournalTheme.paper.opacity(0.82))
                        ProgressView(value: appeared ? Double(nextMedal.progress) : 0)
                            .tint(HikeJournalTheme.trail)
                            .padding(.top, 7)
                            .animation(reduceMotion ? nil : .easeOut(duration: 0.75), value: appeared)
                    }
                }
                .padding(.top, 20)
                .accessibilityElement(children: .combine)
            } else {
                Text("Every trail medal is in your collection.")
                    .font(HikeJournalTheme.display(24, relativeTo: .title3))
                    .foregroundStyle(HikeJournalTheme.paper)
                    .padding(.top, 22)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 22)
        .padding(.top, 18)
        .padding(.bottom, 27)
        .background {
            LinearGradient(
                colors: [HikeJournalTheme.moss, HikeJournalTheme.mossSurface],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .overlay(alignment: .trailing) {
                Image(systemName: "mountain.2.fill")
                    .font(.system(size: 118, weight: .ultraLight))
                    .foregroundStyle(HikeJournalTheme.fern.opacity(0.09))
                    .offset(x: 18, y: 32)
                    .accessibilityHidden(true)
            }
        }
    }

    private func medalSection(_ category: BadgeCategory) -> some View {
        let categoryMedals = medals.filter { $0.definition.category == category }
        return VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(category.label)
                    .font(HikeJournalTheme.display(31, relativeTo: .title2))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text(category.description)
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            .padding(.horizontal, 22)

            LazyVGrid(
                columns: Array(repeating: GridItem(.flexible(), spacing: 3), count: 3),
                spacing: 7
            ) {
                ForEach(Array(categoryMedals.enumerated()), id: \.element.id) { index, badge in
                    Button {
                        selectedBadge = badge
                    } label: {
                        TrailMedalTile(
                            badge: badge,
                            visible: appeared,
                            delay: reduceMotion ? 0 : Double(index) * 0.035
                        )
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(badge.definition.title), \(badge.earned ? "earned" : medalProgressLabel(badge))")
                    .accessibilityHint("Opens medal details")
                }
            }
            .padding(.horizontal, 12)
        }
        .padding(.top, 30)
    }

    private func refresh() async {
        await journal.refreshHikes()
        await journal.refreshFieldGuide()
        await journal.loadQuests()
    }
}

private struct TrailMedalTile: View {
    let badge: TrailBadge
    let visible: Bool
    let delay: Double

    var body: some View {
        VStack(spacing: 5) {
            TrailMedalSeal(badge: badge)
                .frame(width: 87, height: 94)
            Text(badge.definition.title)
                .font(HikeJournalTheme.label(14, relativeTo: .caption))
                .foregroundStyle(badge.earned ? HikeJournalTheme.ink : HikeJournalTheme.inkMuted)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .frame(maxWidth: .infinity)
            Text(badge.earned ? "EARNED" : compactMedalProgress(badge))
                .font(HikeJournalTheme.label(10))
                .tracking(0.5)
                .foregroundStyle(badge.earned ? HikeJournalTheme.trailText : HikeJournalTheme.inkMuted)
                .lineLimit(1)
        }
        .padding(.horizontal, 3)
        .padding(.vertical, 7)
        .opacity(visible ? (badge.earned ? 1 : 0.7) : 0)
        .offset(y: visible ? 0 : 8)
        .animation(.easeOut(duration: 0.32).delay(delay), value: visible)
        .contentShape(Rectangle())
    }
}

private struct TrailMedalSeal: View {
    let badge: TrailBadge
    var preview = false

    private var active: Bool { badge.earned || preview }
    private var palette: MedalPalette { MedalPalette(finish: badge.definition.finish, active: active) }

    var body: some View {
        GeometryReader { proxy in
            let size = min(proxy.size.width, proxy.size.height)
            let radius = size * 0.37
            let center = CGPoint(x: proxy.size.width / 2, y: proxy.size.height * 0.44)
            ZStack {
                Canvas { context, canvas in
                    let left = Path { path in
                        path.move(to: CGPoint(x: center.x - radius * 0.62, y: canvas.height * 0.55))
                        path.addLine(to: CGPoint(x: center.x - radius * 0.12, y: canvas.height * 0.55))
                        path.addLine(to: CGPoint(x: center.x - radius * 0.24, y: canvas.height * 0.95))
                        path.addLine(to: CGPoint(x: center.x - radius * 0.66, y: canvas.height * 0.86))
                        path.closeSubpath()
                    }
                    let right = Path { path in
                        path.move(to: CGPoint(x: center.x + radius * 0.12, y: canvas.height * 0.55))
                        path.addLine(to: CGPoint(x: center.x + radius * 0.62, y: canvas.height * 0.55))
                        path.addLine(to: CGPoint(x: center.x + radius * 0.66, y: canvas.height * 0.86))
                        path.addLine(to: CGPoint(x: center.x + radius * 0.24, y: canvas.height * 0.95))
                        path.closeSubpath()
                    }
                    context.fill(left, with: .color(palette.ribbonDark))
                    context.fill(right, with: .color(palette.ribbon))

                    let shadow = Path(ellipseIn: CGRect(
                        x: center.x - radius,
                        y: center.y - radius + size * 0.025,
                        width: radius * 2,
                        height: radius * 2
                    ))
                    context.fill(shadow, with: .color(.black.opacity(0.18)))

                    let face = Path(ellipseIn: CGRect(
                        x: center.x - radius,
                        y: center.y - radius,
                        width: radius * 2,
                        height: radius * 2
                    ))
                    context.fill(
                        face,
                        with: .radialGradient(
                            Gradient(colors: [palette.light, palette.metal, palette.dark]),
                            center: CGPoint(x: center.x - radius * 0.25, y: center.y - radius * 0.28),
                            startRadius: 0,
                            endRadius: radius * 1.45
                        )
                    )

                    let inset = Path(ellipseIn: CGRect(
                        x: center.x - radius * 0.76,
                        y: center.y - radius * 0.76,
                        width: radius * 1.52,
                        height: radius * 1.52
                    ))
                    context.fill(inset, with: .color(palette.face))
                    context.stroke(inset, with: .color(palette.light.opacity(0.72)), lineWidth: max(1, radius * 0.035))
                }

                Image(systemName: badge.definition.symbol.systemImage)
                    .font(.system(size: size * 0.25, weight: .semibold))
                    .foregroundStyle(palette.icon)
                    .offset(y: -size * 0.055)
            }
        }
    }
}

private struct TrailMedalDetailView: View {
    let badge: TrailBadge
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var revealProgress = false

    var body: some View {
        ZStack {
            ParchmentBackground()
            VStack(spacing: 0) {
                TrailMedalSeal(badge: badge, preview: badge.earned)
                    .frame(width: 140, height: 148)
                    .accessibilityHidden(true)
                Text(badge.earned ? "MEDAL EARNED" : badge.definition.category.label.uppercased())
                    .font(HikeJournalTheme.label(11))
                    .tracking(1.4)
                    .foregroundStyle(badge.earned ? HikeJournalTheme.trailText : HikeJournalTheme.inkMuted)
                Text(badge.definition.title)
                    .font(HikeJournalTheme.display(39, relativeTo: .largeTitle))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .multilineTextAlignment(.center)
                    .padding(.top, 2)
                Text(badge.definition.requirement)
                    .font(HikeJournalTheme.body(17))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .multilineTextAlignment(.center)
                    .padding(.top, 6)
                ProgressView(value: revealProgress ? Double(badge.progress) : 0)
                    .tint(badge.earned ? HikeJournalTheme.trail : HikeJournalTheme.moss)
                    .padding(.top, 24)
                Text(medalProgressLabel(badge))
                    .font(HikeJournalTheme.bodyMedium(16))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .padding(.top, 8)
                if !badge.earned {
                    Text(remainingMedalLabel(badge))
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .padding(.top, 2)
                }
                Button("Close") { dismiss() }
                    .buttonStyle(TrailButtonStyle())
                    .padding(.top, 24)
            }
            .padding(.horizontal, 28)
            .padding(.bottom, 22)
        }
        .task {
            withAnimation(reduceMotion ? nil : .easeOut(duration: 0.7)) {
                revealProgress = true
            }
        }
    }
}

private struct MedalPalette {
    let metal: Color
    let light: Color
    let dark: Color
    let face: Color
    let icon: Color
    let ribbon: Color
    let ribbonDark: Color

    init(finish: BadgeFinish, active: Bool) {
        guard active else {
            metal = Color.gray.opacity(0.5)
            light = Color.white.opacity(0.52)
            dark = Color.gray.opacity(0.68)
            face = Color.gray.opacity(0.3)
            icon = HikeJournalTheme.inkMuted.opacity(0.7)
            ribbon = HikeJournalTheme.inkMuted.opacity(0.38)
            ribbonDark = HikeJournalTheme.inkMuted.opacity(0.52)
            return
        }
        switch finish {
        case .bronze:
            metal = Color(red: 0.69, green: 0.40, blue: 0.22)
            light = Color(red: 0.94, green: 0.69, blue: 0.45)
            dark = Color(red: 0.37, green: 0.18, blue: 0.10)
            face = Color(red: 0.76, green: 0.50, blue: 0.30)
            icon = Color(red: 0.27, green: 0.12, blue: 0.06)
        case .silver:
            metal = Color(red: 0.64, green: 0.68, blue: 0.66)
            light = Color(red: 0.94, green: 0.95, blue: 0.91)
            dark = Color(red: 0.35, green: 0.39, blue: 0.38)
            face = Color(red: 0.78, green: 0.81, blue: 0.78)
            icon = Color(red: 0.20, green: 0.27, blue: 0.23)
        case .gold:
            metal = Color(red: 0.82, green: 0.63, blue: 0.20)
            light = Color(red: 1.0, green: 0.88, blue: 0.48)
            dark = Color(red: 0.49, green: 0.32, blue: 0.06)
            face = Color(red: 0.91, green: 0.73, blue: 0.29)
            icon = Color(red: 0.31, green: 0.19, blue: 0.02)
        case .evergreen:
            metal = Color(red: 0.20, green: 0.40, blue: 0.30)
            light = Color(red: 0.54, green: 0.69, blue: 0.55)
            dark = Color(red: 0.08, green: 0.22, blue: 0.16)
            face = Color(red: 0.30, green: 0.51, blue: 0.38)
            icon = Color(red: 0.94, green: 0.86, blue: 0.57)
        }
        ribbon = HikeJournalTheme.trail
        ribbonDark = HikeJournalTheme.trailText
    }
}

private extension BadgeSymbol {
    var systemImage: String {
        switch self {
        case .boot: "figure.hiking"
        case .mountain: "mountain.2.fill"
        case .route: "point.topleft.down.to.point.bottomright.curvepath"
        case .flag: "flag.fill"
        case .rare: "star.fill"
        case .compass: "safari.fill"
        case .plant: "leaf.fill"
        case .mammal: "pawprint.fill"
        case .fungi: "tree.fill"
        case .bird: "bird.fill"
        case .insect: "ant.fill"
        }
    }
}

private func compactMedalProgress(_ badge: TrailBadge) -> String {
    switch badge.definition.metric {
    case .totalMiles, .longestHike:
        "\(formatMedalNumber(badge.current)) / \(formatMedalNumber(badge.definition.target)) MI"
    default:
        "\(Int(badge.current.rounded())) / \(Int(badge.definition.target.rounded()))"
    }
}

private func medalProgressLabel(_ badge: TrailBadge) -> String {
    let current = Int(badge.current.rounded())
    let target = Int(badge.definition.target.rounded())
    switch badge.definition.metric {
    case .totalMiles:
        return badge.earned
            ? "\(formatMedalNumber(badge.current)) lifetime miles recorded"
            : "\(formatMedalNumber(badge.current)) of \(formatMedalNumber(badge.definition.target)) lifetime miles"
    case .longestHike:
        return badge.earned
            ? "Longest hike · \(formatMedalNumber(badge.current)) miles"
            : "\(formatMedalNumber(badge.current)) of \(formatMedalNumber(badge.definition.target)) miles in one hike"
    case .hikeCount: return badge.earned ? "\(current) hikes logged" : "\(current) of \(target) hikes"
    case .completedQuests: return badge.earned ? "\(current) Field Quests completed" : "\(current) of \(target) completed quests"
    case .rareFinds: return badge.earned ? "\(current) less-often-reported finds" : "\(current) of \(target) less-often-reported finds"
    case .speciesCount: return badge.earned ? "\(current) distinct species logged" : "\(current) of \(target) distinct species"
    case .plants: return badge.earned ? "\(current) distinct plants logged" : "\(current) of \(target) plants"
    case .mammals: return badge.earned ? "\(current) distinct mammals logged" : "\(current) of \(target) mammals"
    case .fungi: return badge.earned ? "\(current) distinct fungi logged" : "\(current) of \(target) fungi"
    case .birds: return badge.earned ? "\(current) distinct birds logged" : "\(current) of \(target) birds"
    case .insects: return badge.earned ? "\(current) distinct insects logged" : "\(current) of \(target) insects"
    }
}

private func remainingMedalLabel(_ badge: TrailBadge) -> String {
    let remaining = max(0, badge.definition.target - badge.current)
    return switch badge.definition.metric {
    case .totalMiles, .longestHike: "\(formatMedalNumber(remaining)) miles to go"
    default: "\(Int(remaining.rounded())) to go"
    }
}

private func formatMedalNumber(_ value: Double) -> String {
    value.rounded() == value ? String(format: "%.0f", value) : String(format: "%.1f", value)
}
