"""Offline, deliberately bounded SHACL import and form compilation."""

import hashlib
import json
import math
import re
from copy import deepcopy
from functools import lru_cache
from urllib.parse import urlsplit

from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, RDFS, SH, XSD

from .errors import DesignError
from .profile_bundles import bundle_graph
from .vocabulary import KEY_RE

DATATYPES = {
    str(XSD[x]) for x in ("string", "boolean", "integer", "decimal", "double", "date", "dateTime")
}
RESERVED = {
    "path",
    "dtype",
    "shape",
    "profile_uri",
    "required_fields",
    "design_node_id",
    "design_label",
    "design_type",
    "designed_shape",
}
NODE_PROPERTIES = {
    SH.property,
    SH.node,
    SH.name,
    SH.description,
    SH.targetClass,
    SH.targetNode,
    SH.targetSubjectsOf,
    SH.targetObjectsOf,
    SH.closed,
}
PROPERTY_PROPERTIES = {
    SH.node,
    SH.qualifiedValueShape,
    SH.qualifiedMinCount,
    SH.qualifiedMaxCount,
    SH.qualifiedValueShapesDisjoint,
    SH.path,
    SH.name,
    SH.description,
    SH.order,
    SH.group,
    SH.defaultValue,
    SH.datatype,
    SH.nodeKind,
    SH["class"],
    SH.xone,
    SH.minCount,
    SH.maxCount,
    SH["in"],
    SH.hasValue,
    SH.minInclusive,
    SH.maxInclusive,
    SH.minExclusive,
    SH.maxExclusive,
    SH.minLength,
    SH.maxLength,
    SH.pattern,
    SH.flags,
    SH.message,
    SH.severity,
}


def absolute_iri(value):
    try:
        return (
            isinstance(value, (str, URIRef))
            and bool(urlsplit(str(value)).scheme)
            and not re.search(r'[\s<>"{}|\\^`]', str(value))
        )
    except ValueError:
        return False


def parse_profile(ttl: str) -> Graph:
    if not isinstance(ttl, str) or len(ttl.encode()) > 1_000_000:
        raise DesignError("Profile must be Turtle text, at most 1 MB.")
    try:
        return Graph().parse(data=ttl, format="turtle", publicID="urn:fair-hdf5:import:")
    except Exception as exc:
        raise DesignError(f"Invalid Turtle: {exc}") from exc


def profile_hash(ttl: str) -> str:
    return hashlib.sha256(ttl.encode()).hexdigest()


def one(g, subject, predicate, default=None):
    values = list(g.objects(subject, predicate))
    if len(values) > 1:
        raise DesignError(f"{predicate}: multiple declarations are unsupported.")
    return values[0] if values else default


def localized(graph, subject, predicate):
    values = sorted(
        graph.objects(subject, predicate), key=lambda v: (getattr(v, "language", "") or "", str(v))
    )
    return {getattr(v, "language", None) or "": str(v) for v in values}


def display_text(values, fallback):
    return values.get("en") or values.get("") or next(iter(values.values()), fallback)


def count(graph, subject, predicate, default):
    value = one(graph, subject, predicate)
    if value is None:
        return default
    if (
        not isinstance(value, Literal)
        or value.datatype != XSD.integer
        or value.ill_typed
        or int(value) < 0
    ):
        raise DesignError(f"{predicate}: expected a nonnegative integer.")
    return int(value)


def compile_profile(
    ttl: str, shape_id: str, mapping: dict | None = None, documents=None, source_uri=None
):
    if not isinstance(ttl, str) or not isinstance(shape_id, str):
        raise DesignError("Profile Turtle and shape IRI must be strings.")
    if mapping is not None and (
        not isinstance(mapping, dict)
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items())
    ):
        raise DesignError("Field mapping must associate property IRIs with attribute names.")
    return deepcopy(
        _compile_profile(
            ttl,
            shape_id,
            json.dumps(mapping or {}, sort_keys=True),
            json.dumps(documents or {}, sort_keys=True),
            source_uri,
        )
    )


