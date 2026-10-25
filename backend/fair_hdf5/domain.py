"""Shared parsing and scientific constraints, with no transport dependencies."""

import math
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .catalog import CATALOG
from .errors import DesignError
from .profile_schema import absolute_iri
from .profiles import node_template
from .repositories import CatalogRepository
from .settings import Settings
from .templates import validate_snapshot
from .vocabulary import ALLOWED_DTYPES, ID_RE, KEY_RE


class NodeInput(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None
    x: float | None = None
    y: float | None = None


class EdgeInput(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    source: str
    target: str


class BlueprintInput(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str = "Untitled experiment"
    version: str = "0.1"
    nodes: list[NodeInput]
    edges: list[EdgeInput] = Field(default_factory=list)


@dataclass(frozen=True)
class ValidatedBlueprint:
    data: dict[str, Any]
    dataset_shapes: dict[str, tuple[int, ...]]


def parse_blueprint(
    value: Any, settings: Settings, repository: CatalogRepository | None = None
) -> ValidatedBlueprint:
    try:
        model = BlueprintInput.model_validate(value)
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise DesignError(f"Invalid blueprint: {errors}") from exc
    design = model.model_dump(exclude_unset=True)
    design.setdefault("name", model.name)
    design.setdefault("version", model.version)
    design.setdefault("edges", [])
    for node in design["nodes"]:
        if node.get("template") is not None:
            node["template"] = validate_snapshot(node["template"], settings=settings)
            if node["template"]["id"] != node["type"]:
                raise DesignError("Node type and template ID do not match.")
        elif repository is not None:
            node["template"] = repository.get(node["type"], 1 if node["type"] in CATALOG else None)
        elif node["type"] in CATALOG:
            node["template"] = validate_snapshot(CATALOG[node["type"]], settings=settings)
        else:
            raise DesignError("Unknown node type or missing template snapshot.")
        for coordinate in ("x", "y"):
            if coordinate in node and (
                node[coordinate] is None or not math.isfinite(node[coordinate])
            ):
                raise DesignError(f"Node {node['id']}: {coordinate} must be finite.")
    return ValidatedBlueprint(design, validate_constraints(design, settings))


def validate_constraints(design: dict[str, Any], settings: Settings) -> dict[str, tuple[int, ...]]:
    dataset_shapes = {}
    if (
        not isinstance(design, dict)
        or not isinstance(design.get("nodes"), list)
        or not isinstance(design.get("edges", []), list)
    ):
        raise DesignError("Expected a design containing arrays 'nodes' and 'edges'.")
    nodes = design["nodes"]
    edges = design.get("edges", [])
    if len(nodes) > settings.max_nodes or len(edges) > settings.max_edges:
        raise DesignError(
            f"Blueprint limit: {settings.max_nodes} nodes and {settings.max_edges} edges."
        )
    ids = set()
    paths: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or (
            not node.get("template") and node.get("type") not in CATALOG
        ):
            raise DesignError("Unknown node type.")
        id = node.get("id", "")
        if not isinstance(id, str) or not ID_RE.fullmatch(id) or id in ids:
            raise DesignError(
                "Node IDs must be unique alphanumeric strings (hyphens and underscores allowed)."
            )
        ids.add(id)
        if not isinstance(node.get("config", {}), dict):
            raise DesignError(f"Node {id}: configuration must be an object.")
        config = node.get("config", {})
        _validate_metadata(node, settings)
        kind = node_template(node)["kind"]
        if kind:
            path = config.get("path", "")
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or path == "/"
                or "//" in path
                or path.endswith("/")
                or "\x00" in path
                or len(path) > 512
            ):
                raise DesignError(f"Node {id}: invalid absolute HDF5 path.")
            if path.startswith("/__design__"):
                raise DesignError("/__design__ is a reserved path.")
            if path in paths:
                raise DesignError(f"Nodes {paths[path]} and {id} share HDF5 path {path}.")
            paths[path] = id
        if config.get("required_fields"):
            extra = config["required_fields"]
            if not isinstance(extra, str):
                raise DesignError(f"Node {id}: required_fields must be a comma-separated string.")
            for field in [x.strip() for x in extra.split(",") if x.strip()]:
                if not KEY_RE.fullmatch(field) or field in {
                    "path",
                    "dtype",
                    "shape",
                    "profile_uri",
                    "required_fields",
                }:
                    raise DesignError(f"Node {id}: invalid custom required field: {field}")
        if kind == "dataset":
            if config.get("dtype", "float64") not in ALLOWED_DTYPES:
                raise DesignError(f"Node {id}: unsupported numeric dtype.")
            dataset_shapes[id] = parse_shape(str(config.get("shape", "0")), settings)
    dataset_paths = {n["config"]["path"] for n in nodes if node_template(n)["kind"] == "dataset"}
    for path in paths:
        parts = path.strip("/").split("/")
        for i in range(1, len(parts)):
            ancestor = "/" + "/".join(parts[:i])
            if ancestor in dataset_paths:
                raise DesignError(f"HDF5 dataset at {ancestor} cannot contain child object {path}.")
    by_id = {n["id"]: n for n in nodes}
    semantic_keys = set()
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or edge.get("source") not in ids
            or edge.get("target") not in ids
        ):
            raise DesignError("Every edge must connect existing nodes.")
        if edge.get("predicate") is not None or edge.get("field_id") is not None:
            source, target = by_id[edge["source"]], by_id[edge["target"]]
            field = next(
                (
                    f
                    for f in node_template(source).get("fields", [])
                    if f.get("id") == edge.get("field_id") and f.get("kind") == "reference"
                ),
                None,
            )
            if not field or field["predicate"] != edge.get("predicate"):
                raise DesignError("Semantic edge does not match a source profile field.")
            if node_template(target).get("shape") != field["targetShape"]:
                raise DesignError("Semantic edge targets an incompatible profile.")
            key = (source["id"], target["id"], edge["predicate"], edge["field_id"])
            if key in semantic_keys:
                raise DesignError("Duplicate semantic relationship.")
            semantic_keys.add(key)
    return dataset_shapes


def parse_shape(raw: str, settings: Settings) -> tuple[int, ...]:
    try:
        dims = tuple(int(x.strip()) for x in raw.split(","))
    except (ValueError, TypeError) as exc:
        raise DesignError(
            "Dataset shape must be comma-separated nonnegative integers, e.g. '0' or '0,3'."
        ) from exc
    if not 1 <= len(dims) <= settings.max_dataset_dimensions or any(
        x < 0 or x > settings.max_dimension_size for x in dims
    ):
        raise DesignError(
            f"Dataset shape must contain 1–{settings.max_dataset_dimensions} nonnegative dimensions <={settings.max_dimension_size}."
        )
    if any(dim == 0 for dim in dims[1:]):
        raise DesignError(
            "Only the first dataset dimension may be 0 (resizable); subsequent dimensions must be positive."
        )
    if math.prod(dims) > settings.max_dataset_elements:
        raise DesignError(
            f"Template datasets are limited to {settings.max_dataset_elements} elements."
        )
    return dims


def _validate_metadata(node: dict[str, Any], settings: Settings) -> None:
    node_id = node["id"]
    config = node.get("config", {})
    definitions = {f["key"]: f for f in node_template(node).get("fields", [])}
    for k, value in config.items():
        if k in {"design_node_id", "design_label", "design_type", "designed_shape"}:
            raise DesignError(f"Node {node_id}: reserved HDF5 attribute: {k}")
        definition = definitions.get(k, {})
        if definition.get("kind") == "reference":
            raise DesignError(f"Node {node_id}: {k} must be represented by semantic edges.")
        if isinstance(value, list):
            if not definition.get("multiple") or len(value) > settings.max_metadata_length:
                raise DesignError(f"Node {node_id}: unsupported or oversized list: {k}")
            if value and (
                any(type(v) is not type(value[0]) for v in value) or any(v is None for v in value)
            ):
                raise DesignError(f"Node {node_id}: lists must contain homogeneous scalar values.")
            values = value
        else:
            values = [value]
        for v in values:
            if not KEY_RE.fullmatch(str(k)) or not isinstance(
                v, (str, int, float, bool, type(None))
            ):
                raise DesignError(f"Node {node_id}: unsupported metadata key or value: {k}")
            if isinstance(v, float) and not math.isfinite(v):
                raise DesignError(f"Node {node_id}: metadata must be finite.")
            if isinstance(v, int) and not -(2**63) <= v < 2**64:
                raise DesignError(f"Node {node_id}: integer outside HDF5 range.")
            if isinstance(v, str) and ("\x00" in v or len(v) > settings.max_metadata_length):
                raise DesignError(f"Node {node_id}: invalid or oversized metadata text.")
            if definition.get("datatype") == "IRI" and v not in (None, "") and not absolute_iri(v):
                raise DesignError(f"Node {node_id}: {k} must be an absolute IRI.")
