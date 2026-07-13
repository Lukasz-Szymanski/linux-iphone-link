# Architecture — Linux-iPhone-Link

> Version 0.1 — Phase 1 Baseline  
> Last updated: 2026-07-13

---

## 1. Design Philosophy

Linux-iPhone-Link is designed around three hard constraints:

1. **Zero iOS code.** Apple's App Store policies and CoreBluetooth sandboxing prohibit third-party ANCS or MAP clients running on iOS. The entire stack lives on Linux.
2. **Standard protocols only.** The daemon uses publicly documented Bluetooth SIG and Apple-published specifications (ANCS, MAP). No private APIs or reverse-engineered payloads.
3. **Async, non-blocking I/O.** All Bluetooth and D-Bus operations run inside a single `asyncio` event loop to avoid blocking the system notification pipeline.

---

## 2. High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            iOS Device (iPhone)                          │
│                                                                         │
│  [ANCS Server] ──── BLE GATT ────────────────────────────────────────► │
│  [MAP Server]  ──── BR/EDR RFCOMM ───────────────────────────────────► │
└─────────────────────────────────────────────────────────────────────────┘
                         │                        │
                   BLE (LE)               Classic BT (BR/EDR)
                         │                        │
┌─────────────────────────────────────────────────────────────────────────┐
│                       Linux Host (this daemon)                          │
│                                                                         │
│  ┌─────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │ ancs_listener   │   │   ancs_parser    │   │    map_client      │  │
│  │  (Phase 2)      │──►│   (Phase 3)      │   │    (Phase 4)       │  │
│  │ bleak GATT      │   │ ANCS packet dec. │   │ D-Bus MAP profile  │  │
│  └─────────────────┘   └────────┬─────────┘   └────────┬───────────┘  │
│                                  │                       │              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     BlueZ Daemon (bluetoothd)                      │ │
│  │              D-Bus Interface: org.bluez                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                  │                       │              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                  Linux Desktop (Notification Layer)                │ │
│  │   notify-send / org.freedesktop.Notifications D-Bus interface      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Descriptions

### 3.1 `diag_bluetooth.py` (Phase 1)

**Purpose:** System readiness validation.  
**Responsibilities:**
- Open a synchronous connection to the system D-Bus session.
- Introspect `org.bluez` → `org.bluez.Adapter1` to retrieve adapter status (name, address, powered state, discoverable).
- Enumerate all objects under the BlueZ object tree (`GetManagedObjects`), filter by `org.bluez.Device1`, and identify paired devices with an `Apple, Inc.` vendor signature.
- Print a structured diagnostic report to stdout.

**Key D-Bus paths used:**
| Path | Interface | Purpose |
|------|-----------|---------|
| `org.bluez` | `org.freedesktop.DBus.ObjectManager` | Enumerate all Bluetooth objects |
| `/org/bluez/hci0` | `org.bluez.Adapter1` | Adapter properties |
| `/org/bluez/hci0/dev_XX_XX_...` | `org.bluez.Device1` | Per-device properties |

---

### 3.2 `ancs_listener.py` (Phase 2)

**Purpose:** Establish a BLE GATT connection to a paired iPhone and subscribe to the ANCS Notification Source characteristic.  
**Responsibilities:**
- Use `bleak.BleakClient` to connect to the target device MAC.
- Discover GATT services; locate the ANCS Service UUID (`7905F431-B5CE-4E99-A40F-4B1E122D00D6`).
- Enable notifications on the Notification Source characteristic (`9FBF120D-6301-42D9-8C58-25E699A21DBD`).
- Stream raw `bytearray` payloads to stdout for inspection.

---

### 3.3 `ancs_parser.py` (Phase 3)

**Purpose:** Decode ANCS binary packets and dispatch desktop notifications.  
**Responsibilities:**
- Parse the fixed-format ANCS Notification Source packet (8 bytes):
  - `EventID` (1 byte): Added / Modified / Removed
  - `EventFlags` (1 byte): Silent, Important, Pre-existing, Positive/Negative action
  - `CategoryID` (1 byte): Incoming call, Missed call, Voicemail, Social, Schedule, Email, News, Health, Business, Location, Entertainment, Other
  - `CategoryCount` (1 byte)
  - `NotificationUID` (4 bytes, little-endian)
- Issue a GATT `Get Notification Attributes` request to the Control Point characteristic to retrieve Title, Subtitle, Message body, and App Identifier.
- Dispatch the decoded notification via `org.freedesktop.Notifications` D-Bus interface (with fallback to `notify-send` subprocess).

