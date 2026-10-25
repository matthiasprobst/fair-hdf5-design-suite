import { lazy, Suspense } from 'react';
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { AccountView, LogoutView, SignIn } from './auth/AccountViews';
import { AppShell, GlobalHeader } from './layout/AppShell';
import { ProjectsView } from './projects/ProjectsView';
import { UsersView } from './admin/UsersView';
import './styles/projects.css';

const ProjectRoute = lazy(() => import('./projects/ProjectRoute'));
function ApplicationLayout() {
  const { user, loading, error, refresh } = useAuth();
  const location = useLocation(),
    navigate = useNavigate();
  if (loading)
    return (
      <main className="auth-page" role="status">
        Connecting…
      </main>
    );
  if (error)
    return (
      <main className="auth-page">
        <p role="alert">{error}</p>
        <button onClick={() => void refresh()}>Retry connection</button>
      </main>
    );
  if (!user) return <Navigate to="/login" state={{ returnTo: location.pathname }} replace />;
  if (user.must_change_password && !['/account', '/logout'].includes(location.pathname))
    return <Navigate to="/account" replace />;
  const inProject = /^\/projects\/[^/]+$/.test(location.pathname);
  return (
    <AppShell
      header={
        <GlobalHeader
          user={user}
          inProject={inProject}
          onNavigate={(destination) => {
            if (destination === 'projects') navigate('/projects');
            else window.dispatchEvent(new CustomEvent('fair:navigate', { detail: destination }));
          }}
          onValidate={() => window.dispatchEvent(new Event('fair:validate'))}
          onAccount={() => navigate('/account')}
          onAdmin={() => navigate('/admin/users')}
          onLogout={() => navigate('/logout')}
        />
      }
    >
      <Suspense
        fallback={
          <main className="feature-page" role="status">
            Loading project…
          </main>
        }
      >
        <Outlet />
      </Suspense>
    </AppShell>
  );
}
const router = createBrowserRouter([
  { path: '/login', element: <SignIn /> },
  {
    element: <ApplicationLayout />,
    children: [
      { path: '/', element: <Navigate to="/projects" replace /> },
      { path: '/projects', element: <ProjectsView /> },
      { path: '/projects/:id', element: <ProjectRoute /> },
      { path: '/account', element: <AccountView /> },
      { path: '/admin/users', element: <UsersView /> },
      { path: '/logout', element: <LogoutView /> },
      { path: '*', element: <Navigate to="/projects" replace /> },
    ],
  },
]);
export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
