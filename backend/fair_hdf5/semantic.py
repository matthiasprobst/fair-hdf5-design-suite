"""SHACL shapes and the RDF projection of HDF5 metadata."""
from typing import Any
import h5py
import numpy as np
from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.namespace import SH, XSD
from .profiles import node_template
from .vocabulary import H5, META, NODE_BASE, SHAPE_BASE
from .profiles import profile_required as _profile_required, profile_iri as _profile_iri

def _meta_key(key: str):
    return META[key]

def build_shapes(design: dict[str, Any]) -> Graph:
    """Produce a self-contained SHACL document for RDF projection of HDF5 objects.

    The generated shape validates RDF *describing* HDF5, not raw HDF5 bytes.
    The service validates the blueprint before calling this function.
    HDF5 structural checks are implemented separately in the hdf5 module.
    """
    graph = Graph()
    graph.bind("sh", SH)
    graph.bind("h5", H5)
    graph.bind("meta", META)
    graph.bind("xsd", XSD)
    for node in design["nodes"]:
        info = node_template(node)
        if not info["kind"]:
            continue
        if info.get("profile_ttl"):
            source = Graph().parse(data=info["profile_ttl"], format="turtle")
            original = URIRef(info["shape"])
            renamed = {term: BNode() for triple in source for term in triple if isinstance(term, BNode)}
            # Every instance receives its own shape and blank nodes. Source targets
            # never select unrelated instances that happen to share a class.
            for resource in set(source.objects(None, SH.property)) | set(source.subjects(RDF.type, SH.NodeShape)) | set(source.subjects(RDF.type, SH.PropertyShape)):
                renamed[resource] = BNode()
            renamed[original] = URIRef(SHAPE_BASE + node["id"] + "/profile")
            for subject, predicate, obj in source:
                if predicate in (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf):
                    continue
                graph.add((renamed.get(subject, subject), predicate, renamed.get(obj, obj)))
            graph.add((renamed[original], SH.targetNode, URIRef(NODE_BASE + node["id"])))
        cfg = node.get("config", {})
        shape = URIRef(SHAPE_BASE + node["id"])
        focus = URIRef(NODE_BASE + node["id"])
        graph.add((shape, RDF.type, SH.NodeShape))
        graph.add((shape, SH.targetNode, focus))
        graph.add((shape, H5.profileSource, URIRef(_profile_iri(node))))
        for predicate, value in ((H5.path, cfg["path"]), (H5.kind, info["kind"]), (H5.profile, _profile_iri(node))):
            _shape_property(graph, shape, predicate, required=True, has_value=value)
        if info["kind"] == "dataset":
            for key, pred in (("dtype", H5.dtype), ("shape", H5.shape)):
                _shape_property(graph, shape, pred, required=True, has_value=str(cfg.get(key, "float64" if key == "dtype" else "0")))
        for field in _profile_required(node):
            _shape_property(graph, shape, _meta_key(field), required=True)
        for field in ("unit", "quantity"):
            if cfg.get(field):
                definition = next((f for f in info.get("fields", []) if f["predicate"] == str(_meta_key(field))), None)
                expected = _rdf_value(cfg[field], definition) if definition else Literal(str(cfg[field]))
                _shape_property(graph, shape, _meta_key(field), required=True, has_value=expected)
    return graph

def _shape_property(graph, shape, predicate, required=True, has_value=None):
    prop = BNode()
    graph.add((shape, SH.property, prop))
    graph.add((prop, SH.path, predicate))
    if required:
        graph.add((prop, SH.minCount, Literal(1, datatype=XSD.integer)))
    if has_value is not None:
        # SHACL hasValue uses literals for all HDF5 metadata; profileSource is a URI only for provenance.
        graph.add((prop, SH.hasValue, has_value if isinstance(has_value, (Literal, URIRef)) else Literal(has_value)))

def rdf_from_hdf5(design: dict[str, Any], f: h5py.File) -> Graph:
    graph = Graph()
    graph.bind("h5", H5)
    graph.bind("meta", META)
    for node in design["nodes"]:
        kind = node_template(node)["kind"]
        if not kind:
            continue
        path = node["config"]["path"]
        if path not in f:
            continue
        obj = f[path]
        subject = URIRef(NODE_BASE + node["id"])
        graph.add((subject, H5.path, Literal(path)))
        graph.add((subject, H5.kind, Literal("dataset" if isinstance(obj, h5py.Dataset) else "group")))
        if "profile_uri" in obj.attrs:
            graph.add((subject, H5.profile, Literal(str(obj.attrs["profile_uri"]))))
        if isinstance(obj, h5py.Dataset):
            graph.add((subject, H5.dtype, Literal(str(obj.dtype))))
            graph.add((subject, H5.shape, Literal(str(obj.attrs.get("designed_shape", ",".join(map(str, obj.shape)))))))
        for field in node_template(node).get("fields", []):
            key = field["key"]
            if key not in obj.attrs or str(obj.attrs[key]) == "": continue
            graph.add((subject, URIRef(field["predicate"]), _rdf_value(obj.attrs[key], field)))
        for key in set(_profile_required(node) + ["unit", "quantity"]):
            if any(f["predicate"] == str(_meta_key(key)) for f in node_template(node).get("fields", [])):
                continue
            if key in obj.attrs and str(obj.attrs[key]).strip():
                graph.add((subject, _meta_key(key), Literal(str(obj.attrs[key]))))
    return graph


def _rdf_value(raw, field):
    if isinstance(raw, bytes): raw = raw.decode("utf-8", errors="replace")
    value = str(raw)
    if field["datatype"].endswith("#boolean") and isinstance(raw, (bool, np.bool_)):
        value = value.lower()
    return URIRef(value) if field["datatype"] == "IRI" else Literal(value, datatype=URIRef(field["datatype"]), normalize=False)
