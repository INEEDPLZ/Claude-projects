import UIKit

/// Turns album artwork into the Flipper's 48x48 1-bit cover:
/// aspect-fill crop -> grayscale -> auto-contrast -> Atkinson dither -> pack (MSB first, 1 = ink).
enum ArtDither {
    static func convert(_ image: UIImage) -> (bits: Data, preview: UIImage)? {
        let n = FT.artSize
        guard let cg = image.cgImage else { return nil }

        var gray = [UInt8](repeating: 255, count: n * n)
        let ok: Bool = gray.withUnsafeMutableBytes { raw in
            guard let ctx = CGContext(
                data: raw.baseAddress, width: n, height: n, bitsPerComponent: 8, bytesPerRow: n,
                space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue
            ) else { return false }
            ctx.interpolationQuality = .high
            let w = CGFloat(cg.width), h = CGFloat(cg.height)
            let s = max(CGFloat(n) / w, CGFloat(n) / h)
            let dw = w * s, dh = h * s
            ctx.draw(cg, in: CGRect(x: (CGFloat(n) - dw) / 2, y: (CGFloat(n) - dh) / 2, width: dw, height: dh))
            return true
        }
        guard ok else { return nil }

        // Auto-contrast (2% / 98% percentiles) so dark covers don't turn into a black square.
        let sorted = gray.sorted()
        let lo = Float(sorted[sorted.count * 2 / 100])
        let hi = Float(sorted[sorted.count * 98 / 100])
        let range = max(hi - lo, 1)
        var px = gray.map { (Float($0) - lo) / range * 255 }

        // Atkinson dither: diffuses 6/8 of the error, which keeps highlights crisp on tiny screens.
        let taps = [(1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)]
        for y in 0..<n {
            for x in 0..<n {
                let i = y * n + x
                let old = px[i]
                let new: Float = old >= 128 ? 255 : 0
                px[i] = new
                let err = (old - new) / 8
                for (dx, dy) in taps {
                    let xx = x + dx, yy = y + dy
                    if xx >= 0, xx < n, yy < n { px[yy * n + xx] += err }
                }
            }
        }

        var bits = Data(count: FT.artBytes)
        for i in 0..<(n * n) where px[i] < 128 {
            bits[i >> 3] |= UInt8(0x80 >> (i & 7))
        }
        return (bits, preview(bits))
    }

    /// Renders packed bits the way the Flipper LCD shows them (black on orange).
    static func preview(_ bits: Data, scale: Int = 6) -> UIImage {
        let n = FT.artSize
        let size = CGSize(width: n * scale, height: n * scale)
        let fmt = UIGraphicsImageRendererFormat()
        fmt.scale = 1
        return UIGraphicsImageRenderer(size: size, format: fmt).image { ctx in
            UIColor(red: 1, green: 0.51, blue: 0, alpha: 1).setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
            UIColor.black.setFill()
            for i in 0..<(n * n) where bits[i >> 3] & UInt8(0x80 >> (i & 7)) != 0 {
                ctx.fill(CGRect(x: (i % n) * scale, y: (i / n) * scale, width: scale, height: scale))
            }
        }
    }
}
