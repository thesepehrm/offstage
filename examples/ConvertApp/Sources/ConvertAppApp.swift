import OffstagePort
import SwiftUI

@main
struct ConvertAppApp: App {
    @StateObject private var store: ConvertStore
    private var port: AgentPort?

    init() {
        let s = ConvertStore()
        _store = StateObject(wrappedValue: s)
        // Semantic-action port (debug fixture): active only with --uitest-port <sock>.
        port = makeAgentPort(store: s)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
