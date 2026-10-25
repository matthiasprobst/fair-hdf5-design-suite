import type { Blueprint, Catalog } from '../types';
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
  if (source === 'fan' && target.endsWith('_sensor')) return 'instrumented_by';
  if (source.endsWith('_sensor') && target === 'daq') return 'acquired_by';
  if (source === 'daq' && target === 'process') return 'processed_by';
  if (source === 'process' && ['group', 'dataset'].includes(target)) return 'writes_to';
  if (source === 'metadata') return 'describes';
  return 'related_to';
}
