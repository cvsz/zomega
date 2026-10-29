from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "deploy.yml"


class DeployWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_deployment_is_manual_and_main_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotRegex(self.workflow, r"(?m)^\s+(?:push|pull_request):")
        self.assertIn("if: github.ref == 'refs/heads/main'", self.workflow)
        self.assertIn("environment: production", self.workflow)

    def test_all_actions_are_pinned_to_full_commit_shas(self):
        uses = re.findall(r"(?m)^\s+- uses:\s+([^\s#]+)", self.workflow)
        self.assertEqual(len(uses), 3)
        for reference in uses:
            self.assertRegex(
                reference,
                r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$",
            )
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", uses
        )
        self.assertIn(
            "Azure/setup-kubectl@829323503d1be3d00ca8346e5391ca0b07a9ab0d", uses
        )
        self.assertIn(
            "Azure/setup-helm@9bc31f4ebc9c6b171d7bfbaa5d006ae7abdb4310", uses
        )

    def test_dispatch_inputs_are_validated_before_credentials(self):
        self.assertIn('[[ "$IMAGE_TAG" =~ ^[0-9a-f]{40}$ ]] ||', self.workflow)
        self.assertIn(
            r'[[ "$KUBECTL_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||',
            self.workflow,
        )
        self.assertEqual(self.workflow.count("${{ inputs.image_tag }}"), 1)
        self.assertIn('git merge-base --is-ancestor "$IMAGE_TAG" FETCH_HEAD', self.workflow)
        self.assertNotIn("--set image.tag=${{ inputs.image_tag }}", self.workflow)
        self.assertIn('--set-string image.tag="$IMAGE_TAG"', self.workflow)

    def test_attestation_is_bound_to_release_workflow_and_source_commit(self):
        self.assertIn('--signer-workflow "$GITHUB_REPOSITORY/.github/workflows/release.yml"', self.workflow)
        self.assertIn('--source-digest "$IMAGE_TAG"', self.workflow)
        self.assertIn("--deny-self-hosted-runners", self.workflow)
        self.assertIn('gh attestation verify "oci://$image"', self.workflow)

    def test_kubectl_version_skew_is_bounded(self):
        self.assertIn("abs(client_minor - server_minor) > 1", self.workflow)
        self.assertIn("kubectl version --client -o json", self.workflow)
        self.assertIn("version: ${{ inputs.kubectl_version }}", self.workflow)

    def test_runtime_secrets_are_not_passed_as_command_line_values(self):
        self.assertNotIn("--from-literal=", self.workflow)
        self.assertIn('--from-env-file="$secret_file"', self.workflow)
        self.assertIn('chmod 600 "$secret_file"', self.workflow)
        self.assertIn("trap 'rm -f -- \"$secret_file\"' EXIT", self.workflow)
        self.assertIn("Clean up deployment credentials", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
