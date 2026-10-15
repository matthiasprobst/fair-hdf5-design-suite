import test from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as wait } from 'node:timers/promises';
import { createEditorStore } from '../src/editor/store';
import { fromBlueprint, parseBlueprint, toBlueprint } from '../src/editor/adapters';
import { createArtifacts } from '../src/editor/artifacts';
import { readDraft, startPersistence, STORAGE_KEY, RECOVERY_KEY } from '../src/editor/persistence';
import { api } from '../src/lib/api';
import type { Blueprint, Catalog, Preview, ValidationResult } from '../src/types';
const catalog:Catalog={fan:{label:'Fan',category:'Experiment',icon:'fan',profile:'fan',kind:'group',color:'purple',required:[],defaults:{path:'/fan'}},pressure_sensor:{label:'Sensor',category:'Sensor',icon:'sensor',profile:'sensor',kind:'dataset',color:'blue',required:[],defaults:{path:'/sensor'}}};
const blueprint:Blueprint={name:'Experiment',version:'0.1',nodes:[{id:'a',type:'fan',label:'Fan',x:10.25,y:-5.75,config:{path:'/fan',speed:2,active:true,empty:null}},{id:'b',type:'pressure_sensor',label:'Sensor',x:400,y:100,config:{path:'/sensor'}}],edges:[]};
const connection={source:'a',target:'b',sourceHandle:'out',targetHandle:'in'};
const report:ValidationResult={conforms:true,checks:4,issue_count:0,issues:[],shacl_engine:'test',note:''};
const preview:Preview={objects:[],profiles:2,node_count:2,edge_count:0};
function editor(){const store=createEditorStore();store.getState().replace(blueprint,catalog);return store;}
function memory(raw:string|null=null){const values=new Map<string,string>();if(raw!==null)values.set(STORAGE_KEY,raw);let writes=0;return {values,get writes(){return writes;},getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{writes++;values.set(key,value);}};}
function deferred<T>(){let resolve!:(v:T)=>void;let reject!:(e:Error)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}

