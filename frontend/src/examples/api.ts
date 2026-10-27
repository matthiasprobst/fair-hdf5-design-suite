import type { Blueprint, Catalog } from '../types';
import { parseBlueprint } from '../editor/blueprint';
import { isRecord } from '../lib/validation';
import { jsonRequest } from '../lib/http';
import { parseSummary } from '../projects/api';

export interface ExampleSummary {
  id: string;
  name: string;
  description: string;
  node_count: number;
  edge_count: number;
}
export interface Example extends ExampleSummary {
  blueprint: Blueprint;
}
export function parseExampleSummary(value: unknown): ExampleSummary {
  if (
    !isRecord(value) ||
    !['id', 'name', 'description'].every((k) => typeof value[k] === 'string') ||
    !['node_count', 'edge_count'].every(
      (k) =>
        typeof value[k] === 'number' && Number.isSafeInteger(value[k]) && Number(value[k]) >= 0,
    )
  )
    throw new Error('Invalid example response. Please reload and try again.');
  return value as unknown as ExampleSummary;
}
const path = (id: string) => `/api/examples/${encodeURIComponent(id)}`;
export const examplesApi = {
  list: async (signal?: AbortSignal): Promise<ExampleSummary[]> => {
    const data: unknown = await jsonRequest('/api/examples', 'GET', undefined, undefined, signal);
    if (!Array.isArray(data)) throw new Error('Invalid examples response.');
    return data.map(parseExampleSummary);
  },
  get: async (id: string, catalog: Catalog, signal?: AbortSignal): Promise<Example> => {
    const data: unknown = await jsonRequest(path(id), 'GET', undefined, undefined, signal);
    const summary = parseExampleSummary(data);
    if (!isRecord(data)) throw new Error('Invalid example response.');
    return { ...summary, blueprint: parseBlueprint(data.blueprint, catalog) };
  },
  copy: async (id: string) => parseSummary(await jsonRequest(`${path(id)}/copy`, 'POST')),
};
