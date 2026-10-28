"""DCAT dataset/distribution semantics and declared equipment-to-data lineage."""

import io
import tempfile
from copy import deepcopy

import h5py
from fair_hdf5.application import create_app
from fair_hdf5.errors import DesignError
from fair_hdf5.example_projects import csv_example, example_csv
from fair_hdf5.project_blueprint import editable_blueprint
from fair_hdf5.provenance import CSV_MEDIA_TYPE, node_iri
from fair_hdf5.semantic import rdf_from_hdf5
from fair_hdf5.services import DesignService
from fair_hdf5.settings import Settings
from fair_hdf5.vocabulary import DCAT, H5, META, PROV
from fastapi.testclient import TestClient
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, XSD
from support import CatalogTestCase, authenticated_client


class ProvenanceTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)
        self.service = DesignService(self.settings)
        self.design = csv_example()

    def graph(self, design=None):
        return Graph().parse(data=self.service.rdf(design or self.design), format="turtle")

    def test_csv_data_node_has_a_dataset_and_csv_distribution(self):
        graph = self.graph()
        data = node_iri("csv_measurements")
        distribution = URIRef(str(data) + "/distribution")
        self.assertIn((data, RDF.type, DCAT.Dataset), graph)
        self.assertIn((data, DCAT.distribution, distribution), graph)
        self.assertIn((distribution, RDF.type, DCAT.Distribution), graph)
        self.assertIn((distribution, DCAT.mediaType, CSV_MEDIA_TYPE), graph)
        self.assertIn((distribution, DCTERMS.title, Literal("measurements.csv")), graph)
        self.assertNotIn("München", self.service.rdf(self.design))
        self.assertFalse(
            list(graph.objects(distribution, DCAT.downloadURL)),
            "A local filename is not a download URL",
        )

    def test_daq_is_equipment_used_by_an_acquisition_activity(self):
        graph = self.graph()
        data, daq = node_iri("csv_measurements"), node_iri("example_daq")
        activity = URIRef(str(data) + "/generation/example_daq")
        self.assertIn((data, PROV.wasGeneratedBy, activity), graph)
        self.assertIn((activity, RDF.type, PROV.Activity), graph)
        self.assertIn((activity, PROV.used, daq), graph)
        self.assertIn((daq, RDF.type, PROV.Entity), graph)
        self.assertNotIn((daq, RDF.type, PROV.Activity), graph)
        self.assertNotIn((data, PROV.wasGeneratedBy, daq), graph)

    def test_dataset_derivation_preserves_csv_column_mapping(self):
        graph = self.graph()
        data, target = node_iri("csv_measurements"), node_iri("pressure")
        activity = URIRef(str(target) + "/csv-import")
        self.assertIn((target, PROV.wasDerivedFrom, data), graph)
        self.assertIn((target, PROV.wasGeneratedBy, activity), graph)
        self.assertIn((activity, PROV.used, URIRef(str(data) + "/distribution")), graph)
        self.assertIn((activity, H5.csvColumnIndex, Literal(1, datatype=XSD.integer)), graph)
        self.assertIn((activity, H5.csvColumnName, Literal("pressure")), graph)
        self.assertIn((target, H5.path, Literal("/data/pressure")), graph)

    def test_forward_and_reverse_generation_have_the_same_rdf_meaning(self):
        reverse = deepcopy(self.design)
        edge = reverse["edges"][0]
        edge.update(source=edge["target"], target=edge["source"], relation="was_generated_by")
        self.assertTrue(isomorphic(self.graph(), self.graph(reverse)))

    def test_regular_relationships_and_bindings_round_trip_together(self):
        self.design["edges"].append(
            {
                "id": "related",
                "source": "csv_measurements",
                "target": "pressure",
                "relation": "related_to",
            }
        )
        saved = editable_blueprint(self.design, self.settings, self.service.repository)
        self.assertEqual(saved["edges"], self.design["edges"])
        self.assertIn(
            (node_iri("csv_measurements"), DCTERMS.relation, node_iri("pressure")),
            self.graph(saved),
        )
        self.assertTrue(self.service.validate_template(saved)["conforms"])

    def test_invalid_relationship_directions_and_column_mixing_are_rejected(self):
        for patch in [
            {"relation": "was_generated_by"},
            {"source": "csv_measurements", "target": "example_daq"},
            {"source": "csv_measurements", "target": "csv_measurements", "relation": "related_to"},
            {"column_index": 0},
            {"relation": {"bad": "value"}},
        ]:
            design = deepcopy(self.design)
            design["edges"][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(DesignError):
                self.service.rdf(design)

    def _toolbox_graph(self, content):
        import h5rdmtoolbox as h5tbx

        with tempfile.NamedTemporaryFile(suffix=".h5") as tmp:
            tmp.write(content)
            tmp.flush()
            raw = h5tbx.serialize(
                tmp.name,
                format="ttl",
                structural=False,
                contextual=True,
                file_uri="https://example.org/generated-file/",
            )
        graph = Graph().parse(data=raw, format="turtle")
        graph.remove((None, URIRef("https://schema.org/about"), None))
        return graph

    def _expected_hdf5_graph(self, content, design):
        graph = Graph().parse(data=self.service.rdf(design), format="turtle")
        with h5py.File(io.BytesIO(content), "r") as handle:
            graph += rdf_from_hdf5(design, handle)
        return graph

    def test_template_and_populated_file_use_toolbox_rdf_annotations(self):
        design = self.service.normalize(self.design)
        template = self.service.template(design)
        content = self.service.data_file(design, {"csv_measurements": io.BytesIO(example_csv())})

        for exported in (template, content):
            with self.subTest(populated=exported is content):
                with h5py.File(io.BytesIO(exported), "r") as handle:
                    self.assertNotIn("metadata_ttl", handle["/__design__"])
                    self.assertIn("rdf_resources", handle["/__design__"])
                    self.assertIn("Declared", handle["/__design__"].attrs["metadata_note"])
                    self.assertNotIn("/csv_measurements", handle)
                self.assertTrue(
                    isomorphic(
                        self._expected_hdf5_graph(exported, design), self._toolbox_graph(exported)
                    )
                )

        with h5py.File(io.BytesIO(content), "r") as handle:
            self.assertEqual(handle["/data/pressure"][:].tolist(), [1.25, 2.5, 3.75])
        self.assertTrue(self.service.validate(self.design, content)["conforms"])
        # Previously generated files with the Turtle payload remain validatable.
        legacy = io.BytesIO(content)
        with h5py.File(legacy, "r+") as handle:
            handle["/__design__"].create_dataset(
                "metadata_ttl", data=self.service.rdf(self.design), dtype=h5py.string_dtype("utf-8")
            )
        self.assertTrue(self.service.validate(self.design, legacy.getvalue())["conforms"])

    def test_metadata_endpoint_and_escaped_custom_relations(self):
        self.design["edges"].append(
            {
                "id": "custom",
                "source": "csv_measurements",
                "target": "pressure",
                "relation": "connected to / sample",
            }
        )
        graph = self.graph()
        self.assertIn(
            (
                node_iri("csv_measurements"),
                META["connected%20to%20%2F%20sample"],
                node_iri("pressure"),
            ),
            graph,
        )
        app = create_app(self.settings)
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/export/rdf", json=self.design).status_code, 401)
            authenticated_client(client)
            response = client.post("/api/export/rdf", json=self.design)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("text/turtle", response.headers["content-type"])
            self.assertIn("experiment.metadata.ttl", response.headers["content-disposition"])
            self.assertTrue(isomorphic(graph, Graph().parse(data=response.text, format="turtle")))
            self.assertEqual(response.headers["cache-control"], "no-store")
            bad = deepcopy(self.design)
            bad["edges"][0]["relation"] = []
            self.assertEqual(client.post("/api/export/rdf", json=bad).status_code, 422)

    def test_unconfigured_csv_sources_can_export_metadata_without_a_file(self):
        source = next(n for n in self.design["nodes"] if n["type"] == "csv_source")
        source["config"].update(columns=[], filename="")
        graph = self.graph()
        self.assertIn((node_iri(source["id"]), RDF.type, DCAT.Dataset), graph)
        self.assertTrue(self.service.validate_template(self.design)["conforms"])
