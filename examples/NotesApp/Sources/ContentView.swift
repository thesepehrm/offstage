import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: NotesStore
    @State private var renaming: Note.ID?
    @State private var renameText = ""

    var body: some View {
        NavigationSplitView {
            List(selection: $store.selection) {
                ForEach(store.notes) { note in
                    if renaming == note.id {
                        TextField("Title", text: $renameText, onCommit: {
                            store.rename(id: note.id, to: renameText)
                            renaming = nil
                        })
                        .accessibilityIdentifier("renameField")
                    } else {
                        Text(note.title)
                            .tag(note.id)
                            .accessibilityIdentifier("noteRow-\(note.title)")
                            .contextMenu {
                                Button("Rename") {
                                    renameText = note.title
                                    renaming = note.id
                                }
                                Button("Delete") { store.deleteNote(id: note.id) }
                            }
                    }
                }
                .onMove { from, to in
                    store.notes.move(fromOffsets: from, toOffset: to)
                }
            }
            .navigationSplitViewColumnWidth(min: 180, ideal: 220)
            .toolbar {
                ToolbarItem {
                    Button(action: { store.addNote() }) {
                        Label("New Note", systemImage: "square.and.pencil")
                    }
                    .accessibilityIdentifier("addNote")
                }
                ToolbarItem {
                    // Deliberately unlabelled icon-only button: the a11y-audit probe.
                    Button(action: { store.undoDelete() }) {
                        Image(systemName: "arrow.uturn.backward")
                            .accessibilityLabel("")
                    }
                    .accessibilityIdentifier("undoDelete")
                }
            }
        } detail: {
            if let id = store.selection,
               let idx = store.notes.firstIndex(where: { $0.id == id }) {
                DetailView(note: $store.notes[idx])
            } else {
                Text("No note selected")
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("emptyDetail")
            }
        }
        .navigationTitle("Notes")
    }
}

struct DetailView: View {
    @Binding var note: Note

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Title", text: $note.title)
                .font(.title2)
                .textFieldStyle(.plain)
                .accessibilityIdentifier("detailTitle")
            Divider()
            TextEditor(text: $note.body)
                .font(.body)
                .accessibilityIdentifier("detailBody")
        }
        .padding()
    }
}
