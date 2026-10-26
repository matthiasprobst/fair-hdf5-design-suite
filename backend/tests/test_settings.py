"""Configuration is explicit, isolated and independent of the working directory."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fair_hdf5.application import create_app
from fair_hdf5.settings import PROJECT_ROOT, Settings
from pydantic import ValidationError
from support import CatalogTestCase


class SettingsTests(CatalogTestCase):
    def test_project_auth_settings_validate_origins_and_lock_timing(self):
        self.assertIsNone(Settings(_env_file=None, public_url="").public_url)
        self.assertEqual(
            Settings(_env_file=None, public_url="https://design.example.org/").public_url,
            "https://design.example.org",
        )
        for origin in (
            "https://design.example.org/path",
            "https://user:password@example.org",
            "file:///tmp/app",
            "https://example.org?query=yes",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                Settings(_env_file=None, public_url=origin)
        with self.assertRaises(ValueError):
            Settings(_env_file=None, edit_lock_seconds=30)

    def setUp(self):
        super().setUp()
        self.environment = patch.dict(
            os.environ, {"FAIR_HDF5_DATA_DIR": str(self.catalog_directory)}, clear=True
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_defaults_and_public_capabilities(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.port, 8000)
        self.assertEqual(settings.password_min_length, 15)
        self.assertEqual(settings.shacl_engine, "pyshacl")
        self.assertEqual(settings.max_dataset_elements, 2_000_000)
        self.assertEqual(
            settings.capabilities(),
            {
                "max_nodes": 250,
                "max_edges": 1000,
                "max_upload_bytes": 30_000_000,
                "shacl_engine": "pyshacl",
                "max_dimension_size": 50_000,
                "max_dataset_elements": 2_000_000,
            },
        )

    def test_explicit_environment_dotenv_default_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("FAIR_HDF5_PORT=8010\nFAIR_HDF5_MAX_NODES=33\nUNRELATED=value\n")
            self.assertEqual(Settings(_env_file=path).port, 8010)
            with patch.dict(os.environ, {"FAIR_HDF5_PORT": "8020"}):
                self.assertEqual(Settings(_env_file=path).port, 8020)
                self.assertEqual(Settings(_env_file=path, port=8030).port, 8030)
                self.assertEqual(Settings(_env_file=path).max_nodes, 33)
            self.assertEqual(Settings(_env_file=None).max_nodes, 250)

    def test_invalid_settings_fail_before_serving(self):
        for overrides in (
            {"port": 0},
            {"port": 65536},
            {"password_min_length": 2},
            {"password_min_length": 129},
            {"max_nodes": 0},
            {"max_upload_bytes": -1},
            {"shacl_engine": "automatic"},
            {"max_dataset_dimensions": 33},
            {"log_level": "silent"},
            {"temp_dir": "/missing-fair-hdf5-directory"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                Settings(_env_file=None, **overrides)

    def test_password_minimum_can_be_configured_from_environment(self):
        for minimum in (3, 128):
            with (
                self.subTest(minimum=minimum),
                patch.dict(os.environ, {"FAIR_HDF5_PASSWORD_MIN_LENGTH": str(minimum)}),
            ):
                self.assertEqual(Settings(_env_file=None).password_min_length, minimum)

    def test_paths_resolve_from_project_not_cwd(self):
        settings = Settings(_env_file=None, frontend_dist="frontend/custom")
        self.assertEqual(settings.frontend_dist, PROJECT_ROOT / "frontend/custom")

    def test_storage_probe_and_application_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            first = create_app(
                Settings(_env_file=None, max_nodes=1, shacl_engine="subset", temp_dir=directory)
            )
            second = create_app(Settings(_env_file=None, max_nodes=500, shacl_engine="pyshacl"))
            self.assertEqual(first.state.design_service.settings.max_nodes, 1)
            self.assertEqual(second.state.design_service.settings.max_nodes, 500)
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIsNot(first.state.design_service, second.state.design_service)
        with patch(
            "fair_hdf5.settings.tempfile.TemporaryFile", side_effect=PermissionError("denied")
        ):
            with self.assertRaisesRegex(RuntimeError, "not writable"):
                create_app(Settings(_env_file=None))
