"""Immutable file repository and validated, portable template snapshots."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Protocol
from uuid import uuid4
from .catalog import seed_templates
from .errors import DesignError
from .profile_schema import compile_profile, profile_from_fields, profile_hash, RESERVED
from .vocabulary import ID_RE


class RevisionConflict(DesignError):
    pass


class CatalogRepository(Protocol):
    def catalog(self) -> dict: ...
    def get(self, identifier: str, revision: int | None = None) -> dict: ...
    def publish(self, draft: dict, identifier: str | None = None, expected_revision: int | None = None) -> dict: ...


def validate_snapshot(raw: dict) -> dict:
    if not isinstance(raw, dict): raise DesignError('Template must be an object.')
    info = deepcopy(raw)
    info.pop("initial", None)
    if not isinstance(info.get('id'), str) or not ID_RE.fullmatch(info['id']): raise DesignError('Invalid template ID.')
    if type(info.get('revision')) is not int or info['revision'] < 1: raise DesignError('Invalid template revision.')
    if info.get('kind') not in ('group', 'dataset'): raise DesignError('Invalid HDF5 object kind.')
    for key in ('label', 'category', 'icon', 'color', 'profile', 'shape'):
        if not isinstance(info.get(key), str) or not info[key] or len(info[key]) > 2000: raise DesignError(f'Invalid template {key}.')
    if info['color'] not in ('blue', 'green', 'purple', 'orange', 'amber', 'coral', 'rose', 'violet'): raise DesignError('Unsupported template color.')
    mapping = info.get('mapping', {})
    if not isinstance(mapping, dict): raise DesignError('Field mapping must be an object.')
    info['fields'] = compile_profile(info.get('profile_ttl'), info['shape'], mapping)
    digest = profile_hash(info['profile_ttl'])
    if info.get('profile_hash', digest) != digest: raise DesignError('Profile snapshot hash does not match its Turtle.')
    info['profile_hash'] = digest
    info['mapping'] = {f['predicate']: f['key'] for f in info['fields']}
    info['required'] = [f['key'] for f in info['fields'] if f['required']]
    defaults = info.get('defaults', {})
    if not isinstance(defaults, dict): raise DesignError('Defaults must be an object.')
    from .vocabulary import KEY_RE
    import math
    for key, value in defaults.items():
        if not KEY_RE.fullmatch(key) or not isinstance(value, (str, int, float, bool, type(None))): raise DesignError('Defaults must contain scalar attribute values.')
        if isinstance(value, float) and not math.isfinite(value): raise DesignError('Defaults must be finite.')
        if key in RESERVED - {'path', 'shape', 'dtype', 'profile_uri', 'required_fields'}: raise DesignError(f'Reserved attribute: {key}')
    for f in info['fields']:
        defaults.setdefault(f['key'], f.get('defaultValue', f.get('hasValue', '')))
    info['defaults'] = defaults
    info['schema_version'] = 1
    return info


class FileCatalogRepository:
    def __init__(self, directory: Path, settings=None):
        self.settings = settings
        self.directory = directory / 'catalog'
        self.profiles = self.directory / 'profiles'
        self.templates = self.directory / 'templates'
        self.profiles.mkdir(parents=True, exist_ok=True)
        self.templates.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._cache = {}
        self._seed()

    @contextmanager
    def locked(self):
        with self._lock, (self.directory / '.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)

    def _atomic(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as handle:
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
            os.replace(name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            if os.path.exists(name): os.unlink(name)

    def _seed(self):
        with self.locked():
            for identifier, info in seed_templates().items():
                if (self.templates / identifier / '1.json').exists(): continue
                self._store(validate_snapshot(info))

    def _store(self, info):
        manifest = deepcopy(info)
        ttl = manifest.pop('profile_ttl')
        manifest.pop('fields', None); manifest.pop('required', None)
        profile = self.profiles / f"{info['profile_hash']}.ttl"
        if not profile.exists(): self._atomic(profile, ttl)
        self._atomic(self.templates / info['id'] / f"{info['revision']}.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    def get(self, identifier, revision=None):
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier): raise DesignError('Invalid template ID.')
        directory = self.templates / identifier
        revisions = [int(p.stem) for p in directory.glob('*.json') if p.stem.isdigit()]
        if not revisions: raise DesignError(f'Unknown template: {identifier}')
        revision = max(revisions) if revision is None else revision
        if type(revision) is not int or revision not in revisions: raise DesignError(f'Unknown revision: {identifier}/{revision}')
        cache_key = (identifier, revision)
        if cache_key not in self._cache:
            try:
                info = json.loads((directory / f'{revision}.json').read_text())
                digest = info['profile_hash']
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest): raise DesignError('Invalid stored profile hash.')
                info['profile_ttl'] = (self.profiles / f'{digest}.ttl').read_text()
                self._cache[cache_key] = validate_snapshot(info)
            except (OSError, ValueError, KeyError) as exc:
                raise RuntimeError(f'Cannot read catalog entry {identifier}/{revision}; restore it from backup.') from exc
        return deepcopy(self._cache[cache_key])

    def catalog(self):
        return {p.name: self.get(p.name) for p in sorted(self.templates.iterdir()) if p.is_dir() and any(p.glob('*.json'))}

    def publish(self, draft, identifier=None, expected_revision=None):
        if not isinstance(draft, dict): raise DesignError('Template must be an object.')
        info = deepcopy(draft)
        if 'profile_ttl' not in info:
            info['profile_ttl'] = profile_from_fields(info.get('shape', ''), info.get('fields', []))
            info['mapping'] = {f['predicate']: f['key'] for f in info.get('fields', [])}
        with self.locked():
            if identifier is None:
                identifier, revision = 'custom_' + uuid4().hex[:16], 1
            else:
                previous = self.get(identifier)
                if expected_revision != previous['revision']: raise RevisionConflict('Template changed. Reload the latest revision before saving.')
                revision = previous['revision'] + 1
            info.update(id=identifier, revision=revision)
            info.pop('profile_hash', None)
            info.setdefault('profile', info.get('shape', ''))
            info = validate_snapshot(info)
            # Apply the same storage constraints as designs before publishing defaults.
            from .domain import parse_blueprint
            from .settings import Settings
            parse_blueprint({'nodes':[{'id':'default', 'type':identifier, 'config':info['defaults'], 'template':info}], 'edges':[]}, self.settings or Settings())
            self._store(info)
            return info
