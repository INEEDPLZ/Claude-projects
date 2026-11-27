import CoreBluetooth
import Foundation

/// BLE central that talks to the Flipper's serial service.
final class FlipperLink: NSObject, ObservableObject {
    static let service = CBUUID(string: "8FE5B3D5-2E7F-4A98-2A48-7ACC60FE0000")
    static let rxChar = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E62FE0000") // we write -> Flipper
    static let txChar = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E61FE0000") // Flipper indicates -> us

    enum Status: Equatable {
        case bluetoothOff, idle, scanning, connecting(String), connected(String)
    }

    @Published private(set) var status: Status = .idle
    @Published private(set) var found: [CBPeripheral] = []

    var onReady: (() -> Void)?
    var onCommand: ((FT.Cmd) -> Void)?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var rx: CBCharacteristic?
    private var outbox: [Data] = []
    private var writing = false
    private let parser = FrameParser()
    private let savedKey = "fliptune.peripheral"

    override init() {
        super.init()
        central = CBCentralManager(
            delegate: self, queue: .main,
            options: [CBCentralManagerOptionRestoreIdentifierKey: "fliptune.central"])
    }

    var isConnected: Bool {
        if case .connected = status { return true }
        return false
    }

    // MARK: API

    func scan() {
        guard central.state == .poweredOn else { return }
        found = []
        status = .scanning
        // Flipper doesn't advertise the 128-bit serial UUID, so scan broadly and filter by name.
        central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func connect(_ p: CBPeripheral) {
        central.stopScan()
        peripheral = p
        p.delegate = self
        status = .connecting(p.name ?? "Flipper")
        UserDefaults.standard.set(p.identifier.uuidString, forKey: savedKey)
        central.connect(p)
    }

    func disconnect() {
        UserDefaults.standard.removeObject(forKey: savedKey)
        if let p = peripheral { central.cancelPeripheralConnection(p) }
        peripheral = nil
        status = .idle
    }

    func send(_ frames: [Data]) {
        guard let p = peripheral, rx != nil else { return }
        let mtu = min(p.maximumWriteValueLength(for: .withResponse), 180)
        for f in frames {
            var off = 0
            while off < f.count {
                let end = min(off + mtu, f.count)
                outbox.append(f.subdata(in: off..<end))
                off = end
            }
        }
        pump()
    }

    func send(_ frame: Data) { send([frame]) }

    // Writes with response give us natural flow control against the Flipper's RX buffer.
    private func pump() {
        guard !writing, let p = peripheral, let rx, !outbox.isEmpty else { return }
        writing = true
        p.writeValue(outbox.removeFirst(), for: rx, type: .withResponse)
    }

    private func reconnectSaved() {
        guard let s = UserDefaults.standard.string(forKey: savedKey), let id = UUID(uuidString: s),
              let p = central.retrievePeripherals(withIdentifiers: [id]).first else { return }
        connect(p) // pends indefinitely; iOS completes it whenever the Flipper app opens
    }
}

extension FlipperLink: CBCentralManagerDelegate {
    func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        if let p = (dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral])?.first {
            peripheral = p
            p.delegate = self
        }
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else { status = .bluetoothOff; return }
        if let p = peripheral, p.state == .connected {
            status = .connected(p.name ?? "Flipper")
            p.discoverServices([Self.service])
        } else {
            status = .idle
            reconnectSaved()
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover p: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = p.name ?? (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? ""
        guard name.lowercased().hasPrefix("flipper") || name.lowercased().hasPrefix("fz"),
              !found.contains(where: { $0.identifier == p.identifier }) else { return }
        found.append(p)
    }

    func centralManager(_ central: CBCentralManager, didConnect p: CBPeripheral) {
        p.discoverServices([Self.service])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        status = .idle
        reconnectSaved()
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        rx = nil
        outbox.removeAll()
        writing = false
        status = .idle
        reconnectSaved() // auto-reconnect when FlipTune is reopened on the Flipper
    }
}

extension FlipperLink: CBPeripheralDelegate {
    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        guard let s = p.services?.first(where: { $0.uuid == Self.service }) else { return }
        p.discoverCharacteristics([Self.rxChar, Self.txChar], for: s)
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for c in service.characteristics ?? [] {
            if c.uuid == Self.rxChar { rx = c }
            if c.uuid == Self.txChar { p.setNotifyValue(true, for: c) } // triggers pairing (PIN on Flipper)
        }
    }

    func peripheral(_ p: CBPeripheral, didUpdateNotificationStateFor c: CBCharacteristic, error: Error?) {
        guard c.uuid == Self.txChar, c.isNotifying else { return }
        status = .connected(p.name ?? "Flipper")
        onReady?()
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor c: CBCharacteristic, error: Error?) {
        guard c.uuid == Self.txChar, let v = c.value else { return }
        for (type, payload) in parser.feed(v) where type == .command {
            if let b = payload.first, let cmd = FT.Cmd(rawValue: b) { onCommand?(cmd) }
        }
    }

    func peripheral(_ p: CBPeripheral, didWriteValueFor c: CBCharacteristic, error: Error?) {
        writing = false
        pump()
    }
}
