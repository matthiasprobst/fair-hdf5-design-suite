import { createStore } from 'zustand/vanilla';
import type { Config, CsvPreview } from '../types';
import { api } from '../lib/api';
import { errorMessage } from '../lib/validation';
import { toBlueprint, toNode } from './adapters';
import type { EditorStore } from './store';
import { CSV_SOURCE } from './dataNodes';

export interface CsvInput {
  file: File;
  preview: CsvPreview | null;
  loading: boolean;
  error: string;
  settingsKey: string;
}
const parserKey = (config: Config) =>
  JSON.stringify([config.delimiter, config.decimal_separator, config.has_header]);

/** Files and previews belong to one open project tab, never to its blueprint. */
export function createCsvSession(editor: EditorStore, client = api) {
  const store = createStore(() => ({
    inputs: {} as Record<string, CsvInput>,
    revision: 0,
    building: false,
    error: '',
  }));
  const previews = new Map<string, AbortController>();
  let generation: AbortController | null = null;
  const invalidate = () => {
    generation?.abort();
    generation = null;
    store.setState((s) => ({ revision: s.revision + 1, building: false, error: '' }));
  };
  const clear = () => {
    previews.forEach((c) => c.abort());
    previews.clear();
    invalidate();
    store.setState({ inputs: {} });
  };
  const remove = (id: string) => {
    previews.get(id)?.abort();
    previews.delete(id);
    const inputs = { ...store.getState().inputs };
    delete inputs[id];
    invalidate();
    store.setState({ inputs });
  };
  async function load(id: string, file: File): Promise<CsvPreview | undefined> {
    const node = editor
      .getState()
      .nodes.find((n) => n.id === id && n.data.blockType === CSV_SOURCE);
    if (!node) return;
    remove(id);
    const controller = new AbortController();
    previews.set(id, controller);
    const settingsKey = parserKey(node.data.config);
    const input: CsvInput = { file, preview: null, loading: true, error: '', settingsKey };
    store.setState((s) => ({ inputs: { ...s.inputs, [id]: input } }));
    const current = () => !controller.signal.aborted && previews.get(id) === controller;
    try {
      const limit = editor.getState().capabilities?.max_upload_bytes;
      if (!limit) throw new Error('Backend limits are not loaded.');
      if (file.size > limit) throw new Error(`CSV upload limit is ${limit} bytes.`);
      const preview = await client.csvPreview(file, node.data.config, controller.signal);
      if (!current()) return;
      store.setState((s) => ({
        inputs: { ...s.inputs, [id]: { ...input, loading: false, preview } },
      }));
      return preview;
    } catch (error) {
      if (!current()) return;
      store.setState((s) => ({
        inputs: { ...s.inputs, [id]: { ...input, loading: false, error: errorMessage(error) } },
      }));
    } finally {
      if (previews.get(id) === controller) previews.delete(id);
    }
  }
  const issues = () => {
    const state = editor.getState();
    const datasets = state.nodes.filter(
      (n) => (n.data.template || state.catalog[n.data.blockType])?.kind === 'dataset',
    );
    if (!datasets.length) return ['Add a Dataset node to build an HDF5 file with data.'];
    const problems: string[] = [];
    const sources = new Set<string>();
    for (const node of datasets) {
      const edge = state.edges.find((e) => e.target === node.id && e.data?.kind === 'data');
      if (!edge) {
        problems.push(`${node.data.label}: connect a CSV column.`);
        continue;
      }
      sources.add(edge.source);
      const source = state.nodes.find((n) => n.id === edge.source);
      const input = store.getState().inputs[edge.source];
      if (
        !source ||
        !input?.preview ||
        input.loading ||
        input.settingsKey !== parserKey(source.data.config)
      ) {
        problems.push(`${source?.data.label || 'CSV source'}: select a file and load its preview.`);
        continue;
      }
      if (JSON.stringify(input.preview.columns) !== JSON.stringify(source.data.config.columns))
        problems.push(`${source.data.label}: review and accept the changed headers.`);
      if (!input.preview.row_count) problems.push(`${source.data.label}: no data rows.`);
      const index = edge.data?.column_index;
      if (index === undefined || index >= input.preview.columns.length)
        problems.push(`${node.data.label}: select an available column.`);
    }
    const bytes = [...sources].reduce(
      (sum, id) => sum + (store.getState().inputs[id]?.file.size || 0),
      0,
    );
    if (bytes > (state.capabilities?.max_upload_bytes || 0))
      problems.push('Combined CSV files exceed the upload limit.');
    return [...new Set(problems)];
  };
  async function build(signal?: AbortSignal): Promise<Blob | undefined> {
    invalidate();
    const problems = issues();
    if (problems.length) {
      store.setState({ error: problems.join(' ') });
      return;
    }
    const state = editor.getState();
    const files: Record<string, File> = {};
    for (const edge of state.edges) {
      if (edge.data?.kind === 'data')
        files[edge.source] = store.getState().inputs[edge.source].file;
    }
    const controller = new AbortController();
    generation = controller;
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    store.setState({ building: true, error: '' });
    try {
      const blob = await client.hdf5Data(toBlueprint(state), files, controller.signal);
      if (!controller.signal.aborted && generation === controller) return blob;
    } catch (error) {
      if (!controller.signal.aborted && generation === controller)
        store.setState({ error: errorMessage(error) });
    } finally {
      signal?.removeEventListener('abort', abort);
      if (generation === controller) {
        generation = null;
        store.setState({ building: false });
      }
    }
  }
  const start = () => {
    const unsubscribe = editor.subscribe((s, previous) => {
      if (s.graphRevision !== previous.graphRevision) {
        clear();
        return;
      }
      if (s.semanticRevision !== previous.semanticRevision) invalidate();
      for (const [id, input] of Object.entries(store.getState().inputs)) {
        const source = s.nodes.find((n) => n.id === id && n.data.blockType === CSV_SOURCE);
        if (!source) {
          remove(id);
          continue;
        }
        if (input.settingsKey !== parserKey(toNode(source).config)) {
          previews.get(id)?.abort();
          previews.delete(id);
          store.setState((value) => ({
            inputs: {
              ...value.inputs,
              [id]: {
                ...input,
                preview: null,
                loading: false,
                settingsKey: parserKey(source.data.config),
              },
            },
          }));
        }
      }
    });
    return () => {
      unsubscribe();
      clear();
    };
  };
  return { store, start, clear, remove, load, issues, build };
}
