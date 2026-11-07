"""Build-time policy contract for operating-system security updates."""
from pathlib import Path
import re
import unittest


BASE_IMAGE = "python:3.12.15-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


class DockerfileSecurityContract(unittest.TestCase):
    def test_base_image_is_version_and_digest_pinned(self):
        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
        match = re.search(r"(?m)^FROM\s+(\S+)\s*$", dockerfile)

        self.assertIsNotNone(match, "Dockerfile must declare a base image")
        self.assertEqual(match.group(1), BASE_IMAGE)
        self.assertRegex(match.group(1), r"^python:3\.12\.15-slim@sha256:[0-9a-f]{64}$")

    def test_os_package_manifest_is_captured_before_runtime_user(self):
        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")

        update_index = dockerfile.index("apt-get update")
        upgrade_index = dockerfile.index("apt-get upgrade -y --no-install-recommends")
        manifest_index = dockerfile.index("/usr/share/zomega/os-packages.tsv")
        cleanup_index = dockerfile.index("rm -rf /var/lib/apt/lists/*")
        user_index = dockerfile.index("USER zomega")

        self.assertLess(update_index, upgrade_index)
        self.assertLess(upgrade_index, manifest_index)
        self.assertLess(manifest_index, cleanup_index)
        self.assertLess(cleanup_index, user_index)
        self.assertIn("dpkg-query -W", dockerfile)


if __name__ == "__main__":
    unittest.main()
