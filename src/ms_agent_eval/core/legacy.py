from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import ConfigurationError, IntegrityError
from .hashing import content_hash
from .models import ArtifactReference
from .storage import ArtifactStore


_LABEL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")


@dataclass(frozen=True)
class LegacyFileRecord:
    original_path: str
    content_hash: str
    size_bytes: int
    artifact: ArtifactReference


@dataclass(frozen=True)
class LegacyArchive:
    schema_version: int
    namespace: str
    source_label: str
    files: tuple[LegacyFileRecord, ...]
    tree_hash: str
    manifest_artifact: ArtifactReference


class LegacyArchiveExporter:
    """Export read-only schema-v0 trees without modifying or interpreting their bytes."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts

    def export_tree(
        self,
        source: Path,
        *,
        source_label: str,
        namespace: str,
    ) -> LegacyArchive:
        root = source.resolve()
        if not root.is_dir():
            raise ConfigurationError(f"legacy source is not a directory: {source}")
        for value, name in ((source_label, "source_label"), (namespace, "namespace")):
            if not _LABEL.fullmatch(value) or ".." in PurePosixPath(value).parts:
                raise ConfigurationError(f"legacy {name} is unsafe: {value!r}")
        records = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise IntegrityError(f"legacy archive refuses symlink: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            with path.open("rb") as handle:
                reference = self.artifacts.put_blob(
                    handle, "application/octet-stream"
                )
            records.append(
                LegacyFileRecord(
                    f"{source_label}/{relative}",
                    reference.content_id,
                    reference.size_bytes,
                    reference,
                )
            )
        if not records:
            raise ConfigurationError("legacy source contains no files")
        tree_hash = content_hash(
            [
                {
                    "original_path": record.original_path,
                    "content_hash": record.content_hash,
                    "size_bytes": record.size_bytes,
                }
                for record in records
            ]
        )
        manifest = self.artifacts.put_manifest(
            f"legacy/{namespace}/{tree_hash.removeprefix('sha256:')}",
            {
                "schema_version": 1,
                "source_schema_version": 0,
                "namespace": namespace,
                "source_label": source_label,
                "tree_hash": tree_hash,
                "files": records,
            },
        )
        return LegacyArchive(1, namespace, source_label, tuple(records), tree_hash, manifest)


def load_legacy_json(path: Path) -> dict[str, object]:
    """Read a schema-v0 JSON document without rewriting it."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigurationError(f"legacy JSON document must be an object: {path}")
    return {str(key): value for key, value in payload.items()}
