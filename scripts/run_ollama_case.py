from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import os
import re
from pathlib import Path

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.10:11434")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one training case against an Ollama model.")
    parser.add_argument("--model", required=True, help="Ollama model name, for example ms-reasoning:latest.")
    parser.add_argument(
        "--case",
        required=True,
        help="Case id or case directory path, for example or-001-recurring-artifact-job.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_OLLAMA_BASE_URL,
        help="Ollama base URL. Defaults to OLLAMA_BASE_URL or http://192.168.1.10:11434.",
    )
    parser.add_argument(
        "--agent",
        default="ollama",
        help="Agent label stored in the run folder.",
    )
    parser.add_argument(
        "--evaluator-name",
        default="codex-heuristic-v1",
        help="Name stored in the evaluation JSON for the automatic evaluator.",
    )
    parser.add_argument(
        "--evaluator-kind",
        default="rule-based",
        help="Evaluator kind stored in the evaluation JSON.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature sent to Ollama.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP timeout in seconds.",
    )
    return parser


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return slug.strip("-").lower() or "unknown"


def read_sdk_version() -> str:
    return importlib.metadata.version("mainsequence")


def locate_sdk_root(sdk_version: str) -> Path:
    sdk_root = REPO_ROOT / "sdk" / sdk_version
    if not sdk_root.exists():
        raise SystemExit(f"SDK snapshot not found for installed version {sdk_version}: {sdk_root}")
    return sdk_root


def load_case_map(sdk_root: Path) -> dict:
    path = sdk_root / "case-map.yaml"
    if not path.exists():
        raise SystemExit(f"Case map not found for SDK snapshot: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_source_of_truth(sdk_root: Path) -> dict:
    path = sdk_root / "source-of-truth.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def case_sets_for_sdk(sdk_root: Path) -> list[str]:
    case_map = load_case_map(sdk_root)
    case_sets = set()
    default_case_set = case_map.get("default_case_set")
    if default_case_set:
        case_sets.add(str(default_case_set))
    for entry in (case_map.get("skills", {}) or {}).values():
        if isinstance(entry, str):
            case_sets.add(entry)
        elif isinstance(entry, dict) and entry.get("case_set"):
            case_sets.add(str(entry["case_set"]))
    return sorted(case_sets)


def find_case_by_id(case_id: str, sdk_root: Path) -> Path:
    matches = []
    for case_set in case_sets_for_sdk(sdk_root):
        case_root = REPO_ROOT / "cases" / case_set / "skills"
        if not case_root.exists():
            continue
        for case_yaml in case_root.glob("**/case.yaml"):
            payload = yaml.safe_load(case_yaml.read_text(encoding="utf-8")) or {}
            if payload.get("id") == case_id:
                matches.append(case_yaml.parent)
    if not matches:
        raise SystemExit(f"Case id not found: {case_id}")
    if len(matches) > 1:
        raise SystemExit(f"Case id is ambiguous: {case_id}")
    return matches[0]


def resolve_case(case_arg: str, sdk_root: Path) -> Path:
    candidate = Path(case_arg)
    if candidate.exists():
        return candidate.resolve()
    return find_case_by_id(case_arg, sdk_root)


def infer_skill_path_from_case(case_path: Path) -> str:
    case_payload = yaml.safe_load((case_path / "case.yaml").read_text(encoding="utf-8")) or {}
    if case_payload.get("skill_path"):
        return str(case_payload["skill_path"])

    current = case_path.resolve()
    for parent in [current] + list(current.parents):
        if parent.name != "cases":
            continue
        try:
            relative = parent.parent.relative_to(REPO_ROOT / "cases")
        except ValueError:
            continue
        parts = relative.parts
        if len(parts) >= 3 and parts[1] == "skills":
            return "/".join(parts[2:])
    raise SystemExit(f"Could not determine skill path for case: {case_path}")


def find_skill_root(skill_path: str, sdk_root: Path) -> Path:
    skill_root = sdk_root / "skills" / skill_path
    if not (skill_root / "source" / "SKILL.md").exists():
        raise SystemExit(f"Could not find SDK skill snapshot for {skill_path}: {skill_root}")
    return skill_root


def build_prompt_bundle(case_path: Path, sdk_root: Path, skill_root: Path) -> tuple[str, str]:
    agents_path = sdk_root / "agent_scaffold" / "AGENTS.md"
    skill_path = skill_root / "source" / "SKILL.md"
    prompt_path = case_path / "prompt.md"

    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    skill_text = skill_path.read_text(encoding="utf-8")
    user_prompt = prompt_path.read_text(encoding="utf-8")

    system_prompt = (
        "You are being evaluated on a Main Sequence skill.\n\n"
        "Use the provided project scaffold instructions and the skill instructions as authoritative context.\n\n"
        "Project scaffold instructions:\n"
        f"{agents_text}\n\n"
        "Skill instructions:\n"
        f"{skill_text}\n"
    )
    return system_prompt, user_prompt


def create_run_root(sdk_version: str, agent: str, model: str) -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_root = REPO_ROOT / "runs" / "sdk" / sdk_version / slugify(agent) / slugify(model) / timestamp
    for child in ("skills", "evaluations", "logs"):
        (run_root / child).mkdir(parents=True, exist_ok=True)
    return run_root


def write_run_manifest(
    run_root: Path,
    sdk_root: Path,
    sdk_version: str,
    agent: str,
    model: str,
    base_url: str,
) -> None:
    manifest = {
        "run_id": f"{sdk_version}:{slugify(agent)}:{slugify(model)}:{run_root.name}",
        "created_at": run_root.name,
        "sdk": {
            "package": "mainsequence",
            "version": sdk_version,
            "snapshot_root": str(sdk_root),
            "source_of_truth_file": str(sdk_root / "source-of-truth.yaml"),
            "source_of_truth": load_source_of_truth(sdk_root),
        },
        "agent": {
            "name": agent,
            "slug": slugify(agent),
            "model": model,
            "model_slug": slugify(model),
            "provider": "ollama",
            "base_url": base_url,
        },
        "paths": {
            "skills": "skills",
            "evaluations": "evaluations",
            "logs": "logs",
        },
    }
    (run_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_ollama_chat(
    *,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    timeout: int,
) -> dict:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": temperature,
        },
    }
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return {
        "request": payload,
        "response": response.json(),
    }


