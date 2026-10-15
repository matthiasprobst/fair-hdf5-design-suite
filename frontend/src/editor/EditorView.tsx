import { ReactFlowProvider } from '@xyflow/react';
import { useStore } from 'zustand';
import { CircleCheck, Code2, LoaderCircle } from 'lucide-react';
import { AppShell, GlobalHeader } from '../layout/AppShell';
import Artifacts from '../components/Artifacts';
import Modal from '../components/Modal';
import { artifacts, useEditorLifecycle } from './lifecycle';
import { useEditor } from './store';
import { useEditorCommands } from './useEditorCommands';
import { ProjectToolbar } from './components/ProjectToolbar';
import { EditorFeedback } from './components/EditorFeedback';
import { EditorWorkspace } from './components/EditorWorkspace';
import '../styles/editor.css';

export function EditorView() {
  const initialized = useEditor((state) => state.initialized);
  const name = useEditor((state) => state.name);
  const { apiError, storageError, savedAt, recoveryRaw } = useEditorLifecycle();
  const commands = useEditorCommands(recoveryRaw);
  const artifactState = useStore(artifacts.store);
  const preview = artifactState.preview.status === 'current' ? artifactState.preview.data : null;
  const validation =
    artifactState.validation.status === 'current' ? artifactState.validation.data : null;
  const shacl = artifactState.shacl.status === 'current' ? artifactState.shacl.data || '' : '';
  const requestErrors = Object.values(artifactState)
    .filter((item) => item.status === 'failed')
    .map((item) => item.error);

  if (apiError)
    return (
      <main className="editor-view">
        <div className="api-error">
          <h1>Python backend unavailable</h1>
          <p>{apiError}</p>
          <button onClick={() => window.location.reload()}>Retry connection</button>
          {recoveryRaw !== null && (
            <button onClick={commands.exportRecovery}>Export saved draft</button>
          )}
        </div>
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
    <AppShell
      header={
        <GlobalHeader onNavigate={commands.setDialog} onValidate={() => commands.runValidation()} />
      }
    >
      <main className="editor-view">
        <ProjectToolbar
          name={name}
          savedAt={savedAt}
          storageError={storageError}
          hasRecovery={recoveryRaw !== null}
          commands={commands}
        />
        {(storageError || requestErrors.length > 0) && (
          <div className="editor-error" role="alert">
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
            artifacts={
              <Artifacts
                previewStatus={artifactState.preview.status}
                validationStatus={artifactState.validation.status}
                preview={preview}
                validation={validation}
                busy={commands.busy}
                onRefresh={commands.refresh}
                onShaclPreview={commands.previewShacl}
                onShaclDownload={commands.exportShacl}
                onStructure={commands.previewStructure}
                onHdf5Download={commands.exportHdf5}
                onValidation={() => commands.runValidation()}
                onReport={() => commands.setDialog('validation')}
              />
            }
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
    </AppShell>
  );
}
