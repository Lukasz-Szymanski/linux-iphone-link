import asyncio
from flask import Flask, render_template, jsonify, request
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant

app = Flask(__name__)
MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"

async def get_map_session():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    # Najpierw spróbujmy znaleźć istniejącą sesję MAP używając ObjectManager
    obj_manager_intro = await bus.introspect('org.bluez.obex', '/')
    obj_manager_proxy = bus.get_proxy_object('org.bluez.obex', '/', obj_manager_intro)
    obj_manager = obj_manager_proxy.get_interface('org.freedesktop.DBus.ObjectManager')
    
    managed_objects = await obj_manager.call_get_managed_objects()
    session_path = None
    
    for path, interfaces in managed_objects.items():
        if 'org.bluez.obex.Session1' in interfaces:
            props = interfaces['org.bluez.obex.Session1']
            dest = props.get('Destination', Variant('s', '')).value
            if dest.upper() == MAC_ADDRESS.upper():
                session_path = path
                break
            
    if not session_path:
        # Jeśli nie ma, próbujemy utworzyć nową
        introspection = await bus.introspect('org.bluez.obex', '/org/bluez/obex')
        obex_proxy = bus.get_proxy_object('org.bluez.obex', '/org/bluez/obex', introspection)
        obex_client = obex_proxy.get_interface('org.bluez.obex.Client1')
        try:
            session_path = await obex_client.call_create_session(MAC_ADDRESS, {"Target": Variant('s', "map")})
        except Exception as e:
            # Nie udało się utworzyć, spróbujmy odświeżyć listę
            managed_objects = await obj_manager.call_get_managed_objects()
            for path, interfaces in managed_objects.items():
                if 'org.bluez.obex.Session1' in interfaces:
                    props = interfaces['org.bluez.obex.Session1']
                    dest = props.get('Destination', Variant('s', '')).value
                    if dest.upper() == MAC_ADDRESS.upper():
                        session_path = path
                        break
            
    if not session_path:
        return None, None
        
    try:
        session_intro = await bus.introspect('org.bluez.obex', session_path)
        session_proxy = bus.get_proxy_object('org.bluez.obex', session_path, session_intro)
        map_iface = session_proxy.get_interface('org.bluez.obex.MessageAccess1')
        return map_iface, session_path
    except Exception:
        return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages')
async def list_messages():
    map_iface, _ = await get_map_session()
    if not map_iface:
        return jsonify({"error": "Brak połączenia z iPhonem"}), 500
        
    try:
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

import os
import tempfile

@app.route('/api/send', methods=['POST'])
async def send_message():
    data = request.json
    number = data.get('number')
    text = data.get('text')
    
    if not number or not text:
        return jsonify({"error": "Brak numeru lub treści"}), 400
        
    map_iface, _ = await get_map_session()
    if not map_iface:
        return jsonify({"error": "Brak sesji MAP"}), 500
        
    # Tworzymy plik w standardzie bMessage (vMessage) dla systemu OBEX
    bmsg_content = f"""BEGIN:BMSG
VERSION:1.0
STATUS:UNREAD
TYPE:SMS_GSM
FOLDER:telecom/msg/outbox
BEGIN:BENV
BEGIN:VCARD
VERSION:3.0
N:;{number};;;
TEL:{number}
END:VCARD
BEGIN:BBODY
ENCODING:8BIT
LENGTH:{len(text.encode('utf-8'))}
BEGIN:MSG
{text}
END:MSG
END:BBODY
END:BENV
END:BMSG"""

    fd, path = tempfile.mkstemp(suffix=".bmsg")
    with os.fdopen(fd, 'w') as f:
        f.write(bmsg_content)
        
    try:
        # Przekazujemy plik do demona obexd
        transfer = await map_iface.call_push_message(path, {})
        return jsonify({"success": True, "transfer": str(transfer)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Usuwamy plik tymczasowy po wysłaniu
        try:
            os.remove(path)
        except:
            pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
