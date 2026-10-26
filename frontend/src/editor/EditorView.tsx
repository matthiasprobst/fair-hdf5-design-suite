import { graphLimitError } from './limits';
import { ReactFlowProvider } from '@xyflow/react';
import { useStore } from 'zustand';
import { CircleCheck, Code2, LoaderCircle } from 'lucide-react';
import Artifacts from '../components/Artifacts';
import Modal from '../components/Modal';
import { useEffect } from 'react';
import { useProjectSession } from '../projects/EditorSessionContext';
import { useNavigate } from 'react-router-dom';
import { useEditor } from './store';
import { useEditorCommands } from './useEditorCommands';
import { ProjectToolbar } from './components/ProjectToolbar';
import { EditorFeedback } from './components/EditorFeedback';
import { EditorWorkspace } from './components/EditorWorkspace';
import '../styles/editor.css';

export function EditorView() {
  const initialized = useEditor((state) => state.initialized);
  const limitError = useEditor((state) =>
    state.initialized ? graphLimitError(state, state.capabilities) : '',
  );
  const name = useEditor((state) => state.name);
  const session = useProjectSession();
  const navigateTo = useNavigate();
  const { artifacts } = session;
  const sessionState = useStore(session.state);
  const savedAt = sessionState.status;
  const storageError = sessionState.error;
  const recoveryRaw = sessionState.recovery;
  const commands = useEditorCommands(recoveryRaw);
  const { setDialog, runValidation } = commands;
  useEffect(() => {
    const navigate = (event: Event) => setDialog((event as CustomEvent).detail);
    const validate = () => runValidation();
    window.addEventListener('fair:navigate', navigate);
    window.addEventListener('fair:validate', validate);
    return () => {
      window.removeEventListener('fair:navigate', navigate);
      window.removeEventListener('fair:validate', validate);
    };
  }, [setDialog, runValidation]);
  const artifactState = useStore(artifacts.store);
  const csvState = useStore(session.csv.store);
  const preview = artifactState.preview.status === 'current' ? artifactState.preview.data : null;
  const validation =
    artifactState.validation.status === 'current' ? artifactState.validation.data : null;
  const shacl = artifactState.shacl.status === 'current' ? artifactState.shacl.data || '' : '';
  const requestErrors = Object.values(artifactState)
    .filter((item) => item.status === 'failed')
    .map((item) => item.error)
    .filter((error) => error !== limitError);

  if (sessionState.accessLost)
    return (
      <main className="feature-page empty-state">
        <h1>Project unavailable</h1>
        <p role="alert">{storageError || 'This project is no longer shared with you.'}</p>
        <button className="secondary-btn" onClick={commands.onSaveJson}>
          Export your draft
        </button>
        <button className="primary-btn" onClick={() => navigateTo('/projects')}>
          Back to projects
        </button>
      </main>
    );

  if (!initialized)
    return (
      <main className="editor-view">
        <div className="app-loading">
          <LoaderCircle className="spin" size={32} />
          <h2>Loading research data workspace</h2>
          <p>Connecting to the Python backend…</p>
        </div>
      </main>
    );

  return (
    <main className="editor-view">
      <ProjectToolbar
        name={name}
        savedAt={savedAt}
        storageError={storageError}
        hasRecovery={recoveryRaw !== null}
        commands={commands}
      />
      {sessionState.project.edit_lock && sessionState.mode === 'view' && (
        <div className="project-session-banner">
          <p>
            {sessionState.project.edit_lock.display_name} is editing this project. You can continue
            viewing.
          </p>
          <button
            onClick={() => void session.refresh().catch((e) => commands.onNotice(String(e), true))}
          >
            Refresh
          </button>
        </div>
      )}
      {(sessionState.mode === 'paused' || sessionState.recoveryAvailable) && (
        <div className="project-session-banner">
          <p>
            {sessionState.mode === 'paused'
              ? 'Editing paused. Preserve your draft before loading another server version.'
              : 'A local recovery draft is available. Start editing to restore it, or save it as a private copy.'}
          </p>
          <div className="row-actions">
            {sessionState.mode === 'editing' && (
              <button onClick={() => session.restore()}>Restore draft</button>
            )}
            <button
              onClick={
                sessionState.mode === 'paused' ? commands.onSaveJson : commands.exportRecovery
              }
            >
              Export draft
            </button>
            <button
              onClick={() =>
                void session
                  .saveCopy()
                  .then(async (copy) => {
                    await session.discard();
                    navigateTo(`/projects/${copy.id}`);
                  })
                  .catch((e) => commands.onNotice(String(e), true))
              }
            >
              Save private copy
            </button>
            {sessionState.mode === 'paused' && (
              <button
                onClick={() => {
                  if (window.confirm('Discard local changes and load the saved server version?'))
                    void session.discard().catch((e) => commands.onNotice(String(e), true));
                }}
              >
                Load server version
              </button>
            )}
          </div>
        </div>
      )}
      {(storageError || limitError || requestErrors.length > 0) && (
        <div className="editor-error" role="alert">
          {limitError && <span>{limitError}</span>}
          {storageError && (
            <span>
              {storageError}{' '}
              {recoveryRaw !== null && (
                <button onClick={commands.exportRecovery}>Export original draft</button>
              )}
            </span>
          )}
          {requestErrors.map((message, index) => (
            <span key={index}>{message}</span>
          ))}
        </div>
      )}
      <ReactFlowProvider>
        <EditorWorkspace
          onNotice={commands.onNotice}
          previewStructure={commands.previewStructure}
          artifacts={(onClose) => (
            <Artifacts
              onClose={onClose}
              previewStatus={artifactState.preview.status}
              validationStatus={artifactState.validation.status}
              preview={preview}
              validation={validation}
              busy={commands.busy}
              onRefresh={commands.refresh}
              onShaclPreview={commands.previewShacl}
              onShaclDownload={commands.exportShacl}
              onMetadataDownload={commands.exportMetadata}
              onStructure={commands.previewStructure}
              onHdf5Download={commands.exportHdf5}
              onDataDownload={commands.exportData}
              dataIssues={session.csv.issues()}
              dataError={csvState.error}
              dataBuilding={csvState.building}
              onValidation={() => commands.runValidation()}
              onReport={() => commands.setDialog('validation')}
            />
          )}
        />
      </ReactFlowProvider>
      <div className="statusbar">
        <span>
          <CircleCheck size={12} /> Python API connected
        </span>
        <span>
          <Code2 size={12} /> Local illustrative metadata profiles · No live MPS connection
        </span>
        <span>Research prototype 0.1.0-beta.1</span>
      </div>
      <input
        type="file"
        accept=".json,application/json"
        hidden
        ref={commands.importRef}
        onChange={(event) => {
          void commands.importBlueprint(event);
        }}
      />
      <input
        type="file"
        accept=".h5,.hdf5,application/x-hdf5"
        hidden
        ref={commands.uploadRef}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) commands.runValidation(file);
          event.target.value = '';
        }}
      />
      <EditorFeedback commands={commands} />
      <Modal
        dialog={commands.dialog}
        onClose={() => commands.setDialog(null)}
        preview={preview}
        ttl={shacl}
        validation={validation}
        name={name}
        onNotice={commands.onNotice}
      />
    </main>
  );
}
