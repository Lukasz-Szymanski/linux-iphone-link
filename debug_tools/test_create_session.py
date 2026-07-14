import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # XX:XX:XX:XX:XX:XX
    import dbus_next
    msg = dbus_next.Message(
        destination='org.bluez.obex',
        path='/org/bluez/obex',
        interface='org.bluez.obex.Client1',
        member='CreateSession',
        signature='sa{sv}',
        body=["XX:XX:XX:XX:XX:XX", {"Target": Variant('s', "map")}]
    )
    
    reply = await bus.call(msg)
    print("REPLY:", reply.body if reply else None)

asyncio.run(test())
