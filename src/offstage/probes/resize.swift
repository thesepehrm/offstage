// resize: set an app's first window to WxH via AX.
// Sets the first app window to WxH via AX. Usage: resize <bundle-id> <w> <h>
import ApplicationServices
import AppKit
guard CommandLine.arguments.count > 3 else { print("usage: resize <bundle-id> <w> <h>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(
        withBundleIdentifier: CommandLine.arguments[1]).first else { print("NOAPP"); exit(1) }
let ax = AXUIElementCreateApplication(app.processIdentifier)
var v: CFTypeRef?
AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &v)
guard let w = (v as? [AXUIElement])?.first else { print("NOWIN"); exit(1) }
var size = CGSize(width: Double(CommandLine.arguments[2])!, height: Double(CommandLine.arguments[3])!)
let sv = AXValueCreate(.cgSize, &size)!
print("RESIZE=\(AXUIElementSetAttributeValue(w, kAXSizeAttribute as CFString, sv).rawValue)")
