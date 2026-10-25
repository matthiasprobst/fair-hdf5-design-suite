import { Plus, Trash2 } from 'lucide-react';
import type { LibraryEditorModel } from './useLibraryEditor';
import type { ProfileField } from '../types';

const XSD = 'http://www.w3.org/2001/XMLSchema#';
const datatypes = [
  'string',
  'boolean',
  'integer',
  'decimal',
  'double',
  'date',
  'dateTime',
  'IRI',
  'reference',
];
const freshField = (): ProfileField => ({
  key: '',
  predicate: '',
  label: '',
  datatype: XSD + 'string',
  required: false,
  minCount: 0,
  maxCount: 1,
  multiple: false,
});
export function TemplateFields({ editor }: { editor: LibraryEditorModel }) {
  const { fields, mode, setFields, updateField } = editor;
  return (
    <section>
      <h3>Fields and HDF5 attribute mapping</h3>
      {fields.map((field, index) => (
        <fieldset className="library-field" key={index}>
          <legend>{field.label || `Field ${index + 1}`}</legend>
          <p className="muted-small">
            {field.kind === 'reference'
              ? `Linked node: ${field.targetShape}`
              : field.multiple
                ? 'Repeatable values'
                : 'Single value'}{' '}
            · Minimum {field.minCount ?? 0} · Maximum {field.maxCount ?? 'unbounded'}
          </p>
          <div className="library-grid">
            <label>
              HDF5 attribute
              <input
                value={field.key}
                onChange={(e) =>
                  setFields((fs) =>
                    fs.map((f) =>
                      f.predicate === field.predicate ? { ...f, key: e.target.value } : f,
                    ),
                  )
                }
              />
            </label>
            <label>
              Label
              <input
                value={field.label}
                readOnly={mode === 'turtle'}
                onChange={(e) => updateField(index, { label: e.target.value })}
              />
            </label>
            <label className="library-wide">
              Property IRI
              <input
                value={field.predicate}
                readOnly={mode === 'turtle'}
                onChange={(e) => updateField(index, { predicate: e.target.value })}
              />
            </label>
            <label>
              Datatype
              <select
                value={field.datatype.replace(XSD, '')}
                disabled={mode === 'turtle'}
                onChange={(e) =>
                  updateField(index, {
                    datatype: e.target.value === 'IRI' ? 'IRI' : XSD + e.target.value,
                  })
                }
              >
                {datatypes
                  .filter((d) => mode === 'turtle' || d !== 'reference')
                  .map((d) => (
                    <option key={d}>{d}</option>
                  ))}
              </select>
            </label>
            <label>
              Default value
              <input
                disabled={field.kind === 'reference'}
                value={field.defaultValue ?? ''}
                onChange={(e) => updateField(index, { defaultValue: e.target.value })}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={field.required}
                disabled={mode === 'turtle'}
                onChange={(e) =>
                  updateField(index, {
                    required: e.target.checked,
                    minCount: e.target.checked ? 1 : 0,
                  })
                }
              />{' '}
              Required
            </label>
          </div>
          {mode === 'form' && (
            <label>
              <input
                type="checkbox"
                checked={!!field.multiple}
                onChange={(e) =>
                  updateField(index, {
                    multiple: e.target.checked,
                    maxCount: e.target.checked ? null : 1,
                  })
                }
              />{' '}
              Allow multiple values
            </label>
          )}
          {mode === 'form' ? (
            <details>
              <summary>Constraints and description</summary>
              <div className="library-grid">
                <label>
                  Description
                  <input
                    value={field.description || ''}
                    onChange={(e) => updateField(index, { description: e.target.value })}
                  />
                </label>
                <label>
                  Choices (one per line)
                  <textarea
                    value={field.choices?.join('\n') || ''}
                    onChange={(e) =>
                      updateField(index, { choices: e.target.value.split('\n').filter(Boolean) })
                    }
                  />
                </label>
                {(
                  [
                    'hasValue',
                    'minInclusive',
                    'maxInclusive',
                    'minExclusive',
                    'maxExclusive',
                    'minLength',
                    'maxLength',
                    'pattern',
                    'flags',
                  ] as const
                ).map((k) => (
                  <label key={k}>
                    {k}
                    <input
                      value={field[k] || ''}
                      onChange={(e) => updateField(index, { [k]: e.target.value })}
                    />
                  </label>
                ))}
              </div>
            </details>
          ) : (
            <p className="muted-small">
              {field.description} {field.choices && `Choices: ${field.choices.join(', ')}`}{' '}
              {field.pattern && `Pattern: ${field.pattern}`}{' '}
              {field.minInclusive && `Minimum: ${field.minInclusive}`}{' '}
              {field.maxInclusive && `Maximum: ${field.maxInclusive}`}
            </p>
          )}
          {mode === 'form' && (
            <button
              aria-label={`Remove field ${index + 1}`}
              onClick={() => setFields((fs) => fs.filter((_, i) => i !== index))}
            >
              <Trash2 size={14} /> Remove field
            </button>
          )}
        </fieldset>
      ))}
      {mode === 'form' && (
        <button onClick={() => setFields((fs) => [...fs, freshField()])}>
          <Plus size={14} /> Add field
        </button>
      )}
    </section>
  );
}
