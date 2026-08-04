// sckwin: SCK-capture the main content window of a pid. Prefers windows with a
// non-empty title: SwiftUI apps carry phantom untitled windows (tab-bar strips,
// ghosts) that can tie or beat the content window on area alone and capture as
// blank (observed on a 500x500 fixture window).
// Usage: sckwin <pid> <out.png>
import ScreenCaptureKit
import AppKit

guard CommandLine.arguments.count > 2, let pid = pid_t(CommandLine.arguments[1]) else {
    print("usage: sckwin <pid> <out.png>"); exit(64)
}
let out = CommandLine.arguments[2]
_ = NSApplication.shared

Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
        let wins = content.windows.filter { $0.owningApplication?.processID == pid }
        let titled = wins.filter { !($0.title ?? "").isEmpty }
        let pool = titled.isEmpty ? wins : titled
        guard let window = pool.max(by: { $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height }) else {
            print("ERROR: no window for pid \(pid)"); exit(1)
        }
        print("WINDOW title='\(window.title ?? "")' frame=\(Int(window.frame.width))x\(Int(window.frame.height))")
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let cfg = SCStreamConfiguration()
        cfg.width = Int(window.frame.width) * 2
        cfg.height = Int(window.frame.height) * 2
        cfg.showsCursor = false
        let img = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg)
        let rep = NSBitmapImageRep(cgImage: img)
        try rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: out))
        print("OK \(img.width)x\(img.height)")
        exit(0)
    } catch {
        print("ERROR: \(error)"); exit(1)
    }
}
RunLoop.main.run()
