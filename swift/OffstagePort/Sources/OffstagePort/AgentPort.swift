import Foundation

/// Debug-only semantic-action port an app embeds behind `--uitest-port <path>`.
///
/// Protocol: line-delimited JSON over a UNIX domain socket. The app supplies a
/// handler that receives the decoded command object and returns the reply
/// object; the handler always runs on the **main thread**, so it may touch the
/// app's stores directly. Echo-after-mutate is the convention: every reply
/// should include the store state AFTER the mutation, so callers can verify.
///
/// Two caveats that must survive into any consumer's verifier design:
///  * ground truth stays in the app's persistence (UserDefaults etc.); claims
///    built on the port's echo alone are model-level — the port bypasses all
///    UI input plumbing;
///  * ship the port only in debug/QA builds.
///
/// Keep a strong reference to the instance for the app's lifetime (e.g. a
/// property on your `App` struct) — the accept loop holds `self` weakly and
/// stops when the port is deallocated.
public final class AgentPort: @unchecked Sendable {
    public typealias Handler = ([String: Any]) -> [String: Any]

    private let path: String
    private let handler: Handler
    private var fd: Int32 = -1

    /// Start listening at `path` (an existing socket file is replaced).
    /// `path` must fit `sun_path` (~104 bytes) — prefer short `/tmp` paths.
    public init(path: String, handler: @escaping Handler) {
        precondition(path.utf8.count < 104, "socket path too long for sun_path: \(path)")
        self.path = path
        self.handler = handler
        start()
    }

    /// Convenience: reads the port path from the launch arguments and returns
    /// a running port, or nil when the flag is absent (normal runs).
    ///
    /// Accepts `-uitest-port <path>` (the harness's form — AppKit strips
    /// `-key value` pairs, so they never masquerade as documents to open;
    /// leftover bare args like `--uitest-port` suppress SwiftUI window
    /// creation once three of them accumulate) and `--uitest-port <path>` for
    /// manual runs.
    public static func fromLaunchArguments(handler: @escaping Handler) -> AgentPort? {
        if let path = UserDefaults.standard.string(forKey: "uitest-port") {
            return AgentPort(path: path, handler: handler)
        }
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "--uitest-port"), args.count > i + 1 else {
            return nil
        }
        return AgentPort(path: args[i + 1], handler: handler)
    }

    /// True when the harness asked for a fresh-user launch (`-uitest-reset 1`
    /// or `--uitest-reset`). Apps should drop their persistent domain and all
    /// window/split autosave state when this is set.
    public static var resetRequested: Bool {
        UserDefaults.standard.bool(forKey: "uitest-reset")
            || ProcessInfo.processInfo.arguments.contains("--uitest-reset")
    }

    private func start() {
        unlink(path)
        fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { return }
        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        _ = path.withCString { cs in
            withUnsafeMutableBytes(of: &addr.sun_path) { buf in
                strncpy(buf.baseAddress!.assumingMemoryBound(to: CChar.self), cs, buf.count - 1)
            }
        }
        let len = socklen_t(MemoryLayout<sockaddr_un>.size)
        let bindOK = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, len) }
        }
        guard bindOK == 0, listen(fd, 4) == 0 else { return }
        DispatchQueue.global().async { [weak self] in self?.acceptLoop() }
    }

    private func acceptLoop() {
        while true {
            let client = accept(fd, nil, nil)
            guard client >= 0 else { break }
            var data = Data()
            var buf = [UInt8](repeating: 0, count: 4096)
            while true {
                let n = read(client, &buf, buf.count)
                guard n > 0 else { break }
                data.append(contentsOf: buf[0..<n])
                if let nl = data.firstIndex(of: 0x0A) {
                    let line = data[..<nl]
                    let reply = handle(Data(line))
                    _ = reply.withUnsafeBytes { write(client, $0.baseAddress, reply.count) }
                    data.removeSubrange(...nl)
                }
            }
            close(client)
        }
    }

    private func handle(_ line: Data) -> Data {
        guard let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any],
              obj["cmd"] is String else {
            return Data("{\"error\":\"bad json\"}\n".utf8)
        }
        // Built-in settle barrier, answered without involving the app handler:
        // the reply still hops through the main thread, so one round-trip
        // proves every main-thread task queued before it (button actions,
        // store writes) has completed.
        if obj["cmd"] as? String == "offstage.ping" {
            if !Thread.isMainThread { DispatchQueue.main.sync {} }
            return Data("{\"ok\":1}\n".utf8)
        }
        var replyObj: [String: Any] = [:]
        if Thread.isMainThread {
            replyObj = handler(obj)
        } else {
            DispatchQueue.main.sync { replyObj = self.handler(obj) }
        }
        guard let reply = try? JSONSerialization.data(withJSONObject: replyObj) else {
            return Data("{\"error\":\"unencodable reply\"}\n".utf8)
        }
        return reply + Data("\n".utf8)
    }
}
