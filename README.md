# FAIR HDF5 Design Suite

A research prototype for visually designing experiment workflows and HDF5 target structures for fluid-mechanics data. The React and TypeScript interface is backed by a Python API using FastAPI, h5py, RDFLib, and SHACL.

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

### Start the development servers

From the repository root, create and activate a virtual environment, then install the Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

In the first terminal, start the API:

```bash
python app.py
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
python app.py
```

Open <http://127.0.0.1:8000>. FastAPI serves the built React app from `frontend/dist/`. If the build is missing, the API root returns a setup message; during development, use the Vite address above.

## Tests and checks

Install the additional test dependencies first:

```bash
python -m pip install -r requirements-dev.txt
```

Then run the checks from the repository root:

```bash
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
python -m unittest discover -s tests -v
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
