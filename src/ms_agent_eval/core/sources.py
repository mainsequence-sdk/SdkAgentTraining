from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import ResolutionError
from .models import GitSource, SourceRef, SourceRefKind


_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ResolvedSource:
    repository_url_requested: str
    repository_url_canonical: str
    requested_ref: SourceRef
    resolved_commit: str


class SourceProvider(Protocol):
    def resolve(self, source: GitSource) -> ResolvedSource: ...

    def materialize(self, source: ResolvedSource, destination: Path) -> None: ...


GitRunner = Callable[[Sequence[str], Path | None], str]


def run_git(arguments: Sequence[str], cwd: Path | None = None) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    try:
        completed = subprocess.run(
            ["git", "-c", f"core.hooksPath={os.devnull}", *arguments],
            cwd=cwd,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        stderr = getattr(error, "stderr", "") or ""
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else type(error).__name__
        raise ResolutionError(f"Git command failed safely: {detail}") from error
    return completed.stdout


class GitHubSourceProvider:
    def __init__(self, runner: GitRunner = run_git) -> None:
        self._runner = runner

    @staticmethod
    def canonical_url(repository_url: str) -> str:
        return repository_url.removesuffix("/").removesuffix(".git") + ".git"

    def resolve(self, source: GitSource) -> ResolvedSource:
        canonical = self.canonical_url(source.repository_url)
        if source.submodules or source.git_lfs:
            raise ResolutionError("submodules and Git LFS are disabled by the initial safe provider")
        if source.ref.type is SourceRefKind.COMMIT:
            commit = source.ref.value
        else:
            ref = f"refs/tags/{source.ref.value}"
            output = self._runner(
                ["ls-remote", "--tags", canonical, ref, f"{ref}^{{}}"], None
            )
            matches: dict[str, str] = {}
            for line in output.splitlines():
                fields = line.split("\t", maxsplit=1)
                if len(fields) == 2 and _COMMIT_PATTERN.fullmatch(fields[0]):
                    matches[fields[1]] = fields[0]
            commit = matches.get(f"{ref}^{{}}") or matches.get(ref)
            if commit is None:
                raise ResolutionError(f"GitHub tag {source.ref.value!r} was not found")
        if not _COMMIT_PATTERN.fullmatch(commit):
            raise ResolutionError("source did not resolve to a full lowercase commit SHA")
        return ResolvedSource(source.repository_url, canonical, source.ref, commit)

    def materialize(self, source: ResolvedSource, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        self._runner(["init", "--quiet"], destination)
        self._runner(["remote", "add", "origin", source.repository_url_canonical], destination)
        self._runner(
            ["fetch", "--quiet", "--depth=1", "--no-tags", "origin", source.resolved_commit],
            destination,
        )
        self._runner(["checkout", "--quiet", "--detach", "FETCH_HEAD"], destination)
        actual = self._runner(["rev-parse", "HEAD"], destination).strip()
        if actual != source.resolved_commit:
            raise ResolutionError(
                f"materialized commit {actual!r} differs from lock {source.resolved_commit!r}"
            )
