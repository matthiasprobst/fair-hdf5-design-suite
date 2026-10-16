"""Illustrative local profiles and demonstration blueprint."""
from typing import Any

# A small local profile catalog. This is a POC substitute for a future MPS import.
CATALOG: dict[str, dict[str, Any]] = {
    "fan": {"label": "System", "category": "Experiment", "icon": "◉", "profile": "fan", "kind": "group", "color": "purple", "required": ["model", "manufacturer"], "defaults": {"path": "/experiment/equipment/fan", "model": "RF-120", "manufacturer": "Lab demonstrator"}},
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
