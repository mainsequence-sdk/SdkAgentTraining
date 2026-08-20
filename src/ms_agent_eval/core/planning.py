from __future__ import annotations

import itertools
from typing import cast

from .config import ConfigurationRepository
from .errors import ConfigurationError, ResolutionError
from .hashing import content_hash, json_value
from .models import ExperimentKind, ExperimentLock, PlannedJob


def plan_experiment(
    repository: ConfigurationRepository,
    experiment_id: str,
) -> ExperimentLock:
    experiment = repository.experiment(experiment_id)
    matrix = experiment.matrix

    targets = {item: repository.target(item) for item in matrix["targets"]}
    snapshots = {item: repository.snapshot(item) for item in matrix["snapshots"]}
    suites = {item: repository.suite(item) for item in matrix["suites"]}
    compatibilities = {
        item: repository.compatibility(item) for item in matrix["compatibilities"]
    }
    programs = {item: repository.program(item) for item in matrix["programs"]}
    providers = {item: repository.provider(item) for item in matrix["providers"]}
    runtimes = {item: repository.runtime(item) for item in matrix["runtimes"]}
    evaluators = {item: repository.evaluator(item) for item in matrix["evaluators"]}
    storage = repository.storage(experiment.storage)
    optimizer = repository.optimizer(experiment.optimizer) if experiment.optimizer else None

    if experiment.kind is ExperimentKind.OPTIMIZATION and optimizer is None:
        raise ConfigurationError("optimization planning requires an optimizer")
    if optimizer is not None and any(program.engine != optimizer.engine for program in programs.values()):
        raise ConfigurationError("every optimization program engine must match the optimizer engine")

    raw_jobs: list[dict[str, object]] = []
    product = itertools.product(*(matrix[axis] for axis in matrix))
    for values in product:
        selected = dict(zip(matrix, values, strict=True))
        target = targets[selected["targets"]]
        snapshot = snapshots[selected["snapshots"]]
        if snapshot.target_id != target.id:
            continue
        if snapshot.target_specification_hash != target.specification_hash:
            raise ResolutionError(
                f"snapshot {snapshot.id!r} was not created from target specification "
                f"{target.id!r}"
            )
        if snapshot.requested_ref != target.source.ref or (
            snapshot.repository_url.removesuffix(".git")
            != target.source.repository_url.removesuffix(".git")
        ):
            raise ResolutionError(
                f"snapshot {snapshot.id!r} source does not match target {target.id!r}"
            )
        if snapshot.extraction_configuration_hash != content_hash(
            target.instruction_bundles
        ):
            raise ResolutionError(
                f"snapshot {snapshot.id!r} extraction configuration is stale"
            )
        bundle_ids = {bundle.id for bundle in target.instruction_bundles}
        if selected["bundles"] not in bundle_ids:
            continue
        suite = suites[selected["suites"]]
        compatibility = compatibilities[selected["compatibilities"]]
        if compatibility.snapshot_id != snapshot.id or compatibility.suite_id != suite.id:
            continue
        if compatibility.suite_version != suite.version:
            raise ResolutionError(
                f"compatibility {compatibility.id!r} selects suite version "
                f"{compatibility.suite_version!r}, not {suite.version!r}"
            )
        if any(case.bundle_id not in bundle_ids for case in suite.cases):
            raise ResolutionError(
                f"suite {suite.id!r} contains a bundle unavailable on target {target.id!r}"
            )
        suite_cases = {case.id: case for case in suite.cases}
        compatibility_cases = {case.case_id: case for case in compatibility.cases}
        if suite_cases.keys() != compatibility_cases.keys():
            raise ResolutionError(
                f"compatibility {compatibility.id!r} must map every case in suite {suite.id!r}"
            )
        snapshot_units = {
            (unit.bundle_id, unit.unit_id): unit for unit in snapshot.units
        }
        for case_id, case in suite_cases.items():
            mapped = compatibility_cases[case_id]
            if (mapped.bundle_id, mapped.unit_id) != (case.bundle_id, case.unit_id):
                raise ResolutionError(
                    f"compatibility {compatibility.id!r} changes the locked unit for "
                    f"case {case_id!r}"
                )
            if (mapped.bundle_id, mapped.unit_id) not in snapshot_units:
                raise ResolutionError(
                    f"case {case_id!r} does not resolve to a locked instruction unit in "
                    f"snapshot {snapshot.id!r}"
                )
        split_manifest_id = suite.split_manifest_id
        if split_manifest_id is not None:
            split_manifest = repository.split(split_manifest_id)
            split_cases = {assignment.case_id for assignment in split_manifest.assignments}
            if split_cases != suite_cases.keys():
                raise ResolutionError(
                    f"split manifest {split_manifest.id!r} must assign every suite case exactly once"
                )
        for repetition in range(experiment.repetitions):
            raw_jobs.append(
                {
                    "target_id": target.id,
                    "snapshot_id": snapshot.id,
                    "bundle_id": selected["bundles"],
                    "suite_id": suite.id,
                    "compatibility_id": compatibility.id,
                    "split_manifest_id": split_manifest_id,
                    "program_id": programs[selected["programs"]].id,
                    "provider_id": providers[selected["providers"]].id,
                    "runtime_id": runtimes[selected["runtimes"]].id,
                    "evaluator_id": evaluators[selected["evaluators"]].id,
                    "repetition": repetition,
                }
            )
    if not raw_jobs:
        raise ResolutionError("experiment matrix did not produce any valid target/snapshot jobs")

    jobs: list[PlannedJob] = []
    for ordinal, job in enumerate(raw_jobs, start=1):
        jobs.append(PlannedJob.create(ordinal=ordinal, **job))  # type: ignore[arg-type]

    config_hashes = {
        "workspace": repository.document_hash_for_workspace(),
        "plan": repository.document_hash("plans", experiment.id),
        "storage": repository.document_hash("storage", storage.id),
    }
    for kind, selected_ids in (
        ("targets", targets),
        ("snapshots", snapshots),
        ("suites", suites),
        ("compatibility", compatibilities),
        ("programs", programs),
        ("providers", providers),
        ("runtimes", runtimes),
        ("evaluators", evaluators),
    ):
        for selected_id in selected_ids:
            config_hashes[f"{kind}:{selected_id}"] = repository.document_hash(kind, selected_id)  # type: ignore[arg-type]
    for suite in suites.values():
        if suite.split_manifest_id is not None:
            config_hashes[f"splits:{suite.split_manifest_id}"] = repository.document_hash(
                "splits", suite.split_manifest_id
            )
    if optimizer is not None:
        config_hashes[f"optimizers:{optimizer.id}"] = repository.document_hash(
            "optimizers", optimizer.id
        )

    return ExperimentLock.create(
        experiment_id=experiment.id,
        experiment_kind=experiment.kind,
        experiment_hash=experiment.specification_hash,
        storage_id=storage.id,
        optimizer_id=optimizer.id if optimizer else None,
        config_hashes=config_hashes,
        jobs=tuple(jobs),
    )


def lock_as_dict(lock: ExperimentLock) -> dict[str, object]:
    return cast(dict[str, object], json_value(lock))
