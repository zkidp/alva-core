#!/usr/bin/env bash
# Reproducible rclone interop test for the durable alva S3 server.
# Requires: alva toolchain built, network access to download rclone.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
RCLONE_VERSION="v1.75.0"
WORK="$(mktemp -d)"
DATA_ROOT="$WORK/store-data"
trap 'pkill -f "store-data" 2>/dev/null || true' EXIT

echo "== building durable store server =="
"$ALVA" project build "$ROOT/examples/store_split/alva.toml" --out-dir "$WORK/out" >/dev/null
SERVER="$WORK/out/store/target/debug/store"
[ -f "${SERVER}.exe" ] && SERVER="${SERVER}.exe"

echo "== starting server (data root $DATA_ROOT) =="
ALVA_DATA_ROOT="$DATA_ROOT" "$SERVER" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 2

echo "== downloading rclone $RCLONE_VERSION =="
OS_NAME="$(uname -s)"
case "$OS_NAME" in
  Linux*) RCLONE_OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) RCLONE_OS="windows" ;;
  *) echo "unsupported OS: $OS_NAME"; exit 1 ;;
esac
curl -fsSLo "$WORK/rclone.zip" "https://downloads.rclone.org/${RCLONE_VERSION}/rclone-${RCLONE_VERSION}-${RCLONE_OS}-amd64.zip"
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$WORK/rclone.zip" "$WORK/rclone-alva"
RCLONE="$(find "$WORK/rclone-alva" -type f -name 'rclone*' ! -name '*.1' ! -name '*.txt' | head -n 1)"
chmod +x "$RCLONE" 2>/dev/null || true

echo "== rclone copy =="
"$RCLONE" --config "$ROOT/tests/s3-rclone/rclone.conf" \
  copy "$ROOT/tests/s3-rclone/fixtures" localstore:ci

echo "== rclone check before restart (expect 0 differences) =="
OUT="$("$RCLONE" --config "$ROOT/tests/s3-rclone/rclone.conf" \
  check "$ROOT/tests/s3-rclone/fixtures" localstore:ci 2>&1)"
echo "$OUT"
echo "$OUT" | grep -qi "0 differences"

echo "== restarting server =="
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true
ALVA_DATA_ROOT="$DATA_ROOT" "$SERVER" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 2

echo "== rclone check after restart (expect 0 differences) =="
OUT="$("$RCLONE" --config "$ROOT/tests/s3-rclone/rclone.conf" \
  check "$ROOT/tests/s3-rclone/fixtures" localstore:ci 2>&1)"
echo "$OUT"
echo "$OUT" | grep -qi "0 differences"

echo "== rclone interop OK (persistent store) =="
