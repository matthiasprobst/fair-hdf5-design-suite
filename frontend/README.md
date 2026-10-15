# Frontend structure

`App` selects the current feature view. `EditorView` connects the editor lifecycle,
commands and generated artifacts to the UI. A future project view can use
`AppShell` and `GlobalHeader` without mounting React Flow or starting an editor.

## Layout ownership

- `AppShell` owns the viewport, global header and scrollable content slot.
- `EditorView` composes the project toolbar, error banner, workspace and status bar.
- `WorkbenchLayout` owns the workspace/artifacts split and the
  library/canvas/inspector split. Its named slots accept content, not dimensions.
- `styles/workbench.css` owns outer panel sizes. The CSS properties
  `--library-width`, `--inspector-width` and `--artifacts-height` are preferred
  sizes for the next resize-handle implementation. Keep resizing state local to
  this layout; do not put it in the blueprint store or its persistence format.
- `styles/editor.css` contains editor-scoped presentation and internal scrolling.
  Panels fill their allocated space. Keep `min-width: 0` and `min-height: 0`
  throughout the grid/flex chain, and keep scrolling in the panel content.
- `styles/shell.css` is independent of the editor. Global `styles.css` contains
  only base document styles.

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
cancellation and transient notifications. `editor/store`, `lifecycle`,
`persistence` and `artifacts` retain responsibility for domain state and data.

Run from the repository root:

```bash
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
FAIR_UI_URL=http://127.0.0.1:5173 .venv/bin/python tests/ui_playwright_editor.py
```

Browser tests need the API and Vite servers, plus Playwright Chromium. Set
`FAIR_BROWSER_EXECUTABLE` if using an existing browser binary. Screenshots go to
`/tmp/fair-editor-qa` by default. Tests cover desktop/compact transitions, stable
canvas identity and transform, panel keyboard controls, drag/drop, long content,
error banners and internal scrolling, as well as existing editor operations.

The existing `hideAttribution` React Flow setting produces a development-only
library notice with current installed versions. Browser tests exclude that
specific known notice, also reproduced on the original frontend; other console
warnings/errors still fail. The setting itself is unchanged by this refactor.
