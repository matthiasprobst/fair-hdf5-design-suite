import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { CatalogItem } from '../types';
import { useLibraryEditor } from '../library/useLibraryEditor';
import { TurtleImport } from '../library/TurtleImport';
import { TemplateFields } from '../library/TemplateFields';

export default function LibraryEditor({
  template,
  onClose,
}: {
  template?: CatalogItem;
  onClose: () => void;
}) {
  const editor = useLibraryEditor(template, onClose);
  const {
    mode,
    setMode,
    label,
    setLabel,
    category,
    setCategory,
    kind,
    setKind,
    path,
    setPath,
    dtype,
    setDtype,
    dimensions,
    setDimensions,
    color,
    setColor,
    icon,
    setIcon,
    shape,
    setShape,
    analyzed,
    error,
    busy,
    save,
  } = editor;
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="library-overlay" />
        <Dialog.Content className="library-dialog">
          <div className="modal-head">
            <div>
              <Dialog.Title>
                {template ? `Edit ${template.label}` : 'Create library template'}
              </Dialog.Title>
              <Dialog.Description>
                {template
                  ? `Saving creates revision ${(template.revision || 1) + 1}. Existing nodes keep their current revision.`
                  : 'Create a reusable template or import a SHACL Turtle file.'}
              </Dialog.Description>
            </div>
            <Dialog.Close
              disabled={busy}
              className="icon-button"
              aria-label="Close template editor"
            >
              <X size={20} />
            </Dialog.Close>
          </div>
          <div className="library-editor-body">
            <fieldset className="library-editor-fields" disabled={busy}>
              {!template && (
                <div className="library-mode">
                  <button aria-pressed={mode === 'form'} onClick={() => setMode('form')}>
                    Form editor
                  </button>
                  <button aria-pressed={mode === 'turtle'} onClick={() => setMode('turtle')}>
                    SHACL Turtle import
                  </button>
                </div>
              )}
              <div className="library-grid">
                <label>
                  Template name
                  <input value={label} onChange={(e) => setLabel(e.target.value)} />
                </label>
                <label>
                  Category
                  <input value={category} onChange={(e) => setCategory(e.target.value)} />
                </label>
                <label>
                  HDF5 object
                  <select
                    value={kind}
                    onChange={(e) => setKind(e.target.value as 'group' | 'dataset')}
                  >
                    <option value="group">Group</option>
                    <option value="dataset">Dataset</option>
                  </select>
                </label>
                <label>
                  Default HDF5 path
                  <input value={path} onChange={(e) => setPath(e.target.value)} />
                </label>
                <label>
                  Color
                  <select value={color} onChange={(e) => setColor(e.target.value)}>
                    {['blue', 'green', 'purple', 'orange', 'amber', 'coral', 'rose', 'violet'].map(
                      (c) => (
                        <option key={c}>{c}</option>
                      ),
                    )}
                  </select>
                </label>
                <label>
                  Icon
                  <select value={icon} onChange={(e) => setIcon(e.target.value)}>
                    {Array.from(
                      new Set([
                        icon,
                        'metadata',
                        'group',
                        'dataset',
                        'custom_sensor',
                        'process',
                        'experiment_setup',
                      ]),
                    ).map((i) => (
                      <option key={i}>{i}</option>
                    ))}
                  </select>
                </label>
                {kind === 'dataset' && (
                  <>
                    <label>
                      Dataset datatype
                      <select value={dtype} onChange={(e) => setDtype(e.target.value)}>
                        {['float64', 'float32', 'int64', 'int32', 'uint16', 'uint8'].map((d) => (
                          <option key={d}>{d}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Dataset dimensions
                      <input value={dimensions} onChange={(e) => setDimensions(e.target.value)} />
                    </label>
                  </>
                )}
              </div>
              {mode === 'turtle' ? (
                <TurtleImport editor={editor} />
              ) : (
                <label>
                  Profile shape IRI
                  <input value={shape} onChange={(e) => setShape(e.target.value)} />
                </label>
              )}
              {(mode === 'form' || analyzed) && <TemplateFields editor={editor} />}
              {error && (
                <p className="library-error" role="alert">
                  {error}
                </p>
              )}
            </fieldset>
          </div>
          <footer className="modal-footer">
            <button disabled={busy} onClick={onClose}>
              Cancel
            </button>
            <button
              disabled={
                busy || !label.trim() || !category.trim() || (mode === 'turtle' && !analyzed)
              }
              onClick={() => void save()}
            >
              {busy ? 'Processing…' : template ? 'Publish new revision' : 'Save to library'}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
