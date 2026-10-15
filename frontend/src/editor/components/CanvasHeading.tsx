import {
  BookOpen,
  GitBranch,
  LayoutGrid,
  Maximize2,
  SlidersHorizontal,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { useReactFlow } from '@xyflow/react';
import { useEditor } from '../store';
import type { WorkbenchPanels } from '../../layout/useWorkbenchPanels';

type Props = {
  panels: WorkbenchPanels;
  showMinimap: boolean;
  toggleMinimap: () => void;
  previewStructure: () => void;
};

export function CanvasHeading({ panels, showMinimap, toggleMinimap, previewStructure }: Props) {
  const nodeCount = useEditor((state) => state.nodes.length);
  const edgeCount = useEditor((state) => state.edges.length);
  const flow = useReactFlow();

  return (
    <div className="canvas-heading">
      <div>
        <h2>Target HDF5 Design</h2>
        <span className="canvas-subheading">
          <span className="live-dot" /> {nodeCount} blocks · {edgeCount} connections
        </span>
      </div>
      <div className="canvas-tools">
        <button
          ref={panels.libraryTrigger}
          hidden={!panels.compact}
          aria-label="Toggle block library"
          aria-expanded={panels.libraryOpen}
          aria-controls="workbench-library"
          onClick={panels.toggleLibrary}
        >
          <BookOpen size={16} />
        </button>
        <button
          onClick={() => {
            void flow.zoomOut({ duration: 200 });
          }}
          title="Zoom out"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={() => {
            void flow.zoomIn({ duration: 200 });
          }}
          title="Zoom in"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={() => {
            void flow.fitView({ padding: 0.12, duration: 400, maxZoom: 1 });
          }}
          title="Fit to view"
        >
          <Maximize2 size={15} />
        </button>
        <span className="tool-separator" />
        <button
          className={showMinimap ? 'tool-active' : ''}
          onClick={toggleMinimap}
          title="Toggle minimap"
          aria-pressed={showMinimap}
        >
          <LayoutGrid size={15} />
        </button>
        <button onClick={previewStructure} title="HDF5 structure">
          <GitBranch size={15} />
        </button>
        <button
          ref={panels.inspectorTrigger}
          hidden={!panels.compact && panels.inspectorOpen}
          aria-label="Toggle inspector"
          aria-expanded={panels.inspectorOpen}
          aria-controls="workbench-inspector"
          onClick={panels.toggleInspector}
        >
          <SlidersHorizontal size={16} />
        </button>
      </div>
    </div>
  );
}
