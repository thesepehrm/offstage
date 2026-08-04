import Foundation
import OffstagePort
import Combine

enum LengthUnit: String, CaseIterable, Codable, Identifiable {
    case m, km, mi, ft
    var id: String { rawValue }

    /// Meters per one of this unit.
    var meters: Double {
        switch self {
        case .m: return 1
        case .km: return 1000
        case .mi: return 1609.344
        case .ft: return 0.3048
        }
    }
}

enum TempUnit: String, CaseIterable, Codable, Identifiable {
    case c = "C", f = "F", k = "K"
    var id: String { rawValue }
}

final class ConvertStore: ObservableObject {
    @Published var lengthInput: String = "1" { didSet { persist() } }
    @Published var lengthFrom: LengthUnit = .m { didSet { persist() } }
    @Published var lengthTo: LengthUnit = .km { didSet { persist() } }
    @Published var tempInput: String = "0" { didSet { persist() } }
    @Published var tempFrom: TempUnit = .c { didSet { persist() } }
    @Published var tempTo: TempUnit = .f { didSet { persist() } }

    private let defaultsKey = "convert.v1"
    private let defaults: UserDefaults
    private var restoring = false

    private struct Saved: Codable {
        var lengthInput: String
        var lengthFrom: LengthUnit
        var lengthTo: LengthUnit
        var tempInput: String
        var tempFrom: TempUnit
        var tempTo: TempUnit
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if AgentPort.resetRequested {
            // Full fresh-user state: also drops NSWindow frame autosave, which otherwise
            // leaks layout across runs. Load-bearing for goldens.
            if let bid = Bundle.main.bundleIdentifier {
                defaults.removePersistentDomain(forName: bid)
            }
            defaults.removeObject(forKey: defaultsKey)
        }
        if let data = defaults.data(forKey: defaultsKey),
           let saved = try? JSONDecoder().decode(Saved.self, from: data) {
            restoring = true
            lengthInput = saved.lengthInput
            lengthFrom = saved.lengthFrom
            lengthTo = saved.lengthTo
            tempInput = saved.tempInput
            tempFrom = saved.tempFrom
            tempTo = saved.tempTo
            restoring = false
        }
    }

    private func persist() {
        guard !restoring else { return }
        let saved = Saved(lengthInput: lengthInput, lengthFrom: lengthFrom, lengthTo: lengthTo,
                          tempInput: tempInput, tempFrom: tempFrom, tempTo: tempTo)
        if let data = try? JSONEncoder().encode(saved) {
            defaults.set(data, forKey: defaultsKey)
        }
    }

    // MARK: - Conversion math

    static func convert(length value: Double, from: LengthUnit, to: LengthUnit) -> Double {
        value * from.meters / to.meters
    }

    static func convert(temp value: Double, from: TempUnit, to: TempUnit) -> Double {
        let celsius: Double
        switch from {
        case .c: celsius = value
        case .f: celsius = (value - 32) * 5 / 9
        case .k: celsius = value - 273.15
        }
        switch to {
        case .c: return celsius
        case .f: return celsius * 9 / 5 + 32
        case .k: return celsius + 273.15
        }
    }

    static func format(_ value: Double) -> String {
        String(format: "%.6g", value)
    }

    // MARK: - Live results

    var lengthResult: String {
        guard let v = Double(lengthInput.trimmingCharacters(in: .whitespaces)) else { return "—" }
        return Self.format(Self.convert(length: v, from: lengthFrom, to: lengthTo))
            + " \(lengthTo.rawValue)"
    }

    var tempResult: String {
        guard let v = Double(tempInput.trimmingCharacters(in: .whitespaces)) else { return "—" }
        return Self.format(Self.convert(temp: v, from: tempFrom, to: tempTo))
            + " °\(tempTo.rawValue)"
    }

    func swapLengthUnits() {
        (lengthFrom, lengthTo) = (lengthTo, lengthFrom)
    }
}
