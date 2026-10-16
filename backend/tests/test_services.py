"""Scientific processing regression tests, without HTTP transport."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

import h5py
from rdflib.compare import isomorphic
from fair_hdf5 import compat as backend
from fair_hdf5.catalog import demo
from fair_hdf5.domain import parse_blueprint, parse_shape
from fair_hdf5.engines import create_engine
from fair_hdf5.errors import DesignError, UploadTooLarge
from fair_hdf5.services import DesignService
from fair_hdf5.settings import Settings


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None)
        self.service = DesignService(self.settings)

    def test_overflow_and_shape_boundaries(self):
        self.assertEqual(parse_shape('0,3', self.settings), (0, 3))
        self.assertEqual(parse_shape('2000,1000', self.settings), (2000, 1000))
        for raw in ['50000,50000,50000,50000,50000', '2001,1000', '1,0', '-1', '50001', 'a', '1,1,1,1,1,1']:
            with self.subTest(raw=raw), self.assertRaises(DesignError):
                parse_shape(raw, self.settings)
        self.assertEqual(parse_shape('2,3', Settings(_env_file=None, max_dataset_elements=6)), (2, 3))
        with self.assertRaises(DesignError):
            parse_shape('2,4', Settings(_env_file=None, max_dataset_elements=6))

    def test_finite_metadata_and_envelope_types(self):
        for value in [float('nan'), float('inf'), float('-inf'), [], {}, 2**64, -(2**63)-1, 'a\x00b']:
            design = demo()
            design['nodes'][0]['config']['reading'] = value
            with self.subTest(value=value), self.assertRaises(DesignError):
                self.service.preview(design)
        for value in [None, [], {'nodes': [] ,'name': 42}, {'nodes': [], 'edges': None}]:
            with self.subTest(value=value), self.assertRaises(DesignError):
                self.service.preview(value)

    def test_limits_and_no_input_mutation(self):
        design = demo()
        original = json.dumps(design)
        with self.assertRaises(DesignError):
            DesignService(Settings(_env_file=None, max_nodes=1)).preview(design)
        with self.assertRaises(DesignError):
            DesignService(Settings(_env_file=None, max_edges=1)).preview(design)
        with self.assertRaises(DesignError):
            DesignService(Settings(_env_file=None, max_metadata_length=1)).preview(design)
        self.service.preview(design)
        self.assertEqual(json.dumps(design), original)
        with patch('fair_hdf5.services.parse_blueprint', wraps=parse_blueprint) as parser:
            self.service.validate_template(design)
            self.assertEqual(parser.call_count, 1)

    def test_optional_and_extra_blueprint_fields_are_preserved(self):
        design = {'nodes': [{'id': 'root', 'type': 'group', 'config': {'path': '/root'}, 'custom': 'keep'}], 'custom': {'future': 1}}
        result = self.service.template(design)
        with h5py.File(io.BytesIO(result), 'r') as handle:
            restored = json.loads(handle['/__design__/blueprint_json'][()])
        self.assertEqual(restored['nodes'], design['nodes'])
        self.assertEqual(restored['custom'], design['custom'])
        self.assertEqual(restored['edges'], [])
        self.assertEqual(restored['name'], 'Untitled experiment')

    def test_python_facade_and_semantic_output(self):
        design = demo()
        self.assertEqual(backend.structure_preview(design), self.service.preview(design))
        self.assertTrue(isomorphic(backend.build_shapes(design), self.service.shapes(design)))
        self.assertTrue(backend.validate_hdf5(design, self.service.template(design))['conforms'])

    def test_explicit_engines_and_missing_pyshacl(self):
        for name in ['pyshacl', 'subset']:
            service = DesignService(Settings(_env_file=None, shacl_engine=name))
            self.assertTrue(service.validate_template(demo())['conforms'])
        with patch.dict(sys.modules, {'pyshacl': None}):
            with self.assertRaisesRegex(RuntimeError, 'pySHACL is required'):
                create_engine('pyshacl')
            self.assertIn('subset', create_engine('subset').name)
        engine = create_engine('pyshacl')
        with patch.object(engine, '_validate', side_effect=ImportError('engine failure')):
            with self.assertRaises(ImportError):
                DesignService(self.settings, engine).validate_template(demo())

    def test_upload_boundary_and_bounded_read(self):
        content = self.service.template(demo())
        service = DesignService(Settings(_env_file=None, max_upload_bytes=len(content)))
        self.assertTrue(service.validate_upload(demo(), io.BytesIO(content))['conforms'])
        with self.assertRaises(UploadTooLarge):
            service.validate(demo(), content + b'x')
        stream = io.BytesIO(content + b'x' * 20)
        with self.assertRaises(UploadTooLarge):
            service.validate_upload(demo(), stream)
        self.assertEqual(stream.tell(), len(content) + 1)

    def test_temporary_files_removed_on_success_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DesignService(Settings(_env_file=None, temp_dir=directory))
            self.assertTrue(service.validate_template(demo())['conforms'])
            with self.assertRaisesRegex(DesignError, 'not a readable HDF5'):
                service.validate(demo(), b'not hdf5')
            with patch.object(service.engine, 'validate', side_effect=RuntimeError('engine failed')):
                with self.assertRaises(RuntimeError):
                    service.validate_template(demo())
            self.assertEqual(list(Path(directory).iterdir()), [])
        with patch('fair_hdf5.hdf5.tempfile.NamedTemporaryFile', side_effect=PermissionError('disk denied')):
            with self.assertRaises(PermissionError):
                self.service.validate(demo(), b'anything')

    def test_reports_are_truncated_without_losing_issue_count(self):
        design = demo()
        design['nodes'][0]['config'].pop('manufacturer')
        design['nodes'][0]['config'].pop('model')
        report = DesignService(Settings(_env_file=None, max_report_issues=1)).validate_template(design)
        self.assertFalse(report['conforms'])
        self.assertGreater(report['issue_count'], 1)
        self.assertEqual(len(report['issues']), 1)

    def test_concurrent_templates_have_independent_files(self):
        def generate(index):
            design = demo()
            design['name'] = f'experiment-{index}'
            with h5py.File(io.BytesIO(self.service.template(design)), 'r') as handle:
                return json.loads(handle['/__design__/blueprint_json'][()])['name']
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(generate, range(8))), [f'experiment-{i}' for i in range(8)])
