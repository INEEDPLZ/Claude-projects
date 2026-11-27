import Foundation

/// Glue between the Music app and the Flipper.
final class Bridge: ObservableObject {
    let link = FlipperLink()
    let music = NowPlaying()

    @Published private(set) var lastCommand: FT.Cmd?
    private var sentTrackID: UInt64?

    init() {
        link.onReady = { [weak self] in self?.push(force: true) }
        link.onCommand = { [weak self] cmd in self?.handle(cmd) }
        music.onChange = { [weak self] in self?.push(force: false) }
    }

    private func handle(_ cmd: FT.Cmd) {
        switch cmd {
        case .sync:
            push(force: true)
        case .poll:
            push(force: false)
        default:
            lastCommand = cmd
            music.perform(cmd)
            // the player needs a moment to settle before we report back
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { self.push(force: false) }
        }
    }

    /// Sends state, plus track + art if the track changed (or `force`).
    func push(force: Bool) {
        guard link.isConnected else { return }
        music.refresh()
        guard let t = music.track else {
            link.send(FT.stateFrame(playing: false, elapsed: 0, duration: 0, volume: music.volume))
            return
        }
        if force || t.id != sentTrackID {
            sentTrackID = t.id
            link.send(FT.trackFrame(title: t.title, artist: t.artist, album: t.album))
            sendState()
            music.artBits { [weak self] bits in
                guard let self, self.sentTrackID == t.id else { return }
                self.link.send(bits.map(FT.artFrames) ?? [FT.frame(.artNone)])
            }
        } else {
            sendState()
        }
    }

    private func sendState() {
        link.send(FT.stateFrame(
            playing: music.isPlaying, elapsed: music.elapsed,
            duration: music.track?.duration ?? 0, volume: music.volume))
    }
}
