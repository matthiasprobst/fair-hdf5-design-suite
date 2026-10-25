"""Per-test catalog isolation, including the legacy facade's cached service."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fair_hdf5 import compat


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
