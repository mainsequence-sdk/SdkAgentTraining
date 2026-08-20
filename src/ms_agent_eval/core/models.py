from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal
from urllib.parse import urlparse

from .errors import ConfigurationError
from .hashing import content_hash


SCHEMA_VERSION = 1
PLANNER_VERSION = "0.1.0"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_TAG_PATTERN = re.compile(r"^(?!-)(?!.*(?:\.\.|@\{|//))[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _schema(payload: Mapping[str, object]) -> int:
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ConfigurationError(
            f"schema_version must be {SCHEMA_VERSION}, received {version!r}"
        )
    return SCHEMA_VERSION


def _identifier(value: object, field_name: str = "id") -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise ConfigurationError(
            f"{field_name} must match {_ID_PATTERN.pattern!r}, received {value!r}"
        )
    return value


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field_name} must be a non-empty string")
    return value


def _strings(value: object, field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ConfigurationError(f"{field_name} must be a list of strings")
    result = tuple(_string(item, field_name) for item in value)
    if not allow_empty and not result:
        raise ConfigurationError(f"{field_name} must not be empty")
    if len(set(result)) != len(result):
        raise ConfigurationError(f"{field_name} must not contain duplicates")
    return result


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{field_name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _frozen_mapping(value: object, field_name: str) -> Mapping[str, object]:
    return MappingProxyType(dict(_mapping(value, field_name)))


def _repository_path(value: object, field_name: str) -> str:
    text = _string(value, field_name).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or "\x00" in text or ":" in path.parts[0]:
        raise ConfigurationError(f"{field_name} must be a safe repository-relative POSIX path")
    normalized = path.as_posix()
    if normalized in ("", "."):
        raise ConfigurationError(f"{field_name} must identify a repository path")
    return normalized


class ExperimentKind(str, Enum):
    BENCHMARK = "benchmark"
    OPTIMIZATION = "optimization"


class SourceRefKind(str, Enum):
    TAG = "tag"
    COMMIT = "commit"


class RunStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


class EvaluationStatus(str, Enum):
    EVALUATED = "evaluated"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    NOT_EVALUABLE = "not_evaluable"
    EVALUATOR_ERROR = "evaluator_error"


@dataclass(frozen=True)
class SourceRef:
    type: SourceRefKind
    value: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SourceRef:
        try:
            kind = SourceRefKind(payload.get("type"))
        except ValueError as error:
            raise ConfigurationError("source ref type must be 'tag' or 'commit'") from error
        value = _string(payload.get("value"), "source.ref.value")
        if kind is SourceRefKind.COMMIT and not _COMMIT_PATTERN.fullmatch(value):
            raise ConfigurationError("commit refs must be full lowercase 40-character SHA values")
        if kind is SourceRefKind.TAG and (
            not _TAG_PATTERN.fullmatch(value)
            or value.endswith(("/", "."))
            or value.endswith(".lock")
        ):
            raise ConfigurationError("tag ref contains unsafe or invalid Git ref characters")
        return cls(kind, value)


@dataclass(frozen=True)
class GitSource:
    repository_url: str
    ref: SourceRef
    submodules: bool = False
    git_lfs: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> GitSource:
        if payload.get("type") != "github":
            raise ConfigurationError("the initial source type must be 'github'")
        repository_url = _string(payload.get("repository_url"), "source.repository_url")
        parsed = urlparse(repository_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError("repository_url must be an HTTPS github.com repository URL")
        repository_parts = [part for part in PurePosixPath(parsed.path).parts if part != "/"]
        if len(repository_parts) != 2 or not all(
            re.fullmatch(r"[A-Za-z0-9_.-]+", part.removesuffix(".git"))
            for part in repository_parts
        ):
            raise ConfigurationError("repository_url must identify one GitHub owner/repository")
        fetch = _mapping(payload.get("fetch", {}), "source.fetch")
        return cls(
            repository_url=repository_url.rstrip("/"),
            ref=SourceRef.from_mapping(_mapping(payload.get("ref"), "source.ref")),
            submodules=bool(fetch.get("submodules", False)),
            git_lfs=bool(fetch.get("git_lfs", False)),
        )


@dataclass(frozen=True)
class ContextFileSpecification:
    id: str
    source_path: str
    required: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ContextFileSpecification:
        return cls(
            _identifier(payload.get("id"), "global_context.id"),
            _repository_path(payload.get("source_path"), "global_context.source_path"),
            bool(payload.get("required", True)),
        )


@dataclass(frozen=True)
class ExplicitUnitEntry:
    id: str
    source_path: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ExplicitUnitEntry:
        return cls(
            _string(payload.get("id"), "unit entry id"),
            _repository_path(payload.get("source_path"), "unit entry source_path"),
        )


@dataclass(frozen=True)
class UnitSourceSpecification:
    id: str
    type: Literal["directory", "explicit"]
    root: str | None
    filename: str | None
    recursive: bool
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    follow_symlinks: bool
    id_prefix: str
    allow_empty: bool
    exact_count: int | None
    required_ids: tuple[str, ...]
    entries: tuple[ExplicitUnitEntry, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> UnitSourceSpecification:
        source_type = payload.get("type")
        if source_type not in ("directory", "explicit"):
            raise ConfigurationError("unit source type must be 'directory' or 'explicit'")
        logical_id = _mapping(payload.get("logical_id", {}), "units.logical_id")
        prefix = str(logical_id.get("prefix", ""))
        if prefix.startswith("/") or ".." in PurePosixPath(prefix).parts:
            raise ConfigurationError("logical id prefix must be relative and traversal-free")
        if source_type == "directory":
            locator = _mapping(payload.get("locator"), "units.locator")
            filename = _string(locator.get("filename"), "units.locator.filename")
            if "/" in filename or "\\" in filename:
                raise ConfigurationError("locator filename must be a basename")
            include = _strings(locator.get("include", [f"**/{filename}"]), "locator.include")
            exclude = _strings(locator.get("exclude", []), "locator.exclude", allow_empty=True)
            entries: tuple[ExplicitUnitEntry, ...] = ()
            root = _repository_path(payload.get("root"), "units.root")
        else:
            raw_entries = payload.get("entries")
            if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
                raise ConfigurationError("explicit unit source entries must be a list")
            entries = tuple(
                ExplicitUnitEntry.from_mapping(_mapping(item, "units.entries[]"))
                for item in raw_entries
            )
            if not entries:
                raise ConfigurationError("explicit unit source entries must not be empty")
            root = None
            filename = None
            include = ()
            exclude = ()
        assertions = _mapping(payload.get("assertions", {}), "units.assertions")
        exact_count = assertions.get("exact_count")
        if exact_count is not None and (
            not isinstance(exact_count, int) or exact_count < 0
        ):
            raise ConfigurationError("units.assertions.exact_count must be non-negative")
        required_ids = _strings(
            assertions.get("required_ids", []),
            "units.assertions.required_ids",
            allow_empty=True,
        )
        return cls(
            id=_identifier(payload.get("id"), "unit source id"),
            type=source_type,
            root=root,
            filename=filename,
            recursive=bool(
                _mapping(payload.get("locator", {}), "units.locator").get("recursive", True)
            ),
            include=include,
            exclude=exclude,
            follow_symlinks=bool(
                _mapping(payload.get("locator", {}), "units.locator").get(
                    "follow_symlinks", False
                )
            ),
            id_prefix=prefix,
            allow_empty=bool(payload.get("allow_empty", False)),
            exact_count=exact_count,
            required_ids=required_ids,
            entries=entries,
        )


@dataclass(frozen=True)
class InstructionBundleSpecification:
    id: str
    display_name: str
    global_context: tuple[ContextFileSpecification, ...]
    unit_sources: tuple[UnitSourceSpecification, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> InstructionBundleSpecification:
        raw_context = payload.get("global_context", [])
        raw_sources = _mapping(payload.get("units"), "bundle.units").get("sources")
        if not isinstance(raw_context, Sequence) or isinstance(raw_context, (str, bytes)):
            raise ConfigurationError("global_context must be a list")
        if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
            raise ConfigurationError("units.sources must be a list")
        contexts = tuple(
            ContextFileSpecification.from_mapping(_mapping(item, "global_context[]"))
            for item in raw_context
        )
        sources = tuple(
            UnitSourceSpecification.from_mapping(_mapping(item, "units.sources[]"))
            for item in raw_sources
        )
        if not sources:
            raise ConfigurationError("an instruction bundle requires at least one unit source")
        ids = [source.id for source in sources]
        if len(set(ids)) != len(ids):
            raise ConfigurationError("unit source ids must be unique within a bundle")
        return cls(
            _identifier(payload.get("id"), "bundle id"),
            _string(payload.get("display_name", payload.get("id")), "bundle display_name"),
            contexts,
            sources,
        )


@dataclass(frozen=True)
class TargetSpecification:
    schema_version: int
    id: str
    display_name: str
    source: GitSource
    instruction_bundles: tuple[InstructionBundleSpecification, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TargetSpecification:
        raw_bundles = payload.get("instruction_bundles")
        if not isinstance(raw_bundles, Sequence) or isinstance(raw_bundles, (str, bytes)):
            raise ConfigurationError("instruction_bundles must be a list")
        bundles = tuple(
            InstructionBundleSpecification.from_mapping(_mapping(item, "instruction_bundles[]"))
            for item in raw_bundles
        )
        if not bundles:
            raise ConfigurationError("a target requires at least one instruction bundle")
        ids = [bundle.id for bundle in bundles]
        if len(ids) != len(set(ids)):
            raise ConfigurationError("bundle ids must be unique within a target")
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            _string(payload.get("display_name", payload.get("id")), "display_name"),
            GitSource.from_mapping(_mapping(payload.get("source"), "source")),
            bundles,
        )

    @property
    def specification_hash(self) -> str:
        return content_hash(self)


@dataclass(frozen=True)
class LockedFile:
    source_path: str
    snapshot_path: str
    content_hash: str
    size_bytes: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> LockedFile:
        size = payload.get("size_bytes")
        if not isinstance(size, int) or size < 0:
            raise ConfigurationError("locked file size_bytes must be a non-negative integer")
        return cls(
            _repository_path(payload.get("source_path"), "locked file source_path"),
            _repository_path(payload.get("snapshot_path"), "locked file snapshot_path"),
            _string(payload.get("content_hash"), "locked file content_hash"),
            size,
        )


@dataclass(frozen=True)
class LockedInstructionUnit:
    bundle_id: str
    source_id: str
    unit_id: str
    source_path: str
    snapshot_path: str
    content_hash: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> LockedInstructionUnit:
        return cls(
            _identifier(payload.get("bundle_id"), "unit bundle_id"),
            _identifier(payload.get("source_id"), "unit source_id"),
            _string(payload.get("unit_id"), "unit_id"),
            _repository_path(payload.get("source_path"), "unit source_path"),
            _repository_path(payload.get("snapshot_path"), "unit snapshot_path"),
            _string(payload.get("content_hash"), "unit content_hash"),
        )


@dataclass(frozen=True)
class SnapshotLock:
    schema_version: int
    id: str
    target_id: str
    repository_url: str
    requested_ref: SourceRef
    resolved_commit: str
    target_specification_hash: str
    extraction_configuration_hash: str
    inventory_hash: str
    files: tuple[LockedFile, ...]
    units: tuple[LockedInstructionUnit, ...]
    content_hash: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SnapshotLock:
        raw_files = payload.get("files", [])
        raw_units = payload.get("units", [])
        if not isinstance(raw_files, Sequence) or isinstance(raw_files, (str, bytes)):
            raise ConfigurationError("snapshot files must be a list")
        if not isinstance(raw_units, Sequence) or isinstance(raw_units, (str, bytes)):
            raise ConfigurationError("snapshot units must be a list")
        lock = cls.create(
            id=_identifier(payload.get("id")),
            target_id=_identifier(payload.get("target_id"), "snapshot target_id"),
            repository_url=_string(payload.get("repository_url"), "snapshot repository_url"),
            requested_ref=SourceRef.from_mapping(
                _mapping(payload.get("requested_ref"), "snapshot requested_ref")
            ),
            resolved_commit=_string(payload.get("resolved_commit"), "snapshot resolved_commit"),
            target_specification_hash=_string(
                payload.get("target_specification_hash"), "snapshot target_specification_hash"
            ),
            extraction_configuration_hash=_string(
                payload.get("extraction_configuration_hash"),
                "snapshot extraction_configuration_hash",
            ),
            files=tuple(
                LockedFile.from_mapping(_mapping(item, "snapshot files[]"))
                for item in raw_files
            ),
            units=tuple(
                LockedInstructionUnit.from_mapping(_mapping(item, "snapshot units[]"))
                for item in raw_units
            ),
        )
        declared = _string(payload.get("content_hash"), "snapshot content_hash")
        declared_inventory = _string(
            payload.get("inventory_hash"), "snapshot inventory_hash"
        )
        if declared_inventory != lock.inventory_hash:
            raise ConfigurationError(
                "snapshot inventory hash mismatch: "
                f"declared {declared_inventory!r}, computed {lock.inventory_hash!r}"
            )
        if declared != lock.content_hash:
            raise ConfigurationError(
                f"snapshot content hash mismatch: declared {declared!r}, computed {lock.content_hash!r}"
            )
        return lock

    @classmethod
    def create(
        cls,
        *,
        id: str,
        target_id: str,
        repository_url: str,
        requested_ref: SourceRef,
        resolved_commit: str,
        target_specification_hash: str,
        extraction_configuration_hash: str,
        files: Sequence[LockedFile],
        units: Sequence[LockedInstructionUnit],
    ) -> SnapshotLock:
        if not _COMMIT_PATTERN.fullmatch(resolved_commit):
            raise ConfigurationError("resolved_commit must be a full lowercase commit SHA")
        inventory_hash = content_hash({"files": tuple(files), "units": tuple(units)})
        identity = {
            "schema_version": SCHEMA_VERSION,
            "id": _identifier(id),
            "target_id": _identifier(target_id),
            "repository_url": repository_url,
            "requested_ref": requested_ref,
            "resolved_commit": resolved_commit,
            "target_specification_hash": _string(
                target_specification_hash, "target_specification_hash"
            ),
            "extraction_configuration_hash": _string(
                extraction_configuration_hash, "extraction_configuration_hash"
            ),
            "inventory_hash": inventory_hash,
            "files": tuple(files),
            "units": tuple(units),
        }
        return cls(**identity, content_hash=content_hash(identity))


SplitName = Literal["train", "development", "test", "challenge"]


@dataclass(frozen=True)
class SplitAssignment:
    case_id: str
    group_id: str
    split: SplitName


@dataclass(frozen=True)
class SplitManifest:
    schema_version: int
    id: str
    assignments: tuple[SplitAssignment, ...]
    content_hash: str

    @classmethod
    def create(cls, *, id: str, assignments: Sequence[SplitAssignment]) -> SplitManifest:
        if not assignments:
            raise ConfigurationError("split manifest must not be empty")
        case_ids = [assignment.case_id for assignment in assignments]
        if len(case_ids) != len(set(case_ids)):
            raise ConfigurationError("split manifest case ids must be unique")
        group_owner: dict[str, SplitName] = {}
        for assignment in assignments:
            previous = group_owner.setdefault(assignment.group_id, assignment.split)
            if previous != assignment.split:
                raise ConfigurationError(
                    f"group {assignment.group_id!r} leaks across {previous!r} and {assignment.split!r}"
                )
        identity = {
            "schema_version": SCHEMA_VERSION,
            "id": _identifier(id),
            "assignments": tuple(assignments),
        }
        return cls(**identity, content_hash=content_hash(identity))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SplitManifest:
        _schema(payload)
        raw_assignments = payload.get("assignments")
        if not isinstance(raw_assignments, Sequence) or isinstance(
            raw_assignments, (str, bytes)
        ):
            raise ConfigurationError("split assignments must be a list")
        assignments: list[SplitAssignment] = []
        for item in raw_assignments:
            assignment = _mapping(item, "split assignments[]")
            split = assignment.get("split")
            if split not in ("train", "development", "test", "challenge"):
                raise ConfigurationError(f"invalid split name {split!r}")
            assignments.append(
                SplitAssignment(
                    case_id=_identifier(assignment.get("case_id"), "split case_id"),
                    group_id=_identifier(assignment.get("group_id"), "split group_id"),
                    split=split,
                )
            )
        manifest = cls.create(id=_identifier(payload.get("id")), assignments=assignments)
        declared = _string(payload.get("content_hash"), "split content_hash")
        if declared != manifest.content_hash:
            raise ConfigurationError(
                f"split content hash mismatch: declared {declared!r}, "
                f"computed {manifest.content_hash!r}"
            )
        return manifest


@dataclass(frozen=True)
class CaseReference:
    id: str
    bundle_id: str
    unit_id: str
    path: str


@dataclass(frozen=True)
class SuiteSpecification:
    schema_version: int
    id: str
    version: str
    cases: tuple[CaseReference, ...]
    split_manifest_id: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SuiteSpecification:
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes)):
            raise ConfigurationError("suite cases must be a list")
        cases = tuple(
            CaseReference(
                id=_identifier(_mapping(item, "suite cases[]").get("id"), "case id"),
                bundle_id=_identifier(
                    _mapping(item, "suite cases[]").get("bundle_id"), "case bundle_id"
                ),
                unit_id=_string(
                    _mapping(item, "suite cases[]").get("unit_id"), "case unit_id"
                ),
                path=_repository_path(
                    _mapping(item, "suite cases[]").get("path"), "case path"
                ),
            )
            for item in raw_cases
        )
        if not cases:
            raise ConfigurationError("suite cases must not be empty")
        ids = [case.id for case in cases]
        if len(ids) != len(set(ids)):
            raise ConfigurationError("suite case ids must be unique")
        split_id = payload.get("split_manifest_id")
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            _string(payload.get("version"), "suite version"),
            cases,
            _identifier(split_id, "split_manifest_id") if split_id else None,
        )


@dataclass(frozen=True)
class CompatibilityCase:
    case_id: str
    bundle_id: str
    unit_id: str


@dataclass(frozen=True)
class CompatibilityMapping:
    schema_version: int
    id: str
    snapshot_id: str
    suite_id: str
    suite_version: str
    cases: tuple[CompatibilityCase, ...]
    content_hash: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CompatibilityMapping:
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes)):
            raise ConfigurationError("compatibility cases must be a list")
        cases: list[CompatibilityCase] = []
        for item in raw_cases:
            case = _mapping(item, "compatibility cases[]")
            cases.append(
                CompatibilityCase(
                    case_id=_identifier(case.get("case_id"), "compatibility case_id"),
                    bundle_id=_identifier(case.get("bundle_id"), "compatibility bundle_id"),
                    unit_id=_string(case.get("unit_id"), "compatibility unit_id"),
                )
            )
        if not cases:
            raise ConfigurationError("compatibility cases must not be empty")
        case_ids = [case.case_id for case in cases]
        if len(case_ids) != len(set(case_ids)):
            raise ConfigurationError("compatibility case ids must be unique")
        identity = {
            "schema_version": _schema(payload),
            "id": _identifier(payload.get("id")),
            "snapshot_id": _identifier(payload.get("snapshot_id"), "snapshot_id"),
            "suite_id": _identifier(payload.get("suite_id"), "suite_id"),
            "suite_version": _string(payload.get("suite_version"), "suite_version"),
            "cases": tuple(cases),
        }
        mapping = cls(**identity, content_hash=content_hash(identity))
        declared = _string(payload.get("content_hash"), "compatibility content_hash")
        if declared != mapping.content_hash:
            raise ConfigurationError(
                f"compatibility content hash mismatch: declared {declared!r}, "
                f"computed {mapping.content_hash!r}"
            )
        return mapping


