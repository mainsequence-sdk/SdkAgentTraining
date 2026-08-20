from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType

from .config import ConfigurationRepository
from .errors import ConfigurationError, IntegrityError
from .evaluation import EvaluatorRegistry
from .models import EvaluatorProfile


EvaluatorFactory = Callable[..., EvaluatorRegistry]


def load_evaluator_module(
    workspace_root: Path, profile: EvaluatorProfile
) -> ModuleType:
    """Load explicitly trusted evaluator code from an experiment workspace."""

    workspace = workspace_root.resolve()
    module_path = (workspace / profile.module_path).resolve()
    if workspace not in module_path.parents or not module_path.is_file():
        raise ConfigurationError(
            "evaluator module_path must identify a file inside the workspace"
        )
    module_name = (
        "_ms_agent_eval_workspace_"
        + hashlib.sha256(str(module_path).encode("utf-8")).hexdigest()[:16]
    )
    module = ModuleType(module_name)
    module.__file__ = str(module_path)
    module.__package__ = ""
    try:
        source = module_path.read_bytes()
        exec(compile(source, str(module_path), "exec"), module.__dict__)
    except Exception as error:
        raise ConfigurationError(
            f"failed to load evaluator module {profile.module_path}: {type(error).__name__}"
        ) from error
    return module


def load_evaluator_registry(
    repository: ConfigurationRepository, evaluator_id: str
) -> EvaluatorRegistry:
    profile = repository.evaluator(evaluator_id)
    module = load_evaluator_module(repository.workspace_root, profile)
    factory = getattr(module, profile.factory, None)
    if not callable(factory):
        raise ConfigurationError(
            f"evaluator factory {profile.factory!r} is not callable in {profile.module_path}"
        )
    registry = factory(
        workspace_root=repository.workspace_root,
        configuration=profile.configuration,
    )
    if not isinstance(registry, EvaluatorRegistry):
        raise IntegrityError("evaluator factory must return EvaluatorRegistry")
    return registry


def resolve_workspace_path(
    workspace_root: Path, configuration: Mapping[str, object], key: str
) -> Path:
    value = configuration.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"evaluator configuration {key!r} must be a path")
    workspace = workspace_root.resolve()
    path = (workspace / value).resolve()
    if workspace not in path.parents:
        raise ConfigurationError(
            f"evaluator configuration path {key!r} escapes the workspace"
        )
    return path
