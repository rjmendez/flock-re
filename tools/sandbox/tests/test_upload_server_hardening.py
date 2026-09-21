import socket
import struct
import threading

import pytest

from tools.sandbox import upload_server


def _make_handler_thread(left):
    """Helper to start the server handler in a thread."""
    args = type('Args', (), {'chunk': 2800})()
    thread = threading.Thread(
        target=upload_server.handle,
        args=(left, ("127.0.0.1", 0), args),
        daemon=True,
    )
    thread.start()
    return thread


def _valid_hello(conn):
    """Send a valid HELLO handshake to establish server state."""
    conn.sendall(b"\x02")  # HELLO opcode
    conn.sendall(b"\x03")  # protocol version
    payload = b'{"authToken":"SANDBOX-FAKE-TOKEN","serial":"MOCK-000000"}'
    conn.sendall(struct.pack(">q", len(payload)))
    conn.sendall(payload)
    n = struct.unpack(">q", conn.recv(8))[0]
    conn.recv(n)
    conn.sendall(b"\x01")  # OK ack


# ============================================================================
# read_len() direct unit tests
# ============================================================================

def test_read_len_rejects_non_positive_and_oversized():
    """Ensure read_len() rejects all invalid length values."""
    for n in (0, -1, (1 << 20) + 1, (1 << 63) - 1):
        left, right = socket.socketpair()
        right.sendall(struct.pack(">q", n))
        right.close()
        with pytest.raises(ValueError):
            upload_server.read_len(left)
        left.close()


# ============================================================================
# HELLO opcode boundary tests
# ============================================================================

@pytest.mark.parametrize("length_val", [
    0,
    -1,
    -(2**63),  # INT64_MIN
    -(2**40),
])
def test_hello_negative_or_zero_length_fails_closed(length_val):
    """
    HELLO with non-positive length must reject and send FAIL byte.
    No success-shaped fallback (e.g., OK byte) should occur.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    right.sendall(b"\x02")  # HELLO opcode
    right.sendall(b"\x03")  # protocol version
    right.sendall(struct.pack(">q", length_val))  # crafted invalid length
    # send some bytes anyway so the connection doesn't look truncated
    body = b'{"authToken":"SANDBOX-FAKE-TOKEN"}'
    right.sendall(body)

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for HELLO len={length_val}, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_hello_oversized_length_fails_closed():
    """
    HELLO with length > 1MB must reject and send FAIL byte.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    right.sendall(b"\x02")  # HELLO opcode
    right.sendall(b"\x03")  # protocol version
    right.sendall(struct.pack(">q", (1 << 20) + 1))  # 1MB + 1 byte
    right.sendall(b'x' * 100)  # send some junk

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for oversized HELLO, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_hello_min_valid_length_succeeds():
    """
    HELLO with length=1 (minimum valid) must succeed and accept.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    right.sendall(b"\x02")  # HELLO opcode
    right.sendall(b"\x03")  # protocol version
    right.sendall(struct.pack(">q", 1))  # length=1
    right.sendall(b"x")  # 1 byte payload

    # server should respond with length + response
    n = struct.unpack(">q", right.recv(8))[0]
    response = right.recv(n)
    assert len(response) > 0, "Server should send response for valid HELLO"

    # send OK ack
    right.sendall(b"\x01")
    thread.join(1)
    right.close()
    left.close()


def test_hello_max_valid_length_succeeds():
    """
    HELLO with length=MAX_FRAME_BYTES (1MB exactly) must succeed.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    right.sendall(b"\x02")  # HELLO opcode
    right.sendall(b"\x03")  # protocol version
    max_len = 1 << 20  # 1MB
    right.sendall(struct.pack(">q", max_len))
    right.sendall(b"x" * max_len)

    # server should respond with length + response
    n = struct.unpack(">q", right.recv(8))[0]
    response = right.recv(n)
    assert len(response) > 0, "Server should send response for max-valid HELLO"

    right.sendall(b"\x01")
    thread.join(1)
    right.close()
    left.close()


# ============================================================================
# METADATA opcode boundary tests
# ============================================================================

