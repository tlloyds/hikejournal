// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HikeJournalDomain",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(name: "HikeJournalDomain", targets: ["HikeJournalDomain"]),
    ],
    targets: [
        .target(name: "HikeJournalDomain"),
        .testTarget(
            name: "HikeJournalDomainTests",
            dependencies: ["HikeJournalDomain"]
        ),
    ],
    swiftLanguageVersions: [.v5]
)
