import asyncio
import os
import tempfile
import threading
from flask import Flask, render_template, jsonify, request
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant, Message, MessageType

app = Flask(__name__)
# You can set the MAC address via environment variable:
# export IPHONE_MAC="XX:XX:XX:XX:XX:XX"
MAC_ADDRESS = os.environ.get("IPHONE_MAC", "BRAK_ADRESU_MAC")

async def _discover_iphone_mac():
    try:
        sys_bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        intro = await sys_bus.introspect('org.bluez', '/')
        proxy = sys_bus.get_proxy_object('org.bluez', '/', intro)
        obj_manager = proxy.get_interface('org.freedesktop.DBus.ObjectManager')
        managed_objects = await obj_manager.call_get_managed_objects()
        
        for path, interfaces in managed_objects.items():
            if 'org.bluez.Device1' in interfaces:
                props = interfaces['org.bluez.Device1']
                paired = props.get('Paired', Variant('b', False)).value
                trusted = props.get('Trusted', Variant('b', False)).value
                if paired and trusted:
                    name = props.get('Name', Variant('s', '')).value.lower()
                    vendor = props.get('Vendor', Variant('s', '')).value.lower()
                    if 'apple' in name or 'iphone' in name or 'apple' in vendor:
                        return props.get('Address', Variant('s', '')).value
        # Fallback to first paired/trusted device
        for path, interfaces in managed_objects.items():
            if 'org.bluez.Device1' in interfaces:
                props = interfaces['org.bluez.Device1']
                if props.get('Paired', Variant('b', False)).value and props.get('Trusted', Variant('b', False)).value:
                    return props.get('Address', Variant('s', '')).value
    except Exception as e:
        print(f"Auto-discovery failed: {e}")
    return None

_global_loop = asyncio.new_event_loop()
def _start_global_loop():
    asyncio.set_event_loop(_global_loop)
    _global_loop.run_forever()
threading.Thread(target=_start_global_loop, daemon=True).start()

_shared_bus = None
async def get_shared_bus():
    global _shared_bus
    if _shared_bus is None:
        _shared_bus = await MessageBus(bus_type=BusType.SESSION).connect()
    return _shared_bus

async def get_map_session():
    global MAC_ADDRESS
    if MAC_ADDRESS == "BRAK_ADRESU_MAC" or not MAC_ADDRESS:
        discovered = await _discover_iphone_mac()
        if discovered:
            MAC_ADDRESS = discovered
        else:
            return None, None, "Nie ustawiono IPHONE_MAC, a autowykrywanie nie znalazło sparowanego telefonu."
            
    try:
        bus = await get_shared_bus()
        
        obj_manager_intro = await bus.introspect('org.bluez.obex', '/')
        obj_manager_proxy = bus.get_proxy_object('org.bluez.obex', '/', obj_manager_intro)
        obj_manager = obj_manager_proxy.get_interface('org.freedesktop.DBus.ObjectManager')
        
        managed_objects = await obj_manager.call_get_managed_objects()
        session_path = None
        
        for path, interfaces in managed_objects.items():
            if 'org.bluez.obex.Session1' in interfaces and 'org.bluez.obex.MessageAccess1' in interfaces:
                props = interfaces['org.bluez.obex.Session1']
                dest = props.get('Destination', Variant('s', '')).value
                if dest.upper() == MAC_ADDRESS.upper():
                    session_path = path
                    break
                
        if not session_path:
            introspection = await bus.introspect('org.bluez.obex', '/org/bluez/obex')
            obex_proxy = bus.get_proxy_object('org.bluez.obex', '/org/bluez/obex', introspection)
            obex_client = obex_proxy.get_interface('org.bluez.obex.Client1')
            last_error = "Nie odnaleziono sesji (sesja wygasła?)"
            try:
                session_path = await obex_client.call_create_session(MAC_ADDRESS, {"Target": Variant('s', "map")})
                await asyncio.sleep(0.5) 
            except Exception as e:
                last_error = str(e)
            
            managed_objects = await obj_manager.call_get_managed_objects()
            session_path = None
            
            for path, interfaces in managed_objects.items():
                if 'org.bluez.obex.Session1' in interfaces and 'org.bluez.obex.MessageAccess1' in interfaces:
                    props = interfaces['org.bluez.obex.Session1']
                    dest = props.get('Destination', Variant('s', '')).value
                    if dest.upper() == MAC_ADDRESS.upper():
                        session_path = path
                        break
                        
            if not session_path:
                err_msg = f"Nie udało się połączyć z urządzeniem (brak MAP): {last_error}"
                print(f"\n[BŁĄD POŁĄCZENIA MAP] {err_msg}\n")
                return None, None, err_msg
                
        return bus, session_path, None
    except Exception as e:
        err_msg = f"Błąd inicjalizacji DBus: {str(e)}"
        print(f"\n[BŁĄD INICJALIZACJI DBUS] {err_msg}\n")
        return None, None, err_msg

@app.route('/')
def index():
    return render_template('index.html')

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _global_loop)
    return future.result()

@app.route('/api/messages')
def list_messages():
    return run_async(_list_messages_async())

