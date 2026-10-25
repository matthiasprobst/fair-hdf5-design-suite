"""Bounded import resolution. Saved bundles are validated entirely offline."""

import hashlib
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit

from rdflib import OWL, RDF, Graph, URIRef
from rdflib.namespace import SH

from .errors import DesignError


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_document(ttl, uri):
    if not isinstance(ttl, str):
        raise DesignError("Expected Turtle text.")
    try:
        return Graph().parse(data=ttl, format="turtle", publicID=uri or "urn:fair-hdf5:import:")
    except Exception as exc:
        raise DesignError(f"Invalid Turtle at {uri}: {exc}") from exc


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, address, timeout):
        super().__init__(hostname, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_document(uri, settings):
    current = uri
    try:
        parsed = urlsplit(current)
        port = parsed.port
    except ValueError as exc:
        raise DesignError(f"Invalid profile import URL: {current}") from exc
    if parsed.scheme == "http":
        if not parsed.hostname or parsed.username or parsed.password or port not in (None, 80):
            raise DesignError(f"Profile imports require public HTTPS URLs: {current}")
        # Upgrade only the requested import. Redirects are still required to use
        # HTTPS, so a server cannot redirect the resolver through plaintext HTTP.
        hostname = parsed.hostname
        netloc = f"[{hostname}]" if ":" in hostname else hostname
        current = urlunsplit(("https", netloc, parsed.path, parsed.query, parsed.fragment))
    for _ in range(settings.profile_max_redirects + 1):
        try:
            parsed = urlsplit(current)
            port = parsed.port
        except ValueError as exc:
            raise DesignError(f"Invalid profile import URL: {current}") from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or port not in (None, 443)
        ):
            raise DesignError(f"Profile imports require public HTTPS URLs: {current}")
        try:
            # Preserve resolver order and try every vetted address. Sorting textual
            # IPs can put an unreachable IPv6 address ahead of a working IPv4 one.
            addresses = list(
                dict.fromkeys(
                    a[4][0]
                    for a in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
                )
            )
            if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
                raise DesignError(f"Profile import must resolve to public addresses: {current}")
            failures = []
            redirected = False
            for address in addresses:
                connection = PinnedHTTPSConnection(
                    parsed.hostname, address, settings.profile_fetch_timeout
                )
                try:
                    connection.request(
                        "GET",
                        parsed.path + ("?" + parsed.query if parsed.query else ""),
                        headers={"Accept": "text/turtle", "User-Agent": "FAIR-HDF5-Design-Suite"},
                    )
                    response = connection.getresponse()
                    if response.status in (301, 302, 303, 307, 308):
                        location = response.getheader("Location")
                        if not location:
                            raise DesignError(f"Missing redirect location: {current}")
                        current = urljoin(current, location)
                        redirected = True
                        break
                    if response.status != 200:
                        raise DesignError(f"Profile import HTTP {response.status}: {current}")
                    data = response.read(settings.profile_max_document_bytes + 1)
                    if len(data) > settings.profile_max_document_bytes:
                        raise DesignError(f"Profile exceeds document limit: {current}")
                    return data.decode("utf-8"), current
                except DesignError:
                    raise
                except (OSError, ValueError, http.client.HTTPException) as exc:
                    failures.append(f"{address}: {exc}")
                finally:
                    connection.close()
            if redirected:
                continue
            if failures:
                raise DesignError(
                    f"Cannot fetch {uri}: all resolved addresses failed ({'; '.join(failures)}). Upload this dependency file instead."
                )
        except DesignError:
            raise
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise DesignError(
                f"Cannot fetch {uri}: {exc}. Upload this dependency file instead."
            ) from exc
    raise DesignError(f"Too many redirects fetching {uri}.")


def resolve_bundle(ttl, source_uri, supplied, settings, fetch=False):
    if not isinstance(ttl, str) or len(ttl.encode("utf-8")) > settings.profile_max_document_bytes:
        raise DesignError("Root profile exceeds document limit or is not Turtle text.")
    root = parse_document(ttl, source_uri)
    source_uri = source_uri or str(
        next(root.subjects(RDF.type, SH.NodeShape), "urn:fair-hdf5:root:")
    )
    supplied = supplied or {}
    if not isinstance(supplied, dict):
        raise DesignError("Dependencies must be keyed by their requested URI.")
    documents, active = {}, set()
    total = 0

    def visit(uri, text, resolved, depth):
        nonlocal total
        if uri in active:
            raise DesignError(f"Cyclic profile import: {uri}")
        if uri in documents:
            return
        if depth > settings.profile_max_depth:
            raise DesignError("Profile dependency depth exceeded.")
        if len(documents) >= settings.profile_max_documents:
            raise DesignError("Too many profile documents.")
        size = len(text.encode("utf-8"))
        total += size
        if size > settings.profile_max_document_bytes or total > settings.profile_max_total_bytes:
            raise DesignError("Profile bundle size limit exceeded.")
        graph = parse_document(text, uri)
        active.add(uri)
        documents[uri] = {"ttl": text, "hash": digest(text), "resolved_url": resolved}
        # Only imported documents that provide an explicitly referenced SHACL
        # shape are needed to compile and validate this profile. Vocabulary
        # ontologies (for example QUDT) can contain thousands of unrelated terms.
        shape_refs = {
            target
            for predicate in (SH.node, SH.qualifiedValueShape)
            for target in graph.objects(None, predicate)
            if isinstance(target, URIRef)
        }
        defined_shapes = set(graph.subjects(RDF.type, SH.NodeShape))
        shape_refs.difference_update(defined_shapes)
        imports = set(graph.objects(None, OWL.imports))
        if any(not isinstance(target, URIRef) for target in imports):
            raise DesignError("owl:imports must reference a document IRI.")
        needed_imports = {
            target for target in imports if target in shape_refs or str(target) in supplied
        }
        for target in sorted(needed_imports, key=str):
            if not isinstance(target, URIRef):
                raise DesignError("owl:imports must reference a document IRI.")
            target = str(target)
            if target in active:
                raise DesignError(f"Cyclic profile import: {target}")
            if target in documents:
                continue
            item = supplied.get(target)
            if item is not None:
                if not isinstance(item, dict) or not isinstance(item.get("ttl"), str):
                    raise DesignError(f"Invalid dependency: {target}")
                if item.get("hash", digest(item["ttl"])) != digest(item["ttl"]):
                    raise DesignError(f"Dependency hash mismatch: {target}")
                content, final_url = item["ttl"], item.get("resolved_url", target)
            elif fetch:
                content, final_url = fetch_document(target, settings)
            else:
                raise DesignError(
                    f"Missing pinned dependency: {target}. Analyze imports or upload its Turtle file."
                )
            visit(target, content, final_url, depth + 1)
        active.remove(uri)

    visit(source_uri, ttl, source_uri, 0)
    documents.pop(source_uri)
    return source_uri, documents


def bundle_graph(ttl, source_uri=None, documents=None):
    graph = parse_document(ttl, source_uri)
    for uri, item in sorted((documents or {}).items()):
        graph += parse_document(item["ttl"], uri)
    return graph


def unbundled_imports(ttl, source_uri=None, documents=None):
    """List imports from loaded shape documents that were intentionally not fetched."""
    graph = bundle_graph(ttl, source_uri, documents)
    imported = {str(uri) for uri in graph.objects(None, OWL.imports) if isinstance(uri, URIRef)}
    defined_shapes = {str(shape) for shape in graph.subjects(RDF.type, SH.NodeShape)}
    return sorted(imported - set(documents or {}) - defined_shapes)
