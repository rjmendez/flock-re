import hashlib, json, os, socket, struct, sys, time
OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1,2,3,4,5,6,7,8,9,12

def connect(host='127.0.0.1', port=18081):
    s = socket.create_connection((host, port), timeout=5)
    return s

def recvn(s, n):
    b = b''
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError('closed')
        b += c
    return b

def hello(s, token='SANDBOX-FAKE-TOKEN'):
    payload = json.dumps({'authToken': token, 'serial': 'MOCK-000000', 'clientVersion': 'sandbox'}).encode()
    s.sendall(bytes([HELLO])); s.sendall(bytes([3])); s.sendall(struct.pack('>q', len(payload))); s.sendall(payload)
    n = struct.unpack('>q', recvn(s, 8))[0]
    resp = recvn(s, n)
    s.recv(1)
    s.sendall(bytes([OK]))
    return resp

def upload_once(port):
    data = os.urandom(4096)
    digest = hashlib.sha256(data).digest()
    meta = json.dumps({'cameraSerial': 'MOCK-000000', 'createdAt': int(time.time()), 'note': 'replay-probe'}).encode()
    s = connect(port=port)
    hello(s)
    for op in (SESSION, START):
        s.sendall(bytes([op])); recvn(s, 1)
    s.sendall(bytes([METADATA])); s.sendall(struct.pack('>q', len(meta))); s.sendall(meta); recvn(s, 1)
    s.sendall(bytes([FILE])); s.sendall(struct.pack('>q', len(data)))
    for i in range(0, len(data), 2800):
        s.sendall(data[i:i+2800])
    recvn(s, 1)
    s.sendall(bytes([HASH])); s.sendall(digest)
    hres = recvn(s, 1)[0]
    for op in (SAVE, COMPLETE, SESSION):
        s.sendall(bytes([op])); recvn(s, 1)
    s.close()
    return {'hash_match': bool(hres == OK), 'accepted': bool(hres == OK)}

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18081
    results = {'label': 'replay_rejection_probe', 'cases': [
        {'case': 'valid_upload_connection_1', 'result': upload_once(port)},
        {'case': 'valid_upload_connection_2', 'result': upload_once(port)},
    ]}
    print(json.dumps(results, indent=2))
