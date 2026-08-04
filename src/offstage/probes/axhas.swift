// axhas: does an element with the given accessibility identifier exist in the app's
// windows (menu bar excluded)? Prints HAS=1/0. Usage: axhas <bundle-id> <identifier>
import ApplicationServices
import AppKit

guard CommandLine.arguments.count > 2 else { print("usage: axhas <bundle-id> <identifier>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(
        withBundleIdentifier: CommandLine.arguments[1]).first else { print("NOAPP"); exit(1) }
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
