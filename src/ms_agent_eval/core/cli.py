from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .config import ConfigurationRepository, load_document
from .errors import AgentEvalError
from .evaluation import CaseDefinition, EvaluationService, validate_case_bank
from .evaluator_plugins import load_evaluator_registry
from .hashing import json_value
from .lifecycle import ExperimentRunRecord
from .legacy import LegacyArchiveExporter
from .models import SnapshotLock
from .planning import lock_as_dict, plan_experiment
from .snapshots import ExternalSnapshotStore, SnapshotBuilder
from .sources import GitHubSourceProvider
from .storage import FilesystemArtifactStore, SQLiteMetadataStore
from .reporting import ReportRecord, SummaryReporter


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ms-agent-eval",
        description="Plan and operate repository-neutral agent evaluation experiments.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config", help="Validate framework configuration.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser("validate", help="Validate all workspace documents.")
    validate.add_argument("--workspace", type=Path, required=True)

    target = commands.add_parser("target", help="Resolve and snapshot target repositories.")
    target_commands = target.add_subparsers(dest="target_command", required=True)
    resolve = target_commands.add_parser("resolve", help="Resolve a tag/commit to a commit.")
    resolve.add_argument("target_id")
    resolve.add_argument("--workspace", type=Path, required=True)
    snapshot = target_commands.add_parser(
        "snapshot", help="Create an immutable snapshot outside the workspace."
    )
    snapshot.add_argument("target_id")
    snapshot.add_argument("--workspace", type=Path, required=True)
    snapshot.add_argument("--data-root", type=Path)

    snapshots = commands.add_parser("snapshot", help="Verify immutable snapshots.")
    snapshot_commands = snapshots.add_subparsers(dest="snapshot_command", required=True)
    verify = snapshot_commands.add_parser("verify", help="Verify an external snapshot.")
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--data-root", type=Path, required=True)

    experiment = commands.add_parser("experiment", help="Manage immutable experiments.")
    experiment_commands = experiment.add_subparsers(dest="experiment_command", required=True)
    plan = experiment_commands.add_parser("plan", help="Expand an experiment matrix.")
    plan.add_argument("experiment_id")
    plan.add_argument("--workspace", type=Path, required=True)
    plan.add_argument("--output", type=Path)
    create = experiment_commands.add_parser(
        "create", help="Create an externally persisted experiment run."
    )
    create.add_argument("experiment_id")
    create.add_argument("--workspace", type=Path, required=True)
    create.add_argument("--data-root", type=Path)

    evaluator = commands.add_parser(
        "evaluator", help="Operate trusted experiment-owned evaluators."
    )
    evaluator_commands = evaluator.add_subparsers(
        dest="evaluator_command", required=True
    )
    evaluator_validate = evaluator_commands.add_parser(
        "validate", help="Validate a suite against a configured evaluator registry."
    )
    evaluator_validate.add_argument("evaluator_id")
    evaluator_validate.add_argument("--suite", dest="suite_id", required=True)
    evaluator_validate.add_argument("--workspace", type=Path, required=True)
    evaluator_score = evaluator_commands.add_parser(
        "score", help="Score one saved LLM response against an authored case."
    )
    evaluator_score.add_argument("evaluator_id")
    evaluator_score.add_argument("--suite", dest="suite_id", required=True)
    evaluator_score.add_argument("--case", dest="case_id", required=True)
    evaluator_score.add_argument("--response", type=Path, required=True)
    evaluator_score.add_argument("--workspace", type=Path, required=True)
    evaluator_score.add_argument("--allow-unscored", action="store_true")

    legacy = commands.add_parser("legacy", help="Export read-only legacy trees.")
    legacy_commands = legacy.add_subparsers(dest="legacy_command", required=True)
    legacy_export = legacy_commands.add_parser(
        "export", help="Copy a legacy tree into external content-addressed storage."
    )
    legacy_export.add_argument("--source", type=Path, required=True)
    legacy_export.add_argument("--source-label", required=True)
    legacy_export.add_argument("--namespace", required=True)
    legacy_export.add_argument("--workspace-root", type=Path, required=True)
    legacy_export.add_argument("--data-root", type=Path, required=True)

    report = commands.add_parser("report", help="Create identity-safe external reports.")
    report_commands = report.add_subparsers(dest="report_command", required=True)
    summary = report_commands.add_parser("summary")
    summary.add_argument("--records", type=Path, required=True)
    summary.add_argument("--report-id", required=True)
    summary.add_argument("--workspace-root", type=Path, required=True)
    summary.add_argument("--data-root", type=Path, required=True)
    regression = report_commands.add_parser("regression")
    regression.add_argument("--baseline", type=Path, required=True)
    regression.add_argument("--candidate", type=Path, required=True)
    regression.add_argument("--report-id", required=True)
    regression.add_argument("--workspace-root", type=Path, required=True)
    regression.add_argument("--data-root", type=Path, required=True)
    return parser


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _external_data_root(
    arguments: argparse.Namespace, repository: ConfigurationRepository
) -> Path:
    explicit = getattr(arguments, "data_root", None)
    if explicit is not None:
        return explicit
    variable = repository.workspace.external_data_root_env
    value = os.environ.get(variable)
    if not value:
        value = _workspace_dotenv_value(repository, variable)
    if not value:
        raise AgentEvalError(
            "external data root is required; pass --data-root, set "
            f"{variable}, or define it in {repository.workspace_root / '.env'}"
        )
    return Path(value)


