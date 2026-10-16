"""Compatibility facade. New integrations should use fair_hdf5.services.DesignService."""
from functools import lru_cache

from fair_hdf5.catalog import CATALOG, demo
from fair_hdf5.domain import parse_shape
from fair_hdf5.engines import _simple_shacl_check
from fair_hdf5.profiles import profile_iri as _profile_iri, profile_required as _profile_required
from fair_hdf5.semantic import rdf_from_hdf5, _meta_key
from fair_hdf5.services import DesignService
from fair_hdf5.settings import Settings
from fair_hdf5.vocabulary import ALLOWED_DTYPES, BASE, H5, META, PROFILES, NODE_BASE, SHAPE_BASE, ID_RE, KEY_RE


@lru_cache(maxsize=1)
def _service():
    return DesignService(Settings())


def normalize(design):
    return _service().normalize(design)


def _parse_shape(raw):
    return parse_shape(raw, _service().settings)


def build_shapes(design):
    return _service().shapes(design)


def shacl_turtle(design):
    return _service().shacl(design)


def hdf5_template(design):
    return _service().template(design)


def validate_hdf5(design, content):
    return _service().validate(design, content)


def structure_preview(design):
    return _service().preview(design)
