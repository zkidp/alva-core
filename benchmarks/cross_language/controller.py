"""New prospective controller. The existing AppServer supplies transport only."""
from __future__ import annotations
from collections import deque
import json
import queue
import time


class InfrastructureError(RuntimeError):pass


class Controller:
    def __init__(self,host):
        self.host=host
        self.ordinal=10000
        self.deferred=deque()
        self.thread_id=self.turn_id=None
        self.interrupt_id=None
        self.interrupt_ack=False
        self.rpc_error=None
    def rpc(self,method,params,timeout=30):
        self.ordinal+=1
        ident=self.ordinal
        self.host.send({"id":ident,"method":method,"params":params})
        deadline=time.monotonic()+timeout
        while True:
            msg=self.host.messages.get(timeout=max(.01,deadline-time.monotonic()))
            if msg is None:raise InfrastructureError("Host exited during "+method)
            if msg.get("id")==ident:
                if "error" in msg:raise InfrastructureError(method+": "+json.dumps(msg["error"]))
                return msg["result"]
            self.deferred.append(msg)
    def bind(self,thread,turn):
        self.thread_id=thread["thread"]["id"]
        self.turn_id=turn["turn"]["id"]
        if not self.thread_id or not self.turn_id:raise InfrastructureError("Missing actual thread/turn IDs")
    def interrupt(self):
        if self.interrupt_id is not None:return
        if not self.thread_id or not self.turn_id:raise InfrastructureError("Cannot interrupt unbound turn")
        self.ordinal+=1
        self.interrupt_id=self.ordinal
        self.host.send({"id":self.interrupt_id,"method":"turn/interrupt",
                        "params":{"threadId":self.thread_id,"turnId":self.turn_id}})
    def observe(self,msg):
        if self.interrupt_id is not None and msg.get("id")==self.interrupt_id:
            if "error" in msg:
                self.rpc_error=msg["error"]
                raise InfrastructureError("Interrupt RPC failed: "+json.dumps(self.rpc_error))
            if msg.get("result")!={}:raise InfrastructureError("Unrecognized interrupt acknowledgment")
            self.interrupt_ack=True
        if msg.get("method")=="turn/completed":
            turn=msg["params"]["turn"]
            if turn["id"]!=self.turn_id:raise InfrastructureError("Wrong terminal turn identity")
            return turn["status"]
        return None
    def next(self,timeout=1):
        return self.deferred.popleft() if self.deferred else self.host.messages.get(timeout=timeout)


