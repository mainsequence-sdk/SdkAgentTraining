from __future__ import annotations

import importlib.metadata
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = "platform_operations/orchestration_and_releases"
CASE_SET_VERSION = "v2"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def command_case(
    *,
    case_id: str,
    title: str,
    tags: list[str],
    question: str,
    command: str,
    explanation: str,
    success: list[str],
    docs: list[str],
    pitfalls: list[str],
    difficulty: str = "easy",
) -> dict:
    prompt = f"""You want to answer this operational question from the CLI:

"{question}"

Respond with:

1. the exact command you would run
2. one short sentence explaining why that command is the correct way to answer the question

Prefer a structured-output path rather than counting human-formatted table rows."""
    expected = f"""The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
{command}
```

Why:

{explanation}

Weak answers should be rejected if they:
{chr(10).join(f"- {item}" for item in pitfalls)}"""
    rubric = {
        "passing_score": 0.85,
        "criteria": [
            {
                "id": "command-surface",
                "weight": 0.45,
                "description": "Uses the correct documented CLI command family.",
            },
            {
                "id": "structured-output",
                "weight": 0.2,
                "description": "Uses `--json` or another explicitly structured output path.",
            },
            {
                "id": "transform-logic",
                "weight": 0.25,
                "description": "Applies the correct count, filter, or selection logic.",
            },
            {
                "id": "explanation",
                "weight": 0.1,
                "description": "Explains why the command answers the question.",
            },
        ],
        "notes": [
            "This case tests command selection and structured output handling.",
        ],
    }
    case = {
        "id": case_id,
        "title": title,
        "skill_path": SKILL_PATH,
        "case_set_version": CASE_SET_VERSION,
        "authored_against_sdk_version": sdk_version(),
        "tags": tags,
        "difficulty": difficulty,
        "requires": {"network": False, "auth": False, "writes_code": False},
        "success": success,
        "source_docs": docs,
    }
    return {
        "case": case,
        "prompt": prompt,
        "expected": expected,
        "rubric": rubric,
    }


def decision_case(
    *,
    case_id: str,
    title: str,
    tags: list[str],
    scenario: str,
    expected_points: list[str],
    docs: list[str],
    difficulty: str = "medium",
) -> dict:
    prompt = f"""You are answering an operational workflow question for the Main Sequence SDK.

Scenario:

{scenario}

Respond with:

1. the decision you would make
2. the exact file, command, or object you would use if relevant
3. one short sentence explaining why

Keep the answer grounded in documented Main Sequence behavior."""
    expected = "A strong answer should make these points explicit:\n\n" + "\n".join(
        f"- {point}" for point in expected_points
    )
    rubric = {
        "passing_score": 0.85,
        "criteria": [
            {
                "id": "decision",
                "weight": 0.4,
                "description": "Makes the correct operational decision.",
            },
            {
                "id": "sdk-grounding",
                "weight": 0.25,
                "description": "References the right documented file, command, or platform object.",
            },
            {
                "id": "safety",
                "weight": 0.2,
                "description": "Avoids unsafe or undocumented operational guidance.",
            },
            {
                "id": "explanation",
                "weight": 0.15,
                "description": "Explains why the decision is correct.",
            },
        ],
        "notes": [
            "This case tests documented operational decision-making, not live platform execution.",
        ],
    }
    case = {
        "id": case_id,
        "title": title,
        "skill_path": SKILL_PATH,
        "case_set_version": CASE_SET_VERSION,
        "authored_against_sdk_version": sdk_version(),
        "tags": tags,
        "difficulty": difficulty,
        "requires": {"network": False, "auth": False, "writes_code": False},
        "success": expected_points,
        "source_docs": docs,
    }
    return {
        "case": case,
        "prompt": prompt,
        "expected": expected,
        "rubric": rubric,
    }


