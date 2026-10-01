"""A removed Waf environment lock must not turn a clean audit into an incremental build."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_release


class BuildCleanupTests(unittest.TestCase):
    def test_sdk_noop_clean_cannot_reuse_old_generated_artifact(self):
        with tempfile.TemporaryDirectory(prefix="kasugabus-clean-") as directory:
            root = Path(directory)
            (root / "build").mkdir()
            (root / "build/stale.pbw").write_bytes(b"previous artifact")
            source = root / "source.c"
            source.write_text("preserved source")
            with patch.object(check_release.subprocess, "run"):
                check_release.clean_build_output(root)
            self.assertFalse((root / "build").exists())
            self.assertEqual(source.read_text(), "preserved source")

    def test_redirected_build_folder_is_refused_before_sdk_or_file_removal(self):
        with tempfile.TemporaryDirectory(prefix="kasugabus-clean-") as directory:
            parent = Path(directory)
            root, outside = parent / "project", parent / "unrelated"
            root.mkdir()
            outside.mkdir()
            valuable = outside / "keep.txt"
            valuable.write_text("preserve")
            (root / "build").symlink_to(outside, target_is_directory=True)
            with patch.object(check_release.subprocess, "run") as cli, self.assertRaisesRegex(RuntimeError, "symlink"):
                check_release.clean_build_output(root)
            cli.assert_not_called()
            self.assertEqual(valuable.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
