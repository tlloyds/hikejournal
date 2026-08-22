import GoogleSignInSwift
import SwiftUI

struct AccountView: View {
    @ObservedObject var authentication: AuthenticationStore
    @ObservedObject var storefront: StorefrontStore
    let webBaseURL: URL?
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.openURL) private var openURL
    @State private var showingDeleteConfirmation = false
    @State private var showingPaywall = false

    var body: some View {
        ZStack {
            ParchmentBackground()
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("HIKEJOURNAL")
                        .font(HikeJournalTheme.display(39, relativeTo: .largeTitle))
                        .foregroundStyle(HikeJournalTheme.moss)
                        .accessibilityAddTraits(.isHeader)

                    phaseContent
                        .padding(.top, 12)
                }
                .padding(.horizontal, 24)
                .padding(.top, 20)
                .padding(.bottom, 48)
            }
            .scrollIndicators(.hidden)
        }
        .navigationTitle("Account")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: accountIdentity) {
            await storefront.configureForCurrentAccount()
        }
        .sheet(isPresented: $showingPaywall) {
            PlusPaywallView(
                storefront: storefront,
                privacyURL: webBaseURL?.appendingPathComponent("privacy")
            )
        }
        .confirmationDialog(
            "Delete your HikeJournal account?",
            isPresented: $showingDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete account and cloud data", role: .destructive) {
                Task { await authentication.deleteAccount() }
            }
            Button("Keep account", role: .cancel) {}
        } message: {
            Text("This permanently removes the account and its cloud journals and media. An App Store subscription is managed separately and is not canceled automatically.")
        }
    }

    @ViewBuilder
    private var phaseContent: some View {
        switch authentication.phase {
        case .restoring:
            HStack(spacing: 12) {
                ProgressView()
                Text("Opening your field journal…")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            .frame(minHeight: 72)
        case .signedOut:
            signedOutContent
        case let .signedIn(account):
            signedInContent(account)
        }
    }

    private var signedOutContent: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Keep every trail tied to you.")
                .font(HikeJournalTheme.display(35, relativeTo: .title))
                .foregroundStyle(HikeJournalTheme.ink)
            Text("Sign in to sync journal entries and use the same account across devices. Recording and local drafts remain useful without a signal.")
                .font(HikeJournalTheme.body(18))
                .foregroundStyle(HikeJournalTheme.inkMuted)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)

            Divider()
                .overlay(HikeJournalTheme.line)
                .padding(.vertical, 26)

            NativeAppleSignInButton(
                colorScheme: colorScheme,
                action: {
                    Task { await authentication.signInWithApple() }
                }
            )
            .id(colorScheme)
            .frame(height: 52)
            .disabled(authentication.isPerformingAction)
            .opacity(authentication.isPerformingAction ? 0.6 : 1)

            if authentication.isGoogleSignInConfigured {
                GoogleSignInButton(
                    scheme: colorScheme == .dark ? .dark : .light,
                    style: .wide,
                    state: authentication.isPerformingAction ? .disabled : .normal
                ) {
                    Task { await authentication.signInWithGoogle() }
                }
                .frame(height: 52)
                .disabled(authentication.isPerformingAction)
                .padding(.top, 12)
                .accessibilityHint("Uses the same HikeJournal account as Google sign-in on Android")
            }

            if authentication.isPerformingAction {
                ProgressView("Signing in…")
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .padding(.top, 14)
            }

            errorContent
        }
    }

    private func signedInContent(_ account: AuthAccount) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Welcome back, \(account.displayName.isEmpty ? "Hiker" : account.displayName).")
                .font(HikeJournalTheme.display(35, relativeTo: .title))
                .foregroundStyle(HikeJournalTheme.ink)
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 15) {
                accountLine("Email", value: account.email.isEmpty ? "Private Apple relay" : account.email)
                accountLine("Signed in with", value: providerName(account.identityProvider))
                accountLine("Plan", value: authentication.entitlement?.plan.displayName ?? "Checking…")
            }
            .padding(.top, 26)

            if let entitlement = authentication.entitlement {
                entitlementActions(entitlement)
                    .padding(.top, 22)
            }

            Divider()
                .overlay(HikeJournalTheme.line)
                .padding(.vertical, 26)

            Button {
                Task { await authentication.loadEntitlement() }
            } label: {
                Label("Refresh account status", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(minHeight: 46)
            .disabled(authentication.isPerformingAction)

            Button {
                Task { await authentication.signOut() }
            } label: {
                Label("Sign out on this iPhone", systemImage: "rectangle.portrait.and.arrow.right")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(minHeight: 46)
            .disabled(authentication.isPerformingAction)

            Button(role: .destructive) {
                showingDeleteConfirmation = true
            } label: {
                Label("Delete account", systemImage: "trash")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .frame(minHeight: 46)
            .disabled(authentication.isPerformingAction)

            errorContent

            if let message = storefront.notice ?? storefront.errorMessage {
                Text(message)
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(storefront.errorMessage == nil ? HikeJournalTheme.moss : HikeJournalTheme.error)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 14)
            }
        }
    }

    @ViewBuilder
    private func entitlementActions(_ entitlement: EntitlementSnapshot) -> some View {
        if entitlement.plan == .free {
            VStack(alignment: .leading, spacing: 10) {
                quotaLine(
                    title: "Cloud journals",
                    used: entitlement.usage.cloudHikes,
                    limit: entitlement.limits.cloudHikes
                )
                quotaLine(
                    title: "Cloud photos & videos",
                    used: entitlement.usage.cloudMedia,
                    limit: entitlement.limits.cloudMedia
                )
                Button("Explore HikeJournal Plus") {
                    showingPaywall = true
                }
                .buttonStyle(TrailButtonStyle())
                .padding(.top, 8)
            }
        } else if entitlement.plan == .plus,
                  entitlement.source == .appleSubscription {
            Button {
                Task { await storefront.showManageSubscriptions() }
            } label: {
                Label("Manage subscription", systemImage: "creditcard")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(minHeight: 46)
        } else if entitlement.plan == .lifetime {
            Text("Lifetime access is active. No subscription is needed.")
                .font(HikeJournalTheme.body(16))
                .foregroundStyle(HikeJournalTheme.moss)
        }

        if entitlement.plan != .lifetime {
            Button("Restore App Store purchases") {
                Task { await storefront.restorePurchases() }
            }
            .font(HikeJournalTheme.label(15, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(minHeight: 44)

            if storefront.errorMessage != nil {
                Button("Open App Store subscriptions") {
                    openURL(storefront.managementFallbackURL)
                }
                .font(HikeJournalTheme.body(14))
            }
        }
    }

    private func quotaLine(title: String, used: Int, limit: Int?) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(title)
                Spacer()
                Text(limit.map { "\(used) of \($0)" } ?? "\(used)")
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            .font(HikeJournalTheme.body(15))
            if let limit, limit > 0 {
                ProgressView(value: min(Double(used) / Double(limit), 1))
                    .tint(HikeJournalTheme.trailText)
            }
        }
    }

    private func accountLine(_ label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(HikeJournalTheme.label(11))
                .tracking(1.1)
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Text(value)
                .font(HikeJournalTheme.body(17))
                .foregroundStyle(HikeJournalTheme.ink)
                .textSelection(.enabled)
        }
    }

    @ViewBuilder
    private var errorContent: some View {
        if let message = authentication.errorMessage {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(HikeJournalTheme.error)
                    .accessibilityHidden(true)
                Text(message)
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.error)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Button {
                    authentication.clearError()
                } label: {
                    Image(systemName: "xmark")
                }
                .accessibilityLabel("Dismiss message")
            }
            .padding(.top, 18)
        }
    }

    private func providerName(_ provider: String?) -> String {
        switch provider?.lowercased() {
        case "apple": "Apple"
        case "google": "Google"
        case .some: "HikeJournal"
        case nil: "HikeJournal"
        }
    }

    private var accountIdentity: String {
        if case let .signedIn(account) = authentication.phase {
            return account.userID ?? account.subject
        }
        return "signed-out"
    }
}
