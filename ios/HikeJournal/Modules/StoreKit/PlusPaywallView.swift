import HikeJournalStoreKit
import SwiftUI

struct PlusPaywallView: View {
    @ObservedObject var storefront: StorefrontStore
    let privacyURL: URL?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var revealBenefits = false

    private let termsURL = URL(
        string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/"
    )!

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        hero
                        offer
                            .padding(.horizontal, 24)
                            .padding(.top, 28)
                            .padding(.bottom, 40)
                    }
                }
                .scrollIndicators(.hidden)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Close") { dismiss() }
                }
            }
            .task {
                await storefront.configureForCurrentAccount()
                guard !reduceMotion else {
                    revealBenefits = true
                    return
                }
                withAnimation(.easeOut(duration: 0.55)) {
                    revealBenefits = true
                }
            }
        }
    }

    private var hero: some View {
        ZStack(alignment: .bottomLeading) {
            BrandLandscape()
                .frame(height: 270)
                .overlay(
                    LinearGradient(
                        colors: [.clear, Color.black.opacity(0.55)],
                        startPoint: .center,
                        endPoint: .bottom
                    )
                )
            VStack(alignment: .leading, spacing: 4) {
                Text("HIKEJOURNAL PLUS")
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.6)
                Text("Go farther. Keep it all.")
                    .font(HikeJournalTheme.display(40, relativeTo: .largeTitle))
                Text("Full field intelligence, deeper history, and room for every season outside.")
                    .font(HikeJournalTheme.body(17))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
            .padding(24)
        }
        .accessibilityElement(children: .combine)
    }

    private var offer: some View {
        VStack(alignment: .leading, spacing: 0) {
            benefit("sparkles", "Field Briefings, weather history, comparisons, and advanced discovery")
            benefit("map.fill", "Offline map regions and the complete trail-planning toolkit")
            benefit("photo.stack.fill", "Expanded cloud journals and media without Free limits")

            Divider().overlay(HikeJournalTheme.line).padding(.vertical, 24)

            ForEach(HikeJournalProductID.allCases.sorted(by: { $0.displayOrder < $1.displayOrder }), id: \.self) { productID in
                planButton(productID)
                    .padding(.bottom, 12)
            }

            Button {
                Task { await storefront.purchase(storefront.selectedProductID) }
            } label: {
                HStack {
                    if storefront.purchasingProductID != nil {
                        ProgressView().tint(HikeJournalTheme.paper)
                    }
                    Text(purchaseLabel)
                    Spacer()
                    Image(systemName: "arrow.right")
                }
            }
            .buttonStyle(TrailButtonStyle())
            .disabled(selectedProduct == nil || storefront.purchasingProductID != nil)
            .opacity(selectedProduct == nil ? 0.55 : 1)
            .padding(.top, 4)

            Button("Restore purchases") {
                Task { await storefront.restorePurchases() }
            }
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(maxWidth: .infinity, minHeight: 48)
            .disabled(storefront.isLoading)

            message

            Text("Payment is charged to your Apple ID. Subscriptions renew automatically unless canceled at least 24 hours before the current period ends. Manage or cancel in your App Store account.")
                .font(HikeJournalTheme.body(13, relativeTo: .caption))
                .foregroundStyle(HikeJournalTheme.inkMuted)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 14)

            HStack(spacing: 20) {
                Link("Terms", destination: termsURL)
                if let privacyURL {
                    Link("Privacy", destination: privacyURL)
                }
            }
            .font(HikeJournalTheme.label(14, relativeTo: .caption))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(maxWidth: .infinity)
            .padding(.top, 16)
        }
    }

    private func benefit(_ symbol: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: symbol)
                .foregroundStyle(HikeJournalTheme.trailText)
                .frame(width: 24)
                .accessibilityHidden(true)
            Text(text)
                .font(HikeJournalTheme.body(16))
                .foregroundStyle(HikeJournalTheme.ink)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 9)
        .opacity(revealBenefits ? 1 : 0)
        .offset(y: revealBenefits ? 0 : 8)
    }

    private func planButton(_ productID: HikeJournalProductID) -> some View {
        let product = storefront.products.first { $0.productID == productID.rawValue }
        let selected = storefront.selectedProductID == productID
        return Button {
            storefront.selectedProductID = productID
        } label: {
            HStack(spacing: 14) {
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(selected ? HikeJournalTheme.trailText : HikeJournalTheme.inkMuted)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(productID == .plusAnnual ? "Annual" : "Monthly")
                            .font(HikeJournalTheme.label(17, relativeTo: .headline))
                        if productID == .plusAnnual {
                            Text("BEST VALUE")
                                .font(HikeJournalTheme.label(10))
                                .tracking(0.8)
                                .foregroundStyle(HikeJournalTheme.trailText)
                        }
                    }
                    Text(priceDescription(product, productID: productID))
                        .font(HikeJournalTheme.body(15))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
                Spacer()
            }
            .foregroundStyle(HikeJournalTheme.ink)
            .padding(16)
            .background(
                selected ? HikeJournalTheme.lichen.opacity(0.8) : Color.clear,
                in: RoundedRectangle(cornerRadius: 14, style: .continuous)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(selected ? HikeJournalTheme.moss : HikeJournalTheme.line, lineWidth: selected ? 2 : 1)
            }
        }
        .buttonStyle(.plain)
        .disabled(product == nil)
        .accessibilityLabel("\(productID == .plusAnnual ? "Annual" : "Monthly") plan, \(priceDescription(product, productID: productID))")
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    @ViewBuilder
    private var message: some View {
        if let notice = storefront.notice {
            Label(notice, systemImage: "checkmark.circle.fill")
                .foregroundStyle(HikeJournalTheme.moss)
                .font(HikeJournalTheme.body(15))
                .padding(.top, 10)
        }
        if let error = storefront.errorMessage {
            Label(error, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(HikeJournalTheme.error)
                .font(HikeJournalTheme.body(15))
                .padding(.top, 10)
        }
    }

    private var selectedProduct: StoreProductInfo? {
        storefront.products.first { $0.productID == storefront.selectedProductID.rawValue }
    }

    private var purchaseLabel: String {
        guard let selectedProduct else { return storefront.isLoading ? "Loading App Store…" : "Unavailable" }
        return "Continue — \(selectedProduct.displayPrice)"
    }

    private func priceDescription(
        _ product: StoreProductInfo?,
        productID: HikeJournalProductID
    ) -> String {
        guard let product else { return storefront.isLoading ? "Loading price…" : "Not available" }
        return "\(product.displayPrice) per \(productID == .plusAnnual ? "year" : "month")"
    }
}
