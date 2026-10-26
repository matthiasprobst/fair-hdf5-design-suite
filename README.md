# FAIR HDF5 Design Suite

A research prototype for visually designing experiment workflows and HDF5 target structures for fluid-mechanics data. The React and TypeScript interface is backed by a Python API using FastAPI, h5py, RDFLib, and SHACL.

**Version 0.1.0-beta.1 — Beta.** This version is intended for evaluation and feedback. Features and interfaces may change, and bugs are still expected.

## What it does

- Build experiment workflows from equipment, sensor, processing, metadata, HDF5 group, and dataset blocks.
- Configure metadata and HDF5 paths, datatypes, and shapes.
- Preview the target HDF5 structure and generate HDF5 templates and SHACL constraints.
- Import CSV columns through data-source nodes and build populated HDF5 files with numeric and UTF-8 text datasets.
- Validate generated templates or uploaded HDF5 files against the selected design.
- Manage private projects and share them with selected viewers or editors.
- Import and export portable blueprint JSON; projects are saved on the server with browser recovery for unsaved edits.

Workflow connections describe experimental relationships. HDF5 paths describe the physical file hierarchy; the two are modeled separately.

## Build HDF5 with CSV data

Your dashboard includes two personal example projects: **Example: Radial fan experiment** and **Example: CSV to HDF5**. Use the **Examples** filter to find them. Every account, including existing accounts, receives its own private, editable copies on its first dashboard visit. Subsequent visits preserve edits and do not recreate deleted examples. Copies are never synchronized with another user's projects or overwritten by updated examples. Examples that exceed the installation's configured graph or blueprint-size limits are skipped until those limits permit them.

To try the CSV example, open **Example: CSV to HDF5**, select **Example CSV measurements**, and choose **Load example CSV**. Its three column mappings, dataset types, paths, metadata, and units are already configured. Then choose **Build HDF5 with data**. The bundled data is synthetic; loading it keeps it only in the current project session, just like a locally selected file.

1. Open an unlocked project and add **CSV Source** from **Data inputs**. Editing starts automatically when you have edit permission.
2. Set the delimiter, decimal separator, and header option, then select a UTF-8 CSV file. The inspector shows column types and previews the first 50 rows.
3. Select columns and choose **Create datasets from selected columns**. Alternatively, connect the source's square output to an existing Dataset node's square input, then select its column in the inspector. Round ports continue to describe experimental relationships.
4. Configure each dataset's path, datatype, metadata, and unit. Each column becomes a one-dimensional dataset. Shape `0` uses the CSV row count; a fixed shape must match exactly. `string` creates variable-length UTF-8 text datasets. Suggested datatypes are editable; use `string` for identifiers whose leading zeros must be preserved.
5. In **Generated Artifacts**, choose **Build HDF5 with data**. Every Dataset node must be connected to a CSV column, and all connected sources must have files loaded. **Download template .h5** remains available independently and generates the designed datasets without importing CSV values.

Try [the example CSV](examples/csv/measurements.csv) with **Semicolon**, decimal **Comma**, and headers enabled. It produces `/data/time`, `/data/pressure`, and `/data/sample`. Configure suitable units (for example `s`, `Pa`, and `1`) before validating its metadata.

Files and preview rows are kept only in memory for the open project. Selecting a file sends it to the server for request-only parsing; the server does not retain it. Project saves, recovery drafts, copies, and blueprint exports contain source settings, filenames, expected headers, and mappings, **not CSV contents**. Reselect files after reopening or importing a blueprint. Viewers can load their own files for existing mappings and export without editing the project. Changed headers require an editor's explicit acceptance; bindings retain their column positions.

CSV import supports UTF-8 (including BOM), comma/semicolon/tab delimiters, an optional header row, quoted fields, and dot/comma decimal separators. The delimiter and decimal separator must differ. Duplicate headers are distinguished by column position. Empty text cells are preserved; empty or invalid numeric cells, fractional integers, overflow, and nonfinite values stop the build with a source/row/column/target error. Rows are never silently dropped.