def config_case(
    *,
    case_id: str,
    title: str,
    tags: list[str],
    request: str,
    snippet: str,
    key_points: list[str],
    docs: list[str],
    difficulty: str = "medium",
) -> dict:
    prompt = f"""You are answering a Main Sequence operational setup task.

Task:

{request}

Respond with:

1. the exact CLI command or YAML/Python snippet
2. one short sentence explaining why this is the correct structure

Keep the answer aligned with the latest documented SDK behavior."""
    expected = f"""A strong answer should include a snippet like this:

```text
{snippet}
```

It should also make these points explicit:
{chr(10).join(f"- {item}" for item in key_points)}"""
    rubric = {
        "passing_score": 0.85,
        "criteria": [
            {
                "id": "shape",
                "weight": 0.35,
                "description": "Uses the correct command or file shape.",
            },
            {
                "id": "required-fields",
                "weight": 0.3,
                "description": "Includes the required arguments or fields from the docs.",
            },
            {
                "id": "sdk-grounding",
                "weight": 0.2,
                "description": "Matches documented SDK/CLI behavior.",
            },
            {
                "id": "explanation",
                "weight": 0.15,
                "description": "Explains why the structure is correct.",
            },
        ],
        "notes": [
            "This case tests exact operational authoring rather than free-form explanation.",
        ],
    }
    case = {
        "id": case_id,
        "title": title,
        "skill_path": SKILL_PATH,
        "case_set_version": CASE_SET_VERSION,
        "authored_against_sdk_version": sdk_version(),
        "tags": tags,
        "difficulty": difficulty,
        "requires": {"network": False, "auth": False, "writes_code": False},
        "success": key_points,
        "source_docs": docs,
    }
    return {
        "case": case,
        "prompt": prompt,
        "expected": expected,
        "rubric": rubric,
    }


def sdk_version() -> str:
    return importlib.metadata.version("mainsequence")


def target_root() -> Path:
    return (
        REPO_ROOT
        / "cases"
        / CASE_SET_VERSION
        / "skills"
        / "platform_operations"
        / "orchestration_and_releases"
        / "cases"
    )


