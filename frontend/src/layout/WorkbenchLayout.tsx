import type { ReactNode } from 'react';
import { ChevronUp, PanelBottom } from 'lucide-react';
import type { WorkbenchPanels } from './useWorkbenchPanels';
import { useWorkbenchSizing } from './useWorkbenchSizing';
import { ResizeHandle } from './ResizeHandle';
import { PANEL_MIN } from './panelSizes';
import type { ResizablePanel } from './panelSizes';
import '../styles/workbench.css';

type Props = {
  panels: WorkbenchPanels;
  library: ReactNode;
  canvas: ReactNode;
  inspector: ReactNode;
  artifacts: ReactNode;
};

/** Owns both split axes. Canvas identity and domain state are independent of panel sizes. */
export function WorkbenchLayout({ panels, library, canvas, inspector, artifacts }: Props) {
  const sizing = useWorkbenchSizing(panels);
  const { sizes } = sizing;
  const separator = (panel: ResizablePanel) => (
    <ResizeHandle
      label={`Resize ${panel === 'artifacts' ? 'generated artifacts' : panel === 'library' ? 'block library' : 'inspector'}`}
      controls={`workbench-${panel}`}
      orientation={panel === 'artifacts' ? 'horizontal' : 'vertical'}
      direction={panel === 'library' ? 1 : -1}
      value={sizes[panel]}
      min={PANEL_MIN[panel]}
      max={sizing.maxima[panel]}
      onResize={(size) => sizing.resize(panel, size)}
      onReset={() => sizing.reset(panel)}
    />
  );
  const columns = panels.compact
    ? 'minmax(0, 1fr)'
    : [
        panels.libraryOpen ? `${sizes.library}px` : '',
        'minmax(360px, 1fr)',
        panels.inspectorOpen ? `${sizes.inspector}px` : '',
      ]
        .filter(Boolean)
        .join(' ');

  return (
    <div
      className="workbench-layout"
      ref={sizing.ref}
      data-artifacts-open={panels.artifactsOpen}
      style={{
        gridTemplateRows: `minmax(240px, 1fr) ${panels.artifactsOpen ? sizes.artifacts : 30}px`,
      }}
    >
      <div
        className="main-stage"
        data-compact={panels.compact}
        data-inspector-open={panels.inspectorOpen}
        data-library-open={panels.libraryOpen}
        style={{ gridTemplateColumns: columns }}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && panels.compact) {
            panels.closeOverlay();
            event.stopPropagation();
          }
        }}
      >
        <div
          className="workbench-library"
          id="workbench-library"
          hidden={!panels.libraryOpen}
          style={panels.compact ? { width: sizes.library } : undefined}
        >
          {library}
          {panels.libraryOpen && separator('library')}
        </div>
        {canvas}
        <div
          className="workbench-inspector"
          id="workbench-inspector"
          hidden={!panels.inspectorOpen}
          style={panels.compact ? { width: sizes.inspector } : undefined}
        >
          {inspector}
          {panels.inspectorOpen && separator('inspector')}
        </div>
      </div>
      <div className="workbench-artifacts" id="workbench-artifacts" hidden={!panels.artifactsOpen}>
        {artifacts}
        {panels.artifactsOpen && separator('artifacts')}
      </div>
      <button
        className="artifacts-collapsed"
        hidden={panels.artifactsOpen}
        aria-label="Expand generated artifacts"
        aria-expanded={false}
        aria-controls="workbench-artifacts"
        onClick={panels.toggleArtifacts}
      >
        <PanelBottom size={15} /> Generated Artifacts <ChevronUp size={15} />
      </button>
    </div>
  );
}
