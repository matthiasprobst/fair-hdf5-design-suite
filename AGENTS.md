# Repository Guidelines

## Project Structure & Module Organization

- `backend/fair_hdf5/` contains the FastAPI API, domain models, HDF5 processing, and RDF/SHACL validation. Keep HTTP handling in `api.py` and orchestration in `services.py`.
- `frontend/src/` contains the React/TypeScript interface: components, editor state, layout, and styles. Keep panel sizing separate from persisted blueprint state.
- `backend/tests/` holds backend/API tests; `frontend/tests/` holds editor unit tests; root `tests/` contains browser checks.
- `backend/fair_hdf5/seeds/` supplies bundled templates; `examples/` contains blueprints, profiles, and synthetic data. Root `app.py` and requirements files provide compatibility entry points.

## Build, Test, and Development Commands

Use Python 3.10+ and Node.js 20+. Run commands from the repository root with `.venv` activated.

- `python -m pip install -e ./backend -r backend/requirements-dev.txt`: install backend and test dependencies.
- `npm ci --prefix frontend`: install locked frontend dependencies.
- `python -m fair_hdf5`: start the API on port 8000.
- `npm run dev --prefix frontend`: start Vite on port 5173 with API proxying.
- `./start.sh`: install dependencies, build, and serve the complete app.
- `docker compose up --build`: build and run the containerized app.
- `npm run build --prefix frontend`: compile TypeScript and build production assets.

## Coding Style & Naming Conventions

Follow surrounding formatting: Python uses four-space indentation and `snake_case`; React components use PascalCase and hooks use `useCamelCase`. Prefer two-space indentation in formatted TypeScript, single-quoted imports, and semicolons. TypeScript strict mode is enabled. No dedicated formatter or linter is configured; run `npm run typecheck --prefix frontend`.

## Testing Guidelines

Run `python -m unittest discover -s backend/tests -v` and `npm test --prefix frontend` (Node's test runner with esbuild). Name Python tests `test_*.py` with `test_*` methods. Frontend tests currently enter through `frontend/tests/editor.test.ts`; wire additional files into the runner.

For UI changes, run `FAIR_UI_URL=http://127.0.0.1:5173 python tests/ui_playwright_editor.py` with both servers running and Playwright Chromium installed. Add regression checks for changed behavior; no numerical coverage threshold is configured.

## Commit & Pull Request Guidelines

History uses short, informal summaries such as `resizable ui`; no enforced prefix convention is evident. Use concise, action-oriented subjects. PRs should explain behavior changes, link relevant issues, report verification, and include screenshots for UI changes.

## Configuration & Data

Preserve existing `.env` settings; consult `.env.example`. Never edit published catalog revisions in place under `FAIR_HDF5_DATA_DIR`; create new revisions instead.
