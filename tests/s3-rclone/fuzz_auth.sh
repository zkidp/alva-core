#!/usr/bin/env bash
# SigV4 健壮性 fuzz：畸形 Authorization 绝不能导致服务器 panic，
# 只能返回 400/403。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
URL="http://127.0.0.1:9000/"

echo "== building store server =="
"$ALVA" build "$ROOT/alva/examples/store_server.alva" --out-dir "$ROOT/out"

SERVER="$ROOT/out/store_server/target/debug/store_server"
[ -f "${SERVER}.exe" ] && SERVER="${SERVER}.exe"
"$SERVER" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 1

echo "== structured malformed auth headers =="
while IFS= read -r h; do
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: $h" "$URL")"
  if [ "$code" != "400" ] && [ "$code" != "403" ]; then
    echo "FAIL: header='$h' code=$code"
    exit 1
  fi
done <<'EOF'
AWS4-HMAC-SHA256 Credential=onlyone
AWS4-HMAC-SHA256 Credential=a/b, SignedHeaders=host
AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/s3/aws4_request
AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/s3/aws4_request, SignedHeaders=host, Signature=abc
Bearer token123
Basic dGVzdDp0ZXN0
EOF

echo "== 1000 random malformed auth headers =="
python3 - "$URL" <<'EOF'
import random
import string
import subprocess
import sys

url = sys.argv[1]
alphabet = string.ascii_letters + string.digits + "/=;,+ .:-_%"
ok = True
for _ in range(1000):
    n = random.randint(0, 80)
    h = "".join(random.choice(alphabet) for _ in range(n))
    code = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "-H", f"Authorization: {h}", url],
        capture_output=True, text=True,
    ).stdout
    if code not in ("400", "403"):
        print(f"FAIL: header={h!r} code={code}")
        ok = False
sys.exit(0 if ok else 1)
EOF

echo "== server must still be alive =="
kill -0 "$SERVER_PID"
echo "FUZZ PASSED"
