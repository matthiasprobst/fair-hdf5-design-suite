import type { Blueprint, Catalog } from '../types';
import { CSV_SOURCE } from './dataNodes';
export function makeId(type: string, existing: Set<string>): string {
  let id: string;
  do {
    id = type + '_' + Math.random().toString(36).slice(2, 9);
  } while (existing.has(id));
  return id;
}
export function uniquePath(path: string, design: Blueprint): string {
  const others = new Set(design.nodes.map((n) => String(n.config.path || '')));
  if (!others.has(path)) return path;
  let i = 2;
  while (others.has(`${path}_${i}`)) i++;
  return `${path}_${i}`;
}
export function requiredFields(
  type: string,
  config: Record<string, unknown>,
  catalog: Catalog,
): string[] {
  return [
    ...new Set([
      ...(catalog[type]?.required || []),
      ...String(config.required_fields || '')
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean),
    ]),
  ];
}
export const relations = [
  'instrumented_by',
  'acquired_by',
  'processed_by',
  'writes_to',
  'describes',
  'related_to',
];
export function suggestedRelation(source: string, target: string): string {
  if (source === 'metadata') return 'describes';
  if (target === CSV_SOURCE && source !== CSV_SOURCE) return 'generated';
  if (source === CSV_SOURCE && target === 'daq') return 'was_generated_by';
  if (source === CSV_SOURCE && target === 'dataset') return 'writes_to';
  if (source === CSV_SOURCE && target === 'process') return 'processed_by';
  if (source === 'fan' && target.endsWith('_sensor')) return 'instrumented_by';
  if (source.endsWith('_sensor') && target === 'daq') return 'acquired_by';
  if (source === 'daq' && target === 'process') return 'processed_by';
  if (source === 'process' && ['group', 'dataset'].includes(target)) return 'writes_to';
  return 'related_to';
}

export function relationshipOptions(source: string, target: string): string[] {
  return [
    ...relations,
    ...(target === CSV_SOURCE ? ['generated'] : []),
    ...(source === CSV_SOURCE ? ['was_generated_by'] : []),
  ];
}

export function validRelationship(source: string, target: string, relation: string): boolean {
  if (source !== CSV_SOURCE && target !== CSV_SOURCE) return true;
  return (
    !(relation === 'generated' && target !== CSV_SOURCE) &&
    !(relation === 'was_generated_by' && source !== CSV_SOURCE)
  );
}
