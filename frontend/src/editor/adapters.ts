import { graphLimitError } from './limits';
import type { Capabilities } from './limits';
import { MarkerType } from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';
import type { Blueprint, Catalog, Config, DesignEdge, DesignNode, NodeType } from '../types';

export type ScientificData = { label: string; blockType: NodeType; config: Config };
export type ScientificFlowNode = Node<ScientificData, 'scientific'>;
export type ScientificFlowEdge = Edge<{ relation: string }>;
export type Graph = { name: string; version: string; nodes: ScientificFlowNode[]; edges: ScientificFlowEdge[] };
const relationColor: Record<string, string> = {instrumented_by:'#2777e9', acquired_by:'#2579e6', processed_by:'#e9a01e', writes_to:'#f19b14', describes:'#9864e5', related_to:'#6887a7'};

// Validate the storage/import envelope, not scientific constraints. Incomplete
// paths and metadata must remain editable even when the backend rejects them.
export function parseBlueprint(value: unknown, catalog: Catalog, limits?: Capabilities): Blueprint {
  const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
  const fail = (message: string): never => { throw new Error(`Invalid blueprint: ${message}`); };
  if (!object(value) || typeof value.name !== 'string' || typeof value.version !== 'string' || !Array.isArray(value.nodes) || !Array.isArray(value.edges)) return fail('expected name, version, nodes and edges.');
  if (limits) {
    const error = graphLimitError({nodes:value.nodes, edges:value.edges}, limits);
    if (error) return fail(error);
  }
  const ids = new Set<string>();
  const nodes = value.nodes.map((n): DesignNode => {
    if (!object(n) || typeof n.id !== 'string' || !/^[A-Za-z0-9_-]{1,90}$/.test(n.id) || ids.has(n.id)) return fail('node IDs must be valid and unique.');
    if (typeof n.type !== 'string' || !Object.prototype.hasOwnProperty.call(catalog, n.type) || typeof n.label !== 'string' || typeof n.x !== 'number' || !Number.isFinite(n.x) || typeof n.y !== 'number' || !Number.isFinite(n.y) || !object(n.config)) return fail(`invalid node ${n.id}.`);
    const config: Config = {};
    for (const [key, v] of Object.entries(n.config)) {
      if (!/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(key) || !(['string','boolean'].includes(typeof v) || v === null || (typeof v === 'number' && Number.isFinite(v)))) return fail(`unsupported metadata in ${n.id}.`);
      Object.defineProperty(config, key, { value: v, enumerable: true, writable: true, configurable: true });
    }
    ids.add(n.id);
    return { id:n.id, type:n.type as NodeType, label:n.label, x:n.x, y:n.y, config };
  });
  const edgeIds = new Set<string>();
  const edges = value.edges.map((e): DesignEdge => {
    if (!object(e) || typeof e.id !== 'string' || !e.id || edgeIds.has(e.id) || typeof e.source !== 'string' || typeof e.target !== 'string' || !ids.has(e.source) || !ids.has(e.target) || typeof e.relation !== 'string') return fail('invalid or dangling connection.');
    edgeIds.add(e.id);
    return { id:e.id, source:e.source, target:e.target, relation:e.relation };
  });
  return { name:value.name, version:value.version, nodes, edges };
}

export function fromNode(n: DesignNode): ScientificFlowNode {
  return { id:n.id, type:'scientific', position:{ x:n.x, y:n.y }, data:{ label:n.label, blockType:n.type, config:{...n.config} } };
}
export function fromEdge(e: DesignEdge): ScientificFlowEdge {
  const color = relationColor[e.relation] || '#618bad';
  return { id:e.id, source:e.source, target:e.target, sourceHandle:'out', targetHandle:'in', type:'smoothstep', animated:false,
    style:{stroke:color, strokeWidth:2.5}, markerEnd:{type:MarkerType.ArrowClosed, color, width:15, height:15}, data:{relation:e.relation} };
}
export function toNode(n: ScientificFlowNode): DesignNode {
  return { id:n.id, type:n.data.blockType, label:n.data.label, x:n.position.x, y:n.position.y, config:{...n.data.config} };
}
export function toEdge(e: ScientificFlowEdge): DesignEdge {
  return { id:e.id, source:e.source, target:e.target, relation:e.data!.relation };
}
export function fromBlueprint(blueprint: Blueprint): Graph {
  return { name:blueprint.name, version:blueprint.version, nodes:blueprint.nodes.map(fromNode), edges:blueprint.edges.map(fromEdge) };
}
export function toBlueprint(graph: Graph): Blueprint {
  return { name:graph.name, version:graph.version, nodes:graph.nodes.map(toNode), edges:graph.edges.map(toEdge) };
}
