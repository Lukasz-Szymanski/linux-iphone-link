import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    introspection = await bus.introspect('org.bluez.obex', '/')
    proxy = bus.get_proxy_object('org.bluez.obex', '/', introspection)
    obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    
    managed = await obj_manager.call_get_managed_objects()
    for path, interfaces in managed.items():
        if 'org.bluez.obex.MessageAccess1' in interfaces:
            print(f"Znalazłem sesję MAP: {path}")
            intro = await bus.introspect('org.bluez.obex', path)
            for interface in intro.interfaces:
                if interface.name == 'org.bluez.obex.MessageAccess1':
                    print("Dostępne metody:")
                    for method in interface.methods:
                        args = [arg.signature for arg in method.in_args]
                        print(f" - {method.name}({', '.join(args)})")
            break

asyncio.run(main())
