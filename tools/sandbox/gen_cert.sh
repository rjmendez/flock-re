#!/usr/bin/env bash
# Self-signed cert+key for the mock upload server (sandbox TLS). The device does no
# cert pinning, so any cert works. Output: server.pem (cert+key concatenated).
set -e
out="${1:-server.pem}"
openssl req -x509 -newkey rsa:2048 -keyout key.tmp -out cert.tmp -days 365 -nodes \
  -subj "/CN=localhost" >/dev/null 2>&1
cat cert.tmp key.tmp > "$out"
rm -f cert.tmp key.tmp
echo "wrote $out"
