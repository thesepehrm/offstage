// axdump: compact generic AX summary of an app's windows.
// One line per element: Role "label" val="value" id=identifier — empty parts omitted,
// menu bar excluded, no indentation. Usage: axdump <bundle-id>
import ApplicationServices
import AppKit

guard CommandLine.arguments.count > 1 else { print("usage: axdump <bundle-id>"); exit(64) }
guard let app = NSRunningApplication.runningApplications(
        withBundleIdentifier: CommandLine.arguments[1]).first else { print("NOAPP"); exit(1) }
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
