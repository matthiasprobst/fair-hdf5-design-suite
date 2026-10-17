import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { nodeTone, ICONS, TYPE_DESCRIPTIONS } from '../lib/ui';
import { Check, FileCode2, GitBranch, MoreHorizontal, Box } from 'lucide-react';

import type { ScientificFlowNode } from '../editor/adapters';
export type { ScientificFlowNode } from '../editor/adapters';

function ScientificNodeBase({data, selected}:NodeProps<ScientificFlowNode>) {
  const Icon=ICONS[data.template?.icon || data.blockType] || ICONS[data.blockType] || Box;
  const tone=nodeTone(data.blockType,data.template?.color);
  return (
    <div className={`scientific-node node-${tone} ${selected?'active':''}`}>
      <Handle type="target" position={Position.Left} id="in" className="scientific-handle" />
      <div className="scientific-node-top">
        <span className="node-icon-square"><Icon size={19}/></span>
        <span className="node-title" title={data.label}>{data.label}</span>
        <MoreHorizontal className="node-ellipsis" size={16}/>
      </div>
      {data.blockType==='fan' ? (
        <div className="node-fan-drawing"><span className="fan-rotor">✹</span><span className="fan-body"/><span className="fan-base"/></div>
      ) : (
        <div className="node-info-row">
          <span className="node-secondary-icon"><Icon size={25} strokeWidth={1.65}/></span>
          <div className="node-chip-wrap">
            <span className="node-category-chip">{data.template?.category || (['pressure_sensor','temperature_sensor','torque_sensor','flow_sensor','vibration_sensor','custom_sensor'].includes(data.blockType)?'Sensor':data.blockType==='dataset'?'Dataset':data.blockType==='group'?'HDF5':data.blockType==='daq'?'Equipment':data.blockType==='process'?'Process':'Metadata')}</span>
            <span className="node-profile-chip"><Check size={9}/> Profile</span>
          </div>
        </div>
      )}
      {data.blockType==='fan' && <div className="node-chip-wrap fan-chips"><span className="node-category-chip">Equipment</span><span className="node-profile-chip"><Check size={9}/> Profile</span></div>}
      <div className="node-description">{TYPE_DESCRIPTIONS[data.blockType] || data.template?.label}</div>
      {(data.template?.kind==='dataset' || data.blockType==='dataset') && <div className="node-target"><FileCode2 size={10}/>{String(data.config.path||'').split('/').slice(-1)[0]}</div>}
      {data.blockType==='group' && <div className="node-target"><GitBranch size={10}/>{String(data.config.path||'')}</div>}
      <Handle type="source" position={Position.Right} id="out" className="scientific-handle" />
    </div>
  );
}
export const ScientificNode=memo(ScientificNodeBase);
