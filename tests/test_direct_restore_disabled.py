"""Regression tests for the disabled direct database restore entry points."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DirectRestoreDisabledTests(unittest.TestCase):
    def test_restore_script_fails_closed_without_invoking_pg_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            marker = temp / "pg-restore-called"
            pg_restore = bin_dir / "pg_restore"
            pg_restore.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'printf called > "$PG_RESTORE_MARKER"\n',
                encoding="utf-8",
            )
            pg_restore.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["DATABASE_URL"] = "postgresql://synthetic.invalid/production"
            env["PG_RESTORE_MARKER"] = str(marker)

            result = subprocess.run(
                ["bash", str(ROOT / "restore.sh"), "synthetic.dump"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
            self.assertIn("Direct database restore is disabled", result.stderr)
            self.assertFalse(marker.exists(), "restore.sh must never invoke pg_restore")


    def test_make_restore_target_exits_before_any_pg_restore_command(self):
        make = shutil.which("make")
        if make is None:
            self.skipTest("make is unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            marker = temp / "pg-restore-called"
            pg_restore = bin_dir / "pg_restore"
            pg_restore.write_text(
                "#!/usr/bin/env bash\\n"
                "set -euo pipefail\\n"
                'printf called > "$PG_RESTORE_MARKER"\\n',
                encoding="utf-8",
            )
            pg_restore.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["DATABASE_URL"] = "postgresql://synthetic.invalid/production"
            env["PG_RESTORE_MARKER"] = str(marker)

            result = subprocess.run(
                [make, "restore", "src=synthetic.dump"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Direct database restore is disabled", result.stderr)
            self.assertFalse(marker.exists(), "make restore must never invoke pg_restore")

    def test_make_restore_target_fails_closed_without_calling_restore_script(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^restore:\n(?P<body>(?:^[ \t].*\n|^\n)*)", makefile)
        self.assertIsNotNone(match, "Makefile must keep an explicit restore target")
        body = match.group("body")
        self.assertIn("Direct database restore is disabled", body)
        self.assertIn("exit 64", body)
        self.assertNotIn("./restore.sh", body)


if __name__ == "__main__":
    unittest.main()
