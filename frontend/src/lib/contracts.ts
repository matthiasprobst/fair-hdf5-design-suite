/** Runtime checks for JSON received from the API. Scientific validation stays in Python. */
import type {
  Catalog,
  Preview,
  ProfileAnalysis,
  ProfileDocument,
  TemplateSnapshot,
  ValidationResult,
} from '../types';
import { isCatalogItem, isProfileField, isRecord, isTemplateSnapshot } from './validation';

function invalid(contract: string): never {
  throw new Error(`Invalid ${contract} response from backend.`);
}
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((v) => typeof v === 'string');
const count = (value: unknown) =>
  typeof value === 'number' && Number.isInteger(value) && value >= 0;

export function parseTemplate(value: unknown): TemplateSnapshot {
  if (!isTemplateSnapshot(value)) return invalid('template');
  return value;
}
function parseCatalogItems(value: unknown): Catalog {
  if (!isRecord(value)) return invalid('catalog');
  const result: Catalog = {};
  for (const [id, item] of Object.entries(value)) {
    if (!isCatalogItem(item) || (item.revision !== undefined && !isTemplateSnapshot(item)))
      return invalid('catalog');
    result[id] = item;
  }
  return result;
}
export function parseCatalog(value: unknown): { catalog: Catalog; profile_source: string } {
  if (!isRecord(value) || typeof value.profile_source !== 'string') return invalid('catalog');
  const catalog = parseCatalogItems(value.catalog);
  const legacy = value.legacy_catalog === undefined ? {} : parseCatalogItems(value.legacy_catalog);
  for (const [id, item] of Object.entries(catalog)) {
    if (item.revision !== 1 && legacy[id]) catalog[id] = { ...item, initial: legacy[id] };
  }
  return { catalog, profile_source: value.profile_source };
}
export function parseProfileAnalysis(value: unknown): ProfileAnalysis {
  if (
    !isRecord(value) ||
    !isRecord(value.documents) ||
    !Array.isArray(value.shapes) ||
    (value.source_uri !== undefined && typeof value.source_uri !== 'string') ||
    (value.unbundled_imports !== undefined && !strings(value.unbundled_imports))
  )
    return invalid('profile analysis');
  const documents: Record<string, ProfileDocument> = {};
  for (const [uri, doc] of Object.entries(value.documents)) {
    if (
      !isRecord(doc) ||
      typeof doc.ttl !== 'string' ||
      ['hash', 'resolved_url'].some((key) => doc[key] !== undefined && typeof doc[key] !== 'string')
    )
      return invalid('profile analysis');
    documents[uri] = {
      ttl: doc.ttl,
      ...(typeof doc.hash === 'string' ? { hash: doc.hash } : {}),
      ...(typeof doc.resolved_url === 'string' ? { resolved_url: doc.resolved_url } : {}),
    };
  }
  const shapes = value.shapes.map((shape) => {
    if (
      !isRecord(shape) ||
      typeof shape.shape !== 'string' ||
      typeof shape.label !== 'string' ||
      typeof shape.supported !== 'boolean' ||
      (shape.error !== undefined && typeof shape.error !== 'string') ||
      (shape.fields !== undefined &&
        (!Array.isArray(shape.fields) || !shape.fields.every(isProfileField)))
    )
      return invalid('profile analysis');
    return {
      shape: shape.shape,
      label: shape.label,
      supported: shape.supported,
      ...(Array.isArray(shape.fields) ? { fields: shape.fields.filter(isProfileField) } : {}),
      ...(typeof shape.error === 'string' ? { error: shape.error } : {}),
    };
  });
  return {
    documents,
    shapes,
    ...(typeof value.source_uri === 'string' ? { source_uri: value.source_uri } : {}),
    ...(strings(value.unbundled_imports) ? { unbundled_imports: value.unbundled_imports } : {}),
  };
}
export function parsePreview(value: unknown): Preview {
  if (
    !isRecord(value) ||
    !Array.isArray(value.objects) ||
    !count(value.profiles) ||
    !count(value.node_count) ||
    !count(value.edge_count) ||
    !value.objects.every(
      (item) =>
        isRecord(item) &&
        ['path', 'label', 'profile'].every((key) => typeof item[key] === 'string') &&
        ['group', 'dataset'].includes(String(item.kind)),
    )
  )
    return invalid('preview');
  return value as unknown as Preview;
}
export function parseValidation(value: unknown): ValidationResult {
  if (
    !isRecord(value) ||
    typeof value.conforms !== 'boolean' ||
    !count(value.checks) ||
    !count(value.issue_count) ||
    typeof value.shacl_engine !== 'string' ||
    typeof value.note !== 'string' ||
    !Array.isArray(value.issues) ||
    !value.issues.every(
      (issue) =>
        isRecord(issue) &&
        ['path', 'rule', 'message', 'layer'].every((key) => typeof issue[key] === 'string'),
    )
  )
    return invalid('validation');
  return value as unknown as ValidationResult;
}
