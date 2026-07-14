import asyncio, dbus_next
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    reply = await bus.call(
        dbus_next.Message(
            destination='org.bluez.obex',
            path='/',
            interface='org.freedesktop.DBus.ObjectManager',
            member='GetManagedObjects'
        )
    )
    import json
    for path, ifaces in reply.body[0].items():
        print(path, list(ifaces.keys()))

asyncio.run(test())