def drive(controller,workbench,config,result):
    deadline=time.monotonic()+config["wall_observation_seconds"]
    interruption=None
    seen=set()
    result.update(tool_calls=0,withheld_calls=0,tools=[],usage=None,terminal_status=None,
                  usage_complete=False,interrupt_requested=False,interrupt_ack=False,
                  unauthorized_items=[],model_reroutes=[])
    start=time.monotonic()
    while True:
        now=time.monotonic()
        if interruption is None and now>=deadline:
            interruption=now
            result["stop_reason"]="WALL_OBSERVATION_LIMIT"
            controller.interrupt()
        if interruption is not None and now-interruption>=config["interrupt_grace_seconds"]:
            result["stop_reason"]+="_TERMINATION_UNCONFIRMED"
            break
        try:msg=controller.next(.5)
        except queue.Empty:continue
        if msg is None:raise InfrastructureError("Host exited without terminal notification")
        terminal=controller.observe(msg)
        if terminal:
            result["terminal_status"]=terminal
            result["usage_complete"]=result["usage"] is not None
            result.setdefault("stop_reason","NATURAL_"+terminal.upper())
            break
        method=msg.get("method")
        if method=="thread/tokenUsage/updated":
            usage=msg["params"]["tokenUsage"]
            result["usage"]=usage
            total=usage.get("total",{}).get("totalTokens")
            if not isinstance(total,int):raise InfrastructureError("Unknown usage schema; not zero")
            if total>=config["token_observation_threshold"] and interruption is None:
                interruption=time.monotonic()
                result["stop_reason"]="TOKEN_OBSERVATION_LIMIT"
                controller.interrupt()
        elif method=="model/rerouted":
            result["model_reroutes"].append(msg["params"])
            raise InfrastructureError("Model rerouted: frozen identity not maintained")
        elif method=="item/started":
            item=msg["params"]["item"]
            if item["type"] in ("commandExecution","fileChange","mcpToolCall","collabToolCall","webSearch"):
                result["unauthorized_items"].append(item["type"])
                if interruption is None:
                    interruption=time.monotonic()
                    result["stop_reason"]="UNAUTHORIZED_TOOL"
                    controller.interrupt()
        elif method=="item/tool/call":
            p=msg["params"]
            call_id=p["callId"]
            result["tool_calls"]+=1
            if call_id in seen:
                answer={"error":"DUPLICATE_CALL_NOT_EXECUTED"}
            elif interruption is not None or result["tool_calls"]>config["tool_callback_limit"]:
                answer={"error":"TOOL_LIMIT_OR_INTERRUPTION_NO_DISPATCH"}
                result["withheld_calls"]+=1
            else:
                seen.add(call_id)
                try:
                    args=p["arguments"]
                    if not isinstance(args,dict) or p["tool"]!="study":raise ValueError("Unknown tool/argument envelope")
                    action=args["action"]
                    detail=json.loads(args["arguments"])
                except (ValueError,KeyError,TypeError) as exc:
                    answer={"error":"INVALID_TOOL_ARGUMENTS","message":str(exc)}
                else:
                    answer=workbench.dispatch(action,detail)
                    result["tools"].append({"call_id":call_id,"action":action,"arguments":detail,
                                            "response":answer,"observed_usage_before":result["usage"]})
            controller.host.send({"id":msg["id"],"result":{"success":True,"contentItems":[{"type":"inputText","text":json.dumps(answer,ensure_ascii=False)}]}})
            if result["tool_calls"]>=config["tool_callback_limit"] and interruption is None:
                interruption=time.monotonic()
                result["stop_reason"]="TOOL_LIMIT"
                controller.interrupt()
        elif "id" in msg and "method" in msg:
            raise InfrastructureError("Unexpected server request: "+str(method))
    result.update(elapsed_seconds=round(time.monotonic()-start,3),interrupt_requested=controller.interrupt_id is not None,
                  interrupt_ack=controller.interrupt_ack,thread_id=controller.thread_id,turn_id=controller.turn_id)
    if controller.interrupt_id is not None and not controller.interrupt_ack:
        raise InfrastructureError("Interrupt not acknowledged")


def simulated_validation():
    class Fake:
        def __init__(self):self.messages=queue.Queue();self.sent=[]
        def send(self,m):self.sent.append(m)
    h=Fake();c=Controller(h)
    c.bind({"thread":{"id":"actual-thread"}},{"turn":{"id":"actual-turn"}})
    c.interrupt();c.interrupt()
    assert len(h.sent)==1 and h.sent[0]["params"]=={"threadId":"actual-thread","turnId":"actual-turn"}
    c.observe({"id":c.interrupt_id,"result":{}})
    assert c.interrupt_ack
    assert c.observe({"method":"turn/completed","params":{"turn":{"id":"actual-turn","status":"interrupted"}}})=="interrupted"
    bad=Controller(Fake());bad.bind({"thread":{"id":"t"}},{"turn":{"id":"v"}});bad.interrupt()
    try:bad.observe({"id":bad.interrupt_id,"error":{"code":-32600,"message":"synthetic invalid request"}})
    except InfrastructureError:pass
    else:raise AssertionError("RPC errors ignored")
    # Missing terminal/usage stays incomplete, never defaulted to zero/PASS.
    class WB:
        def dispatch(self,*a):raise AssertionError("withheld action dispatched")
    missing=Controller(Fake());missing.bind({"thread":{"id":"t"}},{"turn":{"id":"v"}})
    missing.host.messages.put({"id":10001,"result":{}})
    row={};drive(missing,WB(),{"wall_observation_seconds":0,"interrupt_grace_seconds":.01,"tool_callback_limit":1,"token_observation_threshold":1},row)
    assert row["terminal_status"] is None and row["usage"] is None and not row["usage_complete"]
    return {"status":"PASS","thread_turn_identity":True,"rpc_errors_fail_closed":True,
            "terminal_confirmation":True,"missing_usage_is_null":True,"model_generation_calls":0}
