export type NodeType = string;
export type Value = string | number | boolean | null;
export type Config = Record<string, Value>;
export interface DesignNode { id: string; type: NodeType; label: string; x: number; y: number; config: Config; template?: CatalogItem }
export interface DesignEdge { id: string; source: string; target: string; relation: string }
export interface Blueprint { name: string; version: string; nodes: DesignNode[]; edges: DesignEdge[] }
export interface ProfileField {
  key: string; predicate: string; label: string; description?: string; datatype: string;
  required: boolean; order?: number; choices?: string[]; defaultValue?: string; hasValue?: string;
  minInclusive?: string; maxInclusive?: string; minExclusive?: string; maxExclusive?: string;
  minLength?: string; maxLength?: string; pattern?: string; flags?: string;
}
export interface CatalogItem {
  initial?: CatalogItem;
  id?: string; revision?: number; shape?: string; profile_ttl?: string; profile_hash?: string;
  mapping?: Record<string,string>; fields?: ProfileField[];
  label: string; category: string; icon: string; profile: string; kind: 'group'|'dataset'|null;
  color: string; required: string[]; defaults: Config;
}
export type Catalog = Record<string, CatalogItem>;
export interface PreviewObject { path: string; kind: 'group'|'dataset'; label: string; profile: string }
export interface Preview { objects: PreviewObject[]; profiles: number; node_count: number; edge_count: number }
export interface ValidationIssue { path: string; rule: string; message: string; layer: string }
export interface ValidationResult {
  conforms: boolean; checks: number; issue_count: number; issues: ValidationIssue[]; shacl_engine: string; note: string;
}
