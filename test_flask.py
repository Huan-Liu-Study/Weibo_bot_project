import traceback
from server import app
import json

app.testing = True
client = app.test_client()

try:
    print("Sending POST request to /api/detect")
    response = client.post('/api/detect', json={'topic': '谢娜晒倒立照', 'limit': 5})
    print("Status code:", response.status_code)
    print("Response data:", response.data.decode('utf-8'))
except Exception as e:
    print("CAUGHT EXCEPTION IN TEST CLIENT:")
    traceback.print_exc()
