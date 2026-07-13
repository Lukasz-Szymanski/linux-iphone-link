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
        if 'org.bluez.obex.Session1' in interfaces and 'org.bluez.obex.MessageAccess1' in interfaces:
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
        last_error = "Nie odnaleziono sesji (sesja wygasła?)"
        try:
            session_path = await obex_client.call_create_session(MAC_ADDRESS, {"Target": Variant('s', "map")})
            import asyncio
            await asyncio.sleep(0.5) # Czekamy aż obexd podepnie interfejs MAP
        except Exception as e:
            last_error = str(e)
            
        # Zawsze weryfikujemy czy interfejs istnieje
        managed_objects = await obj_manager.call_get_managed_objects()
        session_path = None # Reset i szukamy ponownie by upewnić się że ma MessageAccess1
        for path, interfaces in managed_objects.items():
            if 'org.bluez.obex.Session1' in interfaces and 'org.bluez.obex.MessageAccess1' in interfaces:
                props = interfaces['org.bluez.obex.Session1']
                dest = props.get('Destination', Variant('s', '')).value
                if dest.upper() == MAC_ADDRESS.upper():
                    session_path = path
                    break
                            
    if not session_path:
        return None, None, None, f"Nie udało się połączyć z urządzeniem: {last_error}"
        
    try:
        session_intro = await bus.introspect('org.bluez.obex', session_path)
        session_proxy = bus.get_proxy_object('org.bluez.obex', session_path, session_intro)
        map_iface = session_proxy.get_interface('org.bluez.obex.MessageAccess1')
        return bus, map_iface, session_path, None
    except Exception as e:
        # Introspekcja zawiodła, ale sesja istnieje. Zwracamy bus by wykonać raw call.
        return bus, None, session_path, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages')
async def list_messages():
    try:
        bus, map_iface, _, err = await get_map_session()
        if not map_iface:
            return jsonify({"error": err or "Brak połączenia z iPhonem"}), 500
    except Exception as e:
        return jsonify({"error": f"Błąd DBus: {str(e)}"}), 500
        
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
        
    try:
        bus, map_iface, session_path, err = await get_map_session()
        if not session_path:
            return jsonify({"error": err or "Brak sesji MAP"}), 500
    except Exception as e:
        return jsonify({"error": f"Błąd inicjalizacji DBus: {str(e)}"}), 500
        
    # Tworzymy plik w standardzie bMessage (vMessage) dla systemu OBEX
    # Zgodnie ze specyfikacją MAP musi zawierać zakończenia linii \r\n
    msg_part = f"BEGIN:MSG\r\n{text}\r\nEND:MSG\r\n"
    msg_length = len(msg_part.encode('utf-8'))
    
    bmsg_content = f"BEGIN:BMSG\r\n" \
                   f"VERSION:1.0\r\n" \
                   f"STATUS:UNREAD\r\n" \
                   f"TYPE:SMS_GSM\r\n" \
                   f"FOLDER:telecom/msg/outbox\r\n" \
                   f"BEGIN:BENV\r\n" \
                   f"BEGIN:VCARD\r\n" \
                   f"VERSION:2.1\r\n" \
                   f"TEL:{number}\r\n" \
                   f"END:VCARD\r\n" \
                   f"BEGIN:BBODY\r\n" \
                   f"CHARSET:UTF-8\r\n" \
                   f"LENGTH:{msg_length}\r\n" \
                   f"{msg_part}" \
                   f"END:BBODY\r\n" \
                   f"END:BENV\r\n" \
                   f"END:BMSG\r\n"
    
    fd, path = tempfile.mkstemp(suffix=".bmsg")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(bmsg_content)
        
    try:
        from dbus_next import Message, MessageType
        
        # Tworzymy RAW Message zamiast polegać na map_iface.call_push_message
        msg = Message(destination='org.bluez.obex',
                      path=session_path,
                      interface='org.bluez.obex.MessageAccess1',
                      member='PushMessage',
                      signature='ssa{sv}',
                      body=[path, "", {}])
                      
        reply = await bus.call(msg)
        
        if reply.message_type == MessageType.ERROR:
            return jsonify({"error": f"BlueZ Error: {reply.error_name} - {reply.body}"}), 500
            
        transfer = reply.body[0] if reply.body else "unknown"
        return jsonify({"success": True, "transfer": str(transfer)})
    except Exception as e:
        return jsonify({"error": f"BlueZ Error: {str(e)}"}), 500
    finally:
        # Usuwamy plik tymczasowy po wysłaniu
        try:
            os.remove(path)
        except:
            pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
