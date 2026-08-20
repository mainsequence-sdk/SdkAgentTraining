from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .errors import ConfigurationError, IntegrityError, ResolutionError
from .hashing import canonical_json_bytes, content_hash, sha256_file
from .models import (
    LockedFile,
    LockedInstructionUnit,
    SnapshotLock,
    TargetSpecification,
    UnitSourceSpecification,
)
from .sources import ResolvedSource, SourceProvider


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _safe_source_file(checkout: Path, relative: str) -> Path:
    candidate = checkout / relative
    current = checkout
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ResolutionError(f"snapshot source path contains a symlink: {relative}")
    if not candidate.is_file():
        raise ResolutionError(f"configured snapshot source file does not exist: {relative}")
    resolved = candidate.resolve()
    if not _is_within(resolved, checkout.resolve()):
        raise ResolutionError(f"snapshot source path escapes checkout: {relative}")
    return candidate


def _matches(relative: PurePosixPath, patterns: Iterable[str]) -> bool:
    return any(relative.match(pattern) for pattern in patterns)


def _join_unit_id(prefix: str, value: str) -> str:
    components = [item.strip("/") for item in (prefix, value) if item.strip("/")]
    logical_id = "/".join(components)
    if not logical_id:
        raise ResolutionError("instruction locator produced an empty logical unit id")
    return logical_id


def _directory_units(
    checkout: Path, source: UnitSourceSpecification
) -> list[tuple[str, str]]:
    assert source.root is not None
    assert source.filename is not None
    root = checkout / source.root
    if root.is_symlink() or not root.is_dir():
        raise ResolutionError(f"configured instruction root is not a directory: {source.root}")
    if not _is_within(root.resolve(), checkout.resolve()):
        raise ResolutionError(f"configured instruction root escapes checkout: {source.root}")
    candidates = root.rglob(source.filename) if source.recursive else root.glob(source.filename)
    selected: list[tuple[str, str]] = []
    for candidate in sorted(candidates):
        relative_to_root = PurePosixPath(candidate.relative_to(root).as_posix())
        if not _matches(relative_to_root, source.include):
            continue
        if source.exclude and _matches(relative_to_root, source.exclude):
            continue
        source_path = candidate.relative_to(checkout).as_posix()
        _safe_source_file(checkout, source_path)
        parent = relative_to_root.parent.as_posix()
        derived = candidate.stem if parent == "." else parent
        selected.append((_join_unit_id(source.id_prefix, derived), source_path))
    return selected


def _source_units(
    checkout: Path, source: UnitSourceSpecification
) -> list[tuple[str, str]]:
    if source.type == "directory":
        selected = _directory_units(checkout, source)
    else:
        selected = []
        for entry in source.entries:
            _safe_source_file(checkout, entry.source_path)
            selected.append((_join_unit_id(source.id_prefix, entry.id), entry.source_path))
    if not selected and not source.allow_empty:
        raise ResolutionError(f"instruction source {source.id!r} matched no files")
    if source.exact_count is not None and len(selected) != source.exact_count:
        raise ResolutionError(
            f"instruction source {source.id!r} expected {source.exact_count} files, "
            f"found {len(selected)}"
        )
    selected_ids = {unit_id for unit_id, _ in selected}
    missing = sorted(set(source.required_ids) - selected_ids)
    if missing:
        raise ResolutionError(f"instruction source {source.id!r} misses required ids: {missing}")
    return selected


