import json
from pathlib import Path
import queue
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from controller import Controller,InfrastructureError,drive,simulated_validation


class Host:
    def __init__(self):self.messages=queue.Queue();self.sent=[]
    def send(self,m):self.sent.append(m)


class ControllerTests(unittest.TestCase):
    def test_simulated_contract(self):self.assertEqual(simulated_validation()["status"],"PASS")
    def test_preserve_notifications_during_rpc(self):
        h=Host();c=Controller(h)
        notification={"method":"thread/tokenUsage/updated","params":{}}
        h.messages.put(notification);h.messages.put({"id":10001,"result":{"ok":True}})
        self.assertEqual(c.rpc("test",{}),{"ok":True})
        self.assertEqual(c.next(),notification)
    def test_wrong_terminal_identity(self):
        c=Controller(Host());c.bind({"thread":{"id":"t"}},{"turn":{"id":"v"}})
        with self.assertRaises(InfrastructureError):c.observe({"method":"turn/completed","params":{"turn":{"id":"other","status":"completed"}}})
    def test_completed_callback_and_duplicate(self):
        h=Host();c=Controller(h);c.bind({"thread":{"id":"t"}},{"turn":{"id":"v"}})
        for i in (1,2):h.messages.put({"id":i,"method":"item/tool/call","params":{"tool":"study","callId":"one","arguments":{"action":"read","arguments":"{}"}}})
        h.messages.put({"method":"turn/completed","params":{"turn":{"id":"v","status":"completed"}}})
        class WB:
            calls=0
            def dispatch(self,*args):self.calls+=1;return {"ok":True}
        wb=WB();r={};drive(c,wb,{"wall_observation_seconds":10,"interrupt_grace_seconds":1,"tool_callback_limit":10,"token_observation_threshold":100},r)
        self.assertEqual(wb.calls,1);self.assertIsNone(r["usage"])
        self.assertFalse(r["usage_complete"]);self.assertEqual(r["terminal_status"],"completed")
        self.assertIn("DUPLICATE_CALL",json.dumps(h.sent))


if __name__=="__main__":unittest.main()
