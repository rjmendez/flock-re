#!/usr/bin/env python3
"""Adversarial-JSON fuzzer for the Flock capture-upload mock's HELLO/METADATA frames.

Extends upload_client.py's --fuzz idea with JSON-shape adversarial cases aimed at the
HELLO (auth token) and METADATA payloads specifically:
  - duplicate JSON keys (e.g. "token" appearing twice with different values)
  - the auth-token field typed as null / bool / array / object / number instead of a string
  - deeply nested arrays (1000+ levels of "[[[...]]]") inside an otherwise small payload,
    aimed at a recursive-descent JSON parser's call-stack depth
  - a raw NUL byte embedded inside a JSON string field
  - invalid UTF-8 byte sequences embedded inside a JSON string field

Each case is sent as the length-prefixed HELLO payload (and, where noted, replayed as a
METADATA payload after a benign HELLO) against a LOCAL mock upload_server.py instance.
After every case the script does a fresh, benign HELLO round-trip as a liveness/health
check to see whether the server process is still accepting and correctly handling
connections (i.e. whether the malformed frame corrupted server state even if that one
connection didn't blow up).

SANDBOX ONLY. Connect only to your own local mock (see tools/sandbox/upload_server.py).
"""
import argparse, json, socket, ssl, struct, sys, time

OK, HELLO, PROTO, SESSION, START, FILE, HASH, SAVE, COMPLETE, METADATA = 1, 2, 3, 4, 5, 6, 7, 8, 9, 12


def connect(host, port, tls, timeout=5):
    s = socket.create_connection((host, port), timeout=timeout)
    if tls:
        ctx = ssl._create_unverified_context()
        s = ctx.wrap_socket(s, server_hostname=host)
    s.settimeout(timeout)
    return s


def be_long(n):
    return struct.pack(">q", n)


def recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return b


def raw_hello(s, payload_bytes, expect_reply=True):
    """Send a HELLO frame with an attacker-controlled raw payload (bytes, not JSON-encoded
    for us -- the caller builds the exact bytes on the wire, including any deliberately
    malformed JSON/UTF-8)."""
    s.sendall(bytes([HELLO]))
    s.sendall(bytes([3]))  # protocol version marker, as the real client sends
    s.sendall(be_long(len(payload_bytes)))
    s.sendall(payload_bytes)
    if not expect_reply:
        return None
    n = struct.unpack(">q", recvn(s, 8))[0]
    resp = recvn(s, n)
    s.sendall(bytes([OK]))
    return resp.decode("utf-8", "replace")


def raw_metadata(s, payload_bytes):
    s.sendall(bytes([METADATA]))
    s.sendall(be_long(len(payload_bytes)))
    s.sendall(payload_bytes)
    ack = recvn(s, 1)
    return ack


