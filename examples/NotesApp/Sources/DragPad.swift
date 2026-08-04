import AppKit

// Debug surface: logs raw mouse tracking to a file. Not compiled out in
// release because the whole app is a test fixture; gated behind --uitest-dragpad.
final class DragPadView: NSView {
    let logPath: String

    init(frame: NSRect, logPath: String) {
        self.logPath = logPath
        super.init(frame: frame)
    }

    required init?(coder: NSCoder) { fatalError() }

    private func log(_ kind: String, _ event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        let line = "\(kind) x=\(Int(p.x)) y=\(Int(p.y)) t=\(Date().timeIntervalSince1970)\n"
        if let d = line.data(using: .utf8) {
            if let h = FileHandle(forWritingAtPath: logPath) {
                h.seekToEndOfFile(); h.write(d); try? h.close()
            } else {
                try? d.write(to: URL(fileURLWithPath: logPath))
            }
        }
    }

    // Without this, the first click on an inactive window is swallowed by activation
    // semantics — the exact failure mode 006 is probing.
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseDown(with event: NSEvent) { log("down", event) }
    override func mouseDragged(with event: NSEvent) { log("drag", event) }
    override func mouseUp(with event: NSEvent) { log("up", event) }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.systemTeal.setFill()
        dirtyRect.fill()
    }
}

final class ButtonLog: NSObject {
    let logPath: String
    init(logPath: String) { self.logPath = logPath }

    @objc func pressed() {
        let line = "buttonPressed t=\(Date().timeIntervalSince1970)\n"
        if let d = line.data(using: .utf8), let h = FileHandle(forWritingAtPath: logPath) {
            h.seekToEndOfFile(); h.write(d); try? h.close()
        }
    }
}

@MainActor
enum DragPad {
    static var window: NSWindow?

    static func open(logPath: String) {
        DispatchQueue.main.async {
            let win = NSWindow(contentRect: NSRect(x: 100, y: 100, width: 300, height: 300),
                               styleMask: [.titled], backing: .buffered, defer: false)
            win.title = "DragPad"
            let pad = DragPadView(frame: NSRect(x: 0, y: 0, width: 300, height: 300),
                                  logPath: logPath)
            let button = NSButton(title: "PadButton", target: nil, action: nil)
            button.frame = NSRect(x: 100, y: 10, width: 100, height: 30)
            let holder = ButtonLog(logPath: logPath)
            button.target = holder
            button.action = #selector(ButtonLog.pressed)
            objc_setAssociatedObject(win, "holder", holder, .OBJC_ASSOCIATION_RETAIN)
            pad.addSubview(button)
            win.contentView = pad
            win.orderBack(nil)
            win.makeKey() // key within the (inactive) app, so mouse dispatch has a target
            window = win
            // CGEvent.postToPid mouse events reach the queue with window == nil (AppKit
            // associates windows via the real cursor, which is elsewhere). This shim
            // re-targets them at the window under the event's own screen location and
            // dispatches directly — the "cooperative app" half of the 006 finding.
            NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .leftMouseDragged, .leftMouseUp]) { ev in
                guard ev.window == nil else { return ev }
                let screenPoint = ev.locationInWindow // global, bottom-origin, when window is nil
                guard let target = NSApp.windows.first(where: {
                    $0.isVisible && $0.frame.contains(screenPoint)
                }) else { return ev }
                let local = target.convertPoint(fromScreen: screenPoint)
                guard let retargeted = NSEvent.mouseEvent(
                    with: ev.type, location: local, modifierFlags: ev.modifierFlags,
                    timestamp: ev.timestamp, windowNumber: target.windowNumber, context: nil,
                    eventNumber: ev.eventNumber, clickCount: ev.clickCount,
                    pressure: ev.pressure) else { return ev }
                target.sendEvent(retargeted)
                return nil // swallow the unrouted original
            }
            // Same bridge for key events: pid-posted keys reach the queue with no window;
            // route them to the key (or main) window so the focused field receives them.
            NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp]) { ev in
                guard ev.window == nil,
                      let target = NSApp.keyWindow ?? NSApp.mainWindow else { return ev }
                target.sendEvent(ev)
                return nil
            }
        }
    }
}
