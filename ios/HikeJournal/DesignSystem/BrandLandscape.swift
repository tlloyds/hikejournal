import SwiftUI

struct BrandLandscape: View {
    var trailProgress: CGFloat = 1

    var body: some View {
        GeometryReader { proxy in
            let size = proxy.size
            ZStack {
                LinearGradient(
                    colors: [Color(red: 0.19, green: 0.35, blue: 0.27), Color(red: 0.07, green: 0.19, blue: 0.14)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )

                Circle()
                    .fill(Color(red: 0.96, green: 0.94, blue: 0.84).opacity(0.72))
                    .frame(width: min(size.width, size.height) * 0.12)
                    .position(x: size.width * 0.81, y: size.height * 0.22)

                Path { path in
                    path.move(to: CGPoint(x: 0, y: size.height * 0.88))
                    path.addLine(to: CGPoint(x: size.width * 0.24, y: size.height * 0.37))
                    path.addLine(to: CGPoint(x: size.width * 0.48, y: size.height * 0.69))
                    path.addLine(to: CGPoint(x: size.width * 0.68, y: size.height * 0.28))
                    path.addLine(to: CGPoint(x: size.width, y: size.height * 0.74))
                    path.addLine(to: CGPoint(x: size.width, y: size.height))
                    path.addLine(to: CGPoint(x: 0, y: size.height))
                    path.closeSubpath()
                }
                .fill(Color(red: 0.46, green: 0.57, blue: 0.43))

                Path { path in
                    path.move(to: CGPoint(x: size.width * 0.24, y: size.height * 0.37))
                    path.addLine(to: CGPoint(x: size.width * 0.33, y: size.height * 0.50))
                    path.addLine(to: CGPoint(x: size.width * 0.40, y: size.height * 0.58))
                    path.closeSubpath()
                }
                .fill(Color(red: 0.77, green: 0.82, blue: 0.66).opacity(0.9))

                TrailPath()
                    .trim(from: 0, to: min(max(trailProgress, 0), 1))
                    .stroke(
                        Color(red: 0.83, green: 0.49, blue: 0.26),
                        style: StrokeStyle(lineWidth: max(12, size.width * 0.034), lineCap: .round)
                    )
                    .shadow(color: .black.opacity(0.12), radius: 3, y: 2)

                TrailPath()
                    .trim(from: 0, to: min(max(trailProgress, 0), 1))
                    .stroke(
                        Color(red: 1, green: 0.96, blue: 0.84).opacity(0.42),
                        style: StrokeStyle(lineWidth: max(2, size.width * 0.006), lineCap: .round)
                    )
            }
            .clipped()
        }
        .accessibilityHidden(true)
    }
}

private struct TrailPath: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: -rect.width * 0.04, y: rect.height * 0.98))
        path.addCurve(
            to: CGPoint(x: rect.width * 0.65, y: rect.height * 0.66),
            control1: CGPoint(x: rect.width * 0.20, y: rect.height * 0.70),
            control2: CGPoint(x: rect.width * 0.43, y: rect.height * 0.92)
        )
        path.addCurve(
            to: CGPoint(x: rect.width * 1.05, y: rect.height * 0.50),
            control1: CGPoint(x: rect.width * 0.79, y: rect.height * 0.46),
            control2: CGPoint(x: rect.width * 0.90, y: rect.height * 0.61)
        )
        return path
    }
}
