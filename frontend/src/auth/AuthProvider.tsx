import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { accountApi } from '../projects/api';
import type { PasswordPolicy, Session, User } from '../projects/types';
import { setCsrfToken } from '../lib/http';
import { errorMessage } from '../lib/validation';

interface AuthState {
  user: User | null;
  passwordPolicy: PasswordPolicy | null;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
}
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [passwordPolicy, setPasswordPolicy] = useState<PasswordPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const pending = useRef<Promise<void> | null>(null);
  const apply = useCallback((session: Session) => {
    setCsrfToken(session.csrf_token);
    setUser(session.user);
    setPasswordPolicy(session.password_policy);
  }, []);
  const refresh = useCallback(() => {
    if (pending.current) return pending.current;
    setLoading(true);
    setError('');
    pending.current = accountApi
      .session()
      .then(apply)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => {
        setLoading(false);
        pending.current = null;
      });
    return pending.current;
  }, [apply]);
  useEffect(() => {
    void refresh();
    const expired = () => {
      setUser(null);
      void refresh();
    };
    window.addEventListener('fair:session-expired', expired);
    return () => window.removeEventListener('fair:session-expired', expired);
  }, [refresh]);
  const login = useCallback(
    async (username: string, password: string) => {
      apply(await accountApi.login(username, password));
    },
    [apply],
  );
  const logout = useCallback(async () => {
    await accountApi.logout();
    setUser(null);
    setCsrfToken('');
    await refresh();
  }, [refresh]);
  const changePassword = useCallback(
    async (oldPassword: string, newPassword: string) => {
      apply(await accountApi.changePassword(oldPassword, newPassword));
    },
    [apply],
  );
  return (
    <AuthContext.Provider
      value={{
        user,
        passwordPolicy,
        loading,
        error,
        refresh,
        login,
        logout,
        changePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('Authentication context is missing.');
  return auth;
}
