"""Validate editable storage envelopes without requiring a finished design."""

import json
import math
import re
from copy import deepcopy

from .access import fail
from .templates import validate_snapshot


def editable_blueprint(value, settings, catalog):
    def invalid():
        fail(422, "invalid_blueprint", "Invalid blueprint storage format.")

    if not isinstance(value, dict) or not all(
        isinstance(value.get(k), str) for k in ("name", "version")
    ):
        invalid()
    nodes, edges = value.get("nodes"), value.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        invalid()
    if len(nodes) > settings.max_nodes or len(edges) > settings.max_edges:
        fail(422, "graph_limit", "The blueprint exceeds the configured graph limits.")
    ids, edge_ids = set(), set()
    result = {"name": value["name"], "version": value["version"], "nodes": [], "edges": []}

    def scalar(item):
        return isinstance(item, (str, bool)) or finite_number(item)

    def finite_number(item):
        try:
            return type(item) in (int, float) and math.isfinite(item)
        except OverflowError:
            return False

    for node in nodes:
        if not isinstance(node, dict):
            invalid()
        identifier = node.get("id")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,90}", identifier)
            or identifier in ids
        ):
            invalid()
        if not all(isinstance(node.get(k), str) for k in ("type", "label")):
            invalid()
        if not all(finite_number(node.get(k)) for k in ("x", "y")):
            invalid()
        config = node.get("config")
        if not isinstance(config, dict):
            invalid()
        for key, item in config.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", key):
                invalid()
            if (
                item is not None
                and not scalar(item)
                and not (
                    isinstance(item, list)
                    and all(
                        scalar(v)
                        and (
                            type(v) is type(item[0])
                            or (type(v) in (int, float) and type(item[0]) in (int, float))
                        )
                        for v in item
                    )
                )
            ):
                invalid()
        saved = {k: deepcopy(node[k]) for k in ("id", "type", "label", "x", "y", "config")}
        if "template" in node:
            snapshot = validate_snapshot(node["template"], settings=settings)
            if snapshot["id"] != node["type"]:
                invalid()
            saved["template"] = snapshot
        else:
            saved["template"] = catalog.get(node["type"], 1)
        ids.add(identifier)
        result["nodes"].append(saved)
    for edge in edges:
        if not isinstance(edge, dict) or not all(
            isinstance(edge.get(k), str) for k in ("id", "source", "target", "relation")
        ):
            invalid()
        if (
            not edge["id"]
            or edge["id"] in edge_ids
            or edge["source"] not in ids
            or edge["target"] not in ids
        ):
            invalid()
        saved = {k: edge[k] for k in ("id", "source", "target", "relation")}
        if "field_id" in edge or "predicate" in edge:
            if not all(isinstance(edge.get(k), str) for k in ("field_id", "predicate")):
                invalid()
            saved.update(field_id=edge["field_id"], predicate=edge["predicate"])
        edge_ids.add(edge["id"])
        result["edges"].append(saved)
    try:
        encoded = json.dumps(result, allow_nan=False)
    except (ValueError, TypeError):
        invalid()
    if len(encoded.encode()) > settings.max_blueprint_bytes:
        fail(413, "blueprint_too_large", "The blueprint is too large to save.")
    return result
