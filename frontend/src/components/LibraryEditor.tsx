import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Plus, Trash2, X } from 'lucide-react';
import type { CatalogItem, Config, ProfileField } from '../types';
import { api } from '../lib/api';
import type { ProfileAnalysis } from '../lib/api';
import { editorStore } from '../editor/store';

const XSD = 'http://www.w3.org/2001/XMLSchema#';
const datatypes = ['string','boolean','integer','decimal','double','date','dateTime','IRI'];
const freshField = (): ProfileField => ({key:'',predicate:'',label:'',datatype:XSD+'string',required:false});
export default function LibraryEditor({template,onClose}:{template?:CatalogItem;onClose:()=>void}) {
  const [mode,setMode] = useState<'form'|'turtle'>(template?'turtle':'form');
  const [label,setLabel] = useState(template?.label || '');
  const [category,setCategory] = useState(template?.category || 'Metadata');
  const [kind,setKind] = useState<'group'|'dataset'>(template?.kind || 'group');
  const [path,setPath] = useState(String(template?.defaults.path || '/experiment/custom'));
  const [dtype,setDtype] = useState(String(template?.defaults.dtype || 'float64'));
  const [dimensions,setDimensions] = useState(String(template?.defaults.shape || '0'));
  const [color,setColor] = useState(template?.color || 'blue');
  const [icon,setIcon] = useState(template?.icon || 'metadata');
  const [shape,setShape] = useState(()=>template?.shape || `urn:fair-hdf5:profile:${crypto.randomUUID()}`);
  const [ttl,setTtl] = useState(template?.profile_ttl || '');
  const [fields,setFields] = useState<ProfileField[]>(()=>template?.fields?.map(f=>({...f,defaultValue:String(template.defaults[f.key]??f.defaultValue??'')})) || []);
  const [analysis,setAnalysis] = useState<ProfileAnalysis|null>(null);
  const [analyzed,setAnalyzed] = useState(!!template);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const updateField = (index:number, patch:Partial<ProfileField>) => setFields(fs=>fs.map((f,i)=>i===index?{...f,...patch}:f));
  const analyze = async () => {
    setBusy(true);setError('');setAnalyzed(false);
    try {
      const result=await api.analyzeProfile(ttl);setAnalysis(result);
      const selected=result.shapes.find(s=>s.shape===shape&&s.supported)||result.shapes.find(s=>s.supported);
      if(selected){setShape(selected.shape);setFields((selected.fields||[]).map(f=>({...f,key:template?.mapping?.[f.predicate]||f.key})));setAnalyzed(true);}
      else setError('This file has no supported flat profile. See the explanations below.');
    } catch(e){setError(e instanceof Error?e.message:String(e));} finally {setBusy(false);}
  };
  const save = async () => {
    setError('');setBusy(true);
    try {
      const defaults: Config = {...template?.defaults,path,...(kind==='dataset'?{dtype,shape:dimensions}:{})};
      for(const f of fields) defaults[f.key]=f.defaultValue ?? f.hasValue ?? defaults[f.key] ?? '';
      const draft:Partial<CatalogItem>={label,category,kind,color,icon,shape,profile:shape,defaults,mapping:Object.fromEntries(fields.map(f=>[f.predicate,f.key]))};
      if(mode==='turtle') draft.profile_ttl=ttl; else draft.fields=fields;
      const saved=await api.saveTemplate(draft,template?.id,template?.revision);
      editorStore.getState().setCatalog({...editorStore.getState().catalog,[saved.id!]:{...saved,initial:template?.initial || (template?.revision===1?template:undefined)}});
      onClose();
    } catch(e){setError(e instanceof Error?e.message:String(e));} finally{setBusy(false);}
  };
  return <Dialog.Root open onOpenChange={open=>{if(!open&&!busy)onClose();}}>
    <Dialog.Portal><Dialog.Overlay className="library-overlay"/><Dialog.Content className="library-dialog">
      <div className="modal-head"><div><Dialog.Title>{template?`Edit ${template.label}`:'Create library template'}</Dialog.Title>
        <Dialog.Description>{template?`Saving creates revision ${(template.revision||1)+1}. Existing nodes keep their current revision.`:'Create a reusable template or import a SHACL Turtle file.'}</Dialog.Description></div>
        <Dialog.Close disabled={busy} className="icon-button" aria-label="Close template editor"><X size={20}/></Dialog.Close>
      </div>
      <fieldset className="library-editor-body" disabled={busy}>
        {!template&&<div className="library-mode"><button aria-pressed={mode==='form'} onClick={()=>setMode('form')}>Form editor</button><button aria-pressed={mode==='turtle'} onClick={()=>setMode('turtle')}>SHACL Turtle import</button></div>}
        <div className="library-grid">
          <label>Template name<input value={label} onChange={e=>setLabel(e.target.value)}/></label>
          <label>Category<input value={category} onChange={e=>setCategory(e.target.value)}/></label>
          <label>HDF5 object<select value={kind} onChange={e=>setKind(e.target.value as 'group'|'dataset')}><option value="group">Group</option><option value="dataset">Dataset</option></select></label>
          <label>Default HDF5 path<input value={path} onChange={e=>setPath(e.target.value)}/></label>
          <label>Color<select value={color} onChange={e=>setColor(e.target.value)}>{['blue','green','purple','orange','amber','coral','rose','violet'].map(c=><option key={c}>{c}</option>)}</select></label>
          <label>Icon<select value={icon} onChange={e=>setIcon(e.target.value)}>{Array.from(new Set([icon,'metadata','group','dataset','custom_sensor','process','experiment_setup'])).map(i=><option key={i}>{i}</option>)}</select></label>
          {kind==='dataset'&&<><label>Dataset datatype<select value={dtype} onChange={e=>setDtype(e.target.value)}>{['float64','float32','int64','int32','uint16','uint8'].map(d=><option key={d}>{d}</option>)}</select></label><label>Dataset dimensions<input value={dimensions} onChange={e=>setDimensions(e.target.value)}/></label></>}
        </div>
        {mode==='turtle'?<section>
          <label>Import .ttl file<input type="file" accept=".ttl,text/turtle" disabled={busy} onChange={async e=>{const file=e.target.files?.[0];if(!file)return;if(file.size>1_000_000){setError('Profile limit is 1 MB.');return;}try{setTtl(await file.text());setAnalyzed(false);setAnalysis(null);}catch{setError('Cannot read this file.');}}}/></label>
          <label>Turtle source<textarea className="library-turtle" value={ttl} onChange={e=>{setTtl(e.target.value);setAnalyzed(false);setAnalysis(null);}} spellCheck={false}/></label>
          <button onClick={()=>void analyze()} disabled={busy||!ttl.trim()}>Analyze profile</button>
          {analysis&&<div className="library-analysis">{analysis.shapes.map(s=><div key={s.shape}><label><input type="radio" name="profile-shape" checked={shape===s.shape&&s.supported} disabled={!s.supported} onChange={()=>{setShape(s.shape);setFields(s.fields||[]);setAnalyzed(true);}}/>{s.label}</label>{s.error&&<p role="status">{s.error}</p>}</div>)}</div>}
          <p className="muted-small">One scalar value per field. Nested profiles, lists and SPARQL rules are not supported.</p>
        </section>:<label>Profile shape IRI<input value={shape} onChange={e=>setShape(e.target.value)}/></label>}
        {(mode==='form'||analyzed)&&<section><h3>Fields and HDF5 attribute mapping</h3>
          {fields.map((field,index)=><fieldset className="library-field" key={index}>
            <legend>{field.label||`Field ${index+1}`}</legend>
            <div className="library-grid">
              <label>HDF5 attribute<input value={field.key} onChange={e=>updateField(index,{key:e.target.value})}/></label>
              <label>Label<input value={field.label} readOnly={mode==='turtle'} onChange={e=>updateField(index,{label:e.target.value})}/></label>
              <label className="library-wide">Property IRI<input value={field.predicate} readOnly={mode==='turtle'} onChange={e=>updateField(index,{predicate:e.target.value})}/></label>
              <label>Datatype<select value={field.datatype.replace(XSD,'')} disabled={mode==='turtle'} onChange={e=>updateField(index,{datatype:e.target.value==='IRI'?'IRI':XSD+e.target.value})}>{datatypes.map(d=><option key={d}>{d}</option>)}</select></label>
              <label>Default value<input value={field.defaultValue??''} onChange={e=>updateField(index,{defaultValue:e.target.value})}/></label>
              <label><input type="checkbox" checked={field.required} disabled={mode==='turtle'} onChange={e=>updateField(index,{required:e.target.checked})}/> Required</label>
            </div>
            {mode==='form'?<details><summary>Constraints and description</summary><div className="library-grid">
              <label>Description<input value={field.description||''} onChange={e=>updateField(index,{description:e.target.value})}/></label>
              <label>Choices (one per line)<textarea value={field.choices?.join('\n')||''} onChange={e=>updateField(index,{choices:e.target.value.split('\n').filter(Boolean)})}/></label>
              {(['hasValue','minInclusive','maxInclusive','minExclusive','maxExclusive','minLength','maxLength','pattern','flags'] as const).map(k=><label key={k}>{k}<input value={field[k]||''} onChange={e=>updateField(index,{[k]:e.target.value})}/></label>)}
            </div></details>:<p className="muted-small">{field.description} {field.choices&&`Choices: ${field.choices.join(', ')}`} {field.pattern&&`Pattern: ${field.pattern}`} {field.minInclusive&&`Minimum: ${field.minInclusive}`} {field.maxInclusive&&`Maximum: ${field.maxInclusive}`}</p>}
            {mode==='form'&&<button aria-label={`Remove field ${index+1}`} onClick={()=>setFields(fs=>fs.filter((_,i)=>i!==index))}><Trash2 size={14}/> Remove field</button>}
          </fieldset>)}
          {mode==='form'&&<button onClick={()=>setFields(fs=>[...fs,freshField()])}><Plus size={14}/> Add field</button>}
        </section>}
        {error&&<p className="library-error" role="alert">{error}</p>}
      </fieldset>
      <footer className="modal-footer"><button disabled={busy} onClick={onClose}>Cancel</button><button disabled={busy||!label.trim()||!category.trim()||(mode==='turtle'&&!analyzed)} onClick={()=>void save()}>{busy?'Processing…':template?'Publish new revision':'Save to library'}</button></footer>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
