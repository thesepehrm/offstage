import Foundation
import OffstagePort

// Debug-only semantic-action port. Commands:
//   {"cmd":"state"}
//   {"cmd":"rename","index":i,"title":t}
//   {"cmd":"reorder","from":i,"to":j}
// Every response echoes the store's titles AFTER the mutation, so callers can
// verify — but ground truth remains UserDefaults, and verifier claims built on
// this port are model-level: it bypasses all UI input plumbing.
func makeAgentPort(store: NotesStore) -> AgentPort? {
    AgentPort.fromLaunchArguments { obj in
        switch obj["cmd"] as? String {
        case "rename":
            if let i = obj["index"] as? Int, let t = obj["title"] as? String,
               store.notes.indices.contains(i) {
                store.rename(id: store.notes[i].id, to: t)
            }
        case "reorder":
            if let f = obj["from"] as? Int, let t = obj["to"] as? Int,
               store.notes.indices.contains(f) {
                store.notes.move(fromOffsets: IndexSet(integer: f),
                                 toOffset: t > f ? t + 1 : t)
            }
        default:
            break // "state" and unknown commands just echo
        }
        return ["titles": store.notes.map(\.title)]
    }
}
