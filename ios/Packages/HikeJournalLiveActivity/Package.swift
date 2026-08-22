// swift-tools-version: 5.10

import PackageDescription

let package = Package(
  name: "HikeJournalLiveActivity",
  platforms: [
    .iOS(.v17),
    .macOS(.v13),
  ],
  products: [
    .library(
      name: "HikeJournalLiveActivity",
      targets: ["HikeJournalLiveActivity"]
    ),
    .library(
      name: "HikeJournalLiveActivityTracking",
      targets: ["HikeJournalLiveActivityTracking"]
    ),
    .library(
      name: "HikeJournalLiveActivityWidget",
      targets: ["HikeJournalLiveActivityWidget"]
    ),
  ],
  dependencies: [
    .package(path: "../HikeJournalTracking")
  ],
  targets: [
    .target(name: "HikeJournalLiveActivity"),
    .target(
      name: "HikeJournalLiveActivityTracking",
      dependencies: [
        "HikeJournalLiveActivity",
        .product(name: "HikeJournalTracking", package: "HikeJournalTracking"),
      ]
    ),
    .target(
      name: "HikeJournalLiveActivityWidget",
      dependencies: ["HikeJournalLiveActivity"]
    ),
    .testTarget(
      name: "HikeJournalLiveActivityTests",
      dependencies: [
        "HikeJournalLiveActivity",
        "HikeJournalLiveActivityTracking",
        .product(name: "HikeJournalTracking", package: "HikeJournalTracking"),
      ]
    ),
  ]
)
