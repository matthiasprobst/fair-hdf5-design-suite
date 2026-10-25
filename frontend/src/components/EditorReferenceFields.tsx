import type { DesignNode } from '../types';
import { editorStore, useEditor } from '../editor/store';
import ReferenceFields from './ReferenceFields';

export function EditorReferenceFields({
  node,
  onNotice,
}: {
  node: DesignNode;
  onNotice: (message: string, error?: boolean) => void;
}) {
  const nodes = useEditor((s) => s.nodes);
  const edges = useEditor((s) => s.edges);
  const limits = useEditor((s) => s.capabilities);
  const actions = editorStore.getState();
  return (
    <ReferenceFields
      node={node}
      nodes={nodes}
      edges={edges}
      limits={limits}
      onSelect={(id) => actions.select(id)}
      onRemove={(id) => actions.deleteElements([], [id])}
      onLink={(field, target) => actions.linkNode(node.id, field, target)}
      onCreate={(field) => {
        actions.createLinkedNode(node.id, field);
        onNotice('Linked node created. Select it to enter its metadata.');
      }}
    />
  );
}
