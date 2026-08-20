from __future__ import annotations

from pathlib import Path

import pytest

from ms_agent_eval.core.errors import ConfigurationError, IntegrityError
from ms_agent_eval.core.legacy import LegacyArchiveExporter
from ms_agent_eval.core.reporting import ReportRecord, SummaryReporter, read_legacy_run
from ms_agent_eval.core.storage import FilesystemArtifactStore


ROOT = Path(__file__).parents[1]
LEGACY_RUN = ROOT / "tests" / "fixtures" / "legacy-run-v0"


def _record(**overrides: object) -> ReportRecord:
    payload: dict[str, object] = {
        "case_id": "case-001",
        "suite_id": "suite",
        "suite_version": "1",
        "target_id": "target",
        "source_commit": "a" * 40,
        "snapshot_id": "snapshot",
        "bundle_id": "bundle",
        "unit_id": "unit",
        "program_id": "program",
        "engine": "dspy",
        "module": "predict",
        "adapter": "chat",
        "compiled_artifact": "uncompiled",
        "dspy_version": "3.2.1",
        "optimizer_lock": None,
        "split_role": "development",
        "provider_id": "provider",
        "model": "model",
        "parameters_hash": "sha256:parameters",
        "evaluator_name": "target.exact-v1",
        "evaluator_version": "1",
        "status": "evaluated",
        "score": 1.0,
        "passed": True,
        "configured_cost": 0.1,
        "tokens": 10,
        "latency_seconds": 0.2,
    }
    payload.update(overrides)
    return ReportRecord.from_mapping(payload)


def test_legacy_export_preserves_paths_hashes_and_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "legacy-source"
    source.mkdir()
    first = source / "nested" / "one.txt"
    first.parent.mkdir()
    first.write_bytes(b"one\n")
    second = source / "two.bin"
    second.write_bytes(b"\x00\x01")
    before = {path: path.read_bytes() for path in (first, second)}
    store = FilesystemArtifactStore(tmp_path / "external")
    exporter = LegacyArchiveExporter(store)
    archive = exporter.export_tree(
        source, source_label="sdk", namespace="legacy-snapshots"
    )
    repeated = exporter.export_tree(
        source, source_label="sdk", namespace="legacy-snapshots"
    )
    assert archive.tree_hash == repeated.tree_hash
    assert archive.manifest_artifact == repeated.manifest_artifact
    assert [item.original_path for item in archive.files] == [
        "sdk/nested/one.txt",
        "sdk/two.bin",
    ]
    assert all(store.verify(item.artifact) for item in archive.files)
    assert {path: path.read_bytes() for path in (first, second)} == before


def test_legacy_export_refuses_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "legacy-source"
    source.mkdir()
    target = source / "target"
    target.write_text("value", encoding="utf-8")
    (source / "link").symlink_to(target)
    with pytest.raises(IntegrityError, match="symlink"):
        LegacyArchiveExporter(FilesystemArtifactStore(tmp_path / "external")).export_tree(
            source, source_label="runs", namespace="legacy-runs"
        )


def test_reporting_separates_split_revision_and_compiled_identity() -> None:
    records = (
        _record(),
        _record(case_id="case-002", split_role="test"),
        _record(
            case_id="case-003",
            source_commit="b" * 40,
            compiled_artifact="sha256:compiled",
        ),
    )
    report = SummaryReporter().summarize(records)
    assert report["record_count"] == 3
    assert len(report["groups"]) == 3  # type: ignore[arg-type]


def test_regression_requires_locked_axes_and_marks_negative_delta() -> None:
    reporter = SummaryReporter()
    report = reporter.regression(
        [_record(score=1.0)],
        [_record(score=0.5, compiled_artifact="sha256:candidate")],
    )
    assert report["regression_count"] == 1
    with pytest.raises(ConfigurationError, match="source_commit"):
        reporter.regression([_record()], [_record(source_commit="b" * 40)])


def test_legacy_run_is_readable_without_claiming_resolved_provenance() -> None:
    records = read_legacy_run(LEGACY_RUN)
    assert len(records) == 1
    assert records[0].case_id == "or-001-recurring-artifact-job"
    assert records[0].source_commit == "unresolved"
    assert records[0].score == 0.25
    report = SummaryReporter().summarize(records)
    assert report["warnings"] == ["legacy record has unresolved source revision"]
