from __future__ import annotations

import pytest

from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.models import (
    ExperimentSpecification,
    SourceRef,
    SplitAssignment,
    SplitManifest,
    TargetSpecification,
)


def test_commit_ref_requires_full_lowercase_sha() -> None:
    with pytest.raises(ConfigurationError, match="full lowercase"):
        SourceRef.from_mapping({"type": "commit", "value": "ABC123"})


def test_target_paths_cannot_escape_repository() -> None:
    payload = {
        "schema_version": 1,
        "id": "unsafe",
        "source": {
            "type": "github",
            "repository_url": "https://github.com/example/unsafe",
            "ref": {"type": "tag", "value": "v1"},
        },
        "instruction_bundles": [
            {
                "id": "docs",
                "units": {
                    "sources": [
                        {
                            "id": "manuals",
                            "type": "explicit",
                            "entries": [{"id": "bad", "source_path": "../secret"}],
                        }
                    ]
                },
            }
        ],
    }
    with pytest.raises(ConfigurationError, match="repository-relative"):
        TargetSpecification.from_mapping(payload)


def test_split_manifest_rejects_group_leakage() -> None:
    assignments = (
        SplitAssignment("case-a", "same-family", "train"),
        SplitAssignment("case-b", "same-family", "test"),
    )
    with pytest.raises(ConfigurationError, match="leaks"):
        SplitManifest.create(id="leaky", assignments=assignments)


def test_benchmark_cannot_have_optimizer() -> None:
    payload = {
        "schema_version": 1,
        "id": "invalid",
        "kind": "benchmark",
        "matrix": {
            "targets": ["alpha"],
            "snapshots": ["alpha-v1"],
            "bundles": ["project-skills"],
            "suites": ["synthetic"],
            "compatibilities": ["alpha-v1--synthetic"],
            "programs": ["raw-control"],
            "providers": ["deterministic"],
            "runtimes": ["response-only"],
            "evaluators": ["synthetic-rules-v1"],
        },
        "storage": "local-external",
        "optimizer": "gepa-small",
    }
    with pytest.raises(ConfigurationError, match="cannot declare"):
        ExperimentSpecification.from_mapping(payload)
