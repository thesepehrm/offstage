import XCTest
@testable import ConvertApp

final class ConvertStoreTests: XCTestCase {

    // MARK: - Length

    func testMetersToKilometers() {
        XCTAssertEqual(ConvertStore.convert(length: 2500, from: .m, to: .km),
                       2.5, accuracy: 1e-9)
    }

    func testMilesToMeters() {
        XCTAssertEqual(ConvertStore.convert(length: 1, from: .mi, to: .m),
                       1609.344, accuracy: 1e-9)
    }

    func testFeetToMiles() {
        XCTAssertEqual(ConvertStore.convert(length: 5280, from: .ft, to: .mi),
                       1.0, accuracy: 1e-9)
    }

    func testLengthRoundTrip() {
        let v = 123.456
        let out = ConvertStore.convert(length: v, from: .km, to: .ft)
        let back = ConvertStore.convert(length: out, from: .ft, to: .km)
        XCTAssertEqual(back, v, accuracy: 1e-9)
    }

    // MARK: - Temperature

    func testTemperatureIdentity() {
        XCTAssertEqual(ConvertStore.convert(temp: 37.5, from: .c, to: .c),
                       37.5, accuracy: 1e-12)
    }

    func testCelsiusToFahrenheit() {
        XCTAssertEqual(ConvertStore.convert(temp: 100, from: .c, to: .f),
                       212, accuracy: 1e-9)
    }

    func testFahrenheitToKelvin() {
        XCTAssertEqual(ConvertStore.convert(temp: 32, from: .f, to: .k),
                       273.15, accuracy: 1e-9)
    }

    func testTemperatureRoundTrip() {
        let v = -40.0
        let out = ConvertStore.convert(temp: v, from: .f, to: .k)
        let back = ConvertStore.convert(temp: out, from: .k, to: .f)
        XCTAssertEqual(back, v, accuracy: 1e-9)
    }

    // MARK: - Store behaviour

    func testSwapUnits() {
        let store = ConvertStore(defaults: UserDefaults(suiteName: "test.swap")!)
        store.lengthFrom = .mi
        store.lengthTo = .ft
        store.swapLengthUnits()
        XCTAssertEqual(store.lengthFrom, .ft)
        XCTAssertEqual(store.lengthTo, .mi)
    }

    func testResultForBadInputIsPlaceholder() {
        let store = ConvertStore(defaults: UserDefaults(suiteName: "test.bad")!)
        store.lengthInput = "not a number"
        XCTAssertEqual(store.lengthResult, "—")
    }
}
