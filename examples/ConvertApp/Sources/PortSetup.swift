import Foundation
import OffstagePort

// Debug-only semantic-action port. Commands:
//   {"cmd":"state"}
//   {"cmd":"set","field":"lengthInput"|"tempInput","value":"<string>"}
//   {"cmd":"units","tab":"length"|"temp","from":"m","to":"km"}
// Every response echoes the full store state AFTER the mutation. Ground truth
// remains UserDefaults; verifier claims built on this port are model-level: it
// bypasses UI input.
func makeAgentPort(store: ConvertStore) -> AgentPort? {
    AgentPort.fromLaunchArguments { obj in
        switch obj["cmd"] as? String {
        case "set":
            if let field = obj["field"] as? String, let value = obj["value"] as? String {
                switch field {
                case "lengthInput": store.lengthInput = value
                case "tempInput": store.tempInput = value
                default: break
                }
            }
        case "units":
            let tab = obj["tab"] as? String
            if tab == "length" {
                if let f = obj["from"] as? String, let u = LengthUnit(rawValue: f) {
                    store.lengthFrom = u
                }
                if let t = obj["to"] as? String, let u = LengthUnit(rawValue: t) {
                    store.lengthTo = u
                }
            } else if tab == "temp" {
                if let f = obj["from"] as? String, let u = TempUnit(rawValue: f) {
                    store.tempFrom = u
                }
                if let t = obj["to"] as? String, let u = TempUnit(rawValue: t) {
                    store.tempTo = u
                }
            }
        default:
            break // "state" and unknown commands just echo
        }
        return [
            "lengthInput": store.lengthInput,
            "lengthFrom": store.lengthFrom.rawValue,
            "lengthTo": store.lengthTo.rawValue,
            "lengthResult": store.lengthResult,
            "tempInput": store.tempInput,
            "tempFrom": store.tempFrom.rawValue,
            "tempTo": store.tempTo.rawValue,
            "tempResult": store.tempResult,
        ]
    }
}
