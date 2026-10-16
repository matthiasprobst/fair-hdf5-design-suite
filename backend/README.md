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

- `application` creates the FastAPI app; `api` owns HTTP transport.
- `services` coordinates preview, export, and validation.
- `domain`, `catalog`, `profiles`, and `vocabulary` own blueprint rules and definitions.
- `hdf5` handles HDF5 generation, files, and structural checks.
- `semantic` builds RDF/SHACL graphs; `engines` executes semantic validation.
- `settings` validates configuration; `compat` maintains the legacy function API.

`pyproject.toml` reads runtime dependencies from `requirements.txt`, keeping
version constraints in one place. `requirements-shacl.txt` remains a compatibility
include because full pySHACL is now a standard dependency.

## Tests

From the repository root:

```bash
python -m pip install -e ./backend -r backend/requirements-dev.txt
python -m unittest discover -s backend/tests -v
```

From this directory, use `python -m unittest discover -s tests -v` instead.
Full-app Playwright checks remain in the root `tests/` directory.
