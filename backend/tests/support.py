"""Per-test catalog isolation, including the legacy facade's cached service."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fair_hdf5 import compat

TEST_PASSWORD = "correct horse battery staple for tests"


def authenticated_client(client):
    """Exercise the real cookie/CSRF login flow for existing processing tests."""
    accounts = client.app.state.account_service
    with accounts.database.transaction() as connection:
        exists = connection.execute("SELECT id FROM users WHERE username='testadmin'").fetchone()
    if not exists:
        accounts.create_user(
            "testadmin", "Test administrator", TEST_PASSWORD, is_admin=True, bootstrap=True
        )
    session = client.get("/api/auth/session").json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    response = client.post(
        "/api/auth/login", json={"username": "testadmin", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


class CatalogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        directory = tempfile.TemporaryDirectory(prefix="fair-class-test-")
        cls.addClassCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {"FAIR_HDF5_DATA_DIR": directory.name})
        environment.start()
        cls.addClassCleanup(environment.stop)

    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory(prefix="fair-test-")
        self.addCleanup(directory.cleanup)
        self.catalog_directory = Path(directory.name)
        environment = patch.dict(os.environ, {"FAIR_HDF5_DATA_DIR": directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        compat._service.cache_clear()
        self.addCleanup(compat._service.cache_clear)


class AsyncCatalogTestCase(CatalogTestCase, unittest.IsolatedAsyncioTestCase):
    """The same storage isolation for asynchronous API tests."""
