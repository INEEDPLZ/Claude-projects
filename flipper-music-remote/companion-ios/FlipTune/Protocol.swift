import Foundation

/// FlipTune wire protocol — mirrors flipper_app/fliptune_protocol.h.
/// Frame: 0xA5 | type | len_lo | len_hi | payload | xor(type, len, payload)
enum FT {
    static let sync: UInt8 = 0xA5
    static let artSize = 48
    static let artBytes = artSize * artSize / 8
    static let artChunk = 128

    enum Msg: UInt8 {
        case track = 0x01, state = 0x02, artChunk = 0x03, artDone = 0x04, artNone = 0x05
        case command = 0x10
    }

    enum Cmd: UInt8 {
        case playPause = 1, next, prev, volUp, volDown, seekFwd, seekBack, sync, poll
    }

    static func frame(_ type: Msg, _ payload: Data = Data()) -> Data {
        let n = payload.count
        var out = Data([sync, type.rawValue, UInt8(n & 0xFF), UInt8(n >> 8)])
        out.append(payload)
        var chk: UInt8 = 0
        for b in out.dropFirst() { chk ^= b }
        out.append(chk)
        return out
    }

    static func le32(_ v: UInt32) -> Data {
        Data([UInt8(v & 0xFF), UInt8((v >> 8) & 0xFF), UInt8((v >> 16) & 0xFF), UInt8(v >> 24)])
    }

    static func trackFrame(title: String, artist: String, album: String) -> Data {
        var p = Data()
        for s in [title, artist, album] {
            p.append(contentsOf: Array(ascii(s).utf8))
            p.append(0)
        }
        return frame(.track, p)
    }

    static func stateFrame(playing: Bool, elapsed: TimeInterval, duration: TimeInterval, volume: Int?) -> Data {
        var p = Data([playing ? 1 : 0])
        p.append(le32(UInt32(max(0, elapsed) * 1000)))
        p.append(le32(UInt32(max(0, duration) * 1000)))
        p.append(volume.map { UInt8(clamping: max(0, min(100, $0))) } ?? 255)
        return frame(.state, p)
    }

    static func artFrames(_ bits: Data) -> [Data] {
        var frames: [Data] = []
        var off = 0
        while off < bits.count {
            let end = min(off + artChunk, bits.count)
            var p = Data([UInt8(off & 0xFF), UInt8(off >> 8)])
            p.append(bits.subdata(in: off..<end))
            frames.append(frame(.artChunk, p))
            off = end
        }
        frames.append(frame(.artDone))
        return frames
    }

    /// The Flipper's fonts are ASCII only: transliterate, strip accents, drop the rest.
    static func ascii(_ s: String, limit: Int = 63) -> String {
        let latin = s.applyingTransform(.toLatin, reverse: false) ?? s
        let plain = latin.applyingTransform(.stripDiacritics, reverse: false) ?? latin
        var out = String.UnicodeScalarView()
        out.append(contentsOf: plain.unicodeScalars.lazy.filter { $0.value >= 0x20 && $0.value < 0x7F }.prefix(limit))
        return String(out)
    }
}

/// Stream parser for Flipper -> phone frames (only Command frames today).
final class FrameParser {
    private var buf = [UInt8]()

    func feed(_ data: Data) -> [(FT.Msg, [UInt8])] {
        buf.append(contentsOf: data)
        var out: [(FT.Msg, [UInt8])] = []
        while true {
            guard let i = buf.firstIndex(of: FT.sync) else { buf.removeAll(); break }
            buf.removeFirst(i)
            guard buf.count >= 4 else { break }
            let n = Int(buf[2]) | Int(buf[3]) << 8
            if n > 512 { buf.removeFirst(); continue }
            guard buf.count >= 5 + n else { break }
            var chk: UInt8 = 0
            for b in buf[1..<(4 + n)] { chk ^= b }
            if chk == buf[4 + n] {
                if let t = FT.Msg(rawValue: buf[1]) { out.append((t, Array(buf[4..<(4 + n)]))) }
                buf.removeFirst(5 + n)
            } else {
                buf.removeFirst()
            }
        }
        return out
    }
}
