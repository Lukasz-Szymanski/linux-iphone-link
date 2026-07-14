import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    introspection = await bus.introspect('org.bluez', '/')
    proxy = bus.get_proxy_object('org.bluez', '/', introspection)
    obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    managed = await obj_manager.call_get_managed_objects()
    
    found = False
    for path, ifaces in managed.items():
        if 'org.bluez.GattCharacteristic1' in ifaces:
            uuid = ifaces['org.bluez.GattCharacteristic1'].get('UUID').value
            if '9fbf120d' in uuid.lower():
                print(f"FOUND ANCS Notif Source at: {path}")
                found = True
    
    if not found:
        print("ANCS Characteristic not found in DBus.")

asyncio.run(main())
