import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Copy, RefreshCcw } from 'lucide-react';
import { examplesApi } from './api';
import { api } from '../lib/api';
import { errorMessage } from '../lib/validation';
import { useAuth } from '../auth/AuthProvider';
import { EditorStoreContext } from '../editor/context';
import { EditorSessionContext } from '../projects/EditorSessionContext';
import { EditorView } from '../editor/EditorView';
import { ExamplePreviewSession } from './previewSession';

function Preview({
  session,
  exampleId,
  reload,
}: {
  session: ExamplePreviewSession;
  exampleId: string;
  reload: () => void;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  useEffect(() => session.start(), [session]);
  const copy = async () => {
    setBusy(true);
    setError('');
    try {
      const project = await examplesApi.copy(exampleId);
      navigate(`/projects/${project.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <EditorSessionContext.Provider value={session}>
      <EditorStoreContext.Provider value={session.graph}>
        <EditorView
          toolbar={
            <div className="example-preview-toolbar">
              <div>
                <Link to="/examples">← Examples</Link>
                <strong>{session.graph.getState().name}</strong>
                <span className="example-badge">Read-only example</span>
              </div>
              <div className="row-actions">
                <button className="secondary-btn" onClick={reload}>
                  <RefreshCcw size={14} />
                  Refresh example
                </button>
                <button className="primary-btn" disabled={busy} onClick={() => void copy()}>
                  <Copy size={15} />
                  {busy ? 'Copying…' : 'Copy to my projects'}
                </button>
              </div>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
            </div>
          }
        />
      </EditorStoreContext.Provider>
    </EditorSessionContext.Provider>
  );
}

export default function ExampleRoute() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const [loaded, setLoaded] = useState<{ id: string; session: ExamplePreviewSession } | null>(null);
  const [error, setError] = useState(''),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    setLoaded(null);
    setError('');
    void (async () => {
      try {
        const [{ catalog }, capabilities] = await Promise.all([
          api.catalog(controller.signal),
          api.capabilities(controller.signal),
        ]);
        const example = await examplesApi.get(id, catalog, controller.signal);
        if (!controller.signal.aborted)
          setLoaded({
            id,
            session: new ExamplePreviewSession(example, catalog, capabilities, user.id),
          });
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      }
    })();
    return () => controller.abort();
  }, [id, user, revision]);
  const reload = () => setRevision((r) => r + 1);
  if (error)
    return (
      <main className="feature-page empty-state">
        <h1>Example unavailable</h1>
        <p className="form-error" role="alert">
          {error}
        </p>
        <button onClick={reload}>Retry</button>
        <Link to="/examples">Back to examples</Link>
      </main>
    );
  if (!loaded || loaded.id !== id)
    return (
      <main className="feature-page empty-state" role="status">
        Loading example…
      </main>
    );
  return (
    <Preview key={`${id}-${revision}`} session={loaded.session} exampleId={id} reload={reload} />
  );
}
