# E3 container image: build and freeze the digest

This workspace has NO Docker daemon, so the digest cannot be produced here.
Run the commands below on a Docker-capable host (e.g., the machine that ran
the original 176-run experiments, or any host with Docker + network).

## 1. Build from the frozen source (commit 7c03ca0 / 338b584 Rust tree)

```powershell
git -C <alva-core> checkout exp3/migrate-signature-feasibility
cd <alva-core>
docker build -t alva-e3:final -f tests/e3/runner/container/E3.Dockerfile .
```

## 2. Push to a registry (RECOMMENDED; freezes the OCI manifest digest)

```powershell
docker tag alva-e3:final ghcr.io/zkidp/alva-e3:e3-final
docker push ghcr.io/zkidp/alva-e3:e3-final
docker pull ghcr.io/zkidp/alva-e3:e3-final
docker image inspect ghcr.io/zkidp/alva-e3:e3-final --format '{{json .RepoDigests}}'
```

Paste back the `ghcr.io/zkidp/alva-e3@sha256:...` value (the `@sha256:...`
digest, NOT the `:e3-final` tag).

## 3. Fallback if you do not push a registry

```powershell
docker image inspect alva-e3:final --format '{{.Id}}'
```

This is the local image ID / config digest, not the OCI manifest digest.
It is acceptable only if you will NOT push the image; the freeze must then
state that the image is local-only.

## 4. Freeze

Fill `tests/e3/runner/EXECUTION-FREEZE.json`:

```json
"container_digest": "sha256:<paste the 64-hex digest>"
```

Commit that as the FINAL freeze-record commit, recompute the final prereg
hash, and set FINAL-PREREGISTRATION-FREEZE.md to FROZEN.

## Run-time network contract (relay-only)

The container must be run with a relay-only network where ONLY the model
API host (or the host-side relay) is reachable:

```powershell
docker run --rm -i --network e3-relay-only -v <workspace>:/workspace \
  alva-e3:final
```

The host-side runner enforces the remaining 8-assertion gate items
(host secrets not readable, repository not mounted, relay reachable,
non-relay blocked, workspace writable, root/tool dirs read-only).
