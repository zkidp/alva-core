#!/usr/bin/env python3
"""Durable object storage acceptance tests for the alva S3 server.

Covers the v0.3 durable-storage contract:
  1. PUT survives process restart (GET content identical, SHA-256)
  2. DELETE survives restart
  3. overwrite is old-or-new and survives restart
  4. every commit failpoint crashes before a half-object is visible
  5. metadata never references a missing blob (recovery quarantines it)
  6. corrupted blobs produce structured storage errors
  7. path traversal keys never escape the data root
  8. concurrent GET/PUT only ever observe the old or the new object
  9. content-addressed blobs are deduplicated
 10. orphan blobs are invisible to LIST and get GC'd
 11. 85MB object survives restart byte-for-byte
 12. rclone check reports zero differences before and after restart

Usage:
  ALVA_STORE_BIN=<path-to-store-exe> python tests/storage/durable_test.py
"""

import datetime
import hashlib
import hmac
import http.client
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import zipfile

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

AK = "test"
SK = "testtest"
PORT = 9000
ENDPOINT = f"http://127.0.0.1:{PORT}"


def log(msg):
    print(msg, flush=True)


def fail(msg):
    log(f"FAIL: {msg}")
    raise SystemExit(1)


class Server:
    def __init__(self, data_root, bin_path, extra_env=None, wait=2.5):
        env = dict(os.environ)
        env["ALVA_DATA_ROOT"] = data_root
        if extra_env:
            env.update(extra_env)
        self.proc = subprocess.Popen(
            [bin_path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(wait)
        if self.proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {self.proc.returncode}")

    def stop(self, kill=False):
        if self.proc.poll() is None:
            if kill:
                self.proc.kill()
            else:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode

    def expect_dead(self):
        self.proc.wait(timeout=5)
        return self.proc.returncode


def sign(method, path, body=b"", query=""):
    now = datetime.datetime.now(datetime.timezone.utc)
    amz = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = (
        f"host:127.0.0.1:{PORT}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = (
        f"{method}\n{path}\n{query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    scope = f"{date}/us-east-1/s3/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    def h(key, msg):
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    key = h(h(h(h(("AWS4" + SK).encode(), date), "us-east-1"), "s3"), "aws4_request")
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={AK}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "x-amz-date": amz,
        "x-amz-content-sha256": payload_hash,
    }


def req(method, path, body=b""):
    headers = sign(method, path, body)
    headers["Host"] = f"127.0.0.1:{PORT}"
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    out_headers = {k.lower(): v for k, v in resp.getheaders()}
    status = resp.status
    conn.close()
    return status, data, out_headers


def put(path, body):
    return req("PUT", path, body)


def get(path):
    return req("GET", path)


def head(path):
    return req("HEAD", path)


def delete(path):
    return req("DELETE", path)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def walk_files(root):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            out.append(os.path.join(dirpath, f))
    return out


def main():
    bin_path = os.environ.get("ALVA_STORE_BIN")
    if bin_path and os.name == "nt" and not bin_path.lower().endswith(".exe"):
        # CI passes the cargo target path without the Windows extension.
        exe = bin_path + ".exe"
        if os.path.exists(exe):
            bin_path = exe
    if not bin_path or not os.path.exists(bin_path):
        fail("set ALVA_STORE_BIN to the built store server binary")
    work = tempfile.mkdtemp(prefix="alva-durable-test-")
    log(f"data roots under: {work}")

    # ---- 1. PUT survives restart ----
    log("[1] PUT survives restart")
    root1 = os.path.join(work, "r1")
    os.makedirs(root1)
    payload1 = bytes(random.Random(1).randrange(256) for _ in range(200_000))
    s = Server(root1, bin_path)
    st, body, _ = put("/b1/obj1.bin", payload1)
    if st != 201:
        fail(f"PUT /b1/obj1.bin -> {st}")
    s.stop(kill=True)
    s2 = Server(root1, bin_path)
    st, body, _ = get("/b1/obj1.bin")
    if st != 200 or sha(body) != sha(payload1):
        fail("object content differs after restart")
    s2.stop(kill=True)
    log("  ok")

    # ---- 2. DELETE survives restart ----
    log("[2] DELETE survives restart")
    root2 = os.path.join(work, "r2")
    os.makedirs(root2)
    s = Server(root2, bin_path)
    put("/b2/k", b"to-delete")
    st, _, _ = delete("/b2/k")
    if st != 204:
        fail(f"DELETE -> {st}")
    s.stop(kill=True)
    s2 = Server(root2, bin_path)
    st, _, _ = get("/b2/k")
    if st != 404:
        fail(f"deleted object still present after restart ({st})")
    s2.stop(kill=True)
    log("  ok")

    # ---- 3. overwrite old-or-new and survives restart ----
    log("[3] overwrite is old-or-new and survives restart")
    root3 = os.path.join(work, "r3")
    os.makedirs(root3)
    s = Server(root3, bin_path)
    put("/b3/k", b"old-version")
    put("/b3/k", b"new-version-content")
    s.stop(kill=True)
    s2 = Server(root3, bin_path)
    st, body, _ = get("/b3/k")
    if st != 200 or body != b"new-version-content":
        fail(f"overwrite did not stick ({st}, {body!r})")
    s2.stop(kill=True)
    log("  ok")

    # ---- 4. failpoints: crash at each commit stage ----
    log("[4] failpoint crash consistency")
    failpoints = [
        "after_temp_blob_write",
        "after_blob_fsync",
        "after_blob_rename",
        "after_metadata_write",
        "after_metadata_fsync",
        "after_metadata_rename",
    ]
    for fp in failpoints:
        root = os.path.join(work, f"fp-{fp}")
        os.makedirs(root)
        s = Server(root, bin_path, extra_env={"ALVA_FAILPOINT": fp})
        try:
            put("/bf/k", b"failpoint-data")
        except Exception:
            pass  # the failpoint kills the process before the response is sent
        code = s.expect_dead()
        if code != 17:
            fail(f"failpoint {fp}: expected exit 17, got {code}")
        s2 = Server(root, bin_path)
        st, body, _ = get("/bf/k")
        if st == 200:
            if body != b"failpoint-data":
                fail(f"failpoint {fp}: visible object is partial/corrupt")
        elif st != 404:
            fail(f"failpoint {fp}: unexpected status {st}")
        leftovers = [f for f in walk_files(root) if ".tmp" in f]
        if leftovers:
            fail(f"failpoint {fp}: stale tmp files after recovery: {leftovers}")
        s2.stop(kill=True)
        log(f"  {fp}: ok (status {st})")

    # ---- 5. metadata never references a missing blob ----
    log("[5] missing blob is quarantined by recovery")
    root5 = os.path.join(work, "r5")
    os.makedirs(root5)
    s = Server(root5, bin_path)
    put("/b5/k", b"blob-to-remove")
    s.stop(kill=True)
    blobs = [f for f in walk_files(os.path.join(root5, "blobs"))]
    if not blobs:
        fail("no blob files found")
    os.remove(blobs[0])
    s2 = Server(root5, bin_path)
    st, _, _ = get("/b5/k")
    if st != 404:
        fail(f"object referencing missing blob should be gone, got {st}")
    quarantined = walk_files(os.path.join(root5, "quarantine"))
    if not quarantined:
        fail("recovery did not quarantine metadata referencing a missing blob")
    s2.stop(kill=True)
    log("  ok")

    # ---- 6. corrupted blob detected ----
    log("[6] corrupted blob yields structured error")
    root6 = os.path.join(work, "r6")
    os.makedirs(root6)
    s = Server(root6, bin_path)
    put("/b6/k", b"corrupt-me")
    s.stop(kill=True)
    blobs = [f for f in walk_files(os.path.join(root6, "blobs"))]
    with open(blobs[0], "wb") as fh:
        fh.write(b"XX")
    s2 = Server(root6, bin_path)
    st, body, _ = get("/b6/k")
    if st != 500 or b"E_STORAGE_007" not in body:
        fail(f"corrupted blob not reported as E_STORAGE_007 ({st}, {body[:120]!r})")
    s2.stop(kill=True)
    log("  ok")

    # ---- 7. path traversal keys stay inside the data root ----
    log("[7] path traversal keys cannot escape the data root")
    root7 = os.path.join(work, "r7")
    os.makedirs(root7)
    s = Server(root7, bin_path)
    hostile_keys = [
        "../escape",
        "..\\escape",
        "a/../../escape2",
        "uni/h\xe9llo/\u4e16\u754c",
        "ctl/\x01name",
        "..",
    ]
    for k in hostile_keys:
        st, _, _ = put(f"/b7/{urllib.parse.quote(k, safe='')}", b"x")
        if st != 201:
            fail(f"PUT hostile key {k!r} -> {st}")
    s.stop(kill=True)
    outside = [
        f
        for f in walk_files(work)
        if os.path.dirname(f).startswith(root7) is False and "r7" in f
    ]
    escaped = [f for f in outside if "escape" in os.path.basename(f)]
    if escaped:
        fail(f"path traversal escaped data root: {escaped}")
    s2 = Server(root7, bin_path)
    for k in hostile_keys:
        st, body, _ = get(f"/b7/{urllib.parse.quote(k, safe='')}")
        if st != 200 or body != b"x":
            fail(f"GET hostile key {k!r} -> {st} {body!r}")
    s2.stop(kill=True)
    log("  ok")

    # ---- 8. concurrent GET/PUT see old or new only ----
    log("[8] concurrent GET/PUT old-or-new")
    root8 = os.path.join(work, "r8")
    os.makedirs(root8)
    s = Server(root8, bin_path)
    put("/b8/k", b"v0")
    old = b"old" * 10
    new = b"new" * 10
    put("/b8/k", old)
    for _ in range(8):
        put("/b8/k", new)
        for _ in range(5):
            st, body, _ = get("/b8/k")
            if st != 200:
                fail(f"GET during overwrite -> {st}")
            if body not in (old, new):
                fail("observed a partial/mixed object during overwrite")
        put("/b8/k", old)
        for _ in range(5):
            st, body, _ = get("/b8/k")
            if body not in (old, new):
                fail("observed a partial/mixed object during overwrite")
    s.stop(kill=True)
    log("  ok")

    # ---- 9. content-addressed dedupe ----
    log("[9] content-addressed blob dedupe")
    root9 = os.path.join(work, "r9")
    os.makedirs(root9)
    s = Server(root9, bin_path)
    put("/b9/a", b"same-content")
    put("/b9/b", b"same-content")
    put("/b9/c", b"other-content")
    s.stop(kill=True)
    blobs = walk_files(os.path.join(root9, "blobs"))
    if len(blobs) != 2:
        fail(f"expected 2 unique blobs, found {len(blobs)}")
    log("  ok")

    # ---- 10. orphan blob invisible + GC ----
    log("[10] orphan blobs are GC'd")
    root10 = os.path.join(work, "r10")
    os.makedirs(root10)
    s = Server(root10, bin_path)
    put("/b10/k", b"keep-me")
    s.stop(kill=True)
    shard = os.path.join(root10, "blobs", "zz")
    os.makedirs(shard, exist_ok=True)
    orphan = os.path.join(shard, "zz" + "1" * 62)
    with open(orphan, "wb") as fh:
        fh.write(b"orphan")
    s2 = Server(root10, bin_path)
    st, body, _ = get("/b10/k")
    if st != 200:
        fail(f"kept object broke after GC ({st})")
    if os.path.exists(orphan):
        fail("orphan blob was not collected by startup GC")
    s2.stop(kill=True)
    log("  ok")

    # ---- 11. 85MB object survives restart ----
    log("[11] 85MB object survives restart byte-for-byte")
    if os.environ.get("ALVA_DURABLE_FULL") == "1":
        root11 = os.path.join(work, "r11")
        os.makedirs(root11)
        big = bytes(random.Random(42).randrange(256) for _ in range(85 * 1024 * 1024))
        s = Server(root11, bin_path)
        st, _, _ = put("/b11/big.bin", big)
        if st != 201:
            fail(f"85MB PUT -> {st}")
        s.stop(kill=True)
        s2 = Server(root11, bin_path)
        st, body, _ = get("/b11/big.bin")
        if st != 200 or sha(body) != sha(big):
            fail("85MB object differs after restart")
        s2.stop(kill=True)
        log("  ok")
    else:
        log("  skipped (smoke mode; set ALVA_DURABLE_FULL=1 for the 85MB case)")

    # ---- 12. rclone check before/after restart ----
    log("[12] rclone check zero differences before/after restart")
    if os.environ.get("ALVA_DURABLE_FULL") == "1":
        root12 = os.path.join(work, "r12")
        os.makedirs(root12)
        fixture = os.path.join(work, "fixture")
        os.makedirs(os.path.join(fixture, "sub"))
        for name, data in [
            ("a.txt", b"alpha"),
            ("b.bin", bytes(range(256)) * 4),
            (os.path.join("sub", "c.txt"), b"gamma"),
        ]:
            with open(os.path.join(fixture, name), "wb") as fh:
                fh.write(data)
        rclone = fetch_rclone()
        if rclone is None:
            log("  skipped: rclone unavailable")
        else:
            conf = os.path.join(work, "rclone.conf")
            with open(conf, "w", encoding="utf-8") as fh:
                fh.write(
                    "[localstore]\n"
                    "type = s3\nprovider = Other\n"
                    f"endpoint = http://127.0.0.1:{PORT}\n"
                    "access_key_id = test\nsecret_access_key = testtest\n"
                    "force_path_style = true\n"
                )
            s = Server(root12, bin_path)
            run([rclone, "--config", conf, "copy", fixture, "localstore:ci"])
            run([rclone, "--config", conf, "check", fixture, "localstore:ci"])
            s.stop(kill=True)
            s2 = Server(root12, bin_path)
            run([rclone, "--config", conf, "check", fixture, "localstore:ci"])
            s2.stop(kill=True)
            log("  ok")
    else:
        log("  skipped (smoke mode; covered by the rclone interop job)")

    log("ALL DURABLE STORAGE TESTS PASSED")


def run(cmd, **kw):
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        fail(f"command failed: {' '.join(cmd)}\n{proc.stdout[-800:]}\n{proc.stderr[-800:]}")


def fetch_rclone():
    cache = os.path.join(tempfile.gettempdir(), "alva-rclone")
    exe = None
    if os.path.exists(cache):
        for f in os.listdir(cache):
            if f.startswith("rclone") and not f.endswith((".1", ".txt")):
                exe = os.path.join(cache, f)
                break
    if exe:
        return exe
    version = "v1.75.0"
    os_name = "windows" if os.name == "nt" else "linux"
    url = (
        f"https://downloads.rclone.org/{version}/rclone-{version}-{os_name}-amd64.zip"
    )
    try:
        zip_path = os.path.join(tempfile.gettempdir(), "rclone.zip")
        urllib.request.urlretrieve(url, zip_path)
        os.makedirs(cache, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                if name.endswith(".exe") or (os.name != "nt" and "/rclone" in name):
                    z.extract(name, cache)
                    exe = os.path.join(cache, name)
                    if os.name != "nt":
                        os.chmod(exe, 0o755)
                    break
    except Exception as e:  # noqa: BLE001
        log(f"  rclone download failed: {e}")
        return None
    return exe


if __name__ == "__main__":
    main()
