import XCTest
@testable import NotesApp

final class NotesStoreTests: XCTestCase {
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "test.notes")
        defaults.removePersistentDomain(forName: "test.notes")
    }

    func testAddInsertsAtTopAndSelects() {
        let store = NotesStore(defaults: defaults)
        let a = store.addNote(title: "A")
        let b = store.addNote(title: "B")
        XCTAssertEqual(store.notes.map(\.title), ["B", "A"])
        XCTAssertEqual(store.selection, b.id)
        _ = a
    }

    func testDeleteThenUndoRestoresAtIndex() {
        let store = NotesStore(defaults: defaults)
        store.addNote(title: "A")
        let b = store.addNote(title: "B")
        store.deleteNote(id: b.id)
        XCTAssertEqual(store.notes.map(\.title), ["A"])
        store.undoDelete()
        XCTAssertEqual(store.notes.map(\.title), ["B", "A"])
        XCTAssertEqual(store.selection, b.id)
    }

    func testRename() {
        let store = NotesStore(defaults: defaults)
        let n = store.addNote(title: "Old")
        store.rename(id: n.id, to: "New")
        XCTAssertEqual(store.notes.first?.title, "New")
    }

    func testPersistenceRoundTrip() {
        let store = NotesStore(defaults: defaults)
        store.addNote(title: "Persist me")
        let reloaded = NotesStore(defaults: defaults)
        XCTAssertEqual(reloaded.notes.map(\.title), ["Persist me"])
    }
}
