// axscan: count accessibility hygiene defects in an app's UI.
// Counts (a) AXButtons with no title and no description anywhere in the app windows,
// (b) empty-title AXMenuItems in the menu bar (separators excluded: they expose no
// AXEnabled attribute). Usage: axscan <bundle-id>
import ApplicationServices
import AppKit

guard CommandLine.arguments.count > 1 else { print("usage: axscan <bundle-id>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(
        withBundleIdentifier: CommandLine.arguments[1]).first else { print("NOAPP"); exit(1) }
let ax = AXUIElementCreateApplication(app.processIdentifier)

func attr(_ el: AXUIElement, _ n: String) -> CFTypeRef? {
    var v: CFTypeRef?
    return AXUIElementCopyAttributeValue(el, n as CFString, &v) == .success ? v : nil
}
func str(_ el: AXUIElement, _ n: String) -> String { (attr(el, n) as? String) ?? "" }
func kids(_ el: AXUIElement) -> [AXUIElement] { (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }

var unlabelledButtons: [String] = []
var emptyMenuItems = 0

func scanWin(_ el: AXUIElement) {
    let role = str(el, kAXRoleAttribute)
    if role == "AXMenuBar" { return }
    if role == "AXButton" {
        let t = str(el, kAXTitleAttribute), d = str(el, kAXDescriptionAttribute)
        if t.isEmpty && d.isEmpty {
            unlabelledButtons.append(str(el, kAXIdentifierAttribute))
        }
    }
    for k in kids(el) { scanWin(k) }
}
func scanMenu(_ el: AXUIElement) {
    let role = str(el, kAXRoleAttribute)
    if role == "AXMenuItem" {
        let t = str(el, kAXTitleAttribute)
        let enabledPresent = attr(el, kAXEnabledAttribute) != nil
        if t.isEmpty && enabledPresent { emptyMenuItems += 1 }
    }
    for k in kids(el) { scanMenu(k) }
}

scanWin(ax)
if let mb = attr(ax, kAXMenuBarAttribute) { scanMenu(mb as! AXUIElement) }
print("UNLABELLED_BUTTONS=\(unlabelledButtons.count) ids=\(unlabelledButtons)")
print("EMPTY_MENU_ITEMS=\(emptyMenuItems)")
