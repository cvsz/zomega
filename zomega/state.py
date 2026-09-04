VALID = {
    "PENDING": {"PENDING_DISPATCH", "CANCELLED"},
    "PENDING_DISPATCH": {"QUEUED", "CANCELLED", "FAIL"},
    "QUEUED": {"RUNNING", "CANCELLED", "FAIL"},
    "RUNNING": {"PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCEL_REQUESTED"},
    "CANCEL_REQUESTED": {"CANCELLED", "FAIL", "BLOCKED"},
    "PASS": set(),
    "PARTIAL": set(),
    "FAIL": set(),
    "BLOCKED": set(),
    "CANCELLED": set(),
}

TERMINAL = {"PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCELLED"}

def validate_transition(old: str, new: str):
    if new not in VALID.get(old, set()):
        raise ValueError(f"invalid state transition: {old} -> {new}")

def is_terminal(status: str) -> bool:
    return status in TERMINAL
