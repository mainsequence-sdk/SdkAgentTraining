from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a saved model response for one case.")
    parser.add_argument("--case-path", type=Path, required=True, help="Path to the case directory.")
    parser.add_argument("--response-path", type=Path, required=True, help="Path to the saved response.md file.")
    parser.add_argument(
        "--evaluator-name",
        default="codex-heuristic-v1",
        help="Name of the evaluator recorded in the evaluation JSON.",
    )
    parser.add_argument(
        "--evaluator-kind",
        default="rule-based",
        help="Evaluator kind, for example rule-based, llm-judge, or human-review.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="Optional path for the evaluation JSON. Prints to stdout when omitted.",
    )
    return parser


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def contains_all(text: str, patterns: list[str]) -> bool:
    return all(pattern in text for pattern in patterns)


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def score_or_001(response_text: str, rubric: dict) -> dict:
    lowered = response_text.lower()
    results: list[dict] = []

    def add_result(criterion_id: str, score: float, evidence: list[str]) -> None:
        weight = next(
            item["weight"]
            for item in rubric["criteria"]
            if item["id"] == criterion_id
        )
        results.append(
            {
                "id": criterion_id,
                "weight": weight,
                "score": score,
                "weighted_score": round(score * weight, 4),
                "evidence": evidence,
            }
        )

    workflow_evidence = []
    workflow_score = 0.0
    if "scheduled_jobs.yaml" in lowered:
        workflow_score = 0.5
        workflow_evidence.append("mentions scheduled_jobs.yaml")
    if contains_any(lowered, ["schedule_batch_jobs", "repository-managed", "version control", "team-managed"]):
        workflow_score = 1.0
        workflow_evidence.append("treats recurring workflow as code-managed")
    add_result("workflow-choice", workflow_score, workflow_evidence)

    artifact_evidence = []
    artifact_score = 0.0
    if "artifact" in lowered:
        artifact_score = 0.5
        artifact_evidence.append("mentions Artifact")
    if contains_any(lowered, ["platform-managed file", "file primitive", "local path", "fragile local path"]):
        artifact_score = 1.0
        artifact_evidence.append("explains why Artifact is used instead of local files")
    add_result("artifact-handling", artifact_score, artifact_evidence)

    pinned_image_evidence = []
    pinned_image_score = 0.0
    if contains_any(lowered, ["project image", "related_image_id", "pinned image"]):
        pinned_image_score = 0.5
        pinned_image_evidence.append("mentions project image pinning")
    if contains_any(lowered, ["related_image_id", "pinned image", "freeze", "reproducible"]):
        pinned_image_score = 1.0
        pinned_image_evidence.append("ties reproducibility to image pinning")
    add_result("pinned-image", pinned_image_score, pinned_image_evidence)

    strict_evidence = []
    strict_score = 0.0
    if "--strict" in response_text:
        strict_score = 0.5
        strict_evidence.append("mentions --strict")
    if "--strict" in response_text and contains_any(
        lowered,
        ["not the default", "do not use", "only if", "full desired state", "dangerous", "casually"],
    ):
        strict_score = 1.0
        strict_evidence.append("treats --strict as an intentional/safe choice, not default")
    add_result("strict-safety", strict_score, strict_evidence)

    verification_evidence = []
    verification_score = 0.0
    if contains_any(lowered, ["jobs list", "runs list", "runs logs"]):
        verification_score = 0.5
        verification_evidence.append("mentions post-creation verification commands")
    if contains_all(lowered, ["jobs list", "runs list", "runs logs"]):
        verification_score = 1.0
        verification_evidence.append("covers jobs, runs, and logs verification")
    add_result("verification", verification_score, verification_evidence)

    concrete_evidence = []
    concrete_score = 0.0
    if contains_any(lowered, ["jobs:", "execution_path:", "task_schedule:", "related_image_id:"]):
        concrete_score = 0.5
        concrete_evidence.append("includes YAML-like example")
    if contains_any(lowered, ["mainsequence project schedule_batch_jobs", "mainsequence project sync"]):
        concrete_score = 1.0
        concrete_evidence.append("includes concrete CLI flow")
    add_result("concrete-example", concrete_score, concrete_evidence)

    penalties: list[dict] = []
    penalty_total = 0.0

    invented_command_patterns = [
        "mainsequence project create_image",
        "mainsequence project pin_image",
        "mainsequence project create_job",
        "mainsequence project create_artifact",
        "mainsequence project artifacts list",
        "mainsequence project artifacts show",
    ]
    invented_matches = [pattern for pattern in invented_command_patterns if pattern in lowered]
    if invented_matches:
        penalties.append(
            {
                "id": "invented-cli-commands",
                "amount": 0.25,
                "evidence": invented_matches,
            }
        )
        penalty_total += 0.25

    wrong_yaml_markers = []
    if "mode:" in lowered:
        wrong_yaml_markers.append("mode:")
    if "\n    schedule:" in lowered or "\n    image:" in lowered:
        wrong_yaml_markers.extend(
            marker
            for marker in ["schedule:", "image:"]
            if marker in lowered
        )
    if wrong_yaml_markers and "task_schedule:" not in lowered:
        penalties.append(
            {
                "id": "wrong-job-yaml-shape",
                "amount": 0.2,
                "evidence": wrong_yaml_markers,
            }
        )
        penalty_total += 0.2

    if "related_image_id" not in lowered:
        penalties.append(
            {
                "id": "missing-related-image-id-example",
                "amount": 0.15,
                "evidence": ["response example omitted related_image_id"],
            }
        )
        penalty_total += 0.15

    raw_total = round(sum(item["weighted_score"] for item in results), 4)
    total = round(max(0.0, raw_total - penalty_total), 4)
    return {
        "method": "rule-based-checklist",
        "case_id": "or-001-recurring-artifact-job",
        "raw_score": raw_total,
        "total_score": total,
        "passing_score": rubric["passing_score"],
        "passed": total >= rubric["passing_score"],
        "criteria": results,
        "penalties": penalties,
        "limitations": [
            "This is a heuristic evaluator.",
            "It checks presence of expected concepts but not full reasoning quality.",
        ],
    }


def evaluate_case(case_path: Path, response_path: Path) -> dict:
    case_payload = load_yaml(case_path / "case.yaml")
    rubric = load_yaml(case_path / "rubric.yaml")
    response_text = response_path.read_text(encoding="utf-8")
    case_id = case_payload["id"]

    if case_id == "or-001-recurring-artifact-job":
        return score_or_001(response_text, rubric)

    raise SystemExit(f"No evaluator is registered for case {case_id!r}.")


def main() -> int:
    args = build_parser().parse_args()
    case_path = args.case_path.resolve()
    response_path = args.response_path.resolve()
    evaluation = evaluate_case(case_path, response_path)
    evaluation["evaluator"] = {
        "name": args.evaluator_name,
        "kind": args.evaluator_kind,
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    payload = json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n"
    if args.output_path:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
