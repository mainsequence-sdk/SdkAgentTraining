from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .errors import ConfigurationError, ResolutionError
from .evaluation import CaseDefinition
from .hashing import content_hash, sha256_file
from .models import (
    CompatibilityMapping,
    EvaluatorProfile,
    ExperimentSpecification,
    OptimizerProfile,
    ProgramSpecification,
    ProviderProfile,
    RuntimeProfile,
    SnapshotLock,
    SplitManifest,
    StorageProfile,
    SuiteSpecification,
    TargetSpecification,
    WorkspaceConfiguration,
)


DocumentKind = Literal[
    "compatibility",
    "targets",
    "snapshots",
    "splits",
    "suites",
    "programs",
    "providers",
    "runtimes",
    "evaluators",
    "optimizers",
    "storage",
    "plans",
]


def load_document(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise ResolutionError(f"Configuration document does not exist: {path}")
    try:
        if path.suffix == ".json":
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Invalid configuration syntax: {error}", path=path) from error
    if not isinstance(payload, Mapping):
        raise ConfigurationError("configuration document must contain a mapping", path=path)
    return {str(key): value for key, value in payload.items()}


def _load(path: Path, loader):  # type: ignore[no-untyped-def]
    try:
        return loader(load_document(path))
    except ConfigurationError as error:
        if error.path is not None:
            raise
        raise ConfigurationError(str(error), path=path) from error


@dataclass(frozen=True)
class ConfigurationRepository:
    workspace_file: Path
    workspace_root: Path
    workspace: WorkspaceConfiguration

    @classmethod
    def from_file(cls, workspace_file: Path) -> ConfigurationRepository:
        resolved = workspace_file.resolve()
        workspace = _load(resolved, WorkspaceConfiguration.from_mapping)
        return cls(resolved, resolved.parent, workspace)

    def root_for(self, kind: DocumentKind) -> Path:
        root_kind = "suites" if kind == "splits" else kind
        relative = self.workspace.roots[root_kind]
        candidate = (self.workspace_root / relative).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            raise ConfigurationError(f"workspace root {kind!r} escapes the configuration directory")
        return candidate

    def path_for(self, kind: DocumentKind, document_id: str) -> Path:
        matches = []
        for path in self._catalog_paths(kind):
            payload = load_document(path)
            if payload.get("id") == document_id:
                matches.append(path)
        if len(matches) > 1:
            raise ConfigurationError(
                f"duplicate {kind} document id {document_id!r}: {matches}"
            )
        if matches:
            return matches[0]
        suffix = ".json" if kind == "snapshots" else ".yaml"
        return self.root_for(kind) / f"{document_id}{suffix}"

    def _catalog_paths(self, kind: DocumentKind) -> tuple[Path, ...]:
        root = self.root_for(kind)
        if kind == "suites":
            patterns = ("*/suite.yaml", "*/suite.yml")
        elif kind == "splits":
            patterns = ("*/split.json", "*/split.yaml", "*/split.yml")
        elif kind == "evaluators":
            patterns = ("*/evaluator.yaml", "*/evaluator.yml")
        elif kind == "snapshots":
            patterns = ("*.json",)
        else:
            patterns = ("*.yaml", "*.yml")
        return tuple(sorted(path for pattern in patterns for path in root.glob(pattern)))

    def target(self, document_id: str) -> TargetSpecification:
        return _load(self.path_for("targets", document_id), TargetSpecification.from_mapping)

    def snapshot(self, document_id: str) -> SnapshotLock:
        return _load(self.path_for("snapshots", document_id), SnapshotLock.from_mapping)

    def suite(self, document_id: str) -> SuiteSpecification:
        return _load(self.path_for("suites", document_id), SuiteSpecification.from_mapping)

    def split(self, document_id: str) -> SplitManifest:
        return _load(self.path_for("splits", document_id), SplitManifest.from_mapping)

    def compatibility(self, document_id: str) -> CompatibilityMapping:
        return _load(
            self.path_for("compatibility", document_id), CompatibilityMapping.from_mapping
        )

    def program(self, document_id: str) -> ProgramSpecification:
        return _load(self.path_for("programs", document_id), ProgramSpecification.from_mapping)

    def provider(self, document_id: str) -> ProviderProfile:
        return _load(self.path_for("providers", document_id), ProviderProfile.from_mapping)

    def runtime(self, document_id: str) -> RuntimeProfile:
        return _load(self.path_for("runtimes", document_id), RuntimeProfile.from_mapping)

    def evaluator(self, document_id: str) -> EvaluatorProfile:
        path = self.path_for("evaluators", document_id)
        profile = _load(path, EvaluatorProfile.from_mapping)
        module_path = (self.workspace_root / profile.module_path).resolve()
        if module_path.parent != path.parent.resolve() or not module_path.is_file():
            raise ConfigurationError(
                "evaluator module_path must identify a file beside evaluator.yaml",
                path=path,
            )
        return profile

    def optimizer(self, document_id: str) -> OptimizerProfile:
        return _load(self.path_for("optimizers", document_id), OptimizerProfile.from_mapping)

    def storage(self, document_id: str) -> StorageProfile:
        path = self.path_for("storage", document_id)
        profile = _load(path, StorageProfile.from_mapping)
        if profile.data_root_env != self.workspace.external_data_root_env:
            raise ConfigurationError(
                "storage data-root variable must match workspace external_data_root_env",
                path=path,
            )
        return profile

    def experiment(self, document_id: str) -> ExperimentSpecification:
        return _load(self.path_for("plans", document_id), ExperimentSpecification.from_mapping)

    def document_hash(self, kind: DocumentKind, document_id: str) -> str:
        path = self.path_for(kind, document_id)
        if kind not in {"suites", "evaluators"}:
            return sha256_file(path)
        excluded = {"split.json", "split.yaml", "split.yml"} if kind == "suites" else set()
        files: dict[str, str] = {}
        for candidate in sorted(path.parent.rglob("*")):
            if candidate.is_symlink():
                raise ConfigurationError(
                    f"{kind} integrity tree must not contain symlinks", path=candidate
                )
            if candidate.is_file() and candidate.name not in excluded:
                files[candidate.relative_to(path.parent).as_posix()] = sha256_file(candidate)
        if not files:
            raise ConfigurationError(f"{kind} integrity tree is empty", path=path.parent)
        return content_hash(files)

    def document_hash_for_workspace(self) -> str:
        return sha256_file(self.workspace_file)

    def validate_all(self) -> dict[str, int]:
        loaders = {
            "compatibility": CompatibilityMapping.from_mapping,
            "targets": TargetSpecification.from_mapping,
            "snapshots": SnapshotLock.from_mapping,
            "splits": SplitManifest.from_mapping,
            "suites": SuiteSpecification.from_mapping,
            "programs": ProgramSpecification.from_mapping,
            "providers": ProviderProfile.from_mapping,
            "runtimes": RuntimeProfile.from_mapping,
            "evaluators": EvaluatorProfile.from_mapping,
            "optimizers": OptimizerProfile.from_mapping,
            "storage": StorageProfile.from_mapping,
            "plans": ExperimentSpecification.from_mapping,
        }
        counts: dict[str, int] = {}
        for kind, loader in loaders.items():
            root = self.root_for(kind)  # type: ignore[arg-type]
            if not root.is_dir():
                raise ConfigurationError(f"configured {kind} root does not exist: {root}")
            paths = self._catalog_paths(kind)  # type: ignore[arg-type]
            for path in paths:
                document = _load(path, loader)
                if kind not in {"suites", "splits", "evaluators"} and (
                    getattr(document, "id") != path.stem
                ):
                    raise ConfigurationError(
                        f"document id {getattr(document, 'id')!r} must match filename {path.stem!r}",
                        path=path,
                    )
                if kind == "evaluators":
                    module_path = (self.workspace_root / document.module_path).resolve()
                    if (
                        module_path.parent != path.parent.resolve()
                        or not module_path.is_file()
                    ):
                        raise ConfigurationError(
                            "evaluator module_path must identify a file beside evaluator.yaml",
                            path=path,
                        )
                if kind == "storage" and (
                    document.data_root_env != self.workspace.external_data_root_env
                ):
                    raise ConfigurationError(
                        "storage data-root variable must match workspace external_data_root_env",
                        path=path,
                    )
            counts[kind] = len(paths)
        for suite_path in self._catalog_paths("suites"):
            suite = _load(suite_path, SuiteSpecification.from_mapping)
            for case in suite.cases:
                case_path = (self.workspace_root / case.path).resolve()
                if self.workspace_root not in case_path.parents:
                    raise ConfigurationError(
                        f"suite case path escapes the workspace: {case.path}",
                        path=suite_path,
                    )
                loaded_case = CaseDefinition.load(case_path)
                if loaded_case.id != case.id:
                    raise ConfigurationError(
                        f"suite case id {case.id!r} differs from {loaded_case.id!r}",
                        path=suite_path,
                    )
                for required_file in ("prompt.md", "expected/response.md"):
                    if not (case_path / required_file).is_file():
                        raise ConfigurationError(
                            f"case {case.id!r} is missing {required_file}",
                            path=suite_path,
                        )
            if suite.split_manifest_id is None:
                continue
            split_path = self.path_for("splits", suite.split_manifest_id)
            if split_path.parent != suite_path.parent:
                raise ConfigurationError(
                    f"suite {suite.id!r} and split {suite.split_manifest_id!r} must be co-located"
                )
            split = _load(split_path, SplitManifest.from_mapping)
            if {case.id for case in suite.cases} != {
                assignment.case_id for assignment in split.assignments
            }:
                raise ConfigurationError(
                    f"split {split.id!r} must assign every case in suite {suite.id!r}"
                )
        return counts
