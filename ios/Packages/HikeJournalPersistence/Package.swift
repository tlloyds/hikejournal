// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HikeJournalPersistence",
    platforms: [
        .iOS(.v17),
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "HikeJournalPersistence",
            targets: ["HikeJournalPersistence"]
        ),
    ],
    targets: [
        .target(
            name: "HikeJournalPersistence",
            linkerSettings: [.linkedLibrary("sqlite3")]
        ),
        .testTarget(
            name: "HikeJournalPersistenceTests",
            dependencies: ["HikeJournalPersistence"]
        ),
    ]
)
