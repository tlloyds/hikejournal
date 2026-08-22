// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HikeJournalMedia",
    platforms: [
        .iOS(.v17),
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "HikeJournalMedia",
            targets: ["HikeJournalMedia"]
        ),
    ],
    targets: [
        .target(name: "HikeJournalMedia"),
        .testTarget(
            name: "HikeJournalMediaTests",
            dependencies: ["HikeJournalMedia"]
        ),
    ],
    swiftLanguageVersions: [.v5]
)
