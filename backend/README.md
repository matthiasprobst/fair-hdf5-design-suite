# Backend

Python code, dependency declarations, and backend/API tests live here.
Shared deployment files, `.env`, examples, and full-app browser tests remain at
the repository root. The React application lives in the sibling `frontend/`.

## Setup and launch

From the repository root, with the virtual environment activated:

```bash
python -m pip install -e ./backend
python -m fair_hdf5
```

From this directory, the equivalent installation command is
`python -m pip install -e .`. The editable install makes `fair_hdf5` importable
without setting `PYTHONPATH` and keeps code changes visible immediately.
Local development and Docker both retain this source layout, so `.env`, relative
configuration paths, and `frontend/dist` resolve from the repository root.

For the whole app, use `./start.sh` from the repository root. The root `app.py`
and requirements files are compatibility entry points for existing commands.
Python integrations import `fair_hdf5.catalog` for catalog/demo data and
`fair_hdf5.services.DesignService` for preview, export, and validation.

## Responsibilities

- `application` creates the FastAPI app and wires shared dependencies; `api` owns HTTP transport.
- `services.DesignService` coordinates preview, export, and validation.
- `account_service` owns local authentication, sessions and administrator use cases;
  `access.Principal` keeps project policy independent of the login mechanism.
- `project_service` owns project/membership/lease policy; `project_catalog` composes
  private project templates with the read-only installation catalog.
- `database` owns SQLite connections and versioned SQL migrations. Rights, leases
  and revisions are checked in the same short write transaction.
- `project_blueprint` validates editable storage envelopes; incomplete scientific
  designs remain saveable independently of `domain` validation.
- `services.CatalogService` coordinates profile analysis and template publication. Both HTTP and Python callers use these services for application behavior.
- `domain` parses blueprint envelopes and checks scientific/storage constraints; `templates` normalizes portable snapshots and derives related profiles. Neither imports the file repository.
- `repositories` defines the storage protocol; `library` implements immutable file storage, caching, locking, and atomic revision checks.
- `catalog`, `profiles`, and `vocabulary` provide seed definitions and shared profile access.
- `profile_schema` compiles supported SHACL form fields; `profile_bundles` resolves pinned dependencies and bounds explicit network imports.
- `hdf5` handles file generation, uploaded files, and structural checks; `semantic` projects metadata to RDF and builds shapes; `engines` executes SHACL validation.
- `settings` validates configuration; `errors` contains domain errors; `compat` preserves the legacy function API.

Keep dependencies directed toward the shared rules and storage contracts. HTTP
handlers translate transport inputs and delegate; they do not compile profiles
or call the repository. Services prepare and validate snapshots before storing
them. The file repository rechecks the expected revision under its process/file
lock, so concurrent writers cannot overwrite an existing revision. Reads return
independent snapshots; published files are never edited in place.

Retain extensible blueprint fields and the supported snapshot schemas when
changing models. Add behavior tests at the relevant service boundary and HTTP
contract tests when status codes or response handling are affected. Test fixtures
inherit the catalog isolation helpers in `tests/support.py`, including async tests.
Network-import tests use controlled responses and do not require live providers.

`pyproject.toml` reads runtime dependencies from `requirements.txt`, keeping
version constraints in one place. `requirements-shacl.txt` remains a compatibility
include because full pySHACL is now a standard dependency.

## Tests

From the repository root:

```bash
python -m pip install -e ./backend -r backend/requirements-dev.txt
python -m unittest discover -s backend/tests -v
ruff check .
ruff format --check .
```

From this directory, use `python -m unittest discover -s tests -v` instead.
Full-app Playwright checks remain in the root `tests/` directory.

## CSV inputs

Built-in `csv_source` nodes are operational inputs rather than SHACL templates. Their scalar configuration contains `delimiter`, `decimal_separator`, `has_header`, `filename`, and a string-array `columns` manifest. Data edges carry `kind: "data"`, `column_index`, and `relation: "provides_data"`; each connects a source to a single Dataset node. Legacy edges omit `kind`.

CSV nodes also accept regular relationship edges (without `kind`, `column_index`, or HDF5 profile-reference fields). `generated` points from a producer to a CSV data node; `was_generated_by` points in the reverse direction. These connections describe provenance and remain independent of executable column bindings.

Authenticated, CSRF-protected `POST /api/data/csv/preview` accepts multipart `settings_json` and `file`, returning `columns`, `row_count`, `suggested_dtypes`, and at most 50 preview `rows`. `POST /api/export/hdf5/data` accepts multipart `design_json` plus one file field named for each connected source-node ID, returning an HDF5 attachment. Uploads are closed at request completion and are not persisted. `csv_data.py` owns parsing and checked conversions; `DesignService` owns input resolution and export orchestration. Existing template/SHACL APIs do not require source files.

## Example gallery

Authenticated `GET /api/examples` lists the current bundled definitions; `GET /api/examples/{id}` returns a normalized, read-only blueprint. These routes never create projects, leases, or user-specific copies. `POST /api/examples/{id}/copy` is CSRF-protected and creates one ordinary private project for the current user from the current server-side definition. Each explicit copy has a fresh project ID and pinned template snapshots. Unknown examples return 404; unsupported graph sizes fail before a project is written. Examples have no update/delete endpoints: maintain them with the bundled application definitions.

`GET /api/projects` only lists owned/shared projects. The legacy `user_examples` table and nullable project-summary `example_id` remain readable so existing personal copies survive unchanged; new gallery copies are normal projects and do not create provisioning receipts. No account creation or dashboard operation automatically copies examples. Updating bundled definitions changes subsequent gallery reads and explicit copies without modifying previously copied projects.

The read-only preview uses the existing workbench with graph mutation disabled and only artifact/CSV-session lifecycles active. It never starts project polling, autosave, recovery writes, or lease acquisition. CSV nodes may include the optional `example_file: "measurements.csv"` hint; other file references are rejected. The authenticated `GET /api/examples/files/measurements.csv` endpoint serves only this packaged, synthetic asset. Loading it keeps it in preview/project session memory and never embeds it in saved blueprints.

## DCAT and PROV metadata

Authenticated, CSRF-protected `POST /api/export/rdf` accepts the same blueprint JSON as the SHACL endpoint and returns `experiment.metadata.ttl`. `provenance.py` builds the declared RDF graph offline: CSV nodes become `dcat:Dataset` resources with a distinct `dcat:Distribution`, an IANA CSV media-type IRI, and optional filename title. No upload, download URL, timestamp, or acquisition identity is inferred from a local filename.

Producer/CSV relationships create a `prov:Activity` that `prov:used` the producer equipment/entity; both the dataset and CSV distribution reference it through `prov:wasGeneratedBy`. Column bindings declare target `prov:wasDerivedFrom` and import activities using the source distribution, with `h5:csvColumnIndex` and optional `h5:csvColumnName`. Other modeled relationships retain their declared predicates (or the application metadata namespace); `related_to` uses `dcterms:relation`.

HDF5 materialization embeds the same graph in `/__design__/metadata_ttl` and its scope in the design group's `metadata_note` attribute. This is a declared design graph, including for empty templates, and is deliberately separate from the RDF projection used for file conformance. Do not feed these expected declarations back into validation as evidence that an actual acquisition happened. The existing SHACL export and HDF5 validation contract remain unchanged.
