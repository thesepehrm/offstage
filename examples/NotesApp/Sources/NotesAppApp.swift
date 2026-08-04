import OffstagePort
import SwiftUI

@main
struct NotesAppApp: App {
    @StateObject private var store: NotesStore
    private var port: AgentPort?

    init() {
        let s = NotesStore()
        _store = StateObject(wrappedValue: s)
        // Semantic-action port (debug fixture): active only with --uitest-port <sock>.
        port = makeAgentPort(store: s)
        Self.setupDebugFixtures()
    }

    private static func setupDebugFixtures() {
        // Debug drag pad: a plain AppKit tracking view that logs every
        // mouseDown/Dragged/Up with window coordinates, so an external CGEventPostToPid
        // probe can verify synthetic mouse sequences reach a background app.
        if let i = ProcessInfo.processInfo.arguments.firstIndex(of: "--uitest-dragpad"),
           ProcessInfo.processInfo.arguments.count > i + 1 {
            DragPad.open(logPath: ProcessInfo.processInfo.arguments[i + 1])
        }
        // Debug event tap: log received keyDowns so an external
        // CGEventPostToPid probe can verify delivery to this (possibly background) app.
        if let i = ProcessInfo.processInfo.arguments.firstIndex(of: "--uitest-eventlog"),
           ProcessInfo.processInfo.arguments.count > i + 1 {
            let path = ProcessInfo.processInfo.arguments[i + 1]
            NSEvent.addLocalMonitorForEvents(matching: .keyDown) { ev in
                let line = "keyDown code=\(ev.keyCode) t=\(Date().timeIntervalSince1970)\n"
                if let d = line.data(using: .utf8) {
                    if let h = FileHandle(forWritingAtPath: path) {
                        h.seekToEndOfFile(); h.write(d); try? h.close()
                    } else {
                        try? d.write(to: URL(fileURLWithPath: path))
                    }
                }
                return ev
            }
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("New Note") { store.addNote() }
                    .keyboardShortcut("n", modifiers: [.command, .shift])
                Button("Delete Note") {
                    if let id = store.selection { store.deleteNote(id: id) }
                }
                .keyboardShortcut(.delete, modifiers: [.command])
            }
        }
    }
}
