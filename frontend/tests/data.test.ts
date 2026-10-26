import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseBlueprint } from '../src/editor/blueprint';
import { fromBlueprint, toBlueprint } from '../src/editor/adapters';
import { csvSource } from '../src/editor/dataNodes';
import type { Blueprint, Catalog } from '../src/types';

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
