export type NodeType = 'fan'|'pressure_sensor'|'temperature_sensor'|'torque_sensor'|'flow_sensor'|'daq'|'process'|'group'|'dataset'|'metadata'|'experiment_setup'|'boundary_condition'|'vibration_sensor'|'custom_sensor'|'controller'|'power_supply'|'data_processor'|'data_processing'|'filter_process'|'unit_conversion'|'custom_process';
export type Value = string | number | boolean | null;
export type Config = Record<string, Value>;
export interface DesignNode { id: string; type: NodeType; label: string; x: number; y: number; config: Config }
export interface DesignEdge { id: string; source: string; target: string; relation: string }
export interface Blueprint { name: string; version: string; nodes: DesignNode[]; edges: DesignEdge[] }
export interface CatalogItem {
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
