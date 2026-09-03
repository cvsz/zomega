import unittest
from omega.catalog import load_skills, load_agents, public_catalog

class CatalogTest(unittest.TestCase):
    def test_exact_catalog(self):
        skills = load_skills()
        agents = load_agents()
        self.assertEqual(len(skills), 100)
        self.assertEqual(len(agents), 12)
        self.assertTrue(all(s["billing"]["reservation"] > 0 for s in skills.values()))
        self.assertTrue(all(s["prompt"].strip() for s in skills.values()))

    def test_public_catalog_never_exposes_internal_prompts(self):
        catalog = public_catalog()
        self.assertEqual(len(catalog["skills"]), 100)
        for skill in catalog["skills"]:
            self.assertNotIn("prompt", skill)
            self.assertNotIn("permissions", skill)
            self.assertNotIn("validation", skill)

if __name__ == "__main__":
    unittest.main()