@dataclass(frozen=True)
class ProgramSpecification:
    schema_version: int
    id: str
    engine: str
    payload: Mapping[str, object]
    content_hash: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ProgramSpecification:
        identity = {
            "schema_version": _schema(payload),
            "id": _identifier(payload.get("id")),
            "engine": _identifier(payload.get("engine"), "engine"),
            "payload": dict(_mapping(payload.get("payload", {}), "program.payload")),
        }
        return cls(**identity, content_hash=content_hash(identity))


@dataclass(frozen=True)
class CompiledProgramManifest:
    schema_version: int
    id: str
    base_program_hash: str
    engine_version: str
    optimizer_lock_hash: str
    state_artifact: str
    state_format: Literal["json"]
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        id: str,
        base_program_hash: str,
        engine_version: str,
        optimizer_lock_hash: str,
        state_artifact: str,
    ) -> CompiledProgramManifest:
        identity = {
            "schema_version": SCHEMA_VERSION,
            "id": _identifier(id),
            "base_program_hash": _string(base_program_hash, "base_program_hash"),
            "engine_version": _string(engine_version, "engine_version"),
            "optimizer_lock_hash": _string(optimizer_lock_hash, "optimizer_lock_hash"),
            "state_artifact": _string(state_artifact, "state_artifact"),
            "state_format": "json",
        }
        return cls(**identity, content_hash=content_hash(identity))


