import { useRef, useState } from 'react';
import {
  ArrowLeft,
  ChevronDown,
  CircleCheck,
  CloudUpload,
  Download,
  FileCode2,
  FileJson2,
  RefreshCcw,
  Save,
  Share2,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { editorStore } from '../store';
import type { EditorCommands } from '../useEditorCommands';

type Props = {
  name: string;
  savedAt: string;
  storageError: string;
  hasRecovery: boolean;
  commands: EditorCommands;
};
export function ProjectToolbar({ name, savedAt, storageError, hasRecovery, commands }: Props) {
  const [menu, setMenu] = useState<'project' | null>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const {
    setDialog,
    onSaveJson,
    onLoadFile,
    exportRecovery,
    reset,
    uploadRef,
    busy,
    runValidation,
    exportShacl,
    exportHdf5,
  } = commands;
  return (
    <div className="project-toolbar">
      <div className="project-ident">
        <button className="project-back" onClick={() => setDialog('projects')} title="Projects">
          <ArrowLeft size={18} />
        </button>
        <input
          aria-label="Experiment title"
          className="project-name"
          value={name === 'Radial fan experiment' ? 'Fan Experiment – HDF5 Design' : name}
          onChange={(e) => editorStore.getState().rename(e.target.value)}
        />
        <span className="draft-tag">Draft</span>
        <span className="saved-text">
          <CircleCheck size={13} /> {storageError ? 'Local save unavailable' : savedAt}
        </span>
      </div>
      <div className="toolbar-buttons">
        <div
          className="project-menu-wrap"
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setMenu(null);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setMenu(null);
              menuTrigger.current?.focus();
              event.stopPropagation();
            }
          }}
        >
          <button
            ref={menuTrigger}
            className="secondary-btn action-small"
            aria-expanded={menu === 'project'}
            aria-controls="project-actions"
            onClick={() => setMenu((m) => (m === 'project' ? null : 'project'))}
          >
            <FileJson2 size={15} /> Project <ChevronDown size={13} />
          </button>
          {menu === 'project' && (
            <div className="project-dropdown" id="project-actions">
              <button
                onClick={() => {
                  onSaveJson();
                  setMenu(null);
                }}
              >
                <Save size={15} /> Export blueprint JSON
              </button>
              <button
                onClick={() => {
                  onLoadFile();
                  setMenu(null);
                }}
              >
                <Upload size={15} /> Import blueprint JSON
              </button>
              {hasRecovery && (
                <button
                  onClick={() => {
                    exportRecovery();
                    setMenu(null);
                  }}
                >
                  <Save size={15} /> Export original draft
                </button>
              )}
              <button
                onClick={() => {
                  reset();
                  setMenu(null);
                }}
              >
                <RefreshCcw size={15} /> Reset example
              </button>
              <button
                onClick={() => {
                  uploadRef.current?.click();
                  setMenu(null);
                }}
              >
                <CloudUpload size={15} /> Validate existing .h5
              </button>
            </div>
          )}
        </div>
        <button className="secondary-btn share-btn" onClick={() => setDialog('share')}>
          <Share2 size={15} /> Share
        </button>
        <button className="validate-btn" disabled={!!busy} onClick={() => runValidation()}>
          <ShieldCheck size={16} /> Validate
        </button>
        <button className="primary-btn" disabled={!!busy} onClick={exportShacl}>
          <Download size={16} /> Export SHACL
        </button>
        <button className="purple-btn" disabled={!!busy} onClick={exportHdf5}>
          <FileCode2 size={16} /> Export HDF5 Template
        </button>
      </div>
    </div>
  );
}
