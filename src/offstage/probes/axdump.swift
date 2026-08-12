// axdump: compact generic AX summary of an app's windows.
// One line per element: Role "label" val="value" id=identifier — empty parts omitted,
// menu bar excluded, no indentation. Usage: axdump <pid-or-bundle-id>
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

guard CommandLine.arguments.count > 1 else { print("usage: axdump <pid-or-bundle-id>"); exit(64) }
guard let app = offstageApp(CommandLine.arguments[1]) else { print("NOAPP"); exit(1) }
let ax = AXUIElementCreateApplication(app.processIdentifier)

func attr(_ el: AXUIElement, _ n: String) -> CFTypeRef? {
    var v: CFTypeRef?
    return AXUIElementCopyAttributeValue(el, n as CFString, &v) == .success ? v : nil
}
func str(_ el: AXUIElement, _ n: String) -> String { (attr(el, n) as? String) ?? "" }
func kids(_ el: AXUIElement) -> [AXUIElement] { (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }

// Structural roles carry no information of their own; skip the line, keep the children.
let SKIP: Set<String> = ["AXGroup", "AXSplitGroup", "AXScrollArea", "AXLayoutArea",
                         "AXLayoutItem", "AXUnknown", "AXGenericElement"]

func walk(_ el: AXUIElement, depth: Int = 0) {
    if depth > 40 { return }
    let role = str(el, kAXRoleAttribute)
    if role == "AXMenuBar" { return }
    if !role.isEmpty && !SKIP.contains(role) {
        let title = str(el, kAXTitleAttribute)
        let label = title.isEmpty ? str(el, kAXDescriptionAttribute) : title
        var value = ""
        if let v = attr(el, kAXValueAttribute) {
            if let s = v as? String { value = s }
            else if let n = v as? NSNumber { value = n.stringValue }
        }
        let id = str(el, kAXIdentifierAttribute)
        var line = role
        if !label.isEmpty { line += " \"\(label)\"" }
        if !value.isEmpty { line += " val=\"\(value)\"" }
        if !id.isEmpty { line += " id=\(id)" }
        print(line)
    }
    for k in kids(el) { walk(k, depth: depth + 1) }
}
walk(ax)
