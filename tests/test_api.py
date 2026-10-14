"""FastAPI integration smoke tests for the v2 React-compatible HTTP contract."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import h5py
from fastapi.testclient import TestClient
from app import app


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.blueprint = cls.client.get('/api/demo').json()

    def test_catalog_has_reusable_extended_components(self):
        response = self.client.get('/api/catalog')
        self.assertEqual(response.status_code, 200)
        self.assertIn('vibration_sensor', response.json()['catalog'])
        self.assertIn('experiment_setup', response.json()['catalog'])
        self.assertIn('illustrative local', response.json()['profile_source'].lower())

    def test_blueprint_exports_and_preview(self):
        preview = self.client.post('/api/preview', json=self.blueprint)
        self.assertEqual(preview.status_code, 200)
        self.assertGreater(preview.json()['node_count'], 5)
        turtle = self.client.post('/api/export/shacl', json=self.blueprint)
        self.assertEqual(turtle.status_code, 200)
        self.assertIn('sh:NodeShape', turtle.text)
        raw = self.client.post('/api/export/hdf5', json=self.blueprint)
        self.assertEqual(raw.status_code, 200)
        with h5py.File(io.BytesIO(raw.content), 'r') as h5:
            self.assertIn('/experiment/measurements/velocity', h5)
            self.assertEqual(h5['/experiment/measurements/velocity'].shape, (0,))

    def test_validation_uses_generated_template(self):
        response = self.client.post('/api/validate/template', json=self.blueprint)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['conforms'])

    def test_unknown_component_rejected(self):
        bad = dict(self.blueprint)
        bad['nodes'] = [{**self.blueprint['nodes'][0], 'type':'unknown'}]
        bad['edges'] = []
        response = self.client.post('/api/preview', json=bad)
        self.assertEqual(response.status_code, 422)

    def test_health_and_react_only_routes(self):
        self.assertEqual(self.client.get('/health').json()['status'], 'ok')
        self.assertEqual(self.client.get('/legacy').status_code, 404)
        self.assertEqual(self.client.get('/static/index.html').status_code, 404)

        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir)
            with patch('app.FRONTEND_DIST', dist):
                unavailable = self.client.get('/')
                self.assertEqual(unavailable.status_code, 503)
                self.assertIn('React frontend is not built', unavailable.json()['detail'])

                (dist / 'index.html').write_text('<!doctype html><title>React app</title>')
                built = self.client.get('/')
                self.assertEqual(built.status_code, 200)
                self.assertIn('React app', built.text)


if __name__=='__main__':
    unittest.main()
