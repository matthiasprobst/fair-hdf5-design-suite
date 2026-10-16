"""HDF5 materialization, request-owned files, and structural checks."""
import json
import tempfile
from contextlib import contextmanager
from uuid import uuid4
from typing import Any
import h5py
from .catalog import CATALOG
from .errors import DesignError
from .profiles import profile_required as _profile_required, profile_iri as _profile_iri

def hdf5_template(design: dict[str, Any], dataset_shapes: dict[str, tuple[int, ...]]) -> bytes:
    # h5py's 'core' virtual filesystem lets us export an HDF5 file without a disk path.
    with h5py.File(f"template-{uuid4().hex}.h5", "w", driver="core", backing_store=False) as f:
        f.attrs["generated_by"] = "FAIR HDF5 Design Suite (POC)"
        f.attrs["design_schema_version"] = "0.1"
        f.attrs["validation_note"] = "Semantic SHACL validation applies to an RDF projection of this file."
        # First create all groups (explicit + implicit parent groups).
        group_nodes = sorted((n for n in design["nodes"] if CATALOG[n["type"]]["kind"] == "group"), key=lambda n: n["config"]["path"].count("/"))
        for node in group_nodes:
            path = node["config"]["path"]
            if path in f and not isinstance(f[path], h5py.Group):
                raise DesignError(f"Cannot create group at {path}: dataset already exists.")
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
                    raise DesignError(f"Cannot create dataset at {path}: object already exists.")
                shape = dataset_shapes[node["id"]]
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

@contextmanager
def open_uploaded_hdf5(content: bytes, temp_dir):
    # Storage failures propagate as server errors. Only an HDF5 open failure is input-related.
    with tempfile.NamedTemporaryFile(suffix=".h5", dir=temp_dir) as tmp:
        tmp.write(content)
        tmp.flush()
        try:
            with h5py.File(tmp.name, "r") as handle:
                yield handle
        except OSError as exc:
            if exc.errno is not None:
                raise
            raise DesignError("Uploaded file is not a readable HDF5 file.") from exc


def structural_checks(design, f, dataset_shapes):
    issues = []
    checks = 0
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
            expected_shape = dataset_shapes[node["id"]]
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
    return issues, checks
