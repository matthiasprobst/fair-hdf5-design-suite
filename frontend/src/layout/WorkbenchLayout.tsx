import type { ReactNode } from 'react';
import type { WorkbenchPanels } from './useWorkbenchPanels';
import '../styles/workbench.css';

type Props = {
  panels: WorkbenchPanels;
  library: ReactNode;
  canvas: ReactNode;
  inspector: ReactNode;
  artifacts: ReactNode;
};

/**
 * Owns both split axes: workspace/artifacts, then library/canvas/inspector.
 * Future resize handles belong here; children only fill their assigned area.
 * Keep the canvas in the same tree position across panel and viewport changes.
 */
export function WorkbenchLayout({ panels, library, canvas, inspector, artifacts }: Props) {
  return (
    <div className="workbench-layout">
      <div
        className="main-stage"
        data-compact={panels.compact}
        data-inspector-open={panels.inspectorOpen}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && panels.compact) {
            panels.closeOverlay();
            event.stopPropagation();
          }
        }}
      >
        <div className="workbench-library" id="workbench-library" hidden={!panels.libraryOpen}>
          {library}
        </div>
        {canvas}
        <div
          className="workbench-inspector"
          id="workbench-inspector"
          hidden={!panels.inspectorOpen}
        >
          {inspector}
        </div>
      </div>
      <div className="workbench-artifacts">{artifacts}</div>
    </div>
  );
}
