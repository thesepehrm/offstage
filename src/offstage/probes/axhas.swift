// axhas: does an element with the given accessibility identifier exist in the app's
// windows (menu bar excluded)? Prints HAS=1/0. Usage: axhas <pid-or-bundle-id> <identifier>
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

guard CommandLine.arguments.count > 2 else { print("usage: axhas <pid-or-bundle-id> <identifier>"); exit(64) }
guard let app = offstageApp(CommandLine.arguments[1]) else { print("NOAPP"); exit(1) }
let ax = AXUIElementCreateApplication(app.processIdentifier)
let want = CommandLine.arguments[2]

func attr(_ el: AXUIElement, _ n: String) -> CFTypeRef? {
    var v: CFTypeRef?
    return AXUIElementCopyAttributeValue(el, n as CFString, &v) == .success ? v : nil
}
func find(_ el: AXUIElement) -> Bool {
    if (attr(el, kAXRoleAttribute) as? String) == "AXMenuBar" { return false }
    if (attr(el, kAXIdentifierAttribute) as? String) == want { return true }
    for k in (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? [] {
        if find(k) { return true }
    }
    return false
}
print("HAS=\(find(ax) ? 1 : 0)")
