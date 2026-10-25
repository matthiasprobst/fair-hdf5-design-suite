import { useMemo } from 'react';
import Inspector from './Inspector';
import { EditorReferenceFields } from './EditorReferenceFields';
import { useTemplateUpgrade } from '../editor/useTemplateUpgrade';
import { editorStore, useEditor } from '../editor/store';
import { toEdge, toNode } from '../editor/adapters';
const deleteNode = (id: string) => editorStore.getState().deleteElements([id]);
const deleteEdge = (id: string) => editorStore.getState().deleteElements([], [id]);
export function EditorInspector({
  onClose,
  onNotice,
}: {
  onClose: () => void;
  onNotice: (text: string, error?: boolean) => void;
}) {
  const upgrade = useTemplateUpgrade(onNotice);
  const selectedNode = useEditor((s) => s.nodes.find((n) => n.selected));
  const selectedEdge = useEditor((s) => s.edges.find((e) => e.selected));
  const catalog = useEditor((s) => s.catalog);
  const node = useMemo(() => (selectedNode ? toNode(selectedNode) : null), [selectedNode]);
  const edge = useMemo(() => (selectedEdge ? toEdge(selectedEdge) : null), [selectedEdge]);
  const actions = editorStore.getState();
  return (
    <Inspector
      referenceFields={node ? <EditorReferenceFields node={node} onNotice={onNotice} /> : null}
      onUpgrade={upgrade.apply}
      upgrading={upgrade.busy}
      key={node?.id || edge?.id || 'empty'}
      node={node}
      edge={edge}
      catalog={catalog}
      onUpdate={actions.updateNode}
      onDelete={deleteNode}
      onDuplicate={actions.duplicateNode}
      onEdgeChange={actions.updateEdge}
      onDeleteEdge={deleteEdge}
      onClose={onClose}
      onNotice={onNotice}
    />
  );
}
