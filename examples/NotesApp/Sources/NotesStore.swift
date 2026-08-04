import Foundation
import OffstagePort
import Combine

struct Note: Identifiable, Codable, Equatable {
    var id: UUID = UUID()
    var title: String
    var body: String
    var modified: Date = Date()
}

final class NotesStore: ObservableObject {
    @Published var notes: [Note] = [] { didSet { persist() } }
    @Published var selection: Note.ID?

    private var lastDeleted: (note: Note, index: Int)?
    private let defaultsKey = "notes.v1"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if AgentPort.resetRequested {
            // Full fresh-user state: also drops NSWindow frame and NSSplitView autosave,
            // which otherwise leak layout across runs and break goldens.
            if let bid = Bundle.main.bundleIdentifier {
                defaults.removePersistentDomain(forName: bid)
            }
            defaults.removeObject(forKey: defaultsKey)
        }
        if let data = defaults.data(forKey: defaultsKey),
           let saved = try? JSONDecoder().decode([Note].self, from: data) {
            notes = saved
        }
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(notes) {
            defaults.set(data, forKey: defaultsKey)
        }
    }

    @discardableResult
    func addNote(title: String = "Untitled") -> Note {
        let note = Note(title: title, body: "")
        notes.insert(note, at: 0)
        selection = note.id
        return note
    }

    func deleteNote(id: Note.ID) {
        guard let idx = notes.firstIndex(where: { $0.id == id }) else { return }
        lastDeleted = (notes[idx], idx)
        notes.remove(at: idx)
        if selection == id { selection = notes.first?.id }
    }

    func undoDelete() {
        guard let (note, idx) = lastDeleted else { return }
        notes.insert(note, at: min(idx, notes.count))
        selection = note.id
        lastDeleted = nil
    }

    func rename(id: Note.ID, to title: String) {
        guard let idx = notes.firstIndex(where: { $0.id == id }) else { return }
        notes[idx].title = title
        notes[idx].modified = Date()
    }

    func updateBody(id: Note.ID, to body: String) {
        guard let idx = notes.firstIndex(where: { $0.id == id }) else { return }
        notes[idx].body = body
        notes[idx].modified = Date()
    }
}
