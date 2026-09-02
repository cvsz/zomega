import unittest
from omega.catalog import load_skills, load_agents

class CatalogTest(unittest.TestCase):
    def test_exact_catalog(self):
        skills = load_skills()
        agents = load_agents()
        self.assertEqual(len(skills), 100)
        self.assertEqual(len(agents), 12)
        self.assertTrue(all(s["billing"]["reservation"] > 0 for s in skills.values()))
        self.assertTrue(all(s["prompt"].strip() for s in skills.values()))

if __name__ == "__main__":
    unittest.main()
