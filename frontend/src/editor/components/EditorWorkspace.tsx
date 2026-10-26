import { useCallback, useRef, useState } from 'react';
import type { DragEvent, ReactNode } from 'react';
import { useReactFlow } from '@xyflow/react';
import { SlidersHorizontal } from 'lucide-react';
import type { NodeType } from '../../types';
import Palette from '../../components/Palette';
import { EditorInspector } from '../../components/EditorInspector';
import { Canvas, CanvasErrorBoundary } from '../../components/Canvas';
import { WorkbenchLayout } from '../../layout/WorkbenchLayout';
import { useWorkbenchPanels } from '../../layout/useWorkbenchPanels';
import { useEditor } from '../store';
import { useEditorStore } from '../context';
import { jsonFile } from '../../lib/downloads';
import { toBlueprint } from '../adapters';
import { CanvasHeading } from './CanvasHeading';
import { CSV_SOURCE } from '../dataNodes';

type Props = {
  artifacts: (onClose: () => void) => ReactNode;
  onNotice: (text: string, error?: boolean) => void;
  previewStructure: () => void;
};

export function EditorWorkspace({ artifacts, onNotice, previewStructure }: Props) {
  const editorStore = useEditorStore();
  const catalog = useEditor((state) => state.catalog);
  const panels = useWorkbenchPanels();
  const { showInspector } = panels;
  const [showMinimap, setShowMinimap] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const flow = useReactFlow();

  const addNode = useCallback(
    (type: NodeType, x: number, y: number) => {
      const { nodes, capabilities } = editorStore.getState();
      if (!capabilities) return;
      if (nodes.length >= capabilities.max_nodes) {
        onNotice(`The blueprint limit is ${capabilities.max_nodes} blocks.`, true);
        return;
      }
      editorStore.getState().addNode(type, x, y);
      showInspector();
    },
    [onNotice, showInspector, editorStore],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const type =
        event.dataTransfer.getData('application/x-fair-component') ||
        event.dataTransfer.getData('text/plain');
      if (type !== CSV_SOURCE && !Object.prototype.hasOwnProperty.call(catalog, type)) return;
      const position = flow.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      addNode(type as NodeType, position.x - 95, position.y - 38);
    },
    [catalog, flow, addNode],
  );

  const addFromLibrary = (type: NodeType) => {
    const bounds = canvasRef.current?.getBoundingClientRect();
    const position = bounds
      ? flow.screenToFlowPosition({
          x: bounds.left + bounds.width * 0.48,
          y: bounds.top + bounds.height * 0.43,
        })
      : { x: 80, y: 100 };
    addNode(type, position.x - 80, position.y - 35);
  };

  return (
    <WorkbenchLayout
      panels={panels}
      library={
        <Palette catalog={catalog} onAdd={addFromLibrary} onClose={() => panels.close('library')} />
      }
      inspector={<EditorInspector onClose={() => panels.close('inspector')} onNotice={onNotice} />}
      artifacts={artifacts(() => panels.close('artifacts'))}
      canvas={
        <section className="canvas-shell" aria-label="Design canvas">
          <CanvasHeading
            panels={panels}
            showMinimap={showMinimap}
            toggleMinimap={() => setShowMinimap((value) => !value)}
            previewStructure={previewStructure}
          />
          <div
            className="canvas-region"
            ref={canvasRef}
            onDrop={onDrop}
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = 'copy';
            }}
          >
            <CanvasErrorBoundary
              onExport={() =>
                jsonFile(toBlueprint(editorStore.getState()), 'recovered-blueprint.json')
              }
            >
              <Canvas showMinimap={showMinimap} onSelection={showInspector} />
            </CanvasErrorBoundary>
            <div className="canvas-corner-note">
              <SlidersHorizontal size={13} /> Round ports: relationships · Square ports: CSV data
            </div>
          </div>
        </section>
      }
    />
  );
}
