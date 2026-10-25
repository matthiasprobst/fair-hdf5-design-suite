import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Plus, Users } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { accountApi } from '../projects/api';
import type { User } from '../projects/types';
import { errorMessage } from '../lib/validation';
import { ModalDialog } from '../ui/ModalDialog';

export function UsersView() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]),
    [error, setError] = useState('');
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [creating, setCreating] = useState(false);
  const [username, setUsername] = useState(''),
    [displayName, setDisplayName] = useState(''),
    [admin, setAdmin] = useState(false);
  const [temporary, setTemporary] = useState<{ username: string; password: string } | null>(null);
  const load = useCallback(async () => {
    setError('');
    try {
      setUsers(await accountApi.users());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (user?.is_admin) void load();
  }, [user?.is_admin, load]);
  if (!user?.is_admin) return <Navigate to="/projects" replace />;
  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await work();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="feature-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Administration</span>
          <h1>User accounts</h1>
          <p>Manage access to this installation. Project access is granted by project owners.</p>
        </div>
        <button className="primary-btn" onClick={() => setCreating(true)}>
          <Plus size={17} />
          New account
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p role="status">Loading accounts…</p>
      ) : (
        <div className="feature-card list-card">
          <div className="list-heading">
            <Users size={18} />
            <strong>{users.length} accounts</strong>
          </div>
          {users.map((u) => (
            <article className="account-row" key={u.id}>
              <div>
                <strong>{u.display_name}</strong>
                <small>
                  {u.username} · {u.is_admin ? 'Administrator' : 'User'} ·{' '}
                  {u.active ? 'Active' : 'Inactive'}
                </small>
              </div>
              <div className="row-actions">
                <button
                  className="secondary-btn"
                  disabled={busy || u.id === user.id}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Reset the password for ${u.username}? Existing sessions will be signed out.`,
                      )
                    )
                      void run(async () =>
                        setTemporary({
                          username: u.username,
                          password: await accountApi.resetPassword(u.id),
                        }),
                      );
                  }}
                >
                  Reset password
                </button>
                <button
                  className="secondary-btn"
                  disabled={busy || u.id === user.id}
                  onClick={() => {
                    if (
                      u.active &&
                      !window.confirm(
                        `Deactivate ${u.username}? Their sessions and editing reservations will end.`,
                      )
                    )
                      return;
                    void run(async () => {
                      await accountApi.setActive(u.id, !u.active);
                    });
                  }}
                >
                  {u.active ? 'Deactivate' : 'Activate'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {creating && (
        <ModalDialog
          title="Create account"
          description="A temporary password will be shown once. Share it directly with this person."
          onClose={() => setCreating(false)}
          busy={busy}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                const password = await accountApi.createUser(username, displayName, admin);
                setTemporary({ username, password });
                setCreating(false);
                setUsername('');
                setDisplayName('');
                setAdmin(false);
              });
            }}
          >
            <fieldset className="app-fields" disabled={busy}>
              <label>
                Username
                <input
                  required
                  minLength={3}
                  maxLength={64}
                  pattern="[a-zA-Z0-9][a-zA-Z0-9._\-]{2,63}"
                  autoComplete="off"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
              <label>
                Display name
                <input
                  required
                  maxLength={120}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={admin}
                  onChange={(e) => setAdmin(e.target.checked)}
                />
                Administrator
              </label>
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
                Create account
              </button>
            </div>
          </form>
        </ModalDialog>
      )}
      {temporary && (
        <ModalDialog
          title="Temporary password"
          description={`For ${temporary.username}. This person must change it after signing in.`}
          onClose={() => setTemporary(null)}
        >
          <label className="app-fields">
            Password
            <input readOnly value={temporary.password} onFocus={(e) => e.target.select()} />
          </label>
          <p>Copy this password now. It will not be shown again.</p>
          <div className="dialog-actions">
            <button className="primary-btn" onClick={() => setTemporary(null)}>
              Done
            </button>
          </div>
        </ModalDialog>
      )}
    </main>
  );
}
