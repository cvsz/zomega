from pathlib import Path
import yaml

BASE = Path(__file__).resolve().parent.parent
SKILLS_DIR = BASE / "skills"
AGENTS_DIR = BASE / "agents"

def load_skills():
    items = {}
    for p in sorted(SKILLS_DIR.glob("*/skill.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        items[data["id"]] = data
    return items

def load_agents():
    items = {}
    for p in sorted(AGENTS_DIR.glob("*/agent.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        items[data["id"]] = data
    return items

def resolve_agent_skills(agent: dict, skills: dict | None = None) -> list[str]:
    catalog = skills if skills is not None else load_skills()
    configured = list(agent.get("skills", []))
    if "*" in configured:
        return [
            skill_id
            for skill_id, skill in catalog.items()
            if bool(skill.get("enabled", True))
        ]
    return [
        skill_id
        for skill_id in configured
        if skill_id in catalog and bool(catalog[skill_id].get("enabled", True))
    ]

def public_skill(skill: dict) -> dict:
    billing = skill.get("billing", {})
    return {
        "id": skill["id"],
        "version": skill.get("version"),
        "agent": skill.get("agent"),
        "description": skill.get("description"),
        "enabled": bool(skill.get("enabled", True)),
        "billing": {
            "mode": billing.get("mode"),
            "base_price": billing.get("base_price"),
            "reservation": billing.get("reservation"),
        },
        "plans": list(skill.get("entitlement", {}).get("plans", [])),
    }

def public_agent(agent: dict) -> dict:
    skill_ids = resolve_agent_skills(agent)
    return {
        "id": agent["id"],
        "role": agent.get("role"),
        "version": agent.get("version"),
        "skills": skill_ids,
        "skill_count": len(skill_ids),
    }

def public_catalog() -> dict:
    return {
        "skills": [public_skill(s) for s in load_skills().values()],
        "agents": [public_agent(a) for a in load_agents().values()],
    }
