import { memo } from 'react';
import { useStore } from 'zustand';
import { useProjectSession } from '../projects/EditorSessionContext';
import { CSV_SOURCE } from '../editor/dataNodes';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { nodeTone, ICONS, TYPE_DESCRIPTIONS } from '../lib/ui';
import { Check, FileCode2, GitBranch, MoreHorizontal, Box } from 'lucide-react';

import type { ScientificFlowNode } from '../editor/adapters';
export type { ScientificFlowNode } from '../editor/adapters';

function ScientificNodeBase({ id, data, selected }: NodeProps<ScientificFlowNode>) {
  const session = useProjectSession();
  const input = useStore(session.csv.store, (s) => s.inputs[id]);
  const source = data.blockType === CSV_SOURCE;
  const Icon = ICONS[data.template?.icon || data.blockType] || ICONS[data.blockType] || Box;
  const tone = nodeTone(data.blockType, data.template?.color);
  return (
    <div className={`scientific-node node-${tone} ${selected ? 'active' : ''}`}>
      {!source && (
        <Handle type="target" position={Position.Left} id="in" className="scientific-handle" />
      )}
      {(data.template?.kind === 'dataset' || data.blockType === 'dataset') && (
        <Handle
          type="target"
          position={Position.Left}
          id="data-in"
          className="scientific-handle data-handle"
          style={{ top: '75%' }}
        />
      )}
      <div className="scientific-node-top">
        <span className="node-icon-square">
          <Icon size={19} />
        </span>
        <span className="node-title" title={data.label}>
          {data.label}
        </span>
        <MoreHorizontal className="node-ellipsis" size={16} />
      </div>
      {data.blockType === 'fan' ? (
        <div className="node-fan-drawing">
          <span className="fan-rotor">✹</span>
          <span className="fan-body" />
          <span className="fan-base" />
        </div>
      ) : (
        <div className="node-info-row">
          <span className="node-secondary-icon">
            <Icon size={25} strokeWidth={1.65} />
          </span>
          <div className="node-chip-wrap">
            <span className="node-category-chip">
              {data.template?.category ||
                (source
                  ? 'Data input'
                  : [
                        'pressure_sensor',
                        'temperature_sensor',
                        'torque_sensor',
                        'flow_sensor',
                        'vibration_sensor',
                        'custom_sensor',
                      ].includes(data.blockType)
                    ? 'Sensor'
                    : data.blockType === 'dataset'
                      ? 'Dataset'
                      : data.blockType === 'group'
                        ? 'HDF5'
                        : data.blockType === 'daq'
                          ? 'Equipment'
                          : data.blockType === 'process'
                            ? 'Process'
                            : 'Metadata')}
            </span>
            {!source && (
              <span className="node-profile-chip">
                <Check size={9} /> Profile
              </span>
            )}
          </div>
        </div>
      )}
      {data.blockType === 'fan' && (
        <div className="node-chip-wrap fan-chips">
          <span className="node-category-chip">Equipment</span>
          <span className="node-profile-chip">
            <Check size={9} /> Profile
          </span>
        </div>
      )}
      <div className="node-description">
        {TYPE_DESCRIPTIONS[data.blockType] || data.template?.label}
      </div>
      {(data.template?.kind === 'dataset' || data.blockType === 'dataset') && (
        <div className="node-target">
          <FileCode2 size={10} />
          {
            String(data.config.path || '')
              .split('/')
              .slice(-1)[0]
          }
        </div>
      )}
      {data.blockType === 'group' && (
        <div className="node-target">
          <GitBranch size={10} />
          {String(data.config.path || '')}
        </div>
      )}
      {source ? (
        <>
          <div className="node-target">
            {input?.loading
              ? 'Loading CSV…'
              : input?.error
                ? 'CSV error'
                : input?.preview
                  ? `${input.preview.row_count} rows · ${input.preview.columns.length} columns`
                  : 'Select file again'}
          </div>
          <Handle
            type="source"
            position={Position.Right}
            id="data-out"
            className="scientific-handle data-handle"
          />
        </>
      ) : (
        <Handle type="source" position={Position.Right} id="out" className="scientific-handle" />
      )}
    </div>
  );
}
export const ScientificNode = memo(ScientificNodeBase);
