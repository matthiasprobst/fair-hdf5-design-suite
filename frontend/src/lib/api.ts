import { parseCapabilities } from '../editor/limits';
import type { Blueprint, ProfileDocument, TemplateDraft } from '../types';
import {
  parseCatalog,
  parsePreview,
  parseProfileAnalysis,
  parseTemplate,
  parseValidation,
} from './contracts';
import { isRecord } from './validation';

async function checked(response: Response): Promise<Response> {
  if (response.ok) return response;
  let message = `Request failed (HTTP ${response.status})`;
  try {
    const body: unknown = await response.json();
    if (isRecord(body) && typeof body.detail === 'string') message = body.detail;
  } catch {
    /* Keep the status when the response has no JSON body. */
  }
  throw new Error(message);
}
async function getJson(url: string, signal?: AbortSignal): Promise<unknown> {
  return (await checked(await fetch(url, { signal }))).json();
}
async function post(url: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  return checked(
    await fetch(url, {
      signal,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
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
  analyzeProfile: (
    ttl: string,
    documents: Record<string, ProfileDocument> = {},
    source_uri?: string,
    signal?: AbortSignal,
  ) =>
    postJson('/api/catalog/analyze', { ttl, documents, source_uri }, parseProfileAnalysis, signal),
  saveTemplate: (template: TemplateDraft, id?: string, revision?: number, signal?: AbortSignal) =>
    postJson(
      id ? `/api/catalog/${encodeURIComponent(id)}/revisions` : '/api/catalog',
      id ? { expected_revision: revision, template } : template,
      parseTemplate,
      signal,
    ),
  capabilities: async (signal?: AbortSignal) =>
    parseCapabilities(await getJson('/api/capabilities', signal)),
  catalog: async (signal?: AbortSignal) => parseCatalog(await getJson('/api/catalog', signal)),
  // Callers validate the editable envelope using the catalog loaded during initialization.
  demo: (signal?: AbortSignal) => getJson('/api/demo', signal),
  preview: (design: Blueprint, signal?: AbortSignal) =>
    postJson('/api/preview', design, parsePreview, signal),
  shacl: async (design: Blueprint, signal?: AbortSignal) =>
    (await post('/api/export/shacl', design, signal)).blob(),
  hdf5: async (design: Blueprint, signal?: AbortSignal) =>
    (await post('/api/export/hdf5', design, signal)).blob(),
  validateTemplate: (design: Blueprint, signal?: AbortSignal) =>
    postJson('/api/validate/template', design, parseValidation, signal),
  validateFile: async (design: Blueprint, file: File, signal?: AbortSignal) => {
    const body = new FormData();
    body.append('design_json', JSON.stringify(design));
    body.append('file', file);
    return parseValidation(
      await (
        await checked(await fetch('/api/validate/file', { signal, method: 'POST', body }))
      ).json(),
    );
  },
};
