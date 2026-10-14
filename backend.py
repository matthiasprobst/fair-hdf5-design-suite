"""FAIR HDF5 Design Suite — demonstrator backend.

Separation of concerns:
- Design graph: experiment / acquisition / process relationships.
- Materialized HDF5 model: paths, groups, datasets, metadata.
- SHACL graph: semantic description of HDF5 objects, validated on the RDF projection.

Local illustrative profiles are NOT claimed to be live NFDI4Ing MPS profiles.
"""
from __future__ import annotations
import io
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SH, XSD

BASE = "https://w3id.org/fair-hdf5-designer/demo/"
H5 = Namespace(BASE + "hdf5#")
META = Namespace(BASE + "metadata#")
PROFILES = Namespace(BASE + "profiles/")
NODE_BASE = BASE + "node/"
SHAPE_BASE = BASE + "shape/"

# A small local profile catalog. This is a POC substitute for a future MPS import.
CATALOG: dict[str, dict[str, Any]] = {
    "fan": {"label": "Radial fan", "category": "Experiment", "icon": "◉", "profile": "fan", "kind": "group", "color": "purple", "required": ["model", "manufacturer"], "defaults": {"path": "/experiment/equipment/fan", "model": "RF-120", "manufacturer": "Lab demonstrator"}},
    "pressure_sensor": {"label": "Pressure sensor", "category": "Sensor", "icon": "◉", "profile": "pressure-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number", "calibration_date"], "defaults": {"path": "/experiment/instrumentation/pressure_01", "quantity": "pressure", "unit": "Pa", "manufacturer": "Demo Instruments", "serial_number": "P-001", "calibration_date": "2026-02-01"}},
    "temperature_sensor": {"label": "Temperature sensor", "category": "Sensor", "icon": "♨", "profile": "temperature-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number", "calibration_date"], "defaults": {"path": "/experiment/instrumentation/temperature_01", "quantity": "temperature", "unit": "K", "manufacturer": "Demo Instruments", "serial_number": "T-002", "calibration_date": "2026-02-01"}},
    "torque_sensor": {"label": "Torque sensor", "category": "Sensor", "icon": "↻", "profile": "torque-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number", "calibration_date"], "defaults": {"path": "/experiment/instrumentation/torque_01", "quantity": "torque", "unit": "N m", "manufacturer": "Demo Instruments", "serial_number": "Q-003", "calibration_date": "2026-02-01"}},
    "flow_sensor": {"label": "Flow sensor", "category": "Sensor", "icon": "≋", "profile": "flow-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number"], "defaults": {"path": "/experiment/instrumentation/flow_01", "quantity": "volumetric flow rate", "unit": "m3/s", "manufacturer": "Demo Instruments", "serial_number": "F-004"}},
    "daq": {"label": "DAQ / Logger", "category": "Equipment", "icon": "▣", "profile": "data-acquisition", "kind": "group", "color": "green", "required": ["system", "sampling_rate_hz"], "defaults": {"path": "/experiment/acquisition/daq_01", "system": "Python acquisition", "sampling_rate_hz": "1000"}},
    "process": {"label": "Processing step", "category": "Process", "icon": "⚙", "profile": "processing", "kind": "group", "color": "amber", "required": ["method"], "defaults": {"path": "/experiment/processing/write_to_hdf5", "method": "Acquire and write measurements"}},
    "group": {"label": "HDF5 group", "category": "HDF5 structure", "icon": "▤", "profile": "group", "kind": "group", "color": "rose", "required": [], "defaults": {"path": "/experiment"}},
    "dataset": {"label": "HDF5 dataset", "category": "HDF5 structure", "icon": "▥", "profile": "dataset", "kind": "dataset", "color": "rose", "required": ["quantity", "unit"], "defaults": {"path": "/experiment/measurements/velocity", "quantity": "velocity", "unit": "m/s", "dtype": "float64", "shape": "0"}},
    "metadata": {"label": "Experiment metadata", "category": "Metadata", "icon": "≡", "profile": "experiment-metadata", "kind": "group", "color": "violet", "required": ["operator", "experiment_date"], "defaults": {"path": "/experiment/metadata", "operator": "Lab researcher", "experiment_date": "2026-10-13"}},
    # Additional locally modeled building blocks support a fuller experimental
    # palette. These remain illustrative profiles, NOT live NFDI4Ing MPS shapes.
    "experiment_setup": {"label": "Experimental setup", "category": "Experiment", "icon": "◈", "profile": "experimental-setup", "kind": "group", "color": "purple", "required": ["description"], "defaults": {"path": "/experiment/setup", "description": "Experimental test rig"}},
    "boundary_condition": {"label": "Boundary condition", "category": "Experiment", "icon": "◈", "profile": "boundary-condition", "kind": "group", "color": "purple", "required": ["condition_name"], "defaults": {"path": "/experiment/boundary_conditions/condition_01", "condition_name": "Inlet condition"}},
    "vibration_sensor": {"label": "Vibration sensor", "category": "Sensor", "icon": "~", "profile": "vibration-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number"], "defaults": {"path": "/experiment/instrumentation/vibration_01", "quantity": "acceleration", "unit": "m/s2", "manufacturer": "Demo Instruments", "serial_number": "V-005"}},
    "custom_sensor": {"label": "Custom sensor", "category": "Sensor", "icon": "◉", "profile": "custom-sensor", "kind": "group", "color": "blue", "required": ["manufacturer", "serial_number"], "defaults": {"path": "/experiment/instrumentation/custom_01", "quantity": "measured quantity", "unit": "1", "manufacturer": "Demo Instruments", "serial_number": "S-006"}},
    "controller": {"label": "Controller", "category": "Equipment", "icon": "▣", "profile": "controller", "kind": "group", "color": "green", "required": ["model"], "defaults": {"path": "/experiment/equipment/controller_01", "model": "Controller demonstrator"}},
    "power_supply": {"label": "Power supply", "category": "Equipment", "icon": "▣", "profile": "power-supply", "kind": "group", "color": "green", "required": ["model"], "defaults": {"path": "/experiment/equipment/power_supply_01", "model": "Power supply demonstrator"}},
    "data_processor": {"label": "Data processor", "category": "Equipment", "icon": "▣", "profile": "data-processor", "kind": "group", "color": "green", "required": ["software"], "defaults": {"path": "/experiment/equipment/data_processor_01", "software": "Python"}},
    "data_processing": {"label": "Data processing", "category": "Process", "icon": "⚙", "profile": "processing", "kind": "group", "color": "amber", "required": ["method"], "defaults": {"path": "/experiment/processing/data_processing_01", "method": "Processing step"}},
    "filter_process": {"label": "Filtering / averaging", "category": "Process", "icon": "⚙", "profile": "filtering", "kind": "group", "color": "amber", "required": ["method"], "defaults": {"path": "/experiment/processing/filtering_01", "method": "Averaging"}},
    "unit_conversion": {"label": "Unit conversion", "category": "Process", "icon": "⚙", "profile": "unit-conversion", "kind": "group", "color": "amber", "required": ["method"], "defaults": {"path": "/experiment/processing/unit_conversion_01", "method": "Unit conversion"}},
    "custom_process": {"label": "Custom process", "category": "Process", "icon": "⚙", "profile": "custom-process", "kind": "group", "color": "amber", "required": ["method"], "defaults": {"path": "/experiment/processing/custom_process_01", "method": "Custom process"}},
}