def _workspace_dotenv_value(
    repository: ConfigurationRepository, variable: str
) -> str | None:
    dotenv = repository.workspace_root / ".env"
    if not dotenv.is_file():
        return None
    found: str | None = None
    for line_number, raw_line in enumerate(
        dotenv.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, raw_value = line.partition("=")
        if not separator or not key.strip():
            raise AgentEvalError(f"invalid .env entry at {dotenv}:{line_number}")
        if key.strip() != variable:
            continue
        if found is not None:
            raise AgentEvalError(f"duplicate {variable} entry in {dotenv}")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            raise AgentEvalError(f"{variable} must not be empty in {dotenv}")
        found = value
    return found


def _report_records(path: Path) -> tuple[ReportRecord, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = payload.get("records")
        else:
            rows = None
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if not isinstance(rows, list):
        raise AgentEvalError("report input must be a JSON list, JSONL, or {records: [...]} object")
    return tuple(ReportRecord.from_mapping(row) for row in rows)


def _run(arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.command == "legacy":
        workspace = arguments.workspace_root.resolve()
        source = arguments.source.resolve()
        if source != workspace and workspace not in source.parents:
            raise AgentEvalError("legacy source must be inside the selected workspace")
        artifacts = FilesystemArtifactStore(
            arguments.data_root, workspace_root=workspace
        )
        archive = LegacyArchiveExporter(artifacts).export_tree(
            source,
            source_label=arguments.source_label,
            namespace=arguments.namespace,
        )
        return json_value(archive)  # type: ignore[return-value]

    if arguments.command == "report":
        artifacts = FilesystemArtifactStore(
            arguments.data_root,
            workspace_root=arguments.workspace_root,
        )
        reporter = SummaryReporter()
        if arguments.report_command == "summary":
            payload = reporter.summarize(_report_records(arguments.records))
        else:
            payload = reporter.regression(
                _report_records(arguments.baseline),
                _report_records(arguments.candidate),
            )
        reference = artifacts.put_manifest(
            f"reports/{arguments.report_id}", payload
        )
        return {"report": payload, "artifact": json_value(reference)}

    if arguments.command == "snapshot":
        lock = SnapshotLock.from_mapping(load_document(arguments.lock))
        store = ExternalSnapshotStore(arguments.data_root)
        store.verify(lock)
        return {"status": "valid", "snapshot_id": lock.id, "content_hash": lock.content_hash}

    repository = ConfigurationRepository.from_file(arguments.workspace)
    if arguments.command == "config":
        return {
            "status": "valid",
            "workspace": repository.workspace.id,
            "documents": repository.validate_all(),
        }
    if arguments.command == "target":
        target = repository.target(arguments.target_id)
        provider = GitHubSourceProvider()
        if arguments.target_command == "resolve":
            return json_value(provider.resolve(target.source))  # type: ignore[return-value]
        store = ExternalSnapshotStore(
            _external_data_root(arguments, repository),
            workspace_root=repository.workspace_root,
        )
        lock = SnapshotBuilder(provider, store).create(target)
        return json_value(lock)  # type: ignore[return-value]
    if arguments.command == "evaluator":
        suite = repository.suite(arguments.suite_id)
        registry = load_evaluator_registry(repository, arguments.evaluator_id)
        if arguments.evaluator_command == "validate":
            suite_root = repository.path_for("suites", suite.id).parent
            return validate_case_bank(suite_root, registry)
        case_reference = next(
            (case for case in suite.cases if case.id == arguments.case_id), None
        )
        if case_reference is None:
            raise AgentEvalError(
                f"case {arguments.case_id!r} is not indexed by suite {suite.id!r}"
            )
        case_path = (repository.workspace_root / case_reference.path).resolve()
        if repository.workspace_root not in case_path.parents:
            raise AgentEvalError("suite case path escapes the experiment workspace")
        if not arguments.response.is_file():
            raise AgentEvalError(
                f"LLM response file does not exist: {arguments.response}"
            )
        response = arguments.response.read_text(encoding="utf-8")
        record = EvaluationService(registry).evaluate(
            CaseDefinition.load(case_path),
            response,
            allow_unscored=arguments.allow_unscored,
        )
        return json_value(record)  # type: ignore[return-value]
    lock = plan_experiment(repository, arguments.experiment_id)
    if arguments.experiment_command == "create":
        data_root = _external_data_root(arguments, repository)
        artifacts = FilesystemArtifactStore(
            data_root, workspace_root=repository.workspace_root
        )
        metadata = SQLiteMetadataStore(
            data_root / "metadata" / "ms-agent-eval.sqlite",
            workspace_root=repository.workspace_root,
        )
        run = ExperimentRunRecord.create(lock)
        lock_reference = artifacts.put_manifest(
            f"experiments/{run.id}/experiment.lock", lock_as_dict(lock)
        )
        metadata.create_experiment_run(run, lock)
        return {
            "run": json_value(run),
            "experiment_lock": json_value(lock_reference),
        }
    payload = lock_as_dict(lock)
    if arguments.output is not None:
        _atomic_json(arguments.output, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        payload = _run(arguments)
    except AgentEvalError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
