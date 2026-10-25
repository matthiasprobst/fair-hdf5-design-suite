import { Component, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useNodesInitialized,
  useReactFlow,
} from '@xyflow/react';
import { ScientificNode } from './ScientificNode';
import { useEditor } from '../editor/store';
import { useEditorStore } from '../editor/context';
import { useCanEdit } from '../projects/EditorSessionContext';
import type { ScientificFlowEdge, ScientificFlowNode } from '../editor/adapters';
import { COLORS } from '../lib/ui';
const nodeTypes = { scientific: ScientificNode };
const edgeDefaults = { type: 'smoothstep' };
const lineStyle = { stroke: '#3c81e7', strokeWidth: 2 };
const proOptions = { hideAttribution: true };
const deleteKeys = ['Backspace', 'Delete'];
function FitAfterLoad() {
  const initialized = useNodesInitialized();
  const revision = useEditor((s) => s.graphRevision);
  const nodes = useEditor((s) => s.nodes);
  const { fitView, getNodes } = useReactFlow<ScientificFlowNode>();
  const fitted = useRef(-1);
  useEffect(() => {
    // A graph replacement may briefly share the old flow's initialized flag.
    // Wait for the replacement objects and their measurements as well.
    if (
      !initialized ||
      fitted.current === revision ||
      !nodes.length ||
      nodes.some((n) => !n.measured?.width || !n.measured?.height)
    )
      return;
    const current = getNodes();
    if (current.length !== nodes.length || current.some((n, i) => n.data !== nodes[i].data)) return;
    fitted.current = revision;
    void fitView({ padding: 0.13, maxZoom: 0.9 });
  }, [initialized, revision, nodes, fitView, getNodes]);
  return null;
}
export function Canvas({
  showMinimap,
  onSelection,
}: {
  showMinimap: boolean;
  onSelection: () => void;
}) {
  const editorStore = useEditorStore();
  const canEdit = useCanEdit();
  const nodes = useEditor((s) => s.nodes),
    edges = useEditor((s) => s.edges);
  const revision = useEditor((s) => s.graphRevision);
  const actions = editorStore.getState();
  return (
    <ReactFlow<ScientificFlowNode, ScientificFlowEdge>
      key={revision}
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={actions.onNodesChange}
      onEdgesChange={actions.onEdgesChange}
      onConnect={actions.connect}
      isValidConnection={actions.isValidConnection}
      onNodeClick={onSelection}
      onEdgeClick={onSelection}
      defaultEdgeOptions={edgeDefaults}
      connectionLineStyle={lineStyle}
      deleteKeyCode={canEdit ? deleteKeys : null}
      selectionOnDrag={false}
      nodesDraggable={canEdit}
      nodesConnectable={canEdit}
      elementsSelectable
      minZoom={0.05}
      maxZoom={1.7}
      proOptions={proOptions}
    >
      <FitAfterLoad />
      <Background color="#dbe3f0" variant={BackgroundVariant.Dots} gap={19} size={1.05} />
      <Controls className="react-flow-ctrl" position="bottom-left" showInteractive={false} />
      {showMinimap && (
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) =>
            ({
              purple: '#9861e8',
              blue: '#3c85ee',
              green: '#3ab37c',
              orange: '#f4a629',
              coral: '#f07180',
              violet: '#aa69df',
            })[COLORS[node.data.blockType as string]] || '#748baa'
          }
          position="bottom-right"
        />
      )}
    </ReactFlow>
  );
}
export class CanvasErrorBoundary extends Component<
  { children: ReactNode; onExport: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="api-error" role="alert">
          <h2>Canvas could not be displayed</h2>
          <p>Your blueprint is still available for recovery.</p>
          <button onClick={this.props.onExport}>Export recovery blueprint</button>
          <button onClick={() => this.setState({ failed: false })}>Retry canvas</button>
        </div>
      );
    return this.props.children;
  }
}
