# Frontend structure

`App` owns routes, the shared shell and authenticated navigation. `/projects`
lists accessible projects; `/projects/:id` opens one editor; `/account` and
`/admin/users` manage the account and installation users. The editor route loads
lazily so project/account views do not mount React Flow or request previews.

`auth/AuthProvider` owns the cookie/CSRF session. `projects/api` checks API JSON;
`projects/editorSession` coordinates the project revision, serial save queue,
local recovery and tab-bound edit lease. Each route has its own graph and artifact
stores through `EditorStoreContext` and `EditorSessionContext`. Do not introduce
global editor stores or shared mutable project state.

Projects open read-only. Mutation capability requires both a writing role and a
confirmed unexpired lease; all graph mutation actions enforce it in addition to
UI controls. Selection and measurement changes remain available. Navigation uses
the router blocker to save, release and then leave. Late replies must never
publish into a different route's session.

## Layout ownership

- `AppShell` owns the viewport, global header and scrollable content slot.
- `EditorView` composes the project toolbar, error banner, workspace and status bar.
- `WorkbenchLayout` owns the workspace/artifacts split and the
  library/canvas/inspector split. Its named slots accept content, not dimensions.
- `styles/workbench.css` owns outer panel sizes. The CSS properties
  `--library-width`, `--inspector-width` and `--artifacts-height` are initial
  sizes. `useWorkbenchSizing` keeps user sizes local to this layout; do not put them in the blueprint store or its persistence format.
- `styles/editor.css` contains editor-scoped presentation and internal scrolling.
  Panels fill their allocated space. Keep `min-width: 0` and `min-height: 0`
  throughout the grid/flex chain, and keep scrolling in the panel content.
- `styles/shell.css` is independent of the editor. Global `styles.css` contains
  only base document styles.

Library, inspector and artifacts can be collapsed independently using their
header controls or the canvas toolbar. Closing a panel preserves its size for
reopening during the current session. Sizes are intentionally not persisted.
`panelSizes.ts` reserves at least 360px for the desktop canvas and 240px for the
workspace height. Sidebar widths are clamped to the available space on browser
resize, while retaining the user's preferred sizes for a larger window.

`ResizeHandle` uses pointer capture and supports mouse, touch and keyboard:
arrow keys move the divider by 10px (Shift: 50px), Home/End reach the limits,
Escape cancels an active drag, and double-click restores the responsive default.
Compact overlays can also be resized. React Flow is never remounted by resizing.

The supported viewport starts at 768 × 600. Below 1150px, side panels become
nonmodal overlays above the canvas. Only one overlay is open at a time; entering
compact mode closes overlays and retains the desktop inspector preference.
The media query in `useWorkbenchPanels` must match the CSS breakpoint. Smaller
heights use the shell content scroll; smartphone layouts are outside this step.

Keep the canvas in the same React tree position when panels open or close.
Changing panel sizes must neither remount React Flow nor trigger `fitView`,
blueprint saves or artifact requests. Automatic fitting remains tied to graph
replacement/loading; the existing fit button is the explicit user action.

## Commands and verification

`useEditorCommands` owns import/export/validation commands, pending-operation
cancellation and transient notifications. `editor/store` and `artifacts` own graph state and derived results;
`projects/editorSession` owns server persistence and lease lifetime. The old
`editor/persistence` storage key remains available for explicit legacy import.

Run from the repository root:

```bash
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
FAIR_UI_URL=http://127.0.0.1:5173 FAIR_TEST_PASSWORD='browser test passphrase only' .venv/bin/python tests/ui_playwright_editor.py
FAIR_UI_URL=http://127.0.0.1:5173 FAIR_TEST_PASSWORD='browser test passphrase only' .venv/bin/python tests/ui_playwright_projects.py
```

Provision an isolated catalog and browser accounts using `tests/prepare_browser.py`
as documented in the root README. Browser tests need the API and Vite servers, plus Playwright Chromium. Set
`FAIR_BROWSER_EXECUTABLE` if using an existing browser binary. Screenshots go to
`/tmp/fair-editor-qa` by default. Tests cover desktop/compact transitions, stable
canvas identity and transform, panel keyboard controls, drag/drop, long content,
error banners and internal scrolling, as well as existing editor operations.

The existing `hideAttribution` React Flow setting produces a development-only
library notice with current installed versions. Browser tests exclude that
specific known notice, also reproduced on the original frontend; other console
warnings/errors still fail. The setting itself is unchanged by this refactor.

## Feature and data boundaries

- `lib/api` owns HTTP transport and error messages. `lib/contracts` checks backend
  JSON before it enters application state; `lib/validation` supplies shared type
  guards. API JSON starts as `unknown`.
- `editor/blueprint` validates editable import/storage envelopes; scientific errors
  remain editable and are reported by the backend. `editor/adapters` converts
  between blueprints and React Flow, copying mutable values at the boundary.
- `editor/rules` owns IDs, paths, required fields, and relationship suggestions.
  Browser downloads live in `lib/downloads`.
- `library/useLibraryEditor` owns library form state and cancellable network
  operations. `library/draft` prepares publication payloads without mutating old
  revisions. `TurtleImport` and `TemplateFields` render the two cohesive form sections.
- `EditorInspector` connects selected state and upgrade commands to `Inspector`.
  `EditorReferenceFields` connects reference actions to `ReferenceFields`.
  Presentational components receive data and callbacks instead of calling the API.
- `editor/store` applies synchronous graph operations. Creating a linked node and
  its edge is one state transition. Publishing a catalog revision does not upgrade
  existing nodes; the explicit upgrade command uses normal artifact invalidation
  and stale-response handling.

Distinguish `TemplateDraft`, `TemplateSnapshot`, and legacy `CatalogItem` data.
Persist only published snapshots. Keep view state out of the blueprint. Add new
TypeScript tests anywhere under `tests/` using `*.test.ts`; the runner discovers
all files, and TypeScript checks both application and test code.

Run `npm run check --prefix frontend` for lint, formatting, type checking, tests,
and the build. `npm run format --prefix frontend` applies formatting. ESLint
checks hook usage and dependencies; Prettier owns layout and quote style.
Development tooling requires Node.js 20.19+.