test('complete change stream keeps dimensions, fractions, selection and unaffected identity',()=>{
 const s=editor(), originalB=s.getState().nodes[1], revision=s.getState().semanticRevision, save=s.getState().saveRevision;
 s.getState().onNodesChange([{id:'a',type:'dimensions',dimensions:{width:220,height:175}},{id:'a',type:'select',selected:true}]);
 assert.deepEqual(s.getState().nodes[0].measured,{width:220,height:175});assert.equal(s.getState().nodes[0].selected,true);
 assert.equal(s.getState().saveRevision,save);
 s.getState().onNodesChange([{id:'a',type:'position',position:{x:52.375,y:-12.125},dragging:true}]);
 assert.deepEqual(s.getState().nodes[0].position,{x:52.375,y:-12.125});assert.equal(s.getState().nodes[0].dragging,true);assert.equal(s.getState().saveRevision,save);
 s.getState().onNodesChange([{id:'a',type:'position',dragging:false}]);
 assert.equal(s.getState().nodes[0].dragging,false);assert.equal(s.getState().saveRevision,save+1);
 assert.equal(s.getState().semanticRevision,revision);assert.equal(s.getState().nodes[1],originalB);
 s.getState().updateNode('a',{label:'Changed'});
 assert.deepEqual(s.getState().nodes[0].measured,{width:220,height:175});assert.equal(s.getState().nodes[1],originalB);
});
test('connections reject invalid handles, endpoints, self and duplicates without mutating state',()=>{
 const s=editor(),nodes=s.getState().nodes;
 for(const c of [{...connection,target:'missing'},{...connection,target:'a'},{...connection,sourceHandle:null},{...connection,targetHandle:'out'}]) {const before=s.getState();s.getState().connect(c);assert.equal(s.getState(),before);}
 s.getState().connect(connection);assert.equal(s.getState().nodes,nodes);assert.equal(s.getState().edges[0].data?.relation,'instrumented_by');
 const before=s.getState();s.getState().connect(connection);assert.equal(s.getState(),before);
 const id=s.getState().edges[0].id;s.getState().onEdgesChange([{id,type:'select',selected:true}]);assert.equal(s.getState().semanticRevision,before.semanticRevision);assert.equal(s.getState().nodes,nodes);
 s.getState().updateEdge(id,'related_to');assert.equal(s.getState().nodes,nodes);assert.equal(s.getState().edges[0].selected,true);
 s.getState().deleteElements([],[id]);assert.equal(s.getState().nodes,nodes);assert.equal(s.getState().edges.length,0);
});
test('deletion is idempotent and removes incident edges and inspector selection',()=>{
 const s=editor();s.getState().connect(connection);s.getState().select('a');
 s.getState().onNodesChange([{id:'a',type:'remove'}]);const revision=s.getState().semanticRevision;
 assert.equal(s.getState().nodes.length,1);assert.equal(s.getState().edges.length,0);assert.equal(s.getState().nodes.find(n=>n.selected),undefined);
 s.getState().deleteElements(['a']);s.getState().onEdgesChange([{id:'missing',type:'remove'}]);assert.equal(s.getState().semanticRevision,revision);
});
test('adapters round-trip domain fields only and do not alias configuration',()=>{
 const graph=fromBlueprint(blueprint);graph.nodes[0].measured={width:220,height:175};graph.nodes[0].selected=true;graph.nodes[0].dragging=true;graph.nodes[0].style={color:'red'};
 const out=toBlueprint(graph);assert.deepEqual(out,blueprint);out.nodes[0].config.path='/different';assert.equal(graph.nodes[0].data.config.path,'/fan');
 assert.deepEqual(parseBlueprint({...blueprint,extra:'ignored',nodes:blueprint.nodes.map(n=>({...n,measured:{width:5,height:5}}))},catalog),blueprint);
});
test('malformed imports are rejected while scientific errors remain recoverable',()=>{
 for(const invalid of [null,{}, {...blueprint,nodes:{}},{...blueprint,nodes:[blueprint.nodes[0],blueprint.nodes[0]]},{...blueprint,nodes:[{...blueprint.nodes[0],type:'unknown'}]},{...blueprint,nodes:[{...blueprint.nodes[0],x:Infinity}]},{...blueprint,nodes:[{...blueprint.nodes[0],config:{path:[]}}]},{...blueprint,edges:[{id:'x',source:'a',target:'absent',relation:'related_to'}]}])assert.throws(()=>parseBlueprint(invalid,catalog),/Invalid blueprint/);
 const incomplete=structuredClone(blueprint);incomplete.nodes[0].config.path='';assert.deepEqual(parseBlueprint(incomplete,catalog),incomplete);
 const saved=memory(JSON.stringify(incomplete));assert.deepEqual(readDraft(()=>saved,catalog).blueprint,incomplete);
 const s=editor();s.getState().replace(incomplete);s.getState().updateNode('a',{config:{path:'/fixed'}});assert.equal(toBlueprint(s.getState()).nodes[0].config.path,'/fixed');
});
test('persistence ignores measurements/selection, debounces semantics and saves at drag stop',async()=>{
 const s=editor(), storage=memory();const p=startPersistence(s,()=>storage,()=>{},null,5);
 s.getState().onNodesChange([{id:'a',type:'dimensions',dimensions:{width:10,height:20}},{id:'a',type:'select',selected:true}]);await wait(15);assert.equal(storage.writes,0);
 s.getState().updateNode('a',{label:'One'});s.getState().updateNode('a',{label:'Two'});await wait(15);assert.equal(storage.writes,1);
 s.getState().onNodesChange([{id:'a',type:'position',position:{x:32.5,y:11.25},dragging:true}]);await wait(15);assert.equal(storage.writes,1);
 s.getState().onNodesChange([{id:'a',type:'position',dragging:false}]);await wait(15);assert.equal(storage.writes,2);assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)!).nodes[0].x,32.5);
 p.stop();
});
test('pending semantic autosave waits for drag completion; unload flushes',async()=>{
 const s=editor(),storage=memory(),p=startPersistence(s,()=>storage,()=>{},null,5);
 s.getState().rename('Pending');s.getState().onNodesChange([{id:'a',type:'position',position:{x:1.5,y:2},dragging:true}]);await wait(15);assert.equal(storage.writes,0);
 p.flush(true);assert.equal(storage.writes,1);p.stop();
});
test('unavailable storage is surfaced and raw damaged drafts are archived before replacement',()=>{
 const s=editor(), messages:string[]=[];const denied=()=>{throw new Error('denied');};
 assert.match(readDraft(denied,catalog).error,/denied/);
 const p=startPersistence(s,denied,(m,error)=>{if(error)messages.push(m);});s.getState().rename('Keep working');p.flush();assert.match(messages[0],/Local save failed/);p.stop();
 const storage=memory('{broken json');const recovered=readDraft(()=>storage,catalog);assert.equal(recovered.raw,'{broken json');assert.equal(recovered.blueprint,null);
 const recovery=startPersistence(s,()=>storage,()=>{},recovered.raw);s.getState().rename('Recovered');recovery.flush();assert.equal(storage.getItem(RECOVERY_KEY),'{broken json');assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)!).name,'Recovered');recovery.stop();
});
test('failed recovery archival never overwrites the original draft',()=>{
 const s=editor(),storage=memory('{broken');const p=startPersistence(s,()=>({getItem:storage.getItem,setItem:(key,value)=>{if(key===RECOVERY_KEY)throw new Error('quota');storage.setItem(key,value);}}),()=>{},'{broken');s.getState().rename('New');p.flush();assert.equal(storage.getItem(STORAGE_KEY),'{broken');p.stop();
});
test('out-of-order responses are discarded even when transport ignores abort',async()=>{
 const s=editor();const first=deferred<Preview>(), second=deferred<Preview>();let calls=0;
 const a=createArtifacts(s,{...api,preview:()=>++calls===1?first.promise:second.promise},10000);const stop=a.start();
 const p1=a.preview(),p2=a.preview();second.resolve({...preview,node_count:22});await p2;first.resolve({...preview,node_count:11});assert.equal(await p1,undefined);assert.equal(a.store.getState().preview.data?.node_count,22);stop();
});
test('layout preserves validation, semantic edits stale it and abort obsolete responses',async()=>{
 const s=editor(),later=deferred<ValidationResult>();let signal:AbortSignal|undefined;let calls=0;
 const a=createArtifacts(s,{...api,validateTemplate:(_,sig)=>{signal=sig;return ++calls===1?Promise.resolve(report):later.promise;}},10000);const stop=a.start();
 await a.validation();s.getState().onNodesChange([{id:'a',type:'position',position:{x:3,y:7},dragging:false}]);assert.equal(a.store.getState().validation.status,'current');
 const old=a.validation();s.getState().updateNode('a',{config:{path:''}});assert.equal(signal?.aborted,true);assert.equal(a.store.getState().validation.status,'stale');later.resolve(report);assert.equal(await old,undefined);assert.equal(a.store.getState().validation.status,'stale');stop();
});
test('preview failures retain the graph and become current after repair',async()=>{
 const s=editor();const a=createArtifacts(s,{...api,preview:async d=>{if(!d.nodes[0].config.path)throw new Error('invalid path');return preview;}},10000);const stop=a.start();
 s.getState().updateNode('a',{config:{path:''}});await a.preview();assert.equal(a.store.getState().preview.status,'failed');assert.equal(s.getState().nodes[0].data.config.path,'');
 s.getState().updateNode('a',{config:{path:'/repaired'}});await a.preview();assert.equal(a.store.getState().preview.status,'current');stop();
});
test('automatic preview debounces semantic changes and ignores canvas-only work',async()=>{
 const s=editor();let calls=0;const a=createArtifacts(s,{...api,preview:async()=>{calls++;return preview;}},5);const stop=a.start();await wait(15);assert.equal(calls,1);
 s.getState().onNodesChange([{id:'a',type:'dimensions',dimensions:{width:50,height:50}},{id:'a',type:'select',selected:true},{id:'a',type:'position',position:{x:12,y:3},dragging:false}]);await wait(15);assert.equal(calls,1);
 s.getState().rename('First');s.getState().rename('Second');await wait(15);assert.equal(calls,2);stop();
});
test('stopping async work prevents late publication',async()=>{
 const s=editor(),late=deferred<Preview>();const a=createArtifacts(s,{...api,preview:()=>late.promise},10000);const stop=a.start();const pending=a.preview();stop();late.resolve(preview);assert.equal(await pending,undefined);assert.notEqual(a.store.getState().preview.status,'current');
});
test('250-node limit, duplicate paths and intentional replacement',()=>{
 const s=editor();s.getState().duplicateNode('a');assert.equal(s.getState().nodes.length,3);assert.equal(s.getState().nodes[2].data.config.path,'/fan_2');
 for(let i=3;i<250;i++)s.getState().addNode('fan',i+.25,i+.75);
 assert.equal(s.getState().nodes.length,250);const before=s.getState();s.getState().addNode('fan',0,0);assert.equal(s.getState(),before);
 assert.equal(parseBlueprint(toBlueprint(s.getState()),catalog).nodes.length,250);
 assert.throws(()=>parseBlueprint({...toBlueprint(s.getState()),nodes:[...toBlueprint(s.getState()).nodes,blueprint.nodes[0]]},catalog),/250/);
 const rev=s.getState().graphRevision;s.getState().replace(blueprint);assert.equal(s.getState().graphRevision,rev+1);assert.equal(s.getState().nodes.length,2);
});

