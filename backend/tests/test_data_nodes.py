"""Input nodes remain portable without becoming semantic/HDF5 objects."""

import copy

from fair_hdf5.data_nodes import CSV_DEFAULTS
from fair_hdf5.errors import DesignError
from fair_hdf5.project_blueprint import editable_blueprint
from fair_hdf5.services import DesignService
from fair_hdf5.settings import Settings
from support import CatalogTestCase


def data_design():
    return {
        "name": "CSV experiment",
        "version": "0.1",
        "nodes": [
            {
                "id": "csv",
                "type": "csv_source",
                "label": "Measurements",
                "x": 0,
                "y": 0,
                "config": {**CSV_DEFAULTS, "columns": ["pressure"], "filename": "test.csv"},
            },
            {
                "id": "values",
                "type": "dataset",
                "label": "Pressure",
                "x": 300,
                "y": 0,
                "config": {
                    "path": "/data/pressure",
                    "dtype": "float64",
                    "shape": "0",
                    "quantity": "pressure",
                    "unit": "Pa",
                },
            },
        ],
        "edges": [
            {
                "id": "binding",
                "source": "csv",
                "target": "values",
                "relation": "provides_data",
                "kind": "data",
                "column_index": 0,
            }
        ],
    }


class DataNodeTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)
        self.service = DesignService(self.settings)

    def test_source_round_trip_and_template_independence(self):
        design = data_design()
        saved = editable_blueprint(design, self.settings, self.service.repository)
        self.assertEqual(saved["nodes"][0], design["nodes"][0])
        self.assertEqual(saved["edges"], design["edges"])
        self.assertEqual(self.service.preview(saved)["profiles"], 1)
        self.assertNotIn("csv/profile", self.service.shacl(saved))
        self.assertTrue(self.service.validate_template(saved)["conforms"])

    def test_invalid_data_edges(self):
        for change in [
            {"column_index": -1},
            {"column_index": True},
            {"column_index": "0"},
            {"source": "values", "target": "csv"},
            {"kind": "other"},
            {"predicate": "https://example.org/data"},
        ]:
            design = data_design()
            design["edges"][0].update(change)
            with self.subTest(change=change), self.assertRaises(DesignError):
                self.service.preview(design)
        design = data_design()
        design["edges"].append({**design["edges"][0], "id": "duplicate"})
        with self.assertRaises(DesignError):
            self.service.preview(design)

    def test_source_settings_are_not_arbitrary_metadata(self):
        design = data_design()
        for config in [{"delimiter": ",", "decimal_separator": ","}, {"content": "secret"}]:
            bad = copy.deepcopy(design)
            bad["nodes"][0]["config"] = config
            with self.assertRaises(DesignError):
                self.service.preview(bad)
