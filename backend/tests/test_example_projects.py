"""Read-only example browsing and explicit, independent project copies."""

import io
import json
import sqlite3
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import h5py
from fair_hdf5.application import create_app
from fair_hdf5.example_projects import bundled_examples, csv_example, example_csv
from fair_hdf5.settings import Settings
from fastapi.testclient import TestClient
from support import TEST_PASSWORD, CatalogTestCase, authenticated_client


class ExampleProjectTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)
        self.app = create_app(self.settings)
        self.client = authenticated_client(TestClient(self.app))
        self.addCleanup(self.client.close)
        self.principal = self.app.state.account_service.principal(
            self.client.cookies.get("fair_session")
        )

    def copy(self, identifier="csv-measurements", client=None):
        response = (client or self.client).post(f"/api/examples/{identifier}/copy")
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_browsing_and_opening_never_create_personal_projects(self):
        for _ in range(2):
            summaries = self.client.get("/api/examples").json()
            self.assertEqual({e["id"] for e in summaries}, {"radial-fan", "csv-measurements"})
            for item in summaries:
                response = self.client.get(f"/api/examples/{item['id']}")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["id"], item["id"])
                self.assertIn("blueprint", response.json())
            self.assertEqual(self.client.get("/api/projects").json(), [])
        with self.app.state.database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 0)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM user_examples").fetchone()[0], 0
            )

    def test_explicit_copy_is_private_owned_and_distinct_each_time(self):
        first, second = self.copy(), self.copy()
        self.assertNotEqual(first["id"], second["id"])
        for project in (first, second):
            self.assertEqual(project["owner_id"], self.principal.user_id)
            self.assertEqual(project["role"], "owner")
            self.assertFalse(project["shared"])
            self.assertEqual(project["revision"], 1)
        self.assertEqual(len(self.client.get("/api/projects").json()), 2)
        before = self.client.get("/api/projects").json()
        for _ in range(2):
            self.client.get(f"/api/projects/{first['id']}")
            self.client.get("/api/examples/csv-measurements")
        self.assertEqual(self.client.get("/api/projects").json(), before)

    def test_accounts_only_share_the_canonical_example_not_personal_copies(self):
        first = self.copy()
        identifier = self.app.state.account_service.create_user(
            "exampleuser", "Example user", TEST_PASSWORD, principal=self.principal
        )
        with self.app.state.database.transaction(write=True) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM projects WHERE owner_id=?", (identifier,)
                ).fetchone()[0],
                0,
            )
            connection.execute(
                "UPDATE local_credentials SET must_change=0 WHERE user_id=?", (identifier,)
            )
        with TestClient(self.app) as other:
            token = other.get("/api/auth/session").json()["csrf_token"]
            other.headers["X-CSRF-Token"] = token
            login = other.post(
                "/api/auth/login", json={"username": "exampleuser", "password": TEST_PASSWORD}
            )
            other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            self.assertEqual(other.get("/api/projects").json(), [])
            self.assertEqual(
                other.get("/api/examples/csv-measurements").json(),
                self.client.get("/api/examples/csv-measurements").json(),
            )
            second = self.copy(client=other)
            self.assertEqual(second["owner_id"], identifier)
            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual(other.get(f"/api/projects/{first['id']}").status_code, 404)
            self.assertEqual(self.client.get(f"/api/projects/{second['id']}").status_code, 404)

    def test_library_updates_are_visible_but_existing_copies_are_preserved(self):
        old = self.copy()
        changed = deepcopy(bundled_examples())
        updated = next(e for e in changed if e["id"] == "csv-measurements")
        updated["blueprint"]["name"] = "Updated CSV example"
        updated["blueprint"]["nodes"][0]["label"] = "Updated DAQ"
        with patch("fair_hdf5.example_projects.bundled_examples", return_value=changed):
            current = self.client.get("/api/examples/csv-measurements").json()
            self.assertEqual(current["name"], "Updated CSV example")
            fresh = self.copy()
            self.assertEqual(fresh["blueprint"]["nodes"][0]["label"], "Updated DAQ")
        original = self.client.get(f"/api/projects/{old['id']}").json()
        self.assertEqual(original["name"], old["name"])
        self.assertEqual(original["blueprint"], old["blueprint"])

    def test_edits_and_deletions_do_not_modify_the_shared_example(self):
        canonical = self.client.get("/api/examples/csv-measurements").json()
        project = self.copy()
        url = f"/api/projects/{project['id']}"
        lease = self.client.post(url + "/edit-lock", json={"editor_id": "example-test"}).json()[
            "token"
        ]
        design = project["blueprint"]
        design["name"] = "My changed example"
        response = self.client.put(
            url, headers={"X-Edit-Lease": lease}, json={"blueprint": design, "expected_revision": 1}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/examples/csv-measurements").json(), canonical)
        self.client.delete(url + "/edit-lock", headers={"X-Edit-Lease": lease})
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get("/api/projects").json(), [])
        self.assertEqual(self.client.get("/api/examples/csv-measurements").json(), canonical)

    def test_csv_example_is_ready_to_build_without_creating_a_project(self):
        design = self.client.get("/api/examples/csv-measurements").json()["blueprint"]
        source = next(n for n in design["nodes"] if n["type"] == "csv_source")
        response = self.client.get("/api/examples/files/measurements.csv")
        self.assertEqual(response.content, example_csv())
        raw = self.client.post(
            "/api/export/hdf5/data",
            data={"design_json": json.dumps(design)},
            files={source["id"]: ("measurements.csv", response.content)},
        )
        self.assertEqual(raw.status_code, 200)
        with h5py.File(io.BytesIO(raw.content), "r") as handle:
            self.assertEqual(handle["/data/pressure"][:].tolist(), [1.25, 2.5, 3.75])
            self.assertEqual(
                handle["/data/sample"].asstr()[:].tolist(), ["München", "東京", "Sample C"]
            )
        self.assertTrue(self.app.state.design_service.validate(design, raw.content)["conforms"])
        self.assertEqual(self.client.get("/api/projects").json(), [])

    def test_authentication_missing_examples_and_read_only_library(self):
        with TestClient(self.app) as anonymous:
            for path in (
                "/api/examples",
                "/api/examples/csv-measurements",
                "/api/examples/files/measurements.csv",
            ):
                self.assertEqual(anonymous.get(path).status_code, 401)
            self.assertEqual(anonymous.post("/api/examples/csv-measurements/copy").status_code, 401)
        self.assertEqual(self.client.get("/api/examples/missing").status_code, 404)
        self.assertEqual(self.client.post("/api/examples/missing/copy").status_code, 404)
        self.assertEqual(
            self.client.put("/api/examples/csv-measurements", json={}).status_code, 405
        )
        self.assertEqual(self.client.delete("/api/examples/csv-measurements").status_code, 405)
        self.assertEqual(
            self.client.post(
                "/api/examples/csv-measurements/copy", headers={"X-CSRF-Token": "wrong"}
            ).status_code,
            403,
        )

    def test_restrictive_limits_reject_copy_without_side_effects(self):
        app = create_app(Settings(_env_file=None, max_nodes=2))
        with authenticated_client(TestClient(app)) as client:
            self.assertEqual(len(client.get("/api/examples").json()), 2)
            self.assertEqual(client.post("/api/examples/csv-measurements/copy").status_code, 422)
            self.assertEqual(client.get("/api/projects").json(), [])

    def test_csv_file_is_packaged_and_matches_the_repository_example(self):
        path = Path(__file__).resolve().parents[2] / "examples" / "csv" / "measurements.csv"
        self.assertEqual(example_csv(), path.read_bytes())
        source = next(n for n in csv_example()["nodes"] if n["type"] == "csv_source")
        self.assertEqual(source["config"]["columns"], ["time", "pressure", "sample"])

    def test_existing_personal_example_copies_survive_without_reprovisioning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projects.sqlite3"
            schema = (
                Path(__file__).resolve().parents[1]
                / "fair_hdf5"
                / "migrations"
                / "001_projects.sql"
            ).read_text()
            with sqlite3.connect(path) as connection:
                connection.executescript(schema)
                connection.execute(
                    "INSERT INTO users VALUES ('old-user','olduser','Existing user',0,1,1)"
                )
                connection.execute(
                    "INSERT INTO projects VALUES ('old-project','old-user','Keep me','',?,7,1,1,NULL)",
                    (json.dumps({"name": "Keep me", "version": "0.1", "nodes": [], "edges": []}),),
                )
                connection.execute("PRAGMA user_version=1")
            app = create_app(Settings(_env_file=None, data_dir=Path(directory)))
            with app.state.database.transaction() as connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 1
                )
                self.assertEqual(
                    connection.execute("SELECT revision FROM projects").fetchone()[0], 7
                )
            self.assertEqual(len(app.state.example_service.list()), 2)
