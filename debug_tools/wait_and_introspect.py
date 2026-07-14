import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType
import xml.etree.ElementTree as ET

async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    print("Czekam na sesję MAP...")
    while True:
        try:
            reply = await bus.call(
                dbus_next.Message(
                    destination='org.bluez.obex',
                    path='/',
                    interface='org.freedesktop.DBus.ObjectManager',
                    member='GetManagedObjects'
                )
            )
            managed_objects = reply.body[0]
            for path, ifaces in managed_objects.items():
                if 'org.bluez.obex.MessageAccess1' in ifaces:
                    print(f"Znalazłem sesję: {path}")
                    reply = await bus.call(
                        dbus_next.Message(
                            destination='org.bluez.obex',
                            path=path,
                            interface='org.freedesktop.DBus.Introspectable',
                            member='Introspect'
                        )
                    )
                    xml = reply.body[0]
                    root = ET.fromstring(xml)
                    for iface in root.findall('interface'):
                        if iface.get('name') == 'org.bluez.obex.MessageAccess1':
                            print("Sygnatury metod w MessageAccess1:")
                            for method in iface.findall('method'):
                                args = []
                                for arg in method.findall('arg'):
                                    args.append(f"{arg.get('direction')}:{arg.get('type')}({arg.get('name')})")
                                print(f"  {method.get('name')} -> {', '.join(args)}")
                    return
        except Exception as e:
            pass
        await asyncio.sleep(1)

asyncio.run(main())
