import AVFoundation
import MediaPlayer
import UIKit

/// Reads and controls the Apple Music app through MPMusicPlayerController.systemMusicPlayer.
final class NowPlaying: ObservableObject {
    struct Track: Equatable {
        let id: UInt64
        let title, artist, album: String
        let duration: TimeInterval
    }

    @Published private(set) var track: Track?
    @Published private(set) var isPlaying = false
    @Published private(set) var artPreview: UIImage?
    @Published private(set) var authorized = MPMediaLibrary.authorizationStatus() == .authorized

    /// Fired when the track or the play state changes.
    var onChange: (() -> Void)?

    private let player = MPMusicPlayerController.systemMusicPlayer
    private var artCache: [String: Data?] = [:]

    init() {
        try? AVAudioSession.sharedInstance().setCategory(.ambient, options: [.mixWithOthers])
        try? AVAudioSession.sharedInstance().setActive(true) // needed to read outputVolume; never interrupts Music
        MPMediaLibrary.requestAuthorization { s in
            DispatchQueue.main.async {
                self.authorized = s == .authorized
                self.refresh()
            }
        }
        player.beginGeneratingPlaybackNotifications()
        let nc = NotificationCenter.default
        for name in [Notification.Name.MPMusicPlayerControllerNowPlayingItemDidChange,
                     .MPMusicPlayerControllerPlaybackStateDidChange] {
            nc.addObserver(forName: name, object: player, queue: .main) { [weak self] _ in
                self?.refresh()
                self?.onChange?()
            }
        }
        refresh()
    }

    func refresh() {
        isPlaying = player.playbackState == .playing
        guard let item = player.nowPlayingItem else { track = nil; return }
        track = Track(
            id: item.persistentID,
            title: item.title ?? "Unknown",
            artist: item.artist ?? item.albumArtist ?? "",
            album: item.albumTitle ?? "",
            duration: item.playbackDuration)
    }

    var elapsed: TimeInterval {
        let t = player.currentPlaybackTime
        return t.isFinite ? t : 0
    }

    var volume: Int { Int((AVAudioSession.sharedInstance().outputVolume * 100).rounded()) }

    // MARK: Artwork

    /// 1-bit cover for the current track, or nil if none could be found.
    func artBits(completion: @escaping (Data?) -> Void) {
        guard let t = track else { completion(nil); return }
        let key = "\(t.artist)|\(t.album)"
        if let cached = artCache[key] { publish(cached); completion(cached); return }

        if let img = player.nowPlayingItem?.artwork?.image(at: CGSize(width: 300, height: 300)),
           let out = ArtDither.convert(img) {
            artCache[key] = out.bits
            publish(out.bits)
            completion(out.bits)
            return
        }
        // Catalog (streamed) items often have no local artwork: ask the public iTunes Search API.
        fetchCatalogArt(artist: t.artist, album: t.album) { [weak self] img in
            let bits = img.flatMap { ArtDither.convert($0)?.bits }
            DispatchQueue.main.async {
                self?.artCache[key] = bits
                self?.publish(bits)
                completion(bits)
            }
        }
    }

    private func publish(_ bits: Data?) {
        artPreview = bits.map { ArtDither.preview($0) }
    }

    private func fetchCatalogArt(artist: String, album: String, done: @escaping (UIImage?) -> Void) {
        var c = URLComponents(string: "https://itunes.apple.com/search")!
        c.queryItems = [.init(name: "term", value: "\(artist) \(album)"),
                        .init(name: "entity", value: "album"),
                        .init(name: "limit", value: "1")]
        guard let url = c.url, !album.isEmpty else { done(nil); return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let first = (json["results"] as? [[String: Any]])?.first,
                  let small = first["artworkUrl100"] as? String,
                  let artURL = URL(string: small.replacingOccurrences(of: "100x100", with: "300x300"))
            else { done(nil); return }
            URLSession.shared.dataTask(with: artURL) { d, _, _ in
                done(d.flatMap(UIImage.init(data:)))
            }.resume()
        }.resume()
    }

    // MARK: Commands

    func perform(_ cmd: FT.Cmd) {
        switch cmd {
        case .playPause:
            if player.playbackState == .playing { player.pause() } else { player.play() }
        case .next:
            player.skipToNextItem()
        case .prev:
            if elapsed > 3 { player.skipToBeginning() } else { player.skipToPreviousItem() }
        case .seekFwd:
            player.currentPlaybackTime = min(elapsed + 10, track?.duration ?? .greatestFiniteMagnitude)
        case .seekBack:
            player.currentPlaybackTime = max(elapsed - 10, 0)
        case .volUp:
            SystemVolume.nudge(+0.0625)
        case .volDown:
            SystemVolume.nudge(-0.0625)
        case .sync, .poll:
            break
        }
    }
}

/// iOS has no public API to set the system volume; the supported workaround is
/// driving the slider inside an MPVolumeView. Works while the app is in the foreground.
enum SystemVolume {
    static let view: MPVolumeView = {
        let v = MPVolumeView(frame: CGRect(x: -100, y: -100, width: 10, height: 10))
        v.alpha = 0.01
        return v
    }()

    static func nudge(_ delta: Float) {
        guard let slider = view.subviews.compactMap({ $0 as? UISlider }).first else { return }
        slider.value = max(0, min(1, slider.value + delta))
        slider.sendActions(for: .valueChanged)
    }
}
