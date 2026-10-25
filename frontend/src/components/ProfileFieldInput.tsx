import type { ProfileField } from '../types';
export default function ProfileFieldInput({
  field,
  value,
  onChange,
}: {
  field: ProfileField;
  value: string;
  onChange: (value: string | boolean | null) => void;
}) {
  const datatype = field.datatype.split('#').pop();
  if (field.choices || datatype === 'boolean') {
    const choices = field.choices || ['true', 'false'];
    return (
      <select
        aria-label={field.label}
        value={value}
        onChange={(e) =>
          onChange(
            e.target.value === ''
              ? null
              : datatype === 'boolean'
                ? e.target.value === 'true'
                : e.target.value,
          )
        }
      >
        <option value="">{field.required ? 'Select a value' : 'Not set'}</option>
        {value && !choices.includes(value) && (
          <option value={value}>{value} (outside profile)</option>
        )}
        {choices.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      aria-label={field.label}
      title={field.description || field.predicate}
      value={value}
      type={datatype === 'date' ? 'date' : datatype === 'IRI' ? 'url' : 'text'}
      inputMode={['integer', 'decimal', 'double'].includes(datatype || '') ? 'decimal' : undefined}
      placeholder={field.required ? 'Required value' : 'Optional'}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
