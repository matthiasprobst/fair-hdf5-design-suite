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

Authenticated, CSRF-protected `POST /api/data/csv/preview` accepts multipart `settings_json` and `file`, returning `columns`, `row_count`, `suggested_dtypes`, and at most 50 preview `rows`. `POST /api/export/hdf5/data` accepts multipart `design_json` plus one file field named for each connected source-node ID, returning an HDF5 attachment. Uploads are closed at request completion and are not persisted. `csv_data.py` owns parsing and checked conversions; `DesignService` owns input resolution and export orchestration. Existing template/SHACL APIs do not require source files.

## Personal examples

`GET /api/projects` provisions missing bundled examples for the authenticated account, including existing accounts, before listing accessible projects. The write transaction rechecks the `(user_id, example_id)` receipt to prevent duplicates across tabs. Migration 2 records each receipt separately from its project; deleting a project sets the receipt's project ID to NULL so a later visit does not recreate it. Existing projects and edited example copies are never replaced. Provisioning skips examples that exceed configured graph/blueprint-size limits without recording a receipt.

Project summaries include nullable `example_id` for original example copies. A normal private copy is independent and has no provisioning receipt. CSV nodes may include the optional `example_file: "measurements.csv"` hint; other file references are rejected. The authenticated `GET /api/examples/files/measurements.csv` endpoint serves only this packaged, synthetic CSV asset. The frontend explicitly loads it into session memory through the standard CSV preview flow; it is never embedded in saved blueprints.
