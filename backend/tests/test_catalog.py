"""Publication contracts: immutable snapshots, valid defaults and atomic revisions."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

from fair_hdf5.catalog import CATALOG
from fair_hdf5.domain import parse_blueprint
from fair_hdf5.errors import DesignError, RevisionConflict
from fair_hdf5.library import FileCatalogRepository
from fair_hdf5.services import CatalogService
from fair_hdf5.settings import Settings
from support import CatalogTestCase


class CatalogTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)
        self.repository = FileCatalogRepository(self.catalog_directory, self.settings)
        self.service = CatalogService(self.settings, self.repository)

    def test_publish_round_trip_and_immutable_revisions(self):
        draft = deepcopy(CATALOG["group"])
        original = deepcopy(draft)
        first = self.service.publish(draft)
        self.assertEqual(draft, original)
        manifest = self.repository.templates / first["id"] / "1.json"
        content = manifest.read_bytes()
        first["label"] = "Revised group"
        second = self.service.publish(first, first["id"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertEqual(manifest.read_bytes(), content)
        self.assertNotEqual(self.repository.get(first["id"], 1)["label"], second["label"])
        self.assertEqual(self.repository.get(first["id"]), second)
        first["defaults"]["path"] = "/mutated"
        self.assertNotEqual(self.repository.get(first["id"], 1)["defaults"]["path"], "/mutated")
        restarted = FileCatalogRepository(self.catalog_directory, self.settings)
        self.assertEqual(restarted.get(second["id"]), second)

    def test_invalid_defaults_do_not_publish(self):
        draft = deepcopy(CATALOG["group"])
        draft["defaults"]["path"] = "relative"
        before = set(self.repository.catalog())
        with self.assertRaises(DesignError):
            self.service.publish(draft)
        self.assertEqual(set(self.repository.catalog()), before)

    def test_compare_and_publish_is_atomic_across_repository_instances(self):
        first = self.service.publish(CATALOG["group"])
        other = FileCatalogRepository(self.catalog_directory, self.settings)
        barrier = Barrier(2)

        def publish(repository):
            candidate = {**first, "revision": 2}
            barrier.wait(timeout=5)
            try:
                return repository.publish(candidate, 1)["revision"]
            except RevisionConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, [self.repository, other]))
        self.assertCountEqual(results, [2, "conflict"])
        with self.assertRaises(RevisionConflict):
            self.service.publish(first, first["id"], 1)

    def test_snapshot_with_bundle_is_portable_and_schema_one_is_accepted(self):
        snapshot = self.repository.get("research_project", 1)
        snapshot["schema_version"] = 1
        blueprint = {
            "nodes": [
                {
                    "id": "project",
                    "type": snapshot["id"],
                    "config": snapshot["defaults"],
                    "template": snapshot,
                }
            ]
        }
        normalized = parse_blueprint(blueprint, self.settings).data
        self.assertEqual(normalized["nodes"][0]["template"]["schema_version"], 2)
        self.assertEqual(len(normalized["nodes"][0]["template"]["related_templates"]), 2)

    def test_form_profile_and_engine_policy(self):
        draft = {
            "label": "New profile",
            "category": "Metadata",
            "kind": "group",
            "color": "blue",
            "icon": "metadata",
            "shape": "urn:test:form",
            "defaults": {"path": "/new"},
            "fields": [],
        }
        self.assertEqual(self.service.publish(draft)["fields"], [])
        subset = CatalogService(Settings(_env_file=None, shacl_engine="subset"), self.repository)
        with self.assertRaisesRegex(DesignError, "pyshacl"):
            subset.publish(draft)
