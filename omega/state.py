VALID = {
    "PENDING": {"RUNNING", "CANCELLED"},
    "RUNNING": {"PASS", "FAIL", "BLOCKED", "CANCELLED"},
    "PASS": set(),
    "FAIL": set(),
    "BLOCKED": set(),
    "CANCELLED": set(),
}

def validate_transition(old: str, new: str):
    if new not in VALID.get(old, set()):
        raise ValueError(f"invalid state transition: {old} -> {new}")
