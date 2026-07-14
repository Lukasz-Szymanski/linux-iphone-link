import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        introspection = await bus.introspect('org.bluez.obex', '/')
        proxy = bus.get_proxy_object('org.bluez.obex', '/', introspection)
        obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
        managed = await obj_manager.call_get_managed_objects()
        
        print("--- Active OBEX Sessions ---")
        found = False
        for path, ifaces in managed.items():
            if 'org.bluez.obex.MessageAccess1' in ifaces:
                print(f"Message Access Profile Found: {path}")
                found = True
            elif 'org.bluez.obex.Session1' in ifaces:
                print(f"Session Found: {path}")
        
        if not found:
            print("No active OBEX Message Access sessions. We might need to initiate one.")
            
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
