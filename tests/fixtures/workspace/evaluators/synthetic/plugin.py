from ms_agent_eval.core.evaluation import EvaluatorRegistry


def build_registry(*, workspace_root, configuration):  # type: ignore[no-untyped-def]
    return EvaluatorRegistry()
