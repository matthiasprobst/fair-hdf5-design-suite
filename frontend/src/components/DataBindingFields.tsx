import { useStore } from 'zustand';
import { useEditor } from '../editor/store';
import { useEditorStore } from '../editor/context';
import { useProjectSession } from '../projects/EditorSessionContext';

export function DataBindingFields({ target }: { target: string }) {
  const graph = useEditorStore();
  const session = useProjectSession();
  const edge = useEditor((s) =>
    s.edges.find((e) => e.target === target && e.data?.kind === 'data'),
  );
  const source = useEditor((s) => s.nodes.find((n) => n.id === edge?.source));
  const input = useStore(session.csv.store, (s) => s.inputs[edge?.source || '']);
  const columns = (source?.data.config.columns || []) as string[];
  return (
    <section className="csv-binding">
      <strong>CSV data input</strong>
      {edge && source ? (
        <>
          <p>Source: {source.data.label}</p>
          <div className="form-field">
            <label htmlFor={`data-column-${edge.id}`}>CSV column</label>
            <select
              id={`data-column-${edge.id}`}
              disabled={!session.canEdit()}
              value={edge.data?.column_index ?? 0}
              onChange={(e) => graph.getState().mapColumn(edge.id, Number(e.target.value))}
            >
              {!columns.length && (
                <option value={edge.data?.column_index ?? 0}>Select a CSV file first</option>
              )}
              {!!columns.length && (edge.data?.column_index ?? 0) >= columns.length && (
                <option value={edge.data?.column_index}>Unavailable column</option>
              )}
              {columns.map((name, index) => (
                <option key={index} value={index}>
                  {index + 1}. {name || `Column ${index + 1}`}
                </option>
              ))}
            </select>
          </div>
          <small>
            {input?.preview
              ? `${input.preview.row_count} rows loaded`
              : 'Select the source node and load its CSV file.'}{' '}
            · Dataset shape must be 0 or match the row count.
          </small>
          <button
            disabled={!session.canEdit()}
            onClick={() => graph.getState().deleteElements([], [edge.id])}
          >
            Remove data connection
          </button>
        </>
      ) : (
        <p>Connect a CSV Source’s square output to this dataset’s square input.</p>
      )}
    </section>
  );
}