def save_case_outputs(
    *,
    run_root: Path,
    case_path: Path,
    skill_path: str,
    prompt_bundle: tuple[str, str],
    chat_payload: dict,
) -> tuple[Path, Path]:
    case_payload = yaml.safe_load((case_path / "case.yaml").read_text(encoding="utf-8")) or {}
    case_id = case_payload["id"]
    output_root = run_root / "skills" / Path(skill_path) / case_id
    output_root.mkdir(parents=True, exist_ok=True)

    system_prompt, user_prompt = prompt_bundle
    (output_root / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
    (output_root / "user_prompt.md").write_text(user_prompt, encoding="utf-8")

    response_text = chat_payload["response"]["message"]["content"]
    response_path = output_root / "response.md"
    response_path.write_text(response_text.strip() + "\n", encoding="utf-8")

    log_root = run_root / "logs" / Path(skill_path) / case_id
    log_root.mkdir(parents=True, exist_ok=True)
    request_log = log_root / "ollama_request.json"
    response_log = log_root / "ollama_response.json"
    request_log.write_text(
        json.dumps(chat_payload["request"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    response_log.write_text(
        json.dumps(chat_payload["response"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return response_path, output_root


def evaluate_response(
    case_path: Path,
    run_root: Path,
    response_path: Path,
    evaluator_name: str,
    evaluator_kind: str,
) -> Path:
    import subprocess

    case_id = yaml.safe_load((case_path / "case.yaml").read_text(encoding="utf-8"))["id"]
    evaluation_path = run_root / "evaluations" / f"{case_id}.json"
    subprocess.check_call(
        [
            str(REPO_ROOT / ".venv" / "bin" / "python"),
            str(REPO_ROOT / "scripts" / "evaluate_case.py"),
            "--case-path",
            str(case_path),
            "--response-path",
            str(response_path),
            "--evaluator-name",
            evaluator_name,
            "--evaluator-kind",
            evaluator_kind,
            "--output-path",
            str(evaluation_path),
        ]
    )
    return evaluation_path


def main() -> int:
    args = build_parser().parse_args()
    sdk_version = read_sdk_version()
    sdk_root = locate_sdk_root(sdk_version)
    case_path = resolve_case(args.case, sdk_root)
    skill_path = infer_skill_path_from_case(case_path)
    skill_root = find_skill_root(skill_path, sdk_root)
    system_prompt, user_prompt = build_prompt_bundle(case_path, sdk_root, skill_root)

    run_root = create_run_root(sdk_version, args.agent, args.model)
    write_run_manifest(run_root, sdk_root, sdk_version, args.agent, args.model, args.base_url)

    chat_payload = run_ollama_chat(
        base_url=args.base_url,
        model=args.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=args.temperature,
        timeout=args.timeout,
    )
    response_path, output_root = save_case_outputs(
        run_root=run_root,
        case_path=case_path,
        skill_path=skill_path,
        prompt_bundle=(system_prompt, user_prompt),
        chat_payload=chat_payload,
    )
    evaluation_path = evaluate_response(
        case_path,
        run_root,
        response_path,
        args.evaluator_name,
        args.evaluator_kind,
    )

    print(f"Run root: {run_root}")
    print(f"Case output: {output_root}")
    print(f"Evaluation: {evaluation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
