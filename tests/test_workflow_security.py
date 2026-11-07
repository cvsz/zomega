from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from scripts.check_workflow_security import scan_workflows

class WorkflowSecurityTests(unittest.TestCase):
    def scan(self, workflow: str, filename: str = "test.yml") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / filename).write_text(workflow, encoding="utf-8")
            return scan_workflows(root)

    def test_read_only_pull_request_checkout_is_allowed(self):
        self.assertEqual(self.scan("""name: CI
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
"""), [])

    def test_pull_request_secrets_are_rejected(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    steps:
      - run: echo ${{ secrets.PRIVATE_TOKEN }}
""")
        self.assertTrue(any("must not reference secrets" in item for item in findings))

    def test_top_level_and_job_level_write_permissions_are_rejected(self):
        top_level = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: write
jobs:
  test:
    steps:
      - run: echo test
""")
        job_level = self.scan("""name: Unsafe
on:
  pull_request:
jobs:
  test:
    permissions:
      pull-requests: write
    steps:
      - run: echo test
""")
        self.assertTrue(any("unsafe write permission" in item for item in top_level))
        self.assertTrue(any("unsafe write permission" in item for item in job_level))

    def test_codeql_security_events_write_is_allowed(self):
        findings = self.scan("""name: CodeQL
on:
  pull_request:
permissions:
  contents: read
  security-events: write
jobs:
  analyze:
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
""", filename="codeql.yml")
        self.assertEqual(findings, [])

    def test_security_events_write_is_rejected_outside_security_workflows(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: read
  security-events: write
jobs:
  test:
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
""")
        self.assertTrue(any("unsafe write permission" in item for item in findings))

    def test_pull_request_target_is_rejected(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request_target:
jobs:
  test:
    steps:
      - run: echo test
""")
        self.assertTrue(any("pull_request_target is forbidden" in item for item in findings))

    def test_secret_and_untrusted_ref_combination_is_rejected(self):
        findings = self.scan("""name: Unsafe
on:
  workflow_dispatch:
jobs:
  review:
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.inputs.sha }}
      - run: ./scripts/from-the-pr.sh
        env:
          GH_TOKEN: ${{ secrets.REVIEWER_PAT }}
""")
        self.assertTrue(any("secrets combined" in item for item in findings))

    def test_secretless_pr_ref_is_allowed(self):
        findings = self.scan("""name: Read-only scan
on:
  workflow_dispatch:
jobs:
  inspect:
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.inputs.pr_number && format('refs/pull/{0}/merge', github.event.inputs.pr_number) }}
          persist-credentials: false
      - run: git status --short
""")
        self.assertEqual(findings, [])

if __name__ == "__main__":
    unittest.main()
