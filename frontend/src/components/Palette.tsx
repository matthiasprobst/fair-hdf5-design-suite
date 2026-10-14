import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, GripVertical, Plus, Search, Shapes, Info } from 'lucide-react';
import type { Catalog, NodeType } from '../types';
import { CATEGORY_ICONS, ICONS } from '../lib/ui';

const order=['Experiment','Sensor','Equipment','Process','HDF5 structure','Metadata'];
const descriptions:Record<string,string>={fan:'Fan, pump, physical system',daq:'Data acquisition',process:'Write to HDF5',group:'Group or container',dataset:'Numerical variable',metadata:'Experimental context'};
interface Props { catalog:Catalog; onAdd:(type:NodeType)=>void; }
export default function Palette({catalog,onAdd}:Props){
  const [search,setSearch]=useState('');
  const [collapsed,setCollapsed]=useState<string[]>([]);
  const groups=useMemo(()=> order.map(category=>({category, items:Object.entries(catalog).filter(([key,info])=>info.category.toLowerCase()===category.toLowerCase()&&(`${info.label} ${key}`.toLowerCase().includes(search.toLowerCase())))})).filter(g=>g.items.length),[catalog,search]);
  return <aside className="palette panel-shell">
    <div className="palette-header"><strong>Building Blocks</strong><Shapes size={17} color="#71819d"/></div>
    <div className="palette-search"><Search size={15}/><input aria-label="Search components" placeholder="Search blocks..." value={search} onChange={e=>setSearch(e.target.value)}/></div>
    <div className="palette-scroll">
      {groups.map(({category,items})=>{
        const CategoryIcon=CATEGORY_ICONS[category]; const closed=collapsed.includes(category)&&!search;
        return <section key={category} className="palette-section">
          <button className="palette-section-heading" onClick={()=>setCollapsed(prev=>prev.includes(category)?prev.filter(c=>c!==category):[...prev,category])}>
            <span className={`palette-section-symbol section-${category.toLowerCase().replaceAll(' ','-')}`}><CategoryIcon size={15}/></span>
            <strong>{category}</strong><span className="palette-count">{items.length}</span>
            {closed?<ChevronRight size={14}/>:<ChevronDown size={14}/ >}
          </button>
          {!closed&&items.map(([type,info])=>{
            const Icon=ICONS[type];return <div key={type} className="palette-item" draggable title="Drag onto the canvas or click + to add" onDragStart={event=>{
              event.dataTransfer.setData('application/x-fair-component',type);event.dataTransfer.setData('text/plain',type);event.dataTransfer.effectAllowed='copy';
            }}>
              <span className={`palette-item-icon icon-${info.color}`}><Icon size={15}/></span>
              <div className="palette-item-name"><span>{info.label}</span>{descriptions[type]&&<small>{descriptions[type]}</small>}</div>
              <GripVertical className="palette-grip" size={13}/>
              <button className="palette-add" aria-label={`Add ${info.label}`} onClick={()=>onAdd(type as NodeType)}><Plus size={14}/></button>
            </div>;
          })}
        </section>;
      })}
      {!groups.length&&<div className="palette-empty">No blocks match “{search}”.</div>}
      <div className="palette-future">
        <span className="palette-future-icon"><Info size={16}/></span>
        <span><strong>Profile library</strong><small>Local example profiles; future NFDI4Ing MPS integration</small></span>
      </div>
    </div>
    <div className="palette-foot"><span className="live-dot"/> Local component catalog <span className="mini-version">v2</span></div>
  </aside>;
}
