"""Run the content-script lifecycle and sharing regression tests with Node."""
import shutil
import subprocess
import unittest
from pathlib import Path


class LinkRecoveryTests(unittest.TestCase):
    def test_link_recovery(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for extension behavior tests")
        result = subprocess.run(
            [node, "--test", str(Path(__file__).with_suffix(".cjs"))],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
