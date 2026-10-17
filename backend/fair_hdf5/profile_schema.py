"""Offline, deliberately bounded SHACL import and form compilation."""
from copy import deepcopy
from functools import lru_cache
import json
import math
import hashlib
import re
from urllib.parse import urlsplit
from rdflib import Graph, Literal, URIRef, RDF, BNode
from rdflib.namespace import SH, XSD
from .errors import DesignError
from .vocabulary import KEY_RE

DATATYPES = {str(XSD[x]) for x in ('string', 'boolean', 'integer', 'decimal', 'double', 'date', 'dateTime')}
RESERVED = {'path', 'dtype', 'shape', 'profile_uri', 'required_fields', 'design_node_id', 'design_label', 'design_type', 'designed_shape'}
NODE_PROPERTIES = {SH.property, SH.name, SH.description, SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf}
PROPERTY_PROPERTIES = {SH.path, SH.name, SH.description, SH.order, SH.group, SH.defaultValue, SH.datatype, SH.nodeKind, SH.minCount, SH.maxCount, SH['in'], SH.hasValue, SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength, SH.maxLength, SH.pattern, SH.flags, SH.message, SH.severity}

def absolute_iri(value):
    try:
        return isinstance(value, (str, URIRef)) and bool(urlsplit(str(value)).scheme) and not re.search(r'[\s<>"{}|\\^`]', str(value))
    except ValueError:
        return False

def parse_profile(ttl: str) -> Graph:
    if not isinstance(ttl, str) or len(ttl.encode()) > 1_000_000:
        raise DesignError('Profile must be Turtle text, at most 1 MB.')
    try:
        return Graph().parse(data=ttl, format='turtle', publicID='urn:fair-hdf5:import:')
    except Exception as exc:
        raise DesignError(f'Invalid Turtle: {exc}') from exc

def profile_hash(ttl: str) -> str:
    return hashlib.sha256(ttl.encode()).hexdigest()

def one(g, subject, predicate, default=None):
    values = list(g.objects(subject, predicate))
    if len(values) > 1:
        raise DesignError(f'{predicate}: multiple declarations are unsupported.')
    return values[0] if values else default

def compile_profile(ttl: str, shape_id: str, mapping: dict | None = None):
    if not isinstance(ttl, str) or not isinstance(shape_id, str):
        raise DesignError('Profile Turtle and shape IRI must be strings.')
    if mapping is not None and (not isinstance(mapping, dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in mapping.items())):
        raise DesignError('Field mapping must associate property IRIs with attribute names.')
    return deepcopy(_compile_profile(ttl, shape_id, json.dumps(mapping or {}, sort_keys=True)))


@lru_cache(maxsize=64)
def _compile_profile(ttl: str, shape_id: str, mapping_json: str):
    mapping = json.loads(mapping_json)
    if not absolute_iri(shape_id): raise DesignError("Shape must have an absolute IRI.")
    g = parse_profile(ttl)
    shape = URIRef(shape_id)
    if (shape, RDF.type, SH.NodeShape) not in g:
        raise DesignError('Select a named sh:NodeShape from the profile.')
    for s, p, o in g:
        if str(p).startswith(str(SH)) and p not in NODE_PROPERTIES | PROPERTY_PROPERTIES:
            raise DesignError(f'Unsupported SHACL feature: {p}')
    for p in g.predicates(shape):
        if str(p).startswith(str(SH)) and p not in NODE_PROPERTIES:
            raise DesignError(f'Unsupported node constraint: {p}')
    fields, used, predicates = [], set(), set()
    for prop in g.objects(shape, SH.property):
        for p in g.predicates(prop):
            if str(p).startswith(str(SH)) and p not in PROPERTY_PROPERTIES:
                raise DesignError(f'Unsupported property constraint: {p}')
        path = one(g, prop, SH.path)
        if not isinstance(path, URIRef) or not absolute_iri(path):
            raise DesignError('Only direct, absolute property IRIs are supported.')
        if str(path) in predicates:
            raise DesignError(f'Duplicate property path: {path}')
        predicates.add(str(path))
        minimum, maximum = one(g, prop, SH.minCount, Literal(0)), one(g, prop, SH.maxCount)
        if minimum not in (Literal(0), Literal(1)) or maximum != Literal(1):
            raise DesignError(f'{path}: requires sh:maxCount 1 and sh:minCount 0 or 1; lists are unsupported.')
        dtype = one(g, prop, SH.datatype)
        node_kind = one(g, prop, SH.nodeKind)
        if node_kind == SH.IRI and dtype is None:
            datatype = 'IRI'
        elif str(dtype) in DATATYPES and node_kind in (None, SH.Literal):
            datatype = str(dtype)
        else:
            raise DesignError(f'{path}: declare a supported sh:datatype or sh:nodeKind sh:IRI.')
        key = (mapping or {}).get(str(path))
        if key is None:
            key = re.sub('[^A-Za-z0-9_]', '_', str(path).rstrip('/').rsplit('/', 1)[-1].rsplit('#', 1)[-1])[:70]
            if not key or not key[0].isalpha(): key = 'field_' + key
            if key in RESERVED: key = 'metadata_' + key
            base, i = key, 2
            while key in used:
                key = f'{base}_{i}'; i += 1
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in used or key in RESERVED:
            raise DesignError(f'Invalid or duplicate HDF5 attribute name: {key}')
        used.add(key)
        field = {'key': key, 'predicate': str(path), 'label': str(one(g, prop, SH.name, Literal(key))), 'description': str(one(g, prop, SH.description, Literal(''))), 'datatype': datatype, 'required': minimum == Literal(1)}
        for name in ('defaultValue', 'hasValue', 'minInclusive', 'maxInclusive', 'minExclusive', 'maxExclusive', 'minLength', 'maxLength', 'pattern', 'flags'):
            value = one(g, prop, SH[name])
            if value is not None:
                if not isinstance(value, (Literal, URIRef)): raise DesignError(f'{path}: invalid {name}.')
                field[name] = str(value)
        if 'pattern' in field:
            flags = field.get('flags', '')
            if any(c not in 'imsx' for c in flags): raise DesignError(f'{path}: unsupported regex flags.')
            try: re.compile(field['pattern'], sum({'i':re.I,'m':re.M,'s':re.S,'x':re.X}[c] for c in set(flags)))
            except re.error as exc: raise DesignError(f'{path}: invalid pattern: {exc}') from exc
        order = one(g, prop, SH.order, Literal(0))
        try: field['order'] = float(order)
        except (ValueError, TypeError): raise DesignError(f'{path}: invalid field order.')
        if not math.isfinite(field['order']): raise DesignError(f'{path}: field order must be finite.')
        head = one(g, prop, SH['in'])
        if head is not None:
            try: values = list(g.items(head))
            except ValueError as exc: raise DesignError(f'{path}: invalid selection list.') from exc
            if any(not isinstance(v, (Literal, URIRef)) for v in values): raise DesignError('Only scalar selection values are supported.')
            field['choices'] = [str(v) for v in values]
        fields.append(field)
    # pySHACL's meta validator detects malformed counts, datatypes, patterns, and RDF lists.
    from pyshacl import validate
    try:
        validate(Graph(), shacl_graph=g, meta_shacl=True, advanced=False)
    except Exception as exc:
        raise DesignError(f'Invalid SHACL profile: {exc}') from exc
    return sorted(fields, key=lambda f: (f['order'], f['key']))