@dataclass(frozen=True)
class RuntimeProfile:
    schema_version: int
    id: str
    backend: Literal["none", "docker"]
    python: str
    image: str | None
    network: Literal["none", "restricted", "full"]
    cpus: float
    memory_mb: int
    pids: int
    timeout_seconds: int
    maximum_output_bytes: int
    user: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> RuntimeProfile:
        backend = payload.get("backend")
        network = payload.get("network", "none")
        if backend not in ("none", "docker"):
            raise ConfigurationError("runtime backend must be 'none' or 'docker'")
        if network not in ("none", "restricted", "full"):
            raise ConfigurationError("runtime network must be none, restricted, or full")
        image = payload.get("image")
        if backend == "docker" and not isinstance(image, str):
            raise ConfigurationError("docker runtime profiles require an image")
        if backend == "docker" and not re.fullmatch(
            r"[^\s]+@sha256:[0-9a-f]{64}", image or ""
        ):
            raise ConfigurationError("docker runtime images must be pinned by SHA-256 digest")
        resources = _mapping(payload.get("resources", {}), "runtime.resources")
        cpus = resources.get("cpus", 1.0)
        memory_mb = resources.get("memory_mb", 1024)
        pids = resources.get("pids", 128)
        timeout_seconds = resources.get("timeout_seconds", 900)
        maximum_output_bytes = resources.get("maximum_output_bytes", 104857600)
        if not isinstance(cpus, (int, float)) or isinstance(cpus, bool) or cpus <= 0:
            raise ConfigurationError("runtime cpus must be a positive number")
        for name, value in {
            "memory_mb": memory_mb,
            "pids": pids,
            "timeout_seconds": timeout_seconds,
            "maximum_output_bytes": maximum_output_bytes,
        }.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigurationError(f"runtime {name} must be a positive integer")
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            backend,
            _string(payload.get("python", "3.12"), "runtime.python"),
            str(image) if image is not None else None,
            network,
            float(cpus),
            memory_mb,
            pids,
            timeout_seconds,
            maximum_output_bytes,
            _string(payload.get("user", "10001:10001"), "runtime.user"),
        )


