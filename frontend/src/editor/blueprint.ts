import { graphLimitError } from './limits';
import type { Capabilities } from './limits';
import type { Blueprint, Catalog, CatalogItem, DesignNode, DesignEdge, NodeType } from '../types';
import { isRecord, isConfig, isTemplateSnapshot } from '../lib/validation';

// Validate the storage/import envelope, not scientific constraints. Incomplete
// paths and metadata must remain editable even when the backend rejects them.
export function parseBlueprint(value: unknown, catalog: Catalog, limits?: Capabilities): Blueprint {
  const object = isRecord;
  const fail = (message: string): never => {
    throw new Error(`Invalid blueprint: ${message}`);
  };
  if (
    !object(value) ||
    typeof value.name !== 'string' ||
    typeof value.version !== 'string' ||
    !Array.isArray(value.nodes) ||
    !Array.isArray(value.edges)
  )
    return fail('expected name, version, nodes and edges.');
  if (limits) {
    const error = graphLimitError({ nodes: value.nodes, edges: value.edges }, limits);
    if (error) return fail(error);
  }
  const ids = new Set<string>();
  const nodes = value.nodes.map((n): DesignNode => {
    if (
      !object(n) ||
      typeof n.id !== 'string' ||
      !/^[A-Za-z0-9_-]{1,90}$/.test(n.id) ||
      ids.has(n.id)
    )
      return fail('node IDs must be valid and unique.');
    if (
      typeof n.type !== 'string' ||
      (!Object.prototype.hasOwnProperty.call(catalog, n.type) && !object(n.template)) ||
      typeof n.label !== 'string' ||
      typeof n.x !== 'number' ||
      !Number.isFinite(n.x) ||
      typeof n.y !== 'number' ||
      !Number.isFinite(n.y) ||
      !object(n.config)
    )
      return fail(`invalid node ${n.id}.`);
    let template: CatalogItem | undefined;
    if (n.template !== undefined) {
      if (!isTemplateSnapshot(n.template) || n.template.id !== n.type)
        return fail(`invalid template snapshot in ${n.id}.`);
      template = structuredClone(n.template);
    } else if (catalog[n.type]?.initial) template = catalog[n.type].initial;
    else if (catalog[n.type]?.revision === 1) template = catalog[n.type];
    else if (catalog[n.type]?.revision)
      return fail(`legacy node ${n.id} needs its original template revision.`);
    if (!isConfig(n.config)) return fail(`unsupported metadata in ${n.id}.`);
    const config = structuredClone(n.config);
    ids.add(n.id);
    return {
      id: n.id,
      type: n.type as NodeType,
      label: n.label,
      x: n.x,
      y: n.y,
      config,
      ...(template ? { template } : {}),
    };
  });
  const edgeIds = new Set<string>();
  const edges = value.edges.map((e): DesignEdge => {
    if (
      !object(e) ||
      typeof e.id !== 'string' ||
      !e.id ||
      edgeIds.has(e.id) ||
      typeof e.source !== 'string' ||
      typeof e.target !== 'string' ||
      !ids.has(e.source) ||
      !ids.has(e.target) ||
      typeof e.relation !== 'string'
    )
      return fail('invalid or dangling connection.');
    if (
      (e.field_id !== undefined || e.predicate !== undefined) &&
      (typeof e.field_id !== 'string' || typeof e.predicate !== 'string')
    )
      return fail('invalid semantic relationship.');
    edgeIds.add(e.id);
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      relation: e.relation,
      ...(e.field_id !== undefined
        ? { field_id: e.field_id as string, predicate: e.predicate as string }
        : {}),
    };
  });
  return { name: value.name, version: value.version, nodes, edges };
}
