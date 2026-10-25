import socket
import unittest
from unittest.mock import patch

from fair_hdf5.errors import DesignError
from fair_hdf5.profile_bundles import (
    bundle_graph,
    fetch_document,
    resolve_bundle,
    unbundled_imports,
)
from fair_hdf5.profile_schema import analyze_profile
from fair_hdf5.settings import Settings
from rdflib import URIRef
from rdflib.namespace import SH, XSD
from support import CatalogTestCase


class FakeResponse:
    def __init__(
        self,
        status=200,
        body=b"@prefix sh: <http://www.w3.org/ns/shacl#>. <https://qudt.org/vocab/quantitykind> a sh:NodeShape.",
        headers=None,
    ):
        self.status = status
        self.body = body
        self.headers = headers or {}

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, limit):
        return self.body


class ProfileBundleFetchTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(_env_file=None)

    def test_http_import_fetches_https_and_keeps_original_bundle_key(self):
        request_calls = []

        class Connection:
            def __init__(self, hostname, address, timeout):
                self.hostname = hostname

            def request(self, method, path, headers):
                request_calls.append((self.hostname, method, path, headers))

            def getresponse(self):
                return FakeResponse()

            def close(self):
                pass

        root = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:root> owl:imports <http://qudt.org/vocab/quantitykind> ; sh:node <http://qudt.org/vocab/quantitykind> ."""
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with (
            patch("fair_hdf5.profile_bundles.socket.getaddrinfo", return_value=addresses),
            patch("fair_hdf5.profile_bundles.PinnedHTTPSConnection", Connection),
        ):
            source, documents = resolve_bundle(
                root, "https://example.org/profile", {}, self.settings, fetch=True
            )

        self.assertEqual(source, "https://example.org/profile")
        self.assertIn("http://qudt.org/vocab/quantitykind", documents)
        self.assertEqual(
            documents["http://qudt.org/vocab/quantitykind"]["resolved_url"],
            "https://qudt.org/vocab/quantitykind",
        )
        self.assertEqual(request_calls[0][0:3], ("qudt.org", "GET", "/vocab/quantitykind"))

    def test_only_referenced_shape_imports_are_fetched(self):
        root = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/> .