@lru_cache(maxsize=64)
def _compile_profile(
    ttl: str, shape_id: str, mapping_json: str, documents_json: str, source_uri: str | None
):
    mapping = json.loads(mapping_json)
    if not absolute_iri(shape_id):
        raise DesignError("Shape must have an absolute IRI.")
    g = bundle_graph(ttl, source_uri, json.loads(documents_json))
    shape = URIRef(shape_id)
    if (shape, RDF.type, SH.NodeShape) not in g:
        raise DesignError("Select a named sh:NodeShape from the profile.")
    for _subject, p, _object in g:
        if str(p).startswith(str(SH)) and p not in NODE_PROPERTIES | PROPERTY_PROPERTIES:
            raise DesignError(f"Unsupported SHACL feature: {p}")
    for p in g.predicates(shape):
        if str(p).startswith(str(SH)) and p not in NODE_PROPERTIES:
            raise DesignError(f"Unsupported node constraint: {p}")
    for target_shape in g.objects(shape, SH.node):
        if not isinstance(target_shape, URIRef) or (target_shape, RDF.type, SH.NodeShape) not in g:
            raise DesignError(f"Missing named referenced shape: {target_shape}")
    if one(g, shape, SH.closed, Literal(False)) != Literal(False):
        raise DesignError("Closed shapes are not supported yet.")
    fields, used, predicates = [], set(), {}
    for prop in g.objects(shape, SH.property):
        for p in g.predicates(prop):
            if str(p).startswith(str(SH)) and p not in PROPERTY_PROPERTIES:
                raise DesignError(f"Unsupported property constraint: {p}")
        path = one(g, prop, SH.path)
        if not isinstance(path, URIRef) or not absolute_iri(path):
            raise DesignError("Only direct, absolute property IRIs are supported.")
        minimum = count(g, prop, SH.minCount, 0)
        maximum = count(g, prop, SH.maxCount, None)
        if maximum is not None and maximum < minimum:
            raise DesignError(f"{path}: inconsistent cardinality.")
        reference = one(g, prop, SH.node)
        qualified = one(g, prop, SH.qualifiedValueShape)
        if reference is not None and qualified is not None:
            raise DesignError(
                "Combined sh:node and qualified shapes need separate property entries."
            )
        target_shape = reference or qualified
        if target_shape is not None and (
            not isinstance(target_shape, URIRef) or (target_shape, RDF.type, SH.NodeShape) not in g
        ):
            raise DesignError(f"Missing named referenced shape: {target_shape}")
        dtype = one(g, prop, SH.datatype)
        node_kind = one(g, prop, SH.nodeKind)
        class_iri = one(g, prop, SH["class"])
        if class_iri is not None and (
            not isinstance(class_iri, URIRef) or not absolute_iri(class_iri)
        ):
            raise DesignError(f"{path}: sh:class must reference an absolute class IRI.")
        xone = one(g, prop, SH.xone)
        datatype_options = []
        datatype_labels = []
        if xone is not None:
            if dtype is not None or class_iri is not None or target_shape is not None:
                raise DesignError(
                    f"{path}: sh:xone cannot be combined with a direct datatype, class, or referenced shape."
                )
            try:
                alternatives = list(g.items(xone))
            except ValueError as exc:
                raise DesignError(f"{path}: sh:xone must contain a valid RDF list.") from exc
            if len(alternatives) < 2:
                raise DesignError(f"{path}: sh:xone requires at least two alternatives.")
            for alternative in alternatives:
                alternative_datatype = one(g, alternative, SH.datatype)
                if alternative_datatype not in (XSD.integer, XSD.double):
                    raise DesignError(
                        f"{path}: sh:xone currently supports only xsd:integer and xsd:double alternatives."
                    )
                allowed = {SH.datatype, RDFS.label, RDF.type}
                if any(predicate not in allowed for predicate in g.predicates(alternative)):
                    raise DesignError(
                        f"{path}: each sh:xone alternative may contain only sh:datatype and rdfs:label."
                    )
                datatype_options.append(str(alternative_datatype))
                datatype_labels.append(
                    display_text(
                        localized(g, alternative, RDFS.label),
                        str(alternative_datatype).rsplit("#", 1)[-1],
                    )
                )
        if (
            target_shape is not None
            and dtype is None
            and node_kind in (None, SH.IRI, SH.BlankNodeOrIRI)
        ):
            datatype = "reference"
        elif node_kind == SH.IRI and dtype is None:
            datatype = "IRI"
        elif class_iri is not None and dtype is None and node_kind in (None, SH.IRI):
            datatype = "IRI"
        elif datatype_options:
            datatype = datatype_options[0]
        elif str(dtype) in DATATYPES and node_kind in (None, SH.Literal):
            datatype = str(dtype)
        else:
            raise DesignError(f"{path}: declare a supported sh:datatype or sh:nodeKind sh:IRI.")
        key = predicates.get(str(path), (mapping or {}).get(str(path)))
        if key is None:
            key = re.sub(
                "[^A-Za-z0-9_]", "_", str(path).rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            )[:70]
            if not key or not key[0].isalpha():
                key = "field_" + key
            if key in RESERVED:
                key = "metadata_" + key
            base, i = key, 2
            while key in used:
                key = f"{base}_{i}"
                i += 1
        if (
            not isinstance(key, str)
            or not KEY_RE.fullmatch(key)
            or (key in used and predicates.get(str(path)) != key)
            or key in RESERVED
        ):
            raise DesignError(f"Invalid or duplicate HDF5 attribute name: {key}")
        used.add(key)
        predicates[str(path)] = key
        labels, descriptions = localized(g, prop, SH.name), localized(g, prop, SH.description)
        signature = Graph()
        # Canonicalize the property subgraph so IDs survive blank-node relabeling.
        pending, seen = [prop], set()
        while pending:
            subject = pending.pop()
            if subject in seen:
                continue
            seen.add(subject)
            for triple in g.triples((subject, None, None)):
                signature.add(triple)
                if isinstance(triple[2], BNode):
                    pending.append(triple[2])
        canonical = "\n".join(
            sorted(" ".join(t.n3() for t in triple) for triple in to_canonical_graph(signature))
        )
        field = {
            "id": hashlib.sha256((shape_id + canonical).encode()).hexdigest()[:24],
            "key": key,
            "predicate": str(path),
            "label": display_text(labels, key),
            "labels": labels,
            "description": display_text(descriptions, ""),
            "descriptions": descriptions,
            "datatype": datatype,
            "kind": "reference" if target_shape else "literal",
            "required": minimum > 0,
            "minCount": minimum,
            "maxCount": maximum,
            "multiple": maximum != 1,
            "multiline": one(g, prop, URIRef("http://datashapes.org/dash#singleLine"))
            == Literal(False),
        }
        if class_iri is not None:
            field["class"] = str(class_iri)
        if datatype_options:
            field["datatype_options"] = datatype_options
            field["datatype_labels"] = datatype_labels
        if target_shape:
            disjoint = one(g, prop, SH.qualifiedValueShapesDisjoint, Literal(False))
            if (
                not isinstance(disjoint, Literal)
                or disjoint.datatype != XSD.boolean
                or type(disjoint.value) is not bool
            ):
                raise DesignError("sh:qualifiedValueShapesDisjoint must be a boolean.")
            field.update(
                targetShape=str(target_shape),
                qualification="all" if reference else "qualified",
                qualifiedMinCount=count(g, prop, SH.qualifiedMinCount, None),
                qualifiedMaxCount=count(g, prop, SH.qualifiedMaxCount, None),
                qualifiedDisjoint=disjoint.value,
            )
        for name in (
            "defaultValue",
            "hasValue",
            "minInclusive",
            "maxInclusive",
            "minExclusive",
            "maxExclusive",
            "minLength",
            "maxLength",
            "pattern",
            "flags",
        ):
            value = one(g, prop, SH[name])
            if value is not None:
                if not isinstance(value, (Literal, URIRef)):
                    raise DesignError(f"{path}: invalid {name}.")
                field[name] = str(value)
        if "pattern" in field:
            flags = field.get("flags", "")
            if any(c not in "imsx" for c in flags):
                raise DesignError(f"{path}: unsupported regex flags.")
            try:
                re.compile(
                    field["pattern"],
                    sum({"i": re.I, "m": re.M, "s": re.S, "x": re.X}[c] for c in set(flags)),
                )
            except re.error as exc:
                raise DesignError(f"{path}: invalid pattern: {exc}") from exc
        order = one(g, prop, SH.order, Literal(0))
        try:
            field["order"] = float(order)
        except (ValueError, TypeError) as exc:
            raise DesignError(f"{path}: invalid field order.") from exc
        if not math.isfinite(field["order"]):
            raise DesignError(f"{path}: field order must be finite.")
        head = one(g, prop, SH["in"])
        if head is not None:
            try:
                values = list(g.items(head))
            except ValueError as exc:
                raise DesignError(f"{path}: invalid selection list.") from exc
            if any(not isinstance(v, (Literal, URIRef)) for v in values):
                raise DesignError("Only scalar selection values are supported.")
            field["choices"] = [str(v) for v in values]
        fields.append(field)
    # pySHACL's meta validator detects malformed counts, datatypes, patterns, and RDF lists.
    from pyshacl import validate

    try:
        validate(Graph(), shacl_graph=executable_shapes(g), meta_shacl=True, advanced=False)
    except Exception as exc:
        raise DesignError(f"Invalid SHACL profile: {exc}") from exc
    return sorted(fields, key=lambda f: (f["order"], f["key"]))