@dataclass(frozen=True)
class ProviderProfile:
    schema_version: int
    id: str
    driver: str
    model: str
    parameters: Mapping[str, object]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ProviderProfile:
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            _identifier(payload.get("driver"), "provider.driver"),
            _string(payload.get("model"), "provider.model"),
            _frozen_mapping(payload.get("parameters", {}), "provider.parameters"),
        )


@dataclass(frozen=True)
class EvaluatorProfile:
    schema_version: int
    id: str
    module_path: str
    factory: str
    configuration: Mapping[str, object]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> EvaluatorProfile:
        module_path = _repository_path(
            payload.get("module_path"), "evaluator.module_path"
        )
        if not module_path.endswith(".py"):
            raise ConfigurationError("evaluator.module_path must identify a Python file")
        factory = _string(payload.get("factory"), "evaluator.factory")
        if not factory.isidentifier():
            raise ConfigurationError("evaluator.factory must be a Python identifier")
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            module_path,
            factory,
            _frozen_mapping(
                payload.get("configuration", {}), "evaluator.configuration"
            ),
        )


@dataclass(frozen=True)
class OptimizerProfile:
    schema_version: int
    id: str
    engine: str
    optimizer: str
    parameters: Mapping[str, object]
    budgets: Mapping[str, object]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> OptimizerProfile:
        budgets = _mapping(payload.get("budgets"), "optimizer.budgets")
        required_budgets = {
            "model_calls",
            "configured_cost",
            "tokens",
            "wall_seconds",
            "concurrency",
        }
        missing = sorted(required_budgets - set(budgets))
        if missing:
            raise ConfigurationError(f"optimizer budgets missing fields: {missing}")
        for field_name in ("model_calls", "tokens", "concurrency"):
            value = budgets[field_name]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigurationError(
                    f"optimizer budget {field_name} must be a positive integer"
                )
        for field_name in ("configured_cost", "wall_seconds"):
            value = budgets[field_name]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or float(value) <= 0
            ):
                raise ConfigurationError(
                    f"optimizer budget {field_name} must be a positive number"
                )
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            _identifier(payload.get("engine"), "optimizer.engine"),
            _string(payload.get("optimizer"), "optimizer.optimizer"),
            _frozen_mapping(payload.get("parameters", {}), "optimizer.parameters"),
            MappingProxyType(dict(budgets)),
        )


