import { useCallback, useEffect, useRef, useState } from 'react';
import type { DragEvent, ChangeEvent } from 'react';
import { ReactFlowProvider, useReactFlow } from '@xyflow/react';
import { useStore } from 'zustand';
import {
  ArrowLeft, Bell, ChevronDown, CircleCheck, CircleHelp, CloudUpload, Code2, Download,
  FileCode2, FileJson2, GitBranch, LayoutGrid, LoaderCircle, Maximize2,
  RefreshCcw, Save, Search, Share2, ShieldCheck, SlidersHorizontal, Upload, X, ZoomIn, ZoomOut,
} from 'lucide-react';
import type { NodeType } from './types';
import { api, download, jsonFile } from './lib/api';
import { editorStore, useEditor } from './editor/store';
import { parseBlueprint, toBlueprint } from './editor/adapters';
import { artifacts, useEditorLifecycle } from './editor/lifecycle';
import Palette from './components/Palette';
import { EditorInspector } from './components/EditorInspector';
import { Canvas, CanvasErrorBoundary } from './components/Canvas';
import Artifacts from './components/Artifacts';
import Modal from './components/Modal';
import type { Dialog } from './components/Modal';
const initialPosition={x:80,y:100};

function Workbench(){
 const initialized=useEditor(s=>s.initialized);
 const name=useEditor(s=>s.name);
 const nodeCount=useEditor(s=>s.nodes.length), edgeCount=useEditor(s=>s.edges.length);
 const catalog=useEditor(s=>s.catalog);
 const {apiError,storageError,savedAt,recoveryRaw}=useEditorLifecycle();
 const artifactState=useStore(artifacts.store);
 const preview=artifactState.preview.status==='current'?artifactState.preview.data:null;
 const validation=artifactState.validation.status==='current'?artifactState.validation.data:null;
 const shacl=artifactState.shacl.status==='current'?artifactState.shacl.data||'':'';
 const [dialog,setDialog]=useState<Dialog>(null);
 const [notice,setNotice]=useState<{text:string;error:boolean}|null>(null);
 const [busy,setBusy]=useState('');
 const [inspectorOpen,setInspectorOpen]=useState(true);
 const [showMinimap,setShowMinimap]=useState(false);
 const [menu,setMenu]=useState<'project'|'help'|null>(null);
 const canvasRef=useRef<HTMLDivElement>(null);
 const importRef=useRef<HTMLInputElement>(null);
 const uploadRef=useRef<HTMLInputElement>(null);
 const flow=useReactFlow();
 const noticeTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const operation=useRef(0);
 const pending=useRef<AbortController|null>(null);
 const onNotice=useCallback((text:string,error=false)=>{
   if(noticeTimer.current)clearTimeout(noticeTimer.current);
   setNotice({text,error});noticeTimer.current=setTimeout(()=>setNotice(null),4500);
 },[]);
 useEffect(()=>{
   const unsubscribe=editorStore.subscribe((s,p)=>{if(s.semanticRevision!==p.semanticRevision){pending.current?.abort();operation.current++;setBusy('');}});
   return()=>{unsubscribe();pending.current?.abort();operation.current++;if(noticeTimer.current)clearTimeout(noticeTimer.current);};
 },[]);
 const showInspector=useCallback(()=>setInspectorOpen(true),[]);
 const addNode=useCallback((type:NodeType,x:number,y:number)=>{
   if(editorStore.getState().nodes.length>=250){onNotice('The blueprint limit is 250 blocks.',true);return;}
   editorStore.getState().addNode(type,x,y);setInspectorOpen(true);
 },[onNotice]);
 const onDrop=useCallback((event:DragEvent<HTMLDivElement>)=>{
   event.preventDefault();const type=event.dataTransfer.getData('application/x-fair-component')||event.dataTransfer.getData('text/plain');
   if(!Object.prototype.hasOwnProperty.call(catalog,type))return;
   const p=flow.screenToFlowPosition({x:event.clientX,y:event.clientY});addNode(type as NodeType,p.x-95,p.y-38);
 },[catalog,flow,addNode]);
 const execute=useCallback(async(label:string,fn:(signal:AbortSignal)=>Promise<void>)=>{
   pending.current?.abort();const controller=new AbortController();pending.current=controller;
   const token=++operation.current;setBusy(label);
   try{await fn(controller.signal);}catch(e){if(!controller.signal.aborted)onNotice(e instanceof Error?e.message:String(e),true);}
   finally{if(operation.current===token)setBusy('');}
 },[onNotice]);
 const exportHdf5=()=>void execute('hdf5',async()=>{const blob=await artifacts.hdf5();if(blob)download(blob,'experiment-template.h5');});
 const exportShacl=()=>void execute('shacl',async()=>{const text=await artifacts.shacl();if(text!==undefined)download(new Blob([text],{type:'text/turtle'}),'experiment.shacl.ttl');});
 const previewShacl=()=>void execute('shacl-preview',async()=>{if(await artifacts.shacl()!==undefined)setDialog('shacl');});
 const previewStructure=()=>void execute('preview',async()=>{if(await artifacts.preview())setDialog('structure');});
 const runValidation=(file?:File)=>void execute('validate',async()=>{const report=await artifacts.validation(file);if(report){setDialog('validation');onNotice(report.conforms?'Validation passed.':`${report.issue_count} validation issue(s) found.`,!report.conforms);}});
 const refresh=()=>void execute('refresh',async()=>{if(await artifacts.preview())onNotice('Blueprint analyzed.');});
 const importBlueprint=async(e:ChangeEvent<HTMLInputElement>)=>{
   const file=e.target.files?.[0];if(!file)return;e.target.value='';
   await execute('import',async signal=>{
     const content=parseBlueprint(JSON.parse(await file.text()),editorStore.getState().catalog);
     if(signal.aborted)return;
     editorStore.getState().replace(content);onNotice('Blueprint imported.');
   });
 };
 const reset=()=>void execute('reset',async signal=>{
   if(!window.confirm('Reset the current experiment to the demonstration blueprint?'))return;
   const content=parseBlueprint(await api.demo(signal),editorStore.getState().catalog);
   if(signal.aborted)return;
   editorStore.getState().replace(content);editorStore.getState().select('pressure');setMenu(null);onNotice('Demo experiment restored.');
 });
 const onSaveJson=()=>jsonFile(toBlueprint(editorStore.getState()),'experiment-blueprint.json');
 const onLoadFile=()=>importRef.current?.click();
 const exportRecovery=()=>{if(recoveryRaw!==null)download(new Blob([recoveryRaw],{type:'application/json'}),'original-draft.json');};
 const requestErrors=Object.values(artifactState).filter(a=>a.status==='failed').map(a=>a.error);
 if(apiError)return <main className="api-error"><h1>Python backend unavailable</h1><p>{apiError}</p><button onClick={()=>window.location.reload()}>Retry connection</button>{recoveryRaw!==null&&<button onClick={exportRecovery}>Export saved draft</button>}</main>;
 if(!initialized)return <div className="app-loading"><LoaderCircle className="spin" size={32}/><h2>Loading research data workspace</h2><p>Connecting to the Python backend…</p></div>;
 return <div className="app-shell">
   <header className="global-header">
     <div className="brand"><span className="brand-logo"><DatabaseIcon/></span><strong>FAIR Data Design Suite</strong></div>
     <nav className="global-nav" aria-label="Application navigation"><button onClick={()=>setDialog('projects')}>Projects</button><button onClick={()=>setDialog('templates')}>Templates</button><button onClick={()=>setDialog('profile')}>Metadata Profiles (MPS)</button><button onClick={()=>runValidation()}>Validation</button><button onClick={()=>setDialog('about')}>Help <ChevronDown size={13}/></button></nav>
     <div className="global-right"><div className="global-search"><Search size={17}/><span>Search projects, blocks, profiles...</span><kbd>⌘ K</kbd></div><button className="top-icon" onClick={()=>setDialog('about')} aria-label="Notifications"><Bell size={19}/><span/></button><div className="user-avatar">JD</div><span className="user-name">Researcher</span><ChevronDown size={13} color="#748097"/></div>
   </header>
   <div className="project-toolbar">
     <div className="project-ident"><button className="project-back" onClick={()=>setDialog('projects')} title="Projects"><ArrowLeft size={18}/></button><input aria-label="Experiment title" className="project-name" value={name==='Radial fan experiment'?'Fan Experiment – HDF5 Design':name} onChange={e=>editorStore.getState().rename(e.target.value)} /><span className="draft-tag">Draft</span><span className="saved-text"><CircleCheck size={13}/> {storageError?'Local save unavailable':savedAt}</span></div>
     <div className="toolbar-buttons">
       <div className="project-menu-wrap"><button className="secondary-btn action-small" onClick={()=>setMenu(m=>m==='project'?null:'project')}><FileJson2 size={15}/> Project <ChevronDown size={13}/></button>
         {menu==='project'&&<div className="project-dropdown"><button onClick={()=>{onSaveJson();setMenu(null);}}><Save size={15}/> Export blueprint JSON</button><button onClick={()=>{onLoadFile();setMenu(null);}}><Upload size={15}/> Import blueprint JSON</button>{recoveryRaw!==null&&<button onClick={()=>{exportRecovery();setMenu(null);}}><Save size={15}/> Export original draft</button>}<button onClick={()=>{reset();setMenu(null);}}><RefreshCcw size={15}/> Reset example</button><button onClick={()=>{uploadRef.current?.click();setMenu(null);}}><CloudUpload size={15}/> Validate existing .h5</button></div>}
       </div>
       <button className="secondary-btn share-btn" onClick={()=>setDialog('share')}><Share2 size={15}/> Share</button>
       <button className="validate-btn" disabled={!!busy} onClick={()=>runValidation()}><ShieldCheck size={16}/> Validate</button>
       <button className="primary-btn" disabled={!!busy} onClick={exportShacl}><Download size={16}/> Export SHACL</button>
       <button className="purple-btn" disabled={!!busy} onClick={exportHdf5}><FileCode2 size={16}/> Export HDF5 Template</button>
     </div>
   </div>
   {(storageError||requestErrors.length>0)&&<div className="editor-error" role="alert">{storageError&&<span>{storageError} {recoveryRaw!==null&&<button onClick={exportRecovery}>Export original draft</button>}</span>}{requestErrors.map((message,i)=><span key={i}>{message}</span>)}</div>}
   <div className="main-stage">
     <Palette catalog={catalog} onAdd={type=>{const bounds=canvasRef.current?.getBoundingClientRect();const p=bounds?flow.screenToFlowPosition({x:bounds.left+bounds.width*.48,y:bounds.top+bounds.height*.43}):initialPosition;addNode(type,p.x-80,p.y-35);}} />
     <section className="canvas-shell">
       <div className="canvas-heading"><div><h2>Target HDF5 Design</h2><span className="canvas-subheading"><span className="live-dot"/> {nodeCount} blocks · {edgeCount} connections</span></div>
         <div className="canvas-tools"><button onClick={()=>{flow.zoomOut({duration:200});}} title="Zoom out"><ZoomOut size={16}/></button><button onClick={()=>{flow.zoomIn({duration:200});}} title="Zoom in"><ZoomIn size={16}/></button><button onClick={()=>flow.fitView({padding:.12,duration:400,maxZoom:1})} title="Fit to view"><Maximize2 size={15}/></button><span className="tool-separator"/><button className={showMinimap?'tool-active':''} onClick={()=>setShowMinimap(v=>!v)} title="Toggle minimap"><LayoutGrid size={15}/></button><button onClick={previewStructure} title="HDF5 structure"><GitBranch size={15}/></button></div>
       </div>
       <div className="canvas-region" ref={canvasRef} onDrop={onDrop} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}}>
         <CanvasErrorBoundary><Canvas showMinimap={showMinimap} onSelection={showInspector}/></CanvasErrorBoundary>
         <div className="canvas-corner-note"><SlidersHorizontal size={13}/> Connect blocks using the round ports · Drag blocks from library</div>
       </div>
     </section>
     {inspectorOpen?<EditorInspector onClose={()=>setInspectorOpen(false)} onNotice={onNotice}/>:<button className="inspector-reopen" onClick={()=>setInspectorOpen(true)}><SlidersHorizontal size={16}/> Open inspector</button>}
   </div>
   <Artifacts previewStatus={artifactState.preview.status} validationStatus={artifactState.validation.status} preview={preview} validation={validation} busy={busy} onRefresh={refresh} onShaclPreview={previewShacl} onShaclDownload={exportShacl} onStructure={previewStructure} onHdf5Download={exportHdf5} onValidation={()=>runValidation()} onReport={()=>setDialog('validation')}/>
   <div className="statusbar"><span><CircleCheck size={12}/> Python API connected</span><span><Code2 size={12}/> Local illustrative metadata profiles · No live MPS connection</span><span>Research prototype 0.1.0-beta.1</span></div>
   <input type="file" accept=".json,application/json" hidden ref={importRef} onChange={e=>{void importBlueprint(e);}}/>
   <input type="file" accept=".h5,.hdf5,application/x-hdf5" hidden ref={uploadRef} onChange={e=>{const f=e.target.files?.[0];if(f)runValidation(f);e.target.value='';}}/>
   {notice&&<div className={`toast ${notice.error?'toast-error':''}`} role="status">{notice.error?<CircleHelp size={16}/>:<CircleCheck size={16}/>} {notice.text}<button onClick={()=>setNotice(null)}><X size={13}/></button></div>}
   {busy&&<div className="working-pill"><LoaderCircle className="spin" size={14}/> {busy==='validate'?'Validating model…':'Processing request…'}</div>}
   <Modal dialog={dialog} onClose={()=>setDialog(null)} preview={preview} ttl={shacl} validation={validation} name={name} onNotice={onNotice}/>
 </div>;
}
function DatabaseIcon(){return <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true"><ellipse cx="16" cy="7" rx="11" ry="4.6" stroke="currentColor" strokeWidth="2.4"/><path d="M5 7v8c0 2.6 5 4.7 11 4.7s11-2.1 11-4.7V7M5 15v9c0 2.6 5 4.5 11 4.5S27 26.6 27 24v-9" stroke="currentColor" strokeWidth="2.4"/><path d="M5 15c0 2.5 5 4.5 11 4.5s11-2 11-4.5" stroke="currentColor" strokeWidth="2.4"/></svg>}
export default function App(){return <ReactFlowProvider><Workbench/></ReactFlowProvider>}
