"""Immutable, atomically published file catalog with optimistic revision checks."""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from .catalog import seed_templates
from .errors import DesignError, RevisionConflict
from .settings import Settings
from .templates import validate_snapshot
from .vocabulary import ID_RE


class FileCatalogRepository:
    def __init__(self, directory: Path, settings: Settings | None = None):
        self.settings = settings if settings is not None else Settings()
        self.directory = directory / "catalog"
        self.profiles = self.directory / "profiles"
        self.templates = self.directory / "templates"
        self.profiles.mkdir(parents=True, exist_ok=True)
        self.templates.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._seed()

    @contextmanager
    def locked(self) -> Iterator[None]:
        with self._lock, (self.directory / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _seed(self) -> None:
        with self.locked():
            for identifier, info in seed_templates().items():
                if not (self.templates / identifier / "1.json").exists():
                    self._store(validate_snapshot(info, settings=self.settings))

    def _store(self, info: dict[str, Any]) -> None:
        manifest = deepcopy(info)
        ttl = manifest.pop("profile_ttl")
        for derived in (
            "fields",
            "required",
            "related_templates",
            "target_classes",
            "titles",
            "descriptions",
        ):
            manifest.pop(derived, None)
        for item in manifest.get("documents", {}).values():
            content = item.pop("ttl")
            dependency = self.profiles / f"{item['hash']}.ttl"
            if not dependency.exists():
                self._atomic(dependency, content)
        profile = self.profiles / f"{info['profile_hash']}.ttl"
        if not profile.exists():
            self._atomic(profile, ttl)
        self._atomic(
            self.templates / info["id"] / f"{info['revision']}.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    def _profile_text(self, digest: str) -> str:
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise DesignError("Invalid stored profile hash.")
        return (self.profiles / f"{digest}.ttl").read_text(encoding="utf-8")

    def get(self, identifier: str, revision: int | None = None) -> dict[str, Any]:
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
            raise DesignError("Invalid template ID.")
        directory = self.templates / identifier
        revisions = [int(p.stem) for p in directory.glob("*.json") if p.stem.isdigit()]
        if not revisions:
            raise DesignError(f"Unknown template: {identifier}")
        revision = max(revisions) if revision is None else revision
        if type(revision) is not int or revision not in revisions:
            raise DesignError(f"Unknown revision: {identifier}/{revision}")
        cache_key = (identifier, revision)
        if cache_key not in self._cache:
            try:
                info = json.loads((directory / f"{revision}.json").read_text(encoding="utf-8"))
                info["profile_ttl"] = self._profile_text(info["profile_hash"])
                for item in info.get("documents", {}).values():
                    item["ttl"] = self._profile_text(item.get("hash", ""))
                self._cache[cache_key] = validate_snapshot(info, settings=self.settings)
            except (OSError, ValueError, KeyError) as exc:
                raise RuntimeError(
                    f"Cannot read catalog entry {identifier}/{revision}; restore it from backup."
                ) from exc
        return deepcopy(self._cache[cache_key])

    def catalog(self) -> dict[str, dict[str, Any]]:
        return {
            path.name: self.get(path.name)
            for path in sorted(self.templates.iterdir())
            if path.is_dir() and any(path.glob("*.json"))
        }

    def publish(
        self, snapshot: dict[str, Any], expected_revision: int | None = None
    ) -> dict[str, Any]:
        """Commit a prepared snapshot, checking the current revision under the lock."""
        info = deepcopy(snapshot)
        identifier = info["id"]
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
            raise DesignError("Invalid template ID.")
        with self.locked():
            directory = self.templates / identifier
            revisions = [int(p.stem) for p in directory.glob("*.json") if p.stem.isdigit()]
            latest = max(revisions, default=0)
            if latest != (expected_revision or 0) or info["revision"] != latest + 1:
                raise RevisionConflict(
                    "Template changed. Reload the latest revision before saving."
                )
            self._store(info)
        return info
