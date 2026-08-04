// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "OffstagePort",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "OffstagePort", targets: ["OffstagePort"])
    ],
    targets: [
        .target(name: "OffstagePort"),
        .testTarget(name: "OffstagePortTests", dependencies: ["OffstagePort"]),
    ]
)
