#!/usr/bin/env python3
import asyncio
import subprocess
from bleak import BleakScanner
from rich.console import Console

console = Console()

async def pair_ios():
    console.print("[bold cyan]Scanning for iOS devices...[/]")
    console.print("[dim]Make sure your iPhone is unlocked and the Bluetooth settings screen is OPEN.[/dim]")
    
    devices_dict = await BleakScanner.discover(timeout=5.0, return_adv=True)
    
    apple_devices = []
    for address, (d, adv) in devices_dict.items():
        manufacturer_data = adv.manufacturer_data or {}
        if 76 in manufacturer_data:
            apple_devices.append((address, adv.rssi))
            
    if not apple_devices:
        console.print("[bold red]✘ No iPhone found in BLE range![/]")
        return
        
    # Sort by RSSI (signal strength) descending to pick the closest phone!
    apple_devices.sort(key=lambda x: x[1], reverse=True)
    target_mac = apple_devices[0][0]
        
    console.print(f"\n[bold green]✔ Found iPhone with BLE MAC:[/] [bold]{target_mac}[/]")
    console.print("[yellow]Initiating pairing through bluetoothctl...[/]")
    console.print("[bold magenta]LOOK AT YOUR IPHONE EKRAN NOW! Kliknij 'Pary/Pair'![/]\n")
    
    # Używamy systemowego narzędzia do wymuszenia parowania BLE
    subprocess.run(["bluetoothctl", "pair", target_mac])
    
    console.print("\n[yellow]Ustawianie zaufania...[/]")
    subprocess.run(["bluetoothctl", "trust", target_mac])
    
    console.print("\n[yellow]Nawiązywanie połączenia...[/]")
    subprocess.run(["bluetoothctl", "connect", target_mac])
    
    console.print("\n[bold green]Gotowe! Teraz powinieneś zaakceptować uprawnienia na iPhonie (Share Notifications).[/]")
    console.print(f"[bold cyan]Możesz teraz uruchomić skrypt z tym nowym MAC:[/] python3 ancs_listener.py --mac {target_mac}")

if __name__ == "__main__":
    asyncio.run(pair_ios())
