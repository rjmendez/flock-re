import http.client
import json
import threading

from tools.sandbox.https_phonehome_mock import build_server


def test_phonehome_mock_returns_parser_safe_success_payload():
    server = build_server('127.0.0.1', 0, cert='tools/sandbox/server.pem', plaintext=True)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    conn.request('POST', '/phonehome/fake', body='{}', headers={'Content-Type': 'application/json'})
    res = conn.getresponse()
    payload = json.loads(res.read().decode('utf-8'))
    conn.close()

    server.shutdown()
    server.server_close()
    thread.join(timeout=1)

    assert res.status == 200
    assert payload['status'] is True
    assert payload['fail_reason'] == ''
    assert payload['mock'] is True
