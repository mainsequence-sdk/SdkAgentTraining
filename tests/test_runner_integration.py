from __future__ import annotations

from pathlib import Path

import pytest

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.errors import PreflightError
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationService, EvaluatorRegistry
from ms_agent_eval.core.lifecycle import ExperimentRunRecord
from ms_agent_eval.core.models import ProgramSpecification, RunStatus
from ms_agent_eval.core.planning import plan_experiment
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.providers import ProviderResponse
from ms_agent_eval.core.runner import ExperimentRunner, JobExecution
from ms_agent_eval.core.storage import FilesystemArtifactStore, SQLiteMetadataStore
from ms_agent_eval.programs.raw import RawMessageEngine


FIXTURE = Path(__file__).parent / "fixtures" / "workspace" / "workspace.yaml"


class EchoProvider:
    id = "echo"
    model = "echo-v1"
    parameters = {"temperature": 0}
    configured_cost_per_call = 0.0

    def generate(self, messages):  # type: ignore[no-untyped-def]
        text = f"answer:{messages[-1]['content']}"
        return ProviderResponse(text, {"message": {"content": text}}, {})


class CountingProvider(EchoProvider):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().generate(messages)


def test_same_runner_executes_two_targets_without_target_branching(tmp_path: Path) -> None:
    repository = ConfigurationRepository.from_file(FIXTURE)
    lock = plan_experiment(repository, "two-targets")
    run = ExperimentRunRecord.create(lock)
    artifacts = FilesystemArtifactStore(tmp_path / "external")
    metadata = SQLiteMetadataStore(tmp_path / "external" / "metadata.sqlite3")
    metadata.create_experiment_run(run, lock)
    runner = ExperimentRunner(artifacts=artifacts, metadata=metadata)
    program = ProgramSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "runner-raw",
            "engine": "raw",
            "payload": {
                "system_template": "{global_context}\n{instruction_context}",
                "user_template": "{task}",
            },
        }
    )
    outputs = []
    for job in lock.jobs:
        result = runner.execute(
            run_id=run.id,
            execution=JobExecution(
                job,
                program,
                ProgramInputs(
                    f"global:{job.target_id}",
                    f"unit:{job.bundle_id}",
                    f"task:{job.target_id}",
                ),
            ),
            engine=RawMessageEngine(),
            provider=EchoProvider(),
        )
        outputs.append(result.primary_response)
    assert outputs == ["answer:task:alpha", "answer:task:beta"]
    states = metadata.load_job_states(run.id)
    assert {state.status for state in states.values()} == {RunStatus.COMPLETED}
    assert all(tuple(metadata.artifacts(run.id, job.id)) for job in lock.jobs)


def test_evaluator_preflight_prevents_provider_call_and_unscored_is_external(
    tmp_path: Path,
) -> None:
    repository = ConfigurationRepository.from_file(FIXTURE)
    lock = plan_experiment(repository, "two-targets")
    run = ExperimentRunRecord.create(lock)
    data_root = tmp_path / "external"
    artifacts = FilesystemArtifactStore(data_root)
    metadata = SQLiteMetadataStore(data_root / "metadata.sqlite3")
    metadata.create_experiment_run(run, lock)
    runner = ExperimentRunner(artifacts=artifacts, metadata=metadata)
    program = ProgramSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "runner-raw",
            "engine": "raw",
            "payload": {
                "system_template": "{global_context}\n{instruction_context}",
                "user_template": "{task}",
            },
        }
    )
    case_path = tmp_path / "case"
    case_path.mkdir()
    (case_path / "case.yaml").write_text(
        "id: synthetic-manual\n"
        "evaluator:\n"
        "  name: synthetic.manual-v1\n"
        "  method: human-review\n"
        "  status: manual_review_required\n",
        encoding="utf-8",
    )
    (case_path / "rubric.yaml").write_text(
        "passing_score: 1.0\ncriteria:\n"
        "  - id: correct\n"
        "    weight: 1.0\n"
        "    description: Correct.\n",
        encoding="utf-8",
    )
    provider = CountingProvider()
    job = lock.jobs[0]
    execution = JobExecution(job, program, ProgramInputs("global", "unit", "task"))
    service = EvaluationService(EvaluatorRegistry())
    case = CaseDefinition.load(case_path)

    with pytest.raises(PreflightError, match="no model request was sent"):
        runner.execute_evaluated(
            run_id=run.id,
            execution=execution,
            engine=RawMessageEngine(),
            provider=provider,
            case=case,
            evaluation_service=service,
        )
    assert provider.calls == 0
    assert metadata.load_job_states(run.id)[job.id].status is RunStatus.PLANNED

    result = runner.execute_evaluated(
        run_id=run.id,
        execution=execution,
        engine=RawMessageEngine(),
        provider=provider,
        case=case,
        evaluation_service=service,
        allow_unscored=True,
    )
    assert provider.calls == 1
    assert result.evaluation is not None and result.evaluation.score is None
    assert result.evaluation_artifact is not None
    assert artifacts.verify(result.evaluation_artifact)