---

### 3.4 `map_client.py` (Phase 4)

**Purpose:** Full Message Access Profile client over BlueZ.  
**Responsibilities:**
- Utilize `org.bluez.obex` D-Bus service (BlueZ OBEX daemon) to establish an MAP session.
- List message repositories (SMS, iMessage where exposed).
- Fetch message bodies (BMSG format, RFC 4317 based).
- Expose a simple CLI/socket interface to send reply messages via the MAP `SendMessage` operation.

---

## 4. Bluetooth Protocol Stack

```
Application Layer
  ├── ANCS (Apple Notification Center Service) — BLE GATT
  │     ├── Service UUID: 7905F431-B5CE-4E99-A40F-4B1E122D00D6
  │     ├── Notification Source Char: 9FBF120D-6301-42D9-8C58-25E699A21DBD
  │     ├── Control Point Char:       69D1D8F3-45E1-49A8-9821-9BBDFDAAD9D9
  │     └── Data Source Char:         22EAC6E9-24D6-4BB5-BE44-B36ACE7C7BFB
  │
  └── MAP (Message Access Profile) — BR/EDR RFCOMM/OBEX
        ├── MAS (Message Access Server) on iPhone
        └── MCE (Message Client Equipment) on Linux host

Transport Layer
  ├── BLE (LE) — for ANCS
  └── BR/EDR Classic — for MAP (L2CAP → RFCOMM → OBEX)

Host Controller Interface (HCI)
  └── Linux kernel hci driver → BlueZ userspace daemon

D-Bus IPC
  ├── org.bluez           (Classic BT + BLE adapter management)
  └── org.bluez.obex      (OBEX sessions for MAP/PBAP/OPP)
```

---

## 5. iOS Pairing Flow

```
Linux Host                              iPhone
    │                                     │
    │── HCI Inquiry / BLE Scan ──────────►│
    │◄── Device Advertisement ────────────│
    │                                     │
    │── Pair Request (SSP/MITM) ─────────►│
    │◄── User confirms on iPhone ─────────│
    │                                     │
    │── Link Key Exchange (BR/EDR) ───────│
    │   + LTK Exchange (BLE) ────────────►│
    │                                     │
    │ [Pairing complete; iOS now trusts   │
    │  Linux host as a Bluetooth device]  │
    │                                     │
    │── ANCS GATT Subscribe ─────────────►│  (BLE channel)
    │── MAP OBEX Connect ────────────────►│  (BR/EDR channel)
```

> **Important:** iOS will only expose ANCS and MAP to devices that have been paired with the standard Bluetooth pairing flow. The Linux host **must** complete pairing before attempting GATT service discovery.

---

## 6. Data Flow — Notification Pipeline

```
iPhone generates notification
         │
         ▼
iOS sends ANCS Notification Source packet (8 bytes) → Linux via BLE
         │
         ▼
ancs_listener.py receives raw bytearray
         │
         ▼
ancs_parser.py decodes EventID, CategoryID, NotificationUID
         │
         ▼
ancs_parser.py sends GetNotificationAttributes request via Control Point
         │
         ▼
iOS replies with Title, Subtitle, Message, AppID via Data Source char
         │
         ▼
ancs_parser.py dispatches org.freedesktop.Notifications D-Bus call
         │
         ▼
Desktop notification appears (GNOME / KDE / etc.)
```

---

## 7. Error Handling Strategy

| Error Condition | Strategy |
|----------------|---------|
| BlueZ not running | Detect via D-Bus `org.freedesktop.DBus.Error.ServiceUnknown`; exit with actionable message |
| No Bluetooth adapter | Detect missing `org.bluez.Adapter1`; print setup instructions |
| iPhone not paired | Filter `org.bluez.Device1.Paired == False`; guide user through `bluetoothctl` pairing |
| BLE connection dropped | `bleak` reconnect loop with exponential backoff (max 5 retries) |
| ANCS service not found | Device may not have trusted the host; prompt user to re-pair |
| MAP session rejected | Verify BlueZ OBEX daemon is running (`obexd`); retry once |

---

## 8. Security Considerations

- **No persistent credential storage.** Bluetooth link keys are managed entirely by the BlueZ daemon in `/var/lib/bluetooth/`.
- **Process isolation.** The daemon runs as a regular user; no `root` is required post-pairing (assuming `plugdev` group membership).
- **No network egress.** The daemon makes zero outbound network connections.
- **Message content memory-only.** Notification bodies are held in Python objects for the duration of dispatch only; no disk writes by default.
