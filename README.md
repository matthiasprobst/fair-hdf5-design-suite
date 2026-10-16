# FAIR HDF5 Design Suite

A research prototype for visually designing experiment workflows and HDF5 target structures for fluid-mechanics data. The React and TypeScript interface is backed by a Python API using FastAPI, h5py, RDFLib, and SHACL.

**Version 0.1.0-beta.1 — Beta.** This version is intended for evaluation and feedback. Features and interfaces may change, and bugs are still expected.

## What it does

- Build experiment workflows from equipment, sensor, processing, metadata, HDF5 group, and dataset blocks.
- Configure metadata and HDF5 paths, datatypes, and shapes.
- Preview the target HDF5 structure and generate HDF5 templates and SHACL constraints.
- Validate generated templates or uploaded HDF5 files against the selected design.
- Import and export editable blueprint JSON; the current draft is saved in browser local storage.

Workflow connections describe experimental relationships. HDF5 paths describe the physical file hierarchy; the two are modeled separately.

## Project status and scope

This is a local research prototype, not a production or multi-user service. Its metadata profile catalog is illustrative and local; it does not connect to the NFDI4Ing Metadata Profile Service (MPS). Profile URIs are not resolved or verified against live profiles.

Validation checks the HDF5 structure, datatypes, shapes, and configured metadata, and checks an RDF representation against generated SHACL constraints. Passing validation does not establish that measurements are scientifically correct or that a dataset is fully FAIR.

The files in `examples/` are examples. In particular, `simulate_processing.py` and `synthetic_measured_data.h5` use synthetic data and are not experimental measurements.

## Run with Docker (recommended)

Install Docker with Docker Compose support (for example, Docker Desktop), then
clone or download this repository. From the repository root, run:

```bash
docker compose up --build
```

Open <http://localhost:8000>. Docker builds the React frontend and runs it with
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

Drafts are saved in your browser's local storage, associated with the address you
use to open the app. Restarting or rebuilding the container does not delete them.
Use blueprint JSON export to back up or transfer your work; clearing browser data
removes locally saved drafts. No Docker volumes are required.

## Local development without Docker

The following tools are needed only when running the application directly:

- Python 3.10 or newer
- Node.js 20 or newer and npm

### Start the complete app with one command

```bash
./start.sh
```

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

The optional Playwright browser checks are in `tests/ui_playwright_demo.py` and `tests/ui_playwright_editor.py`. They require the API and frontend servers to be running and a Playwright Chromium browser to be installed. For example:

```bash
python -m playwright install chromium
FAIR_UI_URL=http://127.0.0.1:5173 python tests/ui_playwright_editor.py
```

## Citation and license

If you use this software in research, cite it using the metadata in [`CITATION.cff`](CITATION.cff). A DOI can be added there when a release is archived and assigned one.

The project is released under the [Apache License 2.0](LICENSE). Third-party dependencies retain their own licenses and notices.

## Contributing

Bug reports and contributions are welcome through GitHub issues and pull requests.
