import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    introspection = await bus.introspect('org.bluez.obex', '/')
    proxy = bus.get_proxy_object('org.bluez.obex', '/', introspection)
    obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    
    managed_objects = await obj_manager.call_get_managed_objects()
    print(f"Znaleziono {len(managed_objects)} obiektów DBus w OBEX.")
    
    for path, interfaces in managed_objects.items():
        if 'org.bluez.obex.Session1' in interfaces:
            print(f"SESJA: {path}")
            props = interfaces['org.bluez.obex.Session1']
            for k, v in props.items():
                print(f"  {k}: {v.value}")

asyncio.run(main())
