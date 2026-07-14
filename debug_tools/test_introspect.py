import asyncio, dbus_next
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # Znajdź aktywną sesję
    reply = await bus.call(
        dbus_next.Message(
            destination='org.bluez.obex',
            path='/',
            interface='org.freedesktop.DBus.ObjectManager',
            member='GetManagedObjects'
        )
    )
    managed_objects = reply.body[0]
    session_path = None
    for path, ifaces in managed_objects.items():
        if 'org.bluez.obex.MessageAccess1' in ifaces:
            session_path = path
            break
            
    if not session_path:
        print("Brak aktywnej sesji MAP do introspekcji!")
        return
        
    print(f"Znalazłem sesję MAP: {session_path}")
    
    # Introspect
    reply = await bus.call(
        dbus_next.Message(
            destination='org.bluez.obex',
            path=session_path,
            interface='org.freedesktop.DBus.Introspectable',
            member='Introspect'
        )
    )
    xml = reply.body[0]
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    for iface in root.findall('interface'):
        if iface.get('name') == 'org.bluez.obex.MessageAccess1':
            for method in iface.findall('method'):
                if method.get('name') == 'PushMessage':
                    print("Znalazłem PushMessage!")
                    for arg in method.findall('arg'):
                        print(f"  Arg: name={arg.get('name')} type={arg.get('type')} direction={arg.get('direction')}")

asyncio.run(test())