@dataclass(frozen=True)
class StorageProfile:
    schema_version: int
    id: str
    artifact_uri: str
    metadata_uri: str
    data_root_env: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> StorageProfile:
        artifact_uri = _string(payload.get("artifact_uri"), "storage.artifact_uri")
        metadata_uri = _string(payload.get("metadata_uri"), "storage.metadata_uri")
        artifact_match = re.fullmatch(
            r"file://\$\{([A-Z][A-Z0-9_]*)\}/.+", artifact_uri
        )
        metadata_match = re.fullmatch(
            r"sqlite:///\$\{([A-Z][A-Z0-9_]*)\}/.+", metadata_uri
        )
        if artifact_match is None:
            raise ConfigurationError(
                "artifact_uri must be file://${ENVIRONMENT_VARIABLE}/path"
            )
        if metadata_match is None:
            raise ConfigurationError(
                "metadata_uri must be sqlite:///${ENVIRONMENT_VARIABLE}/path"
            )
        if artifact_match.group(1) != metadata_match.group(1):
            raise ConfigurationError(
                "storage artifact_uri and metadata_uri must use the same data-root variable"
            )
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            artifact_uri,
            metadata_uri,
            artifact_match.group(1),
        )


_MATRIX_AXES = (
    "targets",
    "snapshots",
    "bundles",
    "suites",
    "compatibilities",
    "programs",
    "providers",
    "runtimes",
    "evaluators",
)


