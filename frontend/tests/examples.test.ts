import test from 'node:test';
import assert from 'node:assert/strict';
import { examplesApi, parseExampleSummary } from '../src/examples/api';
import { ExamplePreviewSession } from '../src/examples/previewSession';
import { projectApi } from '../src/projects/api';
import { api } from '../src/lib/api';
import { csvSource } from '../src/editor/dataNodes';
import type { CsvPreview } from '../src/types';

const summary = {
  id: 'csv-measurements',
  name: 'CSV example',
  description: 'Synthetic data',
  node_count: 1,
  edge_count: 0,
};

test('example summaries validate their names and graph counts', () => {
  assert.deepEqual(parseExampleSummary(summary), summary);
  for (const patch of [{ id: 1 }, { node_count: -1 }, { edge_count: 0.5 }, { description: null }])
    assert.throws(() => parseExampleSummary({ ...summary, ...patch }));
});

test('browsing example APIs uses GET and copying requires an explicit POST', async (t) => {
  const calls: { url: string; method: string }[] = [];
  const project = {
    id: 'my-copy',
    name: summary.name,
    description: '',
    owner_id: 'alice',
    owner_name: 'Alice',
    role: 'owner',
    shared: false,
    revision: 1,
    created_at: 1,
    updated_at: 1,
  };
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method || 'GET' });
    const data = url.endsWith('/copy')
      ? project
      : url === '/api/examples'
        ? [summary]
        : { ...summary, blueprint: { name: summary.name, version: '0.1', nodes: [], edges: [] } };
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  });
  await examplesApi.list();
  await examplesApi.get(summary.id, {});
  assert.ok(calls.every((c) => c.method === 'GET'));
  assert.equal((await examplesApi.copy(summary.id)).id, 'my-copy');
  assert.deepEqual(calls.at(-1), { url: '/api/examples/csv-measurements/copy', method: 'POST' });
});

test('example previews cannot mutate, reserve, poll, or save projects', async (t) => {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const previousStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  let writes = 0;
  Object.defineProperty(globalThis, 'window', { configurable: true, value: new EventTarget() });
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: () => null,
      setItem: () => writes++,
      removeItem: () => writes++,
    },
  });
  t.after(() => {
    if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow);
    else Reflect.deleteProperty(globalThis, 'window');
    if (previousStorage) Object.defineProperty(globalThis, 'localStorage', previousStorage);
    else Reflect.deleteProperty(globalThis, 'localStorage');
  });
  const acquire = t.mock.method(projectApi, 'acquire');
  const save = t.mock.method(projectApi, 'save');
  const get = t.mock.method(projectApi, 'get');
  const intervals = t.mock.method(globalThis, 'setInterval');
  const preview: CsvPreview = {
    columns: ['p'],
    rows: [['1']],
    row_count: 1,
    suggested_dtypes: ['int64'],
  };
  t.mock.method(api, 'csvPreview', async () => preview);
  const session = new ExamplePreviewSession(
    {
      ...summary,
      blueprint: {
        name: summary.name,
        version: '0.1',
        edges: [],
        nodes: [
          {
            id: 'csv',
            type: 'csv_source',
            label: 'CSV',
            x: 0,
            y: 0,
            config: { ...csvSource.defaults, columns: ['p'] },
          },
        ],
      },
    },
    {},
    { max_nodes: 250, max_edges: 1000, max_upload_bytes: 30_000_000, shacl_engine: 'pyshacl' },
    'alice',
  );
  const stop = session.start();
  t.after(stop);
  session.graph.getState().rename('Do not modify');
  session.setDescription('Do not save');
  await session.edit();
  await session.csv.load('csv', new File(['p\n1\n'], 'example.csv'));
  assert.equal(session.canEdit(), false);
  assert.equal(session.graph.getState().name, summary.name);
  assert.equal(session.state.getState().dirty, false);
  assert.equal(session.state.getState().project.description, summary.description);
  assert.equal(acquire.mock.callCount(), 0);
  assert.equal(save.mock.callCount(), 0);
  assert.equal(get.mock.callCount(), 0);
  assert.equal(
    intervals.mock.callCount(),
    0,
    'Previews must not schedule reservation or project polling',
  );
  assert.equal(writes, 0);
  stop();
  assert.deepEqual(session.csv.store.getState().inputs, {});
});
