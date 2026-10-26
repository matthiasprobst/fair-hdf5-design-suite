import { useEffect, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { Copy, FileSpreadsheet, Trash2, X } from 'lucide-react';
import type { Config, DesignNode } from '../types';
import { useProjectSession } from '../projects/EditorSessionContext';
import { useEditorStore } from '../editor/context';
import { api } from '../lib/api';
import { errorMessage } from '../lib/validation';

export function CsvSourceInspector({
  node,
  onClose,
  onNotice,
}: {
  node: DesignNode;
  onClose: () => void;
  onNotice: (text: string, error?: boolean) => void;
}) {
  const session = useProjectSession();
  const graph = useEditorStore();
  const canEdit = session.canEdit();
  const input = useStore(session.csv.store, (s) => s.inputs[node.id]);
  const [selected, setSelected] = useState<number[]>([]);
  const [loadingExample, setLoadingExample] = useState(false);
  const exampleRequest = useRef<AbortController | null>(null);
  useEffect(() => () => exampleRequest.current?.abort(), []);
  const preview = input?.preview;
  const matching =
    preview && JSON.stringify(preview.columns) === JSON.stringify(node.config.columns);
  const update = (config: Config) => graph.getState().updateNode(node.id, { config });
  const accept = () => {
    if (preview && input) update({ columns: preview.columns, filename: input.file.name });
  };
  const load = async (file: File) => {
    const result = await session.csv.load(node.id, file);
    if (!result) return;
    setSelected(result.columns.map((_, index) => index));
    const current = graph.getState().nodes.find((n) => n.id === node.id);
    if (session.canEdit() && current && !(current.data.config.columns as string[]).length)
      graph
        .getState()
        .updateNode(node.id, { config: { columns: result.columns, filename: file.name } });
  };
  const loadExample = async () => {
    exampleRequest.current?.abort();
    const controller = new AbortController();
    exampleRequest.current = controller;
    setLoadingExample(true);
    try {
      const file = await api.exampleCsv(controller.signal);
      if (!controller.signal.aborted) await load(file);
    } catch (error) {
      if (!controller.signal.aborted) onNotice(errorMessage(error), true);
    } finally {
      if (!controller.signal.aborted) setLoadingExample(false);
    }
  };
  const createDatasets = () => {
    if (!preview || !matching) return;
    const { capabilities, nodes, edges } = graph.getState();
    if (
      !capabilities ||
      nodes.length + selected.length > capabilities.max_nodes ||
      edges.length + selected.length > capabilities.max_edges
    ) {
      onNotice('Creating these datasets would exceed the graph limits.', true);
      return;
    }
    graph.getState().createDatasets(
      node.id,
      selected.map((index) => ({
        index,
        name: preview.columns[index],
        dtype: preview.suggested_dtypes[index],
      })),
    );
    onNotice(
      `${selected.length} dataset(s) created. Configure their metadata and units in the inspector.`,
    );
  };
  return (
    <aside className="inspector panel-shell">
      <div className="inspector-heading">
        <strong>CSV Source</strong>
        <button className="icon-button" onClick={onClose} aria-label="Close inspector">
          <X size={17} />
        </button>
      </div>
      <div className="inspector-scroll inspector-fields csv-inspector">
        <div className="inspector-profile-card">
          <span className="inspector-icon node-green">
            <FileSpreadsheet size={29} />
          </span>
          <div>
            <strong>{node.label}</strong>
            <p>One CSV column per HDF5 dataset</p>
          </div>
        </div>
        <p className="technical-note">
          Files are kept for this open project only. Select them again after reopening. Settings and
          mappings are saved.
        </p>
        {node.config.example_file === 'measurements.csv' && (
          <div className="csv-header-review">
            <p>
              This example includes synthetic time, pressure and sample-name data. Load it to try
              the existing mappings.
            </p>
            <button disabled={loadingExample || input?.loading} onClick={() => void loadExample()}>
              {loadingExample ? 'Loading example…' : 'Load example CSV'}
            </button>
          </div>
        )}
        <div className="form-field">
          <label htmlFor="csv-name">Block name</label>
          <input
            id="csv-name"
            disabled={!canEdit}
            value={node.label}
            onChange={(e) => graph.getState().updateNode(node.id, { label: e.target.value })}
          />
        </div>
        <fieldset className="csv-settings" disabled={!canEdit}>
          <legend>Import settings</legend>
          <div className="form-field">
            <label htmlFor="csv-delimiter">Delimiter</label>
            <select
              id="csv-delimiter"
              value={String(node.config.delimiter)}
              onChange={(e) =>
                update({
                  delimiter: e.target.value,
                  ...(e.target.value === ',' ? { decimal_separator: '.' } : {}),
                })
              }
            >
              <option value=",">Comma</option>
              <option value=";">Semicolon</option>
              <option value={'\t'}>Tab</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="csv-decimal">Decimal separator</label>
            <select
              id="csv-decimal"
              value={String(node.config.decimal_separator)}
              onChange={(e) => update({ decimal_separator: e.target.value })}
            >
              <option value=".">Dot (1.25)</option>
              <option value="," disabled={node.config.delimiter === ','}>
                Comma (1,25)
              </option>
            </select>
          </div>
          <label className="csv-checkbox">
            <input
              type="checkbox"
              checked={node.config.has_header === true}
              onChange={(e) => update({ has_header: e.target.checked })}
            />
            First row contains headers
          </label>
        </fieldset>
        <div className="form-field">
          <label htmlFor="csv-file">CSV file (UTF-8)</label>
          <input
            id="csv-file"
            type="file"
            disabled={loadingExample}
            accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) void load(file);
            }}
          />
          <small>
            {input
              ? input.file.name
              : node.config.filename
                ? `${node.config.filename} · Select file again`
                : 'Select a file to preview its columns.'}
          </small>
        </div>
        {input && (
          <div className="csv-file-actions">
            <button
              disabled={input.loading || loadingExample}
              onClick={() => void load(input.file)}
            >
              {input.loading ? 'Loading CSV…' : 'Load preview'}
            </button>
            <button
              disabled={input.loading || loadingExample}
              onClick={() => session.csv.remove(node.id)}
            >
              Clear file
            </button>
          </div>
        )}
        {input?.error && (
          <p className="form-error" role="alert">
            {input.error}
          </p>
        )}
        {preview && (
          <>
            <p className="csv-summary">
              {preview.row_count} rows · {preview.columns.length} columns · Preview: first{' '}
              {preview.rows.length} rows
            </p>
            {!matching && (
              <div className="csv-header-review">
                <p>
                  These headers differ from the saved mapping. Bindings keep their column positions;
                  review them before building.
                </p>
                {canEdit ? (
                  <button onClick={accept}>Accept new headers</button>
                ) : (
                  <p>An editor must accept the new headers.</p>
                )}
              </div>
            )}
            <div
              className="csv-table-wrap"
              role="region"
              aria-label="CSV data preview"
              tabIndex={0}
            >
              <table className="csv-table">
                <thead>
                  <tr>
                    {preview.columns.map((name, index) => (
                      <th key={index}>
                        {name || `Column ${index + 1}`}
                        <small>
                          Column {index + 1} · {preview.suggested_dtypes[index]}
                        </small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <fieldset className="csv-columns" disabled={!canEdit || !matching}>
              <legend>Create datasets</legend>
              <p>Select columns to add their Dataset nodes and connections.</p>
              {preview.columns.map((name, index) => (
                <label className="csv-checkbox" key={index}>
                  <input
                    type="checkbox"
                    checked={selected.includes(index)}
                    onChange={(e) =>
                      setSelected((values) =>
                        e.target.checked
                          ? [...values, index].sort((a, b) => a - b)
                          : values.filter((v) => v !== index),
                      )
                    }
                  />
                  {index + 1}. {name || `Column ${index + 1}`}
                  <small>{preview.suggested_dtypes[index]}</small>
                </label>
              ))}
              <button disabled={!selected.length || !canEdit || !matching} onClick={createDatasets}>
                Create datasets from selected columns
              </button>
            </fieldset>
          </>
        )}
        <small className="csv-limits">
          Limits:{' '}
          {((graph.getState().capabilities?.max_upload_bytes || 0) / 1_000_000).toLocaleString()} MB
          combined; {(graph.getState().capabilities?.max_dimension_size || 50_000).toLocaleString()}{' '}
          rows;{' '}
          {(graph.getState().capabilities?.max_dataset_elements || 2_000_000).toLocaleString()}{' '}
          cells / populated values.
        </small>
        <div className="csv-file-actions">
          <button disabled={!canEdit} onClick={() => graph.getState().duplicateNode(node.id)}>
            <Copy size={13} />
            Duplicate source
          </button>
          <button
            className="delete-button"
            disabled={!canEdit}
            onClick={() => graph.getState().deleteElements([node.id])}
          >
            <Trash2 size={13} />
            Delete source
          </button>
        </div>
      </div>
    </aside>
  );
}
