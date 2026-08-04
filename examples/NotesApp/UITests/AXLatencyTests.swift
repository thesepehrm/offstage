import XCTest

// Substrate check 1d: action → tree-settled latency, measured by tight polling of the
// AX-derived element tree after each action. Proxy measurement: XCUITest queries go
// through testmanagerd's AX snapshotting, so this is an upper bound on AX settle time
// plus one query round-trip.
@MainActor
final class AXLatencyTests: XCTestCase {
    func testActionToTreeSettledLatency() throws {
        let app = XCUIApplication()
        app.launch()
        let add = app.buttons["addNote"].firstMatch
        XCTAssertTrue(add.waitForExistence(timeout: 5))

        var samples: [Double] = []
        let reps = 20
        for i in 0..<reps {
            let before = app.outlines.cells.count
            add.click()
            let t0 = Date()
            var settled = false
            while Date().timeIntervalSince(t0) < 5 {
                if app.outlines.cells.count == before + 1 { settled = true; break }
                usleep(10_000) // 10 ms poll
            }
            XCTAssertTrue(settled, "tree never settled on rep \(i)")
            samples.append(Date().timeIntervalSince(t0) * 1000)
        }
        let sorted = samples.sorted()
        let p50 = sorted[reps / 2]
        let p95 = sorted[Int(Double(reps) * 0.95) - 1]
        print("AX_LATENCY_MS samples=\(reps) p50=\(Int(p50)) p95=\(Int(p95)) "
              + "min=\(Int(sorted.first!)) max=\(Int(sorted.last!))")
    }
}