@dataclass(frozen=True)
class ExperimentSpecification:
    schema_version: int
    id: str
    kind: ExperimentKind
    matrix: Mapping[str, tuple[str, ...]]
    storage: str
    optimizer: str | None
    repetitions: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ExperimentSpecification:
        try:
            kind = ExperimentKind(payload.get("kind"))
        except ValueError as error:
            raise ConfigurationError("experiment kind must be benchmark or optimization") from error
        matrix_payload = _mapping(payload.get("matrix"), "experiment.matrix")
        unknown = sorted(set(matrix_payload) - set(_MATRIX_AXES))
        missing = sorted(set(_MATRIX_AXES) - set(matrix_payload))
        if unknown or missing:
            raise ConfigurationError(f"invalid matrix axes; missing={missing}, unknown={unknown}")
        matrix = MappingProxyType(
            {axis: _strings(matrix_payload[axis], f"matrix.{axis}") for axis in _MATRIX_AXES}
        )
        optimizer = payload.get("optimizer")
        if kind is ExperimentKind.OPTIMIZATION and not isinstance(optimizer, str):
            raise ConfigurationError("optimization experiments require an optimizer profile id")
        if kind is ExperimentKind.BENCHMARK and optimizer is not None:
            raise ConfigurationError("benchmark experiments cannot declare an optimizer")
        repetitions = payload.get("repetitions", 1)
        if not isinstance(repetitions, int) or repetitions < 1:
            raise ConfigurationError("repetitions must be a positive integer")
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            kind,
            matrix,
            _identifier(payload.get("storage"), "storage profile id"),
            _identifier(optimizer, "optimizer profile id") if optimizer else None,
            repetitions,
        )

    @property
    def specification_hash(self) -> str:
        return content_hash(self)


