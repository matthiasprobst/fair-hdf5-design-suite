"""DCAT data nodes and declared PROV lineage, separate from HDF5 conformance."""

from urllib.parse import quote

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, XSD

from .data_nodes import CSV_SOURCE
from .profiles import node_template
from .vocabulary import DCAT, H5, META, NODE_BASE, PROV

CSV_MEDIA_TYPE = URIRef("https://www.iana.org/assignments/media-types/text/csv")
DECLARATION_NOTE = (
    "Declared design metadata and lineage; not an independently verified acquisition record."
)


def node_iri(identifier):
    return URIRef(NODE_BASE + identifier)


def design_metadata(design):
    graph = Graph()
    for prefix, namespace in (
        ("dcat", DCAT),
        ("prov", PROV),
        ("dct", DCTERMS),
        ("h5", H5),
        ("meta", META),
    ):
        graph.bind(prefix, namespace)
    graph.add((URIRef(NODE_BASE), DCTERMS.description, Literal(DECLARATION_NOTE)))
    nodes = {node["id"]: node for node in design["nodes"]}
    for identifier, node in nodes.items():
        subject = node_iri(identifier)
        graph.add((subject, DCTERMS.title, Literal(node.get("label") or node["type"])))
        if node_template(node)["kind"]:
            graph.add((subject, H5.path, Literal(node["config"]["path"])))
        if node["type"] == CSV_SOURCE:
            distribution = URIRef(str(subject) + "/distribution")
            graph.add((subject, RDF.type, DCAT.Dataset))
            graph.add((subject, RDF.type, PROV.Entity))
            graph.add((subject, DCAT.distribution, distribution))
            graph.add((distribution, RDF.type, DCAT.Distribution))
            graph.add((distribution, RDF.type, PROV.Entity))
            graph.add((distribution, DCAT.mediaType, CSV_MEDIA_TYPE))
            if node["config"].get("filename"):
                graph.add((distribution, DCTERMS.title, Literal(node["config"]["filename"])))
    for edge in design.get("edges", []):
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        subject, obj = node_iri(source["id"]), node_iri(target["id"])
        relation = edge.get("relation", "related_to")
        if edge.get("kind") == "data":
            activity = URIRef(str(obj) + "/csv-import")
            distribution = URIRef(str(subject) + "/distribution")
            graph.add((obj, RDF.type, PROV.Entity))
            graph.add((obj, PROV.wasDerivedFrom, subject))
            graph.add((obj, PROV.wasGeneratedBy, activity))
            graph.add((activity, RDF.type, PROV.Activity))
            graph.add((activity, PROV.used, distribution))
            graph.add(
                (activity, H5.csvColumnIndex, Literal(edge["column_index"], datatype=XSD.integer))
            )
            columns = source["config"]["columns"]
            if edge["column_index"] < len(columns):
                graph.add((activity, H5.csvColumnName, Literal(columns[edge["column_index"]])))
        elif (
            relation == "generated"
            and target["type"] == CSV_SOURCE
            or relation == "was_generated_by"
            and source["type"] == CSV_SOURCE
        ):
            producer, data_node = (source, target) if relation == "generated" else (target, source)
            entity, data = node_iri(producer["id"]), node_iri(data_node["id"])
            activity = URIRef(str(data) + "/generation/" + producer["id"])
            graph.add((entity, RDF.type, PROV.Entity))
            graph.add((activity, RDF.type, PROV.Activity))
            graph.add((activity, PROV.used, entity))
            graph.add((data, PROV.wasGeneratedBy, activity))
            graph.add((URIRef(str(data) + "/distribution"), PROV.wasGeneratedBy, activity))
        else:
            predicate = (
                URIRef(edge["predicate"])
                if edge.get("predicate")
                else (
                    DCTERMS.relation if relation == "related_to" else META[quote(relation, safe="")]
                )
            )
            graph.add((subject, predicate, obj))
    return graph
