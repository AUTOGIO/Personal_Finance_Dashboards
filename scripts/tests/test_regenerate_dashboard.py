#!/usr/bin/env python3
"""
Regression tests for scripts/regenerate_dashboard.py failure handling.

Uses only the Python standard library. Operates on private scratch copies
of the real workbook and HTML so the primary files are never at risk.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "regenerate_dashboard.py"
XLSX = REPO_ROOT / "data" / "wealthcommand.xlsx"
HTML = REPO_ROOT / "bloomberg-terminal.html"
PYTHON = sys.executable


class TestRegenerateDashboardFailure(unittest.TestCase):
    """Verify the wealth patcher fails closed and leaves output untouched."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)
        self.xlsx = self.td / "wealthcommand.xlsx"
        self.html = self.td / "bloomberg-terminal.html"
        shutil.copy2(XLSX, self.xlsx)
        shutil.copy2(HTML, self.html)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self):
        return subprocess.run(
            [PYTHON, str(SCRIPT), str(self.xlsx), str(self.html), str(self.html)],
            capture_output=True,
            text=True,
        )

    def test_successful_run_passes_spot_checks(self):
        """A valid run exits zero and reports spot-checks passed."""
        result = self._run()
        self.assertEqual(result.returncode, 0, "Expected zero exit on success")
        self.assertIn("[ok] all", result.stdout)
        self.assertIn("spot-checks passed", result.stdout)
        self.assertTrue(self.html.exists())
        self.assertGreater(self.html.stat().st_size, 0)

    def test_broken_anchor_fails_and_leaves_destination_unchanged(self):
        """A deliberately broken required anchor causes non-zero exit and no write."""
        text = self.html.read_text(encoding="utf-8")
        # Break a required Tier-1 anchor: CMD CTR Sub Stack/mo tile label.
        text = text.replace(
            '<div class="kpi-lbl">Sub Stack/mo</div>',
            '<div class="kpi-lbl">Sub Stack BROKEN</div>',
            1,
        )
        self.html.write_text(text, encoding="utf-8")

        # Hash the file exactly as the script will see it, before the run.
        before_hash = hashlib.sha256(self.html.read_bytes()).hexdigest()

        result = self._run()
        after_hash = hashlib.sha256(self.html.read_bytes()).hexdigest()

        self.assertNotEqual(result.returncode, 0, "Expected non-zero exit on broken anchor")
        self.assertIn("spot-check(s) failed", result.stdout)
        self.assertEqual(
            before_hash, after_hash,
            "Destination must be unchanged after a failed run",
        )

    def test_idempotent_second_run(self):
        """Two consecutive successful runs produce identical output."""
        first = self._run()
        self.assertEqual(first.returncode, 0)
        first_hash = hashlib.sha256(self.html.read_bytes()).hexdigest()

        second = self._run()
        self.assertEqual(second.returncode, 0)
        second_hash = hashlib.sha256(self.html.read_bytes()).hexdigest()

        self.assertEqual(first_hash, second_hash)


if __name__ == "__main__":
    unittest.main()
