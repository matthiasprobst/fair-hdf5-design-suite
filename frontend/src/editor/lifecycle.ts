import { demoWithinLimits } from './limits';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { parseBlueprint } from './adapters';
import { editorStore } from './store';
import { createArtifacts } from './artifacts';
import { readDraft, startPersistence, STORAGE_KEY, RECOVERY_KEY } from './persistence';

export const artifacts=createArtifacts(editorStore);
export function useEditorLifecycle() {
  const [apiError,setApiError]=useState('');
  const [storageError,setStorageError]=useState('');
  const [savedAt,setSavedAt]=useState('');
  const [recoveryRaw,setRecoveryRaw]=useState<string|null>(null);
  useEffect(()=>{
    const controller=new AbortController();
    let persistence:ReturnType<typeof startPersistence>|undefined;
    const stopArtifacts=artifacts.start();
    const flush=()=>persistence?.flush(true);
    const visibility=()=>{if(document.visibilityState==='hidden')flush();};
    window.addEventListener('pagehide',flush);document.addEventListener('visibilitychange',visibility);
    void (async()=>{
      try {
        // Read before the API request so recovery remains available if startup fails.
        try {setRecoveryRaw(localStorage.getItem(STORAGE_KEY));}catch(e){setStorageError(`Local storage unavailable: ${String(e)}`);}
        const [{catalog}, capabilities]=await Promise.all([api.catalog(controller.signal), api.capabilities(controller.signal)]);
        if(controller.signal.aborted)return;
        const draft=readDraft(()=>localStorage,catalog);
        let blueprint=draft.blueprint;
        if(!draft.error){
          try {setRecoveryRaw(localStorage.getItem(RECOVERY_KEY));}catch { /* existing storage error is shown below */ }
        }
        if(draft.error) {
          setStorageError(`Saved draft could not be loaded: ${draft.error}. Its original contents are preserved.`);
          blueprint={name:'Recovered workspace',version:'0.1',nodes:[],edges:[]};
        }
        if(!blueprint)blueprint=demoWithinLimits(parseBlueprint(await api.demo(controller.signal),catalog),capabilities);
        if(controller.signal.aborted)return;
        editorStore.getState().setCapabilities(capabilities);
        editorStore.getState().replace(blueprint,catalog);
        if(blueprint.nodes.some(n=>n.id==='pressure'))editorStore.getState().select('pressure');
        setApiError('');setSavedAt(draft.blueprint?'Restored draft':'Not saved yet');
        persistence=startPersistence(editorStore,()=>{
          // If reading failed, never overwrite an unknown saved draft.
          if(draft.error && draft.raw===null)throw new Error('Cannot safely save because the existing draft could not be read. Export JSON to preserve your work.');
          return localStorage;
        },(message,error)=>{
          if(error)setStorageError(message);
          else {setSavedAt(message);if(message!=='Unsaved changes')setStorageError('');}
        },draft.error?draft.raw:null);
        if(!draft.blueprint && !draft.error)persistence.save();
      } catch(e) {if(!controller.signal.aborted)setApiError(e instanceof Error?e.message:String(e));}
    })();
    return ()=>{controller.abort();stopArtifacts();persistence?.stop();window.removeEventListener('pagehide',flush);document.removeEventListener('visibilitychange',visibility);};
  },[]);
  return {apiError,storageError,savedAt,recoveryRaw};
}
