import asyncio
from flask import Flask, render_template, jsonify, request
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant

app = Flask(__name__)
MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"

async def get_map_session():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    introspection = await bus.introspect('org.bluez.obex', '/org/bluez/obex')
    obex_proxy = bus.get_proxy_object('org.bluez.obex', '/org/bluez/obex', introspection)
    obex_client = obex_proxy.get_interface('org.bluez.obex.Client1')
    
    # Próbujemy znaleźć istniejącą sesję lub otworzyć nową
    try:
        session_path = await obex_client.call_create_session(MAC_ADDRESS, {"Target": Variant('s', "map")})
    except Exception as e:
        if "already exists" in str(e).lower() or "inprogress" in str(e).lower():
            # TODO: Wyszukać istniejącą sesję z DBus ObjectManager
            pass
        return None, None
        
    session_intro = await bus.introspect('org.bluez.obex', session_path)
    session_proxy = bus.get_proxy_object('org.bluez.obex', session_path, session_intro)
    
    try:
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
