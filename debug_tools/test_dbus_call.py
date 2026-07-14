import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType, Message, MessageType

async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # Znajdź sesję
    obj_manager_intro = await bus.introspect('org.bluez.obex', '/')
    obj_manager_proxy = bus.get_proxy_object('org.bluez.obex', '/', obj_manager_intro)
    obj_manager = obj_manager_proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    
    managed_objects = await obj_manager.call_get_managed_objects()
    session_path = None
    for path, interfaces in managed_objects.items():
        if 'org.bluez.obex.MessageAccess1' in interfaces:
            session_path = path
            break
            
    if not session_path:
        print("Brak sesji")
        return
        
    print(f"Testuję wywołanie na {session_path}...")
    
    # Test 1: 2 argumenty (sa{sv})
    msg1 = Message(destination='org.bluez.obex',
                   path=session_path,
                   interface='org.bluez.obex.MessageAccess1',
                   member='PushMessage',
                   signature='sa{sv}',
                   body=['/tmp/test.bmsg', {}])
                   
    try:
        reply1 = await bus.call(msg1)
        if reply1.message_type == MessageType.ERROR:
            print(f"Test 1 (sa{{sv}}) Error: {reply1.error_name} - {reply1.body}")
        else:
            print("Test 1 (sa{sv}) SUCCESS!")
    except Exception as e:
        print(f"Test 1 Exception: {e}")
        
    # Test 2: 3 argumenty (ssa{sv})
    msg2 = Message(destination='org.bluez.obex',
                   path=session_path,
                   interface='org.bluez.obex.MessageAccess1',
                   member='PushMessage',
                   signature='ssa{sv}',
                   body=['/tmp/test.bmsg', '', {}])
                   
    try:
        reply2 = await bus.call(msg2)
        if reply2.message_type == MessageType.ERROR:
            print(f"Test 2 (ssa{{sv}}) Error: {reply2.error_name} - {reply2.body}")
        else:
            print("Test 2 (ssa{sv}) SUCCESS!")
    except Exception as e:
        print(f"Test 2 Exception: {e}")

asyncio.run(main())
