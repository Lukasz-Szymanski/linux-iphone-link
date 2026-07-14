import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # Hardcoded XML
    fake_xml = """
    <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
    "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
    <node>
        <interface name="org.bluez.obex.MessageAccess1">
            <method name="PushMessage">
                <arg name="file" type="s" direction="in"/>
                <arg name="folder" type="s" direction="in"/>
                <arg name="args" type="a{sv}" direction="in"/>
                <arg name="transfer" type="o" direction="out"/>
                <arg name="properties" type="a{sv}" direction="out"/>
            </method>
        </interface>
    </node>
    """
    
    proxy = bus.get_proxy_object('org.bluez.obex', '/org/bluez/obex/client/session0', fake_xml)
    iface = proxy.get_interface('org.bluez.obex.MessageAccess1')
    print("SUCCESS: Loaded iface with hardcoded XML!", iface)

asyncio.run(test())
