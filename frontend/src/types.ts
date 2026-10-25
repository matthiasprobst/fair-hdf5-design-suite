export type NodeType = string;
export type ScalarValue = string | number | boolean;
export type Value = ScalarValue | ScalarValue[] | null;
export type Config = Record<string, Value>;
export interface DesignNode {
  id: string;
  type: NodeType;
  label: string;
  x: number;
  y: number;
  config: Config;
  template?: CatalogItem;
}
export interface DesignEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  field_id?: string;
  predicate?: string;
}
export interface Blueprint {
  name: string;
  version: string;
  nodes: DesignNode[];
  edges: DesignEdge[];
}
export interface ProfileDocument {
  ttl: string;
  hash?: string;
  resolved_url?: string;
}
export interface ProfileField {
  id?: string;
  kind?: 'literal' | 'reference';
  targetShape?: string;
  qualification?: 'all' | 'qualified';
  minCount?: number;
  maxCount?: number | null;
  multiple?: boolean;
  multiline?: boolean;
  labels?: Record<string, string>;
  descriptions?: Record<string, string>;
  class?: string;
  datatype_options?: string[];
  datatype_labels?: string[];
  key: string;
  predicate: string;
  label: string;
  description?: string;
  datatype: string;
  required: boolean;
  order?: number;
  choices?: string[];
  defaultValue?: string;
  hasValue?: string;
  minInclusive?: string;
  maxInclusive?: string;
  minExclusive?: string;
  maxExclusive?: string;
  minLength?: string;
  maxLength?: string;
  pattern?: string;
  flags?: string;
}
export interface CatalogItem {
  project_local?: boolean;
  initial?: CatalogItem;
  schema_version?: number;
  source_uri?: string;
  documents?: Record<string, ProfileDocument>;
  requires_pyshacl?: boolean;
  related_templates?: Record<string, CatalogItem>;
  target_classes?: string[];
  id?: string;
  revision?: number;
  shape?: string;
  profile_ttl?: string;
  profile_hash?: string;
  mapping?: Record<string, string>;
  fields?: ProfileField[];
  label: string;
  category: string;
  icon: string;
  profile: string;
  kind: 'group' | 'dataset' | null;
  color: string;
  required: string[];
  defaults: Config;
}
export type Catalog = Record<string, CatalogItem>;
export interface PreviewObject {
  path: string;
  kind: 'group' | 'dataset';
  label: string;
  profile: string;
}
export interface Preview {
  objects: PreviewObject[];
  profiles: number;
  node_count: number;
  edge_count: number;
}
export interface ValidationIssue {
  path: string;
  rule: string;
  message: string;
  layer: string;
}
export interface ValidationResult {
  conforms: boolean;
  checks: number;
  issue_count: number;
  issues: ValidationIssue[];
  shacl_engine: string;
  note: string;
}

/** A published, portable revision; legacy catalog entries may omit these fields. */
export interface TemplateSnapshot extends CatalogItem {
  id: string;
  revision: number;
  shape: string;
  profile_ttl: string;
  fields: ProfileField[];
}
export type TemplateDraft = Omit<
  Partial<TemplateSnapshot>,
  'id' | 'revision' | 'initial' | 'related_templates'
>;
export interface ProfileShapeAnalysis {
  shape: string;
  label: string;
  supported: boolean;
  fields?: ProfileField[];
  error?: string;
}
export interface ProfileAnalysis {
  source_uri?: string;
  documents: Record<string, ProfileDocument>;
  unbundled_imports?: string[];
  shapes: ProfileShapeAnalysis[];
}