def executable_shapes(source):
    """Omit inert qualified-shape annotations for pySHACL compatibility.

    Without either count there is no qualified constraint component to execute.
    Original documents and the field model retain these reference declarations.
    """
    graph = Graph()
    for prefix, namespace in source.namespaces():
        graph.bind(prefix, namespace)
    for subject, predicate, obj in source:
        if (
            predicate in (SH.qualifiedValueShape, SH.qualifiedValueShapesDisjoint)
            and (subject, SH.qualifiedMinCount, None) not in source
            and (subject, SH.qualifiedMaxCount, None) not in source
        ):
            continue
        graph.add((subject, predicate, obj))
    return graph


def analyze_profile(ttl: str, documents=None, source_uri=None):
    g = bundle_graph(ttl, source_uri, documents)
    results = []
    for shape in sorted(set(g.subjects(RDF.type, SH.NodeShape)), key=str):
        item = {
            "shape": str(shape),
            "label": display_text(
                localized(g, shape, DCTERMS.title) or localized(g, shape, SH.name), str(shape)
            ),
            "titles": localized(g, shape, DCTERMS.title),
            "descriptions": localized(g, shape, DCTERMS.description),
        }
        try:
            if not isinstance(shape, URIRef):
                raise DesignError("NodeShapes must have a stable IRI.")
            item["fields"] = compile_profile(
                ttl, str(shape), documents=documents, source_uri=source_uri
            )
            item["supported"] = True
        except DesignError as exc:
            item.update(supported=False, error=str(exc))
        results.append(item)
    if not results:
        raise DesignError("No sh:NodeShape found.")
    return {"shapes": results, "documents": documents or {}, "source_uri": source_uri}


