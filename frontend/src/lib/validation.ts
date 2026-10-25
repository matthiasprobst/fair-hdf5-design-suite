import type { CatalogItem, Config, ProfileField, TemplateSnapshot } from '../types';

export function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
export function isConfig(value: unknown): value is Config {
  const scalar = (item: unknown) =>
    typeof item === 'string' ||
    typeof item === 'boolean' ||
    (typeof item === 'number' && Number.isFinite(item));
  return (
    isRecord(value) &&
    Object.entries(value).every(
      ([key, item]) =>
        /^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(key) &&
        (item === null ||
          scalar(item) ||
          (Array.isArray(item) && item.every((v) => scalar(v) && typeof v === typeof item[0]))),
    )
  );
}
export function isProfileField(value: unknown): value is ProfileField {
  if (!isRecord(value)) return false;
  return (
    ['key', 'predicate', 'datatype', 'label'].every((key) => typeof value[key] === 'string') &&
    typeof value.required === 'boolean' &&
    (value.kind === undefined || value.kind === 'literal' || value.kind === 'reference') &&
    [
      'id',
      'targetShape',
      'description',
      'defaultValue',
      'hasValue',
      'minInclusive',
      'maxInclusive',
      'minExclusive',
      'maxExclusive',
      'minLength',
      'maxLength',
      'pattern',
      'flags',
    ].every((key) => value[key] === undefined || typeof value[key] === 'string') &&
    (value.multiple === undefined || typeof value.multiple === 'boolean') &&
    (value.minCount === undefined ||
      (typeof value.minCount === 'number' &&
        Number.isInteger(value.minCount) &&
        value.minCount >= 0)) &&
    (value.maxCount == null ||
      (typeof value.maxCount === 'number' &&
        Number.isInteger(value.maxCount) &&
        value.maxCount >= 0)) &&
    (value.choices === undefined ||
      (Array.isArray(value.choices) && value.choices.every((v) => typeof v === 'string')))
  );
}
export function isCatalogItem(value: unknown): value is CatalogItem {
  return (
    isRecord(value) &&
    ['label', 'category', 'icon', 'profile', 'color'].every(
      (key) => typeof value[key] === 'string',
    ) &&
    (value.kind === null || value.kind === 'group' || value.kind === 'dataset') &&
    isConfig(value.defaults) &&
    Array.isArray(value.required) &&
    value.required.every((v) => typeof v === 'string') &&
    (value.fields === undefined ||
      (Array.isArray(value.fields) && value.fields.every(isProfileField)))
  );
}
export function isTemplateSnapshot(value: unknown): value is TemplateSnapshot {
  return (
    isCatalogItem(value) &&
    typeof value.id === 'string' &&
    typeof value.revision === 'number' &&
    Number.isInteger(value.revision) &&
    value.revision > 0 &&
    typeof value.profile_ttl === 'string' &&
    typeof value.shape === 'string' &&
    Array.isArray(value.fields)
  );
}
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
