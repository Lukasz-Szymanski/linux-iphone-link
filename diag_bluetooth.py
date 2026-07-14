#!/usr/bin/env python3
"""
diag_bluetooth.py — Linux-iPhone-Link Phase 1 Diagnostic Tool
==============================================================

Validates the system's Bluetooth stack readiness and discovers
paired iOS devices via the BlueZ D-Bus API.

Usage:
    python3 diag_bluetooth.py [--verbose] [--adapter hci0]

Exit codes:
    0  All checks passed; at least one paired iOS device was found.
    1  BlueZ is not running or D-Bus is unavailable.
    2  No Bluetooth adapters found or all adapters are powered off.
    3  No paired iOS devices found (pairing guide is printed).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
try:
    from dbus_next.aio import MessageBus  # noqa: F401 — checked at import time
    import asyncio
    from dbus_next import BusType
    from dbus_next.errors import DBusError
except ImportError:
    print(
        "[FATAL] 'dbus-next' is not installed.\n"
        "  Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
except ImportError:
    print(
        "[FATAL] 'rich' is not installed.\n"
        "  Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# BlueZ well-known D-Bus name and object paths
BLUEZ_BUS_NAME: str = "org.bluez"
BLUEZ_ROOT_PATH: str = "/"

# D-Bus interface names used for introspection
IFACE_OBJECT_MANAGER: str = "org.freedesktop.DBus.ObjectManager"
IFACE_ADAPTER1: str = "org.bluez.Adapter1"
IFACE_DEVICE1: str = "org.bluez.Device1"

# Apple, Inc. Organizationally Unique Identifiers (first 3 octets of MAC address).
# These OUIs are used to identify Apple devices when no vendor name is available.
APPLE_OUIS: frozenset[str] = frozenset(
    {
        "00:03:93", "00:0A:27", "00:0A:95", "00:1B:63",
        "00:1E:52", "00:1E:C2", "00:1F:5B", "00:1F:F3",
        "00:21:E9", "00:22:41", "00:23:12", "00:23:32",
        "00:23:6C", "00:23:DF", "00:24:36", "00:25:00",
        "00:25:4B", "00:25:BC", "00:26:08", "00:26:4A",
        "00:26:B0", "00:26:BB", "00:30:65", "00:3E:E1",
        "00:50:E4", "00:56:CD", "00:61:71", "00:6D:52",
        "04:0C:CE", "04:15:52", "04:1E:64", "04:26:65",
        "04:48:9A", "04:4B:ED", "04:52:F3", "04:54:53",
        "04:69:F8", "04:D3:CF", "04:DB:56", "04:E5:36",
        "04:F1:3E", "08:00:07", "08:6D:41", "08:70:45",
        "0C:3E:9F", "0C:4D:E9", "0C:74:C2", "0C:BC:9F",
        "10:1C:0C", "10:40:F3", "10:9A:DD", "10:DD:B1",
        "14:10:9F", "14:5A:05", "14:8F:C6", "14:99:E2",
        "18:20:32", "18:34:51", "18:65:90", "18:81:0E",
        "18:9E:FC", "18:AF:61", "18:E7:F4", "1C:1A:C0",
        "20:3C:AE", "20:78:F0", "20:A2:E4", "20:AB:37",
        "20:C9:D0", "24:1E:EB", "24:5B:A7", "24:A0:74",
        "28:6A:BA", "28:CF:DA", "28:E0:2C", "2C:1F:23",
        "2C:20:0B", "2C:BE:08", "2C:F0:A2", "34:08:BC",
        "34:12:98", "34:36:3B", "34:51:C9", "34:C0:59",
        "38:0F:4A", "38:48:4C", "38:C9:86", "38:CA:DA",
        "3C:07:54", "3C:2E:F9", "3C:D0:F8", "40:30:04",
        "40:33:1A", "40:3C:FC", "40:6C:8F", "40:98:AD",
        "40:A6:D9", "44:2A:60", "44:4C:0C", "44:D8:84",
        "44:FB:42", "48:43:7C", "48:60:BC", "48:74:6E",
        "48:A1:95", "48:BF:6B", "4C:32:75", "4C:57:CA",
        "4C:74:03", "4C:8D:79", "50:EA:D6", "54:26:96",
        "54:72:4F", "54:9F:13", "58:1F:AA", "58:55:CA",
        "5C:59:48", "5C:96:9D", "5C:F9:38", "60:03:08",
        "60:33:4B", "60:69:44", "60:92:17", "60:C5:47",
        "60:D9:C7", "60:F8:1D", "64:20:0C", "64:76:BA",
        "64:9A:BE", "64:B9:E8", "68:09:27", "68:5B:35",
        "68:64:4B", "68:96:7B", "68:A8:6D", "68:AB:1E",
        "6C:19:C0", "6C:40:08", "6C:4D:73", "6C:70:9F",
        "6C:72:E7", "6C:8D:C1", "6C:AD:F8", "6C:C2:6B",
        "70:11:24", "70:3E:AC", "70:48:0F", "70:56:81",
        "70:73:CB", "70:CD:60", "70:DE:E2", "74:1B:B2",
        "74:E2:F5", "74:E5:43", "74:F0:6D", "78:31:C1",
        "78:4F:43", "78:67:D7", "78:6C:1C", "78:7E:61",
        "78:A3:E4", "78:CA:39", "78:D7:5F", "7C:01:91",
        "7C:04:D0", "7C:11:BE", "7C:5C:F8", "7C:6D:62",
        "7C:C3:A1", "7C:D1:C3", "7C:FA:DF", "80:00:6E",
        "80:49:71", "80:82:23", "80:92:9F", "80:B0:3D",
        "80:BE:05", "80:ED:2C", "84:29:99", "84:38:35",
        "84:41:67", "84:78:8B", "84:85:06", "84:89:AD",
        "84:8E:DF", "84:A1:34", "84:FC:AC", "88:1F:A1",
        "88:53:2E", "88:63:DF", "88:66:A5", "88:AE:07",
        "88:C6:63", "88:E8:7F", "8C:00:6D", "8C:2D:AA",
        "8C:7B:9D", "8C:85:90", "90:27:E4", "90:60:F1",
        "90:72:40", "90:84:0D", "90:B0:ED", "90:C1:C6",
        "94:BF:2D", "94:E9:6A", "94:F6:A3", "98:00:C6",
        "98:01:A7", "98:03:D8", "98:5A:EB", "98:D6:BB",
        "98:E0:D9", "98:FE:94", "9C:04:EB", "9C:20:7B",
        "9C:35:EB", "9C:4F:DA", "A4:31:35", "A4:5E:60",
        "A4:67:06", "A4:B1:97", "A4:C3:61", "A4:D1:8C",
        "A4:D9:31", "A4:E9:75", "A4:F1:E8", "A8:51:AB",
        "A8:5B:4F", "A8:5C:2C", "A8:66:7F", "A8:86:DD",
        "A8:8E:24", "A8:96:8A", "A8:BB:CF", "A8:BE:27",
        "A8:FA:D8", "AC:1F:74", "AC:29:3A", "AC:3C:0B",
        "AC:61:EA", "AC:87:A3", "AC:BC:32", "AC:CF:5C",
        "AC:E4:B5", "AC:FD:EC", "B0:34:95", "B0:65:BD",
        "B0:9F:BA", "B4:18:D1", "B4:4B:D2", "B4:F0:AB",
        "B8:09:8A", "B8:17:C2", "B8:44:D9", "B8:53:AC",
        "B8:8D:12", "B8:C7:5D", "B8:E8:56", "B8:FF:61",
        "BC:3B:AF", "BC:52:B7", "BC:54:36", "BC:67:1C",
        "BC:92:6B", "BC:9F:EF", "C0:1A:DA", "C0:63:94",
        "C0:9F:42", "C0:CE:CD", "C0:D0:12", "C4:2C:03",
        "C4:B3:01", "C8:1E:E7", "C8:2A:14", "C8:33:4B",
        "C8:69:CD", "C8:85:50", "C8:B5:B7", "C8:BC:C8",
        "C8:D0:83", "C8:E0:EB", "CC:08:8D", "CC:20:E8",
        "CC:44:63", "CC:78:5F", "CC:C7:60", "D0:03:4B",
        "D0:23:DB", "D0:25:98", "D0:4F:7E", "D0:A6:37",
        "D0:C5:F3", "D4:61:9D", "D4:9A:20", "D4:F4:6F",
        "D8:1D:72", "D8:30:62", "D8:8F:76", "D8:96:95",
        "D8:A2:5E", "D8:BB:2C", "D8:CF:9C", "DC:0C:5C",
        "DC:2B:61", "DC:37:14", "DC:3A:5E", "DC:86:D8",
        "DC:A4:CA", "E0:5F:45", "E0:66:78", "E0:AC:CB",
        "E0:B5:2D", "E0:C9:7A", "E4:25:E7", "E4:8B:7F",
        "E4:98:D6", "E4:C6:3D", "E4:CE:8F", "E4:E4:AB",
        "E8:04:0B", "E8:06:88", "E8:40:F2", "E8:80:2E",
        "E8:8D:28", "E8:B2:AC", "EC:35:86", "EC:85:2F",
        "F0:18:98", "F0:24:75", "F0:79:60", "F0:99:BF",
        "F0:B4:79", "F0:CB:A1", "F0:D1:A9", "F0:DB:E2",
        "F0:DC:E2", "F0:F6:1C", "F4:0F:24", "F4:1B:A1",
        "F4:31:C3", "F4:37:B7", "F4:5C:89", "F4:F1:5A",
        "F4:F9:51", "F8:27:93", "F8:62:14", "F8:7C:05",
        "F8:95:C7", "F8:E0:79", "FC:25:3F", "FC:E9:98",
    }
)

# Keyword in the BlueZ Device1 "Manufacturer" or "Name" that identifies iOS
APPLE_VENDOR_KEYWORD: str = "Apple"

# Common UUIDs exposed by iOS that confirm it is an Apple mobile device
IOS_HINT_UUIDS: frozenset[str] = frozenset(
    {
        # ANCS — Apple Notification Center Service
        "7905f431-b5ce-4e99-a40f-4b1e122d00d6",
        # Apple Media Service (AMS)
        "89d3502b-0f36-433a-8ef4-c502ad55f8dc",
        # Apple Continuity / Handoff (partial)
        "00001805-0000-1000-8000-00805f9b34fb",  # Current Time Service
        # HFP Hands-Free (classic BT, often listed in UUIDs)
        "0000111e-0000-1000-8000-00805f9b34fb",
        # MAP Message Access Service
        "00001134-0000-1000-8000-00805f9b34fb",
        # PBAP Phone Book Access
        "0000112f-0000-1000-8000-00805f9b34fb",
    }
)

# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------


def _is_apple_device(device_props: dict[str, Any]) -> bool:
    """Determine whether a BlueZ Device1 property dict belongs to an Apple device.

    Heuristics applied in order:
    1. ``Vendor`` string contains "Apple" (populated by BlueZ from SDP records).
    2. ``Name`` string contains "Apple" (rare, but some accessories self-identify).
    3. MAC address OUI matches a known Apple OUI prefix.
    4. At least one UUID in the device's GATT/SDP list matches a known iOS service UUID.

    Args:
        device_props: Flat dict of property name → unwrapped Python value
                      for a single ``org.bluez.Device1`` object.

    Returns:
        ``True`` if at least one heuristic matches.
    """
    # Heuristic 1: Vendor / Manufacturer field
    vendor: str = device_props.get("Vendor", "") or ""
    if APPLE_VENDOR_KEYWORD.lower() in vendor.lower():
        return True

    # Heuristic 2: Device name contains "iPhone" / "iPad" / "Apple"
    name: str = device_props.get("Name", "") or ""
    if any(kw in name for kw in ("iPhone", "iPad", "iPod", "Apple")):
        return True

    # Heuristic 3: OUI match
    address: str = device_props.get("Address", "")
    if address:
        oui = address.upper()[:8]  # e.g. "C2:3A:11"
        # Locally administered addresses (bit 1 of MSB set) won't match OUIs;
        # check anyway — some randomised BLE addresses still carry Apple OUI.
        if oui in APPLE_OUIS:
            return True

    # Heuristic 4: ManufacturerData contains Apple's ID (0x004C / 76)
    # This is crucial because iOS uses random BLE MACs that don't match Apple OUIs.
    manufacturer_data = device_props.get("ManufacturerData", {})
    if 76 in manufacturer_data or "76" in manufacturer_data:
        return True

    # Heuristic 5: UUID intersection
    device_uuids: list[str] = device_props.get("UUIDs", []) or []
    normalized_uuids = {u.lower() for u in device_uuids}
    if normalized_uuids & IOS_HINT_UUIDS:
        return True

    return False


def _unwrap_variant(value: Any) -> Any:
    """Recursively unwrap ``dbus_next.Variant`` wrappers into plain Python types.

    dbus-next wraps all D-Bus values in a ``Variant`` container that has a
    ``.value`` attribute.  This helper unwraps nested structures so that
    downstream code can work with native dicts, lists, and scalars.

    Args:
        value: A raw value from a dbus-next property dict.  May be a
               ``Variant``, a ``dict``, a ``list``, or a scalar.

    Returns:
        The unwrapped Python equivalent.
    """
    # Avoid importing at module level to keep startup fast
    from dbus_next import Variant  # type: ignore[attr-defined]

    if isinstance(value, Variant):
        return _unwrap_variant(value.value)
    if isinstance(value, dict):
        return {k: _unwrap_variant(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unwrap_variant(i) for i in value]
    return value


# ---------------------------------------------------------------------------
# Core diagnostic functions
# ---------------------------------------------------------------------------


async def check_bluez_connection(bus: Any, console: Console) -> bool:
    """Verify that the BlueZ D-Bus service is reachable and responding.

    Attempts to introspect the BlueZ root object.  A successful introspection
    confirms that:
    - The system D-Bus session is accessible.
    - ``bluetoothd`` is running and owns the ``org.bluez`` well-known name.

    Args:
        bus:     An active ``dbus_next.aio.MessageBus`` instance.
        console: Rich console for formatted output.

    Returns:
        ``True`` if BlueZ is reachable, ``False`` otherwise.
    """
    try:
        introspection = await bus.introspect(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH)
        _ = bus.get_proxy_object(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH, introspection)
        console.print("[bold green]✔[/]  BlueZ D-Bus service [bold]org.bluez[/] is [green]reachable[/].")
        return True
    except DBusError as exc:
        console.print(
            f"[bold red]✘[/]  Cannot reach [bold]org.bluez[/] on the system D-Bus.\n"
            f"    Error: {exc}\n\n"
            "    [yellow]Troubleshooting:[/]\n"
            "    • Is [bold]bluetoothd[/] running?  →  [dim]sudo systemctl start bluetooth[/]\n"
            "    • Does the current user have D-Bus access?  →  "
            "[dim]sudo usermod -aG bluetooth $USER[/]\n"
        )
        return False


async def enumerate_adapters(bus: Any, console: Console, verbose: bool) -> list[dict[str, Any]]:
    """Enumerate all Bluetooth adapters managed by BlueZ.

    Uses the ``GetManagedObjects`` method on the root ObjectManager interface
    to discover all objects and filters for those implementing ``org.bluez.Adapter1``.

    Args:
        bus:     An active ``dbus_next.aio.MessageBus`` instance.
        console: Rich console for formatted output.
        verbose: When ``True``, print the full property dump for each adapter.

    Returns:
        A list of dicts, each representing one adapter's unwrapped properties.
        Returns an empty list if no adapters are found.
    """
    introspection = await bus.introspect(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH)
    proxy = bus.get_proxy_object(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH, introspection)
    obj_manager = proxy.get_interface(IFACE_OBJECT_MANAGER)

    managed: dict = await obj_manager.call_get_managed_objects()

    adapters: list[dict[str, Any]] = []
    for obj_path, interfaces in managed.items():
        if IFACE_ADAPTER1 not in interfaces:
            continue
        raw_props: dict = interfaces[IFACE_ADAPTER1]
        props: dict[str, Any] = _unwrap_variant(raw_props)
        props["_object_path"] = str(obj_path)
        adapters.append(props)

    if not adapters:
        console.print(
            "[bold red]✘[/]  No Bluetooth adapters found.\n"
            "    [yellow]Is a Bluetooth adapter (USB dongle or built-in) present?[/]\n"
            "    Try: [dim]hciconfig -a[/]"
        )
        return []

    table = Table(
        title="Bluetooth Adapters",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Path", style="dim")
    table.add_column("Name")
    table.add_column("Address", style="magenta")
    table.add_column("Powered")
    table.add_column("Discoverable")
    table.add_column("Pairable")

    for adapter in adapters:
        powered = adapter.get("Powered", False)
        discoverable = adapter.get("Discoverable", False)
        pairable = adapter.get("Pairable", False)
        table.add_row(
            adapter.get("_object_path", "?"),
            adapter.get("Name", "?"),
            adapter.get("Address", "?"),
            "[green]Yes[/]" if powered else "[red]No[/]",
            "[green]Yes[/]" if discoverable else "[yellow]No[/]",
            "[green]Yes[/]" if pairable else "[yellow]No[/]",
        )
        if verbose:
            console.print(f"\n[dim]Full properties for {adapter.get('_object_path')}:[/]")
            for k, v in sorted(adapter.items()):
                if not k.startswith("_"):
                    console.print(f"  [dim]{k}[/]: {v!r}")

    console.print(table)
    return adapters


async def discover_ios_devices(
    bus: Any,
    console: Console,
    verbose: bool,
) -> list[dict[str, Any]]:
    """Discover paired iOS devices from the BlueZ managed objects.

    Iterates all ``org.bluez.Device1`` objects and applies multi-heuristic
    Apple device detection.  Reports connection status, trust status, paired
    status, and available Bluetooth UUIDs for each identified iOS device.

    Args:
        bus:     An active ``dbus_next.aio.MessageBus`` instance.
        console: Rich console for formatted output.
        verbose: When ``True``, also print all reported UUIDs per device.

    Returns:
        A list of dicts, each representing one iOS device's unwrapped properties.
        Returns an empty list if no iOS devices are paired.
    """
    introspection = await bus.introspect(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH)
    proxy = bus.get_proxy_object(BLUEZ_BUS_NAME, BLUEZ_ROOT_PATH, introspection)
    obj_manager = proxy.get_interface(IFACE_OBJECT_MANAGER)

    managed: dict = await obj_manager.call_get_managed_objects()

    ios_devices: list[dict[str, Any]] = []
    for obj_path, interfaces in managed.items():
        if IFACE_DEVICE1 not in interfaces:
            continue
        raw_props: dict = interfaces[IFACE_DEVICE1]
        props: dict[str, Any] = _unwrap_variant(raw_props)
        props["_object_path"] = str(obj_path)

        if _is_apple_device(props):
            ios_devices.append(props)

    if not ios_devices:
        console.print(
            Panel(
                "[yellow]No paired iOS devices were detected.[/]\n\n"
                "To pair your iPhone with this Linux host, run:\n\n"
                "  [bold dim]bluetoothctl[/]\n"
                "    [dim]power on[/]\n"
                "    [dim]agent on[/]\n"
                "    [dim]default-agent[/]\n"
                "    [dim]scan on[/]\n"
                "    [dim]pair  <iPhone MAC>[/]\n"
                "    [dim]trust <iPhone MAC>[/]\n"
                "    [dim]connect <iPhone MAC>[/]\n\n"
                "Accept the pairing prompt on your iPhone, then re-run this diagnostic.",
                title="[bold red]iOS Pairing Required[/]",
                border_style="red",
            )
        )
        return []

    table = Table(
        title=f"Paired iOS Devices ({len(ios_devices)} found)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="bold")
    table.add_column("Address", style="magenta")
    table.add_column("Paired")
    table.add_column("Trusted")
    table.add_column("Connected")
    table.add_column("RSSI")
    table.add_column("ANCS UUID Present")

    ancs_uuid = "7905f431-b5ce-4e99-a40f-4b1e122d00d6"

    for device in ios_devices:
        paired = device.get("Paired", False)
        trusted = device.get("Trusted", False)
        connected = device.get("Connected", False)
        rssi = device.get("RSSI", "N/A")
        uuids: list[str] = device.get("UUIDs", []) or []
        has_ancs = ancs_uuid in {u.lower() for u in uuids}

        table.add_row(
            device.get("Name", "Unknown"),
            device.get("Address", "?"),
            "[green]✔[/]" if paired else "[red]✘[/]",
            "[green]✔[/]" if trusted else "[red]✘[/]",
            "[green]✔[/]" if connected else "[dim]–[/]",
            str(rssi) if rssi != "N/A" else "[dim]N/A[/]",
            "[green]✔[/]" if has_ancs else "[dim]–[/]",
        )

        if verbose:
            console.print(f"\n[dim]UUIDs reported for {device.get('Name', device.get('Address'))}:[/]")
            for uuid in sorted(uuids):
                console.print(f"  [dim]{uuid}[/]")

    console.print(table)
    return ios_devices


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def _run_diagnostics(args: argparse.Namespace) -> int:
    """Orchestrate all diagnostic checks and return an exit code.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Integer exit code (0 = success, 1–3 = specific failure, see module docstring).
    """
    console = Console()

    console.print(
        Panel.fit(
            "[bold white]Linux-iPhone-Link[/] — Bluetooth Diagnostic Tool\n"
            "[dim]Phase 1: Environment Bootstrap & Device Discovery[/]",
            border_style="blue",
        )
    )
    console.print()

    # ── Step 1: Open D-Bus connection ──────────────────────────────────────
    console.rule("[bold]Step 1[/]: D-Bus → BlueZ Connectivity")
    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    except Exception as exc:
        console.print(
            f"[bold red]✘[/]  Failed to connect to the system D-Bus.\n"
            f"    Error: {exc}\n"
            "    [yellow]Is D-Bus running?[/]  →  [dim]systemctl status dbus[/]"
        )
        return 1

    if not await check_bluez_connection(bus, console):
        return 1

    console.print()

    # ── Step 2: Enumerate adapters ─────────────────────────────────────────
    console.rule("[bold]Step 2[/]: Bluetooth Adapter Status")
    adapters = await enumerate_adapters(bus, console, verbose=args.verbose)
    if not adapters:
        return 2

    # Warn if no adapter is powered
    powered_adapters = [a for a in adapters if a.get("Powered", False)]
    if not powered_adapters:
        console.print(
            "[bold yellow]⚠[/]  All adapters are [red]powered off[/].\n"
            "    Run: [dim]bluetoothctl power on[/]  or  [dim]sudo rfkill unblock bluetooth[/]"
        )
        return 2

    console.print()

    # ── Step 3: Discover paired iOS devices ────────────────────────────────
    console.rule("[bold]Step 3[/]: Paired iOS Device Discovery")
    ios_devices = await discover_ios_devices(bus, console, verbose=args.verbose)
    if not ios_devices:
        return 3

    # ── Summary ────────────────────────────────────────────────────────────
    console.print()
    ancs_ready = [
        d for d in ios_devices
        if d.get("Paired") and d.get("Trusted") and "7905f431-b5ce-4e99-a40f-4b1e122d00d6"
        in {u.lower() for u in (d.get("UUIDs") or [])}
    ]

    if ancs_ready:
        console.print(
            Panel(
                f"[green]✔  {len(ancs_ready)} device(s) are ANCS-ready.[/]\n\n"
                "Next step → Run [bold]Phase 2[/]: [dim]python3 ancs_listener.py[/]",
                title="[bold green]Diagnostic Passed[/]",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[yellow]Paired iOS device(s) found, but ANCS UUID was not advertised.[/]\n\n"
                "This is normal if the device is not currently connected via BLE.\n"
                "Ensure your iPhone's Bluetooth is active and the devices are connected,\n"
                "then re-run this diagnostic.\n\n"
                "You may also need to re-pair if ANCS trust was not granted:\n"
                "  [dim]bluetoothctl remove <MAC>[/] then pair again.",
                title="[bold yellow]Partial Success — ANCS Not Yet Visible[/]",
                border_style="yellow",
            )
        )
        # Return 0 anyway — devices found is a pass for Phase 1
        return 0


def main() -> None:
    """Parse CLI arguments and execute the diagnostic coroutine."""
    parser = argparse.ArgumentParser(
        prog="diag_bluetooth.py",
        description=(
            "Linux-iPhone-Link Phase 1 — Bluetooth Diagnostic Tool.\n"
            "Validates BlueZ connectivity, adapter status, and paired iOS device discovery."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print full adapter property dumps and device UUID lists.",
    )
    parser.add_argument(
        "--adapter",
        default=None,
        metavar="hciN",
        help="Target a specific Bluetooth adapter (e.g. hci0). Default: all adapters.",
    )
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run_diagnostics(args))
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
        sys.exit(130)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
