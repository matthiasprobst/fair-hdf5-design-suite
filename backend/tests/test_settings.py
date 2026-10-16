"""Configuration is explicit, isolated and independent of the working directory."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from fair_hdf5.application import create_app
from fair_hdf5.settings import PROJECT_ROOT, Settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_defaults_and_public_capabilities(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.port, 8000)
        self.assertEqual(settings.shacl_engine, 'pyshacl')
        self.assertEqual(settings.max_dataset_elements, 2_000_000)
        self.assertEqual(settings.capabilities(), {
            'max_nodes': 250, 'max_edges': 1000,
            'max_upload_bytes': 30_000_000, 'shacl_engine': 'pyshacl',
        })

    def test_explicit_environment_dotenv_default_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('FAIR_HDF5_PORT=8010\nFAIR_HDF5_MAX_NODES=33\nUNRELATED=value\n')
            self.assertEqual(Settings(_env_file=path).port, 8010)
            with patch.dict(os.environ, {'FAIR_HDF5_PORT': '8020'}):
                self.assertEqual(Settings(_env_file=path).port, 8020)
                self.assertEqual(Settings(_env_file=path, port=8030).port, 8030)
                self.assertEqual(Settings(_env_file=path).max_nodes, 33)
            self.assertEqual(Settings(_env_file=None).max_nodes, 250)

    def test_invalid_settings_fail_before_serving(self):
        for overrides in ({'port': 0}, {'port': 65536}, {'max_nodes': 0}, {'max_upload_bytes': -1},
                          {'shacl_engine': 'automatic'}, {'max_dataset_dimensions': 33},
                          {'log_level': 'silent'}, {'temp_dir': '/missing-fair-hdf5-directory'}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                Settings(_env_file=None, **overrides)

    def test_paths_resolve_from_project_not_cwd(self):
        settings = Settings(_env_file=None, frontend_dist='frontend/custom')
        self.assertEqual(settings.frontend_dist, PROJECT_ROOT / 'frontend/custom')

    def test_storage_probe_and_application_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            first = create_app(Settings(_env_file=None, max_nodes=1, shacl_engine='subset', temp_dir=directory))
            second = create_app(Settings(_env_file=None, max_nodes=500, shacl_engine='pyshacl'))
            self.assertEqual(first.state.design_service.settings.max_nodes, 1)
            self.assertEqual(second.state.design_service.settings.max_nodes, 500)
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIsNot(first.state.design_service, second.state.design_service)
        with patch('fair_hdf5.settings.tempfile.TemporaryFile', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(RuntimeError, 'not writable'):
                create_app(Settings(_env_file=None))
