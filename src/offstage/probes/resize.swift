// resize: set an app's first window to WxH via AX.
// Sets the first app window to WxH via AX. Usage: resize <pid-or-bundle-id> <w> <h>
import ApplicationServices
import AppKit

// Target token: a pid or a bundle id. A bundle id is ambiguous the moment the
// same app exists in more than one build — worktrees, a release beside a debug
// build — and `.first` then picks an arbitrary one. A pid names exactly one
// process, so the driver passes that whenever it knows which instance is its
// own.
func offstageApp(_ token: String) -> NSRunningApplication? {
    if let pid = pid_t(token) {
        return NSRunningApplication(processIdentifier: pid)
    }
    return NSRunningApplication.runningApplications(withBundleIdentifier: token).first
}
guard CommandLine.arguments.count > 3 else { print("usage: resize <pid-or-bundle-id> <w> <h>"); exit(64) }
guard let app = offstageApp(CommandLine.arguments[1]) else { print("NOAPP"); exit(1) }
let ax = AXUIElementCreateApplication(app.processIdentifier)
var v: CFTypeRef?
AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &v)
guard let w = (v as? [AXUIElement])?.first else { print("NOWIN"); exit(1) }
var size = CGSize(width: Double(CommandLine.arguments[2])!, height: Double(CommandLine.arguments[3])!)
let sv = AXValueCreate(.cgSize, &size)!
print("RESIZE=\(AXUIElementSetAttributeValue(w, kAXSizeAttribute as CFString, sv).rawValue)")
