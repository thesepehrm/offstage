import XCTest

@MainActor
final class NotesAppUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launch()
        return app
    }

    // Substrate check 1c: does performAccessibilityAudit run on the macOS destination,
    // and does the deliberately unlabelled undo button fail it?
    func testAccessibilityAuditRuns() throws {
        let app = launch()
        var issues: [String] = []
        do {
            try app.performAccessibilityAudit { issue in
                issues.append("\(issue.auditType): \(issue.description) [\(issue.element?.description ?? "no element")]")
                return true // handled: collect, don't fail — we want the full list
            }
        } catch {
            XCTFail("performAccessibilityAudit threw on macOS destination: \(error)")
        }
        for (i, issue) in issues.enumerated() {
            print("A11Y_ISSUE[\(i)]: \(issue.replacingOccurrences(of: "\n", with: " | "))")
        }
        print("A11Y_AUDIT_ISSUE_COUNT=\(issues.count)")
    }

    func testAccessibilityAuditFailsOnUnlabelledButton() throws {
        let app = launch()
        var sawUnlabelled = false
        do {
            try app.performAccessibilityAudit(for: .sufficientElementDescription) { issue in
                sawUnlabelled = true
                return true
            }
        } catch {
            // Audit unsupported → this test is inconclusive, recorded as thrown error.
            throw XCTSkip("audit threw: \(error)")
        }
        XCTAssertTrue(sawUnlabelled, "expected the unlabelled undo button to raise a description issue")
    }

    // Substrate check 1b fallback: dump the AX-derived element tree.
    func testDumpElementTree() throws {
        let app = launch()
        _ = app.windows.firstMatch.waitForExistence(timeout: 5)
        let path = NSTemporaryDirectory() + "ax-dump-notesapp.txt"
        try app.debugDescription.write(toFile: path, atomically: true, encoding: .utf8)
        print("AX_DUMP_PATH=\(path)")
    }

    // Journey: create note via toolbar, verify by AX state.
    func testCreateNoteJourney() throws {
        let app = launch()
        let add = app.buttons["addNote"]
        XCTAssertTrue(add.waitForExistence(timeout: 5))
        let before = app.outlines.cells.count + app.tables.cells.count
        add.click()
        let titleField = app.textFields["detailTitle"]
        XCTAssertTrue(titleField.waitForExistence(timeout: 5))
        let after = app.outlines.cells.count + app.tables.cells.count
        XCTAssertEqual(after, before + 1)
    }
}
