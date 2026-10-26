import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseBlueprint } from '../src/editor/blueprint';
import { fromBlueprint, toBlueprint } from '../src/editor/adapters';
import { csvSource } from '../src/editor/dataNodes';
import type { Blueprint, Catalog } from '../src/types';
import { createEditorStore } from '../src/editor/store';
import { createCsvSession } from '../src/editor/csvSession';
import { api } from '../src/lib/api';
import type { CsvPreview } from '../src/types';
import { parseCsvPreview } from '../src/lib/contracts';

const catalog: Catalog = {
  dataset: { ...csvSource, label: 'Dataset', kind: 'dataset', defaults: {} },
};
export const dataBlueprint = (): Blueprint => ({
  name: 'CSV test',
  version: '0.1',
  nodes: [
    {
      id: 'csv',
      type: 'csv_source',
      label: 'CSV',
      x: 0,
      y: 0,
      config: { ...structuredClone(csvSource.defaults), columns: ['pressure'] },
    },
    {
      id: 'data',
      type: 'dataset',
      label: 'Pressure',
      x: 300,
      y: 0,
      config: { path: '/data/pressure', dtype: 'float64', shape: '0' },
    },
  ],
  edges: [
    {
      id: 'binding',
      source: 'csv',
      target: 'data',
      relation: 'provides_data',
      kind: 'data',
      column_index: 0,
    },
  ],
});

test('CSV sources and bindings round trip without SHACL templates or file contents', () => {
  const design = dataBlueprint();
  assert.deepEqual(toBlueprint(fromBlueprint(parseBlueprint(design, catalog))), design);
  assert.equal(fromBlueprint(design).edges[0].sourceHandle, 'data-out');
  assert.equal(fromBlueprint(design).edges[0].targetHandle, 'data-in');
});

test('invalid bindings and arbitrary source configuration are rejected', () => {
  for (const patch of [
    { column_index: -1 },
    { kind: 'other' },
    { source: 'data', target: 'csv' },
  ]) {
    const design = dataBlueprint();
    Object.assign(design.edges[0], patch);
    assert.throws(() => parseBlueprint(design, catalog));
  }
  const design = dataBlueprint();
  design.edges.push({ ...design.edges[0], id: 'duplicate' });
  assert.throws(() => parseBlueprint(design, catalog));
  design.edges.pop();
  design.nodes[0].config.content = 'must never be saved';
  assert.throws(() => parseBlueprint(design, catalog));
});

test('bundled CSV hints round trip while arbitrary file references are rejected', () => {
  const design = dataBlueprint();
  design.nodes[0].config.example_file = 'measurements.csv';
  assert.deepEqual(toBlueprint(fromBlueprint(parseBlueprint(design, catalog))), design);
  design.nodes[0].config.example_file = '../../private.csv';
  assert.throws(() => parseBlueprint(design, catalog));
});

const capabilities = {
  max_nodes: 250,
  max_edges: 1000,
  max_upload_bytes: 30_000_000,
  shacl_engine: 'pyshacl' as const,
};
function editor(canEdit = () => true) {
  const graph = createEditorStore(canEdit);
  graph.getState().setCapabilities(capabilities);
  graph.getState().hydrate(dataBlueprint(), catalog);
  return graph;
}
const preview: CsvPreview = {
  columns: ['pressure'],
  row_count: 2,
  suggested_dtypes: ['float64'],
  rows: [['1.25'], ['2.5']],
};

test('data ports reject incompatible targets, duplicate inputs, and relationship ports', () => {
  const graph = editor();
  const connection = {
    source: 'csv',
    target: 'data',
    sourceHandle: 'data-out',
    targetHandle: 'data-in',
  };
  assert.equal(graph.getState().isValidConnection(connection), false);
  graph.getState().deleteElements([], ['binding']);
  assert.equal(graph.getState().isValidConnection(connection), true);
  assert.equal(graph.getState().isValidConnection({ ...connection, targetHandle: 'in' }), false);
  assert.equal(
    graph.getState().isValidConnection({ ...connection, source: 'data', target: 'csv' }),
    false,
  );
  graph.getState().connect(connection);
  assert.equal(graph.getState().edges[0].data?.kind, 'data');
  assert.equal(graph.getState().edges[0].data?.column_index, 0);
});

