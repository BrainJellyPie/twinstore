"""Exercise release tag binding against a local bare repo and a fake gh command.

Run with python3 .github/tests/test_release_workflow.py. No GitHub calls occur.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "release.yml"
GIT = shutil.which("git")


def shell_step(name):
    lines = WORKFLOW.read_text().splitlines()
    start = lines.index("      - name: " + name)
    while lines[start] != "        run: |":
        start += 1
    script = []
    for line in lines[start + 1:]:
        if line and not line.startswith("          "):
            break
        script.append(line[10:] if line else "")
    return "\n".join(script) + "\n"


class ReleaseTagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="twinstore-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.remote = self.root / "remote.git"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.git("init", "--bare", str(self.remote), cwd=self.root)
        self.git("init", str(self.work), cwd=self.root)
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("commit", "--allow-empty", "-m", "old commit")
        self.old = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("commit", "--allow-empty", "-m", "selected commit")
        self.selected = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "HEAD:refs/heads/main")
        (self.work / "out").mkdir()
        (self.work / "out" / "snapshot.zip").write_bytes(b"fixture")
        self.published = self.root / "published.json"
        self.env = {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "LANG": "C.UTF-8", "RELEASE_TAG": "v1.2.3", "GITHUB_SHA": self.selected,
            "RELEASE_TEST_REMOTE": str(self.remote), "RELEASE_TEST_OLD": self.old,
            "RELEASE_TEST_GIT": str(GIT), "RELEASE_TEST_PUBLISHED": str(self.published),
            "GITHUB_ENV": str(self.root / "github-env"), "GITHUB_OUTPUT": str(self.root / "github-output"),
        }
        gh = self.bin / "gh"
        gh.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import json, os, subprocess, sys
            from pathlib import Path
            args = sys.argv[1:]
            assert args[:2] == ['release', 'create']
            tag = 'refs/tags/' + args[2]
            git = [os.environ['RELEASE_TEST_GIT'], '--git-dir=' + os.environ['RELEASE_TEST_REMOTE']]
            if os.environ.get('RELEASE_TEST_RACE'):
                subprocess.run([*git, 'update-ref', tag, os.environ['RELEASE_TEST_OLD']], check=True)
            if os.environ.get('RELEASE_TEST_DELETE'):
                subprocess.run([*git, 'update-ref', '-d', tag], check=True)
            existing = subprocess.run([*git, 'rev-parse', '--verify', tag + '^{commit}'], capture_output=True, text=True)
            if existing.returncode:
                if '--verify-tag' in args:
                    sys.exit(1)
                target = args[args.index('--target') + 1] if '--target' in args else 'refs/heads/main'
                subprocess.run([*git, 'update-ref', tag, target], check=True)
            target = subprocess.check_output([*git, 'rev-parse', tag + '^{commit}'], text=True).strip()
            Path(os.environ['RELEASE_TEST_PUBLISHED']).write_text(json.dumps({'target': target, 'args': args, 'notes': sys.stdin.read()}))
            """))
        gh.chmod(0o755)

    def git(self, *args, cwd=None, check=True):
        return subprocess.run([GIT, *args], cwd=cwd or self.work, text=True, capture_output=True, check=check)

    def tag(self, target, annotated=False):
        args = ["tag"]
        if annotated:
            args += ["-a", "-m", "Annotated release"]
        self.git(*args, "v1.2.3", target)
        self.git("push", "origin", "refs/tags/v1.2.3")

    def publish(self):
        return subprocess.run(["bash", "-e", "-o", "pipefail", "-c", shell_step("Publish release")],
                              cwd=self.work, env=self.env, text=True, capture_output=True)

    def test_new_version_is_tagged_at_the_selected_commit(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.published.read_text())["target"], self.selected)

    def test_versioned_notes_precede_download_instructions(self):
        notes = self.work / "release-notes" / "v1.2.3.md"
        notes.parent.mkdir()
        notes.write_text("Release-specific changes.\n")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(self.published.read_text())["notes"]
        self.assertTrue(body.startswith("Release-specific changes.\n\n"))
        self.assertIn("Download the file for your computer", body)

    def test_matching_lightweight_and_annotated_tags_are_kept(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                self.tag(self.selected, annotated)
                before = self.git("--git-dir=" + str(self.remote), "rev-parse", "refs/tags/v1.2.3").stdout
                if annotated:
                    self.env["GITHUB_SHA"] = before.strip()
                result = self.publish()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.published.read_text())["target"], self.selected)
                self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "refs/tags/v1.2.3").stdout, before)
                self.git("tag", "-d", "v1.2.3")
                self.git("push", "origin", ":refs/tags/v1.2.3")

    def test_a_tag_for_another_commit_cannot_publish_these_artifacts(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                self.tag(self.old, annotated)
                try:
                    result = self.publish()
                    self.assertNotEqual(result.returncode, 0, "An existing tag ignores gh --target")
                    self.assertFalse(self.published.exists())
                    self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "refs/tags/v1.2.3^{commit}").stdout.strip(), self.old)
                finally:
                    self.git("tag", "-d", "v1.2.3")
                    self.git("push", "origin", ":refs/tags/v1.2.3")
                    self.published.unlink(missing_ok=True)

    def test_a_competing_tag_created_before_push_is_not_overwritten(self):
        wrapper = self.bin / "git"
        wrapper.write_text('#!/bin/sh\nif [ "$1" = "ls-remote" ]; then\n  "$RELEASE_TEST_GIT" "$@"\n  "$RELEASE_TEST_GIT" --git-dir="$RELEASE_TEST_REMOTE" update-ref "refs/tags/$RELEASE_TAG" "$RELEASE_TEST_OLD"\nelse\n  exec "$RELEASE_TEST_GIT" "$@"\nfi\n')
        wrapper.chmod(0o755)
        self.env["RELEASE_TEST_RACE"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.published.exists())
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "refs/tags/v1.2.3^{commit}").stdout.strip(), self.old)

    def test_a_failed_tag_lookup_does_not_publish(self):
        wrapper = self.bin / "git"
        wrapper.write_text('#!/bin/sh\nif [ "$1" = "ls-remote" ]; then exit 128; fi\nexec "$RELEASE_TEST_GIT" "$@"\n')
        wrapper.chmod(0o755)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.published.exists())

    def test_a_tag_removed_just_before_publication_is_not_recreated(self):
        self.tag(self.selected)
        self.env["RELEASE_TEST_DELETE"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.published.exists())
        self.assertNotEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "--verify", "refs/tags/v1.2.3", check=False).returncode, 0)

    def test_version_validation_accepts_snapshot_and_rejects_shell_text(self):
        for tag, valid in [("", True), ("v1.2.3", True), ("v1.2.3-rc.1", True),
                           ("v1.2", False), ("$(touch unexpected)", False), ("v1.2.3\ninjected", False)]:
            with self.subTest(tag=tag):
                result = subprocess.run(["bash", "-e", "-c", shell_step("Check version")], cwd=self.work,
                                        env={**self.env, "RELEASE_TAG": tag}, capture_output=True)
                self.assertEqual(result.returncode == 0, valid)
        self.assertFalse((self.work / "unexpected").exists())

    def test_release_branch_uses_its_version_for_build_and_publication(self):
        for ref, tag, expected, valid in [
            ("refs/heads/release/v0.4.12", "", "v0.4.12", True),
            ("refs/heads/release/v0.4.12-rc.1", "", "v0.4.12-rc.1", True),
            ("refs/heads/release/v0.4", "", "", False),
            ("refs/heads/release/v0.4.12\ninjected", "", "", False),
            ("refs/heads/main", "v0.4.12", "v0.4.12", True),
            ("refs/tags/v0.4.12", "v0.4.12", "v0.4.12", True),
            ("refs/heads/main", "", "", True),
        ]:
            with self.subTest(ref=ref):
                for key in ("GITHUB_ENV", "GITHUB_OUTPUT"):
                    Path(self.env[key]).unlink(missing_ok=True)
                result = subprocess.run(["bash", "-e", "-c", shell_step("Check version")], cwd=self.work,
                                        env={**self.env, "GITHUB_REF": ref, "RELEASE_TAG": tag}, capture_output=True)
                self.assertEqual(result.returncode == 0, valid)
                if valid:
                    self.assertEqual(Path(self.env["GITHUB_ENV"]).read_text(), f"RELEASE_TAG={expected}\n")
                    self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), f"tag={expected}\n")
                else:
                    self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())


if __name__ == "__main__":
    unittest.main()
