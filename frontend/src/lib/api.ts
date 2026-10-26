import { parseCapabilities } from '../editor/limits';
import type { Blueprint, ProfileDocument, Config } from '../types';
import { parseCsvPreview } from './contracts';
import { parseCatalog, parsePreview, parseProfileAnalysis, parseValidation } from './contracts';
import { request } from './http';

async function getJson(url: string, signal?: AbortSignal): Promise<unknown> {
  return (await request(url, { signal })).json();
}
async function post(url: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  return request(url, {
    signal,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
async function postJson<T>(
  url: string,
  body: unknown,
  parse: (value: unknown) => T,
  signal?: AbortSignal,
): Promise<T> {
  return parse(await (await post(url, body, signal)).json());
}
export const api = {
  exampleCsv: async (signal?: AbortSignal) =>
    new File(
      [await (await request('/api/examples/files/measurements.csv', { signal })).blob()],
      'measurements.csv',
      { type: 'text/csv' },
    ),
  csvPreview: async (file: File, config: Config, signal?: AbortSignal) => {
    const body = new FormData();
    body.append('settings_json', JSON.stringify(config));
    body.append('file', file);
    return parseCsvPreview(
      await (await request('/api/data/csv/preview', { method: 'POST', body, signal })).json(),
    );
  },
  hdf5Data: async (design: Blueprint, files: Record<string, File>, signal?: AbortSignal) => {
    const body = new FormData();
    body.append('design_json', JSON.stringify(design));
    for (const [id, file] of Object.entries(files)) body.append(id, file);
    return (await request('/api/export/hdf5/data', { method: 'POST', body, signal })).blob();
  },
  analyzeProfile: (
    ttl: string,
    documents: Record<string, ProfileDocument> = {},
    source_uri?: string,
    signal?: AbortSignal,
  ) =>
    postJson('/api/catalog/analyze', { ttl, documents, source_uri }, parseProfileAnalysis, signal),
  capabilities: async (signal?: AbortSignal) =>
    parseCapabilities(await getJson('/api/capabilities', signal)),
  catalog: async (signal?: AbortSignal) => parseCatalog(await getJson('/api/catalog', signal)),
  // Callers validate the editable envelope using the catalog loaded during initialization.
  demo: (signal?: AbortSignal) => getJson('/api/demo', signal),
  preview: (design: Blueprint, signal?: AbortSignal) =>
    postJson('/api/preview', design, parsePreview, signal),
  shacl: async (design: Blueprint, signal?: AbortSignal) =>
    (await post('/api/export/shacl', design, signal)).blob(),
  metadata: async (design: Blueprint, signal?: AbortSignal) =>
    (await post('/api/export/rdf', design, signal)).blob(),
  hdf5: async (design: Blueprint, signal?: AbortSignal) =>
    (await post('/api/export/hdf5', design, signal)).blob(),
  validateTemplate: (design: Blueprint, signal?: AbortSignal) =>
    postJson('/api/validate/template', design, parseValidation, signal),
  validateFile: async (design: Blueprint, file: File, signal?: AbortSignal) => {
    const body = new FormData();
    body.append('design_json', JSON.stringify(design));
    body.append('file', file);
    return parseValidation(
      await (await request('/api/validate/file', { signal, method: 'POST', body })).json(),
    );
  },
};
