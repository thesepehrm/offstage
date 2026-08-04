import XCTest
@testable import OffstagePort

final class AgentPortTests: XCTestCase {
    /// Round-trip a command through a real UNIX socket and check line framing,
    /// main-thread handler execution, and echo-after-mutate.
    func testRoundTrip() throws {
        let path = "/tmp/osp-\(UUID().uuidString.prefix(8)).sock"
        defer { unlink(path) }
        var titles: [String] = []
        let port = AgentPort(path: path) { obj in
            XCTAssertTrue(Thread.isMainThread)
            if obj["cmd"] as? String == "add", let t = obj["title"] as? String {
                titles.append(t)
            }
            return ["titles": titles]
        }

        func send(_ obj: [String: Any]) throws -> [String: Any] {
            let fd = socket(AF_UNIX, SOCK_STREAM, 0)
            defer { close(fd) }
            var addr = sockaddr_un()
            addr.sun_family = sa_family_t(AF_UNIX)
            _ = path.withCString { cs in
                withUnsafeMutableBytes(of: &addr.sun_path) { buf in
                    strncpy(buf.baseAddress!.assumingMemoryBound(to: CChar.self), cs, buf.count - 1)
                }
            }
            let len = socklen_t(MemoryLayout<sockaddr_un>.size)
            let rc = withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { connect(fd, $0, len) }
            }
            XCTAssertEqual(rc, 0, "connect failed")
            let payload = try JSONSerialization.data(withJSONObject: obj) + Data("\n".utf8)
            _ = payload.withUnsafeBytes { write(fd, $0.baseAddress, payload.count) }
            var data = Data()
            var buf = [UInt8](repeating: 0, count: 4096)
            while !data.contains(0x0A) {
                let n = read(fd, &buf, buf.count)
                guard n > 0 else { break }
                data.append(contentsOf: buf[0..<n])
            }
            return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        }

        // The handler runs DispatchQueue.main.sync, so pump requests off-main
        // and keep the main run loop turning.
        let done = expectation(description: "round trips")
        var results: [[String: Any]] = []
        DispatchQueue.global().async {
            usleep(100_000) // let the listener come up
            results.append((try? send(["cmd": "state"])) ?? [:])
            results.append((try? send(["cmd": "add", "title": "A"])) ?? [:])
            results.append((try? send(["cmd": "state"])) ?? [:])
            done.fulfill()
        }
        withExtendedLifetime(port) { wait(for: [done], timeout: 10) }
        XCTAssertEqual(results.count, 3)
        guard results.count == 3 else { return }
        XCTAssertEqual(results[0]["titles"] as? [String], [])
        XCTAssertEqual(results[1]["titles"] as? [String], ["A"], "echo-after-mutate")
        XCTAssertEqual(results[2]["titles"] as? [String], ["A"])
    }

    func testBadJSON() throws {
        let path = "/tmp/osp-\(UUID().uuidString.prefix(8)).sock"
        defer { unlink(path) }
        let port = AgentPort(path: path) { _ in [:] }
        let done = expectation(description: "bad json reply")
        var reply = ""
        DispatchQueue.global().async {
            usleep(100_000)
            let fd = socket(AF_UNIX, SOCK_STREAM, 0)
            defer { close(fd) }
            var addr = sockaddr_un()
            addr.sun_family = sa_family_t(AF_UNIX)
            _ = path.withCString { cs in
                withUnsafeMutableBytes(of: &addr.sun_path) { buf in
                    strncpy(buf.baseAddress!.assumingMemoryBound(to: CChar.self), cs, buf.count - 1)
                }
            }
            let len = socklen_t(MemoryLayout<sockaddr_un>.size)
            _ = withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { connect(fd, $0, len) }
            }
            let payload = Data("not json\n".utf8)
            _ = payload.withUnsafeBytes { write(fd, $0.baseAddress, payload.count) }
            var data = Data()
            var buf = [UInt8](repeating: 0, count: 4096)
            while !data.contains(0x0A) {
                let n = read(fd, &buf, buf.count)
                guard n > 0 else { break }
                data.append(contentsOf: buf[0..<n])
            }
            reply = String(decoding: data, as: UTF8.self)
            done.fulfill()
        }
        withExtendedLifetime(port) { wait(for: [done], timeout: 10) }
        XCTAssertTrue(reply.contains("bad json"))
    }
}