def health_check(host, port, tls, token=b"HEALTHCHECK-TOKEN"):
    """Fresh connection, benign HELLO. Returns (ok: bool, detail: str)."""
    try:
        s = connect(host, port, tls, timeout=4)
        payload = json.dumps({"authToken": token.decode(), "serial": "MOCK-000000",
                               "clientVersion": "healthcheck"}).encode()
        resp = raw_hello(s, payload)
        s.close()
        ok = resp is not None and "ok" in resp
        return ok, resp
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def build_cases():
    cases = []

    def c(name, payload, via="hello"):
        cases.append({"name": name, "payload": payload, "via": via})

    # 1. Duplicate keys -- last-value-wins is the common (but not universal) JSON
    #    behavior; the interesting question is whether the *validated* token is the
    #    first or second occurrence, or whether the parser rejects/crashes outright.
    c("dup-key-token-good-then-bad",
      b'{"authToken":"SANDBOX-GOOD","authToken":"SANDBOX-BAD","serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("dup-key-token-bad-then-good",
      b'{"authToken":"SANDBOX-BAD","authToken":"SANDBOX-GOOD","serial":"MOCK-000000","clientVersion":"sandbox"}')

    # 2. Token typed as non-string JSON values.
    c("token-null", b'{"authToken":null,"serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("token-bool-true", b'{"authToken":true,"serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("token-array", b'{"authToken":["a","b","c"],"serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("token-object", b'{"authToken":{"nested":{"deeper":1}},"serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("token-number", b'{"authToken":123456789012345,"serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("token-missing", b'{"serial":"MOCK-000000","clientVersion":"sandbox"}')

    # 3. Deeply nested arrays (1000+ levels), small overall length, aimed at a
    #    recursive-descent parser's call stack. Nested as the value of a field so the
    #    frame is still a well-formed top-level JSON object.
    depth = 2000
    nested_value = (b"[" * depth) + (b"]" * depth)
    c(f"deep-nested-array-{depth}-hello",
      b'{"authToken":"SANDBOX-FAKE-TOKEN","serial":"MOCK-000000","clientVersion":' + nested_value + b'}')
    c(f"deep-nested-array-{depth}-metadata",
      b'{"cameraSerial":"MOCK-000000","createdAt":1,"detections":' + nested_value + b'}',
      via="metadata")
    # Also a *bare* deeply nested array as the whole payload (no object wrapper at all).
    c(f"deep-nested-array-{depth}-bare", nested_value)

    # 4. Raw NUL byte embedded inside a JSON string field (invalid per strict JSON, but
    #    a classic C-string-truncation probe: does anything downstream treat this as
    #    end-of-string?).
    c("embedded-nul-in-token",
      b'{"authToken":"SANDBOX-FAKE\x00-TRUNCATED-TAIL","serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("embedded-nul-in-serial",
      b'{"authToken":"SANDBOX-FAKE-TOKEN","serial":"MOCK\x00-000000","clientVersion":"sandbox"}')

    # 5. Invalid UTF-8 byte sequences embedded inside a JSON string field.
    c("invalid-utf8-lone-continuation",
      b'{"authToken":"SANDBOX-\xff\xfe-FAKE","serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("invalid-utf8-overlong-and-surrogate",
      b'{"authToken":"SANDBOX-\xed\xa0\x80-FAKE","serial":"MOCK-000000","clientVersion":"sandbox"}')
    c("invalid-utf8-truncated-multibyte",
      b'{"authToken":"SANDBOX-FAKE-\xe2\x82","serial":"MOCK-000000","clientVersion":"sandbox"}')

    return cases


def run_case(host, port, tls, case, timeout):
    result = {"name": case["name"], "via": case["via"], "payload_len": len(case["payload"])}
    t0 = time.time()
    try:
        s = connect(host, port, tls, timeout=timeout)
        if case["via"] == "hello":
            resp = raw_hello(s, case["payload"])
            result["server_reply"] = resp
        elif case["via"] == "metadata":
            # Need a valid HELLO first so the server proceeds to accept METADATA.
            hello_payload = json.dumps({"authToken": "SANDBOX-FAKE-TOKEN", "serial": "MOCK-000000",
                                         "clientVersion": "sandbox"}).encode()
            raw_hello(s, hello_payload)
            ack = raw_metadata(s, case["payload"])
            result["server_reply"] = f"ack_byte={ack!r}"
        s.close()
        result["outcome"] = "responded"
    except socket.timeout:
        result["outcome"] = "TIMEOUT (possible hang)"
    except Exception as e:
        result["outcome"] = f"EXCEPTION {type(e).__name__}: {e}"
    result["elapsed_s"] = round(time.time() - t0, 3)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--plaintext", action="store_true")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--json-out", default=None, help="write full results as JSON to this path")
    a = ap.parse_args()
    tls = not a.plaintext

    ok, detail = health_check(a.host, a.port, tls)
    print(f"[baseline health check] ok={ok} detail={detail!r}")
    if not ok:
        print("!! server did not respond to a benign HELLO before fuzzing even started -- aborting")
        sys.exit(2)

    all_results = []
    for case in build_cases():
        res = run_case(a.host, a.port, tls, case, a.timeout)
        hc_ok, hc_detail = health_check(a.host, a.port, tls)
        res["post_health_check_ok"] = hc_ok
        res["post_health_check_detail"] = hc_detail
        all_results.append(res)
        flag = "OK " if hc_ok else "!!!"
        print(f"[{flag}] {case['name']:38} via={case['via']:8} len={res['payload_len']:6} "
              f"-> {res['outcome']:40} ({res['elapsed_s']}s)  post-health={hc_ok}")

    n_bad = sum(1 for r in all_results if not r["post_health_check_ok"])
    n_hang = sum(1 for r in all_results if "TIMEOUT" in r["outcome"])
    n_exc = sum(1 for r in all_results if "EXCEPTION" in r["outcome"])
    print(f"\nSummary: {len(all_results)} cases, {n_hang} timeouts, {n_exc} client-side exceptions, "
          f"{n_bad} cases after which the server failed the health check.")

    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump({"host": a.host, "port": a.port, "tls": tls, "cases": all_results,
                       "summary": {"total": len(all_results), "timeouts": n_hang,
                                   "client_exceptions": n_exc, "post_case_health_failures": n_bad}},
                      f, indent=2)
        print(f"wrote {a.json_out}")


if __name__ == "__main__":
    main()