def profile_from_fields(shape_id: str, fields: list[dict]) -> str:
    if not isinstance(fields, list) or any(
        not isinstance(f, dict)
        or not isinstance(f.get("key"), str)
        or not KEY_RE.fullmatch(f["key"])
        or f["key"] in RESERVED
        for f in fields
    ):
        raise DesignError("Fields must be objects with attribute keys.")
    if not absolute_iri(shape_id):
        raise DesignError("Profile shape must have an absolute IRI.")
    g, shape = Graph(), URIRef(shape_id)
    g.bind("sh", SH)
    g.bind("xsd", XSD)
    g.add((shape, RDF.type, SH.NodeShape))
    for index, field in enumerate(fields):
        if not absolute_iri(field.get("predicate", "")):
            raise DesignError("Each field needs an absolute property IRI.")
        prop = BNode()
        g.add((shape, SH.property, prop))
        g.add((prop, SH.path, URIRef(field["predicate"])))
        dtype = field.get("datatype", str(XSD.string))
        if dtype == "IRI":
            g.add((prop, SH.nodeKind, SH.IRI))
        elif dtype in DATATYPES:
            g.add((prop, SH.datatype, URIRef(dtype)))
        else:
            raise DesignError("Unsupported field datatype.")
        if field.get("class"):
            g.add((prop, SH["class"], URIRef(field["class"])))
        maximum = field.get("maxCount", None if field.get("multiple") else 1)
        minimum = field.get("minCount", 1 if field.get("required") else 0)
        if (
            type(minimum) is not int
            or minimum < 0
            or (maximum is not None and (type(maximum) is not int or maximum < minimum))
        ):
            raise DesignError("Invalid field cardinality.")
        if maximum is not None:
            g.add((prop, SH.maxCount, Literal(maximum)))
        g.add((prop, SH.minCount, Literal(minimum)))
        g.add((prop, SH.name, Literal(field.get("label") or field["key"])))
        g.add((prop, SH.description, Literal(field.get("description", ""))))
        g.add((prop, SH.order, Literal(index)))
        for name in (
            "minInclusive",
            "maxInclusive",
            "minExclusive",
            "maxExclusive",
            "minLength",
            "maxLength",
            "pattern",
            "flags",
            "defaultValue",
            "hasValue",
        ):
            value = field.get(name)
            if value is None or value == "":
                continue
            term = Literal(str(value))
            if name in ("minLength", "maxLength"):
                term = Literal(str(value), datatype=XSD.integer)
            elif name not in ("pattern", "flags"):
                term = (
                    URIRef(str(value))
                    if dtype == "IRI"
                    else Literal(str(value), datatype=URIRef(dtype), normalize=False)
                )
            g.add((prop, SH[name], term))
        if field.get("choices") and (
            not isinstance(field["choices"], list)
            or any(not isinstance(v, (str, int, float, bool)) for v in field["choices"])
        ):
            raise DesignError("Choices must be a list of scalar values.")
        if field.get("choices"):
            from rdflib.collection import Collection

            head = BNode()
            g.add((prop, SH["in"], head))
            Collection(
                g,
                head,
                [
                    URIRef(str(v))
                    if dtype == "IRI"
                    else Literal(str(v), datatype=URIRef(dtype), normalize=False)
                    for v in field["choices"]
                ],
            )
    return g.serialize(format="turtle")
