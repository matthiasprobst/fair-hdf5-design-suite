"""Portable template normalization, independent of catalog storage and HTTP."""

import json
import math
from copy import deepcopy
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, SH

from .errors import DesignError
from .profile_bundles import bundle_graph, resolve_bundle
from .profile_schema import RESERVED, compile_profile, display_text, localized, profile_hash
from .settings import Settings
from .vocabulary import ID_RE, KEY_RE


def validate_snapshot(
    raw: dict[str, Any], build_related: bool = True, settings: Settings | None = None
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DesignError("Template must be an object.")
    if raw.get("schema_version") not in (None, 1, 2):
        raise DesignError("Unsupported template snapshot schema.")
    settings = settings or Settings()
    info = deepcopy(raw)
    info.pop("initial", None)
    info.pop("project_local", None)
    info.pop("project_revision", None)
    if not isinstance(info.get("id"), str) or not ID_RE.fullmatch(info["id"]):
        raise DesignError("Invalid template ID.")
    if type(info.get("revision")) is not int or info["revision"] < 1:
        raise DesignError("Invalid template revision.")
    if info.get("kind") not in ("group", "dataset"):
        raise DesignError("Invalid HDF5 object kind.")
    if "requires_pyshacl" in info and type(info["requires_pyshacl"]) is not bool:
        raise DesignError("Template engine requirement must be a boolean.")
    for key in ("label", "category", "icon", "color", "profile", "shape"):
        if not isinstance(info.get(key), str) or not info[key] or len(info[key]) > 2000:
            raise DesignError(f"Invalid template {key}.")
    if info["color"] not in (
        "blue",
        "green",
        "purple",
        "orange",
        "amber",
        "coral",
        "rose",
        "violet",
    ):
        raise DesignError("Unsupported template color.")
    mapping = info.get("mapping", {})
    if not isinstance(mapping, dict):
        raise DesignError("Field mapping must be an object.")
    info["source_uri"], info["documents"] = resolve_bundle(
        info.get("profile_ttl"),
        info.get("source_uri"),
        info.get("documents"),
        settings,
        fetch=False,
    )
    info["fields"] = compile_profile(
        info.get("profile_ttl"), info["shape"], mapping, info["documents"], info["source_uri"]
    )
    digest = profile_hash(info["profile_ttl"])
    if info.get("profile_hash", digest) != digest:
        raise DesignError("Profile snapshot hash does not match its Turtle.")
    info["profile_hash"] = digest
    info["mapping"] = {f["predicate"]: f["key"] for f in info["fields"]}
    info["required"] = list(
        dict.fromkeys(f["key"] for f in info["fields"] if f["required"] and f["kind"] == "literal")
    )
    defaults = info.get("defaults", {})
    if not isinstance(defaults, dict):
        raise DesignError("Defaults must be an object.")
    for key, value in defaults.items():
        if not KEY_RE.fullmatch(key) or not isinstance(
            value, (str, int, float, bool, list, type(None))
        ):
            raise DesignError("Defaults must contain scalar attribute values.")
        if isinstance(value, float) and not math.isfinite(value):
            raise DesignError("Defaults must be finite.")
        if key in RESERVED - {"path", "shape", "dtype", "profile_uri", "required_fields"}:
            raise DesignError(f"Reserved attribute: {key}")
    for f in info["fields"]:
        if f["kind"] == "reference":
            defaults.pop(f["key"], None)
            continue
        default = f.get("defaultValue", f.get("hasValue"))
        defaults.setdefault(
            f["key"],
            ([default] if default is not None else []) if f["multiple"] else (default or ""),
        )
    info["defaults"] = defaults
    info["schema_version"] = 2
    graph = bundle_graph(info["profile_ttl"], info["source_uri"], info["documents"])
    info["target_classes"] = sorted(
        str(v) for v in graph.objects(URIRef(info["shape"]), SH.targetClass)
    )
    info["titles"] = localized(graph, URIRef(info["shape"]), DCTERMS.title)
    info["descriptions"] = localized(graph, URIRef(info["shape"]), DCTERMS.description)
    info.pop("related_templates", None)
    if build_related:
        info["related_templates"] = _related_templates(info, graph, settings)
    return info


def _related_templates(info: dict[str, Any], graph: Graph, settings: Settings) -> dict[str, Any]:
    related = {}
    fingerprint = profile_hash(
        json.dumps(
            {
                "source": info["source_uri"],
                "root": info["profile_hash"],
                "imports": {uri: doc["hash"] for uri, doc in info["documents"].items()},
            },
            sort_keys=True,
        )
    )
    pending = {f["targetShape"] for f in info["fields"] if f["kind"] == "reference"}
    seen = {info["shape"]}
    while pending:
        shape_id = sorted(pending)[0]
        pending.remove(shape_id)
        if shape_id in seen:
            continue
        seen.add(shape_id)
        shape = URIRef(shape_id)
        identity = "profile_" + profile_hash(shape_id + fingerprint)[:20]
        child = {
            **info,
            "id": identity,
            "revision": 1,
            "shape": shape_id,
            "profile": shape_id,
            "label": display_text(localized(graph, shape, DCTERMS.title), shape_id),
            "kind": "group",
            "category": "Metadata",
            "icon": "metadata",
            "color": "violet",
            "mapping": {},
            "defaults": {"path": "/metadata/" + identity},
        }
        child = validate_snapshot(child, build_related=False, settings=settings)
        related[shape_id] = child
        pending.update(f["targetShape"] for f in child["fields"] if f["kind"] == "reference")
    return related
