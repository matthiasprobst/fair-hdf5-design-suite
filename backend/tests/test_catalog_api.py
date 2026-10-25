"""HTTP contract for catalog use cases and centralized domain-error translation."""

from copy import deepcopy

from fair_hdf5.application import create_app
from fair_hdf5.catalog import CATALOG
from fair_hdf5.settings import Settings
from fastapi.testclient import TestClient
from support import CatalogTestCase, authenticated_client


class CatalogAPITests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.client = authenticated_client(TestClient(create_app(Settings(_env_file=None))))
        self.addCleanup(self.client.close)
        self.project = self.client.post("/api/projects", json={"name": "Catalog test"}).json()
        self.url = f"/api/projects/{self.project['id']}/catalog"
        lease = self.client.post(
            f"/api/projects/{self.project['id']}/edit-lock", json={"editor_id": "catalog-test"}
        ).json()
        self.client.headers["X-Edit-Lease"] = lease["token"]

    def test_publish_read_revision_and_conflict(self):
        response = self.client.post(
            self.url, json={"template": CATALOG["group"], "expected_revision": 1}
        )
        self.assertEqual(response.status_code, 201, response.text)
        first = response.json()
        first.pop("project_revision")
        draft = {**first, "label": "Second revision"}
        url = f"{self.url}/{first['id']}/revisions"
        response = self.client.post(
            url, json={"expected_revision": 2, "expected_template_revision": 1, "template": draft}
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["revision"], 2)
        stale = self.client.post(
            url, json={"expected_revision": 3, "expected_template_revision": 1, "template": draft}
        )
        self.assertEqual(stale.status_code, 409)
        self.assertIsInstance(stale.json()["detail"], str)
        old = self.client.get(url + "/1")
        self.assertEqual(old.status_code, 200)
        first.pop("project_local")
        self.assertEqual(old.json(), first)

    def test_analyze_and_invalid_defaults(self):
        response = self.client.post(
            "/api/catalog/analyze", json={"ttl": CATALOG["group"]["profile_ttl"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["shapes"][0]["supported"])
        self.assertEqual(response.json()["documents"], {})
        invalid = deepcopy(CATALOG["group"])
        invalid["defaults"]["path"] = "relative"
        self.assertEqual(
            self.client.post(
                self.url, json={"template": invalid, "expected_revision": 1}
            ).status_code,
            422,
        )

    def test_subset_rejects_publication(self):
        with authenticated_client(
            TestClient(create_app(Settings(_env_file=None, shacl_engine="subset")))
        ) as client:
            project = client.post("/api/projects", json={"name": "Subset project"}).json()
            url = f"/api/projects/{project['id']}"
            lease = client.post(url + "/edit-lock", json={"editor_id": "subset-editor"}).json()
            client.headers["X-Edit-Lease"] = lease["token"]
            self.assertEqual(
                client.post(
                    url + "/catalog", json={"template": CATALOG["group"], "expected_revision": 1}
                ).status_code,
                422,
            )
