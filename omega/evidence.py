from .db import session_scope
from .models import Evidence

def record(run_id: str, event_type: str, payload: dict):
    with session_scope() as db:
        db.add(Evidence(run_id=run_id, event_type=event_type, payload_json=payload))
