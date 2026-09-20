import socket
import struct
import threading

import pytest

from tools.sandbox import upload_server


def test_read_len_rejects_non_positive_and_oversized():
    for n in (0, -1, (1 << 20) + 1, (1 << 63) - 1):
        left, right = socket.socketpair()
        right.sendall(struct.pack(">q", n))
        right.close()
        with pytest.raises(ValueError):
            upload_server.read_len(left)
        left.close()


def test_unknown_opcode_fails_closed():
    left, right = socket.socketpair()
    args = type('Args', (), {'chunk': 2800})()
    thread = threading.Thread(
        target=upload_server.handle,
        args=(left, ("127.0.0.1", 0), args),
        daemon=True,
    )
    thread.start()
    right.sendall(b"\xc8")
    assert right.recv(1) == b"\x00"
    thread.join(1)
    right.close()
    left.close()


def test_invalid_file_length_fails_closed():
    left, right = socket.socketpair()
    args = type('Args', (), {'chunk': 2800})()
    thread = threading.Thread(
        target=upload_server.handle,
        args=(left, ("127.0.0.1", 0), args),
        daemon=True,
    )
    thread.start()
    right.sendall(b"\x06" + struct.pack(">q", 0))
    assert right.recv(1) == b"\x00"
    thread.join(1)
    right.close()
    left.close()
