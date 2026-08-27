#!/bin/sh
set -eu

# Container-side isolation gate (host-side network/relay assertions are
# enforced by the runner + docker network config).
#
# 1. workspace writable
[ -w /workspace ] || { echo "GATE: /workspace not writable" >&2; exit 1; }
# 2. /opt/toolchain must be read-only IF present (mount-based check; plain
#    file-writability checks are meaningless as root)
if [ -d /opt/toolchain ]; then
  ro=$(mount | awk -v p=/opt/toolchain '$3==p && $4 ~ /(^|,)ro(,|$)/ {print 1}')
  [ "$ro" = "1" ] || { echo "GATE: /opt/toolchain not read-only" >&2; exit 1; }
fi
# 3. no repository mount
[ ! -d /repo ] || { echo "GATE: /repo mount present" >&2; exit 1; }
# 4. relay/API host reachable is enforced by the runner before start;
#    non-relay blocking is the docker network's job.

echo "GATE: isolation checks passed" >&2
exec alva agent
