"""Bundled legacy defaults and example design; runtime catalog lives in the repository."""
import json
from pathlib import Path
from typing import Any
from rdflib import Graph, URIRef
from rdflib.namespace import SH

SEED_DIR = Path(__file__).parent / "seeds"

def seed_templates():
    templates = json.loads((SEED_DIR / "templates.json").read_text())
    for identifier, info in templates.items():
        info["profile_ttl"] = (SEED_DIR / f"{identifier}.ttl").read_text()
    return templates

# Compatibility view for existing examples. Rules are derived from bundled SHACL.
CATALOG = seed_templates()
for info in CATALOG.values():
    graph = Graph().parse(data=info["profile_ttl"], format="turtle")
    info["required"] = [info["mapping"][str(graph.value(p, SH.path))] for p in graph.objects(URIRef(info["shape"]), SH.property) if int(graph.value(p, SH.minCount) or 0) == 1]


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
