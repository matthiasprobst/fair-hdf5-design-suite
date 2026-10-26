"""Bundled synthetic examples; each account receives independent project copies."""

from copy import deepcopy

from .catalog import CATALOG, SEED_DIR, demo
from .data_nodes import CSV_DEFAULTS

EXAMPLE_CSV_FILENAME = "measurements.csv"


def example_csv():
    return (SEED_DIR / EXAMPLE_CSV_FILENAME).read_bytes()


def csv_example():
    name = "Example: CSV to HDF5"
    nodes = [
        {
            "id": "csv_measurements",
            "type": "csv_source",
            "label": "Example CSV measurements",
            "x": 80,
            "y": 230,
            "config": {
                **deepcopy(CSV_DEFAULTS),
                "delimiter": ";",
                "decimal_separator": ",",
                "filename": EXAMPLE_CSV_FILENAME,
                "columns": ["time", "pressure", "sample"],
                "example_file": EXAMPLE_CSV_FILENAME,
            },
        }
    ]
    edges = []
    for index, (identifier, label, dtype, quantity, unit) in enumerate(
        [
            ("time", "Time", "float64", "time", "s"),
            ("pressure", "Pressure", "float64", "pressure", "Pa"),
            ("sample", "Sample name", "string", "sample identifier", "1"),
        ]
    ):
        nodes.append(
            {
                "id": identifier,
                "type": "dataset",
                "label": label,
                "x": 440,
                "y": 40 + index * 210,
                "config": {
                    **deepcopy(CATALOG["dataset"]["defaults"]),
                    "path": f"/data/{identifier}",
                    "dtype": dtype,
                    "shape": "0",
                    "quantity": quantity,
                    "unit": unit,
                },
            }
        )
        edges.append(
            {
                "id": f"csv_to_{identifier}",
                "source": "csv_measurements",
                "target": identifier,
                "relation": "provides_data",
                "kind": "data",
                "column_index": index,
            }
        )
    return {"name": name, "version": "0.1", "nodes": nodes, "edges": edges}


def bundled_examples():
    fan = demo()
    fan["name"] = "Example: Radial fan experiment"
    return [
        {
            "id": "radial-fan",
            "blueprint": fan,
            "description": "Explore an experiment workflow with sensors, metadata, HDF5 paths and validation. This is your own editable copy.",
        },
        {
            "id": "csv-measurements",
            "blueprint": csv_example(),
            "description": "Build HDF5 from synthetic CSV data: time, pressure and Unicode sample names. Open the CSV Source and choose Load example CSV, then Build HDF5 with data. This is your own editable copy.",
        },
    ]