@pytest.mark.parametrize("length_val", [
    0,
    -1,
    -(2**63),  # INT64_MIN
    -(2**40),
])
def test_metadata_negative_or_zero_length_fails_closed(length_val):
    """
    METADATA with non-positive length must reject and send FAIL byte.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # METADATA with invalid length
    right.sendall(b"\x0c")  # METADATA opcode
    right.sendall(struct.pack(">q", length_val))
    body = b'{"probe":"test"}'
    right.sendall(body)

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for METADATA len={length_val}, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_metadata_oversized_length_fails_closed():
    """
    METADATA with length > 1MB must reject and send FAIL byte.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # METADATA with oversized length
    right.sendall(b"\x0c")  # METADATA opcode
    right.sendall(struct.pack(">q", (1 << 20) + 1))
    right.sendall(b'x' * 100)

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for oversized METADATA, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_metadata_min_valid_length_succeeds():
    """
    METADATA with length=1 must succeed and send OK.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # METADATA with min valid length
    right.sendall(b"\x0c")  # METADATA opcode
    right.sendall(struct.pack(">q", 1))
    right.sendall(b"x")

    response = right.recv(1)
    assert response == b"\x01", f"Expected OK (0x01) for min-valid METADATA, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_metadata_max_valid_length_succeeds():
    """
    METADATA with length=MAX_FRAME_BYTES must succeed.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # METADATA with max valid length
    right.sendall(b"\x0c")  # METADATA opcode
    max_len = 1 << 20  # 1MB
    right.sendall(struct.pack(">q", max_len))
    right.sendall(b"x" * max_len)

    response = right.recv(1)
    assert response == b"\x01", f"Expected OK (0x01) for max-valid METADATA, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


# ============================================================================
# FILE opcode boundary tests
# ============================================================================

@pytest.mark.parametrize("length_val", [
    0,
    -1,
    -(2**63),  # INT64_MIN
    -(2**40),
])
def test_file_negative_or_zero_length_fails_closed(length_val):
    """
    FILE with non-positive length must reject and send FAIL byte.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # FILE with invalid length
    right.sendall(b"\x06")  # FILE opcode
    right.sendall(struct.pack(">q", length_val))
    right.sendall(b"\x00" * 32)

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for FILE len={length_val}, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_file_oversized_length_fails_closed():
    """
    FILE with length > 1MB must reject and send FAIL byte.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # FILE with oversized length
    right.sendall(b"\x06")  # FILE opcode
    right.sendall(struct.pack(">q", (1 << 20) + 1))
    right.sendall(b"\x00" * 100)

    response = right.recv(1)
    assert response == b"\x00", f"Expected FAIL (0x00) for oversized FILE, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_file_min_valid_length_succeeds():
    """
    FILE with length=1 must succeed and send OK.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # FILE with min valid length
    right.sendall(b"\x06")  # FILE opcode
    right.sendall(struct.pack(">q", 1))
    right.sendall(b"x")

    response = right.recv(1)
    assert response == b"\x01", f"Expected OK (0x01) for min-valid FILE, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


def test_file_max_valid_length_succeeds():
    """
    FILE with length=MAX_FRAME_BYTES must succeed.
    """
    left, right = socket.socketpair()
    thread = _make_handler_thread(left)

    # Setup: valid HELLO
    _valid_hello(right)

    # FILE with max valid length
    right.sendall(b"\x06")  # FILE opcode
    max_len = 1 << 20  # 1MB
    right.sendall(struct.pack(">q", max_len))
    right.sendall(b"\x00" * max_len)

    response = right.recv(1)
    assert response == b"\x01", f"Expected OK (0x01) for max-valid FILE, got {response.hex()}"

    thread.join(1)
    right.close()
    left.close()


# ============================================================================
# Robustness tests: server remains responsive after boundary violations
# ============================================================================

def test_server_remains_responsive_after_hello_boundary_violation():
    """
    After a boundary violation on HELLO, server should close that connection
    but remain responsive to new connections.
    """
    # First connection: invalid HELLO
    left1, right1 = socket.socketpair()
    thread1 = _make_handler_thread(left1)
    right1.sendall(b"\x02" + b"\x03" + struct.pack(">q", 0))
    right1.recv(1)
    right1.close()
    thread1.join(1)
    left1.close()

    # Second connection: valid HELLO should work
    left2, right2 = socket.socketpair()
    thread2 = _make_handler_thread(left2)
    _valid_hello(right2)
    # if we got here without exception, server is still working
    right2.close()
    thread2.join(1)
    left2.close()


def test_unknown_opcode_fails_closed():
    """
    Unknown opcodes must fail closed (send FAIL, not OK).
    """
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
    """
    FILE opcode with invalid length (e.g., 0) must fail closed.
    """
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
