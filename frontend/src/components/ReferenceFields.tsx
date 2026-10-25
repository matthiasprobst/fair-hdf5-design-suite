import type { DesignNode, ProfileField } from '../types';
import type { ScientificFlowNode, ScientificFlowEdge } from '../editor/adapters';
import type { Capabilities } from '../editor/limits';
interface Props {
  node: DesignNode;
  nodes: ScientificFlowNode[];
  edges: ScientificFlowEdge[];
  limits: Capabilities | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  onLink: (field: ProfileField, target: string) => void;
  onCreate: (field: ProfileField) => void;
}
export default function ReferenceFields({
  node,
  nodes,
  edges,
  limits,
  onSelect,
  onRemove,
  onLink,
  onCreate,
}: Props) {
  const fields = node.template?.fields?.filter((f) => f.kind === 'reference') || [];
  const atEdgeLimit = !limits || edges.length >= limits.max_edges;
  return (
    <>
      {fields.map((field) => {
        const links = edges.filter((e) => e.source === node.id && e.data?.field_id === field.id);
        const candidates = nodes.filter(
          (n) =>
            n.id !== node.id &&
            n.data.template?.shape === field.targetShape &&
            !links.some((e) => e.target === n.id),
        );
        return (
          <section className="reference-field" key={field.id}>
            <h4>{field.label}</h4>
            <p>{field.description}</p>
            {links.map((edge) => (
              <div className="reference-link" key={edge.id}>
                <button onClick={() => onSelect(edge.target)}>
                  {nodes.find((n) => n.id === edge.target)?.data.label || 'Missing node'}
                </button>
                <button aria-label={`Remove ${field.label} link`} onClick={() => onRemove(edge.id)}>
                  ×
                </button>
              </div>
            ))}
            <select
              aria-label={`Select ${field.label}`}
              value=""
              disabled={atEdgeLimit}
              onChange={(e) => {
                if (e.target.value) onLink(field, e.target.value);
              }}
            >
              <option value="">Select existing node…</option>
              {candidates.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.data.label}
                </option>
              ))}
            </select>
            <button
              disabled={
                atEdgeLimit ||
                !limits ||
                nodes.length >= limits.max_nodes ||
                !node.template?.related_templates?.[field.targetShape || '']
              }
              onClick={() => {
                onCreate(field);
              }}
            >
              Create linked node
            </button>
            <small>
              {field.qualification === 'qualified'
                ? 'Values matching the referenced profile'
                : 'Every linked value must match the referenced profile'}
              . {links.length} linked.
            </small>
          </section>
        );
      })}
    </>
  );
}
