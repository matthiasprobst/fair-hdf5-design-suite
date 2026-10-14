import type { Catalog } from '../types';
import { parseBlueprint, toBlueprint } from './adapters';
import type { EditorStore } from './store';

export const STORAGE_KEY='fair-hdf5-react-v2-blueprint';
export const RECOVERY_KEY=STORAGE_KEY+'-recovery';
export type StorageAccess = () => Pick<Storage, 'getItem'|'setItem'>;
export function readDraft(access: StorageAccess, catalog: Catalog) {
  let raw: string|null=null;
  try {
    raw=access().getItem(STORAGE_KEY);
    return {blueprint:raw===null?null:parseBlueprint(JSON.parse(raw),catalog),raw,error:''};
  } catch(e) { return {blueprint:null,raw,error:e instanceof Error?e.message:String(e)}; }
}
export function startPersistence(store: EditorStore, access: StorageAccess, report: (message: string, error: boolean)=>void, recoveryRaw: string|null=null, delay=330) {
  let timer: ReturnType<typeof setTimeout>|undefined;
  let dirty=false;
  const flush=(force=false)=>{
    clearTimeout(timer);
    if(!dirty || !store.getState().initialized || (!force && store.getState().nodes.some(n=>n.dragging)))return;
    try {
      const storage=access();
      // Never overwrite an unreadable draft until its exact bytes are archived.
      if(recoveryRaw!==null){storage.setItem(RECOVERY_KEY,recoveryRaw);recoveryRaw=null;}
      storage.setItem(STORAGE_KEY,JSON.stringify(toBlueprint(store.getState())));
      dirty=false;report('Saved locally '+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),false);
    } catch(e) { report(`Local save failed: ${e instanceof Error?e.message:String(e)}`,true); }
  };
  const unsubscribe=store.subscribe((s,previous)=>{
    if(s.saveRevision===previous.saveRevision){
      // Keep a mid-drag snapshot recoverable on pagehide, without scheduling IO.
      if(s.nodes!==previous.nodes && s.nodes.some((n,i)=>n.position!==previous.nodes[i]?.position))dirty=true;
      return;
    }
    dirty=true;report('Unsaved changes',false);clearTimeout(timer);
    timer=setTimeout(flush,delay);
  });
  return {flush, save:()=>{dirty=true;flush();}, stop:()=>{flush(true);clearTimeout(timer);unsubscribe();}};
}
