import Foundation

protocol OnboardingStoring: AnyObject {
    var hasCompleted: Bool { get }
    func markCompleted()
    func reset()
}

final class DefaultsOnboardingStore: OnboardingStoring {
    private enum Key {
        static let completed = "onboarding.completed.v1"
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults) {
        self.defaults = defaults
    }

    var hasCompleted: Bool {
        defaults.bool(forKey: Key.completed)
    }

    func markCompleted() {
        defaults.set(true, forKey: Key.completed)
    }

    func reset() {
        defaults.removeObject(forKey: Key.completed)
    }
}
