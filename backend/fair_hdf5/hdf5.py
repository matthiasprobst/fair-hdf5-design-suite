"""HDF5 materialization, request-owned files, and structural checks."""

import json
import tempfile
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import h5py
import numpy as np

from .errors import DesignError
from .profiles import node_template
from .profiles import profile_iri as _profile_iri
from .profiles import profile_required as _profile_required
from .provenance import DECLARATION_NOTE, design_metadata


def dtype_name(dtype):
    string = h5py.check_string_dtype(dtype)
    return (
        "string" if string and string.encoding == "utf-8" and string.length is None else str(dtype)
    )


def hdf5_template(
    design: dict[str, Any],
    dataset_shapes: dict[str, tuple[int, ...]],
    dataset_values: dict[str, np.ndarray] | None = None,
) -> bytes:
    # h5py's 'core' virtual filesystem lets us export an HDF5 file without a disk path.
    with h5py.File(f"template-{uuid4().hex}.h5", "w", driver="core", backing_store=False) as f:
        f.attrs["generated_by"] = "FAIR HDF5 Design Suite (POC)"
        f.attrs["design_schema_version"] = "0.1"
        f.attrs["validation_note"] = (
            "Semantic SHACL validation applies to an RDF projection of this file."
        )
        # First create all groups (explicit + implicit parent groups).
        group_nodes = sorted(
            (n for n in design["nodes"] if node_template(n)["kind"] == "group"),
            key=lambda n: n["config"]["path"].count("/"),
        )
        for node in group_nodes:
            path = node["config"]["path"]
            if path in f and not isinstance(f[path], h5py.Group):
                raise DesignError(f"Cannot create group at {path}: dataset already exists.")
            f.require_group(path)
        for node in design["nodes"]:
            kind = node_template(node)["kind"]
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
                data = (dataset_values or {}).get(node["id"])
                shape = data.shape if data is not None else dataset_shapes[node["id"]]
                obj = f.create_dataset(
                    path,
                    data=data,
                    shape=shape,
                    maxshape=(None, *shape[1:]),
                    dtype=h5py.string_dtype("utf-8")
                    if cfg.get("dtype") == "string"
                    else cfg.get("dtype", "float64"),
                    chunks=True,
                )
                obj.attrs["designed_shape"] = str(cfg.get("shape", "0"))
            obj.attrs["design_node_id"] = node["id"]
            obj.attrs["design_label"] = str(node.get("label", node["type"]))
            obj.attrs["profile_uri"] = _profile_iri(node)
            obj.attrs["design_type"] = node["type"]
            for k, v in cfg.items():
                if (
                    k in {"path", "shape", "dtype", "profile_uri", "required_fields"}
                    or v is None
                    or v == ""
                ):
                    continue
                if isinstance(v, list):
                    v = [item for item in v if item != ""]
                    if not v:
                        continue
                    obj.attrs.create(
                        k,
                        np.asarray(
                            v, dtype=h5py.string_dtype("utf-8") if isinstance(v[0], str) else None
                        ),
                    )
                else:
                    field = next(
                        (
                            field
                            for field in node_template(node).get("fields", [])
                            if field["key"] == k
                        ),
                        {},
                    )
                    if field.get("multiple"):
                        obj.attrs.create(
                            k,
                            np.asarray(
                                [v],
                                dtype=h5py.string_dtype("utf-8") if isinstance(v, str) else None,
                            ),
                        )
                    else:
                        obj.attrs[k] = v
        by_id = {node["id"]: node for node in design["nodes"]}
        references = {}
        for edge in design.get("edges", []):
            if not edge.get("predicate"):
                continue
            source, target = by_id[edge["source"]], by_id[edge["target"]]
            field = next(
                field
                for field in node_template(source)["fields"]
                if field["id"] == edge["field_id"]
            )
            references.setdefault((source["config"]["path"], field["key"]), set()).add(
                target["config"]["path"]
            )
        for (path, key), targets in references.items():
            f[path].attrs.create(
                key, np.array([f[target].ref for target in sorted(targets)], dtype=h5py.ref_dtype)
            )
        # Store the model used to create this template (and its relationship graph).
        design_group = f.require_group("/__design__")
        design_group.attrs["generated_by"] = "FAIR HDF5 Design Suite"
        design_group.create_dataset(
            "blueprint_json",
            data=json.dumps(design, ensure_ascii=False),
            dtype=h5py.string_dtype("utf-8"),
        )
        design_group.attrs["metadata_note"] = DECLARATION_NOTE
        design_group.create_dataset(
            "metadata_ttl",
            data=design_metadata(design).serialize(format="turtle"),
            dtype=h5py.string_dtype("utf-8"),
        )
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
        info = node_template(node)
        if not info["kind"]:
            continue
        cfg = node.get("config", {})
        path = cfg["path"]
        checks += 1
        if path not in f:
            issues.append(
                {
                    "path": path,
                    "rule": "existence",
                    "message": "Required HDF5 object does not exist.",
                }
            )
            continue
        obj = f[path]
        expected_kind = info["kind"]
        actual_kind = "dataset" if isinstance(obj, h5py.Dataset) else "group"
        if expected_kind != actual_kind:
            issues.append(
                {
                    "path": path,
                    "rule": "object type",
                    "message": f"Expected {expected_kind}, found {actual_kind}.",
                }
            )
            continue
        if actual_kind == "dataset":
            checks += 2
            if dtype_name(obj.dtype) != str(cfg.get("dtype", "float64")):
                issues.append(
                    {
                        "path": path,
                        "rule": "dtype",
                        "message": f"Expected {cfg.get('dtype', 'float64')}, found {obj.dtype}.",
                    }
                )
            expected_shape = dataset_shapes[node["id"]]
            if len(obj.shape) != len(expected_shape) or any(
                (spec > 0 and actual != spec)
                for spec, actual in zip(expected_shape, obj.shape, strict=True)
            ):
                issues.append(
                    {
                        "path": path,
                        "rule": "shape",
                        "message": f"Expected dimensions {expected_shape} (0 means variable), found {obj.shape}.",
                    }
                )
        for field in {field["key"]: field for field in info.get("fields", [])}.values():
            key = field["key"]
            expected_references = set()
            if field.get("kind") == "reference":
                target_ids = {
                    edge["target"]
                    for edge in design.get("edges", [])
                    if edge["source"] == node["id"] and edge.get("predicate") == field["predicate"]
                }
                expected_references = {
                    n["config"]["path"] for n in design["nodes"] if n["id"] in target_ids
                }
                if expected_references and key not in obj.attrs:
                    issues.append(
                        {
                            "path": path,
                            "rule": key,
                            "message": "Expected semantic relationships are missing from HDF5.",
                        }
                    )
            if key in obj.attrs:
                checks += 1
                value = obj.attrs[key]
                if field.get("kind") == "reference":
                    if (
                        not isinstance(value, np.ndarray)
                        or value.ndim != 1
                        or h5py.check_dtype(ref=value.dtype) is None
                    ):
                        issues.append(
                            {
                                "path": path,
                                "rule": key,
                                "message": "Expected a one-dimensional HDF5 object-reference attribute.",
                            }
                        )
                        continue
                    expected_paths = {
                        n["config"]["path"] for n in design["nodes"] if node_template(n)["kind"]
                    }
                    actual_references = set()
                    for reference in value:
                        try:
                            if not reference or f[reference].name not in expected_paths:
                                raise ValueError("Unknown reference target")
                            actual_references.add(f[reference].name)
                        except (ValueError, KeyError, TypeError):
                            issues.append(
                                {
                                    "path": path,
                                    "rule": key,
                                    "message": "Dangling or unknown HDF5 object reference.",
                                }
                            )
                    if actual_references != expected_references:
                        issues.append(
                            {
                                "path": path,
                                "rule": key,
                                "message": "HDF5 relationships differ from the design.",
                            }
                        )
                    continue
                if (field.get("multiple") and getattr(value, "ndim", 0) != 1) or (
                    not field.get("multiple") and getattr(value, "shape", ()) != ()
                ):
                    issues.append(
                        {
                            "path": path,
                            "rule": key,
                            "message": f"Metadata '{key}' has an incompatible HDF5 scalar/list representation.",
                        }
                    )
        for field in _profile_required(node):
            checks += 1
            from .catalog import CATALOG

            strict_text = (node["type"] in CATALOG and info.get("revision", 1) == 1) or not any(
                f["key"] == field for f in info.get("fields", [])
            )
            if (
                field not in obj.attrs
                or (isinstance(obj.attrs[field], np.ndarray) and obj.attrs[field].size == 0)
                or (strict_text and not str(obj.attrs[field]).strip())
            ):
                issues.append(
                    {
                        "path": path,
                        "rule": field,
                        "message": f"Required metadata '{field}' is missing.",
                    }
                )
        for field in ("unit", "quantity"):
            if cfg.get(field) and not isinstance(cfg[field], list):
                checks += 1
                if str(obj.attrs.get(field, "")) != str(cfg[field]):
                    issues.append(
                        {
                            "path": path,
                            "rule": field,
                            "message": f"Expected {field} = {cfg[field]}.",
                        }
                    )
    return issues, checks
