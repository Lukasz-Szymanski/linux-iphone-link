import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    introspection = await bus.introspect('org.bluez.obex', '/')
    proxy = bus.get_proxy_object('org.bluez.obex', '/', introspection)
    obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    
    managed_objects = await obj_manager.call_get_managed_objects()
    for path, interfaces in managed_objects.items():
        if 'org.bluez.obex.MessageAccess1' in interfaces:
            print(f"Introspecting {path}")
            intro = await bus.introspect('org.bluez.obex', path)
            for node in intro.interfaces:
                if node.name == 'org.bluez.obex.MessageAccess1':
                    for method in node.methods:
                        if method.name == 'PushMessage':
                            args = [arg.signature for arg in method.in_args]
                            print(f"PushMessage signature: {''.join(args)}")
            break

asyncio.run(main())
