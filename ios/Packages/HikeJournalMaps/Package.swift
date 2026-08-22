// swift-tools-version: 5.10

import PackageDescription

let package = Package(
  name: "HikeJournalMaps",
  platforms: [
    .iOS(.v17),
    .macOS(.v13),
  ],
  products: [
    .library(name: "HikeJournalMaps", targets: ["HikeJournalMaps"])
  ],
  dependencies: [
    .package(
      url: "https://github.com/maplibre/maplibre-gl-native-distribution",
      exact: "6.28.0"
    )
  ],
  targets: [
    .target(
      name: "HikeJournalMaps",
      dependencies: [
        .product(
          name: "MapLibre",
          package: "maplibre-gl-native-distribution",
          condition: .when(platforms: [.iOS])
        )
      ]
    ),
    .testTarget(
      name: "HikeJournalMapsTests",
      dependencies: ["HikeJournalMaps"]
    ),
  ]
)
