"""Loopback deterministic Responses fixture. NO model, network proxy or auth.

Responses are host-authored test events, not model-generated code. The real
AppServer consumes them through its ordinary model-tool/approval dispatch path.
No API credential is read and no upstream provider request is made.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


class SyntheticProvider:
    def __init__(self):
        self.actions = []
        self.requests = []
        self.errors = []
        self.lock = threading.Lock()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                try:
                    assert self.path in ("/v1/responses", "/responses"), self.path
                    size = int(self.headers.get("Content-Length", 0))
                    assert 0 < size <= 2 * 1024**2
                    data = json.loads(self.rfile.read(size))
                    with owner.lock:
                        assert owner.actions, "Unscheduled synthetic request"
                        action = owner.actions.pop(0)
                        owner.requests.append(data)
                        number = len(owner.requests)
                    if action is None:
                        output = [{"id": "msg_p31_" + str(number), "type": "message", "role": "assistant",
                                   "content": [{"type": "output_text", "text": "Synthetic fixture turn complete."}]}]
                    else:
                        name, args = action
                        output = [{"id": "fc_p31_" + str(number), "type": "custom_tool_call",
                                   "call_id": "p31-call-" + str(number), "name": "exec", "namespace": "functions",
                                   "input": args if name == "__script__" else
                                       "text(await tools." + name + "(" + json.dumps(args) + "));"}]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    response = {"id": "resp_p31_" + str(number), "object": "response", "status": "in_progress", "output": []}
                    events = [{"type": "response.created", "response": response}]
                    for i, item in enumerate(output):
                        events += [{"type": "response.output_item.added", "output_index": i, "item": item},
                                   {"type": "response.output_item.done", "output_index": i, "item": item}]
                    events += [{"type": "response.completed", "response": dict(response, status="completed", output=output,
                        usage={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11,
                               "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}})}]
                    for e in events:
                        self.wfile.write(("data: " + json.dumps(e) + "\n\n").encode())
                    self.wfile.flush()
                except Exception as exc:
                    owner.errors.append(type(exc).__name__ + ":" + str(exc))
                    self.send_error(500)
            def do_GET(self):
                self.send_error(404)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return "http://127.0.0.1:" + str(self.server.server_port) + "/v1"

    def schedule(self, name, arguments):
        with self.lock:
            assert not self.actions
            self.actions = [(name, arguments), None]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
