// axmenu: AXPress a menu item by title on a background app, without opening the menu.
// Usage: axmenu <bundle-id> <menu-title> <item-title>
import ApplicationServices
import AppKit

let a = CommandLine.arguments
guard a.count > 3 else { print("usage: axmenu <bundle-id> <menu> <item>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: a[1]).first else {
    print("ERROR: app not running"); exit(1)
}
let ax = AXUIElementCreateApplication(app.processIdentifier)

func attr(_ el: AXUIElement, _ name: String) -> CFTypeRef? {
    var v: CFTypeRef?
    return AXUIElementCopyAttributeValue(el, name as CFString, &v) == .success ? v : nil
}
func title(_ el: AXUIElement) -> String { (attr(el, kAXTitleAttribute) as? String) ?? "" }
func children(_ el: AXUIElement) -> [AXUIElement] {
    (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? []
}

guard let menubar = attr(ax, kAXMenuBarAttribute) as! AXUIElement? else {
    print("ERROR: no menu bar"); exit(1)
}
guard let barItem = children(menubar).first(where: { title($0) == a[2] }) else {
    print("ERROR: no menu '\(a[2])' — have: \(children(menubar).map(title))"); exit(1)
}
guard let menu = children(barItem).first else { print("ERROR: menu empty"); exit(1) }
func findItem(_ menu: AXUIElement, _ name: String) -> AXUIElement? {
    for item in children(menu) {
        if title(item) == name { return item }
        for sub in children(item) { if let f = findItem(sub, name) { return f } }
    }
    return nil
}
guard let item = findItem(menu, a[3]) else {
    print("ERROR: no item '\(a[3])' — have: \(children(menu).map(title))"); exit(1)
}
let front0 = NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? "?"
let err = AXUIElementPerformAction(item, kAXPressAction as CFString)
usleep(300_000)
let front1 = NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? "?"
print("PRESS_ERR=\(err.rawValue) FRONT_BEFORE=\(front0) FRONT_AFTER=\(front1)")
