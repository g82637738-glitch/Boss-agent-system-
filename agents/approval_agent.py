import time
import uuid

import state


def request_approval(action_summary: str, reason: str) -> str:
    uid = str(uuid.uuid4())
    state.pending_approval = {
        "id": uid,
        "action": action_summary,
        "reason": reason,
        "status": "waiting",
    }

    deadline = time.time() + 90
    while time.time() < deadline:
        status = state.pending_approval.get("status")
        if status in ("approved", "rejected"):
            result = "APPROVED" if status == "approved" else "REJECTED"
            state.pending_approval = {}
            return result
        time.sleep(2)

    state.pending_approval["status"] = "timeout"
    state.pending_approval = {}
    return "TIMEOUT: no response"


def send_notification(message: str) -> None:
    state.notifications.append(message)
    while len(state.notifications) > 10:
        state.notifications.pop(0)
