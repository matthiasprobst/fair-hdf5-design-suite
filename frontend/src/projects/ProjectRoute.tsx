import { useEffect, useRef, useState } from 'react';
import { Link, useBlocker, useParams } from 'react-router-dom';
import { useStore } from 'zustand';
import { useAuth } from '../auth/AuthProvider';
import { api } from '../lib/api';
import { errorMessage } from '../lib/validation';
import { jsonFile } from '../lib/downloads';
import { toBlueprint } from '../editor/adapters';
import { EditorStoreContext } from '../editor/context';
import { EditorSessionContext } from './EditorSessionContext';
import { ProjectEditorSession } from './editorSession';
import { projectApi } from './api';
import { EditorView } from '../editor/EditorView';
import { ModalDialog } from '../ui/ModalDialog';

function SessionView({ session }: { session: ProjectEditorSession }) {
  const state = useStore(session.state);
  const blocker = useBlocker(state.dirty || state.mode === 'editing');
  const [error, setError] = useState('');
  const [leaving, setLeaving] = useState(false);
  const handled = useRef(false);
  useEffect(() => session.start(), [session]);
  useEffect(() => {
    if (blocker.state !== 'blocked') {
      handled.current = false;
      return;
    }
    if (handled.current) return;
    handled.current = true;
    setLeaving(true);
    setError('');
    void session
      .finish()
      .then(() => blocker.proceed())
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLeaving(false));
  }, [blocker, session]);
  return (
    <EditorSessionContext.Provider value={session}>
      <EditorStoreContext.Provider value={session.graph}>
        <EditorView />
        {blocker.state === 'blocked' && (
          <ModalDialog
            title={leaving ? 'Saving your project' : 'Your changes need attention'}
            description="The editing reservation is released after your changes have been saved."
            busy={leaving}
            onClose={() => blocker.reset()}
          >
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <button className="secondary-btn" disabled={leaving} onClick={() => blocker.reset()}>
                Stay
              </button>
              <button
                className="secondary-btn"
                disabled={leaving}
                onClick={() =>
                  jsonFile(toBlueprint(session.graph.getState()), 'project-draft.json')
                }
              >
                Export draft
              </button>
              <button
                className="text-danger"
                disabled={leaving}
                onClick={() => {
                  setLeaving(true);
                  void session
                    .discard()
                    .then(() => blocker.proceed())
                    .catch((e) => {
                      setError(errorMessage(e));
                      setLeaving(false);
                    });
                }}
              >
                Discard and leave
              </button>
              <button
                className="primary-btn"
                disabled={leaving}
                onClick={() => {
                  setLeaving(true);
                  void session
                    .finish()
                    .then(() => blocker.proceed())
                    .catch((e) => {
                      setError(errorMessage(e));
                      setLeaving(false);
                    });
                }}
              >
                {leaving ? 'Saving…' : 'Retry save'}
              </button>
            </div>
          </ModalDialog>
        )}
      </EditorStoreContext.Provider>
    </EditorSessionContext.Provider>
  );
}
export default function ProjectRoute() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const [loaded, setLoaded] = useState<{ id: string; session: ProjectEditorSession } | null>(null);
  const [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    setError('');
    void (async () => {
      try {
        const [{ catalog }, capabilities] = await Promise.all([
          projectApi.catalog(id, controller.signal),
          api.capabilities(controller.signal),
        ]);
        const project = await projectApi.get(id, catalog, controller.signal);
        if (!controller.signal.aborted)
          setLoaded({
            id,
            session: new ProjectEditorSession(project, catalog, capabilities, user.id),
          });
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      }
    })();
    return () => controller.abort();
  }, [id, user, retry]);
  if (error)
    return (
      <main className="feature-page empty-state">
        <h1>Project unavailable</h1>
        <p role="alert">{error}</p>
        <button className="secondary-btn" onClick={() => setRetry((r) => r + 1)}>
          Retry
        </button>
        <Link to="/projects">Back to projects</Link>
      </main>
    );
  if (!loaded || loaded.id !== id)
    return (
      <main className="feature-page empty-state" role="status">
        Loading project…
      </main>
    );
  return <SessionView key={id} session={loaded.session} />;
}
