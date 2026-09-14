from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APP_FILES = {
    "common/backend/__init__.py": "__init__.py",
    "common/backend/models.py": "models.py",
    "common/backend/schemas.py": "schemas.py",
    "common/backend/services.py": "services.py",
    "evidence/backend/evidence_discovery.py": "evidence_discovery.py",
    "reliability-source/backend/reliability_engine.py": "reliability_engine.py",
    "reliability-source/backend/source_verification.py": "source_verification.py",
    "judgment-reevaluation/backend/judgment_engine.py": "judgment_engine.py",
    "history-timeline/backend/timeline.py": "timeline.py",
    "permission-action/backend/action_engine.py": "action_engine.py",
    "release-support-response/backend/release.py": "release.py",
    "release-support-response/backend/response_composer.py": "response_composer.py",
    "release-support-response/backend/support_engine.py": "support_engine.py",
    "system-runtime/backend/database.py": "database.py",
    "system-runtime/backend/main.py": "main.py",
}

TEST_DIRS = [
    "case-management/backend/tests",
    "evidence/backend/tests",
    "reliability-source/backend/tests",
    "judgment-reevaluation/backend/tests",
    "history-timeline/backend/tests",
    "permission-action/backend/tests",
    "sharing-clarity/backend/tests",
    "release-support-response/backend/tests",
    "system-runtime/backend/tests",
]


def copy_required(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"Required file not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def assemble(output: Path) -> None:
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)

    app_dir = output / "backend" / "app"
    tests_dir = output / "backend" / "tests"
    scripts_dir = output / "backend" / "scripts"
    frontend_dir = output / "frontend"

    for src_rel, dst_name in APP_FILES.items():
        copy_required(ROOT / src_rel, app_dir / dst_name)

    copy_required(
        ROOT / "system-runtime/backend/requirements.txt",
        output / "backend" / "requirements.txt",
    )

    for test_dir_rel in TEST_DIRS:
        test_dir = ROOT / test_dir_rel
        if not test_dir.exists():
            continue
        for src in sorted(test_dir.glob("test_*.py")):
            dst = tests_dir / src.name
            if dst.exists() and dst.read_bytes() != src.read_bytes():
                raise RuntimeError(f"Conflicting test filename: {src.name}")
            copy_required(src, dst)

    source_scripts = ROOT / "system-runtime/backend/scripts"
    if source_scripts.exists():
        for src in sorted(source_scripts.glob("*.py")):
            copy_required(src, scripts_dir / src.name)

    copy_required(ROOT / "common/frontend/index.html", frontend_dir / "index.html")
    copy_required(ROOT / "common/frontend/styles.css", frontend_dir / "styles.css")
    copy_required(ROOT / "common/frontend/app_original.js", frontend_dir / "app.js")

    version_file = ROOT / "VERSION.txt"
    if version_file.exists():
        copy_required(version_file, output / "VERSION.txt")

    print(f"Runtime assembled at: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble the feature-organized repository into the original runnable layout."
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / ".runtime-build"),
        help="Output directory for the runnable backend/frontend layout.",
    )
    args = parser.parse_args()
    assemble(Path(args.output))


if __name__ == "__main__":
    main()
