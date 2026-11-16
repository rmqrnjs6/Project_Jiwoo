"""Regression tests for the runtime assembler's output-directory safety."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "assemble_runtime.py"
SPEC = importlib.util.spec_from_file_location("assemble_runtime", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
assembler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembler)


def test_default_generated_folder_is_permitted():
    expected = assembler.ROOT / ".runtime-build"
    assert assembler.validated_output_path(expected) == expected.resolve()


def test_external_custom_output_is_permitted(tmp_path):
    expected = tmp_path / "generated"
    assert assembler.validated_output_path(expected) == expected.resolve()


@pytest.mark.parametrize(
    "relative_or_absolute",
    ["root", "parent", "source", "nested_source"],
)
def test_existing_sources_and_ancestors_are_rejected(tmp_path, monkeypatch, relative_or_absolute):
    root = tmp_path / "project"
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_text("do not remove", encoding="utf-8")
    monkeypatch.setattr(assembler, "ROOT", root)
    paths = {
        "root": root,
        "parent": root.parent,
        "source": root / "common",
        "nested_source": root / "tools" / "generated",
    }
    with pytest.raises(ValueError, match="Unsafe runtime output"):
        assembler.assemble(paths[relative_or_absolute])
    assert sentinel.read_text(encoding="utf-8") == "do not remove"


def test_symlinked_generated_folder_cannot_escape_repository(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    try:
        (root / ".runtime-build").symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable")
    monkeypatch.setattr(assembler, "ROOT", root)
    with pytest.raises(ValueError, match="Unsafe runtime output"):
        assembler.assemble(root / ".runtime-build")
    assert external.is_dir()
