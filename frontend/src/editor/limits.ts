import type { Blueprint } from '../types';

export type Capabilities = {
  max_nodes: number;
  max_edges: number;
  max_upload_bytes: number;
  max_dimension_size?: number;
  max_dataset_elements?: number;
  shacl_engine: 'pyshacl' | 'subset';
};

export function parseCapabilities(value: unknown): Capabilities {
  if (!value || typeof value !== 'object')
    throw new Error('Backend capabilities unavailable. Retry connection.');
  const data = value as Record<string, unknown>;
  for (const key of ['max_nodes', 'max_edges', 'max_upload_bytes']) {
    if (typeof data[key] !== 'number' || !Number.isSafeInteger(data[key]) || data[key] <= 0)
      throw new Error('Backend returned invalid limits. Retry connection.');
  }
  for (const key of ['max_dimension_size', 'max_dataset_elements']) {
    if (
      data[key] !== undefined &&
      (typeof data[key] !== 'number' || !Number.isSafeInteger(data[key]) || data[key] <= 0)
    )
      throw new Error('Backend returned invalid data limits. Retry connection.');
  }
  if (data.shacl_engine !== 'pyshacl' && data.shacl_engine !== 'subset')
    throw new Error('Backend returned an unknown validation engine.');
  return data as Capabilities;
}

export function graphLimitError(
  graph: { nodes: readonly unknown[]; edges: readonly unknown[] },
  limits: Capabilities | null,
): string {
  if (!limits) return 'Backend limits are not loaded. Retry connection.';
  if (graph.nodes.length > limits.max_nodes || graph.edges.length > limits.max_edges)
    return `This blueprint exceeds the server limit of ${limits.max_nodes} blocks and ${limits.max_edges} connections. Remove blocks or connections to process it. Editing and JSON export remain available.`;
  return '';
}

export function demoWithinLimits(blueprint: Blueprint, limits: Capabilities): Blueprint {
  return graphLimitError(blueprint, limits)
    ? { name: 'Untitled experiment', version: '0.1', nodes: [], edges: [] }
    : blueprint;
}