<https://example.org/root> a sh:NodeShape ;
  owl:imports <http://qudt.org/vocab/quantitykind>, <https://qudt.org/vocab/unit/>, <https://profiles.example.org/variable> ;
  sh:node <https://profiles.example.org/variable> ;
  sh:property [ sh:path ex:kind ; sh:class <http://qudt.org/schema/qudt/QuantityKind> ],
              [ sh:path ex:value ; sh:xone ([ sh:datatype <http://www.w3.org/2001/XMLSchema#integer> ] [ sh:datatype <http://www.w3.org/2001/XMLSchema#double> ]) ] ."""
        dependency = """@prefix sh: <http://www.w3.org/ns/shacl#> .
<https://profiles.example.org/variable> a sh:NodeShape ."""
        fetched = []

        def fetch(uri, settings):
            fetched.append(uri)
            if uri != "https://profiles.example.org/variable":
                raise AssertionError(f"Vocabulary import should not be fetched: {uri}")
            return dependency, uri

        with patch("fair_hdf5.profile_bundles.fetch_document", side_effect=fetch):
            source, documents = resolve_bundle(
                root, "https://example.org/root", {}, self.settings, fetch=True
            )
        analysis = analyze_profile(root, documents, source)
        omitted = unbundled_imports(root, source, documents)

        self.assertEqual(fetched, ["https://profiles.example.org/variable"])
        self.assertEqual(set(documents), {"https://profiles.example.org/variable"})
        self.assertEqual(
            omitted, ["http://qudt.org/vocab/quantitykind", "https://qudt.org/vocab/unit/"]
        )
        self.assertTrue(analysis["shapes"][0]["supported"], analysis["shapes"][0].get("error"))
        fields = {field["predicate"]: field for field in analysis["shapes"][0]["fields"]}
        self.assertEqual(fields["https://example.org/kind"]["datatype"], "IRI")
        self.assertEqual(
            fields["https://example.org/kind"]["class"], "http://qudt.org/schema/qudt/QuantityKind"
        )
        self.assertEqual(
            fields["https://example.org/value"]["datatype_options"],
            [str(XSD.integer), str(XSD.double)],
        )

    def test_shape_and_xone_constraints_are_preserved_in_executable_graph(self):
        from fair_hdf5.profile_schema import compile_profile, executable_shapes
        from fair_hdf5.semantic import _rdf_value

        ttl = """@prefix ex: <https://example.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<https://example.org/shape> a sh:NodeShape ; sh:property [ sh:path ex:kind ; sh:class qudt:QuantityKind ], [ sh:path ex:value ; sh:xone ([ sh:datatype xsd:integer ] [ sh:datatype xsd:double ]) ] ."""
        fields = compile_profile(ttl, "https://example.org/shape")
        graph = executable_shapes(bundle_graph(ttl))
        self.assertTrue(
            any(
                graph.value(item, SH.xone) is not None
                for item in graph.objects(URIRef("https://example.org/shape"), SH.property)
            )
        )
        class_field = next(
            field for field in fields if field["predicate"] == "https://example.org/kind"
        )
        numeric_field = next(
            field for field in fields if field["predicate"] == "https://example.org/value"
        )
        self.assertEqual(class_field["datatype"], "IRI")
        self.assertEqual(class_field["class"], "http://qudt.org/schema/qudt/QuantityKind")
        self.assertEqual(numeric_field["datatype_options"], [str(XSD.integer), str(XSD.double)])
        self.assertEqual(_rdf_value("12", numeric_field).datatype, XSD.integer)
        self.assertEqual(_rdf_value("12.5", numeric_field).datatype, XSD.double)

    def test_https_fetch_failure_never_falls_back_to_http(self):
        requested_hosts = []

        class Connection:
            def __init__(self, hostname, address, timeout):
                requested_hosts.append(hostname)

            def request(self, method, path, headers):
                raise OSError("TLS endpoint unavailable")

            def close(self):
                pass

        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with (
            patch("fair_hdf5.profile_bundles.socket.getaddrinfo", return_value=addresses),
            patch("fair_hdf5.profile_bundles.PinnedHTTPSConnection", Connection),
        ):
            with self.assertRaisesRegex(DesignError, "Upload this dependency file instead"):
                fetch_document("http://qudt.org/vocab/quantitykind", self.settings)

        self.assertEqual(requested_hosts, ["qudt.org"])

    def test_http_redirect_is_rejected_without_plaintext_request(self):
        request_calls = []

        class Connection:
            def __init__(self, hostname, address, timeout):
                pass

            def request(self, method, path, headers):
                request_calls.append(path)

            def getresponse(self):
                return FakeResponse(
                    status=302, headers={"Location": "http://other.example/dependency"}
                )

            def close(self):
                pass

        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with (
            patch("fair_hdf5.profile_bundles.socket.getaddrinfo", return_value=addresses),
            patch("fair_hdf5.profile_bundles.PinnedHTTPSConnection", Connection),
        ):
            with self.assertRaisesRegex(DesignError, "require public HTTPS URLs"):
                fetch_document("http://qudt.org/vocab/quantitykind", self.settings)

        self.assertEqual(request_calls, ["/vocab/quantitykind"])

    def test_http_import_with_nonstandard_port_is_rejected(self):
        with self.assertRaisesRegex(DesignError, "require public HTTPS URLs"):
            fetch_document("http://qudt.org:8080/vocab/quantitykind", self.settings)

    def test_supplied_vocabulary_import_is_included_without_fetching(self):
        root = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/root> owl:imports <http://qudt.org/vocab/quantitykind> ."""
        vocabulary = "@prefix qudt: <http://qudt.org/schema/qudt/> . <http://qudt.org/vocab/quantitykind/Length> a qudt:QuantityKind ."
        with patch(
            "fair_hdf5.profile_bundles.fetch_document",
            side_effect=AssertionError("supplied dependency should not be fetched"),
        ):
            _, documents = resolve_bundle(
                root,
                "https://example.org/root",
                {"http://qudt.org/vocab/quantitykind": {"ttl": vocabulary}},
                self.settings,
                fetch=True,
            )
        self.assertIn("http://qudt.org/vocab/quantitykind", documents)
        self.assertEqual(unbundled_imports(root, "https://example.org/root", documents), [])


if __name__ == "__main__":
    unittest.main()
