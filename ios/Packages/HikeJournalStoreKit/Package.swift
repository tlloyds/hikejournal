// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HikeJournalStoreKit",
    platforms: [
        .iOS(.v17),
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "HikeJournalStoreKit",
            targets: ["HikeJournalStoreKit"]
        ),
    ],
    targets: [
        .target(name: "HikeJournalStoreKit"),
        .testTarget(
            name: "HikeJournalStoreKitTests",
            dependencies: ["HikeJournalStoreKit"]
        ),
    ]
)