@dataclass(frozen=True)
class PlannedJob:
    id: str
    ordinal: int
    target_id: str
    snapshot_id: str
    bundle_id: str
    suite_id: str
    compatibility_id: str
    split_manifest_id: str | None
    program_id: str
    provider_id: str
    runtime_id: str
    evaluator_id: str
    repetition: int
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        ordinal: int,
        target_id: str,
        snapshot_id: str,
        bundle_id: str,
        suite_id: str,
        compatibility_id: str,
        split_manifest_id: str | None,
        program_id: str,
        provider_id: str,
        runtime_id: str,
        evaluator_id: str,
        repetition: int,
    ) -> PlannedJob:
        identity = {
            "target_id": _identifier(target_id, "job target_id"),
            "snapshot_id": _identifier(snapshot_id, "job snapshot_id"),
            "bundle_id": _identifier(bundle_id, "job bundle_id"),
            "suite_id": _identifier(suite_id, "job suite_id"),
            "compatibility_id": _identifier(
                compatibility_id, "job compatibility_id"
            ),
            "split_manifest_id": (
                _identifier(split_manifest_id, "job split_manifest_id")
                if split_manifest_id
                else None
            ),
            "program_id": _identifier(program_id, "job program_id"),
            "provider_id": _identifier(provider_id, "job provider_id"),
            "runtime_id": _identifier(runtime_id, "job runtime_id"),
            "evaluator_id": _identifier(evaluator_id, "job evaluator_id"),
            "repetition": repetition,
        }
        if not isinstance(ordinal, int) or ordinal < 1:
            raise ConfigurationError("job ordinal must be a positive integer")
        if not isinstance(repetition, int) or repetition < 0:
            raise ConfigurationError("job repetition must be a non-negative integer")
        job_hash = content_hash(identity)
        return cls(
            id=f"job-{ordinal:06d}-{job_hash.removeprefix('sha256:')[:12]}",
            ordinal=ordinal,
            content_hash=job_hash,
            **identity,
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PlannedJob:
        job = cls.create(
            ordinal=payload.get("ordinal"),  # type: ignore[arg-type]
            target_id=payload.get("target_id"),  # type: ignore[arg-type]
            snapshot_id=payload.get("snapshot_id"),  # type: ignore[arg-type]
            bundle_id=payload.get("bundle_id"),  # type: ignore[arg-type]
            suite_id=payload.get("suite_id"),  # type: ignore[arg-type]
            compatibility_id=payload.get("compatibility_id"),  # type: ignore[arg-type]
            split_manifest_id=payload.get("split_manifest_id"),  # type: ignore[arg-type]
            program_id=payload.get("program_id"),  # type: ignore[arg-type]
            provider_id=payload.get("provider_id"),  # type: ignore[arg-type]
            runtime_id=payload.get("runtime_id"),  # type: ignore[arg-type]
            evaluator_id=payload.get("evaluator_id"),  # type: ignore[arg-type]
            repetition=payload.get("repetition"),  # type: ignore[arg-type]
        )
        if payload.get("id") != job.id or payload.get("content_hash") != job.content_hash:
            raise ConfigurationError(f"planned job {job.ordinal} identity or hash is invalid")
        return job


@dataclass(frozen=True)
class ExperimentLock:
    schema_version: int
    experiment_id: str
    experiment_kind: ExperimentKind
    experiment_hash: str
    storage_id: str
    optimizer_id: str | None
    planner_version: str
    config_hashes: Mapping[str, str]
    jobs: tuple[PlannedJob, ...]
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        experiment_id: str,
        experiment_kind: ExperimentKind,
        experiment_hash: str,
        storage_id: str,
        optimizer_id: str | None,
        config_hashes: Mapping[str, str],
        jobs: Sequence[PlannedJob],
    ) -> ExperimentLock:
        if not jobs:
            raise ConfigurationError("experiment lock requires at least one job")
        identity = {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": _identifier(experiment_id, "experiment_id"),
            "experiment_kind": experiment_kind,
            "experiment_hash": _string(experiment_hash, "experiment_hash"),
            "storage_id": _identifier(storage_id, "storage_id"),
            "optimizer_id": (
                _identifier(optimizer_id, "optimizer_id") if optimizer_id else None
            ),
            "planner_version": PLANNER_VERSION,
            "config_hashes": MappingProxyType(dict(config_hashes)),
            "jobs": tuple(jobs),
        }
        return cls(**identity, content_hash=content_hash(identity))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ExperimentLock:
        if _schema(payload) != SCHEMA_VERSION:
            raise AssertionError("unreachable")
        try:
            kind = ExperimentKind(payload.get("experiment_kind"))
        except ValueError as error:
            raise ConfigurationError("invalid experiment lock kind") from error
        raw_jobs = payload.get("jobs")
        if not isinstance(raw_jobs, Sequence) or isinstance(raw_jobs, (str, bytes)):
            raise ConfigurationError("experiment lock jobs must be a list")
        jobs = tuple(
            PlannedJob.from_mapping(_mapping(item, "experiment lock jobs[]"))
            for item in raw_jobs
        )
        config_hashes_payload = _mapping(
            payload.get("config_hashes"), "experiment lock config_hashes"
        )
        config_hashes = {
            key: _string(value, f"config hash {key}")
            for key, value in config_hashes_payload.items()
        }
        lock = cls.create(
            experiment_id=payload.get("experiment_id"),  # type: ignore[arg-type]
            experiment_kind=kind,
            experiment_hash=payload.get("experiment_hash"),  # type: ignore[arg-type]
            storage_id=payload.get("storage_id"),  # type: ignore[arg-type]
            optimizer_id=payload.get("optimizer_id"),  # type: ignore[arg-type]
            config_hashes=config_hashes,
            jobs=jobs,
        )
        if payload.get("planner_version") != lock.planner_version:
            raise ConfigurationError("experiment lock planner version is incompatible")
        if payload.get("content_hash") != lock.content_hash:
            raise ConfigurationError("experiment lock content hash is invalid")
        return lock


