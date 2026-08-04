import XCTest

// Substrate check 1b: real AX-derived element trees via XCUIElement.debugDescription.
// Host terminal lacks Accessibility permission (kAXErrorAPIDisabled), so raw AXUIElement
// dumps are unavailable; testmanagerd has its own automation rights, so this path works
// headless. debugDescription is a pretty-printed snapshot of the same AX tree.
@MainActor
final class AXDumpTests: XCTestCase {
    private func dump(_ app: XCUIApplication, name: String) throws {
        _ = app.windows.firstMatch.waitForExistence(timeout: 10)
        let path = NSTemporaryDirectory() + "ax-dump-\(name).txt"
        try app.debugDescription.write(toFile: path, atomically: true, encoding: .utf8)
        let frame = app.windows.firstMatch.frame
        print("AX_DUMP path=\(path) window=\(Int(frame.width))x\(Int(frame.height))")
    }

    func testDumpNotesApp() throws {
        let app = XCUIApplication()
        app.launch()
        try dump(app, name: "notesapp")
    }

    func testDumpFinder() throws {
        let finder = XCUIApplication(bundleIdentifier: "com.apple.finder")
        finder.activate()
        try dump(finder, name: "finder")
    }

    func testDumpXcode() throws {
        let xcode = XCUIApplication(bundleIdentifier: "com.apple.dt.Xcode")
        xcode.activate()
        try dump(xcode, name: "xcode")
    }
}
