import ProfileValueEditor from './ProfileValueEditor';
import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Box,
  Check,
  CircleHelp,
  ClipboardList,
  Copy,
  ExternalLink,
  FileCode,
  Folder,
  Info,
  Plus,
  Settings2,
  Trash2,
  X,
} from 'lucide-react';
import type { Catalog, CatalogItem, Config, DesignEdge, DesignNode } from '../types';
import { nodeTone, ICONS } from '../lib/ui';
import { relations, requiredFields } from '../editor/rules';

const keyRe = /^[A-Za-z][A-Za-z0-9_]{0,79}$/;
const internal = ['path', 'dtype', 'shape', 'profile_uri', 'required_fields'];
interface Props {
  node: DesignNode | null;
  edge: DesignEdge | null;
  edgeRelations?: string[];
  catalog: Catalog;
  onUpdate: (id: string, patch: { label?: string; config?: Config }) => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
  onEdgeChange: (id: string, relation: string) => void;
  onDeleteEdge: (id: string) => void;
  onUpgrade: (id: string, template: CatalogItem) => Promise<void>;
  upgrading: boolean;
  referenceFields: ReactNode;
  dataFields?: ReactNode;
  readOnly: boolean;
  onClose: () => void;
  onNotice: (text: string, error?: boolean) => void;
}
export default function Inspector({
  node,
  edge,
  edgeRelations = relations,
  catalog,
  onUpdate,
  onDelete,
  onDuplicate,
  onEdgeChange,
  onDeleteEdge,
  onClose,
  onNotice,
  onUpgrade,
  upgrading,
  referenceFields,
  dataFields,
  readOnly,
}: Props) {
  const [upgradePreview, setUpgradePreview] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [required, setRequired] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  if (!node && edge)
    return (
      <aside className="inspector panel-shell">
        <div className="inspector-heading">
          <strong>Connection</strong>
          <button className="icon-button" onClick={onClose} aria-label="Close inspector">
            <X size={17} />
          </button>
        </div>
        <fieldset className="inspector-scroll inspector-fields" disabled={readOnly}>
          <div className="inspector-profile-card">
            <span className="inspector-icon node-blue">
              <Settings2 size={25} />
            </span>
            <div>
              <strong>Experiment relationship</strong>
              <p>Connections describe the scientific workflow, not the HDF5 hierarchy.</p>
            </div>
          </div>
          <div className="form-field">
            <label>Relation</label>
            <select
              disabled={!!edge.predicate}
              value={edge.relation}
              onChange={(e) => onEdgeChange(edge.id, e.target.value)}
            >
              {(edge.predicate || !edgeRelations.includes(edge.relation)) && (
                <option value={edge.relation}>{edge.relation}</option>
              )}
              {edgeRelations.map((x) => (
                <option value={x} key={x}>
                  {x.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </div>
          <div className="technical-note">
            <Info size={15} /> Round-port relationships describe the experiment and declared
            provenance. Use square ports to map CSV columns into HDF5 datasets. File paths are
            configured on the target nodes.
          </div>
          <button className="delete-button" onClick={() => onDeleteEdge(edge.id)}>
            <Trash2 size={15} /> Delete connection
          </button>
        </fieldset>
      </aside>
    );
  if (!node)
    return (
      <aside className="inspector panel-shell">
        <div className="inspector-heading">
          <strong>Node Configuration</strong>
          <button className="icon-button" onClick={onClose} aria-label="Close inspector">
            <X size={17} />
          </button>
        </div>
        <div className="inspector-empty">
          <Box size={44} />
          <h3>Select a building block</h3>
          <p>Click any node on the canvas to configure its metadata and HDF5 mapping.</p>
        </div>
      </aside>
    );
  const info = node.template || catalog[node.type];
  const latest = catalog[node.type];
  const Icon = ICONS[info?.icon] || ICONS[node.type] || Box;
  const tone = nodeTone(node.type, info?.color);
  const c = node.config;
  const req = requiredFields(node.type, c, { [node.type]: info });
  const fields = Array.from(
    new Set([
      ...Object.keys(c),
      ...(info.fields || []).filter((f) => f.kind !== 'reference').map((f) => f.key),
    ]),
  ).filter(
    (k) =>
      !internal.includes(k) &&
      (!['quantity', 'unit'].includes(k) || !!info.fields?.some((f) => f.key === k)),
  );
  const customReq = String(c.required_fields || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
  const value = (k: string) => (c[k] === undefined || c[k] === null ? '' : String(c[k]));
  const update = (key: string, v: string) => onUpdate(node.id, { config: { [key]: v } });
  const addField = () => {
    const k = newKey.trim();
    if (!keyRe.test(k) || internal.includes(k) || k in c) {
      onNotice('Use a unique attribute name: letters, digits and underscores.', true);
      return;
    }
    onUpdate(node.id, {
      config: { [k]: '', required_fields: [...customReq, ...(required ? [k] : [])].join(',') },
    });
    setNewKey('');
    onNotice(`Field “${k}” added${required ? ' as a requirement' : ''}.`);
  };
  const removeCustom = (k: string) => {
    const newConfig = {
      ...c,
      [k]: null,
      required_fields: customReq.filter((f) => f !== k).join(','),
    };
    onUpdate(node.id, { config: newConfig });
  };
  const hdf5 = Boolean(info?.kind);
  return (
    <aside className="inspector panel-shell">
      <div className="inspector-heading">
        <strong>Node Configuration</strong>
        <button className="icon-button" onClick={onClose} aria-label="Close inspector">
          <X size={17} />
        </button>
      </div>
      <fieldset className="inspector-scroll inspector-fields" disabled={readOnly}>
        <div className="inspector-profile-card">
          <span className={`inspector-icon node-${tone}`}>
            <Icon size={29} strokeWidth={1.5} />
          </span>
          <div>
            <strong>{node.label}</strong>
            <div className="inspector-badges">
              <span className={`pill pill-${tone}`}>{info?.category}</span>
              <span className="pill pill-green">
                <Check size={11} /> Local profile
              </span>
            </div>
          </div>
        </div>
        <div className="form-field">
          <label>Block name</label>
          <input
            value={node.label}
            onChange={(e) => onUpdate(node.id, { label: e.target.value })}
          />
        </div>
        <div className="form-field">
          <label>Attached profile</label>
          <div className="profile-select-wrap">
            <span className="readonly-profile">{info?.profile || 'Not assigned'}</span>
            <button
              onClick={() =>
                window.open('https://profiles.nfdi4ing.de/', '_blank', 'noopener,noreferrer')
              }
              title="Open external Metadata Profile Service"
            >
              <ExternalLink size={15} />
            </button>
          </div>
          <small>Revision {info.revision || 1} · Stored with this design</small>
          {latest?.revision && latest.revision > (info.revision || 1) && (
            <button onClick={() => setUpgradePreview((v) => !v)}>
              Review revision {latest.revision}
            </button>
          )}
          {upgradePreview && (
            <div className="technical-note">
              <div>
                <strong>Update to revision {latest.revision}</strong>
                <p>
                  New fields:{' '}
                  {(latest.fields || [])
                    .filter((f) => !info.fields?.some((old) => old.key === f.key))
                    .map((f) => f.key)
                    .join(', ') || 'None'}
                </p>
                <p>
                  Removed fields:{' '}
                  {(info.fields || [])
                    .filter((f) => !latest.fields?.some((next) => next.key === f.key))
                    .map((f) => f.key)
                    .join(', ') || 'None'}
                  . Existing values are retained.
                </p>
                <p>
                  Required: {latest.required.join(', ') || 'None'}. Rules and HDF5 mapping may
                  change.
                </p>
                <details>
                  <summary>Review new rules</summary>
                  <pre style={{ whiteSpace: 'pre-wrap' }}>{latest.profile_ttl}</pre>
                </details>
                <button
                  disabled={upgrading}
                  onClick={async () => {
                    await onUpgrade(node.id, latest);
                    setUpgradePreview(false);
                  }}
                >
                  {upgrading ? 'Validating…' : 'Apply revision and validate'}
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="form-field">
          <label>Profile URI (optional override)</label>
          <input
            value={value('profile_uri')}
            placeholder="https://example.org/profile/..."
            onChange={(e) => update('profile_uri', e.target.value)}
          />
        </div>
        {hdf5 && (
          <div className="form-field">
            <label>Target path (HDF5)</label>
            <div className="input-icon-wrap">
              <input
                spellCheck={false}
                value={value('path')}
                onChange={(e) => update('path', e.target.value)}
              />
              <Folder size={15} />
            </div>
            <small>Explicit physical location, independent of graph connections.</small>
          </div>
        )}
        {!info.fields?.some((f) => ['unit', 'quantity'].includes(f.key)) &&
          (node.type === 'dataset' || node.type.endsWith('_sensor')) && (
            <>
              <div className="form-field">
                <label>Quantity (measured)</label>
                <input
                  value={value('quantity')}
                  onChange={(e) => update('quantity', e.target.value)}
                />
              </div>
              <div className="form-field">
                <label>Physical unit</label>
                <input
                  value={value('unit')}
                  placeholder="e.g. Pa, m/s, K"
                  onChange={(e) => update('unit', e.target.value)}
                />
              </div>
            </>
          )}
        {info.kind === 'dataset' && (
          <div className="dataset-settings">
            <div className="form-field">
              <label>Dataset data type</label>
              <select
                value={value('dtype') || 'float64'}
                onChange={(e) => update('dtype', e.target.value)}
              >
                {['float64', 'float32', 'int64', 'int32', 'uint16', 'uint8', 'string'].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label>Dataset shape</label>
              <input
                value={value('shape') || '0'}
                onChange={(e) => update('shape', e.target.value)}
              />
              <small>Comma-separated dimensions; first dimension may be 0 (resizable).</small>
            </div>
          </div>
        )}
        {dataFields}
        <div className="inspector-section-title">
          <ClipboardList size={15} /> Required metadata <span>{req.length}</span>
        </div>
        <div className="required-chips">
          {req.length ? (
            req.map((k) => (
              <span
                key={k}
                className="req-chip"
                title={
                  customReq.includes(k)
                    ? 'User-defined required field'
                    : 'Built-in profile requirement'
                }
              >
                {k.replaceAll('_', ' ')}
                {customReq.includes(k) && (
                  <button
                    aria-label={`Remove requirement ${k}`}
                    onClick={() =>
                      update('required_fields', customReq.filter((x) => x !== k).join(','))
                    }
                  >
                    <X size={11} />
                  </button>
                )}
              </span>
            ))
          ) : (
            <span className="muted-small">No mandatory attributes</span>
          )}
        </div>
        {referenceFields}
        <div className="metadata-values">
          <div className="metadata-heading">
            Metadata values <span>{readOnly ? 'Read only' : 'Editable'}</span>
          </div>
          {fields.map((k) => (
            <div key={k} className="metadata-row">
              <label title={k}>
                {info.fields?.find((f) => f.key === k)?.label || k.replaceAll('_', ' ')}
              </label>
              <div className="metadata-input-row">
                {info.fields?.find((f) => f.key === k) ? (
                  <ProfileValueEditor
                    field={info.fields.find((f) => f.key === k)!}
                    value={c[k] ?? null}
                    onChange={(v) => onUpdate(node.id, { config: { [k]: v } })}
                  />
                ) : (
                  <input
                    value={value(k)}
                    onChange={(e) => update(k, e.target.value)}
                    placeholder={req.includes(k) ? 'Required value' : 'Optional'}
                  />
                )}
                {!info.required.includes(k) && (
                  <button aria-label={`Remove ${k}`} onClick={() => removeCustom(k)}>
                    <X size={13} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="add-metadata">
          <input
            aria-label="New metadata field"
            placeholder="new_attribute"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') addField();
            }}
          />
          <button onClick={addField}>
            <Plus size={14} /> Add field
          </button>
        </div>
        <label className="mini-check">
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
          />{' '}
          Make newly added field required
        </label>
        <button className="advanced-toggle" onClick={() => setAdvanced((v) => !v)}>
          <span>
            <FileCode size={15} /> Validation and technical details
          </span>
          <span>{advanced ? '−' : '+'}</span>
        </button>
        {advanced && (
          <div className="advanced-content">
            <p>
              The Python backend generates constraints for an RDF projection of the HDF5 file and
              separately checks HDF5 paths, types, dimensions, and attributes.
            </p>
            <p>
              <strong>Profile ID:</strong> {info.profile}
            </p>
            <p>
              <strong>Node ID:</strong> {node.id}
            </p>
            <p>
              <strong>Materialization:</strong> {info.kind || 'None'}
            </p>
          </div>
        )}
        <div className="inspector-footer-actions">
          <button onClick={() => onDuplicate(node.id)}>
            <Copy size={14} /> Duplicate
          </button>
          <button className="destructive" onClick={() => onDelete(node.id)}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
        <p className="inspector-disclaimer">
          <CircleHelp size={13} /> Metadata conformance does not imply complete FAIR compliance or
          scientific correctness.
        </p>
      </fieldset>
    </aside>
  );
}
