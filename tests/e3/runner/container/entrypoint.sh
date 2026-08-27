#!/bin/sh
set -eu

# Container-side isolation gate (host-side network/relay assertions are
# enforced by the runner + docker network config).
#
# 1. workspace writable
[ -w /workspace ] || { echo "GATE: /workspace not writable" >&2; exit 1; }
# 2. toolchain dirs read-only (nothing writable under /opt/toolchain, /root)
if find /opt/toolchain /root -type f -writable 2>/dev/null | grep -q .; then
  echo "GATE: writable file under /opt/toolchain or /root" >&2
  exit 1
fi
# 3. no repository mount
[ ! -d /repo ] || { echo "GATE: /repo mount present" >&2; exit 1; }
# 4. relay/API host reachable is enforced by the runner before start;
#    non-relay blocking is the docker network's job.

echo "GATE: isolation checks passed" >&2
exec alva agent
