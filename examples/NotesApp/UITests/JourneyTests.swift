import XCTest

// Step 2/3: the three task-card journeys, crystallized as XCUITest.
// Every verification is an AX-state assertion — no screenshots anywhere.
@MainActor
final class JourneyTests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitest-reset"] // start from empty defaults
        app.launch()
        app.activate()
        _ = app.windows.firstMatch.waitForExistence(timeout: 5)
    }

    private var rowCount: Int { app.outlines.cells.count }

    private func addNote() {
        app.buttons["addNote"].firstMatch.click()
    }

    // Journey 1: create a note; verify list grows and detail editor appears.
    func testJourneyCreateNote() throws {
        let before = rowCount
        addNote()
        let title = app.textFields["detailTitle"].firstMatch
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        XCTAssertEqual(rowCount, before + 1)
        XCTAssertEqual(title.value as? String, "Untitled")
    }

    // Journey 2: rename via the detail title field; verify sidebar row follows.
    func testJourneyRenameNote() throws {
        addNote()
        let title = app.textFields["detailTitle"].firstMatch
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        title.click()
        title.typeKey("a", modifierFlags: .command)
        title.typeText("Groceries\n")
        let renamedRow = app.outlines.staticTexts["Groceries"].firstMatch
        XCTAssertTrue(renamedRow.waitForExistence(timeout: 5))
    }

    // Journey 3: delete then undo; verify row disappears and comes back.
    func testJourneyDeleteUndo() throws {
        addNote()
        let title = app.textFields["detailTitle"].firstMatch
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        title.click()
        title.typeKey("a", modifierFlags: .command)
        title.typeText("Doomed\n")
        XCTAssertTrue(app.outlines.staticTexts["Doomed"].firstMatch.waitForExistence(timeout: 5))
        let before = rowCount

        // Select the row, then delete via the app's File > Delete Note menu command.
        // (A bare menuItems["Delete"] query is ambiguous: it can match the Edit-menu
        // text-editing Delete and mutate the focused text field instead.)
        app.outlines.staticTexts["Doomed"].firstMatch.click()
        app.menuBars.menuItems["Delete Note"].click()
        let gone = NSPredicate(format: "exists == false")
        expectation(for: gone, evaluatedWith: app.outlines.staticTexts["Doomed"].firstMatch)
        waitForExpectations(timeout: 5)
        XCTAssertEqual(rowCount, before - 1)

        app.buttons["undoDelete"].firstMatch.click()
        XCTAssertTrue(app.outlines.staticTexts["Doomed"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(rowCount, before)
    }
}
