"""Release verification against real Git repositories and cached source artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from rb.release import REPOSITORY, identity, input_manifest, verify_artifact, verify_deployed


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
        (self.root / "release-notes").mkdir()
        (self.root / "release-notes/v0.1.0.md").write_text('Synthetic release notes.\n')
        (self.root / "site").mkdir()
        (self.root / "site/index.html").write_text('<html>Synthetic site</html>')
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic release fixture")
        self.git("tag", "-a", "v0.1.0", "-m", "Synthetic release")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def test_release_and_development_identity(self):
        release = identity(self.root, "v0.1.0")
        self.assertEqual(release["release_url"], REPOSITORY + "/releases/tag/v0.1.0")
        self.assertEqual(verify_deployed(release, self.root), release)
        self.assertIsNone(identity(self.root)["release_url"])

    def test_reject_wrong_commit_version_and_lightweight_tag(self):
        release = identity(self.root, "v0.1.0")
        for changed in ({"commit": "0" * 40}, {"version": "0.2.0"}, {"tag": "--help"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                verify_deployed({**release, **changed}, self.root)
        self.git("tag", "-d", "v0.1.0")
        self.git("tag", "v0.1.0")
        with self.assertRaises(ValueError):
            identity(self.root, "v0.1.0")

    def test_reject_dirty_tree_and_uncommitted_notes(self):
        (self.root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n# modified\n')
        with self.assertRaises(ValueError):
            identity(self.root, "v0.1.0")

    def test_input_hashes_redaction_and_missing_vintage(self):
        raw_dir = self.root / "data/raw/synthetic"
        raw_dir.mkdir(parents=True)
        body = b'Synthetic source data\n'
        sha = hashlib.sha256(body).hexdigest()
        raw = raw_dir / f'20261004T120000Z__sha256_{sha}.txt'
        raw.write_bytes(body)
        raw.with_suffix('.txt.meta.json').write_text(json.dumps({
            "url": "https://example.invalid/data?api_key=secret", "headers": {}}))
        item = input_manifest(self.root)[0]
        self.assertEqual(item["sha256"], sha)
        self.assertEqual(item["retrieved_at"], "2026-10-04T12:00:00+00:00")
        self.assertNotIn("secret", item["url"])
        self.assertNotIn("source_last_modified", item)
        raw.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            input_manifest(self.root)

    def test_artifact_rejects_changed_data_and_static_files(self):
        release = identity(self.root, "v0.1.0")
        site = self.root / "site"
        (site / "data.json").write_text('{"metrics": []}')
        (site / "version.json").write_text(json.dumps(release))
        (site / "provenance.json").write_text(json.dumps({
            "generator": release, "data_sha256": hashlib.sha256((site / "data.json").read_bytes()).hexdigest()}))
        run = {"head_sha": release["commit"]}
        verify_artifact(site, run, self.root)
        (site / "index.html").write_text('modified')
        with self.assertRaises(ValueError):
            verify_artifact(site, run, self.root)
        (site / "index.html").write_text('<html>Synthetic site</html>')
        (site / "data.json").write_text('{}')
        with self.assertRaises(ValueError):
            verify_artifact(site, run, self.root)


class EntryPointTests(unittest.TestCase):
    def test_installed_and_module_help(self):
        import sys
        executable = Path(sys.executable).parent / "rb"
        for args in ([str(executable), "--help"], [sys.executable, "-m", "rb", "--help"],
                     [sys.executable, "-m", "rb.release", "--help"]):
            with self.subTest(command=args):
                result = subprocess.run(args, text=True, capture_output=True, check=True)
                self.assertIn("usage:", result.stdout)
