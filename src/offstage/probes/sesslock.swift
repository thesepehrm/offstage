import CoreGraphics
if let d = CGSessionCopyCurrentDictionary() as? [String: Any] {
    for k in ["kCGSSessionOnConsoleKey", "CGSSessionScreenIsLocked", "kCGSessionLongUserNameKey"] {
        print(k, "=", d[k] ?? "nil")
    }
} else { print("no session") }
