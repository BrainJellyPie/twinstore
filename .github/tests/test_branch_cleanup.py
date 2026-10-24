"""Exercise branch cleanup against a local remote, without GitHub access."""

import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_merged_branches.py"
spec = importlib.util.spec_from_file_location("cleanup", SCRIPT)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.remote = root / "remote.git"
        self.work = root / "work"
        self.work.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Cleanup check")
        self.git("config", "user.email", "cleanup@example.invalid")
        self.git("commit", "--allow-empty", "-m", "baseline")
        self.old = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "main", "HEAD:fix/merged", "HEAD:fix/kept", "HEAD:fix/open-pr")
        self.git("commit", "--allow-empty", "-m", "new work")
        self.new = self.git("rev-parse", "HEAD")
        self.git("push", "origin", "HEAD:fix/unmerged")
        previous = Path.cwd()
        os.chdir(self.work)
        self.addCleanup(os.chdir, previous)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.work, text=True, stderr=subprocess.DEVNULL).strip()

    def plan(self):
        return cleanup.plan(["fix/kept"], {"fix/open-pr"})

    def test_plan_and_apply_preserve_main_active_open_pr_and_unmerged_branches(self):
        audit = self.plan()
        self.assertEqual(audit["candidates"], [{"name": "fix/merged", "sha": self.old}])
        self.assertIn("refs/heads/fix/merged", self.git("ls-remote", "--heads", "origin"))
        cleanup.apply(audit, {"fix/open-pr"})
        refs = self.git("ls-remote", "--heads", "origin")
        self.assertNotIn("refs/heads/fix/merged", refs)
        for name in ["main", "fix/kept", "fix/open-pr", "fix/unmerged"]:
            self.assertIn("refs/heads/" + name, refs)

    def test_concurrent_new_commit_rejects_entire_atomic_deletion(self):
        self.git("push", "origin", f"{self.old}:refs/heads/fix/also-merged")
        audit = self.plan()
        self.git("push", "origin", "HEAD:fix/merged")
        with self.assertRaises(subprocess.CalledProcessError):
            cleanup.apply(audit, set())
        refs = self.git("ls-remote", "--heads", "origin")
        self.assertIn(self.new + "\trefs/heads/fix/merged", refs)
        self.assertIn(self.old + "\trefs/heads/fix/also-merged", refs)

    def test_new_pull_request_stops_cleanup_before_any_deletion(self):
        audit = self.plan()
        with self.assertRaises(RuntimeError):
            cleanup.apply(audit, {"fix/merged"})
        self.assertIn("refs/heads/fix/merged", self.git("ls-remote", "--heads", "origin"))

    def test_empty_plan_does_not_push_the_checked_out_branch(self):
        with patch.object(cleanup, "git") as git:
            cleanup.apply({"base": self.old, "candidates": [], "retained": []}, set())
        git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
