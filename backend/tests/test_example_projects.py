"""Personal example copies, migration, isolation, and real CSV/HDF5 output."""

import io
import json
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
from fair_hdf5.access import Principal
from fair_hdf5.application import create_app
from fair_hdf5.database import Database
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

    def examples(self):
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200, response.text)
        return {p["example_id"]: p for p in response.json() if p["example_id"]}

    def test_first_dashboard_provisions_private_examples_once(self):
        first = self.examples()
        self.assertEqual(set(first), {example["id"] for example in bundled_examples()})
        self.assertEqual(self.examples(), first)
        for project in first.values():
            self.assertEqual(project["owner_id"], self.principal.user_id)
            self.assertEqual(project["role"], "owner")
            self.assertFalse(project["shared"])
            self.assertEqual(project["revision"], 1)
        database = self.app.state.database
        with database.transaction() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM user_examples").fetchone()[0], 2
            )

    def test_accounts_get_independent_copies_and_cannot_access_each_others(self):
        first = self.examples()
        accounts = self.app.state.account_service
        identifier = accounts.create_user(
            "exampleuser", "Example user", TEST_PASSWORD, principal=self.principal
        )
        with self.app.state.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE local_credentials SET must_change=0 WHERE user_id=?", (identifier,)
            )
        with TestClient(self.app) as other:
            token = other.get("/api/auth/session").json()["csrf_token"]
            other.headers["X-CSRF-Token"] = token
            response = other.post(
                "/api/auth/login", json={"username": "exampleuser", "password": TEST_PASSWORD}
            )
            self.assertEqual(response.status_code, 200)
            projects = other.get("/api/projects").json()
            self.assertEqual(len(projects), 2)
            self.assertTrue(all(p["owner_id"] == identifier for p in projects))
            self.assertTrue(
                set(p["id"] for p in projects).isdisjoint(p["id"] for p in first.values())
            )
            self.assertEqual(
                other.get(f"/api/projects/{first['csv-measurements']['id']}").status_code, 404
            )

    def test_saved_changes_and_deletions_survive_dashboard_reload_and_restart(self):
        csv = self.examples()["csv-measurements"]
        url = f"/api/projects/{csv['id']}"
        project = self.client.get(url).json()
        lease = self.client.post(url + "/edit-lock", json={"editor_id": "examples-test"}).json()[
            "token"
        ]
        design = project["blueprint"]
        design["name"] = "My edited CSV example"
        saved = self.client.put(
            url,
            headers={"X-Edit-Lease": lease},
            json={
                "blueprint": design,
                "description": "Personal changes",
                "expected_revision": 1,
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(self.examples()["csv-measurements"]["name"], "My edited CSV example")
        self.client.delete(url + "/edit-lock", headers={"X-Edit-Lease": lease})
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertNotIn("csv-measurements", self.examples())
        restarted = create_app(self.settings)
        projects = restarted.state.project_service.list(self.principal)
        self.assertEqual([p["example_id"] for p in projects], ["radial-fan"])

    def test_concurrent_dashboard_requests_do_not_duplicate_examples(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: self.app.state.project_service.list(self.principal), range(2)
                )
            )
        self.assertEqual({p["id"] for p in results[0]}, {p["id"] for p in results[1]})
        self.assertEqual(len(results[0]), 2)

    def test_csv_example_is_ready_to_build_and_validate(self):
        summary = self.examples()["csv-measurements"]
        design = self.client.get(f"/api/projects/{summary['id']}").json()["blueprint"]
        source = next(n for n in design["nodes"] if n["type"] == "csv_source")
        response = self.client.get("/api/examples/files/measurements.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, example_csv())
        self.assertEqual(response.headers["cache-control"], "no-store")
        raw = self.client.post(
            "/api/export/hdf5/data",
            data={"design_json": json.dumps(design)},
            files={source["id"]: ("measurements.csv", response.content)},
        )
        self.assertEqual(raw.status_code, 200, raw.text[:300] if raw.status_code != 200 else "")
        with h5py.File(io.BytesIO(raw.content), "r") as handle:
            self.assertEqual(handle["/data/time"][:].tolist(), [0, 1, 2])
            self.assertEqual(handle["/data/pressure"][:].tolist(), [1.25, 2.5, 3.75])
            self.assertEqual(
                handle["/data/sample"].asstr()[:].tolist(), ["München", "東京", "Sample C"]
            )
        self.assertTrue(self.app.state.design_service.validate(design, raw.content)["conforms"])
        self.assertTrue(self.app.state.design_service.validate_template(design)["conforms"])
        with TestClient(self.app) as anonymous:
            self.assertEqual(anonymous.get("/api/examples/files/measurements.csv").status_code, 401)

    def test_restrictive_graph_limits_do_not_break_the_dashboard(self):
        settings = Settings(_env_file=None, max_nodes=2)
        app = create_app(settings)
        self.assertEqual(app.state.project_service.list(self.principal), [])
        # Raising the limits later still provisions examples, since no receipt was recorded.
        self.assertEqual(len(self.examples()), 2)

    def test_csv_file_is_packaged_and_matches_the_repository_example(self):
        path = Path(__file__).resolve().parents[2] / "examples" / "csv" / "measurements.csv"
        self.assertEqual(example_csv(), path.read_bytes())
        source = next(n for n in csv_example()["nodes"] if n["type"] == "csv_source")
        self.assertEqual(source["config"]["columns"], ["time", "pressure", "sample"])

    def test_migration_preserves_an_existing_user_and_project(self):
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
                    "INSERT INTO sessions VALUES ('old-session','old-user','old-csrf',?)",
                    (time.time() + 3600,),
                )
                connection.execute(
                    "INSERT INTO projects VALUES ('old-project','old-user','Keep me','',?,7,1,1,NULL)",
                    (json.dumps({"name": "Keep me", "version": "0.1", "nodes": [], "edges": []}),),
                )
                connection.execute("PRAGMA user_version=1")
            migrated = Database(Path(directory))
            with migrated.transaction() as connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
                row = connection.execute("SELECT * FROM projects WHERE id='old-project'").fetchone()
                self.assertEqual(row["name"], "Keep me")
                self.assertEqual(row["revision"], 7)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM user_examples").fetchone()[0], 0
                )
            app = create_app(Settings(_env_file=None, data_dir=Path(directory)))
            projects = app.state.project_service.list(Principal("old-user", "old-session"))
            self.assertEqual(len(projects), 3)
            original = next(p for p in projects if p["id"] == "old-project")
            self.assertEqual(original["revision"], 7)
            self.assertEqual(original["name"], "Keep me")