test('pagehide preserves an interrupted drag without scheduling autosave',async()=>{
 const s=editor(),storage=memory(),p=startPersistence(s,()=>storage,()=>{},null,5);
 s.getState().onNodesChange([{id:'a',type:'position',position:{x:99.125,y:21.25},dragging:true}]);await wait(15);assert.equal(storage.writes,0);
 p.flush(true);assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)!).nodes[0].x,99.125);p.stop();
});

// Panel sizing must reserve usable canvas space, independent of blueprint state.
import { resolvePanelSizes, PANEL_MIN, CANVAS_MIN_WIDTH, PANEL_GAP } from '../src/layout/panelSizes';

test('oversized side panels shrink to preserve the canvas at a desktop breakpoint', () => {
 const desired={library:480,inspector:560,artifacts:213};
 const sizes=resolvePanelSizes(desired,1134,600,false,true,true);
 assert.ok(sizes.library>=PANEL_MIN.library && sizes.inspector>=PANEL_MIN.inspector);
 assert.ok(1134-sizes.library-sizes.inspector-2*PANEL_GAP>=CANVAS_MIN_WIDTH-.001);
 assert.deepEqual(desired,{library:480,inspector:560,artifacts:213});
});
test('collapsed side panels do not consume the open panel budget', () => {
 const desired={library:480,inspector:560,artifacts:213};
 const sizes=resolvePanelSizes(desired,1134,600,false,false,true);
 assert.equal(sizes.inspector,560);
 assert.equal(sizes.library,480);
});
test('compact overlays and artifacts respect available space and minimum dimensions', () => {
 const sizes=resolvePanelSizes({library:999,inspector:999,artifacts:999},600,400,true,true,false);
 assert.equal(sizes.library,480);
 assert.equal(sizes.inspector,480);
 assert.equal(sizes.artifacts,154);
 assert.deepEqual(resolvePanelSizes({library:0,inspector:-5,artifacts:0},1000,600,false,true,true), PANEL_MIN);
});
