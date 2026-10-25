import io
import unittest

import h5py
from fair_hdf5.compat import demo, hdf5_template, normalize, shacl_turtle, validate_hdf5
from rdflib import Graph
from support import CatalogTestCase


class BackendTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.d = demo()

    def test_shacl_is_valid_turtle_and_targets_nodes(self):
        graph = Graph().parse(data=shacl_turtle(self.d), format="turtle")
        self.assertGreater(len(graph), 150)

    def test_generates_real_hdf5_and_prepopulates_sensor_metadata(self):
        data = hdf5_template(self.d)
        with h5py.File(io.BytesIO(data), "r") as f:
            self.assertIn("/experiment/equipment/fan", f)
            sensor = f["/experiment/instrumentation/pressure_01"]
            self.assertEqual(sensor.attrs["quantity"], "pressure")
            self.assertEqual(sensor.attrs["unit"], "Pa")
            self.assertEqual(sensor.attrs["serial_number"], "P-001")
            pressure = f["/experiment/measurements/pressure"]
            self.assertEqual(pressure.shape, (0,))
            self.assertIn("/__design__/blueprint_json", f)
        result = validate_hdf5(self.d, data)
        self.assertTrue(result["conforms"], result["issues"])

    def test_missing_sensor_metadata_fails(self):
        data = hdf5_template(self.d)
        with h5py.File(io.BytesIO(data), "r+") as f:
            del f["/experiment/instrumentation/pressure_01"].attrs["calibration_date"]
            f.flush()
            changed = f.id.get_file_image()
        report = validate_hdf5(self.d, changed)
        self.assertFalse(report["conforms"])
        self.assertTrue(any("calibration_date" in x["rule"] for x in report["issues"]))

    def test_custom_required_profile_field_is_validated(self):
        sensor = next(n for n in self.d["nodes"] if n["id"] == "pressure")
        sensor["config"]["required_fields"] = "mounting_location"
        generated = hdf5_template(self.d)
        report = validate_hdf5(self.d, generated)
        self.assertFalse(report["conforms"])
        self.assertTrue(any("mounting_location" in issue["rule"] for issue in report["issues"]))
        sensor["config"]["mounting_location"] = "inlet"
        regenerated = hdf5_template(self.d)
        self.assertTrue(validate_hdf5(self.d, regenerated)["conforms"])

    def test_absent_group_detected(self):
        data = hdf5_template(self.d)
        with h5py.File(io.BytesIO(data), "r+") as f:
            del f["/experiment/instrumentation/pressure_01"]
            f.flush()
            changed = f.id.get_file_image()
        report = validate_hdf5(self.d, changed)
        self.assertFalse(report["conforms"])
        self.assertTrue(any(x["rule"] == "existence" for x in report["issues"]))

    def test_duplicate_hdf5_paths_disallowed(self):
        self.d["nodes"][-1]["config"]["path"] = "/experiment"
        with self.assertRaises(ValueError):
            normalize(self.d)

    def test_bad_hdf5_type_disallowed(self):
        dataset = next(n for n in self.d["nodes"] if n["type"] == "dataset")
        dataset["config"]["dtype"] = "object"
        with self.assertRaises(ValueError):
            normalize(self.d)


if __name__ == "__main__":
    unittest.main()
