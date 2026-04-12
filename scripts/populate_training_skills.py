from __future__ import annotations

import importlib
import importlib.metadata
import json
import shutil
from pathlib import Path

import yaml


PACKAGE_NAME = "mainsequence"
BUNDLE_PACKAGE = "agent_scaffold"
REPO_ROOT = Path(__file__).resolve().parents[1]


def installed_sdk_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        raise SystemExit(
            f"Installed package {PACKAGE_NAME!r} was not found. Run `uv sync` first."
        ) from exc


def installed_bundle_dir() -> Path:
    try:
        module = importlib.import_module(BUNDLE_PACKAGE)
    except Exception as exc:
        raise SystemExit(
            f"Installed bundle {BUNDLE_PACKAGE!r} could not be imported: {exc}"
        ) from exc

    package_paths = list(getattr(module, "__path__", []))
    if not package_paths:
        raise SystemExit(f"Installed bundle {BUNDLE_PACKAGE!r} does not expose __path__.")
    return Path(package_paths[0]).resolve()


def scan_skill_files(skills_root: Path) -> list[Path]:
    return sorted(skills_root.rglob("SKILL.md"))


def parse_frontmatter(skill_file: Path) -> dict:
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            block = "\n".join(lines[1:idx]).strip()
            return yaml.safe_load(block) or {}
    return {}


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> int:
    sdk_version = installed_sdk_version()
    bundle_dir = installed_bundle_dir()
    skills_root = bundle_dir / "skills"
    if not skills_root.exists():
        raise SystemExit(f"Installed bundle skills directory was not found: {skills_root}")

    version_root = REPO_ROOT / "cases" / "sdk" / sdk_version
    skills_output_root = version_root / "skills"
    version_root.mkdir(parents=True, exist_ok=True)
    skills_output_root.mkdir(parents=True, exist_ok=True)

    agents_path = bundle_dir / "AGENTS.md"
    if agents_path.exists():
        agents_target = version_root / "agent_scaffold" / "AGENTS.md"
        agents_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(agents_path, agents_target)

    catalog: list[dict[str, object]] = []
    for skill_file in scan_skill_files(skills_root):
        skill_path = skill_file.parent.relative_to(skills_root).as_posix()
        skill_meta = parse_frontmatter(skill_file)

        skill_root = skills_output_root / skill_path
        prompt_cases_root = skill_root / "cases"
        source_root = skill_root / "source"
        prompt_cases_root.mkdir(parents=True, exist_ok=True)
        source_root.mkdir(parents=True, exist_ok=True)

        (prompt_cases_root / ".gitkeep").write_text("", encoding="utf-8")
        snapshot_skill_file = source_root / "SKILL.md"
        shutil.copy2(skill_file, snapshot_skill_file)

        skill_record = {
            "skill_path": skill_path,
            "display_name": skill_meta.get("name", skill_path),
            "description": skill_meta.get("description", ""),
            "sdk_package": PACKAGE_NAME,
            "sdk_version": sdk_version,
            "installed_bundle_package": BUNDLE_PACKAGE,
            "installed_skill_file": str(skill_file),
            "copied_skill_file": str(snapshot_skill_file),
        }
        write_yaml(skill_root / "skill.yaml", skill_record)

        readme = (
            f"# {skill_path}\n\n"
            f"SDK version: `{sdk_version}`\n\n"
            f"Installed skill source: `{skill_file}`\n\n"
            f"Copied bundle file: `{snapshot_skill_file}`\n\n"
            "Add version-specific prompt cases under `cases/`.\n"
        )
        (skill_root / "README.md").write_text(readme, encoding="utf-8")
        catalog.append(skill_record)

    manifest = {
        "sdk_package": PACKAGE_NAME,
        "sdk_version": sdk_version,
        "bundle_package": BUNDLE_PACKAGE,
        "bundle_dir": str(bundle_dir),
        "skills_count": len(catalog),
        "skills": catalog,
    }
    (version_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Populated {len(catalog)} skills for installed SDK {sdk_version}")
    print(version_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