The default limits are 30 MB of combined CSV input, 50,000 rows per source, two million parsed cells (including headers), two million total populated values, and 30 MB of generated value payload. Existing `FAIR_HDF5_MAX_UPLOAD_BYTES`, `FAIR_HDF5_MAX_DIMENSION_SIZE`, and `FAIR_HDF5_MAX_DATASET_ELEMENTS` settings control these limits; the HDF5 container and embedded blueprint add file overhead. Populated files can be checked with the existing uploaded-HDF5 validation action. Validation checks structure and metadata, not equality with the CSV values. Transformations, matrix/compound datasets, and persistent uploads are not included.

## Project status and scope

This is a research prototype with project access controls for a single team installation. Local accounts, private projects and selected-member sharing are supported. Its library includes illustrative templates and supports importing MPS Turtle profiles with pinned dependencies. It has no live MPS catalog discovery or automatic synchronization.

Validation checks the HDF5 structure, datatypes, shapes, and configured metadata, and checks an RDF representation against generated SHACL constraints. Passing validation does not establish that measurements are scientifically correct or that a dataset is fully FAIR.

The files in `examples/` are examples. In particular, `simulate_processing.py` and `synthetic_measured_data.h5` use synthetic data and are not experimental measurements.

## Run with Docker (recommended)

Install Docker with Docker Compose support (for example, Docker Desktop), then
clone or download this repository. From the repository root, run:

```bash
docker compose up --build
```

Create the first administrator in a second terminal:

```bash
docker compose exec app python -m fair_hdf5 --create-admin admin
```

The command prompts for a password of at least 15 characters by default. For local
testing, set `FAIR_HDF5_PASSWORD_MIN_LENGTH=3` in `.env` before starting the app.
The setting accepts 3–128 and applies to all newly set local passwords, including
the first administrator and password changes. Existing passwords remain valid.
After changing the setting, recreate the container with `docker compose up -d --build`;
for a local Python installation, restart the API. There are no default accounts.
Sign in at <http://localhost:8000>. Docker builds the React frontend and runs it with
the Python API in one container. You do not need Python, Node.js, or npm on your
computer. The first build needs internet access to download the base images and
dependencies and may take a few minutes. The app is exposed only on your local
computer.

After downloading project updates, run `docker compose up --build` again to
rebuild and start the updated application. To run in the background, use
`docker compose up --build -d`.

View service status and logs:

```bash
docker compose ps
docker compose logs -f app
```

To stop the foreground process, press Ctrl+C. To stop and remove the container:

```bash
docker compose down
```

Projects, accounts, sessions and project templates are stored in
`data/projects.sqlite3` inside the persistent `catalog-data` volume. The existing
installation catalog remains under `data/catalog`. Restarting or rebuilding does
not remove them. Removing the volume removes both projects and the catalog.
Browser storage holds recovery drafts, separated by account and project; the
server remains the authoritative saved copy. Existing browser-only drafts can be
explicitly imported as a private project after signing in.

Database migration 2 adds per-user example provisioning records without modifying existing projects. These records also remember intentionally deleted examples. Back up the database with the rest of the data directory as described below.

## Accounts, projects and collaboration

For a direct Python installation, create the first administrator once:

```bash
python -m fair_hdf5 --create-admin admin
```

Administrators use **Administration** to create accounts, deactivate users and
reset passwords. Temporary passwords are displayed once and must be changed at
first login. Password resets and deactivation end that user's sessions and edit
reservations. Administrators do not automatically gain access to private projects.
There is no public registration or email-based password reset.

Each project contains one blueprint and optional description. **New project**
offers an empty design, the example experiment or JSON import. All projects start
private. Owners share with existing usernames as **Can view** or **Can edit**.
Viewers can inspect, validate, export and make a private copy. Only owners manage
members or delete projects. Copies do not inherit members or reservations.