class ExternalSnapshotStore:
    def __init__(self, data_root: Path, *, workspace_root: Path | None = None) -> None:
        self.data_root = data_root.resolve()
        if workspace_root is not None and _is_within(self.data_root, workspace_root.resolve()):
            raise ConfigurationError("external snapshot data root must be outside the workspace")
        self.snapshot_root = self.data_root / "snapshots"
        self.temporary_root = self.data_root / "tmp"
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.temporary_root.mkdir(parents=True, exist_ok=True)

    def directory(self, lock: SnapshotLock) -> Path:
        return self.snapshot_root / lock.content_hash.removeprefix("sha256:")

    def publish(self, staging: Path, lock: SnapshotLock) -> Path:
        destination = self.directory(lock)
        if destination.exists():
            self.verify(lock)
            shutil.rmtree(staging)
            return destination
        os.replace(staging, destination)
        self.verify(lock)
        return destination

    def verify(self, lock: SnapshotLock) -> None:
        directory = self.directory(lock)
        lock_file = directory / "snapshot.lock.json"
        if not lock_file.is_file() or lock_file.is_symlink():
            raise IntegrityError(f"snapshot lock is missing or unsafe: {lock_file}")
        try:
            loaded = SnapshotLock.from_mapping(
                json.loads(lock_file.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, ConfigurationError) as error:
            raise IntegrityError(f"snapshot lock cannot be verified: {error}") from error
        if loaded != lock:
            raise IntegrityError("published snapshot lock differs from the expected lock")
        expected_paths = {item.snapshot_path for item in lock.files}
        actual_paths = {
            path.relative_to(directory).as_posix()
            for path in (directory / "content").rglob("*")
            if path.is_file()
        }
        if actual_paths != expected_paths:
            raise IntegrityError("snapshot file inventory differs from its immutable lock")
        for item in lock.files:
            path = directory / item.snapshot_path
            if path.is_symlink() or not path.is_file():
                raise IntegrityError(f"snapshot file is missing or unsafe: {item.snapshot_path}")
            if path.stat().st_size != item.size_bytes or sha256_file(path) != item.content_hash:
                raise IntegrityError(f"snapshot file hash mismatch: {item.snapshot_path}")


class SnapshotBuilder:
    def __init__(self, provider: SourceProvider, store: ExternalSnapshotStore) -> None:
        self.provider = provider
        self.store = store

    def create(self, target: TargetSpecification) -> SnapshotLock:
        resolved = self.provider.resolve(target.source)
        checkout_parent = Path(tempfile.mkdtemp(prefix="checkout-", dir=self.store.temporary_root))
        checkout = checkout_parent / "repository"
        try:
            self.provider.materialize(resolved, checkout)
            return self.create_from_checkout(target, resolved, checkout)
        finally:
            shutil.rmtree(checkout_parent, ignore_errors=True)

    def create_from_checkout(
        self,
        target: TargetSpecification,
        resolved: ResolvedSource,
        checkout: Path,
    ) -> SnapshotLock:
        if resolved.requested_ref != target.source.ref:
            raise ResolutionError("resolved source ref does not match the target specification")
        if not checkout.is_dir():
            raise ResolutionError(f"materialized checkout does not exist: {checkout}")

        staging = Path(tempfile.mkdtemp(prefix="snapshot-", dir=self.store.temporary_root))
        try:
            files: dict[str, LockedFile] = {}
            units: list[LockedInstructionUnit] = []
            unit_keys: set[tuple[str, str]] = set()
            for bundle in target.instruction_bundles:
                for context in bundle.global_context:
                    source_file = checkout / context.source_path
                    if not source_file.exists() and not context.required:
                        continue
                    _safe_source_file(checkout, context.source_path)
                    self._copy_locked(source_file, context.source_path, staging, files)
                for source in bundle.unit_sources:
                    for unit_id, source_path in _source_units(checkout, source):
                        key = (bundle.id, unit_id)
                        if key in unit_keys:
                            raise ResolutionError(
                                f"instruction unit collision for bundle/id {key!r}"
                            )
                        unit_keys.add(key)
                        source_file = _safe_source_file(checkout, source_path)
                        locked_file = self._copy_locked(
                            source_file, source_path, staging, files
                        )
                        units.append(
                            LockedInstructionUnit(
                                bundle_id=bundle.id,
                                source_id=source.id,
                                unit_id=unit_id,
                                source_path=source_path,
                                snapshot_path=locked_file.snapshot_path,
                                content_hash=locked_file.content_hash,
                            )
                        )
            extraction_hash = content_hash(target.instruction_bundles)
            snapshot_id = (
                f"{target.id}-{resolved.resolved_commit[:12]}-"
                f"{extraction_hash.removeprefix('sha256:')[:12]}"
            )
            lock = SnapshotLock.create(
                id=snapshot_id,
                target_id=target.id,
                repository_url=resolved.repository_url_canonical,
                requested_ref=resolved.requested_ref,
                resolved_commit=resolved.resolved_commit,
                target_specification_hash=target.specification_hash,
                extraction_configuration_hash=extraction_hash,
                files=tuple(files[path] for path in sorted(files)),
                units=tuple(sorted(units, key=lambda item: (item.bundle_id, item.unit_id))),
            )
            (staging / "snapshot.lock.json").write_bytes(canonical_json_bytes(lock))
            self.store.publish(staging, lock)
            return lock
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise

    @staticmethod
    def _copy_locked(
        source_file: Path,
        source_path: str,
        staging: Path,
        files: dict[str, LockedFile],
    ) -> LockedFile:
        existing = files.get(source_path)
        if existing is not None:
            return existing
        snapshot_path = f"content/{source_path}"
        destination = staging / snapshot_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, destination, follow_symlinks=False)
        locked = LockedFile(
            source_path=source_path,
            snapshot_path=snapshot_path,
            content_hash=sha256_file(destination),
            size_bytes=destination.stat().st_size,
        )
        files[source_path] = locked
        return locked
