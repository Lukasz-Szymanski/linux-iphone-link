#!/usr/bin/env python3
import asyncio
import sys
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant
from rich.console import Console

console = Console()

async def main():
    mac = "XX:XX:XX:XX:XX:XX"  # Klasyczny adres MAC Twojego iPhone'a
    console.print(f"[bold cyan]Linux-iPhone-Link — MAP SMS Reader[/]")
    console.print(f"[dim]Initiating OBEX MAP session with {mac}...[/dim]")
    
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
    except Exception as e:
        console.print(f"[red]Failed to connect to SESSION bus: {e}[/]")
        return
        
    # 1. Uzyskujemy interfejs klienta OBEX
    try:
        introspection = await bus.introspect('org.bluez.obex', '/org/bluez/obex')
        obex_proxy = bus.get_proxy_object('org.bluez.obex', '/org/bluez/obex', introspection)
        obex_client = obex_proxy.get_interface('org.bluez.obex.Client1')
    except Exception as e:
        console.print(f"[red]Błąd OBEX (upewnij się, że obexd działa): {e}[/]")
        return
    
    # 2. Tworzymy sesję Message Access Profile (MAP)
    try:
        session_path = await obex_client.call_create_session(mac, {"Target": Variant('s', "map")})
        console.print(f"[green]✔ Utworzono sesję OBEX MAP: {session_path}[/]")
    except Exception as e:
        console.print(f"[bold red]✘ Nie udało się utworzyć sesji MAP![/]")
        console.print(f"[yellow]Wskazówka: Upewnij się, że iPhone jest połączony w ustawieniach Bluetooth Linuksa i zezwoliłeś na dostęp do powiadomień/kontaktów.[/]")
        console.print(f"Szczegóły błędu: {e}")
        return
        
        # 3. Dostęp do interfejsu wiadomości
    try:
        session_intro = await bus.introspect('org.bluez.obex', session_path)
        session_proxy = bus.get_proxy_object('org.bluez.obex', session_path, session_intro)
        
        try:
            map_iface = session_proxy.get_interface('org.bluez.obex.MessageAccess1')
        except Exception:
            console.print("[red]✘ Urządzenie nie obsługuje (lub nie udostępniło) profilu MAP.[/]")
            return
        
        console.print("[yellow]Pobieranie wiadomości...[/]")
        
        # Przechodzimy do folderu odebranych wiadomości
        await map_iface.call_set_folder('telecom/msg/inbox')
        
        # Pobieramy najnowsze 10 wiadomości
        filters = {"MaxCount": Variant('q', 10)}
        messages = await map_iface.call_list_messages("", filters)
        
        console.print("\n[bold magenta]--- Skrzynka odbiorcza (Ostatnie 10 wiadomości) ---[/]\n")
        
        # Debugging the structure
        console.print(f"[dim]Debug: typ wiadomości = {type(messages)}[/dim]")
        
        for msg_path, msg_props in messages.items():
            subject = msg_props.get('Subject', Variant('s', '<Brak treści/Szyfrowane>')).value
            sender = msg_props.get('Sender', Variant('s', '<Nieznany>')).value
            sender_name = msg_props.get('SenderName', Variant('s', '')).value
            timestamp = msg_props.get('Timestamp', Variant('s', '')).value
            
            sender_display = f"{sender_name} ({sender})" if sender_name else sender
            console.print(f"[dim]{timestamp}[/] [bold green]{sender_display}[/]: {subject}")
            
    except Exception as e:
        console.print(f"[red]Błąd podczas pobierania SMS: {e}[/]")

if __name__ == '__main__':
    asyncio.run(main())
