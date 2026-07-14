import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    # Let's see all devices and their ServicesResolved property
    introspection = await bus.introspect('org.bluez', '/')
    proxy = bus.get_proxy_object('org.bluez', '/', introspection)
    obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    managed = await obj_manager.call_get_managed_objects()
    for path, ifaces in managed.items():
        if 'org.bluez.Device1' in ifaces:
            props = ifaces['org.bluez.Device1']
            print(f"Device: {props.get('Address').value} - Connected: {props.get('Connected').value} - ServicesResolved: {props.get('ServicesResolved').value}")
            if props.get('UUIDs'):
                print(f"UUIDs: {props.get('UUIDs').value}")

asyncio.run(main())
