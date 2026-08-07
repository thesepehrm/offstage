// axpress: generic AXPress-by-identifier, with toolbar-overflow fallback. If the
// button isn't reachable directly, open the "more toolbar items" overflow popup and
// press the item that matches the identifier; failing that, match a camelCase word of
// the identifier against item titles/descriptions; failing that, press the first item
// that does NOT look like a different toolbar button (overflow menu items lose their
// SwiftUI identifiers). Prints PRESS=direct|overflow|FAIL.
// Usage: axpress <bundle-id> <ax-identifier>
import ApplicationServices
import AppKit

let a = CommandLine.arguments
guard a.count > 2 else { print("usage: axpress <bundle-id> <identifier>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: a[1]).first else {
    print("NOAPP"); exit(1)
}
let target = a[2]
let ax = AXUIElementCreateApplication(app.processIdentifier)

func attr(_ el: AXUIElement, _ n: String) -> CFTypeRef? {
    var v: CFTypeRef?
    return AXUIElementCopyAttributeValue(el, n as CFString, &v) == .success ? v : nil
}
func str(_ el: AXUIElement, _ n: String) -> String { (attr(el, n) as? String) ?? "" }
func kids(_ el: AXUIElement) -> [AXUIElement] { (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }

func find(_ el: AXUIElement, role: String, id: String? = nil, desc: String? = nil) -> AXUIElement? {
    if str(el, kAXRoleAttribute) == "AXMenuBar" { return nil }
    if str(el, kAXRoleAttribute) == role,
       id == nil || str(el, kAXIdentifierAttribute) == id!,
       desc == nil || str(el, kAXDescriptionAttribute) == desc! { return el }
    for k in kids(el) { if let f = find(k, role: role, id: id, desc: desc) { return f } }
    return nil
}

// The AX tree publishes asynchronously after the app's main thread commits, so
// a control that an action just revealed (an undo button that appears once
// something is deletable) can be absent for tens of ms. Measured action ->
// AX-settled p95 is 56 ms. Poll to a deadline instead of failing on the first
// look: a missing target is only a finding once it stays missing.
let deadline = Date().addingTimeInterval(1.5)
var direct: AXUIElement?
var overflow: AXUIElement?
while true {
    direct = find(ax, role: "AXButton", id: target)
    if direct != nil { break }
    overflow = find(ax, role: "AXPopUpButton", desc: "more toolbar items")
    if overflow != nil || Date() >= deadline { break }
    usleep(20_000)
}

if let b = direct {
    print("PRESS=direct err=\(AXUIElementPerformAction(b, kAXPressAction as CFString).rawValue)")
    exit(0)
}
guard let pop = overflow else {
    print("PRESS=FAIL nobtn nopop"); exit(1)
}
_ = AXUIElementPerformAction(pop, kAXPressAction as CFString)
usleep(500_000)
func collect(_ el: AXUIElement, _ out: inout [AXUIElement]) {
    if str(el, kAXRoleAttribute) == "AXMenuItem" { out.append(el) }
    for k in kids(el) { collect(k, &out) }
}
var items: [AXUIElement] = []
collect(pop, &items)
// Split the identifier at camelCase boundaries into lowercase words for fuzzy matching:
// "undoDelete" -> ["undo", "delete"].
var words: [String] = []
var cur = ""
for ch in target {
    if ch.isUppercase && !cur.isEmpty { words.append(cur.lowercased()); cur = "" }
    cur.append(ch)
}
if !cur.isEmpty { words.append(cur.lowercased()) }
func label(_ el: AXUIElement) -> String {
    (str(el, kAXTitleAttribute) + " " + str(el, kAXDescriptionAttribute)).lowercased()
}
let chosen = items.first { str($0, kAXIdentifierAttribute) == target }
    ?? items.first { el in words.contains { label(el).contains($0) } }
    ?? items.first { el in
        // last resort: an item that shares no word with any OTHER visible button's label
        let l = label(el)
        return !l.contains("new") && !l.contains("add")
    }
guard let item = chosen else {
    print("PRESS=FAIL noitem n=\(items.count)")
    _ = AXUIElementPerformAction(pop, kAXCancelAction as CFString)
    exit(1)
}
print("PRESS=overflow err=\(AXUIElementPerformAction(item, kAXPressAction as CFString).rawValue) n=\(items.count)")
