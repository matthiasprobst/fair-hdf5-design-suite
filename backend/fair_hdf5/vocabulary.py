"""Stable scientific identifiers and schema constants."""

import re

from rdflib import Namespace

BASE = "https://w3id.org/fair-hdf5-designer/demo/"
H5 = Namespace(BASE + "hdf5#")
META = Namespace(BASE + "metadata#")
PROFILES = Namespace(BASE + "profiles/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
PROV = Namespace("http://www.w3.org/ns/prov#")
NODE_BASE = BASE + "node/"
SHAPE_BASE = BASE + "shape/"

ALLOWED_DTYPES = {"float32", "float64", "int32", "int64", "uint8", "uint16", "string"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,90}$")
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