async def _list_messages_async():
    try:
        bus, session_path, err = await get_map_session()
        if not session_path:
            err_msg = err or "Brak połączenia z iPhonem"
            print(f"\n[API POBIERANIA] {err_msg}\n")
            return jsonify({"error": err_msg}), 500
            
        intro = await bus.introspect('org.bluez.obex', session_path)
        proxy = bus.get_proxy_object('org.bluez.obex', session_path, intro)
        map_iface = proxy.get_interface('org.bluez.obex.MessageAccess1')
        
        try:
            # Try to navigate to inbox. If we are already there from a previous refresh, this will fail.
            await map_iface.call_set_folder('telecom/msg/inbox')
        except Exception:
            pass # We are likely already in the inbox folder
            
        filters = {"MaxCount": Variant('q', 20)}
        messages_dbus = await map_iface.call_list_messages("", filters)
        
        results = []
        for msg_path, msg_props in messages_dbus.items():
            results.append({
                "path": msg_path,
                "subject": msg_props.get('Subject', Variant('s', '<Szyfrowane>')).value,
                "sender": msg_props.get('Sender', Variant('s', 'Nieznany')).value,
                "sender_name": msg_props.get('SenderName', Variant('s', '')).value,
                "timestamp": msg_props.get('Timestamp', Variant('s', '')).value,
                "type": msg_props.get('Type', Variant('s', 'sms')).value,
                "status": msg_props.get('Status', Variant('s', 'read')).value
            })
            
        return jsonify({"messages": results})
    except Exception as e:
        err_msg = str(e)
        if "MessageAccess1" in err_msg:
            err_msg = "iPhone odrzucił dostęp. Wejdź w iPhonie w Ustawienia -> Bluetooth -> [Komputer] i włącz 'Pokaż powiadomienia'. Następnie w terminalu wpisz: systemctl --user restart obex"
            
        print(f"\n[API POBIERANIA - WYJĄTEK] {err_msg}\n")
        return jsonify({"error": err_msg}), 500

@app.route('/api/send', methods=['POST'])
def send_message():
    return run_async(_send_message_async())

async def _send_message_async():
    data = request.json
    number = data.get('number')
    text = data.get('text')
    
    if not number or not text:
        return jsonify({"error": "Brak numeru lub treści"}), 400

    bus, session_path, err = await get_map_session()
    if err:
        print(f"\n[API WYSYŁANIA] Błąd połączenia: {err}\n")
        return jsonify({"error": err}), 500
        
    msg_part = f"BEGIN:MSG\r\n{text}\r\nEND:MSG\r\n"
    msg_length = len(msg_part.encode('utf-8'))
    
    bmsg_content = f"BEGIN:BMSG\r\nVERSION:1.0\r\nSTATUS:UNREAD\r\nTYPE:SMS_GSM\r\nFOLDER:telecom/msg/outbox\r\nBEGIN:BENV\r\nBEGIN:VCARD\r\nVERSION:2.1\r\nTEL:{number}\r\nEND:VCARD\r\nBEGIN:BBODY\r\nCHARSET:UTF-8\r\nLENGTH:{msg_length}\r\n{msg_part}END:BBODY\r\nEND:BENV\r\nEND:BMSG\r\n"
    
    fd, path = tempfile.mkstemp(suffix=".bmsg")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(bmsg_content)
        
    try:
        # RAW DBUS MESSAGE TO AVOID ANY DBUS-NEXT INTROSPECTION TYPOS
        msg = Message(
            destination='org.bluez.obex',
            path=session_path,
            interface='org.bluez.obex.MessageAccess1',
            member='PushMessage',
            signature='ssa{sv}',
            body=[path, "", {}],
            message_type=MessageType.METHOD_CALL
        )
        
        reply = await bus.call(msg)
        
        if reply.message_type == MessageType.ERROR:
            if "UnknownObject" in reply.error_name or "UnknownMethod" in reply.error_name:
                err_msg = "Błąd: Sesja z telefonem wygasła lub telefon nie zezwolił na MAP. Spróbuj odświeżyć stronę lub wejdź w Ustawienia -> Bluetooth w telefonie."
                print(f"\n[BŁĄD DBUS - WYSYŁANIE] {err_msg}\n")
                return jsonify({"error": err_msg}), 500
            err_msg = f"BlueZ Error: {reply.error_name} - {reply.body}"
            print(f"\n[BŁĄD DBUS - WYSYŁANIE] {err_msg}\n")
            return jsonify({"error": err_msg}), 500
            
        return jsonify({"success": True, "transfer": str(reply.body[0])})
    except Exception as e:
        print(f"\n[API WYSYŁANIA - WYJĄTEK] {str(e)}\n")
        return jsonify({"error": f"Wewnętrzny błąd: {str(e)}"}), 500
    finally:
        try:
            os.remove(path)
        except:
            pass

import threading
import webview
import time

def start_server():
    # Run without debug mode and reloader for stable background execution
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask in the background
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    
    time.sleep(1)
    
    # Launch the native desktop window (WebKitGTK)
    webview.create_window(
        'Linux iPhone Link', 
        'http://127.0.0.1:5000', 
        width=1100, 
        height=750, 
        background_color='#0f172a'
    )
    webview.start()
