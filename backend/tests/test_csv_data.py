"""CSV parsing, checked casts, multipart transport, and real HDF5 values."""

import copy
import io
import json

import h5py
from fair_hdf5.application import create_app
from fair_hdf5.csv_data import parse_csv
from fair_hdf5.errors import DesignError, UploadTooLarge
from fair_hdf5.services import DesignService
from fair_hdf5.settings import Settings
from fastapi.testclient import TestClient
from support import CatalogTestCase, authenticated_client
from test_data_nodes import data_design


class CsvTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)
        self.service = DesignService(self.settings)

    def test_common_dialects_and_preview(self):
        table = parse_csv(
            '\ufeffpressure;name\r\n1,25;"München; Süd"\r\n2,5;"two\nlines"\r\n'.encode(),
            {"delimiter": ";", "decimal_separator": ","},
            self.settings,
        )
        self.assertEqual(
            table.preview(),
            {
                "columns": ["pressure", "name"],
                "row_count": 2,
                "suggested_dtypes": ["float64", "string"],
                "rows": [["1,25", "München; Süd"], ["2,5", "two\nlines"]],
            },
        )
        table = parse_csv(b"1\t2\n3\t4\n", {"delimiter": "\t", "has_header": False}, self.settings)
        self.assertEqual(table.columns, ["Column 1", "Column 2"])
        self.assertEqual(table.preview()["suggested_dtypes"], ["int64", "int64"])

    def test_invalid_and_bounded_inputs(self):
        for content in [b"", b"\xff", b"a\x00b", b'a,b\n"unterminated', b"a,b\n1\n"]:
            with self.subTest(content=content), self.assertRaises(DesignError):
                parse_csv(content, {}, self.settings)
        with self.assertRaises(UploadTooLarge):
            parse_csv(b"a\n12345", {}, Settings(_env_file=None, max_upload_bytes=3))
        with self.assertRaises(UploadTooLarge):
            parse_csv(b"a,b\n1,2", {}, Settings(_env_file=None, max_dataset_elements=3))
        with self.assertRaises(UploadTooLarge):
            parse_csv(b"a\n1\n2", {}, Settings(_env_file=None, max_dimension_size=1))
        table = parse_csv(b"a\n" + b"1\n" * 60, {}, self.settings)
        self.assertEqual(len(table.preview()["rows"]), 50)
        self.assertEqual(table.preview()["row_count"], 60)

    def test_populated_file_and_string_validation(self):
        design = data_design()
        design["nodes"][0]["config"].update(
            delimiter=";", decimal_separator=",", columns=["pressure", "name"]
        )
        text = copy.deepcopy(design["nodes"][1])
        text.update(id="names", label="Sample name")
        text["config"].update(path="/data/names", dtype="string", quantity="name", unit="1")
        design["nodes"].append(text)
        design["edges"].append(
            {**design["edges"][0], "id": "names_binding", "target": "names", "column_index": 1}
        )
        content = self.service.data_file(
            design, {"csv": io.BytesIO("pressure;name\n1,25;München\n2,5;\n".encode())}
        )
        with h5py.File(io.BytesIO(content), "r") as handle:
            self.assertEqual(handle["/data/pressure"][:].tolist(), [1.25, 2.5])
            self.assertEqual(handle["/data/names"].asstr()[:].tolist(), ["München", ""])
            self.assertEqual(h5py.check_string_dtype(handle["/data/names"].dtype).encoding, "utf-8")
            saved = json.loads(handle["/__design__/blueprint_json"][()])
            self.assertNotIn("München", json.dumps(saved))
            self.assertNotIn("columns", handle["/data/pressure"].attrs)
        self.assertTrue(self.service.validate(design, content)["conforms"])
        self.assertTrue(self.service.validate_template(design)["conforms"])

    def test_numeric_errors_identify_row_column_and_target(self):
        for dtype, raw in [
            ("float64", ""),
            ("float64", "NaN"),
            ("float64", "inf"),
            ("float32", "1e100"),
            ("int32", "1.5"),
            ("int32", "2147483648"),
            ("uint8", "-1"),
            ("uint8", "256"),
            ("float64", "not a number"),
        ]:
            design = data_design()
            design["nodes"][1]["config"]["dtype"] = dtype
            with (
                self.subTest(dtype=dtype, raw=raw),
                self.assertRaisesRegex(
                    DesignError, "Measurements: row 2, column 1.*target /data/pressure"
                ),
            ):
                self.service.data_file(design, {"csv": io.BytesIO(f'pressure\n"{raw}"\n'.encode())})

    def test_exact_integer_conversion(self):
        design = data_design()
        design["nodes"][1]["config"]["dtype"] = "int64"
        raw = self.service.data_file(design, {"csv": io.BytesIO(b"pressure\n9007199254740993\n")})
        with h5py.File(io.BytesIO(raw), "r") as handle:
            self.assertEqual(int(handle["/data/pressure"][0]), 9007199254740993)

    def test_duplicate_headers_use_column_position(self):
        design = data_design()
        design["nodes"][0]["config"]["columns"] = ["p", "p"]
        design["edges"][0]["column_index"] = 1
        raw = self.service.data_file(design, {"csv": io.BytesIO(b"p,p\n1,2\n")})
        with h5py.File(io.BytesIO(raw), "r") as handle:
            self.assertEqual(handle["/data/pressure"][0], 2)

    def test_incomplete_mappings_headers_and_shapes(self):
        for modification, content in [
            (lambda d: d.update(edges=[]), b"pressure\n1\n"),
            (lambda d: None, b"different\n1\n"),
            (lambda d: None, b"pressure\n"),
            (lambda d: d["nodes"][1]["config"].update(shape="2"), b"pressure\n1\n"),
            (lambda d: d["nodes"][1]["config"].update(shape="0,2"), b"pressure\n1\n"),
            (lambda d: d["edges"][0].update(column_index=10), b"pressure\n1\n"),
        ]:
            design = data_design()
            modification(design)
            with self.assertRaises(DesignError):
                self.service.data_file(design, {"csv": io.BytesIO(content)})
        with self.assertRaises(DesignError):
            self.service.data_file(data_design(), {})

    def test_aggregate_cells_and_generated_elements(self):
        design = data_design()
        extra = copy.deepcopy(design["nodes"][1])
        extra["id"] = "extra"
        extra["config"]["path"] = "/data/extra"
        design["nodes"].append(extra)
        design["edges"].append({**design["edges"][0], "id": "extra", "target": "extra"})
        service = DesignService(Settings(_env_file=None, max_dataset_elements=3))
        with self.assertRaises(UploadTooLarge):
            service.data_file(design, {"csv": io.BytesIO(b"pressure\n1\n2\n")})

    def test_multipart_endpoints_and_authentication(self):
        app = create_app(self.settings)
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/data/csv/preview").status_code, 401)
            authenticated_client(client)
            response = client.post(
                "/api/data/csv/preview",
                data={"settings_json": "{}"},
                files={"file": ("test.csv", b"pressure\n1\n2\n")},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["row_count"], 2)
            response = client.post(
                "/api/export/hdf5/data",
                data={"design_json": json.dumps(data_design())},
                files={"csv": ("test.csv", b"pressure\n1\n2\n")},
            )
            self.assertEqual(response.status_code, 200, response.text[:300])
            with h5py.File(io.BytesIO(response.content), "r") as handle:
                self.assertEqual(handle["/data/pressure"][:].tolist(), [1, 2])
            self.assertEqual(response.headers["cache-control"], "no-store")
            bad = client.post("/api/export/hdf5/data", data={"design_json": "{}"})
            self.assertEqual(bad.status_code, 422)