ALLOWED_DTYPES = {"float32", "float64", "int32", "int64", "uint8", "uint16"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,90}$")
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")


def demo() -> dict[str, Any]:
    def n(id, type, label, x, y, **overrides):
        return {"id": id, "type": type, "label": label, "x": x, "y": y, "config": {**CATALOG[type]["defaults"], **overrides}}
    nodes = [
        n("fan", "fan", "Radial Fan", 60, 270),
        n("pressure", "pressure_sensor", "Pressure Sensor", 310, 104),
        n("temperature", "temperature_sensor", "Temperature Sensor", 310, 288),
        n("torque", "torque_sensor", "Torque Sensor", 310, 472),
        n("daq", "daq", "DAQ / Logger", 602, 268),
        n("process", "process", "Write to HDF5", 876, 270),
        n("root", "group", "Experiment Group", 1170, 92),
        n("velocity", "dataset", "Velocity Dataset", 1170, 272, path="/experiment/measurements/velocity", quantity="velocity", unit="m/s", dtype="float64", shape="0"),
        n("pressure_data", "dataset", "Pressure Dataset", 1170, 453, path="/experiment/measurements/pressure", quantity="pressure", unit="Pa", dtype="float64", shape="0"),
        n("metadata", "metadata", "Experiment Metadata", 865, 528),
    ]
    edges = []
    for src, dest, relation in [
        ("fan", "pressure", "instrumented_by"), ("fan", "temperature", "instrumented_by"),
        ("fan", "torque", "instrumented_by"), ("pressure", "daq", "acquired_by"),
        ("temperature", "daq", "acquired_by"), ("torque", "daq", "acquired_by"),
        ("daq", "process", "processed_by"), ("process", "root", "writes_to"),
        ("process", "velocity", "writes_to"), ("process", "pressure_data", "writes_to"),
        ("metadata", "root", "describes"),
    ]:
        edges.append({"id": f"e_{src}_{dest}", "source": src, "target": dest, "relation": relation})
    return {"name": "Radial fan experiment", "version": "0.1", "nodes": nodes, "edges": edges}


