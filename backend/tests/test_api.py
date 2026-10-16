"""FastAPI integration smoke tests for the v2 React-compatible HTTP contract."""
import asyncio
import io
import json
import threading
from unittest.mock import patch
import httpx
import tempfile
import unittest
from pathlib import Path

import h5py
from fastapi.testclient import TestClient
from fair_hdf5.application import create_app
from fair_hdf5.settings import Settings


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(Settings(_env_file=None)))
        cls.blueprint = cls.client.get('/api/demo').json()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

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
            with TestClient(create_app(Settings(_env_file=None, frontend_dist=dist))) as client:
                unavailable = client.get('/')
                self.assertEqual(unavailable.status_code, 503)
                self.assertIn('React frontend is not built', unavailable.json()['detail'])

                (dist / 'index.html').write_text('<!doctype html><title>React app</title>')
                built = client.get('/')
                self.assertEqual(built.status_code, 200)
                self.assertIn('React app', built.text)


class APIConfigurationTests(unittest.TestCase):
    def client(self, **overrides):
        client = TestClient(create_app(Settings(_env_file=None, **overrides)), raise_server_exceptions=False)
        self.addCleanup(client.close)
        return client

    def test_capabilities_and_app_settings_are_isolated(self):
        first = self.client(max_nodes=1, max_edges=2, shacl_engine='subset')
        second = self.client(max_nodes=500)
        self.assertEqual(first.get('/api/capabilities').json()['max_nodes'], 1)
        self.assertEqual(second.get('/api/capabilities').json()['max_nodes'], 500)
        self.assertEqual(first.post('/api/preview', json=first.get('/api/demo').json()).status_code, 422)
        self.assertEqual(second.post('/api/preview', json=second.get('/api/demo').json()).status_code, 200)
        self.assertNotIn('temp_dir', first.get('/api/capabilities').json())

    def test_json_and_multipart_share_validation(self):
        client = self.client()
        design = client.get('/api/demo').json()
        exported = client.post('/api/export/hdf5', json=design).content
        template = client.post('/api/validate/template', json=design)
        uploaded = client.post('/api/validate/file', data={'design_json': json.dumps(design)}, files={'file': ('test.h5', exported)})
        self.assertEqual(template.status_code, 200)
        self.assertEqual(uploaded.json(), template.json())
        for invalid in [None, [], {'nodes': [], 'name': 42}, {'nodes': [{'id': 'a', 'type': []}]}]:
            with self.subTest(invalid=invalid):
                # Explicit JSON text distinguishes null from an absent body in httpx.
                response = client.post('/api/preview', content=json.dumps(invalid), headers={'Content-Type':'application/json'})
                upload = client.post('/api/validate/file', data={'design_json': json.dumps(invalid)}, files={'file': ('test.h5', exported)})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(upload.status_code, 422)
                self.assertIsInstance(response.json()['detail'], str)
                self.assertIsInstance(upload.json()['detail'], str)
        malformed = client.post('/api/validate/file', data={'design_json': '{bad'}, files={'file': ('test.h5', exported)})
        self.assertEqual(malformed.status_code, 422)

    def test_upload_limit_and_bad_file(self):
        client = self.client(max_upload_bytes=10)
        blueprint = json.dumps(client.get('/api/demo').json())
        for content, status in [(b'x'*10, 422), (b'x'*11, 413)]:
            response = client.post('/api/validate/file', data={'design_json':blueprint}, files={'file': ('test.h5', content)})
            self.assertEqual(response.status_code, status)

    def test_server_errors_are_logged_without_exposing_details(self):
        client = self.client()
        with patch.object(client.app.state.design_service, 'preview', side_effect=TypeError('private implementation detail')):
            with self.assertLogs('fair_hdf5.application', level='ERROR'):
                response = client.post('/api/preview', json={'nodes': []})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'detail':'Internal server error.'})

    def test_frontend_switch_assets_and_engine_startup_failure(self):
        disabled = self.client(serve_frontend=False)
        self.assertEqual(disabled.get('/').status_code, 404)
        self.assertEqual(disabled.get('/health').status_code, 200)
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            (dist / 'assets').mkdir()
            (dist / 'assets' / 'app.js').write_text('export {};')
            enabled = self.client(frontend_dist=dist)
            self.assertEqual(enabled.get('/assets/app.js').status_code, 200)
        with patch('fair_hdf5.services.create_engine', side_effect=RuntimeError('missing pyshacl')):
            with self.assertRaisesRegex(RuntimeError, 'missing pyshacl'):
                create_app(Settings(_env_file=None))


class APIConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_processing_does_not_block_the_event_loop(self):
        app = create_app(Settings(_env_file=None))
        started, release = threading.Event(), threading.Event()
        loop_thread = threading.get_ident()
        def slow_validation(blueprint, file):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            started.set()
            if not release.wait(5):
                raise RuntimeError('test did not release validation')
            return {'conforms': True}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            with patch.object(app.state.design_service, 'validate_upload', side_effect=slow_validation):
                pending = asyncio.create_task(client.post('/api/validate/file', data={'design_json':'{"nodes":[]}'}, files={'file':('test.h5', b'x')}))
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 2))
                    health = await asyncio.wait_for(client.get('/health'), 1)
                    self.assertEqual(health.status_code, 200)
                finally:
                    release.set()
                    response = await pending
                self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
