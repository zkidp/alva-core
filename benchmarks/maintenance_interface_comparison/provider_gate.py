"""Post-run provider fault classification and future fail-closed slot gate.

Added AFTER MIC-01 wave 01. It is not retroactively part of that frozen runtime.
"""


def provider_fault(record):
    for event in record.get("events", []):
        if event.get("method") == "turn/completed":
            turn = event.get("params", {}).get("turn", {})
            if turn.get("status") == "failed":
                error = turn.get("error") or {}
                return {"kind": "MODEL_SERVICE_OR_RUNTIME_FAILURE", "code": error.get("codexErrorInfo", "UNKNOWN_TERMINAL_FAILURE"),
                        "terminal_confirmed": True}
    if record.get("terminal_status") == "failed":
        return {"kind": "MODEL_SERVICE_OR_RUNTIME_FAILURE", "code": "UNKNOWN_TERMINAL_FAILURE", "terminal_confirmed": True}
    return None


def guarded_drive(original_drive):
    """Let the terminal/interrupt controller finish, then block any next launch.

    A failed model-service turn is not an ordinary wrong solution. Returning
    an infrastructure_hold lets the existing batch cleanup run and stop before
    the next slot, without interrupting an already terminal failed turn.
    """
    def drive(controller, slot, record):
        original_drive(controller, slot, record)
        fault = provider_fault(record)
        if fault:
            record["provider_fault"] = fault
            record["infrastructure_hold"] = "COMMON_PROVIDER_OR_RUNTIME_FAILURE:" + str(fault["code"])
    return drive
