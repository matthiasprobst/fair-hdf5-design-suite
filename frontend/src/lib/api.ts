import { parseCapabilities } from '../editor/limits';
import type { Blueprint, Catalog, CatalogItem, ProfileField, Preview, ValidationResult } from '../types';
async function checked(res: Response): Promise<Response> {
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status})`;
    try { const body = await res.json() as {detail?: string}; if (body.detail) message = body.detail; } catch { /* no JSON */ }
    throw new Error(message);
  }
  return res;
}
async function postJson<T>(url: string, design: unknown, signal?: AbortSignal): Promise<T> {
  const res = await checked(await fetch(url, {signal, method: 'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify(design)}));
  return res.json() as Promise<T>;
}
async function postBlob(url: string, design: Blueprint, signal?: AbortSignal): Promise<Blob> {
  return (await checked(await fetch(url, {signal, method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(design)}))).blob();
}
export interface ProfileAnalysis { shapes: {shape:string;label:string;supported:boolean;fields?:ProfileField[];error?:string}[] }
export const api = {
  analyzeProfile: (ttl:string) => postJson<ProfileAnalysis>('/api/catalog/analyze',{ttl}),
  saveTemplate: (template:Partial<CatalogItem>, id?:string, revision?:number) => postJson<CatalogItem>(id?`/api/catalog/${encodeURIComponent(id)}/revisions`:'/api/catalog',id?{expected_revision:revision,template}:template),
  capabilities: async (signal?: AbortSignal) => parseCapabilities(await (await checked(await fetch('/api/capabilities', {signal}))).json()),
  catalog: async (signal?: AbortSignal): Promise<{catalog:Catalog;profile_source:string}> => {
    const result = await (await checked(await fetch('/api/catalog', {signal}))).json() as {catalog:Catalog;legacy_catalog?:Catalog;profile_source:string};
    for (const [id, item] of Object.entries(result.catalog)) if (item.revision !== 1 && result.legacy_catalog?.[id]) item.initial=result.legacy_catalog[id];
    return result;
  },
  demo: async (signal?: AbortSignal): Promise<Blueprint> => (await checked(await fetch('/api/demo', {signal}))).json(),
  preview: (design:Blueprint, signal?: AbortSignal) => postJson<Preview>('/api/preview',design,signal),
  shacl: (design:Blueprint, signal?: AbortSignal) => postBlob('/api/export/shacl',design,signal),
  hdf5: (design:Blueprint, signal?: AbortSignal) => postBlob('/api/export/hdf5',design,signal),
  validateTemplate: (design:Blueprint, signal?: AbortSignal) => postJson<ValidationResult>('/api/validate/template',design,signal),
  validateFile: async (design: Blueprint, file: File, signal?: AbortSignal): Promise<ValidationResult> => {
    const data = new FormData(); data.append('design_json', JSON.stringify(design)); data.append('file',file);
    return (await checked(await fetch('/api/validate/file',{signal,method:'POST',body:data}))).json();
  },
};
export function download(blob:Blob,filename:string):void {
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=filename;
  document.body.append(a); a.click(); a.remove(); window.setTimeout(()=>URL.revokeObjectURL(url),60000);
}
export function jsonFile(obj:unknown, filename:string):void { download(new Blob([JSON.stringify(obj,null,2)],{type:'application/json'}),filename); }
export function makeId(type:string, existing:Set<string>):string {
  let id=''; do { id=type+'_'+Math.random().toString(36).slice(2,9); } while(existing.has(id)); return id;
}
export function uniquePath(path:string,design:Blueprint):string {
  const others=new Set(design.nodes.map(n=>String(n.config.path||'')));
  if (!others.has(path)) return path;
  let i=2; while(others.has(`${path}_${i}`))i++; return `${path}_${i}`;
}
export function requiredFields(type:string,config:Record<string,unknown>,catalog:Catalog):string[] {
  return [...new Set([...(catalog[type]?.required||[]), ...String(config.required_fields||'').split(',').map(x=>x.trim()).filter(Boolean)])];
}
export const relations = ['instrumented_by','acquired_by','processed_by','writes_to','describes','related_to'];
export function suggestedRelation(source:string,target:string):string {
 if(source==='fan'&&target.endsWith('_sensor'))return 'instrumented_by';
 if(source.endsWith('_sensor')&&target==='daq')return 'acquired_by';
 if(source==='daq'&&target==='process')return 'processed_by';
 if(source==='process'&&['group','dataset'].includes(target))return 'writes_to';
 if(source==='metadata')return 'describes';
 return 'related_to';
}