@dataclass(frozen=True)
class ArtifactReference:
    content_id: str
    media_type: str
    size_bytes: int
    relative_path: str


@dataclass(frozen=True)
class ModelCallRecord:
    call_id: str
    provider_id: str
    model: str
    parameters: Mapping[str, object]
    rendered_messages: tuple[Mapping[str, object], ...]
    request_artifact: ArtifactReference
    response_artifact: ArtifactReference
    usage: Mapping[str, object]
    status: Literal["completed", "failed"]
    error_kind: str | None
    latency_seconds: float
    configured_cost: float


@dataclass(frozen=True)
class ProgramResult:
    outputs: Mapping[str, object]
    primary_response: str | None
    calls: tuple[ModelCallRecord, ...]
    trace_artifact: ArtifactReference | None
    status: Literal["completed", "failed"]
    error_kind: str | None


@dataclass(frozen=True)
class RunRecord:
    schema_version: int
    id: str
    job_hash: str
    status: RunStatus
    result_artifact: ArtifactReference | None
    error_kind: str | None


@dataclass(frozen=True)
class EvaluatorIdentity:
    name: str
    method: str
    version: str


@dataclass(frozen=True)
class EvaluationResult:
    status: EvaluationStatus
    evaluator: EvaluatorIdentity | None
    score: float | None
    passed: bool | None
    feedback: str | None
    checks: tuple[Mapping[str, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WorkspaceConfiguration:
    schema_version: int
    id: str
    roots: Mapping[str, str]
    external_data_root_env: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> WorkspaceConfiguration:
        roots = _mapping(payload.get("roots"), "workspace.roots")
        required = {
            "compatibility",
            "evaluators",
            "targets",
            "snapshots",
            "suites",
            "programs",
            "providers",
            "runtimes",
            "optimizers",
            "storage",
            "plans",
        }
        missing = sorted(required - set(roots))
        unknown = sorted(set(roots) - required)
        if missing or unknown:
            raise ConfigurationError(f"workspace roots invalid; missing={missing}, unknown={unknown}")
        normalized = {
            name: _repository_path(value, f"workspace.roots.{name}")
            for name, value in roots.items()
        }
        environment_name = _string(payload.get("external_data_root_env"), "external_data_root_env")
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", environment_name) is None:
            raise ConfigurationError(
                "external_data_root_env must be an uppercase environment variable name"
            )
        return cls(
            _schema(payload),
            _identifier(payload.get("id")),
            MappingProxyType(normalized),
            environment_name,
        )
