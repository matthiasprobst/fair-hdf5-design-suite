"""Presentation of the materialized design structure."""
from typing import Any
from .profiles import node_template
from .profiles import profile_iri as _profile_iri

def structure_preview(design: dict[str, Any]) -> dict[str, Any]:
    paths = []
    for n in design["nodes"]:
        kind = node_template(n)["kind"]
        if kind:
            paths.append({"path": n["config"]["path"], "kind": kind, "label": n.get("label", n["type"]), "profile": _profile_iri(n)})
    return {"objects": sorted(paths, key=lambda x: x["path"]), "profiles": len(paths), "node_count": len(design["nodes"]), "edge_count": len(design.get("edges", []))}
