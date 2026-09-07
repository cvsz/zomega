import unittest

from zomega.catalog import load_agents, load_skills, resolve_agent_skills


class AgentSkillAccessTest(unittest.TestCase):
    def test_every_agent_resolves_every_enabled_skill(self):
        skills = load_skills()
        agents = load_agents()
        expected = {
            skill_id
            for skill_id, skill in skills.items()
            if bool(skill.get("enabled", True))
        }

        self.assertEqual(len(agents), 12)
        self.assertTrue(expected)

        for agent in agents.values():
            self.assertEqual(agent.get("skills"), ["*"])
            self.assertEqual(set(resolve_agent_skills(agent, skills)), expected)
            self.assertTrue(set(agent.get("default_workflow", [])).issubset(expected))


if __name__ == "__main__":
    unittest.main()
