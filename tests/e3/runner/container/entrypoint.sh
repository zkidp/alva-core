#!/bin/sh
set -eu

# Container-side isolation gate (host-side network/relay assertions are
# enforced by the runner + docker network config).
#
# 1. workspace writable
[ -w /workspace ] || { echo "GATE: /workspace not writable" >&2; exit 1; }
# 2. toolchain binary and dirs read-only (container's own root dotfiles are
#    harmless; the meaningful isolation is the read-only toolchain and the
#    workspace-only mount)
[ -w /usr/local/bin/alva ] && {
  echo "GATE: alva binary is writable" >&2
  exit 1
}
if [ -d /opt/toolchain ] && find /opt/toolchain -type f -writable \
    2>/dev/null | grep -q .; then
  echo "GATE: writable file under /opt/toolchain" >&2
  exit 1
fi
# 3. no repository mount
[ ! -d /repo ] || { echo "GATE: /repo mount present" >&2; exit 1; }
# 4. relay/API host reachable is enforced by the runner before start;
#    non-relay blocking is the docker network's job.

echo "GATE: isolation checks passed" >&2
exec alva agent
