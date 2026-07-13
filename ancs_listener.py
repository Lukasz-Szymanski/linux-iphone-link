#!/usr/bin/env python3
"""
ancs_listener.py — Linux-iPhone-Link Phase 2
==============================================================

Establishes a BLE GATT connection to a paired iPhone, subscribes
to the ANCS Notification Source characteristic, and dumps raw
binary payloads to stdout as notifications arrive.

Usage:
    python3 ancs_listener.py [--mac XX:XX:XX:XX:XX:XX]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

# Third-party imports
try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.characteristic import BleakGATTCharacteristic
    from bleak.exc import BleakError
except ImportError:
    print(
        "[FATAL] 'bleak' is not installed.\n"
        "  Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    print(
        "[FATAL] 'rich' is not installed.\n"
        "  Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# ANCS Constants
ANCS_SERVICE_UUID = "7905f431-b5ce-4e99-a40f-4b1e122d00d6"
NOTIFICATION_SOURCE_UUID = "9fbf120d-6301-42d9-8c58-25e699a21dbd"
CONTROL_POINT_UUID = "69d1d8f3-45e1-49a8-9821-9bbdfdaad9d9"
DATA_SOURCE_UUID = "22eac6e9-24d6-4bb5-be44-b36ace7c7bfb"

console = Console()


def notification_handler(sender: BleakGATTCharacteristic, data: bytearray) -> None:
    """Callback for incoming ANCS Notification Source payloads."""
    hex_data = data.hex(" ")
    dec_data = list(data)
    
    # In Phase 2, we just dump the raw packet.
    console.print(f"\n[bold cyan]🛎️  Incoming ANCS Payload:[/] [yellow]{hex_data}[/]")
    console.print(f"   [dim]Raw bytes: {dec_data}[/]")


async def find_apple_device() -> BLEDevice | None:
    """Scan and find a BLE device advertising the ANCS service or Apple Manufacturer Data."""
    console.print("[dim]Scanning for ANCS-compatible iOS devices...[/]")
    # return_adv=True returns a dict: address -> (BLEDevice, AdvertisementData)
    devices_dict = await BleakScanner.discover(timeout=5.0, return_adv=True)
    
    for address, (d, adv) in devices_dict.items():
        # Check if ANCS UUID is in advertised services
        uuids = adv.service_uuids or []
        if ANCS_SERVICE_UUID in [str(u).lower() for u in uuids]:
            return d
        
        # Check Manufacturer data for Apple (0x004C / 76)
        manufacturer_data = adv.manufacturer_data or {}
        if 76 in manufacturer_data:
            return d

    return None


async def connect_and_listen(mac_address: str | None) -> None:
    """Connect to the iPhone and subscribe to ANCS notifications with reconnect logic."""
    while True:
        device = None
        
        if mac_address:
            # Bypass scanner cache by constructing BLEDevice manually
            # This is necessary because already-connected devices might not be in the active scan cache
            device = BLEDevice(mac_address, mac_address, {}, rssi=0)
        else:
            device = await find_apple_device()
            if not device:
                console.print("[red]✘[/] No paired Apple devices found during scan.")
                console.print("[yellow]Retrying in 5 seconds...[/]")
                await asyncio.sleep(5)
                continue

        address_to_print = device.address if isinstance(device, BLEDevice) else device
        console.print(f"[bold blue]🔄 Attempting to connect to {address_to_print}...[/]")

        try:
            # iOS BLE connections can sometimes take longer than the default timeout
            async with BleakClient(device, timeout=20.0) as client:
                console.print(f"[bold green]✔[/] Connected to [bold]{address_to_print}[/]")
                
                # Force BLE pairing to trigger the iOS "Share Notifications" prompt
                try:
                    console.print("[dim]Requesting BLE pairing (check your iPhone screen)...[/]")
                    await client.pair()
                except Exception as e:
                    console.print(f"[dim]Pairing request info: {e}[/]")
                
                # Verify ANCS service is present
                # After pairing, iOS might take a few seconds to expose ANCS in the GATT table. We loop and wait.
                ancs_service = None
                for attempt in range(10):
                    services = await client.get_services()
                    ancs_service = services.get_service(ANCS_SERVICE_UUID)
                    if ancs_service:
                        break
                    console.print(f"[dim]Waiting for ANCS service to appear in GATT table (attempt {attempt+1}/10)...[/]")
                    await asyncio.sleep(2.0)
                
                if not ancs_service:
                    console.print("[bold red]✘[/] ANCS Service not found on this device after 20 seconds!")
                    console.print("[yellow]Ensure the device is trusted, and you clicked 'Allow' on iPhone.[/]")
                    return

                console.print("[bold green]✔[/] ANCS Service discovered.")
                
                # Subscribe to Notification Source
                await client.start_notify(NOTIFICATION_SOURCE_UUID, notification_handler)
                console.print("[bold green]✔[/] Subscribed to ANCS Notification Source.")
                
                console.print(
                    Panel.fit(
                        "🎧 [bold]Listening for iOS notifications...[/]\n"
                        "[dim]Press Ctrl+C to stop.\n"
                        "Send a test notification to your iPhone to see the raw payload.[/]",
                        border_style="cyan"
                    )
                )

                # Keep connection alive until disconnected
                while client.is_connected:
                    await asyncio.sleep(1)

            console.print("\n[bold yellow]⚠[/] Disconnected from device. Reconnecting...")

        except BleakError as e:
            console.print(f"[bold red]✘[/] BLE Error: {e}")
            console.print("[dim]Retrying in 5 seconds...[/]")
            await asyncio.sleep(5)
        except Exception as e:
            import traceback
            console.print(f"[bold red]✘[/] Unexpected Error: {repr(e)}")
            console.print(f"[dim]{traceback.format_exc()}[/]")
            console.print("[dim]Retrying in 5 seconds...[/]")
            await asyncio.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ancs_listener.py",
        description="Linux-iPhone-Link Phase 2 — ANCS Raw Payload Listener."
    )
    parser.add_argument(
        "--mac",
        "-m",
        default=None,
        help="Target a specific iPhone MAC address. If omitted, auto-discovers Apple devices.",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold white]Linux-iPhone-Link[/] — ANCS Raw Listener\n"
            "[dim]Phase 2: BLE GATT Subscription & Payload Capture[/]",
            border_style="magenta",
        )
    )

    try:
        asyncio.run(connect_and_listen(args.mac))
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Stop requested by user. Exiting...[/]")
        sys.exit(0)


if __name__ == "__main__":
    main()