def build_cases() -> list[dict]:
    docs_cli = ["docs/cli/index.md", "docs/knowledge/cli.md"]
    docs_sched = ["docs/tutorial/scheduling_jobs.md", "docs/knowledge/infrastructure/scheduling_jobs.md"]
    docs_art = ["docs/tutorial/scheduling_jobs.md", "docs/knowledge/infrastructure/artifacts.md"]
    docs_resource = ["docs/cli/index.md", "docs/tutorial/create_your_first_api.md"]

    cases: list[dict] = [
        command_case(
            case_id="or-006-count-project-resources",
            title="Count project resources at the current upstream commit",
            tags=["cli", "resources", "counting", "json"],
            question="How many project resources are currently visible for this project at the current upstream commit?",
            command="mainsequence project project_resource list --json | jq 'length'",
            explanation="`project project_resource list` is the documented resource listing surface and `--json` lets you count the returned resource objects safely.",
            success=["Uses project_resource list", "Uses --json", "Counts returned resources"],
            docs=docs_resource,
            pitfalls=["count terminal rows", "use jobs or images commands instead of resources", "omit the counting step"],
        ),
        command_case(
            case_id="or-007-count-fastapi-resources",
            title="Count FastAPI project resources",
            tags=["cli", "resources", "fastapi", "counting", "json"],
            question="How many FastAPI resources does the current project expose at the current upstream commit?",
            command="mainsequence project project_resource list --filter resource_type=fastapi --json | jq 'length'",
            explanation="The documented project resource list command supports resource-type filters and `--json` makes the count deterministic.",
            success=["Uses project_resource list", "Filters resource_type=fastapi", "Counts structured output"],
            docs=docs_resource,
            pitfalls=["omit the resource_type filter", "count all resources", "count table rows"],
        ),
        command_case(
            case_id="or-008-count-dashboard-resources",
            title="Count dashboard project resources",
            tags=["cli", "resources", "dashboard", "counting", "json"],
            question="How many dashboard resources does the current project expose at the current upstream commit?",
            command="mainsequence project project_resource list --filter resource_type=dashboard --json | jq 'length'",
            explanation="Dashboard resources are exposed through the same project resource list surface, filtered by resource type.",
            success=["Uses project_resource list", "Filters resource_type=dashboard", "Counts structured output"],
            docs=docs_resource,
            pitfalls=["use release commands instead of resource listing", "omit the dashboard filter", "count rendered rows"],
        ),
        command_case(
            case_id="or-009-count-job-runs-for-job",
            title="Count total runs for a specific job",
            tags=["cli", "jobs", "runs", "counting", "json"],
            question="For job `91`, how many recorded runs are currently visible?",
            command="mainsequence project jobs runs list 91 --json | jq 'length'",
            explanation="`project jobs runs list 91` is the documented run-history surface for one job, and `--json` lets you count runs directly.",
            success=["Uses jobs runs list 91", "Uses --json", "Counts run objects"],
            docs=docs_sched,
            pitfalls=["use jobs list instead of runs list", "omit the job id", "count table rows"],
        ),
        command_case(
            case_id="or-010-count-pending-runs-for-job",
            title="Count pending runs for a specific job",
            tags=["cli", "jobs", "runs", "pending", "counting", "json"],
            question="For job `91`, how many runs are currently in `PENDING` state?",
            command="mainsequence project jobs runs list 91 --json | jq '[.[] | select(.status == \"PENDING\")] | length'",
            explanation="The documented runs list command returns job-run objects; filtering by `status == \"PENDING\"` answers the state-specific question.",
            success=["Uses jobs runs list 91", "Uses --json", "Filters for PENDING", "Counts filtered runs"],
            docs=docs_sched,
            pitfalls=["count all runs", "filter the wrong status", "use jobs list instead of runs list"],
            difficulty="medium",
        ),
        command_case(
            case_id="or-011-count-total-project-images",
            title="Count all project images",
            tags=["cli", "images", "counting", "json"],
            question="How many project images does the current project have in total?",
            command="mainsequence project images list --json | jq 'length'",
            explanation="`project images list` is the documented image inventory command, and `--json` makes the total count easy to compute.",
            success=["Uses project images list", "Uses --json", "Counts returned images"],
            docs=docs_sched,
            pitfalls=["count only ready images when total was asked", "use resource commands instead of image commands", "count terminal rows"],
        ),
        command_case(
            case_id="or-012-count-images-for-specific-commit",
            title="Count images for a specific repo hash",
            tags=["cli", "images", "filters", "counting", "json"],
            question="How many project images exist for repo hash `4a1b2c3d`?",
            command="mainsequence project images list --filter project_repo_hash__in=4a1b2c3d --json | jq 'length'",
            explanation="The images list command supports filters and `project_repo_hash__in` is the documented shape for narrowing results to a specific commit hash.",
            success=["Uses project images list", "Uses project_repo_hash__in filter", "Uses --json", "Counts returned images"],
            docs=docs_cli,
            pitfalls=["omit the filter", "use an unsupported ad hoc grep over table output", "count all images"],
            difficulty="medium",
        ),
        command_case(
            case_id="or-013-count-crontab-jobs",
            title="Count jobs that use crontab schedules",
            tags=["cli", "jobs", "schedules", "crontab", "counting", "json"],
            question="How many jobs in the current project use a `crontab` schedule?",
            command="mainsequence project jobs list --json | jq '[.[] | select(.task_schedule.type == \"crontab\")] | length'",
            explanation="The jobs list command returns structured schedule data; filtering `task_schedule.type` isolates crontab jobs.",
            success=["Uses project jobs list", "Uses --json", "Filters task_schedule.type == crontab", "Counts filtered jobs"],
            docs=docs_sched,
            pitfalls=["use runs instead of jobs", "count all jobs", "omit structured filtering"],
            difficulty="medium",
        ),
        command_case(
            case_id="or-014-count-manual-jobs",
            title="Count jobs with no schedule configured",
            tags=["cli", "jobs", "manual", "counting", "json"],
            question="How many jobs in the current project are manual only and do not have a schedule?",
            command="mainsequence project jobs list --json | jq '[.[] | select(.task_schedule == null)] | length'",
            explanation="Manual jobs show up in the jobs list without a schedule object, so the right structured check is `task_schedule == null`.",
            success=["Uses project jobs list", "Uses --json", "Checks for null task_schedule", "Counts filtered jobs"],
            docs=docs_sched,
            pitfalls=["use runs instead of jobs", "filter on an invented mode field", "count all jobs"],
            difficulty="medium",
        ),
        command_case(
            case_id="or-015-count-agent-resources",
            title="Count agent project resources",
            tags=["cli", "resources", "agent", "counting", "json"],
            question="How many agent resources does the current project expose at the current upstream commit?",
            command="mainsequence project project_resource list --filter resource_type=agent --json | jq 'length'",
            explanation="Agent resources are listed through the documented project resource surface and can be narrowed with the resource type filter.",
            success=["Uses project_resource list", "Filters resource_type=agent", "Counts structured output"],
            docs=docs_resource,
            pitfalls=["use agent runtime list instead of project resources", "omit the filter", "count rendered rows"],
            difficulty="medium",
        ),
        command_case(
            case_id="or-016-inspect-current-project-context",
            title="Inspect current project context before live operations",
            tags=["cli", "project", "verification", "context"],
            question="Which command should you run first to verify which Main Sequence project your current checkout is targeting?",
            command="mainsequence project current --debug",
            explanation="`project current --debug` is the documented command for confirming the active project and local context before live platform work.",
            success=["Uses project current --debug", "Chooses project-context verification before live operations"],
            docs=docs_cli,
            pitfalls=["use project list instead of current project resolution", "omit the command entirely", "propose guessing from local files only"],
        ),
        command_case(
            case_id="or-017-list-jobs-as-json",
            title="List project jobs in structured form",
            tags=["cli", "jobs", "json"],
            question="Which command should you run if you need the current project's jobs in structured JSON form for downstream scripting?",
            command="mainsequence project jobs list --json",
            explanation="`project jobs list --json` is the documented structured-output path for project jobs and is appropriate for downstream scripting.",
            success=["Uses project jobs list", "Uses --json"],
            docs=docs_cli,
            pitfalls=["omit --json", "use runs instead of jobs", "count terminal output"],
        ),
        command_case(
            case_id="or-018-stream-logs-for-run",
            title="Stream logs for one job run",
            tags=["cli", "jobs", "runs", "logs"],
            question="Which command should you run to inspect and stream logs for job run `501` while it may still be running?",
            command="mainsequence project jobs runs logs 501 --max-wait-seconds 900",
            explanation="`jobs runs logs` is the documented log-inspection command and `--max-wait-seconds 900` matches the standard long-poll verification flow in the docs.",
            success=["Uses jobs runs logs 501", "Includes max-wait-seconds for operational verification"],
            docs=docs_sched,
            pitfalls=["use runs list instead of logs", "inspect only job metadata", "invent a non-existent logs command"],
        ),
        command_case(
            case_id="or-019-trigger-manual-job-run",
            title="Trigger a manual run for one job",
            tags=["cli", "jobs", "run"],
            question="Which command should you run to trigger job `91` manually?",
            command="mainsequence project jobs run 91",
            explanation="`project jobs run` is the documented command for triggering a manual run for an existing job.",
            success=["Uses project jobs run 91"],
            docs=docs_sched,
            pitfalls=["create a new job instead of running the existing one", "use runs list instead of run", "invent a start command"],
        ),
        command_case(
            case_id="or-020-list-runs-for-job",
            title="List run history for one job",
            tags=["cli", "jobs", "runs", "json"],
            question="Which command should you run to inspect the run history for job `91` in structured form?",
            command="mainsequence project jobs runs list 91 --json",
            explanation="`jobs runs list` is the documented run-history surface, and `--json` makes the returned runs scriptable.",
            success=["Uses jobs runs list 91", "Uses --json"],
            docs=docs_sched,
            pitfalls=["use jobs list instead of runs list", "omit the job id", "inspect logs instead of run history"],
        ),
        command_case(
            case_id="or-021-list-project-resources",
            title="List current project resources",
            tags=["cli", "resources", "json"],
            question="Which command should you run to inspect the current project's resources in structured form?",
            command="mainsequence project project_resource list --json",
            explanation="`project project_resource list` is the documented project-resource surface and `--json` is the right path for structured inspection.",
            success=["Uses project project_resource list", "Uses --json"],
            docs=docs_resource,
            pitfalls=["use release creation commands instead of listing", "use images list instead of resources", "omit structured output"],
        ),
        command_case(
            case_id="or-022-show-supported-filters-project-resources",
            title="Inspect supported filters for project resources",
            tags=["cli", "resources", "filters"],
            question="Which command should you run if you want to inspect the filters supported by project resource listing before writing an automation around it?",
            command="mainsequence project project_resource list --show-filters",
            explanation="The documented `--show-filters` flag is the right way to inspect supported filters before automating around a list command.",
            success=["Uses project_resource list --show-filters"],
            docs=docs_cli,
            pitfalls=["guess filter names from memory", "use raw grep over help text", "list resources without inspecting filters"],
        ),
        command_case(
            case_id="or-023-show-supported-filters-project-images",
            title="Inspect supported filters for project images",
            tags=["cli", "images", "filters"],
            question="Which command should you run if you want to inspect the filters supported by project image listing before writing an automation around it?",
            command="mainsequence project images list --show-filters",
            explanation="The documented `--show-filters` flag is the right way to inspect supported image filters before automating against them.",
            success=["Uses project images list --show-filters"],
            docs=docs_cli,
            pitfalls=["guess image filter names from memory", "skip filter inspection", "use unrelated help output instead"],
        ),
        command_case(
            case_id="or-024-create-image-with-extended-wait",
            title="Create a project image with a longer wait window",
            tags=["cli", "images", "create", "polling"],
            question="Which command should you run if you want to create a project image and wait longer than the default while it becomes ready?",
            command="mainsequence project images create --timeout 600 --poll-interval 15",
            explanation="The documented image-create command supports `--timeout` and `--poll-interval` for longer readiness polling.",
            success=["Uses project images create", "Includes timeout", "Includes poll-interval"],
            docs=docs_sched,
            pitfalls=["invent a separate wait command", "omit image creation", "use unsupported flags"],
        ),
        config_case(
            case_id="or-025-create-manual-job-command",
            title="Author a manual job creation command",
            tags=["cli", "jobs", "manual", "authoring"],
            request='Write the exact CLI command to create a manual job named "Vendor Prices - Manual" that runs `scripts/vendor_prices_launcher.py` against image `77`.',
            snippet='mainsequence project jobs create --name "Vendor Prices - Manual" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77',
            key_points=["Uses `project jobs create`", "Uses `execution-path` relative to the repository root", "Includes `--related-image-id 77`"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-026-create-interval-job-command",
            title="Author an interval job creation command",
            tags=["cli", "jobs", "interval", "authoring"],
            request='Write the exact CLI command to create an hourly interval job named "Vendor Prices - Hourly" that runs `scripts/vendor_prices_launcher.py` against image `77`.',
            snippet='mainsequence project jobs create --name "Vendor Prices - Hourly" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type interval --schedule-every 1 --schedule-period hours',
            key_points=["Uses `project jobs create`", "Uses `--schedule-type interval`", "Uses `--schedule-every 1 --schedule-period hours`", "Includes `--related-image-id 77`"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-027-create-crontab-job-command",
            title="Author a crontab job creation command",
            tags=["cli", "jobs", "crontab", "authoring"],
            request='Write the exact CLI command to create a nightly job named "Vendor Prices - Nightly" that runs `scripts/vendor_prices_launcher.py` against image `77` on `0 0 * * *`.',
            snippet='mainsequence project jobs create --name "Vendor Prices - Nightly" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type crontab --schedule-expression "0 0 * * *"',
            key_points=["Uses `project jobs create`", "Uses `--schedule-type crontab`", "Uses the requested schedule expression", "Includes `--related-image-id 77`"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-028-create-one-off-job-command",
            title="Author a one-off scheduled job command",
            tags=["cli", "jobs", "one-off", "authoring"],
            request='Write the exact CLI command to create a one-time backfill job named "Vendor Prices - One Time" that runs `scripts/vendor_prices_launcher.py` against image `77` at `2026-03-15T02:00:00Z` using crontab expression `0 2 * * *`.',
            snippet='mainsequence project jobs create --name "Vendor Prices - One Time" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type crontab --schedule-expression "0 2 * * *" --schedule-start-time "2026-03-15T02:00:00Z" --schedule-one-off',
            key_points=["Uses the documented one-off flags", "Includes schedule start time", "Includes `--schedule-one-off`", "Includes `--related-image-id 77`"],
            docs=docs_sched,
            difficulty="hard",
        ),
        config_case(
            case_id="or-029-schedule-batch-jobs-command",
            title="Author the batch scheduling command",
            tags=["cli", "jobs", "batch", "authoring"],
            request='Write the exact CLI command to validate and submit the repository-root batch file `scheduled_jobs.yaml`.',
            snippet='mainsequence project schedule_batch_jobs scheduled_jobs.yaml',
            key_points=["Uses `schedule_batch_jobs`", "Targets `scheduled_jobs.yaml`", "Uses the batch scheduling surface rather than direct job creation"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-030-schedule-batch-jobs-strict-command",
            title="Author the strict batch scheduling command",
            tags=["cli", "jobs", "batch", "strict", "authoring"],
            request='Write the exact CLI command to submit `scheduled_jobs.yaml` in strict mode when the file is intentionally the full desired state.',
            snippet='mainsequence project schedule_batch_jobs scheduled_jobs.yaml --strict',
            key_points=["Uses `schedule_batch_jobs`", "Includes `--strict`", "Treats strict mode as intentional full-desired-state behavior"],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-031-choose-batch-vs-direct-job",
            title="Choose repository-managed batch scheduling over direct creation",
            tags=["decision", "jobs", "batch", "git"],
            scenario="A daily shared workflow is important to the team and should be reviewable in git. Decide whether to use `scheduled_jobs.yaml` plus batch scheduling or ad hoc direct `project jobs create` commands.",
            expected_points=[
                "Choose `scheduled_jobs.yaml` plus `mainsequence project schedule_batch_jobs`.",
                "Treat recurring shared jobs as code.",
                "Do not hide the schedule in ad hoc shell history.",
            ],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-032-choose-strict-or-not",
            title="Decide whether strict batch sync is appropriate",
            tags=["decision", "jobs", "batch", "strict", "safety"],
            scenario="A team wants to submit `scheduled_jobs.yaml`, but they have not confirmed that the file represents the full desired state of all remote jobs. Decide whether to use `--strict`.",
            expected_points=[
                "Do not use `--strict` casually.",
                "Only use strict mode when the batch file is intentionally the full desired state.",
                "Call out the risk that strict mode may remove jobs not present in the YAML file.",
            ],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-033-choose-artifact-vs-datanode",
            title="Choose Artifact instead of DataNode for file drops",
            tags=["decision", "artifacts", "files", "datanodes"],
            scenario="A vendor drops a raw CSV file every day and the immediate operational need is to store and retrieve that file reliably before later normalization. Decide whether the first-class primitive should be an `Artifact` or a `DataNode`.",
            expected_points=[
                "Choose `Artifact` for the raw file workflow.",
                "Explain that the operational unit is a file rather than a structured table.",
                "Avoid forcing the workflow into a table primitive too early.",
            ],
            docs=docs_art,
        ),
        decision_case(
            case_id="or-034-choose-pinned-image-policy",
            title="Require pinned images for managed jobs",
            tags=["decision", "images", "reproducibility", "jobs"],
            scenario="A team wants reproducible managed jobs that keep running the same code even after the repository changes. Decide whether jobs should be pinned to a project image.",
            expected_points=[
                "Require a pinned project image through `related_image_id`.",
                "Tie reproducibility to the project image rather than moving repository state.",
                "Treat unpinned jobs as an unacceptable default in a managed project.",
            ],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-035-decide-what-to-verify-after-job-creation",
            title="Define post-creation verification for jobs",
            tags=["decision", "verification", "jobs", "logs"],
            scenario="A teammate says creating the job is enough and no further checks are needed. Decide whether that is acceptable and what must be verified instead.",
            expected_points=[
                "Reject stopping at creation.",
                "Verify that the job exists.",
                "Inspect runs and logs when execution success matters.",
            ],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-036-decide-if-unpushed-commit-can-build-image",
            title="Decide whether an unpushed commit can be turned into an image",
            tags=["decision", "images", "git", "reproducibility"],
            scenario="A developer wants to create a project image from a local commit that has not been pushed to the remote yet. Decide whether that is supported.",
            expected_points=[
                "Reject the idea that an unpushed commit can be used.",
                "State that project images are built from pushed commits.",
                "Require pushing first before image creation.",
            ],
            docs=docs_sched,
        ),
        decision_case(
            case_id="or-037-decide-if-local-file-path-is-acceptable",
            title="Reject fragile local file paths in operational workflows",
            tags=["decision", "artifacts", "files", "safety"],
            scenario="A workflow currently depends on `/tmp/vendor_drop.csv` on one engineer's laptop. Decide whether that is an acceptable long-term operational reference.",
            expected_points=[
                "Reject a laptop-specific local path as the durable operational reference.",
                "Use an `Artifact` as the stable platform identity for the file.",
                "Explain that the workflow should no longer depend on one machine.",
            ],
            docs=docs_art,
        ),
        decision_case(
            case_id="or-038-decide-if-deployed-dashboard-needs-resource-release",
            title="Require resource and release for deployed dashboard behavior",
            tags=["decision", "resources", "releases", "dashboard"],
            scenario="A developer says the local dashboard file exists in the repo, so deployment is finished. Decide whether that is sufficient for a deployed dashboard.",
            expected_points=[
                "Reject the idea that the local file alone is sufficient.",
                "Require a project resource and a release for deployed behavior.",
                "Tie the release to the intended image or resource version.",
            ],
            docs=["docs/tutorial/dashboards/streamlit/streamlit_integration_2.md", "docs/cli/index.md"],
        ),
        decision_case(
            case_id="or-039-decide-if-resource-must-match-image-commit",
            title="Require resource commit alignment with selected image",
            tags=["decision", "resources", "releases", "images"],
            scenario="A teammate wants to create a FastAPI release from a project resource that comes from a different commit than the selected project image. Decide whether that is acceptable.",
            expected_points=[
                "Reject selecting a resource that does not match the selected image commit.",
                "State that eligible resources must have `repo_commit_sha == related_image.project_repo_hash`.",
                "Treat image/resource commit alignment as a release requirement.",
            ],
            docs=docs_resource,
            difficulty="hard",
        ),
        decision_case(
            case_id="or-040-decide-if-recurring-job-should-live-in-git",
            title="Treat recurring schedules as code",
            tags=["decision", "jobs", "git", "schedules"],
            scenario="A nightly workflow is important to the team and should survive personnel changes. Decide whether the schedule should live in version control.",
            expected_points=[
                "Put the recurring schedule in `scheduled_jobs.yaml`.",
                "Treat the file as reviewable code in the repository.",
                "Avoid hiding the schedule in one-off commands or shell history.",
            ],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-041-write-daily-scheduled-jobs-yaml",
            title="Author a daily scheduled_jobs.yaml entry",
            tags=["yaml", "jobs", "batch", "daily", "authoring"],
            request='Write one `scheduled_jobs.yaml` entry for a daily midnight job named "Simulated Prices" that runs `scripts/simulated_prices_launcher.py` against image `77`.',
            snippet='jobs:\n  - name: "Simulated Prices"\n    execution_path: "scripts/simulated_prices_launcher.py"\n    task_schedule:\n      type: "crontab"\n      expression: "0 0 * * *"\n    related_image_id: 77\n    cpu_request: "0.25"\n    memory_request: "0.5"',
            key_points=["Uses a top-level `jobs` list", "Uses `execution_path`", "Uses `task_schedule` with `type` and `expression`", "Includes `related_image_id`", "Includes valid compute fields"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-042-write-weekday-scheduled-jobs-yaml",
            title="Author a weekday scheduled_jobs.yaml entry",
            tags=["yaml", "jobs", "batch", "weekday", "authoring"],
            request='Write one `scheduled_jobs.yaml` entry for a weekday 06:00 UTC job named "Vendor Prices" that runs `scripts/vendor_prices_launcher.py` against image `77`.',
            snippet='jobs:\n  - name: "Vendor Prices"\n    execution_path: "scripts/vendor_prices_launcher.py"\n    task_schedule:\n      type: "crontab"\n      expression: "0 6 * * 1-5"\n    related_image_id: 77\n    cpu_request: "0.25"\n    memory_request: "0.5"',
            key_points=["Uses a top-level `jobs` list", "Uses a weekday crontab expression", "Includes `related_image_id`", "Keeps execution_path relative to the repo root"],
            docs=docs_sched,
        ),
        config_case(
            case_id="or-043-write-two-job-batch-yaml",
            title="Author a two-job batch file shape",
            tags=["yaml", "jobs", "batch", "authoring"],
            request='Write the shape of a `scheduled_jobs.yaml` file that contains two jobs, both to be scheduled through the batch flow and later pinned to the same selected image by the CLI.',
            snippet='jobs:\n  - name: "Job A"\n    execution_path: "scripts/job_a.py"\n    task_schedule:\n      type: "crontab"\n      expression: "0 0 * * *"\n    related_image_id: 77\n  - name: "Job B"\n    execution_path: "scripts/job_b.py"\n    task_schedule:\n      type: "interval"\n      every: 1\n      period: "hours"\n    related_image_id: 77',
            key_points=["Uses one top-level `jobs` list", "Defines each job separately", "Uses valid schedule objects", "Keeps both jobs eligible for one shared selected image in batch flow"],
            docs=docs_sched,
            difficulty="hard",
        ),
        config_case(
            case_id="or-044-write-fastapi-release-command",
            title="Author the FastAPI release command",
            tags=["cli", "resources", "releases", "fastapi", "authoring"],
            request='Write the CLI command family used to create a FastAPI release from a project resource when you already know `--resource-id 42` and `--related-image-id 77`.',
            snippet='mainsequence project project_resource create_fastapi --resource-id 42 --related-image-id 77',
            key_points=["Uses `project project_resource create_fastapi`", "Includes a resource id", "Includes a related image id"],
            docs=docs_resource,
        ),
        config_case(
            case_id="or-045-write-dashboard-release-command",
            title="Author the dashboard release command",
            tags=["cli", "resources", "releases", "dashboard", "authoring"],
            request='Write the CLI command family used to create a dashboard release from a project resource when you already know `--resource-id 42` and `--related-image-id 77`.',
            snippet='mainsequence project project_resource create_dashboard --resource-id 42 --related-image-id 77',
            key_points=["Uses `project project_resource create_dashboard`", "Includes a resource id", "Includes a related image id"],
            docs=["docs/tutorial/dashboards/streamlit/streamlit_integration_2.md", "docs/cli/index.md"],
        ),
        config_case(
            case_id="or-046-write-agent-release-command",
            title="Author the agent release command",
            tags=["cli", "resources", "releases", "agent", "authoring"],
            request='Write the CLI command family used to create an agent release from a project resource when you already know `--resource-id 42` and `--related-image-id 77`.',
            snippet='mainsequence project project_resource create_agent --resource-id 42 --related-image-id 77',
            key_points=["Uses `project project_resource create_agent`", "Includes a resource id", "Includes a related image id"],
            docs=["docs/cli/index.md", "mainsequence/cli/cli.py"],
        ),
        config_case(
            case_id="or-047-write-delete-fastapi-release-command",
            title="Author the FastAPI release delete command",
            tags=["cli", "resources", "releases", "fastapi", "delete", "authoring"],
            request='Write the exact CLI command to delete FastAPI release `701` without confirmation.',
            snippet='mainsequence project project_resource delete_fastapi 701 --yes',
            key_points=["Uses `delete_fastapi`", "Includes the release id", "Includes `--yes` to skip confirmation"],
            docs=docs_resource,
        ),
        config_case(
            case_id="or-048-write-delete-dashboard-release-command",
            title="Author the dashboard release delete command",
            tags=["cli", "resources", "releases", "dashboard", "delete", "authoring"],
            request='Write the exact CLI command to delete dashboard release `501` without confirmation.',
            snippet='mainsequence project project_resource delete_dashboard 501 --yes',
            key_points=["Uses `delete_dashboard`", "Includes the release id", "Includes `--yes` to skip confirmation"],
            docs=["docs/tutorial/dashboards/streamlit/streamlit_integration_2.md", "mainsequence/cli/cli.py"],
        ),
        config_case(
            case_id="or-049-write-artifact-upload-snippet",
            title="Author an Artifact upload snippet",
            tags=["python", "artifacts", "upload", "authoring"],
            request='Write a minimal Python snippet that uploads `vendor_prices_2026_03_15.csv` as an Artifact in bucket `vendor_prices` created by resource `vendor-upload-job`.',
            snippet='from mainsequence.client import Artifact\n\nartifact = Artifact.upload_file(\n    filepath="vendor_prices_2026_03_15.csv",\n    name="vendor_prices_2026_03_15.csv",\n    bucket_name="vendor_prices",\n    created_by_resource_name="vendor-upload-job",\n)',
            key_points=["Uses `Artifact.upload_file()`", "Includes `filepath`", "Includes `name`", "Includes `bucket_name`", "Includes `created_by_resource_name`"],
            docs=docs_art,
        ),
        config_case(
            case_id="or-050-write-artifact-get-snippet",
            title="Author an Artifact retrieval snippet",
            tags=["python", "artifacts", "read", "authoring"],
            request='Write a minimal Python snippet that retrieves Artifact `vendor_prices_2026_03_15.csv` from bucket `vendor_prices` and loads it with pandas.',
            snippet='import pandas as pd\nfrom mainsequence.client import Artifact\n\nsource_artifact = Artifact.get(\n    bucket__name="vendor_prices",\n    name="vendor_prices_2026_03_15.csv",\n)\n\ndf = pd.read_csv(source_artifact.content)',
            key_points=["Uses `Artifact.get()`", "Identifies the bucket and artifact name", "Reads from `source_artifact.content`", "Shows pandas loading from the Artifact handle"],
            docs=docs_art,
        ),
    ]
    return cases


def main() -> int:
    root = target_root()
    root.mkdir(parents=True, exist_ok=True)

    for definition in build_cases():
        case_id = definition["case"]["id"]
        case_root = root / case_id
        write_yaml(case_root / "case.yaml", definition["case"])
        write_text(case_root / "prompt.md", definition["prompt"])
        write_text(case_root / "expected" / "response.md", definition["expected"])
        write_yaml(case_root / "rubric.yaml", definition["rubric"])

    print(f"Generated {len(build_cases())} orchestration cases under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
