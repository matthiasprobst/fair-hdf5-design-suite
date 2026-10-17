import type { Capabilities } from './limits';
import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';
import { addEdge, applyEdgeChanges, applyNodeChanges } from '@xyflow/react';
import type { Connection, EdgeChange, NodeChange } from '@xyflow/react';
import type { Blueprint, Catalog, CatalogItem, Config, NodeType } from '../types';
import { makeId, suggestedRelation, uniquePath } from '../lib/api';
import { fromBlueprint, fromEdge, fromNode, toBlueprint, toEdge, toNode } from './adapters';
import type { Graph, ScientificFlowEdge, ScientificFlowNode } from './adapters';

export interface EditorState extends Graph {
  catalog: Catalog;
  setCatalog: (catalog: Catalog) => void;
  upgradeNode: (id: string, template: CatalogItem) => void;
  capabilities: Capabilities | null;
  setCapabilities: (capabilities: Capabilities) => void;
  initialized: boolean;
  semanticRevision: number;
  saveRevision: number;
  graphRevision: number;
  replace: (blueprint: Blueprint, catalog?: Catalog) => void;
  rename: (name: string) => void;
  onNodesChange: (changes: NodeChange<ScientificFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<ScientificFlowEdge>[]) => void;
  deleteElements: (nodes?: string[], edges?: string[]) => void;
  select: (id: string | null, edge?: boolean) => void;
  addNode: (type: NodeType, x: number, y: number) => void;
  duplicateNode: (id: string) => void;
  updateNode: (id: string, patch: {label?: string; config?: Config}) => void;
  updateEdge: (id: string, relation: string) => void;
  isValidConnection: (connection: Connection | ScientificFlowEdge) => boolean;
  connect: (connection: Connection) => void;
}
const changed = (s: EditorState) => ({semanticRevision:s.semanticRevision+1, saveRevision:s.saveRevision+1});
// All deletion entry points use this same idempotent reduction.
function remove(s: Pick<Graph, 'nodes'|'edges'>, nodeIds: string[], edgeIds: string[]) {
  const nodes = nodeIds.some(id=>s.nodes.some(n=>n.id===id)) ? s.nodes.filter(n=>!nodeIds.includes(n.id)) : s.nodes;
  const edges = s.edges.some(e=>edgeIds.includes(e.id)||nodeIds.includes(e.source)||nodeIds.includes(e.target))
    ? s.edges.filter(e=>!edgeIds.includes(e.id)&&!nodeIds.includes(e.source)&&!nodeIds.includes(e.target)) : s.edges;
  return {nodes, edges};
}
export function createEditorStore() {
  return createStore<EditorState>((set, get) => ({
    name:'', version:'0.1', nodes:[], edges:[], catalog:{}, capabilities:null, initialized:false, semanticRevision:0, saveRevision:0, graphRevision:0,
    setCatalog: catalog => set({catalog}),
    upgradeNode: (id, template) => set(s=>({nodes:s.nodes.map(n=>n.id===id?{...n,data:{...n.data,template,config:{...template.defaults,...n.data.config}}}:n),...changed(s)})),
    setCapabilities: capabilities => set({capabilities}),
    replace: (blueprint, catalog) => set(s=>({...fromBlueprint(blueprint), catalog:catalog??s.catalog, initialized:true, graphRevision:s.graphRevision+1, ...changed(s)})),
    rename: name => set(s=>name===s.name?s:{name,...changed(s)}),
    onNodesChange: changes => set(s=>{
      const removals = changes.filter(c=>c.type==='remove').map(c=>c.id);
      const pruned = remove(s, removals, []);
      const rest = changes.filter(c=>c.type!=='remove');
      const nodes = rest.length ? applyNodeChanges(rest, pruned.nodes) : pruned.nodes;
      const semantic = pruned.nodes!==s.nodes || rest.some(c=>c.type==='add'||c.type==='replace');
      // Drag-stop may carry only dragging:false. Keyboard moves have no dragging flag.
      const saveLayout = rest.some(c=>c.type==='position' && c.dragging!==true && (c.position || c.dragging===false));
      return {nodes, edges:pruned.edges, ...(semantic?changed(s):saveLayout?{saveRevision:s.saveRevision+1}:{})};
    }),
    onEdgesChange: changes => set(s=>{
      const pruned = remove(s, [], changes.filter(c=>c.type==='remove').map(c=>c.id));
      const rest = changes.filter(c=>c.type!=='remove');
      const edges = rest.length ? applyEdgeChanges(rest, pruned.edges) : pruned.edges;
      const semantic = pruned.edges!==s.edges || rest.some(c=>c.type==='add'||c.type==='replace');
      return {edges, ...(semantic?changed(s):{})};
    }),
    deleteElements: (nodeIds=[], edgeIds=[]) => set(s=>{
      const next=remove(s,nodeIds,edgeIds);
      return next.nodes===s.nodes&&next.edges===s.edges?s:{...next,...changed(s)};
    }),
    select: (id, edge=false) => set(s=>({
      nodes:s.nodes.some(n=>!!n.selected!==(!edge&&n.id===id)) ? s.nodes.map(n=>!!n.selected===(!edge&&n.id===id)?n:{...n,selected:!edge&&n.id===id}) : s.nodes,
      edges:s.edges.some(e=>!!e.selected!==(edge&&e.id===id)) ? s.edges.map(e=>!!e.selected===(edge&&e.id===id)?e:{...e,selected:edge&&e.id===id}) : s.edges,
    })),
    addNode: (type,x,y) => set(s=>{
      const info=s.catalog[type]; if(!info || (!s.capabilities || s.nodes.length>=s.capabilities.max_nodes) || !Number.isFinite(x)||!Number.isFinite(y))return s;
      const config={...info.defaults};
      if(info.kind&&config.path)config.path=uniquePath(String(config.path),toBlueprint(s));
      const node=fromNode({id:makeId(type,new Set(s.nodes.map(n=>n.id))),type,label:info.label,x,y,config,template:info});
      return {nodes:[...s.nodes.map(n=>n.selected?{...n,selected:false}:n),{...node,selected:true}],edges:s.edges.map(e=>e.selected?{...e,selected:false}:e),...changed(s)};
    }),
    duplicateNode: id => set(s=>{
      const original=s.nodes.find(n=>n.id===id);if(!original||(!s.capabilities || s.nodes.length>=s.capabilities.max_nodes))return s;
      const n=toNode(original);n.id=makeId(n.type,new Set(s.nodes.map(n=>n.id)));n.label+=' (copy)';n.x+=40;n.y+=85;
      if(n.config.path)n.config.path=uniquePath(String(n.config.path),toBlueprint(s));
      return {nodes:[...s.nodes.map(n=>n.selected?{...n,selected:false}:n),{...fromNode(n),selected:true}],edges:s.edges.map(e=>e.selected?{...e,selected:false}:e),...changed(s)};
    }),
    updateNode: (id,patch) => set(s=>{
      const node=s.nodes.find(n=>n.id===id);if(!node)return s;
      const config={...node.data.config};
      for(const [key,value] of Object.entries(patch.config??{})){if(value===null)delete config[key];else config[key]=value;}
      const label=patch.label??node.data.label;
      if(label===node.data.label&&JSON.stringify(config)===JSON.stringify(node.data.config))return s;
      return {nodes:s.nodes.map(n=>n===node?{...n,data:{...n.data,label,config}}:n),...changed(s)};
    }),
    updateEdge: (id,relation) => set(s=>{
      const edge=s.edges.find(e=>e.id===id);if(!edge||edge.data?.relation===relation)return s;
      return {edges:s.edges.map(e=>e===edge?{...e,...fromEdge({...toEdge(e),relation}),selected:e.selected}:e),...changed(s)};
    }),
    isValidConnection: c => {
      const s=get();return c.source!==c.target && c.sourceHandle==='out' && c.targetHandle==='in' && !!s.capabilities && s.edges.length<s.capabilities.max_edges && s.nodes.some(n=>n.id===c.source) && s.nodes.some(n=>n.id===c.target) && !s.edges.some(e=>e.source===c.source&&e.target===c.target);
    },
    connect: c => {
      if(!get().isValidConnection(c))return;
      set(s=>{
        const a=s.nodes.find(n=>n.id===c.source)!, b=s.nodes.find(n=>n.id===c.target)!;
        const edge=fromEdge({id:makeId('edge',new Set(s.edges.map(e=>e.id))),source:a.id,target:b.id,relation:suggestedRelation(a.data.blockType,b.data.blockType)});
        return {edges:addEdge(edge,s.edges),...changed(s)};
      });
    },
  }));
}
export type EditorStore = ReturnType<typeof createEditorStore>;
export const editorStore=createEditorStore();
export function useEditor<T>(selector: (state: EditorState) => T): T { return useStore(editorStore,selector); }
