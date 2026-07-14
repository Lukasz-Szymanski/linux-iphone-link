import asyncio, dbus_next
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    msg = dbus_next.Message(
        destination="org.bluez.obex",
        path="/org/bluez/obex/client/session29",
        interface="org.bluez.obex.MessageAccess1",
        member="PushMessage",
        signature="ssa{sv}",
        body=["/path/to/nonexistent", "", {}]
    )
    reply = await bus.call(msg)
    print("ERROR_NAME:", reply.error_name)
    print("ERROR_BODY:", reply.body)

asyncio.run(test())
