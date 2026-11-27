import MediaPlayer
import SwiftUI

@main
struct FlipTuneApp: App {
    @StateObject private var bridge = Bridge()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(bridge)
                .environmentObject(bridge.link)
                .environmentObject(bridge.music)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var bridge: Bridge
    @EnvironmentObject var link: FlipperLink
    @EnvironmentObject var music: NowPlaying

    private let flipperOrange = Color(red: 1, green: 0.51, blue: 0)

    var body: some View {
        NavigationStack {
            List {
                Section("Flipper") {
                    statusRow
                    if case .scanning = link.status {
                        ForEach(link.found, id: \.identifier) { p in
                            Button(p.name ?? "Flipper") { link.connect(p) }
                        }
                    }
                }

                Section("Now playing") {
                    if !music.authorized {
                        Text("Allow access to Apple Music in Settings so FlipTune can read what's playing.")
                            .foregroundStyle(.secondary)
                    } else if let t = music.track {
                        HStack(spacing: 14) {
                            cover
                            VStack(alignment: .leading, spacing: 3) {
                                Text(t.title).font(.headline).lineLimit(2)
                                Text(t.artist).lineLimit(1)
                                Text(t.album).foregroundStyle(.secondary).lineLimit(1)
                                Label(music.isPlaying ? "Playing" : "Paused",
                                      systemImage: music.isPlaying ? "play.fill" : "pause.fill")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    } else {
                        Text("Nothing playing in Apple Music.").foregroundStyle(.secondary)
                    }
                }

                Section("On the Flipper") {
                    Text("Apps > Bluetooth > FlipTune Remote. The first time, the Flipper shows a PIN; enter it when iOS asks to pair.")
                    Text("OK play/pause · ◀︎ ▶︎ prev/next · hold ◀︎ ▶︎ seek · ▲ ▼ volume")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("FlipTune")
            .background(VolumeHost().frame(width: 1, height: 1))
        }
        .tint(flipperOrange)
    }

    @ViewBuilder private var statusRow: some View {
        switch link.status {
        case .bluetoothOff:
            Label("Bluetooth is off", systemImage: "antenna.radiowaves.left.and.right.slash")
        case .idle:
            Button { link.scan() } label: { Label("Find my Flipper", systemImage: "magnifyingglass") }
        case .scanning:
            HStack { ProgressView(); Text("Scanning… open FlipTune on the Flipper") }
        case .connecting(let name):
            HStack { ProgressView(); Text("Connecting to \(name)…") }
        case .connected(let name):
            HStack {
                Label(name, systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                Spacer()
                Button("Forget", role: .destructive) { link.disconnect() }.buttonStyle(.borderless)
            }
        }
    }

    private var cover: some View {
        Group {
            if let img = music.artPreview {
                Image(uiImage: img).interpolation(.none).resizable()
            } else {
                flipperOrange.overlay(Image(systemName: "music.note").foregroundStyle(.black))
            }
        }
        .frame(width: 72, height: 72)
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

/// Hosts the hidden MPVolumeView used to change the system volume.
struct VolumeHost: UIViewRepresentable {
    func makeUIView(context: Context) -> UIView {
        let v = UIView()
        v.addSubview(SystemVolume.view)
        return v
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}
