export { parseBlueprint } from './blueprint';
import { MarkerType } from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';
import type { Blueprint, CatalogItem, Config, DesignEdge, DesignNode, NodeType } from '../types';

export type ScientificData = {
  label: string;
  blockType: NodeType;
  config: Config;
  template?: CatalogItem;
};
export type ScientificFlowNode = Node<ScientificData, 'scientific'>;
export type ScientificFlowEdge = Edge<{
  relation: string;
  field_id?: string;
  predicate?: string;
  kind?: 'data';
  column_index?: number;
}>;
export type Graph = {
  name: string;
  version: string;
  nodes: ScientificFlowNode[];
  edges: ScientificFlowEdge[];
};
const relationColor: Record<string, string> = {
  provides_data: '#16845e',
  instrumented_by: '#2777e9',
  acquired_by: '#2579e6',
  processed_by: '#e9a01e',
  writes_to: '#f19b14',
  describes: '#9864e5',
  related_to: '#6887a7',
};

export function fromNode(n: DesignNode): ScientificFlowNode {
  return {
    id: n.id,
    type: 'scientific',
    position: { x: n.x, y: n.y },
    data: {
      label: n.label,
      blockType: n.type,
      config: structuredClone(n.config),
      template: n.template ? structuredClone(n.template) : undefined,
    },
  };
}
export function fromEdge(e: DesignEdge): ScientificFlowEdge {
  const color = relationColor[e.relation] || '#618bad';
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.kind === 'data' ? 'data-out' : 'out',
    targetHandle: e.kind === 'data' ? 'data-in' : 'in',
    type: 'smoothstep',
    animated: false,
    style: { stroke: color, strokeWidth: 2.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 15, height: 15 },
    label:
      e.kind === 'data'
        ? `Column ${(e.column_index ?? 0) + 1}`
        : e.predicate
          ? e.relation
          : undefined,
    data: {
      relation: e.relation,
      field_id: e.field_id,
      predicate: e.predicate,
      kind: e.kind,
      column_index: e.column_index,
    },
  };
}
export function toNode(n: ScientificFlowNode): DesignNode {
  return {
    id: n.id,
    type: n.data.blockType,
    label: n.data.label,
    x: n.position.x,
    y: n.position.y,
    config: structuredClone(n.data.config),
    ...(n.data.template ? { template: structuredClone(n.data.template) } : {}),
  };
}
export function toEdge(e: ScientificFlowEdge): DesignEdge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    relation: e.data?.relation ?? 'related_to',
    ...(e.data?.kind === 'data'
      ? { kind: 'data' as const, column_index: e.data.column_index }
      : {}),
    ...(e.data?.field_id !== undefined
      ? { field_id: e.data.field_id, predicate: e.data.predicate }
      : {}),
  };
}
export function fromBlueprint(blueprint: Blueprint): Graph {
  return {
    name: blueprint.name,
    version: blueprint.version,
    nodes: blueprint.nodes.map(fromNode),
    edges: blueprint.edges.map(fromEdge),
  };
}
export function toBlueprint(graph: Graph): Blueprint {
  return {
    name: graph.name,
    version: graph.version,
    nodes: graph.nodes.map(toNode),
    edges: graph.edges.map(toEdge),
  };
}
