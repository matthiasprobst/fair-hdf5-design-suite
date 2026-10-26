import { useMemo } from 'react';
import Inspector from './Inspector';
import { EditorReferenceFields } from './EditorReferenceFields';
import { useTemplateUpgrade } from '../editor/useTemplateUpgrade';
import { useEditor } from '../editor/store';
import { useEditorStore } from '../editor/context';
import { toEdge, toNode } from '../editor/adapters';
import { useCanEdit } from '../projects/EditorSessionContext';
import { CSV_SOURCE } from '../editor/dataNodes';
import { CsvSourceInspector } from './CsvSourceInspector';
import { DataBindingFields } from './DataBindingFields';
export function EditorInspector({
  onClose,
  onNotice,
}: {
  onClose: () => void;
  onNotice: (text: string, error?: boolean) => void;
}) {
  const editorStore = useEditorStore();
  const canEdit = useCanEdit();
  const upgrade = useTemplateUpgrade(onNotice);
  const selectedNode = useEditor((s) => s.nodes.find((n) => n.selected));
  const selectedEdge = useEditor((s) => s.edges.find((e) => e.selected));
  const catalog = useEditor((s) => s.catalog);
  const node = useMemo(() => (selectedNode ? toNode(selectedNode) : null), [selectedNode]);
  const edge = useMemo(() => (selectedEdge ? toEdge(selectedEdge) : null), [selectedEdge]);
  const actions = editorStore.getState();
  if (node?.type === CSV_SOURCE)
    return <CsvSourceInspector key={node.id} node={node} onClose={onClose} onNotice={onNotice} />;
  if (edge?.kind === 'data')
    return (
      <aside className="inspector panel-shell">
        <div className="inspector-heading">
          <strong>Data connection</strong>
          <button onClick={onClose} aria-label="Close inspector">
            ×
          </button>
        </div>
        <div className="inspector-scroll inspector-fields">
          <DataBindingFields target={edge.target} />
        </div>
      </aside>
    );
  return (
    <Inspector
      readOnly={!canEdit}
      referenceFields={node ? <EditorReferenceFields node={node} onNotice={onNotice} /> : null}
      dataFields={
        node && (node.template || catalog[node.type])?.kind === 'dataset' ? (
          <DataBindingFields target={node.id} />
        ) : null
      }
      onUpgrade={upgrade.apply}
      upgrading={upgrade.busy}
      key={node?.id || edge?.id || 'empty'}
      node={node}
      edge={edge}
      catalog={catalog}
      onUpdate={actions.updateNode}
      onDelete={(id) => actions.deleteElements([id])}
      onDuplicate={actions.duplicateNode}
      onEdgeChange={actions.updateEdge}
      onDeleteEdge={(id) => actions.deleteElements([], [id])}
      onClose={onClose}
      onNotice={onNotice}
    />
  );
}
