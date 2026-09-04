import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_BASELINE_FILES = (
    ".editorconfig",
    ".gitattributes",
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    ".gitignore",
    ".env.example",
    "ABOUT.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "IMPLEMENTATION-CHECKLIST.md",
    "LICENSE",
    "Dockerfile",
    "Makefile",
    "README.md",
    "ROADMAP.md",
    "SECURITY.md",
    "docs/adr/0000-template.md",
    "docs/architecture.md",
    "docs/development.md",
    "docs/release.md",
)


class RepositoryContractTest(unittest.TestCase):
    def test_shared_repository_baseline_is_present_and_named_for_zomega(self):
        for relative_path in TEMPLATE_BASELINE_FILES:
            self.assertTrue(
                (ROOT / relative_path).is_file(),
                f"missing repository baseline file: {relative_path}",
            )

        text_files = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                text_files.append(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                # Ignore generated databases and bytecode; tracked repository files
                # are checked by the explicit baseline assertions above.
                continue

        repository_text = "\n".join(text_files)
        legacy_repository_name = "z" + "template"
        self.assertNotIn(legacy_repository_name, repository_text.lower())
        self.assertIn("github.com/cvsz/zomega", repository_text)

    def test_host_entrypoints_use_python3_and_a_real_database_initializer(self):
        verify = (ROOT / "verify.sh").read_text(encoding="utf-8")
        upgrade = (ROOT / "upgrade.sh").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("python3 -m compileall", verify)
        self.assertIn("python3 -m zomega db-check", verify)
        self.assertIn("alembic upgrade head", upgrade)
        self.assertNotIn("zomega init", upgrade)
        self.assertIn("PYTHON ?= python3", makefile)


if __name__ == "__main__":
    unittest.main()
