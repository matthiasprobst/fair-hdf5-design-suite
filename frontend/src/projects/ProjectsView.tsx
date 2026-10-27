import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Copy,
  Folder,
  FolderPlus,
  LockKeyhole,
  Plus,
  Search,
  Share2,
  Trash2,
  Users,
} from 'lucide-react';
import { projectApi } from './api';
import type { ProjectSummary } from './types';
import { ShareDialog } from './ShareDialog';
import { api } from '../lib/api';
import { errorMessage } from '../lib/validation';
import { ModalDialog } from '../ui/ModalDialog';
import { parseBlueprint } from '../editor/blueprint';
import { STORAGE_KEY } from '../editor/persistence';
import { download } from '../lib/downloads';

export function ProjectsView() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const [search, setSearch] = useState(''),
    [filter, setFilter] = useState('all');
  const [creating, setCreating] = useState(false),
    [sharing, setSharing] = useState<ProjectSummary | null>(null);
  const [name, setName] = useState(''),
    [description, setDescription] = useState(''),
    [start, setStart] = useState('empty');
  const [legacy, setLegacy] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const file = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    try {
      setProjects(await projectApi.list());
      setError('');
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    const focus = () => void load();
    window.addEventListener('focus', focus);
    return () => window.removeEventListener('focus', focus);
  }, [load]);
  const run = async (work: () => Promise<void>) => {
    setError('');
    setBusy(true);
    try {
      await work();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const create = async () => {
    let blueprint;
    if (start !== 'empty') {
      const [{ catalog }, capabilities] = await Promise.all([api.catalog(), api.capabilities()]);
      const selected = file.current?.files?.[0];
      if (start === 'import' && !selected) throw new Error('Choose a blueprint JSON file.');
      blueprint = parseBlueprint(
        start === 'example' ? await api.demo() : JSON.parse(await selected!.text()),
        catalog,
        capabilities,
      );
    }
    const created = await projectApi.create({ name, description, blueprint });
    navigate(`/projects/${created.id}`);
  };
  const importLegacy = async () => {
    if (!legacy) return;
    const [{ catalog }, capabilities] = await Promise.all([api.catalog(), api.capabilities()]);
    const blueprint = parseBlueprint(JSON.parse(legacy), catalog, capabilities);
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(legacy))),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    const created = await projectApi.create({
      name: blueprint.name.trim() || 'Recovered project',
      blueprint,
      import_key: `legacy-${hash}`,
    });
    // Preserve the original bytes separately before removing the migration offer.
    localStorage.setItem(`${STORAGE_KEY}-original`, legacy);
    localStorage.removeItem(STORAGE_KEY);
    setLegacy(null);
    navigate(`/projects/${created.id}`);
  };
  const shown = projects.filter(
    (p) =>
      (filter === 'all' || (filter === 'mine' ? p.role === 'owner' : p.role !== 'owner')) &&
      p.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <main className="feature-page projects-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Your workspace</span>
          <h1>Projects</h1>
          <p>
            Keep your designs private or work with selected people. Browse the example library for
            ideas.
          </p>
        </div>
        <div className="row-actions">
          <Link className="secondary-btn" to="/examples">
            Browse examples
          </Link>
          <button
            className="primary-btn"
            onClick={() => {
              setError('');
              setCreating(true);
            }}
          >
            <Plus size={17} />
            New project
          </button>
        </div>
      </div>
      {legacy && (
        <div className="recovery-banner">
          <div>
            <strong>A draft from this browser is available</strong>
            <p>Import it as a private project under your account, or export the original file.</p>
          </div>
          <div className="row-actions">
            <button
              className="secondary-btn"
              disabled={busy}
              onClick={() => void run(importLegacy)}
            >
              Import draft
            </button>
            <button
              className="secondary-btn"
              onClick={() =>
                download(new Blob([legacy], { type: 'application/json' }), 'original-draft.json')
              }
            >
              Export original
            </button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error} <button onClick={() => void load()}>Retry</button>
        </p>
      )}
      <div className="project-filters">
        <div className="filter-tabs" role="group" aria-label="Filter projects">
          {[
            ['all', 'All projects'],
            ['mine', 'My projects'],
            ['shared', 'Shared with me'],
          ].map(([value, label]) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {label}
            </button>
          ))}
        </div>
        <label className="project-search">
          <Search size={17} />
          <input
            aria-label="Search projects"
            placeholder="Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {loading ? (
        <div className="empty-state" role="status">
          Loading projects…
        </div>
      ) : !shown.length ? (
        <div className="feature-card empty-state">
          <FolderPlus size={36} />
          <h2>{projects.length ? 'No matching projects' : 'Your first project starts here'}</h2>
          <p>
            {projects.length
              ? 'Try another search or filter.'
              : 'Create a design, start from the example or import an existing blueprint.'}
          </p>
          {!projects.length && (
            <button className="primary-btn" onClick={() => setCreating(true)}>
              Create project
            </button>
          )}
        </div>
      ) : (
        <div className="project-list">
          {shown.map((p) => (
            <article className="project-card feature-card" key={p.id}>
              <div className="project-card-main">
                <span className="project-folder">
                  <Folder size={24} />
                </span>
                <div>
                  <Link className="project-link" to={`/projects/${p.id}`}>
                    {p.name}
                  </Link>
                  {p.description && <p className="project-description">{p.description}</p>}
                  <div className="project-meta">
                    {p.example_id && <span className="example-badge">Copied example</span>}
                    <span>
                      {p.shared ? <Users size={13} /> : <LockKeyhole size={13} />}
                      {p.shared ? 'Shared' : 'Private'}
                    </span>
                    <span>{p.owner_name}</span>
                    <span className="role-badge">
                      {p.role === 'owner' ? 'Owner' : p.role === 'editor' ? 'Can edit' : 'Can view'}
                    </span>
                    <span>Updated {new Date(p.updated_at * 1000).toLocaleString()}</span>
                  </div>
                </div>
              </div>
              <div className="row-actions">
                <button
                  className="icon-button"
                  aria-label={`Copy ${p.name}`}
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const copy = await projectApi.create({
                        name: `${p.name.slice(0, 150)} (copy)`,
                        source_id: p.id,
                        description: p.description,
                      });
                      navigate(`/projects/${copy.id}`);
                    })
                  }
                >
                  <Copy size={17} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`${p.role === 'owner' ? 'Share' : 'Members of'} ${p.name}`}
                  onClick={() => setSharing(p)}
                >
                  <Share2 size={17} />
                </button>
                {p.role === 'owner' && (
                  <button
                    className="icon-button text-danger"
                    aria-label={`Delete ${p.name}`}
                    disabled={busy}
                    onClick={() => {
                      if (
                        window.confirm(`Permanently delete “${p.name}” and its project templates?`)
                      )
                        void run(async () => {
                          await projectApi.remove(p.id);
                          await load();
                        });
                    }}
                  >
                    <Trash2 size={17} />
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {creating && (
        <ModalDialog
          title="New project"
          description="Your project starts private. You can share it later."
          onClose={() => setCreating(false)}
          busy={busy}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(create);
            }}
          >
            <fieldset className="app-fields" disabled={busy}>
              <label>
                Project name
                <input
                  autoFocus
                  required
                  maxLength={160}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label>
                Description <span className="muted">(optional)</span>
                <textarea
                  maxLength={3000}
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <label>
                Start with
                <select value={start} onChange={(e) => setStart(e.target.value)}>
                  <option value="empty">Empty blueprint</option>
                  <option value="example">Example experiment</option>
                  <option value="import">Import blueprint JSON</option>
                </select>
              </label>
              {start === 'import' && (
                <label>
                  Blueprint file
                  <input type="file" accept=".json,application/json" required ref={file} />
                </label>
              )}
            </fieldset>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <button
                type="button"
                className="secondary-btn"
                disabled={busy}
                onClick={() => setCreating(false)}
              >
                Cancel
              </button>
              <button className="primary-btn" disabled={busy}>
                {busy ? 'Creating…' : 'Create project'}
              </button>
            </div>
          </form>
        </ModalDialog>
      )}
      {sharing && (
        <ShareDialog
          project={sharing}
          onClose={() => setSharing(null)}
          onChanged={() => void load()}
        />
      )}
    </main>
  );
}
