"""Use cases shared by HTTP endpoints and the compatibility facade."""
from typing import Any, BinaryIO
from rdflib import RDF
from rdflib.namespace import SH

from .domain import parse_blueprint, ValidatedBlueprint
from .engines import create_engine, ValidationEngine
from .errors import UploadTooLarge, DesignError
from .library import FileCatalogRepository, CatalogRepository
from .hdf5 import hdf5_template, open_uploaded_hdf5, structural_checks
from .preview import structure_preview
from .semantic import build_shapes, rdf_from_hdf5
from .settings import Settings


class DesignService:
    def __init__(self, settings: Settings, engine: ValidationEngine | None = None, repository: CatalogRepository | None = None):
        self.settings = settings
        self.repository = repository if repository is not None else FileCatalogRepository(settings.data_dir, settings)
        self.engine = engine if engine is not None else create_engine(settings.shacl_engine)

    def _parse(self, value):
        blueprint = parse_blueprint(value, self.settings, self.repository)
        if self.settings.shacl_engine != "pyshacl":
            for node in blueprint.data["nodes"]:
                info = node["template"]
                from .catalog import CATALOG
                from rdflib.compare import isomorphic
                from .profile_schema import parse_profile
                if node["type"] not in CATALOG or info.get("revision") != 1 or info["mapping"] != CATALOG[node["type"]]["mapping"] or not isomorphic(parse_profile(info["profile_ttl"]), parse_profile(CATALOG[node["type"]]["profile_ttl"])):
                    raise DesignError("Custom profiles require FAIR_HDF5_SHACL_ENGINE=pyshacl.")
        return blueprint

    def normalize(self, value: Any) -> dict[str, Any]:
        return self._parse(value).data

    def preview(self, value: Any):
        return structure_preview(self._parse(value).data)

    def shapes(self, value: Any):
        return build_shapes(self._parse(value).data)

    def shacl(self, value: Any) -> str:
        return self.shapes(value).serialize(format="turtle")

    def template(self, value: Any) -> bytes:
        blueprint = self._parse(value)
        return hdf5_template(blueprint.data, blueprint.dataset_shapes)

    def validate_template(self, value: Any):
        blueprint = self._parse(value)
        content = hdf5_template(blueprint.data, blueprint.dataset_shapes)
        return self._validate(blueprint, content)

    def validate(self, value: Any, content: bytes):
        blueprint = self._parse(value)
        self._check_upload_size(len(content))
        return self._validate(blueprint, content)

    def validate_upload(self, value: Any, file: BinaryIO):
        blueprint = self._parse(value)
        content = file.read(self.settings.max_upload_bytes + 1)
        self._check_upload_size(len(content))
        return self._validate(blueprint, content)

    def _check_upload_size(self, size: int):
        if size > self.settings.max_upload_bytes:
            raise UploadTooLarge(f"Validation upload limit is {self.settings.max_upload_bytes} bytes.")

    def _validate(self, blueprint: ValidatedBlueprint, content: bytes):
        with open_uploaded_hdf5(content, self.settings.temp_dir) as handle:
            issues, checks = structural_checks(blueprint.data, handle, blueprint.dataset_shapes)
            rdf = rdf_from_hdf5(blueprint.data, handle)
        shapes = build_shapes(blueprint.data)
        shacl_issues = self.engine.validate(shapes, rdf)
        checks += len(list(shapes.subjects(RDF.type, SH.NodeShape)))
        issues = [{**issue, "layer": "HDF5"} for issue in issues]
        issues.extend({**issue, "layer": "SHACL/RDF"} for issue in shacl_issues)
        return {
            "conforms": not issues, "checks": checks, "issue_count": len(issues),
            "issues": issues[:self.settings.max_report_issues], "shacl_engine": self.engine.name,
            "note": "Conformance concerns the modeled HDF5 structure and RDF-projected metadata, not physical correctness or full FAIR compliance.",
        }
