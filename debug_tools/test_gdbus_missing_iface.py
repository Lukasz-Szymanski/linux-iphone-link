import asyncio, dbus_next
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # Create session
    reply = await bus.call(dbus_next.Message(
        destination='org.bluez.obex', path='/org/bluez/obex',
        interface='org.bluez.obex.Client1', member='CreateSession',
        signature='sa{sv}', body=["XX:XX:XX:XX:XX:XX", {"Target": Variant('s', "pbap")}]
    ))
    session_path = reply.body[0]
    
    # Try calling PushMessage on MessageAccess1 (which PBAP session DOES NOT have)
    msg = dbus_next.Message(
        destination='org.bluez.obex', path=session_path,
        interface='org.bluez.obex.MessageAccess1', member='PushMessage',
        signature='ssa{sv}', body=["/tmp/test", "", {}]
    )
    reply = await bus.call(msg)
    print("ERROR:", reply.error_name, reply.body)

asyncio.run(test())
