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
import { useEditorStore } from '../context';
import { useState as useLocalState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from 'zustand';
import { useProjectSession, useCanEdit } from '../../projects/EditorSessionContext';
import { ShareDialog } from '../../projects/ShareDialog';
import { ModalDialog } from '../../ui/ModalDialog';
import type { EditorCommands } from '../useEditorCommands';

type Props = {
  name: string;
  savedAt: string;
  storageError: string;
  hasRecovery: boolean;
  commands: EditorCommands;
};
export function ProjectToolbar({ name, savedAt, storageError, hasRecovery, commands }: Props) {
  const editorStore = useEditorStore();
  const session = useProjectSession();
  const state = useStore(session.state);
  const canEdit = useCanEdit();
  const navigate = useNavigate();
  const [sharing, setSharing] = useLocalState(false);
  const [details, setDetails] = useLocalState(false);
  const [menu, setMenu] = useState<'project' | null>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const {
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
        <button
          className="project-back"
          aria-label="Back to projects"
          onClick={() => navigate('/projects')}
          title="Projects"
        >
          <ArrowLeft size={18} />
        </button>
        <input
          aria-label="Experiment title"
          className="project-name"
          value={name}
          readOnly={!canEdit}
          maxLength={160}
          onChange={(e) => editorStore.getState().rename(e.target.value)}
        />
        <span className="draft-tag">{state.project.shared ? 'Shared' : 'Private'}</span>
        <span className="role-badge">
          {state.project.role === 'owner'
            ? 'Owner'
            : state.project.role === 'editor'
              ? 'Can edit'
              : 'Can view'}
        </span>
        <span className="saved-text">
          {!storageError && <CircleCheck size={13} />} {savedAt}
        </span>
      </div>
      <div className="toolbar-buttons">
        {state.mode === 'editing' ? (
          <button
            className="secondary-btn"
            disabled={state.busy}
            onClick={() => void session.finish().catch((e) => commands.onNotice(String(e), true))}
          >
            Finish editing
          </button>
        ) : state.project.role !== 'viewer' ? (
          <button className="primary-btn" disabled={state.busy} onClick={() => void session.edit()}>
            {state.busy ? 'Starting…' : 'Edit project'}
          </button>
        ) : (
          <span className="role-badge">View only</span>
        )}
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
                  setDetails(true);
                  setMenu(null);
                }}
              >
                Project details
              </button>
              <button
                onClick={() => {
                  onSaveJson();
                  setMenu(null);
                }}
              >
                <Save size={15} /> Export blueprint JSON
              </button>
              <button
                disabled={!canEdit}
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
                disabled={!canEdit}
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
        <button className="secondary-btn share-btn" onClick={() => setSharing(true)}>
          <Share2 size={15} /> {state.project.role === 'owner' ? 'Share' : 'Members'}
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
      {sharing && (
        <ShareDialog
          project={state.project}
          onClose={() => setSharing(false)}
          onChanged={() => void session.refresh()}
        />
      )}
      {details && (
        <ModalDialog title="Project details" description={name} onClose={() => setDetails(false)}>
          <div className="app-fields">
            <label>
              Description
              <textarea
                rows={5}
                maxLength={3000}
                readOnly={!canEdit}
                value={state.project.description}
                onChange={(e) => session.setDescription(e.target.value)}
              />
            </label>
            <p>
              {canEdit
                ? 'Changes are saved automatically.'
                : 'Start editing to change project details.'}
            </p>
          </div>
        </ModalDialog>
      )}
    </div>
  );
}
