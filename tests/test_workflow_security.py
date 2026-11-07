from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.check_workflow_security import UniqueKeyLoader, scan_workflows


class WorkflowSecurityTests(unittest.TestCase):
    def scan(self, workflow: str, filename: str = "test.yml") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / filename).write_text(workflow, encoding="utf-8")
            return scan_workflows(root)

    @staticmethod
    def read_only_checkout() -> str:
        return """name: CI
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
"""

    def test_read_only_pull_request_checkout_is_allowed(self):
        self.assertEqual(self.scan(self.read_only_checkout()), [])

    def test_pr_hygiene_workflow_is_read_only_and_never_executes_candidate_code(self):
        root = Path(__file__).resolve().parents[1]
        workflow_path = root / ".github" / "workflows" / "auto-fix-open-prs.yml"
        source = workflow_path.read_text(encoding="utf-8")
        document = yaml.load(source, Loader=UniqueKeyLoader)

        self.assertEqual(set(document["on"]), {"schedule", "workflow_dispatch"})
        self.assertEqual(document["permissions"], {"contents": "read"})
        for forbidden in (
            "POLIEDBC_PAT", "GPG_SIGNING_KEY", "GPG_PASSPHRASE",
            "secrets.", "git push", "git commit", "git add",
            "gh pr review", "gh api",
        ):
            self.assertNotIn(forbidden, source)

        checkout_count = 0
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if isinstance(uses, str) and uses.startswith("actions/checkout@"):
                    checkout_count += 1
                    self.assertEqual(step.get("with", {}).get("persist-credentials"), "false")
                self.assertFalse(str(step.get("run", "")).strip().startswith(("./", "python ", "bash ")))
        self.assertEqual(checkout_count, 1)

    def test_mutable_action_tag_is_rejected(self):
        workflow = self.read_only_checkout().replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
        )
        findings = self.scan(workflow)
        self.assertTrue(any("must use a full 40-character commit SHA" in item for item in findings))

    def test_full_commit_sha_action_ref_is_accepted(self):
        self.assertEqual(self.scan(self.read_only_checkout()), [])

    def test_mutable_reusable_workflow_ref_is_rejected(self):
        findings = self.scan("""name: Reuse
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  verify:
    uses: cvsz/ztemplate/.github/workflows/ci.yml@main
""")
        self.assertTrue(any("must use a full 40-character commit SHA" in item for item in findings))

    def test_docker_action_tag_is_rejected_without_digest(self):
        findings = self.scan("""name: Docker action
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  verify:
    steps:
      - uses: docker://ghcr.io/example/action:v1
""")
        self.assertTrue(any("must pin docker actions by sha256 digest" in item for item in findings))

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

    def test_explicit_top_level_permissions_are_required(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request:
jobs:
  test:
    steps:
      - run: echo test
""")
        self.assertTrue(
            any("requires explicit top-level permissions" in item for item in findings)
        )

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
permissions:
  contents: read
jobs:
  test:
    permissions:
      pull-requests: write
    steps:
      - run: echo test
""")
        self.assertTrue(any("grants contents: write" in item for item in top_level))
        self.assertTrue(any("grants pull-requests: write" in item for item in job_level))

    def test_codeql_security_events_write_is_allowed_only_in_named_workflow(self):
        allowed = self.scan("""name: CodeQL
on:
  pull_request:
permissions:
  contents: read
  security-events: write
jobs:
  analyze:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
""", filename="codeql.yml")
        rejected = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: read
  security-events: write
jobs:
  test:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
""")
        self.assertEqual(allowed, [])
        self.assertTrue(any("grants security-events: write" in item for item in rejected))

    def test_job_level_security_events_write_is_checked(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: read
jobs:
  analyze:
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
""")
        self.assertTrue(any("job 'analyze' permissions" in item for item in findings))

    def test_each_pull_request_checkout_must_disable_persisted_credentials(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
""")
        self.assertTrue(
            any("checkout in job 'test' step 2" in item for item in findings)
        )

    def test_pull_request_target_is_rejected(self):
        findings = self.scan("""name: Unsafe
on:
  pull_request_target:
permissions:
  contents: read
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
permissions:
  contents: read
jobs:
  review:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.inputs.sha }}
          persist-credentials: false
      - run: ./scripts/from-the-pr.sh
        env:
          GH_TOKEN: ${{ secrets.REVIEWER_PAT }}
""")
        self.assertTrue(any("secrets combined" in item for item in findings))

    def test_secretless_pr_ref_workflow_dispatch_is_allowed(self):
        workflow = """name: Read-only scan
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  inspect:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.inputs.pr_number && format('refs/pull/{0}/merge', github.event.inputs.pr_number) }}
          persist-credentials: false
      - run: git status --short
"""
        self.assertEqual(self.scan(workflow), [])

    def test_duplicate_yaml_keys_fail_closed(self):
        findings = self.scan("""name: Ambiguous
on:
  pull_request:
permissions:
  contents: read
permissions:
  contents: write
jobs:
  test:
    steps:
      - run: echo test
""")
        self.assertTrue(any("invalid or ambiguous YAML" in item for item in findings))

    def test_malformed_yaml_fails_closed(self):
        findings = self.scan("name: broken\non: [pull_request\n")
        self.assertTrue(any("invalid or ambiguous YAML" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
