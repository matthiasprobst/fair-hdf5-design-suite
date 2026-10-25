import { useEffect, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Database, LogIn } from 'lucide-react';
import { useAuth } from './AuthProvider';
import { errorMessage } from '../lib/validation';

export function SignIn() {
  const auth = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState(''),
    [password, setPassword] = useState('');
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const returnTo: unknown = location.state?.returnTo;
  if (auth.user)
    return (
      <Navigate
        to={
          auth.user.must_change_password
            ? '/account'
            : typeof returnTo === 'string' && returnTo.startsWith('/projects')
              ? returnTo
              : '/projects'
        }
        replace
      />
    );
  return (
    <main className="auth-page">
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          setBusy(true);
          setError('');
          void auth
            .login(username, password)
            .catch((e) => setError(errorMessage(e)))
            .finally(() => setBusy(false));
        }}
      >
        <span className="auth-logo">
          <Database size={30} />
        </span>
        <h1>FAIR Data Design Suite</h1>
        <p>Sign in to your private and shared projects.</p>
        {auth.loading ? (
          <p role="status">Connecting…</p>
        ) : auth.error ? (
          <>
            <p className="form-error" role="alert">
              {auth.error}
            </p>
            <button type="button" onClick={() => void auth.refresh()}>
              Retry connection
            </button>
          </>
        ) : (
          <>
            <fieldset disabled={busy} className="app-fields">
              <label>
                Username
                <input
                  autoComplete="username"
                  required
                  maxLength={64}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            </fieldset>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="primary-btn" disabled={busy}>
              <LogIn size={16} />
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
            <small>Need an account or a password reset? Contact your administrator.</small>
          </>
        )}
      </form>
    </main>
  );
}
export function AccountView() {
  const auth = useAuth();
  const policy = auth.passwordPolicy;
  const navigate = useNavigate();
  const [oldPassword, setOld] = useState(''),
    [newPassword, setNew] = useState(''),
    [repeat, setRepeat] = useState('');
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState(false);
  if (!policy) return <p role="status">Loading password policy…</p>;
  return (
    <main className="feature-page">
      <div className="page-heading">
        <div>
          <h1>Your account</h1>
          <p>
            {auth.user?.display_name} · {auth.user?.username}
          </p>
        </div>
      </div>
      <form
        className="feature-card account-form"
        onSubmit={(e) => {
          e.preventDefault();
          setError('');
          setSaved(false);
          if (newPassword !== repeat) {
            setError('The new passwords do not match.');
            return;
          }
          const wasRequired = auth.user?.must_change_password;
          setBusy(true);
          void auth
            .changePassword(oldPassword, newPassword)
            .then(() => {
              setOld('');
              setNew('');
              setRepeat('');
              setSaved(true);
              if (wasRequired) navigate('/projects');
            })
            .catch((e) => setError(errorMessage(e)))
            .finally(() => setBusy(false));
        }}
      >
        <h2>Change password</h2>
        <p>
          {auth.user?.must_change_password &&
            'Change your temporary password before opening projects. '}
          Use at least {policy.min_length} characters.
        </p>
        <fieldset disabled={busy} className="app-fields">
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={oldPassword}
              onChange={(e) => setOld(e.target.value)}
            />
          </label>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              minLength={policy.min_length}
              maxLength={policy.max_length}
              required
              value={newPassword}
              onChange={(e) => setNew(e.target.value)}
            />
          </label>
          <label>
            Repeat new password
            <input
              type="password"
              autoComplete="new-password"
              required
              maxLength={policy.max_length}
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
            />
          </label>
        </fieldset>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {saved && <p role="status">Password changed.</p>}
        <button className="primary-btn" disabled={busy}>
          {busy ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </main>
  );
}
export function LogoutView() {
  const { logout } = useAuth();
  const [error, setError] = useState('');
  const started = useRef(false);
  // The route is entered only after the editor's navigation guard finishes.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void logout().catch((e) => setError(errorMessage(e)));
  }, [logout]);
  return (
    <main className="feature-page">
      <p role="status">{error || 'Signing out…'}</p>
    </main>
  );
}