def analyze_profile(ttl: str):
    g = parse_profile(ttl)
    results = []
    for shape in sorted(set(g.subjects(RDF.type, SH.NodeShape)), key=str):
        item = {'shape': str(shape), 'label': str(g.value(shape, SH.name) or shape)}
        try:
            if not isinstance(shape, URIRef): raise DesignError('NodeShapes must have a stable IRI.')
            item['fields'] = compile_profile(ttl, str(shape))
            item['supported'] = True
        except DesignError as exc:
            item.update(supported=False, error=str(exc))
        results.append(item)
    if not results: raise DesignError('No sh:NodeShape found.')
    return {'shapes': results}

def profile_from_fields(shape_id: str, fields: list[dict]) -> str:
    if not isinstance(fields, list) or any(not isinstance(f, dict) or not isinstance(f.get('key'), str) or not KEY_RE.fullmatch(f['key']) or f['key'] in RESERVED for f in fields): raise DesignError('Fields must be objects with attribute keys.')
    if not absolute_iri(shape_id): raise DesignError('Profile shape must have an absolute IRI.')
    g, shape = Graph(), URIRef(shape_id)
    g.bind('sh', SH); g.bind('xsd', XSD)
    g.add((shape, RDF.type, SH.NodeShape))
    for index, field in enumerate(fields):
        if not absolute_iri(field.get('predicate', '')): raise DesignError('Each field needs an absolute property IRI.')
        prop = BNode()
        g.add((shape, SH.property, prop)); g.add((prop, SH.path, URIRef(field['predicate'])))
        dtype = field.get('datatype', str(XSD.string))
        if dtype == 'IRI': g.add((prop, SH.nodeKind, SH.IRI))
        elif dtype in DATATYPES: g.add((prop, SH.datatype, URIRef(dtype)))
        else: raise DesignError('Unsupported field datatype.')
        g.add((prop, SH.maxCount, Literal(1)))
        g.add((prop, SH.minCount, Literal(1 if field.get('required') else 0)))
        g.add((prop, SH.name, Literal(field.get('label') or field['key'])))
        g.add((prop, SH.description, Literal(field.get('description', ''))))
        g.add((prop, SH.order, Literal(index)))
        for name in ('minInclusive', 'maxInclusive', 'minExclusive', 'maxExclusive', 'minLength', 'maxLength', 'pattern', 'flags', 'defaultValue', 'hasValue'):
            value = field.get(name)
            if value is None or value == '': continue
            term = Literal(str(value))
            if name in ('minLength', 'maxLength'): term = Literal(str(value), datatype=XSD.integer)
            elif name not in ('pattern', 'flags'):
                term = URIRef(str(value)) if dtype == 'IRI' else Literal(str(value), datatype=URIRef(dtype), normalize=False)
            g.add((prop, SH[name], term))
        if field.get('choices') and (not isinstance(field['choices'], list) or any(not isinstance(v, (str,int,float,bool)) for v in field['choices'])): raise DesignError('Choices must be a list of scalar values.')
        if field.get('choices'):
            from rdflib.collection import Collection
            head = BNode(); g.add((prop, SH['in'], head))
            Collection(g, head, [URIRef(str(v)) if dtype == 'IRI' else Literal(str(v), datatype=URIRef(dtype), normalize=False) for v in field['choices']])
    return g.serialize(format='turtle')
