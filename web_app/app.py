import asyncio
import os
import tempfile
from flask import Flask, render_template, jsonify, request
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant, Message, MessageType

app = Flask(__name__)
# Można ustawić adres MAC poprzez zmienną środowiskową:
# export IPHONE_MAC="XX:XX:XX:XX:XX:XX"
MAC_ADDRESS = os.environ.get("IPHONE_MAC", "BRAK_ADRESU_MAC")

async def get_map_session():
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        
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
                return None, None, f"Nie udało się połączyć z urządzeniem (brak MAP): {last_error}"
                
        return bus, session_path, None
    except Exception as e:
        return None, None, f"Błąd inicjalizacji DBus: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages')
async def list_messages():
    try:
        bus, session_path, err = await get_map_session()
        if not session_path:
            return jsonify({"error": err or "Brak połączenia z iPhonem"}), 500
            
        intro = await bus.introspect('org.bluez.obex', session_path)
        proxy = bus.get_proxy_object('org.bluez.obex', session_path, intro)
        map_iface = proxy.get_interface('org.bluez.obex.MessageAccess1')
        
        await map_iface.call_set_folder('telecom/msg/inbox')
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
                "type": msg_props.get('Type', Variant('s', 'sms')).value
            })
            
        return jsonify({"messages": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/send', methods=['POST'])
async def send_message():
    data = request.json
    number = data.get('number')
    text = data.get('text')
    
    if not number or not text:
        return jsonify({"error": "Brak numeru lub treści"}), 400

    bus, session_path, err = await get_map_session()
    if err:
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
                return jsonify({"error": "Błąd: Sesja z telefonem wygasła lub telefon nie zezwolił na MAP. Spróbuj odświeżyć stronę lub wejdź w Ustawienia -> Bluetooth w telefonie."}), 500
            return jsonify({"error": f"BlueZ Error: {reply.error_name} - {reply.body}"}), 500
            
        return jsonify({"success": True, "transfer": str(reply.body[0])})
    except Exception as e:
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
    # Uruchamiamy bez debug mode i reloader'a, by działało stabilnie jako desktop app
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Flask startuje w tle
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    
    time.sleep(1)
    
    # Odpalamy natywne okno (WebKitGTK)
    webview.create_window(
        'Linux iPhone Link', 
        'http://127.0.0.1:5000', 
        width=1100, 
        height=750, 
        background_color='#0f172a'
    )
    webview.start()
