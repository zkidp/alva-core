"""Trusted, serialized same-session reads; never modify native tool replies.

Only calls bearing the AppServer callId are observed. Host authority re-reads
and prewarm discovery are not model operations. Observation failure is a common
infrastructure failure, not a missing body silently scored as unchanged.
"""

import hashlib
import threading
import time

MUTATIONS = frozenset((
    "construct_expression", "create_reference", "create_literal", "create_binary",
    "create_call", "create_if", "replace_expression", "change_field",
))


class ObservedNative:
    def __init__(self, inner, sink):
        self.inner, self.sink = inner, sink
        self.baselines = {}
        self.lock = threading.RLock()

    def request(self, method, params=None, **kwargs):
        with self.lock:
            params = params or {}
            answer = self.inner.request(method, params, **kwargs)
            if method != "tools/call" or not params.get("_meta", {}).get("callId"):
                return answer
            op, args = params["name"], params.get("arguments", {})
            call_id = params["_meta"]["callId"]
            tx = args.get("transaction_id")
            good = not answer.get("isError")
            if op == "begin_transaction" and good:
                tx = answer["structuredContent"]["transaction_id"]
                self.capture(tx, call_id, op, baseline=True)
            elif op in MUTATIONS and good and tx:
                if tx not in self.baselines:
                    raise RuntimeError("OBSERVER_MISSING_TRANSACTION_BASELINE")
                self.capture(tx, call_id, op)
            elif op in ("abort_transaction", "commit_transaction") and good:
                self.baselines.pop(tx, None)
            return answer  # no additional model-visible fields/text

    def capture(self, tx, call_id, operation, baseline=False):
        started = time.monotonic_ns()
        params = {"name": "inspect_body", "arguments": {
            "transaction_id": tx, "function": "bench.solve"}}
        answer = self.inner.request("tools/call", params)
        if answer.get("isError") or not isinstance(answer.get("structuredContent", {}).get("body"), str):
            raise RuntimeError("OBSERVER_BODY_UNAVAILABLE")
        body = answer["structuredContent"]["body"]
        digest = hashlib.sha256(body.encode()).hexdigest()
        if baseline:
            self.baselines[tx] = digest
        self.sink({"call_id": call_id, "transaction_id": tx, "after_operation": operation,
                   "baseline": baseline, "body_sha256": digest,
                   "baseline_body_sha256": self.baselines[tx],
                   "changed_from_transaction_start": digest != self.baselines[tx],
                   "observer_calls": 1, "observer_request": params,
                   "observer_response": answer, "finished_ns": time.monotonic_ns(),
                   "elapsed_ns": time.monotonic_ns() - started})

    def tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def notify(self, *args, **kwargs):
        return self.inner.notify(*args, **kwargs)

    def close(self):
        return self.inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.inner.__exit__(*args)
