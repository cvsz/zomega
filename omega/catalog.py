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
