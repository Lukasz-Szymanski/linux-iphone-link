#!/usr/bin/env python3
import asyncio
import pexpect
import sys
from bleak import BleakScanner
from rich.console import Console

console = Console()

async def find_iphone_mac():
    console.print("[dim]Scanning for iPhone BLE signals... (Keep iPhone screen ON)[/]")
    devices_dict = await BleakScanner.discover(timeout=5.0, return_adv=True)
    apple_devices = []
    
    for address, (d, adv) in devices_dict.items():
        if 76 in (adv.manufacturer_data or {}):
            apple_devices.append((address, adv.rssi))
            
    if not apple_devices:
        return None
        
    apple_devices.sort(key=lambda x: x[1], reverse=True)
    return apple_devices[0][0]

def auto_pair(mac):
    console.print(f"[bold cyan]Starting automated Bluetooth Agent for MAC: {mac}[/]")
    
    # Odpalamy pod spodem bluetoothctl i wchodzimy w interakcję
    child = pexpect.spawn('bluetoothctl', encoding='utf-8')
    
    child.expect('>', timeout=5)
    child.sendline('agent on')
    child.expect('Agent registered', timeout=5)
    child.sendline('default-agent')
    child.expect('Default agent request successful', timeout=5)
    
    console.print("[bold yellow]Agent (robot) gotowy. Wymuszam parowanie... PATRZ NA EKRAN IPHONE'A![/]")
    child.sendline(f'pair {mac}')
    
    success = False
    while True:
        try:
            # Oczekujemy na jedną z poniższych fraz z terminala
            idx = child.expect([
                'Confirm passkey', 
                'Accept pairing', 
                'Pairing successful', 
                'Failed', 
                'not available',
                pexpect.EOF, 
                pexpect.TIMEOUT
            ], timeout=15)
            
            if idx == 0 or idx == 1:
                console.print("[dim]🤖 Robot: Automatycznie zatwierdzam kod PIN w Linuksie...[/dim]")
                child.sendline('yes')
            elif idx == 2:
                console.print("[bold green]✔ Parowanie sprzętowe powiodło się![/]")
                success = True
                break
            elif idx == 3 or idx == 4:
                console.print("[bold red]✘ BlueZ odrzucił parowanie. Upewnij się, że nie jest połączony w ustawieniach.[/]")
                break
            else:
                console.print("[bold red]✘ Upłynął czas (Timeout). iPhone nie odpowiedział.[/]")
                break
        except Exception as e:
            console.print(f"[bold red]✘ Wystąpił błąd robota:[/] {e}")
            break
            
    if success:
        console.print("[yellow]Ustawiam status zaufania (Trust)...[/]")
        child.sendline(f'trust {mac}')
        child.expect('>', timeout=5)
        
        console.print("[bold green]✔ Telefon w 100% zaufany i sparowany w standardzie BLE![/]")
    
    child.sendline('quit')
    child.close()
    return success

async def main():
    console.print("[bold magenta]Linux-iPhone-Link — Smart Auto-Agent[/]")
    mac = await find_iphone_mac()
    
    if not mac:
        console.print("[bold red]✘ Nie znaleziono iPhone'a. Wybudź telefon i wejdź w Ustawienia -> Bluetooth.[/]")
        sys.exit(1)
        
    console.print(f"[bold green]✔ Znaleziono Twój telefon z adresem BLE:[/] {mac}")
    
    success = auto_pair(mac)
    if success:
        console.print("\n[bold cyan]Odpal teraz docelowy skrypt. Skopiuj i wklej to:[/]")
        console.print(f"python3 ancs_listener.py --mac {mac}")
    else:
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
