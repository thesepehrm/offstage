// pixdiff: compare two PNGs pixel-by-pixel. Prints DIFF_PCT and DIM_MATCH.
// Usage: pixdiff <a.png> <b.png>
import AppKit

func load(_ p: String) -> CGImage? {
    NSImage(contentsOfFile: p)?.cgImage(forProposedRect: nil, context: nil, hints: nil)
}
func rgba(_ img: CGImage) -> [UInt8] {
    var buf = [UInt8](repeating: 0, count: img.width * img.height * 4)
    let ctx = CGContext(data: &buf, width: img.width, height: img.height, bitsPerComponent: 8,
                        bytesPerRow: img.width * 4, space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: img.width, height: img.height))
    return buf
}

let a = CommandLine.arguments
guard a.count == 3, let x = load(a[1]), let y = load(a[2]) else { print("LOAD_FAIL"); exit(1) }
guard x.width == y.width, x.height == y.height else {
    print("DIM_MATCH=0 a=\(x.width)x\(x.height) b=\(y.width)x\(y.height) DIFF_PCT=100.0")
    exit(0)
}
let (bx, by) = (rgba(x), rgba(y))
var diff = 0
for i in stride(from: 0, to: bx.count, by: 4) {
    if abs(Int(bx[i]) - Int(by[i])) > 2 || abs(Int(bx[i+1]) - Int(by[i+1])) > 2
        || abs(Int(bx[i+2]) - Int(by[i+2])) > 2 { diff += 1 }
}
let total = x.width * x.height
print("DIM_MATCH=1 DIFF_PCT=\(String(format: "%.4f", Double(diff) / Double(total) * 100)) diff=\(diff)/\(total)")
