from web_app.app import app
from flask import jsonify

with app.test_request_context():
    res = jsonify({"error": None or "Brak połączenia z iPhonem"})
    print(res.data)
