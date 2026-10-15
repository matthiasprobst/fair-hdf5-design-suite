export type ResizablePanel = 'library' | 'inspector' | 'artifacts';
export type PanelSizes = Record<ResizablePanel, number>;
export type PanelPreferences = Partial<PanelSizes>;

export const PANEL_MIN = { library: 180, inspector: 260, artifacts: 120 };
export const PANEL_MAX = { library: 480, inspector: 560 };
export const CANVAS_MIN_WIDTH = 360;
export const STAGE_MIN_HEIGHT = 240;
export const PANEL_GAP = 6;

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

/** Fit preferred widths into the workspace without ever consuming the canvas minimum. */
export function resolvePanelSizes(
  preferred: PanelSizes,
  width: number,
  height: number,
  compact: boolean,
  libraryOpen: boolean,
  inspectorOpen: boolean,
): PanelSizes {
  let library = clamp(preferred.library, PANEL_MIN.library, PANEL_MAX.library);
  let inspector = clamp(preferred.inspector, PANEL_MIN.inspector, PANEL_MAX.inspector);
  if (compact) {
    library = clamp(library, PANEL_MIN.library, width * 0.8);
    inspector = clamp(inspector, PANEL_MIN.inspector, width * 0.8);
  } else {
    const available =
      width - CANVAS_MIN_WIDTH - PANEL_GAP * (Number(libraryOpen) + Number(inspectorOpen));
    const used = (libraryOpen ? library : 0) + (inspectorOpen ? inspector : 0);
    const spare =
      (libraryOpen ? library - PANEL_MIN.library : 0) +
      (inspectorOpen ? inspector - PANEL_MIN.inspector : 0);
    if (used > available && spare > 0) {
      const retained = Math.max(0, 1 - (used - available) / spare);
      if (libraryOpen) library = PANEL_MIN.library + (library - PANEL_MIN.library) * retained;
      if (inspectorOpen)
        inspector = PANEL_MIN.inspector + (inspector - PANEL_MIN.inspector) * retained;
    }
  }
  return {
    library,
    inspector,
    artifacts: clamp(
      preferred.artifacts,
      PANEL_MIN.artifacts,
      height - STAGE_MIN_HEIGHT - PANEL_GAP,
    ),
  };
}
