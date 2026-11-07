from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "deploy.yml"
RELEASE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


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
        uses = [
            line.strip().split("#", 1)[0].removeprefix("uses:").strip()
            for line in self.workflow.splitlines()
            if line.strip().startswith("uses:")
        ]
        self.assertEqual(
            uses,
            ["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"],
        )
        for reference in uses:
            self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")
        self.assertNotIn("Azure/setup-kubectl@", self.workflow)
        self.assertNotIn("Azure/setup-helm@", self.workflow)

    def test_release_signer_workflow_actions_are_pinned_to_verified_full_shas(self):
        release_workflow = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")
        references = re.findall(
            r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)",
            release_workflow,
        )
        self.assertEqual(
            [
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
                "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9",
                "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
                "actions/attest-build-provenance@977bb373ede98d70efdf65b84cb5f73e068dcc2a",
            ],
            references,
        )
        for reference in references:
            self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", release_workflow)

    def test_dispatch_inputs_are_validated_before_credentials(self):
        self.assertIn('[[ "$IMAGE_TAG" =~ ^[0-9a-f]{40}$ ]] ||', self.workflow)
        self.assertIn(
            r'[[ "$KUBECTL_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||',
            self.workflow,
        )
        self.assertEqual(self.workflow.count("${{ inputs.image_tag }}"), 1)
        self.assertIn('git merge-base --is-ancestor "$IMAGE_TAG" FETCH_HEAD', self.workflow)
        self.assertNotIn('--set-string image.tag="$IMAGE_TAG"', self.workflow)
        self.assertIn('--set-string image.digest="$IMAGE_DIGEST"', self.workflow)

    def test_operator_input_is_a_lookup_tag_not_deployment_identity(self):
        self.assertIn("deployment uses the verified digest", self.workflow)
        self.assertNotIn("used as the immutable image tag", self.workflow)

    def test_attestation_is_bound_to_release_workflow_and_source_commit(self):
        self.assertIn('--signer-workflow "$GITHUB_REPOSITORY/.github/workflows/release.yml"', self.workflow)
        self.assertIn('--source-digest "$IMAGE_TAG"', self.workflow)
        self.assertIn("--deny-self-hosted-runners", self.workflow)
        self.assertIn('docker buildx imagetools inspect "$tagged_image" --format', self.workflow)
        self.assertIn('gh attestation verify "oci://${immutable_image}"', self.workflow)
        self.assertIn("--format json", self.workflow)
        self.assertIn(".name == $subject and .digest.sha256 == $digest", self.workflow)

    def test_attested_manifest_digest_is_the_deployed_image_reference(self):
        self.assertIn('IMAGE_DIGEST: ${{ steps.image.outputs.image_digest }}', self.workflow)
        self.assertIn('[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]', self.workflow)
        self.assertIn('--set-string image.digest="$IMAGE_DIGEST"', self.workflow)
        self.assertIn('--set-string image.tag=""', self.workflow)
        self.assertNotIn('--set-string image.tag="$IMAGE_TAG"', self.workflow)

        template = (ROOT / "deploy" / "helm" / "zomega" / "templates" / "deployment.yaml").read_text(encoding="utf-8")
        digest_image = 'image: "{{ .Values.image.repository }}{{ if .Values.image.digest }}@{{ .Values.image.digest }}{{ else }}:{{ .Values.image.tag }}{{ end }}"'
        self.assertEqual(template.count(digest_image), 2)

    def test_digest_resolution_and_verification_precede_kubeconfig_loading(self):
        self.assertLess(
            self.workflow.index("Resolve immutable image digest and verify provenance"),
            self.workflow.index("Configure kubeconfig"),
        )
    def test_production_cluster_identity_precedes_mutation(self):
        self.assertIn("EXPECTED_CONTEXT: ${{ vars.ZOMEGA_K8S_EXPECTED_CONTEXT }}", self.workflow)
        self.assertIn(
            "EXPECTED_CLUSTER_SERVER: ${{ vars.ZOMEGA_K8S_EXPECTED_CLUSTER_SERVER }}",
            self.workflow,
        )
        self.assertIn('[[ "$actual_context" == "$EXPECTED_CONTEXT" ]] ||', self.workflow)
        self.assertIn('[[ "$actual_server" == "$EXPECTED_CLUSTER_SERVER" ]] ||', self.workflow)
        self.assertLess(
            self.workflow.index("Verify production cluster identity before mutation"),
            self.workflow.index("Sync production runtime secret"),
        )
        self.assertLess(
            self.workflow.index("Verify production cluster identity before mutation"),
            self.workflow.index("Deploy atomically"),
        )

    def test_kubectl_version_skew_is_bounded(self):
        self.assertIn("abs(client_minor - server_minor) > 1", self.workflow)
        self.assertIn('"kubectl", "version", "--client", "-o", "json"', self.workflow)
        self.assertIn("KUBECTL_VERSION: ${{ inputs.kubectl_version }}", self.workflow)
        self.assertIn("dl.k8s.io/release/${KUBECTL_VERSION}", self.workflow)

    def test_kubectl_and_helm_binaries_are_checksum_verified(self):
        self.assertIn("https://dl.k8s.io/release/${KUBECTL_VERSION}", self.workflow)
        self.assertIn("kubectl.sha256", self.workflow)
        self.assertIn("sha256sum --check --status", self.workflow)
        self.assertIn("https://get.helm.sh/${helm_archive}", self.workflow)
        self.assertIn(
            "0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b",
            self.workflow,
        )
        self.assertIn('helm_version="v4.3.1"', self.workflow)
        self.assertNotIn("Azure/setup-kubectl@", self.workflow)
        self.assertNotIn("Azure/setup-helm@", self.workflow)

    def test_toolchain_installation_precedes_production_credentials(self):
        self.assertLess(
            self.workflow.index("Install checksum-verified kubectl and Helm"),
            self.workflow.index("Configure kubeconfig"),
        )

    def test_every_external_workflow_action_is_pinned_to_a_full_commit_sha(self):
        workflow_dir = ROOT / ".github" / "workflows"
        workflow_paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
        self.assertTrue(workflow_paths, "No GitHub Actions workflow files found")

        references = []
        for workflow_path in workflow_paths:
            workflow_text = workflow_path.read_text(encoding="utf-8")
            references.extend(
                (workflow_path.relative_to(ROOT), reference)
                for reference in re.findall(
                    r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)",
                    workflow_text,
                )
            )

        self.assertTrue(references, "No external action references found")
        for workflow_path, reference in references:
            with self.subTest(workflow=str(workflow_path), reference=reference):
                self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")

    def test_security_scanner_and_sbom_actions_are_pinned(self):
        security_workflow = (
            ROOT / ".github" / "workflows" / "security.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25",
            security_workflow,
        )
        self.assertIn(
            "anchore/sbom-action@66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c",
            security_workflow,
        )

    def test_runtime_secrets_are_not_passed_as_command_line_values(self):
        self.assertNotIn("--from-literal=", self.workflow)
        self.assertIn('--from-env-file="$secret_file"', self.workflow)
        self.assertIn('chmod 600 "$secret_file"', self.workflow)
        self.assertIn("trap 'rm -f -- \"$secret_file\"' EXIT", self.workflow)
        self.assertIn("Clean up deployment credentials", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
