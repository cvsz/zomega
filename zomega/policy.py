from fastapi import HTTPException

DESTRUCTIVE_TERMS = ("rm -rf", "drop database", "terraform destroy", "truncate table")

def enforce_skill_policy(skill: dict, tenant: dict, payload: dict):
    plans = skill.get("entitlement", {}).get("plans", [])
    if plans and tenant.get("plan") not in plans:
        raise HTTPException(403, "Plan is not entitled to this skill")

    raw = str(payload).lower()
    if not skill.get("permissions", {}).get("destructive", False):
        for term in DESTRUCTIVE_TERMS:
            if term in raw:
                raise HTTPException(403, "Destructive action blocked by policy")
