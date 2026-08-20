from __future__ import annotations

from pathlib import Path

from ms_agent_eval.core.config import ConfigurationRepository, load_document
from ms_agent_eval.core.hashing import sha256_file
from ms_agent_eval.core.models import SnapshotLock, TargetSpecification
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.hashing import canonical_json_bytes
from ms_agent_eval.programs.raw import render_messages
from ms_agent_eval.providers.ollama import build_chat_request


ROOT = Path(__file__).parents[1]
PACK = ROOT / "experiments" / "mainsequence-sdk"
LOCK_FILE = (
    PACK
    / "snapshots"
    / "mainsequence-sdk-3b5a20a344ce-dbeab527cb38.json"
)


def test_mainsequence_target_points_to_exact_public_tag_and_skill_root() -> None:
    target = TargetSpecification.from_mapping(
        load_document(PACK / "targets" / "mainsequence-sdk.yaml")
    )
    assert target.source.repository_url == "https://github.com/mainsequence-sdk/mainsequence-sdk"
    assert target.source.ref.value == "v4.4.5"
    bundle = target.instruction_bundles[0]
    assert [context.source_path for context in bundle.global_context] == [
        "agent_scaffold/AGENTS.md"
    ]
    source = bundle.unit_sources[0]
    assert source.root == "agent_scaffold/skills"
    assert source.exact_count == 20


def test_public_v445_lock_has_exact_expected_inventory() -> None:
    lock = SnapshotLock.from_mapping(load_document(LOCK_FILE))
    assert lock.resolved_commit == "3b5a20a344cec0c960351dc3c601d32a66a8b46e"
    assert lock.content_hash == (
        "sha256:fbb65b6b3e6fa1526be6be491acddf8129ebc82b7024635fa6c13c9d2886b221"
    )
    assert len(lock.units) == 20
    assert len(lock.files) == 21
    assert all(
        unit.source_path == f"agent_scaffold/skills/{unit.unit_id}/SKILL.md"
        for unit in lock.units
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_suites_are_the_only_committed_case_source() -> None:
    for version, expected_files in (("v1", 254), ("v2", 340)):
        suite_root = PACK / "suites" / version
        assert len(_tree_hashes(suite_root)) == expected_files
    assert len(_tree_hashes(PACK / "sources")) == 2


def test_repository_has_no_transitional_root_trees() -> None:
    obsolete = (
        "cases",
        "sdk",
        "runs",
        "reports",
        "spikes",
        "packages",
        "runtime-profiles",
        "experiment-packs",
    )
    assert [name for name in obsolete if (ROOT / name).exists()] == []


def test_mainsequence_workspace_has_only_canonical_experiment_layout() -> None:
    assert not (PACK / "splits").exists()
    assert not (PACK / "suites/training_sources").exists()
    assert not (PACK / "suites/mainsequence-agent-skills-v1.yaml").exists()
    assert not (PACK / "suites/mainsequence-agent-skills-v2.yaml").exists()
    for version in ("v1", "v2"):
        suite_root = PACK / "suites" / version
        assert (suite_root / "suite.yaml").is_file()
        assert (suite_root / "split.json").is_file()
        assert (suite_root / "units").is_dir()
        assert not (suite_root / "skills").exists()


def test_suite_compatibility_and_grouped_splits_resolve_exactly() -> None:
    repository = ConfigurationRepository.from_file(PACK / "workspace.yaml")
    assert repository.validate_all()["suites"] == 2
    assert repository.validate_all()["evaluators"] == 1
    snapshot = repository.snapshot("mainsequence-sdk-3b5a20a344ce-dbeab527cb38")
    locked_units = {(unit.bundle_id, unit.unit_id) for unit in snapshot.units}
    expected_counts = {"v1": 55, "v2": 74}
    for version, expected_count in expected_counts.items():
        suite_id = f"mainsequence-agent-skills-{version}"
        suite = repository.suite(suite_id)
        compatibility = repository.compatibility(f"{snapshot.id}--{suite_id}")
        split = repository.split(f"{suite_id}-split-v1")
        assert len(suite.cases) == expected_count
        assert {case.id for case in suite.cases} == {
            case.case_id for case in compatibility.cases
        } == {assignment.case_id for assignment in split.assignments}
        assert all(
            (case.bundle_id, case.unit_id) in locked_units
            for case in compatibility.cases
        )


def test_v2_split_keeps_every_instruction_unit_in_one_partition() -> None:
    repository = ConfigurationRepository.from_file(PACK / "workspace.yaml")
    suite = repository.suite("mainsequence-agent-skills-v2")
    split = repository.split("mainsequence-agent-skills-v2-split-v1")
    assignments = {item.case_id: item for item in split.assignments}
    per_unit: dict[str, set[tuple[str, str]]] = {}
    for case in suite.cases:
        assignment = assignments[case.id]
        per_unit.setdefault(case.unit_id, set()).add(
            (assignment.group_id, assignment.split)
        )
    assert all(len(values) == 1 for values in per_unit.values())
    counts: dict[str, int] = {}
    for assignment in split.assignments:
        counts[assignment.split] = counts.get(assignment.split, 0) + 1
    assert counts == {"development": 11, "test": 11, "train": 52}


def test_legacy_raw_program_reconstructs_historical_ollama_request_byte_for_byte() -> None:
    repository = ConfigurationRepository.from_file(PACK / "workspace.yaml")
    program = repository.program("raw-legacy-mainsequence")
    run_root = ROOT / "tests" / "fixtures" / "legacy-run-v0"
    output = (
        run_root
        / "skills/platform_operations/orchestration_and_releases/or-001-recurring-artifact-job"
    )
    system = (output / "system_prompt.md").read_text(encoding="utf-8")
    prefix = (
        "You are being evaluated on a Main Sequence skill.\n\n"
        "Use the provided project scaffold instructions and the skill instructions as "
        "authoritative context.\n\nProject scaffold instructions:\n"
    )
    global_context, instruction_context = system.removeprefix(prefix).split(
        "\n\nSkill instructions:\n", maxsplit=1
    )
    task = (output / "user_prompt.md").read_text(encoding="utf-8")
    messages = render_messages(
        program,
        ProgramInputs(global_context, instruction_context.removesuffix("\n"), task),
    )
    actual = build_chat_request(
        model="ms-fast:latest", messages=messages, parameters={"temperature": 0.2}
    )
    expected = load_document(
        run_root
        / "logs/platform_operations/orchestration_and_releases/or-001-recurring-artifact-job"
        / "ollama_request.json"
    )
    assert canonical_json_bytes(actual) == canonical_json_bytes(expected)
