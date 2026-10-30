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

    def test_restore_verify_script_fails_closed_without_invoking_pg_restore(self):
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
            env["PG_RESTORE_MARKER"] = str(marker)
            env["ZOMEGA_BACKUP_FILE"] = "synthetic.dump"
            env["ZOMEGA_RESTORE_VERIFY_DATABASE_URL"] = "postgresql://synthetic.invalid/restore"
            env["ZOMEGA_SOURCE_DATABASE_URL"] = "postgresql://synthetic.invalid/source"

            result = subprocess.run(
                ["bash", str(ROOT / "restore-verify.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
            self.assertIn("Restore verification is disabled", result.stderr)
            self.assertFalse(marker.exists(), "restore-verify.sh must never invoke pg_restore")

    def test_make_restore_verify_target_exits_before_any_restore_command(self):
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
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'printf called > "$PG_RESTORE_MARKER"\n',
                encoding="utf-8",
            )
            pg_restore.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["PG_RESTORE_MARKER"] = str(marker)

            result = subprocess.run(
                [make, "restore-verify"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Restore verification is disabled", result.stderr)
            self.assertFalse(marker.exists(), "make restore-verify must not invoke pg_restore")

    def test_dr_workflow_fails_closed_without_database_secret_injection(self):
        workflow = (ROOT / ".github" / "workflows" / "dr-verify.yml").read_text(encoding="utf-8")
        self.assertIn("Block unverified restore verification", workflow)
        self.assertIn("exit 64", workflow)
        self.assertNotIn("secrets.DR_SOURCE_DATABASE_URL", workflow)
        self.assertNotIn("secrets.DR_RESTORE_DATABASE_URL", workflow)

    def test_make_restore_verify_target_fails_closed_without_calling_restore_script(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^restore-verify:\n(?P<body>(?:^[ \t].*\n|^\n)*)", makefile)
        self.assertIsNotNone(match, "Makefile must keep an explicit restore-verify target")
        body = match.group("body")
        self.assertIn("Restore verification is disabled", body)
        self.assertIn("exit 64", body)
        self.assertNotIn("./restore-verify.sh", body)

    def test_make_restore_target_fails_closed_without_calling_restore_script(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^restore:\n(?P<body>(?:^[ \t].*\n|^\n)*)", makefile)
        self.assertIsNotNone(match, "Makefile must keep an explicit restore target")
        body = match.group("body")
        self.assertIn("Direct database restore is disabled", body)
        self.assertIn("exit 64", body)
        self.assertNotIn("./restore.sh", body)

    def test_runbook_does_not_advertise_disabled_restore_command_as_runnable(self):
        runbook = (ROOT / "docs" / "RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("restore and restore verification are disabled", runbook.lower())
        self.assertNotIn("./restore-verify.sh", runbook)
        self.assertNotIn("ZOMEGA_RESTORE_VERIFY_DATABASE_URL=...", runbook)
        self.assertIn("docs/DISASTER_RECOVERY.md", runbook)

    def test_make_help_marks_restore_verification_disabled(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("make restore-verify    - DISABLED:", makefile)
        self.assertNotIn("Run destructive drill against a disposable target only", makefile)


if __name__ == "__main__":
    unittest.main()