Opening an unlocked project automatically reserves it for the current browser tab
and starts editing when you have edit permission. Viewers and tabs opening an
already reserved project remain in view mode. **Finish editing** saves and releases
the reservation, leaving the current page in view mode; **Edit project** can request
it again. Another tab, even under the
same account, stays read-only. Reservations last 120 seconds and renew every 30
seconds while editing. There is no forced takeover. After a crash or lost
connection, a reservation expires automatically. Reloads normally release it; if
that request fails, wait up to two minutes before editing again.

Changes autosave to the server. Incomplete HDF5 paths and metadata can be saved;
scientific validity is checked separately. Connection or reservation failures
pause editing and retain a recovery draft. Resume only after reacquiring the
reservation. If the server changed, export or save a private copy before loading
the server version. Navigation saves before releasing the reservation; failed
saves offer retry, export or explicit discard. Browser-local recovery is a
convenience, so JSON export remains available when browser storage is unavailable.

New/imported library templates are scoped to the current project. Existing
installation templates are read-only starting points; their pencil action creates
a project copy. Existing nodes keep pinned snapshots until explicitly upgraded.
Importing blueprint JSON does not publish templates into a library.

For a team server, place the app behind an HTTPS reverse proxy and configure the
exact browser origin, for example `FAIR_HDF5_PUBLIC_URL=https://design.example.org`
and `FAIR_HDF5_COOKIE_SECURE=true`. Keep the SQLite file on a local filesystem and
run one application instance. No SSO provider is required. Authentication exposes
stable internal user IDs so a later SSO integration can preserve ownership and
memberships.

Back up the entire data directory with the app stopped, or use Python's SQLite
backup API for the database plus a copy of the immutable catalog. Restore into an
empty data directory with the app stopped. Keep database files and backups private:
they contain project content, password hashes and sessions. Existing catalog files
are never rewritten during the upgrade; database migrations run at startup.

## Local development without Docker

The following tools are needed only when running the application directly:

- Python 3.10 or newer
- Node.js 20 or newer and npm

### Start the complete app with one command

```bash
./start.sh
```

Run `python -m fair_hdf5 --create-admin admin` once after installing the backend.
The script creates `.venv` if needed, installs Python dependencies, installs
frontend dependencies when needed, builds the React UI, and starts the Python
server. Open <http://127.0.0.1:8000>. Press Ctrl+C to stop. The first start needs
internet access; use `./start.sh --help` for prerequisites. If a server already
uses the configured port, stop it or choose another `FAIR_HDF5_PORT`.

For frontend development with live reloading, use the two-server setup below.

### Start the development servers

From the repository root, create and activate a virtual environment, then install the Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ./backend
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

In the first terminal, start the API:

```bash
python -m fair_hdf5
```

In a second terminal, install the frontend dependencies and start Vite:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite forwards API requests to the Python server at <http://127.0.0.1:8000>.

### Build and serve locally

Build the React application, then start the Python server from the repository root:

```bash
cd frontend
npm ci
npm run build
cd ..
python -m fair_hdf5
```

Open <http://127.0.0.1:8000>. FastAPI serves the built React app from `frontend/dist/`. If the build is missing, the API root returns a setup message; during development, use the Vite address above.

## Development quality checks

Use Python 3.10+ and Node.js 20.19+ (Node 22 is used in the container). Install
backend development dependencies and the locked frontend packages, then run:

```bash
python -m pip install -e ./backend -r backend/requirements-dev.txt
npm ci --prefix frontend
ruff check .
ruff format --check .
python -m unittest discover -s backend/tests -v
npm run check --prefix frontend
```

`npm run check` runs ESLint, Prettier, TypeScript (including test files), frontend
unit tests, and the production build. Apply formatting with `ruff format .` and
`npm run format --prefix frontend`. Ruff covers the backend, compatibility entry
point, and browser tests; frontend formatting covers source, tests, and tool
configuration. Generated assets and example datasets are excluded.

GitHub Actions runs these checks on pushes and pull requests, with Python
3.10/3.12 and Node 20/22. A separate Chromium job tests the built application,
including library publication, template upgrades, linked profiles, editing,
persistence, and panel layout. It uploads screenshots and the test-server log.
Backend tests create temporary catalogs and never modify the local library.

