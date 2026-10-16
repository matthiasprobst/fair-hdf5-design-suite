import { graphLimitError } from './limits';
import { createStore } from 'zustand/vanilla';
import { api } from '../lib/api';
import type { Preview, ValidationResult } from '../types';
import { toBlueprint } from './adapters';
import type { EditorStore } from './store';

export type ArtifactStatus='idle'|'loading'|'current'|'stale'|'failed';
export type Artifact<T>={status:ArtifactStatus; data:T|null; error:string; revision:number};
type Results={preview:Preview; validation:ValidationResult; shacl:string; hdf5:Blob};
type State={ [K in keyof Results]: Artifact<Results[K]> };
const empty=<T>():Artifact<T>=>({status:'idle',data:null,error:'',revision:-1});
export function createArtifacts(editor: EditorStore, client=api, delay=330) {
  const store=createStore<State>(()=>({preview:empty(),validation:empty(),shacl:empty(),hdf5:empty()}));
  const controllers=new Map<keyof Results,AbortController>();
  let timer: ReturnType<typeof setTimeout>|undefined;
  const cancel=()=>{controllers.forEach(c=>c.abort());controllers.clear();clearTimeout(timer);};
  async function run<K extends keyof Results>(key:K, request:(signal:AbortSignal)=>Promise<Results[K]>):Promise<Results[K]|undefined> {
    controllers.get(key)?.abort();
    const controller=new AbortController();controllers.set(key,controller);
    const revision=editor.getState().semanticRevision;
    store.setState({[key]:{...store.getState()[key],status:'loading',error:'',revision}});
    const current=()=>!controller.signal.aborted && controllers.get(key)===controller && editor.getState().semanticRevision===revision;
    try {
      const state=editor.getState();
      const limitError=graphLimitError(state,state.capabilities);
      if(limitError)throw new Error(limitError);
      const data=await request(controller.signal);
      if(!current())return;
      store.setState({[key]:{status:'current',data,error:'',revision}});
      return data;
    } catch(e) {
      if(!current())return;
      store.setState({[key]:{...store.getState()[key],status:'failed',error:e instanceof Error?e.message:String(e),revision}});
    } finally {if(controllers.get(key)===controller)controllers.delete(key);}
  }
  const preview=()=>{clearTimeout(timer);const blueprint=toBlueprint(editor.getState());return run('preview',signal=>client.preview(blueprint,signal));};
  const validation=(file?:File)=>{const blueprint=toBlueprint(editor.getState());return run('validation',async signal=>{
    const limits=editor.getState().capabilities;
    if(file && limits && file.size>limits.max_upload_bytes)throw new Error(`Validation upload limit is ${limits.max_upload_bytes} bytes.`);
    return file?client.validateFile(blueprint,file,signal):client.validateTemplate(blueprint,signal);
  });};
  const shacl=()=>{const blueprint=toBlueprint(editor.getState());return run('shacl',async signal=>(await client.shacl(blueprint,signal)).text());};
  const hdf5=()=>{const blueprint=toBlueprint(editor.getState());return run('hdf5',signal=>client.hdf5(blueprint,signal));};
  const start=()=>{
    const schedule=()=>{if(editor.getState().initialized)timer=setTimeout(()=>{void preview();},delay);};
    const unsubscribe=editor.subscribe((s,previous)=>{
      if(s.semanticRevision===previous.semanticRevision)return;
      cancel();
      const next={} as State;
      for(const key of Object.keys(store.getState()) as (keyof Results)[]) {
        const old=store.getState()[key];
        Object.assign(next,{[key]:{...old,status:old.status==='idle'?'idle':'stale',error:''}});
      }
      store.setState(next);schedule();
    });
    schedule();
    return ()=>{unsubscribe();cancel();};
  };
  return {store,start,preview,validation,shacl,hdf5};
}
