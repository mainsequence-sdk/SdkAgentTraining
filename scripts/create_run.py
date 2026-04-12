from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create a versioned run folder.")
    parser.add_argument("--agent", required=True, help="Agent label, for example codex.")
    parser.add_argument("--model", required=True, help="Model label, for example gpt-5.4.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root,
        help="Training repository root. Defaults to the current repository.",
    )
    parser.add_argument(
        "--package",
        default="mainsequence",
        help="Installed SDK distribution name.",
    )
    parser.add_argument(
        "--source-checkout",
        type=Path,
        help="Optional source checkout to record alongside the installed package version.",
    )
    parser.add_argument(
        "--sdk-version",
        help="Override the SDK version used in the run path.",
    )
    parser.add_argument(
        "--timestamp",
        help="Override timestamp in ISO-like form, for example 2026-04-12T10-30-00Z.",
    )
    return parser


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return slug.strip("-").lower() or "unknown"


def read_sdk_version(package: str) -> str:
    return importlib.metadata.version(package)


def read_git_commit(source_checkout: Path | None) -> str | None:
    if source_checkout is None:
        return None
    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(source_checkout), "rev-parse", "HEAD"],
                text=True,
            )
            .strip()
        )
    except Exception:
        return None


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    source_checkout = args.source_checkout.resolve() if args.source_checkout else None

    sdk_version = args.sdk_version or read_sdk_version(args.package)
    timestamp = args.timestamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    agent_slug = slugify(args.agent)
    model_slug = slugify(args.model)

    run_root = repo_root / "runs" / "sdk" / sdk_version / agent_slug / model_slug / timestamp
    for child in ("skills", "evaluations", "logs"):
        (run_root / child).mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": f"{sdk_version}:{agent_slug}:{model_slug}:{timestamp}",
        "created_at": timestamp,
        "sdk": {
            "package": args.package,
            "version": sdk_version,
            "source_checkout": str(source_checkout) if source_checkout else None,
            "git_commit": read_git_commit(source_checkout),
        },
        "agent": {
            "name": args.agent,
            "slug": agent_slug,
            "model": args.model,
            "model_slug": model_slug,
        },
        "paths": {
            "skills": "skills",
            "evaluations": "evaluations",
            "logs": "logs",
        },
    }
    manifest_path = run_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
