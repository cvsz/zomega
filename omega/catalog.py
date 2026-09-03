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
    return {
        "id": agent["id"],
        "role": agent.get("role"),
        "version": agent.get("version"),
    }

def public_catalog() -> dict:
    return {
        "skills": [public_skill(s) for s in load_skills().values()],
        "agents": [public_agent(a) for a in load_agents().values()],
    }
