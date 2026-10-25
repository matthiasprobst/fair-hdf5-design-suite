import type { CatalogItem, Config, ProfileDocument, ProfileField, TemplateDraft } from '../types';

export interface LibraryDraft {
  mode: 'form' | 'turtle';
  label: string;
  category: string;
  kind: 'group' | 'dataset';
  path: string;
  dtype: string;
  dimensions: string;
  color: string;
  icon: string;
  shape: string;
  fields: ProfileField[];
  ttl: string;
  sourceUri: string;
  documents: Record<string, ProfileDocument>;
}

/** Build a transport draft without mutating the published revision's defaults. */
export function buildTemplateDraft(form: LibraryDraft, previous?: CatalogItem): TemplateDraft {
  const defaults: Config = {
    ...structuredClone(previous?.defaults ?? {}),
    path: form.path,
    ...(form.kind === 'dataset' ? { dtype: form.dtype, shape: form.dimensions } : {}),
  };
  for (const field of form.fields) {
    if (field.kind === 'reference') {
      delete defaults[field.key];
      continue;
    }
    const value = field.defaultValue ?? field.hasValue;
    if (field.multiple) {
      defaults[field.key] = value
        ? [value]
        : Array.isArray(defaults[field.key])
          ? defaults[field.key]
          : [];
    } else defaults[field.key] = value ?? defaults[field.key] ?? '';
  }
  return {
    label: form.label,
    category: form.category,
    kind: form.kind,
    color: form.color,
    icon: form.icon,
    shape: form.shape,
    profile: form.shape,
    defaults,
    mapping: Object.fromEntries(form.fields.map((field) => [field.predicate, field.key])),
    ...(previous?.requires_pyshacl ? { requires_pyshacl: true } : {}),
    ...(form.mode === 'turtle'
      ? {
          profile_ttl: form.ttl,
          documents: form.documents,
          source_uri: form.sourceUri || undefined,
        }
      : { fields: form.fields }),
  };
}
