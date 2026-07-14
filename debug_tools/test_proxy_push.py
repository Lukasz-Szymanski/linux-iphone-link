import asyncio, dbus_next
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def test():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    xml = """<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
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
        </node>"""
    
    proxy = bus.get_proxy_object("org.bluez.obex", "/org/bluez/obex/client/session29", xml)
    iface = proxy.get_interface("org.bluez.obex.MessageAccess1")
    
    try:
        reply = await iface.call_push_message("/path/to/nonexistent", "", {})
        print("REPLY:", reply)
    except Exception as e:
        print("EXCEPTION:", type(e), str(e))

asyncio.run(test())
