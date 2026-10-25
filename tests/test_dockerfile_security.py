"""Build-time policy contract for operating-system security updates."""
from pathlib import Path
import unittest


class DockerfileSecurityContract(unittest.TestCase):
    def test_base_image_packages_are_upgraded_before_runtime_user(self):
        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")

        update_index = dockerfile.index("apt-get update")
        upgrade_index = dockerfile.index("apt-get upgrade -y --no-install-recommends")
        cleanup_index = dockerfile.index("rm -rf /var/lib/apt/lists/*")
        user_index = dockerfile.index("USER zomega")

        self.assertLess(update_index, upgrade_index)
        self.assertLess(upgrade_index, cleanup_index)
        self.assertLess(cleanup_index, user_index)


if __name__ == "__main__":
    unittest.main()