def normalize(design: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(design, dict) or not isinstance(design.get("nodes"), list) or not isinstance(design.get("edges", []), list):
        raise ValueError("Expected a design containing arrays 'nodes' and 'edges'.")
    nodes = design["nodes"]
    edges = design.get("edges", [])
    if len(nodes) > 250 or len(edges) > 1000:
        raise ValueError("POC limit: 250 nodes and 1000 edges.")
    ids = set()
    paths: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") not in CATALOG:
            raise ValueError("Unknown node type.")
        id = node.get("id", "")
        if not isinstance(id, str) or not ID_RE.fullmatch(id) or id in ids:
            raise ValueError("Node IDs must be unique alphanumeric strings (hyphens and underscores allowed).")
        ids.add(id)
        if not isinstance(node.get("config", {}), dict):
            raise ValueError(f"Node {id}: configuration must be an object.")
        config = node.get("config", {})
        for k, v in config.items():
            if not KEY_RE.fullmatch(str(k)) or not isinstance(v, (str, int, float, bool, type(None))):
                raise ValueError(f"Node {id}: unsupported metadata key or value: {k}")
            if isinstance(v, str) and len(v) > 3000:
                raise ValueError(f"Node {id}: metadata field {k} too long.")
        kind = CATALOG[node["type"]]["kind"]
        if kind:
            path = config.get("path", "")
            if not isinstance(path, str) or not path.startswith("/") or path == "/" or "//" in path or path.endswith("/") or "\x00" in path or len(path) > 512:
                raise ValueError(f"Node {id}: invalid absolute HDF5 path.")
            if path.startswith("/__design__"):
                raise ValueError("/__design__ is a reserved path.")
            if path in paths:
                raise ValueError(f"Nodes {paths[path]} and {id} share HDF5 path {path}.")
            paths[path] = id
        if config.get("required_fields"):
            extra = config["required_fields"]
            if not isinstance(extra, str):
                raise ValueError(f"Node {id}: required_fields must be a comma-separated string.")
            for field in [x.strip() for x in extra.split(",") if x.strip()]:
                if not KEY_RE.fullmatch(field) or field in {"path", "dtype", "shape", "profile_uri", "required_fields"}:
                    raise ValueError(f"Node {id}: invalid custom required field: {field}")
        if kind == "dataset":
            if config.get("dtype", "float64") not in ALLOWED_DTYPES:
                raise ValueError(f"Node {id}: unsupported numeric dtype.")
            _parse_shape(str(config.get("shape", "0")))
    dataset_paths = {n["config"]["path"] for n in nodes if CATALOG[n["type"]]["kind"] == "dataset"}
    for path in paths:
        parts = path.strip("/").split("/")
        for i in range(1, len(parts)):
            ancestor = "/" + "/".join(parts[:i])
            if ancestor in dataset_paths:
                raise ValueError(f"HDF5 dataset at {ancestor} cannot contain child object {path}.")
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("source") not in ids or edge.get("target") not in ids:
            raise ValueError("Every edge must connect existing nodes.")
    return design


def _parse_shape(raw: str) -> tuple[int, ...]:
    try:
        dims = tuple(int(x.strip()) for x in raw.split(","))
    except (ValueError, TypeError) as exc:
        raise ValueError("Dataset shape must be comma-separated nonnegative integers, e.g. '0' or '0,3'.") from exc
    if not 1 <= len(dims) <= 5 or any(x < 0 or x > 50000 for x in dims):
        raise ValueError("Dataset shape must contain 1–5 nonnegative dimensions <=50000.")
    if any(dim == 0 for dim in dims[1:]):
        raise ValueError("Only the first dataset dimension may be 0 (resizable); subsequent dimensions must be positive.")
    if np.prod(dims, dtype=np.int64) > 2_000_000:
        raise ValueError("Template datasets are limited to 2 million elements.")
    return dims


def _profile_required(node: dict[str, Any]) -> list[str]:
    required = list(CATALOG[node["type"]]["required"])
    extra = str(node.get("config", {}).get("required_fields", ""))
    for field in [x.strip() for x in extra.split(",") if x.strip()]:
        if field not in required:
            required.append(field)
    return required


def _profile_iri(node: dict[str, Any]) -> str:
    explicit = str(node.get("config", {}).get("profile_uri", "")).strip()
    return explicit or str(PROFILES[CATALOG[node["type"]]["profile"]])


def _meta_key(key: str):
    return META[key]


def build_shapes(design: dict[str, Any]) -> Graph:
    """Produce a self-contained SHACL document for RDF projection of HDF5 objects.

    The generated shape validates RDF *describing* HDF5, not raw HDF5 bytes.
    Actual file-level checks are implemented separately in validate_hdf5().
    """
    normalize(design)
    graph = Graph()
    graph.bind("sh", SH)
    graph.bind("h5", H5)
    graph.bind("meta", META)
    graph.bind("xsd", XSD)
    for node in design["nodes"]:
        info = CATALOG[node["type"]]
        if not info["kind"]:
            continue
        cfg = node.get("config", {})
        shape = URIRef(SHAPE_BASE + node["id"])
        focus = URIRef(NODE_BASE + node["id"])
        graph.add((shape, RDF.type, SH.NodeShape))
        graph.add((shape, SH.targetNode, focus))
        graph.add((shape, H5.profileSource, URIRef(_profile_iri(node))))
        for predicate, value in ((H5.path, cfg["path"]), (H5.kind, info["kind"]), (H5.profile, _profile_iri(node))):
            _shape_property(graph, shape, predicate, required=True, has_value=value)
        if info["kind"] == "dataset":
            for key, pred in (("dtype", H5.dtype), ("shape", H5.shape)):
                _shape_property(graph, shape, pred, required=True, has_value=str(cfg.get(key, "float64" if key == "dtype" else "0")))
        for field in _profile_required(node):
            _shape_property(graph, shape, _meta_key(field), required=True)
        for field in ("unit", "quantity"):
            if cfg.get(field):
                _shape_property(graph, shape, _meta_key(field), required=True, has_value=str(cfg[field]))
    return graph


def _shape_property(graph, shape, predicate, required=True, has_value=None):
    prop = BNode()
    graph.add((shape, SH.property, prop))
    graph.add((prop, SH.path, predicate))
    if required:
        graph.add((prop, SH.minCount, Literal(1, datatype=XSD.integer)))
    if has_value is not None:
        # SHACL hasValue uses literals for all HDF5 metadata; profileSource is a URI only for provenance.
        graph.add((prop, SH.hasValue, Literal(has_value)))


def shacl_turtle(design: dict[str, Any]) -> str:
    return build_shapes(design).serialize(format="turtle")


def hdf5_template(design: dict[str, Any]) -> bytes:
    normalize(design)
    # h5py's 'core' virtual filesystem lets us export an HDF5 file without a disk path.
    with h5py.File("template.h5", "w", driver="core", backing_store=False) as f:
        f.attrs["generated_by"] = "FAIR HDF5 Design Suite (POC)"
        f.attrs["design_schema_version"] = "0.1"
        f.attrs["validation_note"] = "Semantic SHACL validation applies to an RDF projection of this file."
        # First create all groups (explicit + implicit parent groups).
        group_nodes = sorted((n for n in design["nodes"] if CATALOG[n["type"]]["kind"] == "group"), key=lambda n: n["config"]["path"].count("/"))
        for node in group_nodes:
            path = node["config"]["path"]
            if path in f and not isinstance(f[path], h5py.Group):
                raise ValueError(f"Cannot create group at {path}: dataset already exists.")
            f.require_group(path)
        for node in design["nodes"]:
            kind = CATALOG[node["type"]]["kind"]
            if not kind:
                continue
            cfg = node["config"]
            path = cfg["path"]
            if kind == "group":
                obj = f.require_group(path)
            else:
                parent = path.rsplit("/", 1)[0] or "/"
                f.require_group(parent)
                if path in f:
                    raise ValueError(f"Cannot create dataset at {path}: object already exists.")
                shape = _parse_shape(str(cfg.get("shape", "0")))
                obj = f.create_dataset(path, shape=shape, maxshape=(None, *shape[1:]), dtype=cfg.get("dtype", "float64"), chunks=True)
                obj.attrs["designed_shape"] = str(cfg.get("shape", "0"))
            obj.attrs["design_node_id"] = node["id"]
            obj.attrs["design_label"] = str(node.get("label", node["type"]))
            obj.attrs["profile_uri"] = _profile_iri(node)
            obj.attrs["design_type"] = node["type"]
            for k, v in cfg.items():
                if k in {"path", "shape", "dtype", "profile_uri", "required_fields"} or v is None or v == "":
                    continue
                obj.attrs[k] = v
        # Store the model used to create this template (and its relationship graph).
        design_group = f.require_group("/__design__")
        design_group.attrs["generated_by"] = "FAIR HDF5 Design Suite"
        design_group.create_dataset("blueprint_json", data=json.dumps(design, ensure_ascii=False), dtype=h5py.string_dtype("utf-8"))
        f.flush()
        return f.id.get_file_image()


def rdf_from_hdf5(design: dict[str, Any], f: h5py.File) -> Graph:
    graph = Graph()
    graph.bind("h5", H5)
    graph.bind("meta", META)
    for node in design["nodes"]:
        kind = CATALOG[node["type"]]["kind"]
        if not kind:
            continue
        path = node["config"]["path"]
        if path not in f:
            continue
        obj = f[path]
        subject = URIRef(NODE_BASE + node["id"])
        graph.add((subject, H5.path, Literal(path)))
        graph.add((subject, H5.kind, Literal("dataset" if isinstance(obj, h5py.Dataset) else "group")))
        if "profile_uri" in obj.attrs:
            graph.add((subject, H5.profile, Literal(str(obj.attrs["profile_uri"]))))
        if isinstance(obj, h5py.Dataset):
            graph.add((subject, H5.dtype, Literal(str(obj.dtype))))
            graph.add((subject, H5.shape, Literal(str(obj.attrs.get("designed_shape", ",".join(map(str, obj.shape)))))))
        for key in set(_profile_required(node) + ["unit", "quantity"]):
            if key in obj.attrs and str(obj.attrs[key]).strip():
                graph.add((subject, _meta_key(key), Literal(str(obj.attrs[key]))))
    return graph


def _simple_shacl_check(shapes: Graph, rdf: Graph) -> list[dict[str, str]]:
    """Implements only the minCount and hasValue predicates generated by this POC.

    This fallback MUST NOT be marketed as a general-purpose SHACL validator.
    """
    issues = []
    for shape in shapes.subjects(RDF.type, SH.NodeShape):
        for focus in shapes.objects(shape, SH.targetNode):
            for prop in shapes.objects(shape, SH.property):
                paths = list(shapes.objects(prop, SH.path))
                if not paths:
                    continue
                predicate = paths[0]
                values = list(rdf.objects(focus, predicate))
                if (prop, SH.minCount, Literal(1, datatype=XSD.integer)) in shapes and not values:
                    issues.append({"path": str(focus), "rule": str(predicate), "message": "Required RDF property is missing."})
                expected = list(shapes.objects(prop, SH.hasValue))
                if expected and expected[0] not in values:
                    issues.append({"path": str(focus), "rule": str(predicate), "message": f"Expected RDF value: {expected[0]}"})
    return issues


def validate_hdf5(design: dict[str, Any], content: bytes) -> dict[str, Any]:
    """Check HDF5 structure/attributes and RDF graph against generated SHACL."""
    normalize(design)
    issues: list[dict[str, str]] = []
    checks = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=".h5") as tmp:
            tmp.write(content)
            tmp.flush()
            with h5py.File(tmp.name, "r") as f:
                for node in design["nodes"]:
                    info = CATALOG[node["type"]]
                    if not info["kind"]:
                        continue
                    cfg = node.get("config", {})
                    path = cfg["path"]
                    checks += 1
                    if path not in f:
                        issues.append({"path": path, "rule": "existence", "message": "Required HDF5 object does not exist."})
                        continue
                    obj = f[path]
                    expected_kind = info["kind"]
                    actual_kind = "dataset" if isinstance(obj, h5py.Dataset) else "group"
                    if expected_kind != actual_kind:
                        issues.append({"path": path, "rule": "object type", "message": f"Expected {expected_kind}, found {actual_kind}."})
                        continue
                    if actual_kind == "dataset":
                        checks += 2
                        if str(obj.dtype) != str(cfg.get("dtype", "float64")):
                            issues.append({"path": path, "rule": "dtype", "message": f"Expected {cfg.get('dtype', 'float64')}, found {obj.dtype}."})
                        expected_shape = _parse_shape(str(cfg.get("shape", "0")))
                        if len(obj.shape) != len(expected_shape) or any((spec > 0 and actual != spec) for spec, actual in zip(expected_shape, obj.shape)):
                            issues.append({"path": path, "rule": "shape", "message": f"Expected dimensions {expected_shape} (0 means variable), found {obj.shape}."})
                    for field in _profile_required(node):
                        checks += 1
                        if field not in obj.attrs or not str(obj.attrs[field]).strip():
                            issues.append({"path": path, "rule": field, "message": f"Required metadata '{field}' is missing."})
                    for field in ("unit", "quantity"):
                        if cfg.get(field):
                            checks += 1
                            if str(obj.attrs.get(field, "")) != str(cfg[field]):
                                issues.append({"path": path, "rule": field, "message": f"Expected {field} = {cfg[field]}."})
                shapes = build_shapes(design)
                rdf = rdf_from_hdf5(design, f)
                try:
                    from pyshacl import validate as shacl_validate
                    conforms, report_graph, _ = shacl_validate(rdf, shacl_graph=shapes, inference="none", abort_on_first=False)
                    shacl_issues = []
                    if not conforms:
                        for r in report_graph.subjects(RDF.type, SH.ValidationResult):
                            shacl_issues.append({
                                "path": str(next(report_graph.objects(r, SH.focusNode), "")),
                                "rule": str(next(report_graph.objects(r, SH.resultPath), "SHACL")),
                                "message": str(next(report_graph.objects(r, SH.resultMessage), "SHACL violation")),
                            })
                    engine = "pySHACL"
                except ImportError:
                    shacl_issues = _simple_shacl_check(shapes, rdf)
                    engine = "POC subset (minCount and hasValue only); install pyshacl for complete SHACL Core"
                checks += len(list(shapes.subjects(RDF.type, SH.NodeShape)))
                # Include SHACL issues even if they overlap structural issues; clearly categorized.
                for issue in shacl_issues:
                    issue["layer"] = "SHACL/RDF"
                for issue in issues:
                    issue["layer"] = "HDF5"
                issues.extend(shacl_issues)
    except OSError as exc:
        raise ValueError("Uploaded file is not a readable HDF5 file.") from exc
    return {"conforms": not issues, "checks": checks, "issue_count": len(issues), "issues": issues[:250], "shacl_engine": engine,
            "note": "Conformance concerns the modeled HDF5 structure and RDF-projected metadata, not physical correctness or full FAIR compliance."}


def structure_preview(design: dict[str, Any]) -> dict[str, Any]:
    normalize(design)
    paths = []
    for n in design["nodes"]:
        kind = CATALOG[n["type"]]["kind"]
        if kind:
            paths.append({"path": n["config"]["path"], "kind": kind, "label": n.get("label", n["type"]), "profile": _profile_iri(n)})
    return {"objects": sorted(paths, key=lambda x: x["path"]), "profiles": len(paths), "node_count": len(design["nodes"]), "edge_count": len(design.get("edges", []))}
