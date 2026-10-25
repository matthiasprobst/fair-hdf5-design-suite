"""Use cases shared by HTTP endpoints and the compatibility facade."""

from copy import deepcopy
from typing import Any, BinaryIO
from uuid import uuid4

from rdflib import RDF, Graph
from rdflib.compare import isomorphic
from rdflib.namespace import SH

from .catalog import CATALOG
from .domain import ValidatedBlueprint, parse_blueprint
from .engines import ValidationEngine, create_engine
from .errors import DesignError, RevisionConflict, UploadTooLarge
from .hdf5 import hdf5_template, open_uploaded_hdf5, structural_checks
from .library import FileCatalogRepository
from .preview import structure_preview
from .profile_bundles import resolve_bundle, unbundled_imports
from .profile_schema import analyze_profile, parse_profile, profile_from_fields
from .repositories import CatalogRepository
from .semantic import build_shapes, rdf_from_hdf5
from .settings import Settings
from .templates import validate_snapshot


class DesignService:
    def __init__(
        self,
        settings: Settings,
        engine: ValidationEngine | None = None,
        repository: CatalogRepository | None = None,
    ):
        self.settings = settings
        if repository is None:
            # Direct Python construction also supports a default local catalog.
            repository = FileCatalogRepository(settings.data_dir, settings)
        self.repository = repository
        self.engine = engine if engine is not None else create_engine(settings.shacl_engine)

    def _parse(self, value: Any) -> ValidatedBlueprint:
        blueprint = parse_blueprint(value, self.settings, self.repository)
        if self.settings.shacl_engine != "pyshacl":
            for node in blueprint.data["nodes"]:
                info = node["template"]
                if info.get("requires_pyshacl"):
                    raise DesignError(
                        f"Template '{info['label']}' requires FAIR_HDF5_SHACL_ENGINE=pyshacl."
                    )
                if (
                    node["type"] not in CATALOG
                    or info.get("revision") != 1
                    or info["mapping"] != CATALOG[node["type"]]["mapping"]
                    or not isomorphic(
                        parse_profile(info["profile_ttl"]),
                        parse_profile(CATALOG[node["type"]]["profile_ttl"]),
                    )
                ):
                    raise DesignError("Custom profiles require FAIR_HDF5_SHACL_ENGINE=pyshacl.")
        return blueprint

    def normalize(self, value: Any) -> dict[str, Any]:
        return self._parse(value).data

    def preview(self, value: Any) -> dict[str, Any]:
        return structure_preview(self._parse(value).data)

    def shapes(self, value: Any) -> Graph:
        return build_shapes(self._parse(value).data)

    def shacl(self, value: Any) -> str:
        return self.shapes(value).serialize(format="turtle")

    def template(self, value: Any) -> bytes:
        blueprint = self._parse(value)
        return hdf5_template(blueprint.data, blueprint.dataset_shapes)

    def validate_template(self, value: Any) -> dict[str, Any]:
        blueprint = self._parse(value)
        content = hdf5_template(blueprint.data, blueprint.dataset_shapes)
        return self._validate(blueprint, content)

    def validate(self, value: Any, content: bytes) -> dict[str, Any]:
        blueprint = self._parse(value)
        self._check_upload_size(len(content))
        return self._validate(blueprint, content)

    def validate_upload(self, value: Any, file: BinaryIO) -> dict[str, Any]:
        blueprint = self._parse(value)
        content = file.read(self.settings.max_upload_bytes + 1)
        self._check_upload_size(len(content))
        return self._validate(blueprint, content)

    def _check_upload_size(self, size: int) -> None:
        if size > self.settings.max_upload_bytes:
            raise UploadTooLarge(
                f"Validation upload limit is {self.settings.max_upload_bytes} bytes."
            )

    def _validate(self, blueprint: ValidatedBlueprint, content: bytes) -> dict[str, Any]:
        with open_uploaded_hdf5(content, self.settings.temp_dir) as handle:
            issues, checks = structural_checks(blueprint.data, handle, blueprint.dataset_shapes)
            rdf = rdf_from_hdf5(blueprint.data, handle)
        shapes = build_shapes(blueprint.data)
        shacl_issues = self.engine.validate(shapes, rdf)
        checks += len(list(shapes.subjects(RDF.type, SH.NodeShape)))
        issues = [{**issue, "layer": "HDF5"} for issue in issues]
        issues.extend({**issue, "layer": "SHACL/RDF"} for issue in shacl_issues)
        return {
            "conforms": not issues,
            "checks": checks,
            "issue_count": len(issues),
            "issues": issues[: self.settings.max_report_issues],
            "shacl_engine": self.engine.name,
            "note": "Conformance concerns the modeled HDF5 structure and RDF-projected metadata, not physical correctness or full FAIR compliance.",
        }


class CatalogService:
    """Analyze profiles and prepare valid snapshots before committing to storage."""

    def __init__(self, settings: Settings, repository: CatalogRepository):
        self.settings = settings
        self.repository = repository

    def catalog(self) -> dict[str, Any]:
        return {
            "catalog": self.repository.catalog(),
            "legacy_catalog": {key: self.repository.get(key, 1) for key in CATALOG},
            "profile_source": "Persistent local SHACL library; MPS file import supported",
        }

    def get_revision(self, identifier: str, revision: int) -> dict[str, Any]:
        return self.repository.get(identifier, revision)

    def analyze(
        self, ttl: str, source_uri: str | None, documents: dict[str, Any]
    ) -> dict[str, Any]:
        source, resolved = resolve_bundle(ttl, source_uri, documents, self.settings, fetch=True)
        result = analyze_profile(ttl, resolved, source)
        result["unbundled_imports"] = unbundled_imports(ttl, source, resolved)
        return result

    def publish(
        self,
        draft: dict[str, Any],
        identifier: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if self.settings.shacl_engine != "pyshacl":
            raise DesignError("Custom profiles require pyshacl.")
        if not isinstance(draft, dict):
            raise DesignError("Template must be an object.")
        info = deepcopy(draft)
        if identifier is None:
            identifier = "custom_" + uuid4().hex[:16]
            revision = 1
        else:
            previous = self.repository.get(identifier)
            if expected_revision != previous["revision"]:
                raise RevisionConflict(
                    "Template changed. Reload the latest revision before saving."
                )
            revision = previous["revision"] + 1
        if "profile_ttl" not in info:
            info["profile_ttl"] = profile_from_fields(info.get("shape", ""), info.get("fields", []))
            info["mapping"] = {field["predicate"]: field["key"] for field in info.get("fields", [])}
        info.update(id=identifier, revision=revision)
        info.pop("profile_hash", None)
        info.setdefault("profile", info.get("shape", ""))
        info = validate_snapshot(info, settings=self.settings)
        parse_blueprint(
            {
                "nodes": [
                    {
                        "id": "default",
                        "type": identifier,
                        "config": info["defaults"],
                        "template": info,
                    }
                ],
                "edges": [],
            },
            self.settings,
        )
        return self.repository.publish(info, expected_revision)
