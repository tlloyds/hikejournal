// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HikeJournalTracking",
    platforms: [
        .iOS(.v17),
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "HikeJournalTracking",
            targets: ["HikeJournalTracking"]
        ),
    ],
    targets: [
        .target(name: "HikeJournalTracking"),
        .testTarget(
            name: "HikeJournalTrackingTests",
            dependencies: ["HikeJournalTracking"],
            resources: [.process("Fixtures")]
        ),
    ]
)