test('creating datasets is atomic, generates unique paths, and respects read-only access', () => {
  const graph = editor();
  let updates = 0;
  const stop = graph.subscribe(() => updates++);
  graph.getState().createDatasets('csv', [
    { index: 0, name: 'pressure', dtype: 'float64' },
    { index: 0, name: 'pressure', dtype: 'string' },
  ]);
  assert.equal(updates, 1);
  assert.equal(graph.getState().nodes.length, 4);
  assert.equal(graph.getState().nodes[2].data.config.path, '/data/pressure_2');
  assert.equal(graph.getState().nodes[3].data.config.path, '/data/pressure_3');
  assert.equal(graph.getState().edges.length, 3);
  stop();
  const viewer = editor(() => false);
  viewer.getState().createDatasets('csv', [{ index: 0, name: 'p', dtype: 'float64' }]);
  viewer.getState().mapColumn('binding', 1);
  assert.equal(viewer.getState().nodes.length, 2);
  assert.equal(viewer.getState().edges[0].data?.column_index, 0);
});

test('session files never dirty or serialize into the blueprint; viewers can load and build', async () => {
  const graph = editor(() => false);
  const revision = graph.getState().saveRevision;
  const session = createCsvSession(graph, {
    ...api,
    csvPreview: async () => preview,
    hdf5Data: async () => new Blob(['hdf5']),
  });
  const stop = session.start();
  await session.load('csv', new File(['pressure\n1.25\n2.5'], 'private.csv'));
  assert.equal(graph.getState().saveRevision, revision);
  assert.deepEqual(session.issues(), []);
  assert.equal(await (await session.build())?.text(), 'hdf5');
  assert.equal(JSON.stringify(toBlueprint(graph.getState())).includes('private.csv'), false);
  assert.equal(JSON.stringify(toBlueprint(graph.getState())).includes('1.25'), false);
  stop();
  assert.deepEqual(session.store.getState().inputs, {});
});

test('file replacement and graph edits discard late preview and generation responses', async () => {
  const graph = editor();
  let resolvePreview!: (value: CsvPreview) => void;
  let resolveBuild!: (value: Blob) => void;
  let calls = 0;
  const session = createCsvSession(graph, {
    ...api,
    csvPreview: async () =>
      ++calls === 1
        ? new Promise<CsvPreview>((resolve) => {
            resolvePreview = resolve;
          })
        : preview,
    hdf5Data: () =>
      new Promise<Blob>((resolve) => {
        resolveBuild = resolve;
      }),
  });
  const stop = session.start();
  const first = session.load('csv', new File(['old'], 'old.csv'));
  await session.load('csv', new File(['new'], 'new.csv'));
  resolvePreview({ ...preview, row_count: 99 });
  assert.equal(await first, undefined);
  assert.equal(session.store.getState().inputs.csv.preview?.row_count, 2);
  const building = session.build();
  graph.getState().updateNode('data', { config: { path: '/changed' } });
  resolveBuild(new Blob(['stale']));
  assert.equal(await building, undefined);
  const second = session.build();
  session.remove('csv');
  resolveBuild(new Blob(['also stale']));
  assert.equal(await second, undefined);
  stop();
});

test('changed parsing settings invalidate previews; deletion and graph replacement clear files', async () => {
  const graph = editor();
  const session = createCsvSession(graph, { ...api, csvPreview: async () => preview });
  const stop = session.start();
  await session.load('csv', new File(['data'], 'test.csv'));
  graph.getState().updateNode('csv', { config: { delimiter: ';' } });
  assert.equal(session.store.getState().inputs.csv.preview, null);
  assert.ok(session.issues().length > 0);
  await session.load('csv', session.store.getState().inputs.csv.file);
  graph.getState().replace(dataBlueprint());
  assert.deepEqual(session.store.getState().inputs, {});
  await session.load('csv', new File(['data'], 'test.csv'));
  graph.getState().deleteElements(['csv']);
  assert.deepEqual(session.store.getState().inputs, {});
  stop();
});

test('changed headers and malformed preview contracts cannot enable data export', async () => {
  assert.throws(() => parseCsvPreview({ ...preview, rows: [['one', 'two']] }));
  assert.throws(() => parseCsvPreview({ ...preview, suggested_dtypes: ['bad'] }));
  const graph = editor();
  const session = createCsvSession(graph, {
    ...api,
    csvPreview: async () => ({ ...preview, columns: ['different'] }),
  });
  const stop = session.start();
  await session.load('csv', new File(['data'], 'test.csv'));
  assert.ok(session.issues().some((message) => message.includes('headers')));
  assert.equal(await session.build(), undefined);
  graph.getState().updateNode('csv', { config: { columns: ['different'] } });
  assert.deepEqual(session.issues(), []);
  stop();
});
