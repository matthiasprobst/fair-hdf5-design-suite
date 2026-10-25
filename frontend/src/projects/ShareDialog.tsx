import { useEffect, useState } from 'react';
import { UserPlus } from 'lucide-react';
import { projectApi } from './api';
import type { Member, ProjectSummary } from './types';
import { ModalDialog } from '../ui/ModalDialog';
import { errorMessage } from '../lib/validation';

export function ShareDialog({
  project,
  onClose,
  onChanged,
}: {
  project: ProjectSummary;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [members, setMembers] = useState<Member[]>([]),
    [loading, setLoading] = useState(true);
  const [username, setUsername] = useState(''),
    [role, setRole] = useState<'editor' | 'viewer'>('viewer');
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void projectApi
      .members(project.id)
      .then((v) => {
        if (!cancelled) setMembers(v);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [project.id]);
  const change = async (name: string, next: 'editor' | 'viewer' | null) => {
    setBusy(true);
    setError('');
    try {
      setMembers(await projectApi.member(project.id, name, next));
      setUsername('');
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const owner = project.role === 'owner';
  return (
    <ModalDialog
      title={owner ? 'Share project' : 'Project members'}
      description={project.name}
      onClose={onClose}
      busy={busy}
    >
      <p>
        {members.length > 1
          ? 'Shared with the people below. Only one person can edit at a time.'
          : 'Private. Only the owner can access this project.'}
      </p>
      {loading ? (
        <p role="status">Loading members…</p>
      ) : (
        <ul className="member-list">
          {members.map((m) => (
            <li key={m.id}>
              <div>
                <strong>{m.display_name}</strong>
                <small>{m.username}</small>
              </div>
              {m.role === 'owner' ? (
                <span className="role-badge">Owner</span>
              ) : owner ? (
                <div className="row-actions">
                  <select
                    aria-label={`Role for ${m.username}`}
                    value={m.role}
                    disabled={busy}
                    onChange={(e) => void change(m.username, e.target.value as 'editor' | 'viewer')}
                  >
                    <option value="viewer">Can view</option>
                    <option value="editor">Can edit</option>
                  </select>
                  <button
                    className="text-danger"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm(`Remove access for ${m.username}?`))
                        void change(m.username, null);
                    }}
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <span className="role-badge">{m.role === 'editor' ? 'Can edit' : 'Can view'}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {owner && (
        <form
          className="share-form"
          onSubmit={(e) => {
            e.preventDefault();
            void change(username, role);
          }}
        >
          <fieldset className="app-fields" disabled={busy || loading}>
            <label>
              Add an existing user
              <input
                required
                maxLength={64}
                autoComplete="off"
                placeholder="Exact username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label>
              Permission
              <select
                aria-label="Permission"
                value={role}
                onChange={(e) => setRole(e.target.value as 'editor' | 'viewer')}
              >
                <option value="viewer">Can view</option>
                <option value="editor">Can edit</option>
              </select>
            </label>
          </fieldset>
          <button className="primary-btn" disabled={busy || loading || !username.trim()}>
            <UserPlus size={16} />
            Add member
          </button>
        </form>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </ModalDialog>
  );
}
