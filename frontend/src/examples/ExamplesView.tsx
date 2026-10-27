import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BookOpen, Copy, RefreshCcw } from 'lucide-react';
import { examplesApi } from './api';
import type { ExampleSummary } from './api';
import { errorMessage } from '../lib/validation';

export default function ExamplesView() {
  const navigate = useNavigate();
  const [examples, setExamples] = useState<ExampleSummary[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [search, setSearch] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      void examplesApi
        .list(controller.signal)
        .then((items) => {
          if (!controller.signal.aborted) {
            setExamples(items);
            setError('');
          }
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(errorMessage(e));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    load();
    window.addEventListener('focus', load);
    return () => {
      controller.abort();
      window.removeEventListener('focus', load);
    };
  }, [revision]);
  const copy = async (example: ExampleSummary) => {
    setBusy(example.id);
    setError('');
    try {
      const project = await examplesApi.copy(example.id);
      navigate(`/projects/${project.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy('');
    }
  };
  const shown = examples.filter((e) =>
    `${e.name} ${e.description}`.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <main className="feature-page examples-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Example library</span>
          <h1>Examples</h1>
          <p>
            Browse the latest examples without changing them. Copy an example to your projects when
            you want to edit it.
          </p>
        </div>
        <Link className="secondary-btn" to="/projects">
          My projects
        </Link>
      </div>
      <div className="project-filters">
        <label className="project-search">
          <BookOpen size={17} />
          <input
            aria-label="Search examples"
            placeholder="Search examples…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <button className="secondary-btn" onClick={() => setRevision((r) => r + 1)}>
          <RefreshCcw size={15} />
          Refresh examples
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <div className="empty-state" role="status">
          Loading examples…
        </div>
      ) : !shown.length ? (
        <div className="feature-card empty-state">
          <h2>No matching examples</h2>
          <p>Try another search or refresh the library.</p>
        </div>
      ) : (
        <div className="project-list">
          {shown.map((example) => (
            <article className="project-card feature-card" key={example.id}>
              <div className="project-card-main">
                <span className="project-folder">
                  <BookOpen size={24} />
                </span>
                <div>
                  <Link className="project-link" to={`/examples/${example.id}`}>
                    {example.name}
                  </Link>
                  <p className="project-description">{example.description}</p>
                  <div className="project-meta">
                    <span className="example-badge">Read-only example</span>
                    <span>
                      {example.node_count} nodes · {example.edge_count} connections
                    </span>
                  </div>
                </div>
              </div>
              <div className="row-actions">
                <Link className="secondary-btn" to={`/examples/${example.id}`}>
                  View example
                </Link>
                <button
                  className="primary-btn"
                  disabled={!!busy}
                  aria-label={`Copy ${example.name} to my projects`}
                  onClick={() => void copy(example)}
                >
                  <Copy size={16} />
                  {busy === example.id ? 'Copying…' : 'Copy to my projects'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
