"""Assembly must never remove a pre-existing user-owned path."""
import importlib.util
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "assemble_runtime", Path(__file__).resolve().parents[1] / "assemble_runtime.py"
)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class AssembleRuntimeTests(unittest.TestCase):
    def test_existing_directory_is_rejected_and_contents_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "user-work"
            output.mkdir()
            marker = output / "notes.txt"
            marker.write_text("keep this work", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                runtime.assemble(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep this work")

    def test_existing_file_is_rejected_and_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "notes.txt"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                runtime.assemble(output)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")

    def test_dangling_symlink_is_rejected_without_creating_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "absent"
            output = Path(folder) / "link"
            output.symlink_to(target, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                runtime.assemble(output)
            self.assertTrue(output.is_symlink())
            self.assertFalse(target.exists())

    def test_fresh_output_copies_runtime_sources_without_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "fresh"
            with redirect_stdout(StringIO()):
                runtime.assemble(output)
            for source, destination in runtime.APP_FILES.items():
                self.assertEqual(
                    (runtime.ROOT / source).read_bytes(),
                    (output / "backend/app" / destination).read_bytes(),
                )
            for source, destination in (
                ("index.html", "index.html"),
                ("styles.css", "styles.css"),
                ("app_original.js", "app.js"),
            ):
                self.assertEqual(
                    (runtime.ROOT / "common/frontend" / source).read_bytes(),
                    (output / "frontend" / destination).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
