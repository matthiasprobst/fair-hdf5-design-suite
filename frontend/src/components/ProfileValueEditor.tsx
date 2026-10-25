import type { ProfileField, ScalarValue, Value } from '../types';
import ProfileFieldInput from './ProfileFieldInput';
export default function ProfileValueEditor({
  field,
  value,
  onChange,
}: {
  field: ProfileField;
  value: Value;
  onChange: (value: Value) => void;
}) {
  const hint = field.class
    ? `Expected an instance of ${field.class}`
    : field.datatype_labels?.length
      ? `Value type: ${field.datatype_labels.join(' or ')}`
      : '';
  const input = (v: ScalarValue | null, change: (v: string | boolean | null) => void) =>
    field.multiline ? (
      <textarea
        aria-label={field.label}
        value={v === null ? '' : String(v)}
        onChange={(e) => change(e.target.value)}
        rows={4}
      />
    ) : (
      <ProfileFieldInput field={field} value={v === null ? '' : String(v)} onChange={change} />
    );
  if (!field.multiple)
    return (
      <>
        {input(Array.isArray(value) ? (value[0] ?? null) : value, onChange)}
        {hint && <small>{hint}</small>}
      </>
    );
  const values = Array.isArray(value)
    ? value.map(String)
    : value === null || value === ''
      ? []
      : [String(value)];
  return (
    <div className="profile-values">
      {hint && <small>{hint}</small>}
      {values.map((v, i) => (
        <div className="profile-value-row" key={i}>
          {input(v, (next) =>
            onChange(values.map((old, j) => (j === i ? String(next ?? '') : old))),
          )}
          <button
            aria-label={`Remove ${field.label} value ${i + 1}`}
            onClick={() => onChange(values.filter((_, j) => i !== j))}
          >
            ×
          </button>
        </div>
      ))}
      <button
        disabled={field.maxCount != null && values.length >= field.maxCount}
        onClick={() => onChange([...values, ''])}
      >
        Add value
      </button>
    </div>
  );
}
