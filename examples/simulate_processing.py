"""Demonstrate pre-population of HDF5 setup metadata + later numeric processing.

The numerical samples here are synthetic examples, NOT actual lab measurements.
Run from the project root: python examples/simulate_processing.py
"""
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import demo, hdf5_template, validate_hdf5

blueprint = demo()
out = Path(__file__).resolve().parent / "synthetic_measured_data.h5"
out.write_bytes(hdf5_template(blueprint))

with h5py.File(out, "r+") as file:
    # The sensor setup, instrument serial numbers, units, and group hierarchy
    # are already present: only numerical results need to be written.
    t = np.linspace(0, 10, 1000)
    pressure = file["/experiment/measurements/pressure"]
    pressure.resize((len(t),))
    pressure[:] = 120 + 3 * np.sin(2 * np.pi * t)
    velocity = file["/experiment/measurements/velocity"]
    velocity.resize((len(t),))
    velocity[:] = 4 + .3 * np.cos(2 * np.pi * t)
    file["/experiment/metadata"].attrs["data_origin"] = "synthetic demonstration — not real laboratory measurements"

report = validate_hdf5(blueprint, out.read_bytes())
print(f"Wrote {out}")
print(f"Validation conforms: {report['conforms']} ({report['checks']} checks; {report['issue_count']} findings)")
if not report["conforms"]:
    for issue in report['issues'][:10]:
        print(' -', issue['path'], issue['message'])