See [backend responsibilities](backend/README.md#responsibilities) and
[frontend structure](frontend/README.md) before adding new behavior.

## Repository layout

```text
backend/
  fair_hdf5/          Python API and scientific processing
  tests/             Backend and HTTP API tests
  pyproject.toml     Installable Python package
  requirements*.txt  Python dependency declarations
frontend/
  src/               React application
  tests/             Frontend unit tests
  package.json       Frontend dependencies and scripts
tests/               Full-app browser checks
examples/            Example workflows and synthetic data
start.sh             Build and run the full app
Dockerfile           Full-app container build
compose.yaml         Local container configuration
```

Shared `.env` configuration and `.venv` stay at the repository root. The root
`app.py` and requirements files are small compatibility entry
points. Backend structure and development commands are described in
[`backend/README.md`](backend/README.md).

## Backend configuration

The API and scientific processing live in `backend/fair_hdf5/`. HTTP routes delegate to
`DesignService`; domain parsing, HDF5 handling, RDF/SHACL conversion, and validation
engines are separate modules. The root `app.py` preserves `python app.py` and
`uvicorn app:app`. Python integrations import the installed `fair_hdf5` package;
use `fair_hdf5.catalog` for catalog/demo data and
`fair_hdf5.services.DesignService` for preview, export, and validation.

Copy the settings you want from `.env.example` into the project-root `.env`.
Preserve any existing settings in that file. Configuration precedence is explicit
`Settings(...)` arguments, environment variables, `.env`, then defaults. Unrelated
variables are ignored. Settings are validated at startup and require a restart to
change. Relative paths resolve from the project root, regardless of the launch
working directory.

| Variable prefix: `FAIR_HDF5_` | Default | Purpose |
| --- | --- | --- |
| `HOST`, `PORT` | `127.0.0.1`, `8000` | Python launcher bind address |
| `LOG_LEVEL` | `info` | Logging verbosity |
| `SERVE_FRONTEND`, `FRONTEND_DIST` | `true`, `frontend/dist` | Built frontend hosting |
| `TEMP_DIR` | OS temporary directory | Existing writable directory for validation files |
| `SHACL_ENGINE` | `pyshacl` | Full validator; `subset` explicitly selects only generated minCount/hasValue checks |
| `MAX_UPLOAD_BYTES` | `30000000` | Uploaded HDF5 file limit |
| `MAX_NODES`, `MAX_EDGES` | `250`, `1000` | Blueprint graph limits |
| `MAX_METADATA_LENGTH` | `3000` | Characters per metadata string |
| `MAX_DATASET_DIMENSIONS` | `5` | Dataset rank limit (maximum 32) |
| `MAX_DIMENSION_SIZE` | `50000` | Maximum size per dimension |
| `MAX_DATASET_ELEMENTS` | `2000000` | Maximum initial dataset element count |
| `MAX_REPORT_ISSUES` | `250` | Returned issues; total issue count remains complete |

Full pySHACL is installed with the backend package for both local and container
startup. Runtime dependencies are declared once in `backend/requirements.txt`
and read by `backend/pyproject.toml`. A missing selected engine fails startup
instead of changing validation behavior. Root requirements files remain
compatibility includes; run their pip commands from the repository root.

For example, run `FAIR_HDF5_PORT=8010 ./start.sh`. The script uses Python's settings
loader for its preflight checks and launch. `python -m fair_hdf5 --check` validates
settings, storage, dependencies, and port availability without starting a server.
For external ASGI hosting, `uvicorn app:app` still works; Uvicorn's own CLI options
control its bind address and server logging.

Vite reads the project-root configuration and uses the configured backend port.
Set `FAIR_HDF5_API_TARGET=http://127.0.0.1:8010` to override its proxy target. This
value is used by the development server and is not exposed in the browser bundle.

Docker Compose forwards the documented settings, binds the container to
`0.0.0.0`, and publishes the configured port only on the host's loopback interface.
Paths configured for Docker must exist **inside the container**. Local `.env`
files are excluded from the image. For example:

```bash
FAIR_HDF5_PORT=8010 docker compose up --build
```

`GET /api/capabilities` exposes only graph/upload limits and the engine identifier.
The editor loads these before enabling operations. Lowering limits preserves
existing drafts and JSON export; users can remove nodes or connections to bring a
draft within the new limits. Oversized imports leave the current graph unchanged.
If the demonstration graph exceeds the limits, a new workspace starts empty.

The upload limit bounds the file read by the validation service; it is not a
whole-request HTTP body limit. Multipart parsing may spool the incoming body
before the handler runs. An externally deployed service can enforce a request
body limit at its reverse proxy.

For embedding or isolated tests, construct `Settings(_env_file=None, ...)` and
pass it to `create_app(settings)` or `DesignService(settings)`. Each application
owns its settings and service. Legacy Python wrappers load and cache their default
service on first use; restart the process to apply settings changes.

## Tests and checks

Install the additional test dependencies first:

```bash
python -m pip install -e ./backend -r backend/requirements-dev.txt
```

Then run the checks from the repository root:

```bash
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
python -m unittest discover -s backend/tests -v
```

Browser checks cover both the editor and multi-user projects. Use an isolated
test data directory and provision the test accounts before starting the server.
Against the built frontend, run in the first terminal:

```bash
python -m playwright install chromium
npm run build --prefix frontend
export FAIR_HDF5_DATA_DIR=/tmp/fair-browser-local
export FAIR_TEST_PASSWORD='browser test passphrase only'
python tests/prepare_browser.py
python -m fair_hdf5
```

In another terminal, run both suites against that server:

```bash
FAIR_UI_URL=http://127.0.0.1:8000 FAIR_TEST_PASSWORD='browser test passphrase only' python tests/ui_playwright_editor.py
FAIR_UI_URL=http://127.0.0.1:8000 FAIR_TEST_PASSWORD='browser test passphrase only' python tests/ui_playwright_projects.py
```

`FAIR_TEST_ADMIN` optionally overrides the fixture administrator name (`qaadmin`).
These fixture accounts are for the isolated test directory only. For Vite,
use the same API data directory and set `FAIR_UI_URL` to its development address.

## Citation and license

If you use this software in research, cite it using the metadata in [`CITATION.cff`](CITATION.cff). A DOI can be added there when a release is archived and assigned one.

The project is released under the [Apache License 2.0](LICENSE). Third-party dependencies retain their own licenses and notices.

## Contributing

Bug reports and contributions are welcome through GitHub issues and pull requests.

## Persistent SHACL library

Use **Create / import template** in the building-block library to create a
component with the form editor or import a Turtle (`.ttl`) SHACL file. Analyze
an imported file, select a supported named NodeShape, review the fields and
choose their HDF5 attribute names. Set a category, icon, color, object kind and
default HDF5 path, then save. Use the pencil next to an entry to publish a new
revision; its original Turtle remains editable without discarding annotations.

The installation-wide library lives under `FAIR_HDF5_DATA_DIR` (default:
`data/`, relative to the repository root):

```text
data/catalog/
  profiles/<sha256>.ttl
  templates/<stable-template-id>/<revision>.json
```

SHACL is the source of field rules. JSON stores the profile hash, selected
shape, property-IRI-to-HDF5-attribute mapping, presentation and defaults. Profile
files and revisions are immutable. The file repository uses POSIX file locks,
atomic replacement and fsync; use a local filesystem supporting these semantics.
Temporary `.pending-*` files and unreferenced profiles left after interrupted
writes do not become catalog entries. Back up the entire directory; do not edit
published files in place. Unreadable published files produce an error rather
than silently resetting user data.

The initial templates are packaged in `backend/fair_hdf5/seeds/` and copied only
when their first revision does not exist. Docker Compose mounts the persistent
`catalog-data` volume. Removing that volume removes the library. Existing global entries are readable by authenticated users and remain unchanged.
New templates are stored in the project database with the project access rules.

A local example for file import is `examples/profiles/pressure-profile.ttl`.
It exercises required text, decimal bounds, a date, an enum and a boolean; it is
not an exported MPS profile.

### Profiles and portable designs

Every new node pins a complete template snapshot, including Turtle and its hash.
Blueprint JSON and the blueprint embedded in HDF5 therefore remain portable
without the originating library. Existing legacy nodes resolve to the bundled
first revision, even after their template is updated. The inspector offers an
explicit revision update with rule review and validation. Updating retains
existing values and adds new defaults; validation may report fields requiring
attention. Importing a design does not publish its snapshots into the library.

Supported SHACL includes named NodeShapes with direct property IRIs, scalar and
repeated literal fields, explicit cardinalities, linked named shapes through
`sh:node` or qualified shape declarations, `sh:class` IRI fields, and `sh:xone`
alternatives of `xsd:integer` and `xsd:double`. Literal types include string,
boolean, integer, decimal, double, date, dateTime and IRI. Selection lists, fixed
values, numeric bounds, string lengths, regex patterns, labels, descriptions and
defaults are supported. See the MPS section below for dependency behavior.
Complex paths, closed shapes, logical composition and SPARQL are rejected.
Turtle imports resolve dependencies explicitly during analysis; reopening or
validating a saved template uses only its pinned local bundle.
A file may contain multiple named shapes; select one for the template.

Source targeting is replaced by explicit targeting of each corresponding
canvas node during validation. Original Turtle remains intact in the snapshot.
HDF5 attributes are projected using the selected property IRIs and declared RDF
datatypes. Decimal and date lexical values can remain strings in HDF5 to avoid
precision loss. Blank inputs represent absent attributes. The existing HDF5
structure checks still run. Custom profiles require the pySHACL engine; the
explicit legacy subset mode cannot validate custom profiles.

### Catalog API

- `GET /api/catalog`: current revisions and the original built-in revisions.
- `POST /api/catalog/analyze`: `{ "ttl": "..." }`, returning named shapes,
  supported fields, and explanations for unsupported shapes.
- Global catalog publication routes now return HTTP 403. Use project-scoped
  `/api/projects/{project_id}/catalog` and `/{template_id}/revisions` instead.
  Supply `template`, expected project revision, and expected template revision
  for updates, together with the current edit lease.
- `GET /api/catalog/{id}/revisions/{revision}`: retrieve an immutable snapshot.

MPS catalog discovery, automatic synchronization and JSON-LD are not included.
Compatibility with a specific MPS export must be checked against that file;
no complete MPS compatibility is claimed.

### MPS research projects, people and organizations

`examples/profiles/research_project.ttl` is a self-contained Turtle bundle based
on the MPS Research Project, Person and Organization profiles. It is also
packaged as the built-in **m4i Research Project** template in the **Metadata**
palette category, so it is available in existing installations without a live
MPS request. The importer can also analyze the example directly. The inspector
offers **Create linked node** and existing-node selectors for participating
people and organizations. A Person node similarly offers organization
affiliations. Selecting a linked node opens its own metadata.

The importer preserves multiple language labels (English preferred), multiline
text hints, literal lists, `sh:node` and qualified-shape references. Missing
`sh:maxCount` means repeatable values, including first and last names in the MPS
Person profile. Both project participant selectors share `m4i:projectParticipant`
in RDF and one HDF5 object-reference attribute. Semantic edges carry a field ID
and predicate; ordinary workflow connections remain independent.

Repeated literals use one-dimensional HDF5 attributes. Linked nodes use HDF5
object references, created after all objects exist. Validation reads these
references from the uploaded HDF5 file and reports missing/dangling targets,
wrong attribute representations and relationships that differ from the design.
Every node is also independently validated against its own pinned profile.

The project contains qualified-shape declarations without qualified counts.
These describe reference choices but add no SHACL count constraint. Original
Turtle is preserved; the executable SHACL projection omits these inert
qualified-shape annotations because pySHACL rejects them without counts. It does
not add `sh:node` or mandatory participant counts. Explicit qualified counts and
`sh:node` constraints are retained and executed. `sh:closed false` is supported;
closed shapes, complex property paths, logical composition and SPARQL remain
unsupported.

Snapshot schema 2 adds pinned dependency documents, referenced templates, field
IDs, cardinalities and target classes; schema 1 snapshots are read and upgraded
in memory. Snapshots carry the referenced shape documents needed to reopen and
validate offline.
Dependency templates are included in the saved root template and can be
instantiated from its inspector without separately publishing mutable copies.

For offline import, use **Supply a dependency file** with the exact import URI.
Unchanged reference downloads and a complete `/api/catalog/analyze` JSON request
are included in `examples/profiles/mps-dependencies/`. The `offline-import.json`
request contains both dependency documents and hashes, so it requires no network
access. The original files declare CC0-1.0 licensing.

Network retrieval fetches only imported documents referenced by `sh:node` or
`sh:qualifiedValueShape`. Other ontology imports, such as large QUDT vocabulary
graphs, are left out unless the user supplies them as dependency files. This
keeps profile analysis bounded; if an omitted vocabulary supplies RDF type facts
needed by `sh:class`, provide a smaller Turtle subset containing those facts.
The analyzer reports imports it did not bundle. Fetches use public HTTPS
endpoints, validate redirects and TLS certificates, and pin the resolved IP for
each connection. HTTP import IRIs are upgraded to HTTPS for the initial fetch
while their original IRIs remain the bundle keys; HTTPS redirects are required.
Downloads happen only during explicit import analysis. Missing referenced shape
documents or cycles block saving; no automatic dependency refresh occurs when
loading or validating a design.
The following settings control retrieval:

| Environment variable | Default |
| --- | --- |
| `FAIR_HDF5_PROFILE_FETCH_TIMEOUT` | 10 seconds |
| `FAIR_HDF5_PROFILE_MAX_REDIRECTS` | 5 |
| `FAIR_HDF5_PROFILE_MAX_DEPTH` | 8 |
| `FAIR_HDF5_PROFILE_MAX_DOCUMENTS` | 16 |
| `FAIR_HDF5_PROFILE_MAX_DOCUMENT_BYTES` | 1000000 |
| `FAIR_HDF5_PROFILE_MAX_TOTAL_BYTES` | 8000000 |

`POST /api/catalog/analyze` now accepts optional `source_uri` and `documents`
(a map of requested URI to `{ttl, hash?, resolved_url?}`). Its response includes
resolved documents and per-shape field models. Publishing a template accepts the
same pinned documents. A missing pinned dependency is an error at publication;
publication never downloads a newer version in place of the reviewed content.

### Project API

Start with `GET /api/auth/session`, retain its cookie and send the returned
`csrf_token` as `X-CSRF-Token` on login and subsequent writes. Login/password
changes rotate the session and CSRF token. All `/api` scientific and catalog
operations now require authentication; `/health` remains public.
Session, login and password-change responses include
`password_policy: { min_length, max_length }`, reflecting the installation setting.

- `/api/projects`: list only accessible summaries or create a private project.
- `/api/projects/{id}`: read, save with `expected_revision`, or delete as owner.
- `/api/projects/{id}/members`: list or update an exact username with role
  `viewer`, `editor`, or `null` to remove.
- `/api/projects/{id}/edit-lock`: GET status, POST with `editor_id` to acquire,
  DELETE to release; POST `/renew` extends the lease.
- Blueprint and template writes require `X-Edit-Lease`. Template writes also
  compare the project revision and increment it atomically.

Unknown/inaccessible projects return 404, missing authentication 401, forbidden
roles 403, held/lost leases 423 and stale revisions 409. Project/auth errors include
a stable `code` and readable `detail`. Project saves check the storage envelope;
preview/export/validation retain the scientific checks.
