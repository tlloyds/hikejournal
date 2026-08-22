// swift-tools-version: 5.10

import PackageDescription

let package = Package(
  name: "HikeJournalSync",
  platforms: [
    .iOS(.v17),
    .macOS(.v13),
  ],
  products: [
    .library(
      name: "HikeJournalSync",
      targets: ["HikeJournalSync"]
    )
  ],
  dependencies: [
    .package(path: "../HikeJournalPersistence")
  ],
  targets: [
    .target(
      name: "HikeJournalSync",
      dependencies: [
        .product(
          name: "HikeJournalPersistence",
          package: "HikeJournalPersistence"
        )
      ]
    ),
    .testTarget(
      name: "HikeJournalSyncTests",
      dependencies: [
        "HikeJournalSync",
        .product(
          name: "HikeJournalPersistence",
          package: "HikeJournalPersistence"
        ),
      ]
    ),
  ]
)
