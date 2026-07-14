# Linux-iPhone-Link

> A Linux background daemon that replicates core Windows "Phone Link" functionality for iOS devices — without any iOS-side code.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![BlueZ](https://img.shields.io/badge/BlueZ-5.65%2B-informational)](https://www.bluez.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status: Phase 1 – Bootstrap](https://img.shields.io/badge/Status-Phase%201%20%E2%80%93%20Bootstrap-yellow)]()

---

## Overview

**Linux-iPhone-Link** bridges your iPhone and your Linux desktop over Bluetooth — entirely on the Linux side. By leveraging the Apple Notification Center Service (ANCS) over BLE and the Bluetooth Message Access Profile (MAP) over classic Bluetooth, the daemon allows a Linux machine to:

- **Receive and display iOS push notifications** (calls, messages, social, etc.) as native desktop notifications.
- **Read and reply to SMS/iMessage threads** via a MAP-compliant interface.

The Linux host presents itself to iOS as a trusted Bluetooth peripheral (e.g., a smartwatch or hands-free unit). No jailbreak, no iOS companion app, and no Apple developer account are required.

---

## Architecture at a Glance

```
iPhone  ──── BLE (ANCS)  ────►  ancs_listener.py  ──►  Desktop Notification
        ──── BR/EDR (MAP) ───►  map_client.py      ──►  SMS/iMessage CLI/UI
                                       ▲
                              BlueZ D-Bus API
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design document.

---

## Roadmap

| Phase | Module | Status |
|-------|--------|--------|
| 1 | Environment bootstrap & `diag_bluetooth.py` | ✅ Complete |
| 2 | `ancs_listener.py` — raw ANCS payload capture | 🔜 Pending |
| 3 | ANCS parser → Linux desktop notifications | 🔜 Pending |
| 4 | MAP integration — read/reply SMS/iMessage | 🔜 Pending |

---

## Requirements

### System

| Dependency | Minimum Version | Purpose |
|------------|----------------|---------|
| Linux kernel | 5.10+ | BLE GATT + BR/EDR stable stack |
| BlueZ | 5.65+ | Bluetooth daemon (`bluetoothd`) |
| D-Bus | 1.12+ | IPC to BlueZ |
| Python | 3.11+ | Runtime |
| `libdbus-1-dev` | any | dbus-next C extension headers |

Install system dependencies (Debian/Ubuntu):

```bash
sudo apt update && sudo apt install -y \
  bluetooth bluez bluez-tools \
  libdbus-1-dev python3-dev python3-venv
```

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Quick Start — Phase 1 (Diagnostics)

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/linux-iphone-link.git
cd linux-iphone-link

# 2. Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pair your iPhone via BlueZ (if not already done)
bluetoothctl
  [bluetooth]# power on
  [bluetooth]# agent on
  [bluetooth]# default-agent
  [bluetooth]# scan on
  # Wait for your iPhone to appear, note its MAC address
  [bluetooth]# pair XX:XX:XX:XX:XX:XX
  [bluetooth]# trust XX:XX:XX:XX:XX:XX
  [bluetooth]# connect XX:XX:XX:XX:XX:XX
  [bluetooth]# quit

# 5. Run the diagnostic tool
python3 diag_bluetooth.py
```

Expected output:

```
[INFO] BlueZ D-Bus connection: OK
[INFO] Adapter: hci0  Address: AA:BB:CC:DD:EE:FF  Powered: True
[INFO] Paired devices:
  ✔  [Apple, Inc.]  iPhone – C2:3A:11:... [Connected: True | Trusted: True]
```

---

## Project Structure

```
linux-iphone-link/
├── diag_bluetooth.py      # Phase 1 – BlueZ diagnostics & iOS device discovery
├── ancs_listener.py       # Phase 2 – BLE ANCS raw payload capture  (TBD)
├── ancs_parser.py         # Phase 3 – ANCS decoder + desktop notifications (TBD)
├── map_client.py          # Phase 4 – MAP SMS/iMessage integration     (TBD)
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
└── LICENSE
```

---

## Security & Privacy

- **No data leaves the machine.** All communication is local Bluetooth.
- **No cloud dependency.** The daemon is fully offline.
- Bluetooth pairing relies on standard iOS trust prompts — no credentials are stored.
- Message content is processed in-memory only; persistence is opt-in.

---

## Contributing

Pull requests are welcome. Please open an issue first to discuss major changes. Follow the existing code style (PEP 8, type hints, docstrings).

---

## License

[MIT](./LICENSE) © 2026 Linux-iPhone-Link contributors.

---

## Disclaimer

*"iPhone" is a trademark of Apple Inc. This project is not affiliated with, endorsed by, or connected to Apple Inc. in any way. All trademarks are the property of their respective owners.*
