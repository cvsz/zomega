"""Offline safety tests for the destructive restore verification script."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "restore-verify.sh"
TARGET_MARKER = "0123456789abcdef0123456789abcdef"
TARGET_MARKER_COMMENT = f"ZOMEGA_DISPOSABLE_RESTORE_TARGET:{TARGET_MARKER}"


class RestoreVerifySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.marker = self.root / "pg-restore-called"
        self.backup = self.root / "backup.dump"
        self.backup.write_bytes(b"synthetic backup fixture; no database data")
        digest = hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.backup.with_suffix(self.backup.suffix + ".sha256").write_text(
            f"{digest}  {self.backup}\n", encoding="utf-8"
        )

        psql = self.bin_dir / "psql"
        psql.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'url="$1"; shift\n'
            'query=""\n'
            "while (($#)); do\n"
            '  if [[ "$1" == "-c" ]]; then query="$2"; break; fi\n'
            "  shift\n"
            "done\n"
            'if [[ "$query" == *pg_control_system* ]]; then\n'
            '  if [[ "$url" == *source* ]]; then\n'
            '    [[ "${FAKE_SOURCE_FAIL:-0}" != 1 ]] || exit 41\n'
            '    printf \'%s\\n\' "${FAKE_SOURCE_IDENTITY}"\n'
            "  else\n"
            '    [[ "${FAKE_TARGET_FAIL:-0}" != 1 ]] || exit 42\n'
            '    printf \'%s\\n\' "${FAKE_TARGET_IDENTITY}"\n'
            "  fi\n"
            'elif [[ "$query" == *shobj_description* ]]; then\n'
            '  [[ "${FAKE_TARGET_MARKER_FAIL:-0}" != 1 ]] || exit 43\n'
            '  printf \'%s\\n\' "${FAKE_TARGET_MARKER:-}"\n'
            'elif [[ "$query" == *version_num* ]]; then printf \'0008\\n\'\n'
            'elif [[ "$query" == *available_credits* ]]; then printf \'0\\n\'\n'
            'elif [[ "$query" == *reserved_credits* ]]; then printf \'0\\n\'\n'
            "else echo 'unexpected SQL in test fixture' >&2; exit 97; fi\n",
            encoding="utf-8",
        )
        psql.chmod(0o755)

        pg_restore = self.bin_dir / "pg_restore"
        pg_restore.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'%s\\n\' "$*" >> "$PG_RESTORE_MARKER"\n',
            encoding="utf-8",
        )
        pg_restore.chmod(0o755)

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin_dir}{os.pathsep}{self.env.get('PATH', '')}",
                "ZOMEGA_BACKUP_FILE": str(self.backup),
                "ZOMEGA_SOURCE_DATABASE_URL": "postgresql://source-host/source_db",
                "ZOMEGA_RESTORE_VERIFY_DATABASE_URL": "postgresql://target-host/restore_db",
                "ZOMEGA_RESTORE_CONFIRMATION": "DRILL",
                "ZOMEGA_RESTORE_TARGET_MARKER": TARGET_MARKER,
                "FAKE_SOURCE_IDENTITY": "111",
                "FAKE_TARGET_IDENTITY": "222",
                "FAKE_TARGET_MARKER": TARGET_MARKER_COMMENT,
                "PG_RESTORE_MARKER": str(self.marker),
            }
        )

    def run_script(self, **overrides):
        env = self.env.copy()
        env.update(overrides)
        return subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True, env=env, check=False
        )

    def test_requires_explicit_confirmation_before_restore(self):
        result = self.run_script(ZOMEGA_RESTORE_CONFIRMATION="")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())

    def test_requires_source_database_url(self):
        result = self.run_script(ZOMEGA_SOURCE_DATABASE_URL="")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_requires_disposable_target_marker(self):
        result = self.run_script(ZOMEGA_RESTORE_TARGET_MARKER="")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_refuses_target_without_matching_disposable_marker(self):
        result = self.run_script(
            FAKE_TARGET_MARKER="ZOMEGA_DISPOSABLE_RESTORE_TARGET:wrong-marker"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not marked as the approved disposable database", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_refuses_when_target_marker_cannot_be_verified(self):
        result = self.run_script(FAKE_TARGET_MARKER_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unable to verify disposable restore target marker", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_refuses_same_postgres_cluster_even_when_database_names_differ(self):
        result = self.run_script(
            FAKE_TARGET_IDENTITY=self.env["FAKE_SOURCE_IDENTITY"],
            ZOMEGA_RESTORE_VERIFY_DATABASE_URL="postgresql://target-host/other_db",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("target must be a separate cluster", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_refuses_when_target_cluster_identity_cannot_be_verified(self):
        result = self.run_script(FAKE_TARGET_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unable to verify PostgreSQL cluster identity", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_refuses_malformed_cluster_identity(self):
        result = self.run_script(FAKE_TARGET_IDENTITY='["restore_db","222"]')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty or invalid", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_refuses_when_source_identity_cannot_be_verified(self):
        result = self.run_script(FAKE_SOURCE_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unable to verify PostgreSQL cluster identity", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_restores_only_after_distinct_marked_target_checks_and_verifies_contents(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"status":"PASS"', result.stdout)
        self.assertTrue(self.marker.exists())
        self.assertIn("--clean", self.marker.read_text(encoding="utf-8"))



class BackupSafetyTests(unittest.TestCase):
    def test_backup_respects_explicit_database_url_when_dotenv_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            bin_dir = temp_root / "bin"
            bin_dir.mkdir()
            (temp_root / ".env").write_text(
                "DATABASE_URL=postgresql://wrong.example/zomega\n",
                encoding="utf-8",
            )
            record = temp_root / "pg-dump-url"
            pg_dump = bin_dir / "pg_dump"
            pg_dump.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'printf \'%s\n\' "$1" > "$PG_DUMP_URL_RECORD"\n'
                'dump_file=""\n'
                'for arg in "$@"; do\n'
                '  case "$arg" in --file=*) dump_file="${arg#--file=}";; esac\n'
                "done\n"
                'test -n "$dump_file"\n'
                'printf "synthetic backup fixture" > "$dump_file"\n',
                encoding="utf-8",
            )
            pg_dump.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                    "DATABASE_URL": "postgresql://explicit.example/app",
                    "PG_DUMP_URL_RECORD": str(record),
                    "BACKUP_DIR": str(temp_root / "backups"),
                }
            )
            result = subprocess.run(
                ["bash", str(ROOT / "backup.sh")],
                cwd=temp_root,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                record.read_text(encoding="utf-8").strip(),
                "postgresql://explicit.example/app",
            )

class RestoreWorkflowSecurityTests(unittest.TestCase):
    def test_dr_workflow_pins_checkout_and_disables_persisted_credentials(self):
        workflow = (ROOT / ".github" / "workflows" / "dr-verify.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            workflow,
        )
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("uses: actions/checkout@v7", workflow)

    def test_dr_workflow_scopes_database_secrets_to_required_steps(self):
        workflow = (ROOT / ".github" / "workflows" / "dr-verify.yml").read_text(
            encoding="utf-8"
        )
        lines = workflow.splitlines()
        job_scope = lines[: lines.index("    steps:")]
        self.assertNotIn("    env:", job_scope)

        validation_start = lines.index(
            "      - name: Validate dedicated database configuration"
        )
        validation_end = lines.index(
            "      - name: Test restore safety guards without database access",
            validation_start,
        )
        validation_block = lines[validation_start:validation_end]
        self.assertIn(
            "          ZOMEGA_SOURCE_DATABASE_URL: "
            "${{ secrets.DR_SOURCE_DATABASE_URL }}",
            validation_block,
        )
        self.assertNotIn('          test -n "$DATABASE_URL"', validation_block)

        backup_start = lines.index("      - name: Create ephemeral backup evidence")
        self.assertEqual(
            lines[backup_start : backup_start + 4],
            [
                "      - name: Create ephemeral backup evidence",
                "        env:",
                "          DATABASE_URL: ${{ secrets.DR_SOURCE_DATABASE_URL }}",
                "        run: ./backup.sh",
            ],
        )

        restore_start = lines.index("      - name: Restore and verify")
        self.assertEqual(
            lines[restore_start : restore_start + 7],
            [
                "      - name: Restore and verify",
                "        env:",
                "          ZOMEGA_SOURCE_DATABASE_URL: "
                "${{ secrets.DR_SOURCE_DATABASE_URL }}",
                "          ZOMEGA_RESTORE_VERIFY_DATABASE_URL: "
                "${{ secrets.DR_RESTORE_DATABASE_URL }}",
                "          ZOMEGA_RESTORE_TARGET_MARKER: "
                "${{ secrets.DR_RESTORE_TARGET_MARKER }}",
                "          ZOMEGA_RESTORE_CONFIRMATION: ${{ inputs.confirmation }}",
                "        shell: bash",
            ],
        )

    def test_readme_has_independent_code_owner_for_restore_runbook(self):
        codeowners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertRegex(codeowners, r"(?m)^/README\.md\s+@cvsz\s+@policedbc\s*$")
        self.assertRegex(codeowners, r"(?m)^/\.github/CODEOWNERS\s+@cvsz\s+@policedbc\s*$")


if __name__ == "__main__":
    unittest.main()
